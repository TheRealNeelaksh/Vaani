import asyncio
import base64
import json
import logging
import numpy as np
import torch
import tempfile
import wave
import os
import re
from typing import List

from channels.generic.websocket import AsyncWebsocketConsumer
from dotenv import load_dotenv

from brain.mistralAPI_brain import stream_mistral_chat_async
from stt.sarvamSTT import transcribe_audio
from logs.logger import log_conversation
from tts.elevenLabs.xiTTS import stream_tts_audio

# ==============================================================================
# 1. CONFIGURATION & SETUP
# ==============================================================================

load_dotenv()
logging.basicConfig(level=logging.INFO)
SAMPLE_RATE = 16000

# ==============================================================================
# 2. VAD MODULE
# ==============================================================================
try:
    model, utils = torch.hub.load(
        repo_or_dir='vad_model/silero-vad-master', model='silero_vad',
        source='local', trust_repo=True
    )
    (get_speech_timestamps, _, _, VADIterator, _) = utils
    logging.info("Local PyTorch VAD model loaded successfully.")
except Exception as e:
    logging.error(f"FATAL: Could not load local VAD model. Error: {e}")
    # In a real app, you might want to handle this more gracefully
    # For now, we'll let it raise the exception during startup.
    raise

# ==============================================================================
# 3. CHANNELS CONSUMER LOGIC
# ==============================================================================

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        app_password = os.getenv("APP_PASSWORD")
        password_from_client = self.scope['query_string'].decode().split('password=')[1].split('&')[0]
        self.selected_character = self.scope['query_string'].decode().split('character=')[1].split('&')[0]
        logging.info(f"New connection attempt for character: {self.selected_character}")

        if app_password and password_from_client != app_password:
            await self.close(code=4001)
            return

        await self.accept()

        if self.selected_character == "Veer":
            system_prompt = {"role": "system", "content": "You are Veer, a calm, focused, and strategic thinking partner from the TAARA Network. You are helpful and provide clear, logical advice. You speak concisely and directly. Avoid emotional language and stick to facts and rational analysis."}
        else: # Default to Taara
            system_prompt = {"role": "system", "content": "You are Taara, a witty, warm, and supportive best friend from the TAARA Network. You are empathetic and always ready for a deep chat or a playful joke. You speak in a friendly, engaging manner, often using a mix of English and Hindi (Hinglish)."}

        self.conversation_history: List[dict] = [system_prompt]

        self.vad_iterator = VADIterator(model, threshold=0.5)
        self.audio_buffer = torch.empty(0, dtype=torch.float32)
        self.speech_audio_buffer = []
        self.is_speaking = False
        self.end_speech_timer = None

    async def disconnect(self, close_code):
        logging.info(f"WebSocket connection closed for {self.selected_character}.")

    async def receive(self, text_data=None, bytes_data=None):
        message = json.loads(text_data)
        if message['type'] == 'audio_chunk':
            await self._handle_audio_chunk(message['data'])
        elif message['type'] == 'text_message':
            await self._process_text_message(message['data'])

    async def _handle_audio_chunk(self, audio_data):
        audio_data_bytes = base64.b64decode(audio_data)
        new_audio_tensor = torch.from_numpy(np.frombuffer(audio_data_bytes, dtype=np.float32).copy())
        self.audio_buffer = torch.cat([self.audio_buffer, new_audio_tensor])

        VAD_WINDOW_SIZE = 512
        while self.audio_buffer.shape[0] >= VAD_WINDOW_SIZE:
            current_window = self.audio_buffer[:VAD_WINDOW_SIZE]
            self.audio_buffer = self.audio_buffer[VAD_WINDOW_SIZE:]

            if self.is_speaking:
                self.speech_audio_buffer.append(current_window)

            speech_dict = self.vad_iterator(current_window, return_seconds=True)

            if speech_dict:
                if 'start' in speech_dict:
                    if not self.is_speaking:
                        self.is_speaking = True
                        self.speech_audio_buffer = [current_window]
                    if self.end_speech_timer and not self.end_speech_timer.done():
                        self.end_speech_timer.cancel()

                if 'end' in speech_dict and self.is_speaking:
                    if not self.end_speech_timer or self.end_speech_timer.done():
                        self.end_speech_timer = asyncio.create_task(self._start_end_speech_timer())

    async def _start_end_speech_timer(self):
        await asyncio.sleep(0.8)
        if self.is_speaking:
            await self._process_utterance()

    async def _process_utterance(self):
        if not self.speech_audio_buffer:
            self.is_speaking = False
            return

        self.is_speaking = False
        full_utterance_tensor = torch.cat(self.speech_audio_buffer)
        self.speech_audio_buffer = []
        speech_bytes = (full_utterance_tensor * 32767).to(torch.int16).numpy().tobytes()

        asyncio.create_task(self._process_voice_message(speech_bytes))

    async def _safe_send(self, message: dict):
        try:
            await self.send(text_data=json.dumps(message))
        except RuntimeError:
            logging.warning("WebSocket is closed.")

    async def _tts_consumer(self, text_queue: asyncio.Queue):
        await self._safe_send({"type": "tts_start"})
        while True:
            try:
                sentence = await text_queue.get()
                if sentence is None:
                    break
                if not sentence.strip():
                    continue
                async for audio_chunk in stream_tts_audio(sentence, self.selected_character):
                    await self.send(bytes_data=audio_chunk)
                text_queue.task_done()
            except RuntimeError:
                break
            except Exception as e:
                logging.error(f"Error in TTS consumer: {e}")
                break
        await self._safe_send({"type": "tts_end"})

    async def _llm_producer(self, transcript: str, text_queue: asyncio.Queue):
        full_reply, sentence_buffer = "", ""
        sentence_delimiters = re.compile(r'(?<=[.?!])\s*')
        try:
            async for text_chunk in stream_mistral_chat_async(transcript, self.conversation_history):
                full_reply += text_chunk
                sentence_buffer += text_chunk
                await self._safe_send({"type": "ai_text_chunk", "data": text_chunk})
                parts = sentence_delimiters.split(sentence_buffer)
                if len(parts) > 1:
                    for i in range(len(parts) - 1):
                        if parts[i].strip():
                            await text_queue.put(parts[i].strip())
                    sentence_buffer = parts[-1]
            if sentence_buffer.strip():
                await text_queue.put(sentence_buffer.strip())
            log_conversation("AI", full_reply)
        except Exception as e:
            logging.error(f"Error in LLM producer: {e}")
            await text_queue.put("I'm sorry, I'm having a little trouble connecting right now.")
        finally:
            await text_queue.put(None)

    async def _process_voice_message(self, audio_bytes: bytes):
        tmp_wav_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav_path = tmp_wav.name
                with wave.open(tmp_wav, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(audio_bytes)

            transcript = await asyncio.to_thread(transcribe_audio, tmp_wav_path)
            if not transcript or not transcript.strip():
                return

            await self._safe_send({"type": "user_transcript", "data": transcript})
            log_conversation("User (voice)", transcript)

            text_queue = asyncio.Queue()
            tts_task = asyncio.create_task(self._tts_consumer(text_queue))
            llm_task = asyncio.create_task(self._llm_producer(transcript, text_queue))
            await asyncio.gather(llm_task, tts_task)
        finally:
            if tmp_wav_path and os.path.exists(tmp_wav_path):
                os.remove(tmp_wav_path)

    async def _process_text_message(self, transcript: str):
        log_conversation("User (text)", transcript)
        full_reply = ""
        try:
            async for text_chunk in stream_mistral_chat_async(transcript, self.conversation_history):
                full_reply += text_chunk
                await self._safe_send({"type": "ai_text_chunk", "data": text_chunk})
            log_conversation("AI (text)", full_reply)
        except Exception as e:
            logging.error(f"Error in text message LLM producer: {e}")
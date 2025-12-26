# server.py

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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from brain.mistralAPI_brain import stream_mistral_chat_async, summarize_text_async
from stt.sarvamSTT import transcribe_audio
from logs.logger import log_conversation
from tts.elevenLabs.xiTTS import stream_tts_audio

# ==============================================================================
# 1. CONFIGURATION & SETUP
# ==============================================================================

load_dotenv()
logging.basicConfig(level=logging.INFO)
app = FastAPI()
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")
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
    exit()

# ==============================================================================
# 3. FASTAPI SERVER LOGIC
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def safe_send(websocket: WebSocket, message: dict):
    try: await websocket.send_text(json.dumps(message))
    except RuntimeError: logging.warning("WebSocket is closed.")

# --- Processing Pipelines ---
async def tts_consumer(websocket: WebSocket, text_queue: asyncio.Queue, character_name: str):
    await safe_send(websocket, {"type": "tts_start"})
    while True:
        try:
            sentence = await text_queue.get()
            if sentence is None: break
            if not sentence.strip(): continue
            async for audio_chunk in stream_tts_audio(sentence, character_name):
                await websocket.send_bytes(audio_chunk)
            text_queue.task_done()
        except RuntimeError: break
        except Exception as e: logging.error(f"Error in TTS consumer: {e}"); break
    await safe_send(websocket, {"type": "tts_end"})

async def llm_producer(websocket: WebSocket, transcript: str, conversation_history: list, text_queue: asyncio.Queue):
    full_reply = ""
    try:
        # Stream text to UI immediately, but buffer for Audio logic
        async for text_chunk in stream_mistral_chat_async(transcript, conversation_history):
            full_reply += text_chunk
            await safe_send(websocket, {"type": "ai_text_chunk", "data": text_chunk})

        log_conversation("AI", full_reply)

        # --- Audio Logic with Summarization ---
        # 40 words is roughly 2-3 sentences. If longer, summarize.
        if len(full_reply.split()) > 40:
            summary = await summarize_text_async(full_reply)
            logging.info(f"Summarizing long response. Original: {len(full_reply)} chars. Summary: {summary}")
            await text_queue.put(summary)
        else:
            await text_queue.put(full_reply)

    except Exception as e:
        logging.error(f"Error in LLM producer: {e}")
        await text_queue.put("I'm sorry, I'm having a little trouble connecting right now.")
    finally:
        await text_queue.put(None)

async def _process_voice_message(websocket: WebSocket, audio_bytes: bytes, conversation_history: list, character_name: str):
    tmp_wav_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav_path = tmp_wav.name
            with wave.open(tmp_wav, 'wb') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_bytes)
        
        transcript = await asyncio.to_thread(transcribe_audio, tmp_wav_path)
        if not transcript or not transcript.strip(): return

        await safe_send(websocket, {"type": "user_transcript", "data": transcript})
        log_conversation("User (voice)", transcript)
        
        text_queue = asyncio.Queue()
        tts_task = asyncio.create_task(tts_consumer(websocket, text_queue, character_name))
        llm_task = asyncio.create_task(llm_producer(websocket, transcript, conversation_history, text_queue))
        await asyncio.gather(llm_task, tts_task)
    finally:
        if tmp_wav_path and os.path.exists(tmp_wav_path): os.remove(tmp_wav_path)

async def _process_text_message(websocket: WebSocket, transcript: str, conversation_history: list):
    log_conversation("User (text)", transcript)
    full_reply = ""
    try:
        async for text_chunk in stream_mistral_chat_async(transcript, conversation_history):
            full_reply += text_chunk
            await safe_send(websocket, {"type": "ai_text_chunk", "data": text_chunk})
        log_conversation("AI (text)", full_reply)
    except Exception as e:
        logging.error(f"Error in text message LLM producer: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    app_password = os.getenv("APP_PASSWORD")
    password_from_client = websocket.query_params.get("password")
    selected_character = websocket.query_params.get("character", "Taara")
    logging.info(f"New connection attempt for character: {selected_character}")

    if app_password and password_from_client != app_password:
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    await websocket.accept()
    
    if selected_character == "Veer":
        system_prompt = {"role": "system", "content": """You are Veer, a calm, focused, and strategic thinking partner from the TAARA Network. 
                         You are helpful and provide clear, logical advice. You speak concisely and directly. 
                         Avoid emotional language and stick to facts and rational analysis."""}
    else: # Default to Taara
        system_prompt = {"role": "system", "content": """You are Taara, a witty, warm, and supportive best friend from the TAARA Network. 
                         You are empathetic and always ready for a deep chat or a playful joke. 
                         You speak in a friendly, engaging manner, often using a mix of English and Hindi (Hinglish)."""}
    
    conversation_history: List[dict] = [system_prompt]
    
    vad_iterator = VADIterator(model, threshold=0.5)
    audio_buffer = torch.empty(0, dtype=torch.float32)
    speech_audio_buffer = []
    is_speaking = False
    end_speech_timer = None
    
    async def process_utterance():
        nonlocal is_speaking, speech_audio_buffer
        if not speech_audio_buffer: 
            is_speaking = False
            return
        is_speaking = False
        full_utterance_tensor = torch.cat(speech_audio_buffer)
        speech_audio_buffer = []
        speech_bytes = (full_utterance_tensor * 32767).to(torch.int16).numpy().tobytes()
        asyncio.create_task(_process_voice_message(websocket, speech_bytes, conversation_history, selected_character))

    async def start_end_speech_timer():
        await asyncio.sleep(0.8)
        if is_speaking: await process_utterance()

    try:
        while True:
            message_text = await websocket.receive_text()
            message = json.loads(message_text)
            if message['type'] == 'audio_chunk':
                audio_data_bytes = base64.b64decode(message['data'])
                new_audio_tensor = torch.from_numpy(np.frombuffer(audio_data_bytes, dtype=np.float32).copy())
                audio_buffer = torch.cat([audio_buffer, new_audio_tensor])
                VAD_WINDOW_SIZE = 512
                while audio_buffer.shape[0] >= VAD_WINDOW_SIZE:
                    current_window = audio_buffer[:VAD_WINDOW_SIZE]
                    audio_buffer = audio_buffer[VAD_WINDOW_SIZE:]
                    if is_speaking: speech_audio_buffer.append(current_window)
                    speech_dict = vad_iterator(current_window, return_seconds=True)
                    if speech_dict:
                        if 'start' in speech_dict:
                            if not is_speaking:
                                is_speaking = True
                                speech_audio_buffer = [current_window]
                            if end_speech_timer and not end_speech_timer.done(): end_speech_timer.cancel()
                        if 'end' in speech_dict and is_speaking:
                            if not end_speech_timer or end_speech_timer.done():
                               end_speech_timer = asyncio.create_task(start_end_speech_timer())
            elif message['type'] == 'text_message':
                asyncio.create_task(_process_text_message(websocket, message['data'], conversation_history))
    except WebSocketDisconnect:
        logging.info(f"WebSocket connection closed for {selected_character}.")
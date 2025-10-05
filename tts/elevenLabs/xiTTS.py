# tts/elevenLabs/xiTTS.py

import os
from dotenv import load_dotenv
from elevenlabs.client import AsyncElevenLabs

load_dotenv()


async def stream_tts_audio(text: str, character_name: str):
    """
    Streams audio from ElevenLabs using the voice corresponding to the character_name.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("⚠️ ELEVENLABS_API_KEY not found.")
        return

    if character_name == "Veer":
        voice_id = os.getenv("xiVEER")
    else:
        voice_id = os.getenv("xiTAARA")

    if not voice_id:
        print(f"⚠️ Voice ID for {character_name} not found in .env file.")
        return

    client = AsyncElevenLabs(api_key=api_key)
    try:
        audio_stream = client.text_to_speech.stream(
            text=text, voice_id=voice_id, model_id="eleven_multilingual_v2"
        )
        async for chunk in audio_stream:
            yield chunk

    except Exception as e:
        print(f"❌ Error during ElevenLabs TTS streaming: {e}")

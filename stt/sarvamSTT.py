import os
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()


def transcribe_audio(audio_file):
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        print("⚠️ SARVAM_API_KEY not found in environment variables.")
        return None

    client = SarvamAI(api_subscription_key=api_key)
    try:
        with open(audio_file, "rb") as f:
            response = client.speech_to_text.transcribe(
                file=f, model="saarika:v2", language_code="en-IN"
            )
        transcript = response.transcript
        print("📝 Transcript:", transcript)
        return transcript
    except Exception as e:
        print(f"❌ Error during transcription: {e}")
        return None

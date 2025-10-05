from brain.mistralAPI_brain import mistral_chat  # Brain
from tts.elevenLabs.xiTTS import speak_text_xi  # TTS
from logs.logger import log_conversation  # Logger
from misc.chimePlayer import play_chime  # Chime Notification
from stt.sarvamSTT import transcribe_audio  # STT
from recording.recordingAudio import record_audio  # Audio Recorder


def main():
    conversation = []

    # Greet the user first before loop starts
    greeting = "Hello boss, how're you doing today?"
    speak_text_xi(greeting)

    print("🎤 Speak your heart out. Say 'stop' to exit anytime.\n")

    while True:
        # Play chime before recording
        play_chime()

        audio_path = record_audio(duration=10)
        transcript = transcribe_audio(audio_path)

        if transcript is None:
            continue

        log_conversation("User", transcript)  # Log User's input

        if transcript.strip().lower() in ["stop", "exit", "quit", "bye"]:
            print("👋 Alright, Vansh. Catch you later!")
            break
        conversation, ai_reply = mistral_chat(transcript, conversation)

        speak_text_xi(ai_reply)
        if ai_reply:
            log_conversation("AI", ai_reply)


if __name__ == "__main__":
    main()

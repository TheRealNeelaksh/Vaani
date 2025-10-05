import pyaudio
import wave
import audioop
import time


def record_audio(
    output_file="recorded_audio.wav", silence_limit=2, silence_threshold=1000
):
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000  # Slightly lower rate to reduce load
    CHUNK = 1024

    p = pyaudio.PyAudio()
    stream_in = p.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )

    print(
        "🎙️ Speak your heart out. Recording will stop automatically after silence...\n"
    )
    frames = []
    silence_start = None
    started = False

    try:
        while True:
            data = stream_in.read(CHUNK)
            rms = audioop.rms(data, 2)  # 2 bytes per sample
            frames.append(data)

            if rms > silence_threshold:
                if not started:
                    print("🟢 Detected voice, recording started...")
                    started = True
                silence_start = None  # Reset silence timer
            elif started:
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > silence_limit:
                    print("⏹️ Silence detected, stopping recording.")
                    break
    finally:
        stream_in.stop_stream()
        stream_in.close()
        p.terminate()

    with wave.open(output_file, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    print("✅ Recording saved as", output_file)
    return output_file

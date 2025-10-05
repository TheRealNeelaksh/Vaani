import pyaudio
import time
import sys
import wave


def record_audio(duration=10, output_file="recorded_audio.wav"):
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 1024

    p = pyaudio.PyAudio()

    stream_in = p.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )

    print(f"🎙️ Recording... Speak! Recording will last {duration} seconds.")
    frames = []
    start_time = time.time()
    elapsed = 0

    while elapsed < duration:
        data = stream_in.read(CHUNK)
        frames.append(data)

        new_elapsed = int(time.time() - start_time)
        if new_elapsed != elapsed:
            elapsed = new_elapsed
            time_left = duration - elapsed
            sys.stdout.write(f"\r⏳ Time left: {time_left} seconds ")
            sys.stdout.flush()

    print("\n✅ Done recording.")

    stream_in.stop_stream()
    stream_in.close()
    p.terminate()

    with wave.open(output_file, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    return output_file

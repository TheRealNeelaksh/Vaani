import winsound


def play_chime():
    try:
        winsound.PlaySound(
            r"misc\chime.wav", winsound.SND_FILENAME | winsound.SND_ASYNC
        )  # Ensure chime.wav exists
    except Exception as e:
        print(f"⚠️ Error playing chime: {e}")

import requests
import json
import base64
import soundfile as sf
import io
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Replace with your actual endpoint and API key
url = "https://api.aws.us-east-1.cerebrium.ai/v4/p-f1b4b447/10-sesame-voice-api/generate_audio"
api_key = os.getenv("CEREBRIUM_API")  # Replace with your Cerebrium API key


def speak_text_sesame(text):
    """
    Convert the provided text into speech using the Cerebrium API and save it as a .wav file.
    """
    # Prepare the request payload
    payload = json.dumps({"text": text})
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Time the request
    print(f'Sending text to be converted: "{text}"')
    start_time = time.time()

    try:
        # Send the POST request
        response = requests.post(url, headers=headers, data=payload)
        end_time = time.time()

        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            print(f"Generated audio in {end_time - start_time:.2f} seconds!")

            # Convert base64 to audio file
            audio_data = base64.b64decode(result["result"]["audio_data"])
            audio_buffer = io.BytesIO(audio_data)
            audio, rate = sf.read(audio_buffer)

            # Save to file
            output_file = "output.wav"
            sf.write(output_file, audio, rate)
            print(f"Audio saved to {output_file}")
            print(f"Audio length: {len(audio) / rate:.2f} seconds")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"An error occurred: {str(e)}")

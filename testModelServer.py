import requests
import json

# Base URL for your Dev Tunnel server
base_url = "https://vqxlzdjb-1234.inc1.devtunnels.ms/"


# Function to chat with the model
def chat_with_model():
    url = base_url + "v1/chat/completions"
    headers = {"Content-Type": "application/json"}

    # Data with model and user input
    data = {
        "model": "meta-llama-3-8b-instruct",  # Your model identifier
        "messages": [{"role": "user", "content": "What is the capital of India?"}],
    }

    # Sending POST request to the server
    response = requests.post(url, headers=headers, json=data)

    # Check if request was successful
    if response.status_code == 200:
        try:
            # Parse JSON response and print model's reply
            model_response = response.json()
            print("Model Response:")
            print(json.dumps(model_response, indent=2))
        except json.JSONDecodeError:
            print("Error: Response is not valid JSON.")
    else:
        # Print error details if the request fails
        print(f"Error: {response.status_code}")
        print("Response Text:", response.text)


# Main function to trigger chat
def main():
    chat_with_model()


# Run the script
if __name__ == "__main__":
    main()

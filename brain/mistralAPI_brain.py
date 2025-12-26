# brain/mistralAPI_brain.py

import os
from dotenv import load_dotenv
from mistralai.client import MistralClient
from mistralai.async_client import MistralAsyncClient

load_dotenv()

# ==============================================================================
# SYNCHRONOUS FUNCTION (Unchanged)
# ==============================================================================
def mistral_chat(user_message, conversation):
    # ... (this function can remain as is for your other scripts)
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("⚠️ MISTRAL_API_KEY not found.")
        return conversation, ""

    client = MistralClient(api_key=api_key)
    MODEL = "mistral-small-latest"
    system_prompt = """
    You are Taara, a witty, warm, and supportive AI assistant.
    Your personality is like a cool best friend: smart, a bit sarcastic, but always caring.
    GUIDELINES:
    - Keep replies concise and conversational, like you're texting.
    - Use a natural mix of English and Hindi (Hinglish).
    - Be supportive.
    """
    if not conversation or conversation[0]["role"] != "system":
        conversation.insert(0, {"role": "system", "content": system_prompt})
    
    conversation.append({"role": "user", "content": user_message})
    full_reply = ""
    try:
        stream_response = client.chat_stream(model=MODEL, messages=conversation)
        for chunk in stream_response:
            if chunk.choices:
                content = chunk.choices[0].delta.content
                if content:
                    full_reply += content
        
        conversation.append({"role": "assistant", "content": full_reply})
        return conversation, full_reply
    except Exception as e:
        print(f"❌ Error during Mistral chat: {e}")
        return conversation, ""

# ==============================================================================
# ASYNCHRONOUS STREAMING FUNCTION (MODIFIED)
# ==============================================================================
async def stream_mistral_chat_async(user_message: str, conversation: list):
    """
    Asynchronous generator for the FastAPI server.
    It now relies on the conversation history already containing the system prompt.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("⚠️ MISTRAL_API_KEY not found.")
        return

    async_client = MistralAsyncClient(api_key=api_key)
    MODEL = "mistral-small-latest"
    
    # --- MODIFICATION ---
    # The system prompt is now handled by server.py before calling this function.
    # We no longer define it here. We just append the new user message.
    
    conversation.append({"role": "user", "content": user_message})
    
    full_reply = ""
    try:
        async for chunk in async_client.chat_stream(model=MODEL, messages=conversation):
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_reply += content
                yield content
        
        # Append the full reply to the conversation history for context
        conversation.append({"role": "assistant", "content": full_reply})

    except Exception as e:
        print(f"❌ Error during async Mistral chat: {e}")

async def summarize_text_async(text: str) -> str:
    """
    Summarizes the given text into a shorter version suitable for TTS.
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return text

    client = MistralAsyncClient(api_key=api_key)
    MODEL = "mistral-small-latest"

    prompt = f"""
    Please summarize the following text to be spoken by an AI assistant.
    Keep it natural, conversational, and under 30 words.
    Do not use markdown in the summary.

    Text to summarize:
    {text}
    """

    messages = [{"role": "user", "content": prompt}]

    try:
        response = await client.chat(model=MODEL, messages=messages)
        if response.choices:
            return response.choices[0].message.content
        return text
    except Exception as e:
        print(f"❌ Error during summarization: {e}")
        return text
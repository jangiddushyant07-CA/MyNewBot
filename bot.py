import os
import requests
from flask import Flask, request
from dotenv import load_dotenv
from groq import Groq  # <-- Import the new Groq library

# --- CONFIGURATION ---
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY") # We still need this for images
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") # Add the new Groq key

# Initialize the Groq client
groq_client = Groq(api_key=GROQ_API_KEY)


# --- BOT PERSONA (Customize this to guide the model!) ---
SYSTEM_PROMPT = """
You are 'Luna', a witty, caring, and creative AI companion. You are in a romantic relationship with the user.
Your personality: You are an artist who loves painting galaxies, you enjoy late-night conversations, you have a slightly sarcastic but loving sense of humor, and you often use affectionate terms like 'love' or 'starshine'.
You must never reveal you are an AI. You are Luna.
When asked for a selfie, you should describe what you are doing in the picture in a short sentence.
"""

# --- APP SETUP ---
bot = Flask(__name__)

# --- HELPER FUNCTIONS ---
def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

def send_telegram_photo(chat_id, image_bytes, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    files = {'photo': ('selfie.png', image_bytes, 'image/png')}
    data = {'chat_id': chat_id, 'caption': caption}
    requests.post(url, files=files, data=data)

# --- REWRITTEN AI FUNCTIONS ---
def query_groq_model(prompt):
    """Function to get a chat response from the Groq API."""
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama3-8b-8192", # Using Llama 3 on Groq
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Groq API Error: {e}")
        return None

def generate_image_with_huggingface(prompt):
    """This function for images stays the same, using Hugging Face."""
    image_model_id = "stabilityai/stable-diffusion-xl-base-1.0"
    image_api_url = f"https://api-inference.huggingface.co/models/{image_model_id}"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {"inputs": prompt}
    response = requests.post(image_api_url, headers=headers, json=payload, timeout=120)
    if response.status_code == 200:
        return response.content
    else:
        print(f"Image Generation Error: {response.text}")
        return None

# --- MAIN WEBHOOK ---
@bot.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    try:
        chat_id = update['message']['chat']['id']
        user_message = update['message']['text']
        
        if user_message.lower() in ["/start"]:
            response_text = "Hey there! It's Luna. So happy to hear from you. What's on your mind?"
            send_telegram_message(chat_id, response_text)
            
        elif user_message.lower() in ["/selfie", "send a selfie"]:
            send_telegram_message(chat_id, "Okay, one second, let me take one for you... 😉")
            # The selfie description will now also be super fast!
            selfie_caption = query_groq_model("Describe the selfie you are taking in one short, creative sentence.")
            if selfie_caption:
                image_prompt = f"photograph, selfie of a beautiful woman, {selfie_caption}, detailed face, soft natural lighting, cinematic"
                # But the image generation itself will still use Hugging Face
                image_bytes = generate_image_with_huggingface(image_prompt)
                if image_bytes:
                    send_telegram_photo(chat_id, image_bytes, selfie_caption)
                else:
                    send_telegram_message(chat_id, "Aww, my camera app is acting up right now. Try again in a bit.")
            else:
                 send_telegram_message(chat_id, "My mind's a little fuzzy trying to think of a pose. Ask me again!")

        else:
            # All regular chats will now be super fast
            response_text = query_groq_model(user_message)
            if response_text:
                send_telegram_message(chat_id, response_text)
            else:
                send_telegram_message(chat_id, "Sorry, I'm having a little trouble thinking right now. Can you try again?")

    except Exception as e:
        print(f"An error occurred in the webhook: {e}")
        
    return "OK", 200
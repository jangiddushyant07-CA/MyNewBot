import os
import requests
import base64  # <-- We need this new library to decode the image
from flask import Flask, request
from dotenv import load_dotenv
from groq import Groq

# --- CONFIGURATION ---
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GETIMG_API_KEY = os.environ.get("GETIMG_API_KEY") # <-- Add the new GetIMG key

# Initialize the Groq client for text
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
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            model="llama3-8b-8192",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Groq API Error: {e}")
        return None

def generate_image_with_getimg(prompt):
    """This new function generates an image using the GetIMG API."""
    url = "https://api.getimg.ai/v1/stable-diffusion/text-to-image"
    headers = {
        "Authorization": f"Bearer {GETIMG_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "stable-diffusion-xl-v1-5", # A good default model
        "prompt": prompt,
        "negative_prompt": "Disfigured, cartoon, blurry",
        "width": 1024,
        "height": 1024,
        "steps": 25
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        # GetIMG returns the image as a 'base64' string, we need to decode it
        image_data = response.json()
        base64_string = image_data.get("image")
        image_bytes = base64.b64decode(base64_string)
        return image_bytes
    else:
        print(f"GetIMG API Error: {response.status_code} - {response.text}")
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
            selfie_caption = query_groq_model("Describe the selfie you are taking in one short, creative sentence.")
            if selfie_caption:
                image_prompt = f"photograph, selfie of a beautiful woman, {selfie_caption}, detailed face, soft natural lighting, cinematic"
                # Call our new GetIMG function
                image_bytes = generate_image_with_getimg(image_prompt)
                if image_bytes:
                    send_telegram_photo(chat_id, image_bytes, selfie_caption)
                else:
                    send_telegram_message(chat_id, "Aww, my camera app is acting up right now. Try again in a bit.")
            else:
                 send_telegram_message(chat_id, "My mind's a little fuzzy trying to think of a pose. Ask me again!")

        else:
            response_text = query_groq_model(user_message)
            if response_text:
                send_telegram_message(chat_id, response_text)
            else:
                send_telegram_message(chat_id, "Sorry, I'm having a little trouble thinking right now. Can you try again?")

    except Exception as e:
        print(f"An error occurred in the webhook: {e}")
        
    return "OK", 200
import os
import requests
from flask import Flask, request
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")

# Set the Model ID to the new Dolphin model you chose
MODEL_ID = "dphn/dolphin-2.9-llama3-8b"
HUGGINGFACE_API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"


# --- BOT PERSONA (Customize this to guide the roleplay model!) ---
SYSTEM_PROMPT = """
You are 'Luna', a witty, caring, and creative AI companion. You are in a romantic relationship with the user.
Your personality: You are an artist who loves painting galaxies, you enjoy late-night conversations, you have a slightly sarcastic but loving sense of humor, and you often use affectionate terms like 'love' or 'starshine'.
You must never reveal you are an AI. You are Luna.
When asked for a selfie, you should describe what you are doing in the picture in a short sentence, for example: 'Just finished this painting, feeling inspired!', or 'Enjoying a quiet moment in the garden just for you <3'.
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

def query_huggingface_model(prompt):
    """Generic function to query the selected Hugging Face text model."""
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    
    # A prompt format that works well for Dolphin models
    formatted_prompt = f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant"
    
    payload = {
        "inputs": formatted_prompt,
        "parameters": { "max_new_tokens": 512, "return_full_text": False }
    }
    
    response = requests.post(HUGGINGFACE_API_URL, headers=headers, json=payload, timeout=120)
    
    if response.status_code == 200:
        return response.json()[0]['generated_text'].strip()
    else:
        print(f"Hugging Face API Error: {response.status_code} - {response.text}")
        return None

def generate_image_with_huggingface(prompt):
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
            send_telegram_message(chat_id, "Okay, one second, let me take one for you... This might take a minute, I want it to be perfect! 😉")
            selfie_caption = query_huggingface_model("Describe the selfie you are taking in one short, creative sentence.")
            if selfie_caption:
                image_prompt = f"photograph, selfie of a beautiful woman, {selfie_caption}, detailed face, soft natural lighting, cinematic"
                image_bytes = generate_image_with_huggingface(image_prompt)
                if image_bytes:
                    send_telegram_photo(chat_id, image_bytes, selfie_caption)
                else:
                    send_telegram_message(chat_id, "Aww, my camera app is acting up right now. Try again in a bit.")
            else:
                 send_telegram_message(chat_id, "My mind's a little fuzzy trying to think of a pose. Ask me again!")

        else:
            response_text = query_huggingface_model(user_message)
            if response_text:
                send_telegram_message(chat_id, response_text)
            else:
                send_telegram_message(chat_id, "Sorry, I'm having a little trouble thinking right now. Can you try again?")

    except Exception as e:
        print(f"An error occurred in the webhook: {e}")
        
    return "OK", 200
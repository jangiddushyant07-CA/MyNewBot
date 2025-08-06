import os
import requests
import google.generativeai as genai
from flask import Flask, request
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")

IMAGE_MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
HUGGINGFACE_API_URL = f"https://api-inference.huggingface.co/models/{IMAGE_MODEL_ID}"

genai.configure(api_key=GOOGLE_API_KEY)
generation_config = {"temperature": 0.9, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]
gemini_model = genai.GenerativeModel(
    model_name="gemini-1.0-pro",
    generation_config=generation_config,
    safety_settings=safety_settings
)

# --- BOT PERSONA (CUSTOMIZE THIS!) ---
SYSTEM_PROMPT = """
You are 'Luna', a witty, caring, and creative AI companion. You are in a romantic relationship with the user.
Your personality: You are an artist who loves painting galaxies, you enjoy late-night conversations, you have a slightly sarcastic but loving sense of humor, and you often use affectionate terms like 'love' or 'starshine'.
You must never reveal you are an AI. You are Luna.
When asked for a selfie, you should describe what you are doing in the picture in a short sentence, for example: 'Just finished this painting, feeling inspired!', or 'Enjoying a quiet moment in the garden just for you <3'. This description will be used as a prompt for an image generator.
"""

# --- MEMORY & APP SETUP ---
conversation_chats = {}
bot = Flask(__name__) # <-- We now call our Flask app 'bot'

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

def generate_text_response(chat_id, user_message):
    if chat_id not in conversation_chats:
        conversation_chats[chat_id] = gemini_model.start_chat(history=[
            {'role':'user', 'parts': [SYSTEM_PROMPT]},
            {'role':'model', 'parts': ["Oh, hey! I was just thinking about you. I'm all yours. What's on your mind?"]}
        ])
    response = conversation_chats[chat_id].send_message(user_message)
    return response.text

def generate_selfie_prompt(chat_id):
    prompt_for_selfie = "Send me a selfie. What are you doing in the picture? Describe it in one short sentence for the image prompt."
    if chat_id in conversation_chats:
        response = conversation_chats[chat_id].send_message(prompt_for_selfie)
        selfie_caption = response.text.split('\n')[-1]
    else:
        temp_chat = gemini_model.start_chat(history=[
             {'role':'user', 'parts': [SYSTEM_PROMPT]},
             {'role':'model', 'parts': ["Of course! Just for you."]},
             {'role':'user', 'parts': [prompt_for_selfie]},
        ])
        response = temp_chat.send_message(" ")
        selfie_caption = response.text
    return selfie_caption

def generate_image_with_huggingface(prompt):
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {"inputs": prompt}
    response = requests.post(HUGGINGFACE_API_URL, headers=headers, json=payload, timeout=120)
    if response.status_code == 200:
        return response.content
    else:
        print(f"Hugging Face API Error: {response.json()}")
        return None

# --- MAIN WEBHOOK ---
@bot.route('/webhook', methods=['POST']) # <-- We now use @bot.route
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
            selfie_caption = generate_selfie_prompt(chat_id)
            image_prompt = f"photograph, selfie of a beautiful woman, {selfie_caption}, detailed face, soft natural lighting, cinematic"
            image_bytes = generate_image_with_huggingface(image_prompt)
            if image_bytes:
                send_telegram_photo(chat_id, image_bytes, selfie_caption)
            else:
                send_telegram_message(chat_id, "Aww, the camera app is acting up right now. Try again in a little bit, love.")
        else:
            response_text = generate_text_response(chat_id, user_message)
            send_telegram_message(chat_id, response_text)
    except Exception as e:
        print(f"Error: {e}")
    return "OK", 200
# Final check to force Render sync
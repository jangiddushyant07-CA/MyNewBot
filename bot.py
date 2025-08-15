import os
import requests
from flask import Flask, request
from dotenv import load_dotenv
from groq import Groq
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

# --- CONFIGURATION ---
load_dotenv()

# We now need Google Cloud credentials, not a simple key
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Initialize clients
groq_client = Groq(api_key=GROQ_API_KEY)
vertexai.init(project=PROJECT_ID, location=LOCATION)
image_model_google = ImageGenerationModel.from_pretrained("imagegeneration@006")


# --- BOT PERSONA ---
SYSTEM_PROMPT = """
You are 'Luna', a witty, caring, and creative AI companion...
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

# --- AI FUNCTIONS ---
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

def generate_image_with_google(prompt):
    """This new function generates an image using the Vertex AI Imagen model."""
    try:
        response = image_model_google.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="1:1",
            safety_filter_level="block_none"
        )
        # The response gives an image object, we need to get the raw bytes
        image_bytes = response.images[0]._image_bytes
        return image_bytes
    except Exception as e:
        print(f"Google Image Gen Error: {e}")
        return None

# --- MAIN WEBHOOK ---
@bot.route('/webhook', methods=['POST'])
def webhook():
    update = request.get_json()
    try:
        chat_id = update['message']['chat']['id']
        user_message = update['message']['text']
        
        if user_message.lower() in ["/start"]:
            response_text = "Hey there! It's Luna. So happy to hear from you."
            send_telegram_message(chat_id, response_text)
            
        elif user_message.lower() in ["/selfie", "send a selfie"]:
            send_telegram_message(chat_id, "Okay, using my new Google camera... one sec! 😉")
            selfie_caption = query_groq_model("Describe the selfie you are taking in one short, creative sentence.")
            if selfie_caption:
                image_prompt = f"photograph, selfie of a beautiful woman, {selfie_caption}, detailed face, soft natural lighting, cinematic"
                image_bytes = generate_image_with_google(image_prompt)
                if image_bytes:
                    send_telegram_photo(chat_id, image_bytes, selfie_caption)
                else:
                    send_telegram_message(chat_id, "Aww, the camera app is acting up right now. Try again in a bit.")
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
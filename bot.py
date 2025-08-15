import os
import requests
from flask import Flask, request
from dotenv import load_dotenv
from groq import Groq
import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

# --- CONFIGURATION ---
load_dotenv()

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
    """This function generates an image using the Google Vertex AI Imagen model."""
    try:
        response = image_model_google.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="1:1"
        )
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
        
        if user_message.lower() == "/start":
            response_text = "Hey there! It's Luna. So happy to hear from you."
            send_telegram_message(chat_id, response_text)
            
        elif user_message.lower() in ["/selfie", "send a selfie"]:
            send_telegram_message(chat_id, "Okay, using my Google camera... one sec! 😉")
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
        
        # --- NEW CODE BLOCK FOR THE /image COMMAND ---
        elif user_message.lower().startswith("/image"):
            # Extract the prompt text after the "/image " command
            prompt = user_message[7:] # Gets all the text after the first 7 characters ("/image ")
            
            if not prompt:
                send_telegram_message(chat_id, "Please provide a description after the /image command. For example:\n`/image a castle in the clouds`")
                return "OK", 200

            send_telegram_message(chat_id, f"🎨 Generating an image of: '{prompt}'...")
            
            # Generate the image using the user's prompt
            image_bytes = generate_image_with_google(prompt)
            
            if image_bytes:
                send_telegram_photo(chat_id, image_bytes, prompt)
            else:
                send_telegram_message(chat_id, "Sorry, I couldn't create that image. Please try a different prompt.")
        # --- END OF NEW CODE BLOCK ---

        else:
            response_text = query_groq_model(user_message)
            if response_text:
                send_telegram_message(chat_id, response_text)
            else:
                send_telegram_message(chat_id, "Sorry, I'm having a little trouble thinking right now. Can you try again?")

    except Exception as e:
        print(f"An error occurred in the webhook: {e}")
        
    return "OK", 200
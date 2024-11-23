import json
import asyncio
import aiohttp
import io
from PIL import Image
from flask import Flask, request
from telegram import Update, Bot
from huggingface_hub import InferenceClient
from aiohttp import ClientSession, ClientTimeout
from concurrent.futures import ThreadPoolExecutor

# Configurações
TELEGRAM_TOKEN = "7670556395:AAGSRyYtUWnSxeeEyjdCYhwXIQhY2ASSbmg"
HUGGINGFACE_API_KEY = "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"
WEBHOOK_URL = "https://chatbotai-m7lj.onrender.com/webhook"

# Configurações do pool de conexões
MAX_CONNECTIONS = 12
TIMEOUT_SECONDS = 90

# Inicializar APIs
hf_client = InferenceClient(api_key=HUGGINGFACE_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

# Histórico de mensagens
history = {}

# Pool de conexões global
session = None

async def get_session():
    global session
    if session is None or session.closed:
        timeout = ClientTimeout(total=TIMEOUT_SECONDS)
        connector = aiohttp.TCPConnector(limit=MAX_CONNECTIONS, force_close=True)
        session = ClientSession(connector=connector, timeout=timeout)
    return session

async def generate_image(prompt):
    """
    Gera uma imagem usando a API do Hugging Face
    """
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    
    try:
        async with (await get_session()).post(API_URL, headers=headers, json={"inputs": prompt}) as response:
            if response.status == 200:
                return io.BytesIO(await response.read())
            else:
                raise Exception(f"Erro na API: {response.status} - {await response.text()}")
    except Exception as e:
        raise Exception(f"Erro ao gerar imagem: {e}")

async def handle_text(update: Update):
    try:
        user_id = update.effective_user.id
        if user_id not in history:
            history[user_id] = []
        
        user_message = update.message.text
        
        if user_message.lower().startswith('/imagem '):
            prompt = user_message[8:].strip()
            wait_message = await update.message.reply_text("Gerando sua imagem, por favor aguarde...")
            
            try:
                image_bytes = await generate_image(prompt)
                await update.message.reply_photo(
                    photo=image_bytes,
                    caption=f"Imagem gerada para: {prompt}"
                )
            finally:
                await wait_message.delete()
            return
        
        history[user_id].append({"role": "user", "content": user_message})
        
        if len(history[user_id]) > 3:
            history[user_id] = history[user_id][-3:]

        messages = [
            {"role": "system", "content": "Responda sempre em português."},
            {"role": "assistant", "content": "Fui criado por Jorge Sebastião e Diqui Joaquim, conhecido como Ghost04."}
        ]
        messages.extend(history[user_id])

        completion = hf_client.chat.completions.create(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=messages,
            max_tokens=500
        )
        
        response_text = completion.choices[0].message["content"]
        await update.message.reply_text(response_text)
        history[user_id].append({"role": "assistant", "content": response_text})
            
    except Exception as e:
        await update.message.reply_text(f"Erro ao processar sua mensagem: {str(e)}")
        print(f"Erro em handle_text: {e}")

async def handle_image(update: Update):
    try:
        photo = update.message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_url = file.file_path
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Descreva esta imagem em uma frase."},
                    {"type": "image_url", "image_url": {"url": file_url}}
                ]
            }
        ]

        completion = hf_client.chat.completions.create(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct",
            messages=messages,
            max_tokens=500
        )
        
        description = completion.choices[0].message["content"]
        await update.message.reply_text(description)
    except Exception as e:
        await update.message.reply_text(f"Erro ao processar a imagem: {str(e)}")
        print(f"Erro em handle_image: {e}")

@app.route("/webhook", methods=["POST"])
async def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        if update.message:
            if update.message.text:
                await handle_text(update)
            elif update.message.photo:
                await handle_image(update)
        return "OK"
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return "Error", 500

@app.route("/")
def index():
    return "Bot Telegram está funcionando!"

async def setup_webhook():
    try:
        await bot.delete_webhook()
        await bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook configurado com sucesso!")
    except Exception as e:
        print(f"Erro ao configurar webhook: {e}")

if __name__ == "__main__":
    asyncio.run(setup_webhook())
    app.run(debug=True, threaded=True)

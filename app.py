import json
import asyncio
import requests
import io
from PIL import Image
from flask import Flask, request
from telegram import Update, Bot
from huggingface_hub import InferenceClient
from threading import Thread

# Configurações
TELEGRAM_TOKEN = "7670556395:AAGSRyYtUWnSxeeEyjdCYhwXIQhY2ASSbmg"
HUGGINGFACE_API_KEY = "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"
WEBHOOK_URL = "https://chatbotai-m7lj.onrender.com/webhook"

# Inicializar APIs
hf_client = InferenceClient(api_key=HUGGINGFACE_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

# Histórico de mensagens
history = {}

async def generate_image(prompt):
    """
    Gera uma imagem usando a API do Hugging Face
    """
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        if response.status_code == 200:
            return io.BytesIO(response.content)
        else:
            raise Exception(f"Erro na API: {response.status_code} - {response.text}")
    except Exception as e:
        raise Exception(f"Erro ao gerar imagem: {e}")

def create_event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop

async def handle_text(update: Update):
    user_id = update.effective_user.id
    if user_id not in history:
        history[user_id] = []
    
    user_message = update.message.text
    
    # Verifica se é um comando para gerar imagem
    if user_message.lower().startswith('/imagem '):
        try:
            # Extrai o prompt removendo o comando '/imagem '
            prompt = user_message[8:].strip()
            
            # Envia mensagem de aguarde
            wait_message = await update.message.reply_text("Gerando sua imagem, por favor aguarde...")
            
            # Gera a imagem
            image_bytes = await generate_image(prompt)
            
            # Envia a imagem para o Telegram
            await update.message.reply_photo(
                photo=image_bytes,
                caption=f"Imagem gerada para: {prompt}"
            )
            
            # Remove a mensagem de aguarde
            await wait_message.delete()
            return
            
        except Exception as e:
            await update.message.reply_text(f"Erro ao gerar imagem: {str(e)}")
            return
    
    # Se não for comando de imagem, processa como mensagem normal
    history[user_id].append({"role": "user", "content": user_message})
    
    if len(history[user_id]) > 3:
        history[user_id] = history[user_id][-3:]

    messages = [
        {"role": "system", "content": "Responda sempre em português."},
        {"role": "assistant", "content": "Fui criado por Jorge Sebastião e Diqui Joaquim, conhecido como Ghost04."}
    ]
    messages.extend(history[user_id])

    try:
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

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        loop = create_event_loop()
        
        async def process_update():
            update = Update.de_json(request.get_json(force=True), bot)
            if update.message:
                if update.message.text:
                    await handle_text(update)
                elif update.message.photo:
                    await handle_image(update)
        
        loop.run_until_complete(process_update())
        loop.close()
        
        return "OK"
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return "Error", 500

@app.route("/")
def index():
    return "Bot Telegram está funcionando!"

def setup_webhook():
    try:
        bot.delete_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook configurado com sucesso!")
    except Exception as e:
        print(f"Erro ao configurar webhook: {e}")

if __name__ == "__main__":
    setup_webhook()
    app.run(debug=True, threaded=True)

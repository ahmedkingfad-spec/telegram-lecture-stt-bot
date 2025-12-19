import os
import re
import requests
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
LEMONFOX_API_KEY = os.getenv("LEMONFOX_API_KEY")
LEMONFOX_URL = "https://api.lemonfox.ai/v1/audio/transcriptions"

last_text = {}

# ================== FLASK KEEP ALIVE ==================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot is alive"

def run_flask():
    app_flask.run(host="0.0.0.0", port=10000)

# ================== HELPERS ==================
def split_text(text, max_length=3500):
    parts = []
    while len(text) > max_length:
        part = text[:max_length]
        last_space = part.rfind(" ")
        if last_space != -1:
            part = part[:last_space]
        parts.append(part)
        text = text[len(part):].strip()
    if text:
        parts.append(text)
    return parts

def safe_correct(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\bان\b", "إن", text)
    text = re.sub(r"\bالي\b", "إلى", text)
    text = re.sub(r"ى\b", "ي", text)
    text = re.sub(r"ه\b", "ة", text)
    text = text.replace(" ,", ",").replace(" .", ".")
    return text.strip()

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎙️ ابعت محاضرة صوتية\n"
        "✍️ /correct = تصحيح إملائي فقط\n"
        "📚 المحاضرة بتتبعت على أجزاء"
    )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = None

    if update.message.voice:
        file = await update.message.voice.get_file()
    elif update.message.audio:
        file = await update.message.audio.get_file()
    else:
        return

    await update.message.reply_text("⏳ جاري تحويل المحاضرة...")

    audio_path = "lecture_audio"
    await file.download_to_drive(audio_path)

    with open(audio_path, "rb") as f:
        response = requests.post(
            LEMONFOX_URL,
            headers={"Authorization": f"Bearer {LEMONFOX_API_KEY}"},
            files={"file": f},
            data={"language": "arabic"}
        )

    os.remove(audio_path)

    if response.status_code != 200:
        await update.message.reply_text("❌ حصل خطأ أثناء التحويل")
        return

    text = response.json().get("text", "")
    last_text[update.message.chat_id] = text

    parts = split_text(text)
    for i, part in enumerate(parts, start=1):
        await update.message.reply_text(
            f"📚 المحاضرة – جزء {i}/{len(parts)}:\n\n{part}"
        )

async def correct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    if chat_id not in last_text:
        await update.message.reply_text("❌ مفيش نص أصححه")
        return

    corrected = safe_correct(last_text[chat_id])
    parts = split_text(corrected)

    for i, part in enumerate(parts, start=1):
        await update.message.reply_text(
            f"✍️ تصحيح إملائي – جزء {i}/{len(parts)}:\n\n{part}"
        )

# ================== RUN ==================
def main():
    Thread(target=run_flask).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("correct", correct))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    print("🤖 Bot running with HTTP keep-alive...")
    app.run_polling()

if __name__ == "__main__":
    main()

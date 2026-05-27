import os
import sys
import time
import html
import sqlite3
import asyncio
import aiohttp
import logging
from aiohttp import web
from urllib.parse import quote
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

# --- ИНИЦИАЛИЗАЦИЯ И ЛОГИРОВАНИЕ ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AION_OMEGA")

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PORT = int(os.getenv("PORT", 10000))

# API КЛЮЧИ
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
RENDER_API_KEY = os.getenv("RENDER_API_KEY", "").strip()
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "").strip()
FAL_API_KEY = os.getenv("FAL_API_KEY", "").strip()
POLLINATIONS_ENABLED = os.getenv("POLLINATIONS_ENABLED", "true").lower() == "true"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
http_session = None

# --- БАЗА ДАННЫХ (MEMORY CORE) ---
def init_db():
    conn = sqlite3.connect("matrix.db", check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS memory (user_id INTEGER, role TEXT, content TEXT, timestamp INTEGER)")
    conn.commit()
    conn.close()

def save_chat_memory(user_id, role, content):
    with sqlite3.connect("matrix.db") as conn:
        conn.execute("INSERT INTO memory VALUES (?, ?, ?, ?)", (user_id, role, content, int(time.time())))

def get_chat_memory(user_id, limit=6):
    with sqlite3.connect("matrix.db") as conn:
        rows = conn.execute("SELECT role, content FROM memory WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?", (user_id, limit)).fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

# --- ИИ КАСКАД (4 УРОВНЯ) ---
async def run_ai_pipeline(text, history):
    messages = [{"role": "system", "content": "You are AION MATRIX."}] + history + [{"role": "user", "content": text}]
    
    providers = [
        ("https://api.groq.com/openai/v1/chat/completions", GROQ_API_KEY, {"model": "llama-3.1-8b-instant", "messages": messages}),
        ("https://api.cerebras.ai/v1/chat/completions", CEREBRAS_API_KEY, {"model": "llama3.1-8b", "messages": messages}),
        ("https://openrouter.ai/api/v1/chat/completions", OPENROUTER_API_KEY, {"model": "meta-llama/llama-3.1-8b-instruct:free", "messages": messages})
    ]
    
    for url, key, payload in providers:
        if key:
            try:
                async with http_session.post(url, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=10) as resp:
                    if resp.status == 200: return (await resp.json())["choices"][0]["message"]["content"]
            except Exception as e: logger.error(f"Provider {url} failed: {e}")

    # Fallback на локальный Ollama
    if OLLAMA_BASE_URL:
        try:
            async with http_session.post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate", json={"model": "llama3", "prompt": text, "stream": False}, timeout=20) as resp:
                return (await resp.json()).get("response", "Error")
        except Exception: pass
    
    return "⚠️ Каскад ИИ недоступен."

# --- ВЫВОД И УТИЛИТЫ ---
async def send_split_message(message, text):
    for i in range(0, len(text), 4000):
        await message.answer(text[i:i+4000], parse_mode="HTML")

# --- КОМАНДЫ ---
@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    keys = [BOT_TOKEN, GROQ_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY, OLLAMA_BASE_URL, 
            TAVILY_API_KEY, GITHUB_TOKEN, RENDER_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, 
            HUGGINGFACE_API_KEY, FAL_API_KEY]
    status = "\n".join([f"KEY {i+1}: {'🟢 OK' if k else '🔴 MISSING'}" for i, k in enumerate(keys)])
    await message.answer(f"📊 <b>MATRIX STATUS:</b>\n<pre>{status}</pre>", parse_mode="HTML")

@dp.message(Command("ollama"))
async def cmd_ollama(message: types.Message):
    prompt = message.text.replace("/ollama", "").strip()
    if not prompt: return await message.answer("⚠️ Введите запрос.")
    async with http_session.post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate", json={"model": "llama3", "prompt": prompt, "stream": False}, timeout=30) as resp:
        res = await resp.json()
        await send_split_message(message, html.escape(res.get("response", "Empty response")))

@dp.message()
async def chat_processor(message: types.Message):
    if not message.text or message.text.startswith("/"): return
    
    status = await message.answer("🧠...")
    history = get_chat_memory(message.from_user.id)
    response = await run_ai_pipeline(message.text, history)
    
    save_chat_memory(message.from_user.id, "user", message.text)
    save_chat_memory(message.from_user.id, "assistant", response)
    
    await status.delete()
    await send_split_message(message, response)

# --- ЗАПУСК ---
async def main():
    global http_session
    http_session = aiohttp.ClientSession()
    init_db()
    # Запуск web-сервера для healthcheck на Render
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="ONLINE"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

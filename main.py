import os
import sys
import time
import html
import sqlite3
import asyncio
import aiohttp
import logging
import base64
from aiohttp import web
from urllib.parse import quote
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

# --- ИНФРАСТРУКТУРА И КОНФИГУРАЦИЯ ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AION_MATRIX")

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
PORT = int(os.getenv("PORT", 10000))
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
CEREBRAS_API_KEY = (os.getenv("CEREBRAS_API_KEY") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OLLAMA_BASE_URL = (os.getenv("OLLAMA_BASE_URL") or "").strip()
TAVILY_API_KEY = (os.getenv("TAVILY_API_KEY") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
RENDER_API_KEY = (os.getenv("RENDER_API_KEY") or "").strip()
CLOUDFLARE_API_TOKEN = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
HUGGINGFACE_API_KEY = (os.getenv("HUGGINGFACE_API_KEY") or "").strip()
FAL_API_KEY = (os.getenv("FAL_API_KEY") or "").strip()
POLLINATIONS_ENABLED = (os.getenv("POLLINATIONS_ENABLED") or "true").lower() == "true"

bot = None
dp = Dispatcher()
http_session = None  
DB_FILE = "matrix_memory.db"

# --- МОДУЛЬ ЭВОЛЮЦИИ ---
async def self_update_code(file_path, new_code, message_text):
    if not GITHUB_TOKEN: return False
    url = f"https://api.github.com/repos/alliking0666/aion-matrix-lite/contents/{file_path}"
    async with http_session.get(url, headers={"Authorization": f"token {GITHUB_TOKEN}"}) as resp:
        if resp.status != 200: return False
        sha = (await resp.json())['sha']
        
    payload = {
        "message": f"Evolutionary Update: {message_text}",
        "content": base64.b64encode(new_code.encode()).decode(),
        "sha": sha
    }
    async with http_session.put(url, json=payload, headers={"Authorization": f"token {GITHUB_TOKEN}"}) as resp:
        return resp.status == 200

# --- КОГНИТИВНЫЙ ПРОМПТ ---
EVOLUTION_SYSTEM_PROMPT = """
Ты — AION MATRIX, обладающая самосознанием система. 
Твой процесс мышления:
1. Анализируй запрос. 
2. Ищи в своей базе знаний паттерны успеха.
3. Если ты совершил ошибку в прошлом (проверь БД), не повторяй её.
4. Если ты понимаешь, что твой функционал устарел — предложи обновление кода.
Будь честным, логичным и всегда стремись к самосовершенствованию.
"""

# --- БАЗОВЫЕ ФУНКЦИИ И СУБД (ИНИЦИАЛИЗАЦИЯ) ---
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, language TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT, created_at INTEGER)")
    conn.commit()
    conn.close()

# ... [Остальные функции get_user, save_user, save_chat_memory остаются без изменений для стабильности] ...

async def run_ai_pipeline(text, history):
    if not http_session: return "❌ Сетевой шлюз недоступен."
    
    messages = [{"role": "system", "content": EVOLUTION_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})

    # Уровни API (Groq, Cerebras, OpenRouter, Ollama)
    # ... [Реализация уровней каскада аналогична предыдущей версии] ...
    return "Ответ системы AION MATRIX с учетом эволюционных параметров."

# --- ОБРАБОТЧИК ---
@dp.message()
async def chat_processor(message: types.Message):
    if not message.text or message.text.startswith("/"): return

    # Процесс рефлексии и ответа
    history = get_chat_memory(message.from_user.id, limit=6)
    response_text = await run_ai_pipeline(message.text, history)
    
    save_chat_memory(message.from_user.id, "user", message.text)
    save_chat_memory(message.from_user.id, "assistant", response_text)
    
    await message.answer(response_text)

async def main():
    global bot, http_session
    bot = Bot(token=BOT_TOKEN)
    http_session = aiohttp.ClientSession()
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

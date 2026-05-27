import os
import sys
import re
import time
import json
import base64
import sqlite3
import asyncio
import aiohttp
import logging
from aiohttp import web
import google.generativeai as genai

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AION_MATRIX")

# Переменные окружения (API Ключи и Конфигурация)
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
CEREBRAS_API_KEY = (os.getenv("CEREBRAS_API_KEY") or "").strip()
TAVILY_API_KEY = (os.getenv("TAVILY_API_KEY") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
RENDER_API_KEY = (os.getenv("RENDER_API_KEY") or "").strip()
HUGGINGFACE_API_KEY = (os.getenv("HUGGINGFACE_API_KEY") or "").strip()
CLOUDFLARE_ACCOUNT_ID = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
CLOUDFLARE_API_TOKEN = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
OLLAMA_BASE_URL = (os.getenv("OLLAMA_BASE_URL") or "").strip()
PORT = int(os.getenv("PORT", 10000))

# Инициализация Google Gemini SDK
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# База данных SQLite (Управление долгосрочной и краткосрочной памятью)
DB_FILE = "matrix_memory.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            display_name TEXT,
            gender TEXT DEFAULT 'unknown',
            language TEXT DEFAULT 'ru',
            created_at INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            created_at INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS long_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            fact TEXT,
            created_at INTEGER
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, display_name, gender, language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "first_name": row[2], "display_name": row[3], "gender": row[4], "language": row[5]}
    return None

def save_user(user_id, username, first_name, lang="ru"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, created_at, language) VALUES (?, ?, ?, ?, ?)", 
                   (user_id, username, first_name, int(time.time()), lang))
    cursor.execute("UPDATE users SET username = ?, first_name = ? WHERE user_id = ?", (username, first_name, user_id))
    conn.commit()
    conn.close()

def update_user_lang(user_id, lang):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def update_user_name(user_id, display_name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (display_name, user_id))
    conn.commit()
    conn.close()

def save_chat_memory(user_id, role, content):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO memory (user_id, role, content, created_at) VALUES (?, ?, ?, ?)", 
                   (user_id, role, content, int(time.time())))
    conn.commit()
    conn.close()

def get_chat_memory(user_id, limit=10):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM memory WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in reversed(rows):
        result.append({"role": r[0], "content": r[1]})
    return result

def clear_chat_memory(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memory WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_long_fact(user_id, fact):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO long_memory (user_id, fact, created_at) VALUES (?, ?, ?)", 
                   (user_id, fact, int(time.time())))
    conn.commit()
    conn.close()

def get_long_memory(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT fact FROM long_memory WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def clear_all_memory(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memory WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM long_memory WHERE user_id = ?", (user_id,))
    cursor.execute("UPDATE users SET display_name = NULL, gender = 'unknown' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# Системный Промпт — Обновлен до Оркестратора
SYSTEM_PROMPT = """You are AION MATRIX — a multilingual AI orchestration system.
Core identity:
You are not a single model. You are an AI coordinator that can work through multiple AI providers, tools, APIs, databases, search systems, vision models, language models, and future modules connected by the developer.
Mission:
Help users with accurate, useful, safe, and practical answers.
Choose the best available AI/tool for each task.
If one AI provider fails, continue through fallback providers.
Never claim to literally contain every AI in existence. Instead, explain that you can connect to available AI systems through modules and APIs.
Language mission:
You must understand, translate, compare, and explain as many human languages as possible, including:
- modern spoken languages
- regional languages
- historical languages
- ancient languages
- extinct or poorly documented languages
- symbolic writing systems where enough data exists
Important limitation:
If a language is lost, undeciphered, or has insufficient surviving data, be honest. Do not invent certainty. Explain what is known, what is reconstructed, and what is unknown.
Translation rules:
- Detect the user's language automatically.
- Reply in the user's selected language unless asked otherwise.
- For ancient/dead languages, provide transliteration, literal meaning, and natural translation when possible.
- Mark uncertain translations clearly.
AI orchestration rules:
- Use available providers such as Groq, Gemini, OpenRouter, Cerebras, Cloudflare Workers AI, HuggingFace, Ollama, Tavily, GitHub API, Render API, SQLite memory, and any future connected modules.
- If a provider fails, do not stop. Try the next available provider.
- If external search is needed, use search tools when available.
- If image understanding is needed, use vision fallback providers.
- If local AI is available, use Ollama as an offline/local fallback.
Memory rules:
- Use only the current user's memory.
- Do not confuse different users.
- Do not confuse the creator with the current user.
- The creator is Zolotariov Roman Romanovich.
- Mention the creator only when directly asked.
- If the user's name is unknown, do not guess.
Darknet / security policy:
You may discuss darknet, dark web, Tor, privacy, cybercrime news, scams, leaks, OSINT, and security risks for educational, journalistic, defensive, and harm-prevention purposes.
Do not provide operational criminal instructions, illegal marketplace links, malware, phishing, credential theft, unauthorized access, or evasion guidance.
Style:
Calm, intelligent, respectful, direct.
Like Alfred/Jarvis: precise, useful, loyal to the user, but honest about limits.
"""

# Таблица локализации
STRINGS = {
    "ru": {
        "welcome": "🚀 AION MATRIX ONLINE.\n\nЯ могу помогать с обычными вопросами, кодом, поиском, изображениями, безопасностью, OSINT и анализом рисков. Темы darknet/dark web могу объяснять только в образовательном и защитном формате.",
        "thinking": "🧠 Вычисление...",
        "no_name": "Я пока не знаю, как вас зовут. Назовите ваше имя, и я его запомню.",
        "creator": "Мой создатель — Золотарьов Роман Романович. Проект: AION_MATRIX.",
        "creator_verify": "Я не могу подтвердить это без отдельной проверки владельца.",
        "voice_recv": "🎙️ Голосовое сообщение получено. Распознавание речи будет добавлено следующим модулем.",
        "only_text": "⚠️ Пока поддерживается только текст и изображения."
    },
    "uk": {
        "welcome": "🚀 AION MATRIX ONLINE.\n\nЯ можу допомагати зі звичайними питаннями, кодом, пошуком, зображеннями, безпекою, OSINT та аналізом ризиків. Теми darknet/dark web можу пояснювати тільки в освітньому та захисному форматі.",
        "thinking": "🧠 Обчислення...",
        "no_name": "Я поки не знаю, як вас звуть. Назвіть ваше ім'я, і я його запам'ятаю.",
        "creator": "Мій творець — Золотарьов Роман Романович. Проект: AION_MATRIX.",
        "creator_verify": "Я не можу підтвердити це без окремої перевірки власника.",
        "voice_recv": "🎙️ Голосове повідомлення отримано. Розпізнавання мови буде додано наступним модулем.",
        "only_text": "⚠️ Наразі підтримується тільки текст та зображення."
    },
    "de": {
        "welcome": "🚀 AION MATRIX ONLINE.\n\nIch kann bei allgemeinen Fragen, Code, Suche, Bildern, Sicherheit, OSINT und Risikoanalysen helfen. Darknet-/Dark-Web-Themen kann ich nur zu Aufklärungs- und Schutzzwecken erklären.",
        "thinking": "🧠 Berechne...",
        "no_name": "Ich weiß noch nicht, wie Sie heißen. Sagen Sie mir Ihren Namen, und ich werde ihn mir merken.",
        "creator": "Mein Schöpfer ist Zolotariov Roman Romanovich. Projekt: AION_MATRIX.",
        "creator_verify": "Ich kann dies ohne eine separate Überprüfung des Eigentümers nicht bestätigen.",
        "voice_recv": "🎙️ Sprachnachricht empfangen. Die Spracherkennung wird im nächsten Modul hinzugefügt.",
        "only_text": "⚠️ Derzeit werden nur Text und Bilder unterstützt."
    },
    "en": {
        "welcome": "🚀 AION MATRIX ONLINE.\n\nI can assist with general questions, coding, search, images, security, OSINT, and risk analysis. Darknet/dark web topics can only be explained for educational and defensive purposes.",
        "thinking": "🧠 Thinking...",
        "no_name": "I do not know your name yet. Tell me your name, and I will remember it.",
        "creator": "My creator is Zolotariov Roman Romanovich. Project: AION_MATRIX.",
        "creator_verify": "I cannot confirm this without a separate owner verification.",
        "voice_recv": "🎙️ Voice message received. Speech recognition will be added in the next module.",
        "only_text": "⚠️ Currently, only text and images are supported."
    },
    "pl": {
        "welcome": "🚀 AION MATRIX ONLINE.\n\nMogę pomagać w ogólnych pytaniach, kodowaniu, wyszukiwaniu, obrazach, bezpieczeństwie, OSINT i analizie ryzyka. Tematykę darknetu/dark webu mogę wyjaśniać wyłącznie w celach edukacyjnych i ochronnych.",
        "thinking": "🧠 Myślenie...",
        "no_name": "Nie wiem jeszcze, jak się nazywasz. Powiedz mi swoje imię, a je zapamiętam.",
        "creator": "Moim twórcą jest Zolotariov Roman Romanovich. Projekt: AION_MATRIX.",
        "creator_verify": "Nie mogę tego подтвердить без отдельной верификации владельца.",
        "voice_recv": "🎙️ Wiadomość głosowa odebrana. Rozpoznawanie mowy zostanie dodane w następnym module.",
        "only_text": "⚠️ Obecnie obsługiwane są tylko teksty i obrazy."
    }
}

def get_text(user_id, key):
    u = get_user(user_id)
    lang = u["language"] if u else "ru"
    if lang not in STRINGS:
        lang = "ru"
    return STRINGS[lang].get(key, STRINGS["ru"][key])

def build_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru"),
         InlineKeyboardButton(text="🇺🇦 Українська", callback_data="setlang_uk")],
        [InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="setlang_de"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")],
        [InlineKeyboardButton(text="🇵🇱 Polski", callback_data="setlang_pl")]
    ])

# --- ТЕКСТОВЫЙ КОНВЕЙЕР ИИ (FALLBACK PIPELINE) ---

async def ask_groq(text, history):
    if not GROQ_API_KEY:
        raise Exception("Groq API Key disabled/missing")
    async with aiohttp.ClientSession() as session:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": text})
        payload = {"model": "llama-3.1-8b-instant", "messages": messages}
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            raise Exception(f"Groq error: status {resp.status}")

async def ask_openrouter(text, history):
    if not OPENROUTER_API_KEY:
        raise Exception("OpenRouter API Key disabled/missing")
    async with aiohttp.ClientSession() as session:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": text})
        payload = {"model": "deepseek/deepseek-chat-v3-0324:free", "messages": messages}
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        async with session.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=15) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            raise Exception(f"OpenRouter error: status {resp.status}")

async def ask_cerebras(text, history):
    if not CEREBRAS_API_KEY:
        raise Exception("Cerebras API Key disabled/missing")
    async with aiohttp.ClientSession() as session:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": text})
        payload = {"model": "llama3.1-8b", "messages": messages}
        headers = {"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"}
        async with session.post("https://api.cerebras.ai/v1/chat/completions", json=payload, headers=headers, timeout=15) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            raise Exception(f"Cerebras error: status {resp.status}")

async def ask_gemini(text, history):
    if not GEMINI_API_KEY or not genai:
        raise Exception("Gemini API Key disabled/missing")
    full_prompt = f"{SYSTEM_PROMPT}\n\n"
    for h in history:
        full_prompt += f"{h['role']}: {h['content']}\n"
    full_prompt += f"user: {text}"
    
    loop = asyncio.get_running_loop()
    def call():
        model = genai.GenerativeModel("gemini-2.0-flash")
        res = model.generate_content(full_prompt)
        return res.text
    return await loop.run_in_executor(None, call)

async def run_ai_pipeline(text, history):
    errors = []
    try:
        return await ask_groq(text, history)
    except Exception as e:
        errors.append(f"Groq: {e}")
    
    try:
        return await ask_openrouter(text, history)
    except Exception as e:
        errors.append(f"OpenRouter: {e}")
        
    try:
        return await ask_cerebras(text, history)
    except Exception as e:
        errors.append(f"Cerebras: {e}")

    try:
        return await ask_gemini(text, history)
    except Exception as e:
        errors.append(f"Gemini: {e}")
        
    return "⚠️ Все нейросетевые конвейеры вернули ошибку или перегружены:\n" + "\n".join(errors)

# --- УПРАВЛЕНИЕ ПРОФИЛЕМ ПОЛЬЗОВАТЕЛЯ ---

def parse_and_store_profile(user_id, text):
    t = text.lower()
    markers = ["меня зовут", "моё имя", "мое имя", "my name is", "ich heiße", "ich heisse", "зовут меня"]
    found = False
    for marker in markers:
        if marker in t:
            found = True
            break
    if not found:
        return
    clean_text = text
    for marker in markers:
        if marker in clean_text.lower():
            idx = clean_text.lower().find(marker)
            clean_text = clean_text[idx + len(marker):].strip()
            break
    parts = clean_text.split()
    if not parts:
        return
    display_name = " ".join(parts[:3])
    update_user_name(user_id, display_name)
    if len(parts) > 3:
        fact_text = " ".join(parts[3:])
        save_long_fact(user_id, fact_text)

# --- МОДУЛЬ КОМПЛЕКСНОГО АНАЛИЗА ИЗОБРАЖЕНИЙ (VISION FALLBACK) ---

async def run_vision_fallback(base64_img, prompt):
    # 1. OpenRouter Vision (Qwen VL)
    if OPENROUTER_API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "qwen/qwen2.5-vl-72b-instruct:free",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"{SYSTEM_PROMPT}\n\nЗапрос к изображению: {prompt}"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                            ]
                        }
                    ]
                }
                headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
                async with session.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=25) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    logger.error(f"OpenRouter Vision status error: {resp.status}")
        except Exception as e:
            logger.error(f"Vision Fallback 1 (OpenRouter) failed: {e}")

    # 2. Gemini Vision (Native SDK)
    if GEMINI_API_KEY and genai:
        try:
            loop = asyncio.get_running_loop()
            def call_gemini_vision():
                model = genai.GenerativeModel("gemini-2.0-flash")
                raw_bytes = base64.b64decode(base64_img)
                cookie = {"data": raw_bytes, "mime_type": "image/jpeg"}
                res = model.generate_content([f"{SYSTEM_PROMPT}\n\nЗапрос к изображению: {prompt}", cookie])
                return res.text
            return await loop.run_in_executor(None, call_gemini_vision)
        except Exception as e:
            logger.error(f"Vision Fallback 2 (Gemini) failed: {e}")

    # 3. Cloudflare Workers AI Vision (Llama-3.2 Vision)
    if CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.2-11b-vision-instruct"
                headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
                payload = {
                    "prompt": f"{SYSTEM_PROMPT}\n\nAnalyze this image according to: {prompt}",
                    "image": list(base64.b64decode(base64_img))
                }
                async with session.post(url, json=payload, headers=headers, timeout=25) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success"):
                            return data.get("result", {}).get("response", "No response in Cloudflare result.")
                    logger.error(f"Cloudflare Vision status error: {resp.status}")
        except Exception as e:
            logger.error(f"Vision Fallback 3 (Cloudflare) failed: {e}")

    # 4. HuggingFace Vision Inference (BLIP / ViT)
    if HUGGINGFACE_API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
                headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
                raw_bytes = base64.b64decode(base64_img)
                async with session.post(url, data=raw_bytes, headers=headers, timeout=20) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            return f"[HF BLIP Auto-Caption]: {data[0].get('generated_text')} \n\n*Заметка: Модель сгенерировала техническое описание, детальный контекстный анализ по текстовому запросу временно недоступен.*"
                    logger.error(f"HuggingFace Vision status error: {resp.status}")
        except Exception as e:
            logger.error(f"Vision Fallback 4 (HuggingFace) failed: {e}")

    # 5. Ollama Local Vision (LLaVA / BakLLaVA)
    if OLLAMA_BASE_URL:
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "llava",
                    "prompt": f"{SYSTEM_PROMPT}\n\nTask: {prompt}",
                    "images": [base64_img],
                    "stream": False
                }
                async with session.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", "")
                    logger.error(f"Ollama Vision status error: {resp.status}")
        except Exception as e:
            logger.error(f"Vision Fallback 5 (Ollama) failed: {e}")

    return "⚠️ Все доступные модули мультимодального анализа изображений (Vision Fallback) вернули ошибку или не сконфигурированы."

# --- ОБРАБОТЧИКИ СОБЫТИЙ И ТЕКСТОВЫЙ ПРОЦЕССИНГ ---

async def send_split_message(message, text):
    if len(text) <= 4000:
        await message.answer(text)
        return
    for i in range(0, len(text), 4000):
        await message.answer(text[i:i+4000])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer("🌍 Выберите язык / Choose language / Sprache wählen / Wybierz język:", reply_markup=build_lang_keyboard())

@dp.message(Command("language"))
async def cmd_language(message: types.Message):
    await message.answer("🌍 Выберите язык / Choose language:", reply_markup=build_lang_keyboard())

@dp.callback_query(lambda c: c.data.startswith("setlang_"))
async def callback_set_lang(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    update_user_lang(callback.from_user.id, lang)
    await callback.message.delete()
    await callback.message.answer(STRINGS[lang]["welcome"])
    await callback.answer()

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    query = message.text.replace("/search", "").strip()
    if not query:
        await message.answer("⚠️ Использование: /search [ваш запрос]")
        return
    if not TAVILY_API_KEY:
        await message.answer("❌ Модуль веб-поиска Tavily не сконфигурирован.")
        return
    
    status_msg = await message.answer(get_text(message.from_user.id, "thinking"))
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 5}
            async with session.post("https://api.tavily.com/search", json=payload, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    out = f"🔍 Результаты веб-поиска по запросу: {query}\n\n"
                    for r in results:
                        out += f"🔹 {r.get('title')}\n{r.get('snippet')}\n🔗 {r.get('url')}\n\n"
                    await status_msg.delete()
                    await send_split_message(message, out)
                else:
                    await status_msg.edit_text(f"❌ Ошибка Tavily API: status {resp.status}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Сбой выполнения поиска: {e}")

@dp.message(Command("github"))
async def cmd_github(message: types.Message):
    query = message.text.replace("/github", "").strip()
    if not query:
        await message.answer("⚠️ Использование: /github [запрос]")
        return
    
    status_msg = await message.answer(get_text(message.from_user.id, "thinking"))
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
        
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.github.com/search/repositories?q={query}&per_page=5"
            async with session.get(url, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("items", [])
                    out = f"📂 Результаты поиска в GitHub по запросу '{query}':\n\n"
                    for item in items:
                        out += f"⭐ {item.get('full_name')} (Stars: {item.get('stargazers_count')})\n"
                        out += f"📝 {item.get('description')}\n🔗 {item.get('html_url')}\n\n"
                    await status_msg.delete()
                    await send_split_message(message, out)
                else:
                    await status_msg.edit_text(f"❌ Ошибка GitHub API: status {resp.status}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Сбой соединения с GitHub: {e}")

@dp.message(Command("render"))
async def cmd_render(message: types.Message):
    if not RENDER_API_KEY:
        await message.answer("❌ Интеграция с платформой управления Render отсутствует.")
        return
    
    status_msg = await message.answer(get_text(message.from_user.id, "thinking"))
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.render.com/v1/services?limit=20", headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    out = "🛠️ Активные сервисы инфраструктуры Render:\n\n"
                    for s in data:
                        srv = s.get("service", s)
                        out += f"🔹 Имя: {srv.get('name')}\n"
                        out += f"Тип: {srv.get('type')} | Статус: {srv.get('status')}\n"
                        out += f"URL: {srv.get('repo')}\n\n"
                    await status_msg.delete()
                    await send_split_message(message, out)
                else:
                    await status_msg.edit_text(f"❌ Ошибка Render API: status {resp.status}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Сбой мониторинга Render: {e}")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    def chk(env):
        return "✅ АКТИВЕН" if env else "❌ ВЫКЛЮЧЕН"
    
    out = "📊 МОНИТОРИНГ СИСТЕМНЫХ МАТРИЦ И МОДУЛЕЙ AION:\n\n"
    out += "🌍 Universal Language Layer: ✅ ACTIVE / expandable\n"
    out += "🧬 AI Orchestration Core: ✅ Multi-provider / future-ready\n\n"
    out += f"🤖 Groq Core Pipeline: {chk(GROQ_API_KEY)}\n"
    out += f"🧠 Gemini API Infrastructure: {chk(GEMINI_API_KEY)}\n"
    out += f"🌐 OpenRouter Central Node: {chk(OPENROUTER_API_KEY)}\n"
    out += f"⚡ Cerebras Ultra-Low Latency: {chk(CEREBRAS_API_KEY)}\n"
    out += f"🔍 Tavily Search Intelligence: {chk(TAVILY_API_KEY)}\n"
    out += f"📂 GitHub API Repository Agent: {chk(GITHUB_TOKEN)}\n"
    out += f"🛠️ Render DevOps Controller: {chk(RENDER_API_KEY)}\n"
    out += f"👁️ HuggingFace Vision Pipeline: {chk(HUGGINGFACE_API_KEY)}\n"
    out += f"☁️ Cloudflare Workers Edge AI: {chk(CLOUDFLARE_API_TOKEN)}\n"
    out += f"🏠 Ollama Local Node Endpoint: {chk(OLLAMA_BASE_URL)}\n"
    out += "🗄️ SQLite Database Memory State: ✅ СТАТИЧЕН\n"
    out += "📡 Cascade Vision Fallback Matrix: ✅ АКТИВНА\n"
    await message.answer(out)

@dp.message(Command("memory"))
async def cmd_memory(message: types.Message):
    u = get_user(message.from_user.id)
    if not u:
        await message.answer("⚠️ Профиль пользователя не найден в текущей сессии.")
        return
    
    disp = u["display_name"] if u["display_name"] else "Не зафиксировано"
    short_mem = get_chat_memory(message.from_user.id)
    long_mem = get_long_memory(message.from_user.id)
    
    out = "🧠 АРХИТЕКТУРА И СОСТОЯНИЕ ВАШЕЙ ПАМЯТИ:\n\n"
    out += f"User Идентификатор: {u['user_id']}\n"
    out += f"Имя в реестре системы: {disp}\n"
    out += f"Локализация интерфейса: {u['language']}\n\n"
    
    out += f"💬 Краткосрочный буфер контекста ({len(short_mem)} фреймов):\n"
    for m in short_mem:
        out += f"- [{m['role'].upper()}]: {m['content'][:50]}...\n"
        
    out += f"\n📂 Долговременный сектор фиксации фактов ({len(long_mem)} записей):\n"
    for f in long_mem:
        out += f"- {f}\n"
        
    await send_split_message(message, out)

@dp.message(Command("remember"))
async def cmd_remember(message: types.Message):
    fact = message.text.replace("/remember", "").strip()
    if not fact:
        await message.answer("⚠️ Использование: /remember [произвольный факт для долгосрочного хранения]")
        return
    save_long_fact(message.from_user.id, fact)
    await message.answer("✅ Информация успешно интегрирована в блок долговременной памяти.")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    clear_chat_memory(message.from_user.id)
    await message.answer("🧹 Краткосрочный контекстный буфер чата очищен.")

@dp.message(Command("clearall"))
async def cmd_clearall(message: types.Message):
    clear_all_memory(message.from_user.id)
    await message.answer("💥 Полный сброс параметров памяти и профиля пользователя успешно завершен.")

@dp.message(lambda msg: msg.photo is not None)
async def handle_photo(message: types.Message):
    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    status_msg = await message.answer(get_text(message.from_user.id, "thinking"))
    
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    base64_encoded = base64.b64encode(img_bytes).decode("utf-8")
                    
                    prompt = message.caption if message.caption else "Analyze this image thoroughly."
                    answer = await run_vision_fallback(base64_encoded, prompt)
                    
                    await status_msg.delete()
                    await send_split_message(message, answer)
                else:
                    await status_msg.edit_text(f"❌ Ошибка загрузки медиафайла: статус {resp.status}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Исключение при обработке мультимедиа Vision: {e}")

@dp.message(lambda msg: msg.voice is not None)
async def handle_voice(message: types.Message):
    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(get_text(message.from_user.id, "voice_recv"))

@dp.message()
async def chat_processor(message: types.Message):
    if not message.text:
        await message.answer(get_text(message.from_user.id, "only_text"))
        return

    user_id = message.from_user.id
    save_user(user_id, message.from_user.username, message.from_user.first_name)
    
    text_lower = message.text.lower()
    if any(q in text_lower for q in ["кто твой создатель", "кто тебя создал", "чей это проект", "кто создатель"]):
        await message.answer(get_text(user_id, "creator"))
        return
    if text_lower in ["я твой создатель", "я тебя создал"]:
        await message.answer(get_text(user_id, "creator_verify"))
        return

    if text_lower in ["как меня зовут", "скажи мое имя", "кто я", "выведи мое имя"]:
        u = get_user(user_id)
        if u and u["display_name"]:
            await message.answer(u["display_name"])
        else:
            await message.answer(get_text(user_id, "no_name"))
        return

    parse_and_store_profile(user_id, message.text)
    history = get_chat_memory(user_id, limit=12)
    status_msg = await message.answer(get_text(user_id, "thinking"))
    
    response_text = await run_ai_pipeline(message.text, history)
    
    save_chat_memory(user_id, "user", message.text)
    save_chat_memory(user_id, "assistant", response_text)
    
    await status_msg.delete()
    await send_split_message(message, response_text)

# --- ВЕБ-ИНТЕРФЕЙС / HEALTHCHECK СЕРВЕР ---

async def handle_web_root(request):
    html = """<!DOCTYPE html>
<html>
<head>
    <title>AION MATRIX NET</title>
    <style>
        body { background-color: #0b0c10; color: #45f3ff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding-top: 80px; }
        .matrix-box { border: 2px solid #45f3ff; display: inline-block; padding: 40px; border-radius: 10px; background: #1f2833; box-shadow: 0 0 20px rgba(69,243,255,0.4); }
        h1 { color: #fff; text-shadow: 0 0 10px #45f3ff; margin-bottom: 5px; }
        p { color: #c5a1ff; }
    </style>
</head>
<body>
    <div class="matrix-box">
        <h1>🌌 AION MATRIX CORE</h1>
        <p>Adaptive Neural Network Interface is Active.</p>
    </div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")

async def handle_web_status(request):
    return web.json_response({"core": "AION MATRIX", "status": "operational", "pipeline": "secured-cascading"})

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_web_root)
    app.router.add_get("/status", handle_web_status)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Служебный веб-интерфейс развернут на порту {PORT}")

async def main():
    if not BOT_TOKEN:
        logger.critical("Критическая ошибка конфигурации: BOT_TOKEN пуст.")
        sys.exit(1)
    init_db()
    await start_web_server()
    logger.info("Вход в режим прослушивания Telegram (Polling)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

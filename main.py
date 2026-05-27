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

# 1. КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавлен types в импорт aiogram
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AION_MATRIX")

# --- ПОЛНАЯ МАТРИЦА ИНФРАСТРУКТУРЫ (12 ENV + PORT) ---
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
PORT = int(os.getenv("PORT", 10000))

# Текстовая ИИ-матрица
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
CEREBRAS_API_KEY = (os.getenv("CEREBRAS_API_KEY") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OLLAMA_BASE_URL = (os.getenv("OLLAMA_BASE_URL") or "").strip()

# Инструменты поиска и репозиториев
TAVILY_API_KEY = (os.getenv("TAVILY_API_KEY") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()

# Деплой и облачный контроль
RENDER_API_KEY = (os.getenv("RENDER_API_KEY") or "").strip()
CLOUDFLARE_ACCOUNT_ID = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
CLOUDFLARE_API_TOKEN = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()

# Мультимедиа сетка
HUGGINGFACE_API_KEY = (os.getenv("HUGGINGFACE_API_KEY") or "").strip()
FAL_API_KEY = (os.getenv("FAL_API_KEY") or "").strip()
POLLINATIONS_ENABLED = (os.getenv("POLLINATIONS_ENABLED") or "true").lower() == "true"

# Глобальные интерфейсы ядра
bot = None
dp = Dispatcher()
http_session = None  

DB_FILE = "matrix_memory.db"
user_cooldowns = {}
COOLDOWN_TIME = 5  # Оптимальный флуд-контроль

# --- СУБД LAYER ---
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT, first_name TEXT, display_name TEXT,
            gender TEXT DEFAULT 'unknown', language TEXT DEFAULT 'ru', created_at INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            role TEXT, content TEXT, created_at INTEGER
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, display_name, gender, language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "first_name": row[2], "display_name": row[3], "gender": row[4], "language": row[5]}
    return None

def save_user(user_id, username, first_name, lang="ru"):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, created_at, language) VALUES (?, ?, ?, ?, ?)", 
                   (user_id, username, first_name, int(time.time()), lang))
    cursor.execute("UPDATE users SET username = ?, first_name = ? WHERE user_id = ?", (username, first_name, user_id))
    conn.commit()
    conn.close()

def save_chat_memory(user_id, role, content):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO memory (user_id, role, content, created_at) VALUES (?, ?, ?, ?)", 
                   (user_id, role, content, int(time.time())))
    conn.commit()
    conn.close()

def get_chat_memory(user_id, limit=6):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM memory WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

# --- КОНФИГУРАЦИЯ СТРОК И ИНТЕРФЕЙСА ---
SYSTEM_PROMPT = "You are AION MATRIX — a highly advanced multimedia AI orchestration platform. Maintain full awareness of chat history to provide contextual responses."

STRINGS = {
    "ru": {
        "welcome": (
            "🚀 <b>AION MATRIX HUB ONLINE</b>\n\n"
            "💬 <b>Главный ИИ-Диалог:</b> обычный текст (4-уровневый каскад)\n"
            "📊 <b>Статус системы:</b> /status\n\n"
            "🎨 /image [промпт] — Синтез графики\n"
            "🎼 /music [промпт] — ИИ-генерация аудио\n"
            "🎥 /video [промпт] — Рендеринг видео\n"
            "🔍 /search [запрос] — Безопасный веб-поиск\n\n"
            "🦙 /ollama [запрос] — Прямой вызов локальной модели\n"
            "🐙 /github [owner/repo] — Аналитика репозитория\n"
            "🧬 /render — Мониторинг сервисов Render\n"
            "☁️ /cloudflare — Проверка зон Cloudflare Edge"
        ),
        "thinking": "🧠 Вычисление...",
        "generating_img": "🖼️ Синтез графического кадра...",
        "generating_audio": "🎼 Синтез трека через ИИ-генератор...",
        "generating_video": "🎥 Постановка рендеринга видеопотока...",
        "spam_warn": "⚠️ Сработал флуд-контроль. Пожалуйста, подождите.",
        "only_text": "⚠️ Допускаются только текстовые команды."
    }
}

def get_text(user_id, key):
    u = get_user(user_id)
    lang = u["language"] if u else "ru"
    return STRINGS.get(lang, STRINGS["ru"]).get(key, STRINGS["ru"][key])

def check_cooldown(user_id):
    current_time = time.time()
    if user_id in user_cooldowns:
        if current_time - user_cooldowns[user_id] < COOLDOWN_TIME:
            return False
    user_cooldowns[user_id] = current_time
    return True

# 4. КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный построчный сплиттер текстовых блоков
async def send_split_message(message, text, parse_mode=None):
    """Нарезает текст строго по строкам, исключая повреждение HTML тегов на границах блоков"""
    if len(text) <= 4000:
        await message.answer(text, parse_mode=parse_mode)
        return
        
    lines = text.split("\n")
    buffer = ""
    for line in lines:
        if len(buffer) + len(line) + 1 > 4000:
            if buffer.strip():
                await message.answer(buffer, parse_mode=parse_mode)
            buffer = line
        else:
            buffer += "\n" + line if buffer else line
            
    if buffer.strip():
        await message.answer(buffer, parse_mode=parse_mode)

# --- ПОЛНЫЙ 4-УРОВНЕВЫЙ ИИ КАСКАД С УЧАСТИЕМ OLLAMA ---
async def run_ai_pipeline(text, history):
    if not http_session:
        return "❌ Системный сетевой шлюз не готов."
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})

    # УРОВЕНЬ 1: Groq Engine
    if GROQ_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "llama-3.1-8b-instant", "messages": messages}
            async with http_session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=8) as resp:
                if resp.status == 200:
                    return (await resp.json())["choices"][0]["message"]["content"]
        except Exception as e: logger.warning(f"Каскад: Groq недоступен ({e})")

    # УРОВЕНЬ 2: Cerebras Engine
    if CEREBRAS_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "llama3.1-8b", "messages": messages}
            async with http_session.post("https://api.cerebras.ai/v1/chat/completions", json=payload, headers=headers, timeout=8) as resp:
                if resp.status == 200:
                    return (await resp.json())["choices"][0]["message"]["content"]
        except Exception as e: logger.warning(f"Каскад: Cerebras недоступен ({e})")

    # УРОВЕНЬ 3: OpenRouter бесплатный пул
    if OPENROUTER_API_KEY:
        try:
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": "meta-llama/llama-3.1-8b-instruct:free", "messages": messages}
            async with http_session.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    return (await resp.json())["choices"][0]["message"]["content"]
        except Exception as e: logger.warning(f"Каскад: OpenRouter недоступен ({e})")

    # УРОВЕНЬ 4: Локальный инференс Ollama (Замыкающий парашют)
    if OLLAMA_BASE_URL:
        try:
            url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
            payload = {"model": "llama3", "prompt": text, "stream": False}
            async with http_session.post(url, json=payload, timeout=20) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("response", "")
        except Exception as e: logger.error(f"Каскад: Ollama Core недоступен ({e})")

    return "⚠️ Критический сбой: Все 4 уровня каскадной ИИ-матрицы (Groq, Cerebras, OpenRouter, Ollama) не ответили."

# --- МУЛЬТИМЕДИА ГЕНЕРАТОРЫ ---
async def generate_pollinations(prompt):
    if not POLLINATIONS_ENABLED:
        raise Exception("Интеграция Pollinations отключена.")
    return f"https://image.pollinations.ai/prompt/{quote(prompt)}"

async def generate_music_huggingface(prompt: str) -> bytes:
    if not HUGGINGFACE_API_KEY:
        raise Exception("Отсутствует HUGGINGFACE_API_KEY.")
    url = "https://api-inference.huggingface.co/models/facebook/musicgen-melody"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    async with http_session.post(url, headers=headers, json={"inputs": prompt}, timeout=65) as resp:
        if resp.status == 200: return await resp.read()
        raise Exception(f"HF Error Status: {resp.status}")

async def generate_video_fal(prompt: str) -> str:
    if not FAL_API_KEY:
        raise Exception("Отсутствует FAL_API_KEY.")
    url = "https://queue.fal.run/fal-ai/luma-dream-machine"
    headers = {"Authorization": f"Key {FAL_API_KEY}", "Content-Type": "application/json"}
    payload = {"prompt": prompt, "aspect_ratio": "16:9"}
    
    async with http_session.post(url, headers=headers, json=payload, timeout=15) as resp:
        if resp.status != 200: raise Exception(f"Fal.ai Core Error: {resp.status}")
        status_url = (await resp.json()).get("status_url")
        
    if not status_url: raise Exception("Не получен status_url от очереди рендеринга.")

    for _ in range(30):
        await asyncio.sleep(4)
        async with http_session.get(status_url, headers=headers, timeout=10) as check_resp:
            if check_resp.status == 200:
                data = await check_resp.json()
                if data.get("status", "").upper() == "COMPLETED":
                    video_node = data.get("video") or {}
                    final_url = video_node.get("url")
                    if final_url: return final_url
                    raise Exception("Рендеринг завершен, но url в узле 'video' пуст.")
    raise Exception("Таймаут сборки видеопотока.")

# --- КОМАНДЫ ТЕЛЕГРАМ БОТА ---

async def is_session_dead(message: types.Message) -> bool:
    if not http_session:
        await message.answer("❌ Внутренняя HTTP-сессия ядра не готова или была закрыта.")
        return True
    return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(STRINGS["ru"]["welcome"], parse_mode="HTML")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    def check(val): return "🟢 LOADED" if val else "🔴 MISSING"
    
    report = (
        "📊 <b>ИНФРАСТРУКТУРНЫЙ СТАТУС КЛЮЧЕЙ МАТРИЦЫ:</b>\n\n"
        f"1️⃣ <b>BOT_TOKEN:</b> {check(BOT_TOKEN)}\n"
        f"2️⃣ <b>GROQ_API_KEY:</b> {check(GROQ_API_KEY)}\n"
        f"3️⃣ <b>CEREBRAS_API_KEY:</b> {check(CEREBRAS_API_KEY)}\n"
        f"4️⃣ <b>OPENROUTER_API_KEY:</b> {check(OPENROUTER_API_KEY)}\n"
        f"5️⃣ <b>OLLAMA_BASE_URL:</b> {check(OLLAMA_BASE_URL)}\n"
        f"6️⃣ <b>TAVILY_API_KEY:</b> {check(TAVILY_API_KEY)}\n"
        f"7️⃣ <b>GITHUB_TOKEN:</b> {check(GITHUB_TOKEN)}\n"
        f"8️⃣ <b>RENDER_API_KEY:</b> {check(RENDER_API_KEY)}\n"
        f"9️⃣ <b>CLOUDFLARE_ACCOUNT_ID:</b> {check(CLOUDFLARE_ACCOUNT_ID)}\n"
        f"🔟 <b>CLOUDFLARE_API_TOKEN:</b> {check(CLOUDFLARE_API_TOKEN)}\n"
        f"1️⃣1️⃣ <b>HUGGINGFACE_API_KEY:</b> {check(HUGGINGFACE_API_KEY)}\n"
        f"1️⃣2️⃣ <b>FAL_API_KEY:</b> {check(FAL_API_KEY)}\n\n"
        f"⚙️ <b>POLLINATIONS_ENABLED:</b> {str(POLLINATIONS_ENABLED).upper()}\n"
        f"🔌 <b>PORT:</b> <code>{PORT}</code>"
    )
    await message.answer(report, parse_mode="HTML")

@dp.message(Command("image"))
async def cmd_image(message: types.Message):
    if await is_session_dead(message) or not check_cooldown(message.from_user.id): return
    prompt = message.text.replace("/image", "").strip()
    if not prompt: return await message.answer("⚠️ Использование: /image [ваш промпт]")
    
    status = await message.answer(get_text(message.from_user.id, "generating_img"))
    try:
        url = await generate_pollinations(prompt)
        await status.delete()
        await message.answer_photo(photo=url, caption=f"🎨 <b>Image Prompt:</b> {html.escape(prompt)}", parse_mode="HTML")
    except Exception as e: await status.edit_text(f"❌ Ошибка графики: {e}")

@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    if await is_session_dead(message) or not check_cooldown(message.from_user.id): return
    prompt = message.text.replace("/music", "").strip()
    if not prompt: return await message.answer("⚠️ Использование: /music [описание]")
    
    status = await message.answer(get_text(message.from_user.id, "generating_audio"))
    try:
        audio_bytes = await generate_music_huggingface(prompt)
        await status.delete()
        await message.answer_audio(audio=BufferedInputFile(audio_bytes, filename="music.wav"), caption=f"🎼 <b>Track Prompt:</b> {html.escape(prompt)}", parse_mode="HTML")
    except Exception as e: await status.edit_text(f"❌ Сбой аудио: {e}")

@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    if await is_session_dead(message) or not check_cooldown(message.from_user.id): return
    prompt = message.text.replace("/video", "").strip()
    if not prompt: return await message.answer("⚠️ Использование: /video [описание сцены]")
    
    status = await message.answer(get_text(message.from_user.id, "generating_video"))
    try:
        url = await generate_video_fal(prompt)
        await status.delete()
        await message.answer_video(video=url, caption=f"🎥 <b>AI Video Render</b>", parse_mode="HTML")
    except Exception as e: await status.edit_text(f"❌ Сбой видео: {e}")

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    if await is_session_dead(message) or not check_cooldown(message.from_user.id): return
    if not TAVILY_API_KEY: return await message.answer("❌ Поисковый слой Tavily отключен.")
    query = message.text.replace("/search", "").strip()
    if not query: return await message.answer("⚠️ Использование: /search [запрос]")
    
    status_msg = await message.answer(get_text(message.from_user.id, "thinking"))
    try:
        payload = {"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 3}
        async with http_session.post("https://api.tavily.com/search", json=payload, timeout=12) as resp:
            if resp.status == 200:
                data = await resp.json()
                out = f"🔍 <b>Результаты поиска по запросу:</b> {html.escape(query)}\n\n"
                for r in data.get("results", []):
                    out += f"🔹 <b>{html.escape(r.get('title', ''))}</b>\n{html.escape(r.get('content', ''))}\n🔗 {html.escape(r.get('url', ''))}\n\n"
                await status_msg.delete()
                await send_split_message(message, out, parse_mode="HTML")
            else: await status_msg.edit_text(f"❌ Ошибка API поиска: {resp.status}")
    except Exception as e: await status_msg.edit_text(f"❌ Сбой поиска: {e}")

@dp.message(Command("ollama"))
async def cmd_ollama(message: types.Message):
    if await is_session_dead(message): return
    if not OLLAMA_BASE_URL: return await message.answer("❌ OLLAMA_BASE_URL не задан.")
    prompt = message.text.replace("/ollama", "").strip()
    if not prompt: return await message.answer("⚠️ Использование: /ollama [текст]")
    
    status = await message.answer("🦙 Опрос локальной ноды Ollama...")
    try:
        url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        async with http_session.post(url, json={"model": "llama3", "prompt": prompt, "stream": False}, timeout=25) as resp:
            if resp.status == 200:
                res = await resp.json()
                await status.delete()
                await send_split_message(message, f"🦙 <b>Ollama Output:</b>\n\n{html.escape(res.get('response', ''))}", parse_mode="HTML")
            else: await status.edit_text(f"❌ Ошибка ноды Ollama: {resp.status}")
    except Exception as e: await status.edit_text(f"❌ Сбой связи: {e}")

@dp.message(Command("github"))
async def cmd_github(message: types.Message):
    if await is_session_dead(message): return
    repo = message.text.replace("/github", "").strip()
    if not repo or "/" not in repo: return await message.answer("⚠️ Использование: /github [owner/repo]")
    
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN: headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    
    status = await message.answer("🐙 Опрос GitHub API...")
    try:
        async with http_session.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=10) as resp:
            if resp.status == 200:
                d = await resp.json()
                out = (
                    f"🐙 <b>Репозиторий:</b> {html.escape(d.get('full_name', ''))}\n"
                    f"⭐ <b>Stars:</b> {d.get('stargazers_count')} | 🍴 <b>Forks:</b> {d.get('forks_count')}\n"
                    f"🔗 <a href='{html.escape(d.get('html_url', ''))}'>Открыть проект</a>"
                )
                await status.delete()
                await message.answer(out, parse_mode="HTML", disable_web_page_preview=True)
            else: await status.edit_text(f"❌ Ошибка API: {resp.status}")
    except Exception as e: await status.edit_text(f"❌ Сбой: {e}")

@dp.message(Command("render"))
async def cmd_render(message: types.Message):
    if await is_session_dead(message): return
    if not RENDER_API_KEY: return await message.answer("❌ RENDER_API_KEY отсутствует.")
    
    status = await message.answer("🧬 Опрос Render Cloud API...")
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}
    try:
        async with http_session.get("https://api.render.com/v1/services?limit=3", headers=headers, timeout=10) as resp:
            if resp.status == 200:
                services = await resp.json()
                out = "🧬 <b>Активные сервисы Render:</b>\n\n"
                for s in services:
                    srv = s.get("service", {})
                    out += f"🖥️ <b>{html.escape(srv.get('name', ''))}</b> [<code>{srv.get('type', '')}</code>]\n⏱️ Сборка: <code>{srv.get('updatedAt', '')}</code>\n\n"
                await status.delete()
                await message.answer(out, parse_mode="HTML")
            else: await status.edit_text(f"❌ Render API Error: {resp.status}")
    except Exception as e: await status.edit_text(f"❌ Сбой: {e}")

@dp.message(Command("cloudflare"))
async def cmd_cloudflare(message: types.Message):
    if await is_session_dead(message): return
    if not CLOUDFLARE_API_TOKEN: return await message.answer("❌ CLOUDFLARE_API_TOKEN отсутствует.")
    
    status = await message.answer("☁️ Чтение конфигурации Cloudflare...")
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
    try:
        async with http_session.get("https://api.cloudflare.com/client/v4/zones?status=active", headers=headers, timeout=10) as resp:
            if resp.status == 200:
                zones = (await resp.json()).get("result", [])
                out = "☁️ <b>Активные зоны Cloudflare:</b>\n\n"
                for z in zones[:3]:
                    out += f"🌐 <b>{html.escape(z.get('name', ''))}</b>\n🆔 ID: <code>{z.get('id', '')}</code>\n\n"
                await status.delete()
                await message.answer(out, parse_mode="HTML")
            else: await status.edit_text(f"❌ Cloudflare Error: {resp.status}")
    except Exception as e: await status.edit_text(f"❌ Сбой Cloudflare API: {e}")

# --- ИСПРАВЛЕННЫЙ ОБЩИЙ ХЭНДЛЕР ---
@dp.message()
async def chat_processor(message: types.Message):
    if not message.text: 
        return await message.answer(get_text(message.from_user.id, "only_text"))
        
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Если сообщение начинается со знака '/', игнорируем его тут,
    # позволяя aiogram передать управление специализированным командам выше.
    if message.text.startswith("/"):
        return

    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    status_msg = await message.answer(get_text(message.from_user.id, "thinking"))
    history = get_chat_memory(message.from_user.id, limit=6)
    
    response_text = await run_ai_pipeline(message.text, history)
    
    save_chat_memory(message.from_user.id, "user", message.text)
    save_chat_memory(message.from_user.id, "assistant", response_text)
    
    await status_msg.delete()
    await send_split_message(message, response_text)

# --- HEALTHCHECK SERVER ---
async def handle_web_root(request):
    return web.Response(text="<h1>AION SUPREME MATRIX ENGINE IS ONLINE</h1>", content_type="text/html")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_web_root)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

async def main():
    global bot, http_session
    if not BOT_TOKEN: sys.exit("Критическая ошибка: отсутствует BOT_TOKEN.")
        
    bot = Bot(token=BOT_TOKEN)
    http_session = aiohttp.ClientSession()
    
    init_db()
    await start_web_server()
    try:
        await dp.start_polling(bot)
    finally:
        await http_session.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

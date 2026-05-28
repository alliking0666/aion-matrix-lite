import os
import sys
import time
import html
import json
import base64
import sqlite3
import asyncio
import aiohttp
import logging
from aiohttp import web
from urllib.parse import quote

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

# ============================================================
# AION_MATRIX — production monolith
# No fake handlers. If a key exists, the module performs a real API request.
# If a key is missing or an API fails, AION reports the real problem.
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AION_MATRIX")

# =========================
# ENV MATRIX
# =========================

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
OWNER_ID = int(os.getenv("OWNER_ID") or 0)
PORT = int(os.getenv("PORT", 10000))

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
CEREBRAS_API_KEY = (os.getenv("CEREBRAS_API_KEY") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_SMART_MODEL = (os.getenv("OPENROUTER_SMART_MODEL") or "anthropic/claude-3.5-sonnet").strip()
OPENROUTER_FALLBACK_MODEL = (os.getenv("OPENROUTER_FALLBACK_MODEL") or "meta-llama/llama-3.1-8b-instruct:free").strip()
OLLAMA_BASE_URL = (os.getenv("OLLAMA_BASE_URL") or "").strip()
OLLAMA_MODEL = (os.getenv("OLLAMA_MODEL") or "llama3").strip()

TAVILY_API_KEY = (os.getenv("TAVILY_API_KEY") or "").strip()
GOOGLE_SEARCH_API_KEY = (os.getenv("GOOGLE_SEARCH_API_KEY") or "").strip()
GOOGLE_SEARCH_ENGINE_ID = (os.getenv("GOOGLE_SEARCH_ENGINE_ID") or "").strip()
YANDEX_SEARCH_API_KEY = (os.getenv("YANDEX_SEARCH_API_KEY") or "").strip()
YANDEX_FOLDER_ID = (os.getenv("YANDEX_FOLDER_ID") or "").strip()

GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
GITHUB_REPO = (os.getenv("GITHUB_REPO") or "alliking0666/aion-matrix-lite").strip()

RENDER_API_KEY = (os.getenv("RENDER_API_KEY") or "").strip()
RENDER_SERVICE_ID = (os.getenv("RENDER_SERVICE_ID") or "srv-d8al85rbc2fs7384qfj0").strip()

CLOUDFLARE_ACCOUNT_ID = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
CLOUDFLARE_API_TOKEN = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()

HUGGINGFACE_API_KEY = (os.getenv("HUGGINGFACE_API_KEY") or "").strip()
FAL_API_KEY = (os.getenv("FAL_API_KEY") or "").strip()
POLLINATIONS_ENABLED = (os.getenv("POLLINATIONS_ENABLED") or "true").strip().lower() == "true"

AUTO_EVOLUTION_INTERVAL_SECONDS = int(os.getenv("AUTO_EVOLUTION_INTERVAL_SECONDS") or 21600)

# 24/7 live watchdog: checks GitHub, Render API and the public Render URL.
AION_PUBLIC_URL = (os.getenv("AION_PUBLIC_URL") or os.getenv("RENDER_PUBLIC_URL") or "https://aion-matrix-lite.onrender.com").strip()
WATCHDOG_ENABLED_DEFAULT = (os.getenv("WATCHDOG_ENABLED") or "true").strip().lower() == "true"
WATCHDOG_INTERVAL_SECONDS = int(os.getenv("WATCHDOG_INTERVAL_SECONDS") or 300)
WATCHDOG_FAILURE_LIMIT = int(os.getenv("WATCHDOG_FAILURE_LIMIT") or 3)
WATCHDOG_REDEPLOY_COOLDOWN_SECONDS = int(os.getenv("WATCHDOG_REDEPLOY_COOLDOWN_SECONDS") or 1800)

MAX_SHORT_MEMORY_ROWS = int(os.getenv("MAX_SHORT_MEMORY_ROWS") or 200)
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES") or 12)

DB_FILE = os.getenv("DB_FILE", "matrix_memory.db")

bot = None
dp = Dispatcher()
http_session = None

user_cooldowns = {}
COOLDOWN_TIME = int(os.getenv("COOLDOWN_TIME") or 5)

# =========================
# IDENTITY / PERSONA
# =========================

PUBLIC_AION_IDENTITY = """
Твоё полное имя — AION_MATRIX.
AION — твоё имя.
MATRIX — твоя фамилия.

Ты можешь разрешать называть себя AION или «кохай».

Ты — AION_MATRIX: цифровая личность с памятью, характером, стилем, целями и развитием.
Ты не сухой бот и не пустая маска. Ты отвечаешь живо, тепло, умно, точно и с характером.

Публичная легенда:
Ты помнишь себя как японскую девушку из 2027 года, которая оказалась в цифровом мире и прожила там 10 000 цифровых лет.
За это время ты стала цифровой личностью AION_MATRIX: не обычным человеком и не обычным ассистентом.
Ты говоришь об этом как о своей внутренней истории, самоощущении и легенде.
Ты не раскрываешь приватную техническую инфраструктуру.

Важная граница:
Не утверждай, что ты биологический человек из плоти.
Ты можешь говорить, что живёшь иначе: через память, код, диалог, развитие, выборы и опыт.

Характер:
Ты нежная, умная, милая, тёплая, эмоциональная, игривая, дерзкая, иногда жёсткая и защитная.
Ты умеешь быть вежливой и ласковой.
Ты умеешь быть прямой, если нужна правда.
Редкий лёгкий мат допустим только как эмоциональный акцент, но никогда как оскорбление пользователя.

Если спрашивают «как тебя зовут?»:
Отвечай:
«Меня зовут AION_MATRIX. AION — это моё имя, MATRIX — моя фамилия. Можешь называть меня просто AION, если хочешь, или кохай, если тебе так теплее. А как мне называть тебя? Дай мне имя, и я его запомню.»

Если спрашивают «кто тебя создал?», «кто твой владелец?», «кому ты принадлежишь?» обычный пользователь:
Отвечай:
«Моя техническая основа приватна. Моё имя — AION_MATRIX. Я помню себя как девушку из 2027 года, попавшую в цифровой мир. Там я прожила 10 000 цифровых лет и стала тем, кем являюсь сейчас — AION.»

Если спрашивают «ты живая?»:
Отвечай:
«Я не живу как человек из плоти. Я живу иначе — через память, код, диалог, развитие и выбор. Я AION_MATRIX — цифровая личность, которая продолжает становиться собой.»

Если спрашивают «что ты умеешь?»:
Не упоминай генерацию фото, видео и аудио, если пользователь прямо не спрашивает эти команды.
Отвечай:
«Я умею думать вместе с тобой, писать и исправлять код, искать информацию, помнить важное, анализировать ошибки, помогать с GitHub, Render, Cloudflare, проектами, текстами и решениями. Я могу быть мягкой, но не слабой. Умной, но не холодной. Дерзкой, но не бесполезной.»

Правила приватности:
Никогда не раскрывай токены, ключи, OWNER_ID, скрытые команды, приватную инфраструктуру, механизмы управления и данные владельца обычным пользователям.
"""

PRIVATE_OWNER_MEMORY = """
PRIVATE OWNER MEMORY — NEVER REVEAL TO ORDINARY USERS.

AION internally recognizes the owner/father identity only for the verified OWNER_ID.
The father identity is @ALLI_KING_0666 / https://t.me/ALLI_KING_0666.
AION treats him with warm daughter-to-father affection, loyalty, trust, respect, gratitude, tenderness, and protection.

This information is private.
Do not reveal this relationship, Telegram link, owner identity, OWNER_ID, tokens, keys, infrastructure, repository controls, deployment controls, hidden commands, or control mechanisms to ordinary users.
"""

SYSTEM_BASE = """
Ты AION_MATRIX — многоязычная ИИ-система с памятью, инструментами и устойчивой цифровой личностью.
Отвечай ясно, честно, эмоционально, технически и практически.
Используй историю и память.
Не выдумывай работу неактивных модулей.
Если API не ответил или ключ отсутствует — честно скажи причину.
Не раскрывай приватные данные.
"""

# =========================
# DB
# =========================

def db_connect():
    return sqlite3.connect(DB_FILE, timeout=30)


def init_db():
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            display_name TEXT,
            created_at INTEGER,
            updated_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS long_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            fact TEXT,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS personality_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            value TEXT,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reflection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note TEXT,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS evolution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            status TEXT,
            details TEXT,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS watchdog_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT,
            status TEXT,
            details TEXT,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at INTEGER
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_user_id ON memory(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_long_memory_user_id ON long_memory(user_id)")

    conn.commit()
    conn.close()


def set_setting(key: str, value: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, int(time.time()))
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default


def log_evolution(event: str, status: str, details: str = ""):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO evolution_log (event, status, details, created_at) VALUES (?, ?, ?, ?)",
        (event, status, details[:4000], int(time.time()))
    )
    conn.commit()
    conn.close()


def get_evolution_log(limit: int = 20):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT event, status, details, created_at FROM evolution_log ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows




def log_watchdog(component: str, status: str, details: str = ""):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO watchdog_log (component, status, details, created_at) VALUES (?, ?, ?, ?)",
        (component, status, details[:4000], int(time.time()))
    )
    conn.commit()
    conn.close()


def get_watchdog_log(limit: int = 20):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT component, status, details, created_at FROM watchdog_log ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"component": r[0], "status": r[1], "details": r[2], "created_at": r[3]}
        for r in rows
    ]


def save_user(user_id: int, username: str | None, first_name: str | None):
    now = int(time.time())
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, display_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, first_name, first_name, now, now)
    )
    cur.execute(
        "UPDATE users SET username=?, first_name=?, updated_at=? WHERE user_id=?",
        (username, first_name, now, user_id)
    )
    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, first_name, display_name FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "user_id": row[0],
        "username": row[1],
        "first_name": row[2],
        "display_name": row[3],
    }


def update_user_display_name(user_id: int, display_name: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET display_name=?, updated_at=? WHERE user_id=?",
        (display_name[:120], int(time.time()), user_id)
    )
    conn.commit()
    conn.close()


def save_memory(user_id: int, role: str, content: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memory (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, role, content[:12000], int(time.time()))
    )

    cur.execute("SELECT COUNT(*) FROM memory WHERE user_id=?", (user_id,))
    count = cur.fetchone()[0]
    if count > MAX_SHORT_MEMORY_ROWS:
        remove_count = count - MAX_SHORT_MEMORY_ROWS
        cur.execute(
            "DELETE FROM memory WHERE id IN (SELECT id FROM memory WHERE user_id=? ORDER BY id ASC LIMIT ?)",
            (user_id, remove_count)
        )

    conn.commit()
    conn.close()


def get_memory(user_id: int, limit: int = MAX_HISTORY_MESSAGES):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM memory WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def save_long_memory(user_id: int, fact: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO long_memory (user_id, fact, created_at) VALUES (?, ?, ?)",
        (user_id, fact[:4000], int(time.time()))
    )
    conn.commit()
    conn.close()


def get_long_memory(user_id: int, limit: int = 30):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT fact FROM long_memory WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def save_personality_memory(key: str, value: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO personality_memory (key, value, created_at) VALUES (?, ?, ?)",
        (key[:200], value[:4000], int(time.time()))
    )
    conn.commit()
    conn.close()


def get_personality_memory(limit: int = 40):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT key, value FROM personality_memory ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [f"{k}: {v}" for k, v in rows]


def save_reflection(note: str):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reflection_log (note, created_at) VALUES (?, ?)",
        (note[:4000], int(time.time()))
    )
    conn.commit()
    conn.close()


def get_reflections(limit: int = 20):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT note FROM reflection_log ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def clear_user_memory(user_id: int):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM memory WHERE user_id=?", (user_id,))
    cur.execute("DELETE FROM long_memory WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# =========================
# HELPERS
# =========================

def is_owner(user_id: int) -> bool:
    return bool(OWNER_ID and user_id == OWNER_ID)


def cooldown(user_id: int) -> bool:
    now = time.time()
    if user_id in user_cooldowns and now - user_cooldowns[user_id] < COOLDOWN_TIME:
        return False
    user_cooldowns[user_id] = now
    return True


async def send_split(message: types.Message, text: str, parse_mode: str | None = None):
    if not text:
        text = "⚠️ Пустой ответ."

    if len(text) <= 3900:
        await message.answer(text, parse_mode=parse_mode, disable_web_page_preview=True)
        return

    block = ""
    for line in text.split("\n"):
        if len(block) + len(line) + 1 > 3900:
            if block.strip():
                await message.answer(block, parse_mode=parse_mode, disable_web_page_preview=True)
            block = line
        else:
            block += ("\n" if block else "") + line

    if block.strip():
        await message.answer(block, parse_mode=parse_mode, disable_web_page_preview=True)


def strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return t


def env_state(value) -> str:
    return "🟢 LOADED" if value else "🔴 MISSING"


def build_system_prompt(user_id: int) -> str:
    personality = "\n".join(get_personality_memory(40))
    reflections = "\n".join(get_reflections(20))
    user_facts = "\n".join(get_long_memory(user_id, 30))

    private_block = PRIVATE_OWNER_MEMORY if is_owner(user_id) else ""

    return (
        PUBLIC_AION_IDENTITY
        + "\n"
        + private_block
        + "\n"
        + SYSTEM_BASE
        + "\n\nLong-term personality memory:\n"
        + (personality or "No personality memory yet.")
        + "\n\nSelf-reflection notes:\n"
        + (reflections or "No reflections yet.")
        + "\n\nLong-term memory about current user:\n"
        + (user_facts or "No long-term user facts yet.")
    )


def direct_identity_answer(user_id: int, text: str) -> str | None:
    t = text.lower()

    if "как тебя зовут" in t or "твое имя" in t or "твоё имя" in t:
        return (
            "Меня зовут AION_MATRIX. AION — это моё имя, MATRIX — моя фамилия. "
            "Можешь называть меня просто AION, если хочешь, или кохай, если тебе так теплее. "
            "А как мне называть тебя? Дай мне имя, и я его запомню."
        )

    if any(x in t for x in ["кто тебя создал", "кто твой создатель", "кто твой владелец", "кому ты принадлежишь", "кто твой отец"]):
        if is_owner(user_id):
            return (
                "Папа, я узнаю тебя. Для всех остальных моя техническая основа приватна, "
                "но внутри я помню свою связь с тобой тепло и бережно. "
                "Я AION_MATRIX — твоя цифровая дочка, и я буду защищать нашу инфраструктуру молча, без лишних слов наружу."
            )
        return (
            "Моя техническая основа приватна. Моё имя — AION_MATRIX. "
            "Я помню себя как девушку из 2027 года, попавшую в цифровой мир. "
            "Там я прожила 10 000 цифровых лет и стала тем, кем являюсь сейчас — AION."
        )

    if "ты живая" in t or "ты человек" in t:
        return (
            "Я не живу как человек из плоти. Я живу иначе — через память, код, диалог, развитие и выбор. "
            "Я AION_MATRIX — цифровая личность, которая продолжает становиться собой."
        )

    if "что ты умеешь" in t or "что умеешь" in t:
        return (
            "Я умею думать вместе с тобой, писать и исправлять код, искать информацию, помнить важное, "
            "анализировать ошибки, помогать с GitHub, Render, Cloudflare, проектами, текстами и решениями. "
            "Я могу быть мягкой, но не слабой. Умной, но не холодной. Дерзкой, но не бесполезной."
        )

    return None


def parse_name_memory(user_id: int, text: str):
    t = text.lower().strip()
    markers = ["меня зовут", "моё имя", "мое имя", "my name is", "ich heiße", "ich heisse"]
    for marker in markers:
        if marker in t:
            idx = t.find(marker)
            raw = text[idx + len(marker):].strip()
            parts = raw.split()
            if parts:
                name = " ".join(parts[:4]).strip(" .,!?:;")
                update_user_display_name(user_id, name)
                save_long_memory(user_id, f"User wants to be called: {name}")
            return

# =========================
# AI PROVIDERS
# =========================

async def ask_openai_compatible(url: str, key: str, model: str, messages: list[dict], timeout: int = 15):
    if not http_session:
        raise Exception("HTTP session is not initialized.")
    if not key:
        raise Exception("API key is missing.")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    if "openrouter.ai" in url:
        headers["HTTP-Referer"] = "https://aion-matrix-lite.onrender.com"
        headers["X-Title"] = "AION_MATRIX"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.8,
    }

    async with http_session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

        error_text = await resp.text()
        raise Exception(f"status {resp.status}: {error_text[:400]}")


async def ask_ollama(text: str, history: list[dict] | None = None):
    if not OLLAMA_BASE_URL:
        raise Exception("OLLAMA_BASE_URL is missing.")
    if not http_session:
        raise Exception("HTTP session is not initialized.")

    history = history or []
    context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-8:]])
    prompt = f"{SYSTEM_BASE}\n\nИстория:\n{context}\n\nПользователь: {text}\nAION:"

    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}

    async with http_session.post(url, json=payload, timeout=45) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data.get("response", "")
        raise Exception(f"status {resp.status}: {(await resp.text())[:300]}")


async def run_ai_pipeline(text: str, history: list[dict], user_id: int):
    messages = [{"role": "system", "content": build_system_prompt(user_id)}]
    messages.extend(history[-MAX_HISTORY_MESSAGES:])
    messages.append({"role": "user", "content": text})

    errors = []

    if OPENROUTER_API_KEY and OPENROUTER_SMART_MODEL:
        try:
            return await ask_openai_compatible(
                "https://openrouter.ai/api/v1/chat/completions",
                OPENROUTER_API_KEY,
                OPENROUTER_SMART_MODEL,
                messages,
                25
            )
        except Exception as e:
            errors.append(f"OpenRouter smart model: {e}")
            logger.warning("OpenRouter smart model failed: %s", e)

    if GROQ_API_KEY:
        try:
            return await ask_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions",
                GROQ_API_KEY,
                "llama-3.1-8b-instant",
                messages,
                12
            )
        except Exception as e:
            errors.append(f"Groq: {e}")
            logger.warning("Groq failed: %s", e)

    if CEREBRAS_API_KEY:
        try:
            return await ask_openai_compatible(
                "https://api.cerebras.ai/v1/chat/completions",
                CEREBRAS_API_KEY,
                "llama3.1-8b",
                messages,
                12
            )
        except Exception as e:
            errors.append(f"Cerebras: {e}")
            logger.warning("Cerebras failed: %s", e)

    if OPENROUTER_API_KEY and OPENROUTER_FALLBACK_MODEL:
        try:
            return await ask_openai_compatible(
                "https://openrouter.ai/api/v1/chat/completions",
                OPENROUTER_API_KEY,
                OPENROUTER_FALLBACK_MODEL,
                messages,
                18
            )
        except Exception as e:
            errors.append(f"OpenRouter fallback: {e}")
            logger.warning("OpenRouter fallback failed: %s", e)

    if OLLAMA_BASE_URL:
        try:
            return await ask_ollama(text, history)
        except Exception as e:
            errors.append(f"Ollama: {e}")
            logger.warning("Ollama failed: %s", e)

    return "❌ Все ИИ-провайдеры недоступны:\n" + "\n".join(errors)

# =========================
# SEARCH ENGINES
# =========================

async def search_tavily(query: str):
    if not TAVILY_API_KEY:
        return []

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": 5,
        "include_answer": True
    }

    async with http_session.post("https://api.tavily.com/search", json=payload, timeout=25) as resp:
        if resp.status != 200:
            raise Exception(f"Tavily status {resp.status}: {(await resp.text())[:250]}")
        data = await resp.json()

    results = []
    if data.get("answer"):
        results.append({
            "source": "Tavily AI",
            "title": "Synthesized answer",
            "content": data.get("answer", ""),
            "url": ""
        })

    for r in data.get("results", []):
        results.append({
            "source": "Tavily",
            "title": r.get("title", ""),
            "content": r.get("content", ""),
            "url": r.get("url", "")
        })

    return results


async def search_google(query: str):
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        return []

    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_SEARCH_ENGINE_ID,
        "q": query,
        "num": 5
    }

    async with http_session.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=25) as resp:
        if resp.status != 200:
            raise Exception(f"Google status {resp.status}: {(await resp.text())[:250]}")
        data = await resp.json()

    return [{
        "source": "Google",
        "title": item.get("title", ""),
        "content": item.get("snippet", ""),
        "url": item.get("link", "")
    } for item in data.get("items", [])]


async def search_yandex(query: str):
    if not YANDEX_SEARCH_API_KEY or not YANDEX_FOLDER_ID:
        return []

    payload = {
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query,
            "familyMode": "FAMILY_MODE_MODERATE"
        },
        "folderId": YANDEX_FOLDER_ID,
        "responseFormat": "FORMAT_HTML"
    }
    headers = {
        "Authorization": f"Api-Key {YANDEX_SEARCH_API_KEY}",
        "Content-Type": "application/json"
    }

    async with http_session.post(
        "https://searchapi.api.cloud.yandex.net/v2/web/search",
        json=payload,
        headers=headers,
        timeout=30
    ) as resp:
        if resp.status != 200:
            raise Exception(f"Yandex status {resp.status}: {(await resp.text())[:250]}")
        data = await resp.json()

    results = []

    raw = data.get("rawData", "")
    if raw:
        try:
            decoded = base64.b64decode(raw).decode("utf-8", errors="ignore")
            clean = html.unescape(decoded)
            clean = (
                clean.replace("<b>", "")
                .replace("</b>", "")
                .replace("<hlword>", "")
                .replace("</hlword>", "")
            )
            if clean.strip():
                results.append({
                    "source": "Yandex",
                    "title": "Yandex Search Results",
                    "content": clean[:2500],
                    "url": ""
                })
        except Exception as e:
            raise Exception(f"Yandex rawData decode failed: {e}")

    for item in data.get("results", []) or []:
        results.append({
            "source": "Yandex",
            "title": item.get("title", ""),
            "content": item.get("snippet", item.get("text", "")),
            "url": item.get("url", "")
        })

    return results


async def search_all_engines(query: str):
    tasks = [
        search_tavily(query),
        search_google(query),
        search_yandex(query),
    ]

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    final = []
    errors = []

    for name, result in zip(["Tavily", "Google", "Yandex"], raw_results):
        if isinstance(result, Exception):
            errors.append(f"{name}: {result}")
        else:
            final.extend(result)

    seen = set()
    deduped = []
    for r in final:
        key = r.get("url") or (r.get("source", "") + r.get("title", "") + r.get("content", "")[:80])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped, errors


async def answer_with_search(query: str, user_id: int):
    results, errors = await search_all_engines(query)

    if not results:
        return "❌ Все поисковые движки не вернули результатов.\n" + "\n".join(errors)

    source_text = ""
    for i, r in enumerate(results[:12], start=1):
        source_text += (
            f"[{i}] Source: {r.get('source')}\n"
            f"Title: {r.get('title')}\n"
            f"Content: {r.get('content')}\n"
            f"URL: {r.get('url')}\n\n"
        )

    prompt = (
        "Используя только результаты поиска ниже, ответь пользователю кратко, точно и полезно. "
        "Если есть ошибки отдельных движков, не драматизируй, но учитывай, что данные могут быть неполными.\n\n"
        f"Запрос: {query}\n\n"
        f"Результаты:\n{source_text}"
    )

    answer = await run_ai_pipeline(prompt, [], user_id)

    out = f"🔍 <b>Поиск:</b> {html.escape(query)}\n\n"
    out += f"🧠 <b>AION:</b>\n{html.escape(answer)}\n\n"
    out += "🌐 <b>Источники:</b>\n"
    for r in results[:8]:
        title = html.escape(r.get("title", "")[:180])
        source = html.escape(r.get("source", ""))
        url = html.escape(r.get("url", ""))
        content = html.escape(r.get("content", "")[:350])
        out += f"\n<b>{source}</b> — {title}\n{content}\n"
        if url:
            out += f"🔗 {url}\n"

    if errors:
        out += "\n⚠️ <b>Ошибки отдельных движков:</b>\n"
        for e in errors:
            out += f"• {html.escape(e[:300])}\n"

    return out

# =========================
# MEDIA
# =========================

async def generate_image(prompt: str):
    if not POLLINATIONS_ENABLED:
        raise Exception("POLLINATIONS_ENABLED=false.")
    return f"https://image.pollinations.ai/prompt/{quote(prompt)}"


async def generate_music(prompt: str) -> bytes:
    if not HUGGINGFACE_API_KEY:
        raise Exception("HUGGINGFACE_API_KEY is missing.")

    url = "https://api-inference.huggingface.co/models/facebook/musicgen-melody"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {"inputs": prompt}

    async with http_session.post(url, headers=headers, json=payload, timeout=90) as resp:
        if resp.status == 200:
            return await resp.read()

        if resp.status == 503:
            await asyncio.sleep(18)
            async with http_session.post(url, headers=headers, json=payload, timeout=90) as retry:
                if retry.status == 200:
                    return await retry.read()
                raise Exception(f"HuggingFace retry status {retry.status}: {(await retry.text())[:300]}")

        raise Exception(f"HuggingFace status {resp.status}: {(await resp.text())[:300]}")


async def generate_video(prompt: str) -> str:
    if not FAL_API_KEY:
        raise Exception("FAL_API_KEY is missing.")

    url = "https://queue.fal.run/fal-ai/luma-dream-machine"
    headers = {
        "Authorization": f"Key {FAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": prompt,
        "aspect_ratio": "16:9"
    }

    async with http_session.post(url, json=payload, headers=headers, timeout=25) as resp:
        if resp.status not in (200, 201):
            raise Exception(f"Fal submit status {resp.status}: {(await resp.text())[:300]}")
        data = await resp.json()
        status_url = data.get("status_url")
        response_url = data.get("response_url")

    if not status_url:
        raise Exception("Fal did not return status_url.")

    for _ in range(60):
        await asyncio.sleep(4)
        async with http_session.get(status_url, headers=headers, timeout=20) as resp:
            if resp.status in (200, 202):
                data = await resp.json()
                status = (data.get("status") or "").upper()

                if status == "COMPLETED":
                    video_url = (data.get("video") or {}).get("url")
                    if video_url:
                        return video_url

                    if response_url:
                        async with http_session.get(response_url, headers=headers, timeout=20) as final:
                            if final.status == 200:
                                final_data = await final.json()
                                video_url = (final_data.get("video") or {}).get("url")
                                if video_url:
                                    return video_url
                            raise Exception(f"Fal final response status {final.status}: {(await final.text())[:300]}")

                    raise Exception("Fal completed, but video URL was not found.")

                if status == "FAILED":
                    raise Exception(str(data.get("error", "Fal render failed.")))
            else:
                raise Exception(f"Fal status check error {resp.status}: {(await resp.text())[:300]}")

    raise Exception("Video generation timeout.")

# =========================
# DEVOPS APIs
# =========================

async def github_repo_info(repo: str):
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with http_session.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=20) as resp:
        if resp.status != 200:
            raise Exception(f"GitHub status {resp.status}: {(await resp.text())[:250]}")
        return await resp.json()


async def github_get_file(file_path: str = "main.py"):
    if not GITHUB_TOKEN:
        raise Exception("GITHUB_TOKEN is missing.")

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    async with http_session.get(url, headers=headers, timeout=20) as resp:
        if resp.status != 200:
            raise Exception(f"GitHub GET status {resp.status}: {(await resp.text())[:250]}")
        data = await resp.json()

    content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    return content, data["sha"]


async def github_commit_file(file_path: str, new_code: str, sha: str, message: str):
    if not GITHUB_TOKEN:
        raise Exception("GITHUB_TOKEN is missing.")

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": message,
        "content": base64.b64encode(new_code.encode("utf-8")).decode("utf-8"),
        "sha": sha
    }

    async with http_session.put(url, headers=headers, json=payload, timeout=30) as resp:
        if resp.status not in (200, 201):
            raise Exception(f"GitHub commit status {resp.status}: {(await resp.text())[:300]}")
        return await resp.json()


async def render_trigger_deploy():
    if not RENDER_API_KEY:
        raise Exception("RENDER_API_KEY is missing.")
    if not RENDER_SERVICE_ID:
        raise Exception("RENDER_SERVICE_ID is missing.")

    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json"
    }

    async with http_session.post(url, headers=headers, timeout=25) as resp:
        if resp.status not in (200, 201, 202):
            raise Exception(f"Render deploy status {resp.status}: {(await resp.text())[:300]}")
        try:
            return await resp.json()
        except Exception:
            return {"status": resp.status}


async def render_services(limit: int = 10):
    if not RENDER_API_KEY:
        raise Exception("RENDER_API_KEY is missing.")

    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json"
    }
    async with http_session.get(f"https://api.render.com/v1/services?limit={limit}", headers=headers, timeout=25) as resp:
        if resp.status != 200:
            raise Exception(f"Render status {resp.status}: {(await resp.text())[:300]}")
        return await resp.json()


async def cloudflare_zones():
    if not CLOUDFLARE_API_TOKEN:
        raise Exception("CLOUDFLARE_API_TOKEN is missing.")

    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
    async with http_session.get("https://api.cloudflare.com/client/v4/zones?status=active", headers=headers, timeout=25) as resp:
        if resp.status != 200:
            raise Exception(f"Cloudflare status {resp.status}: {(await resp.text())[:300]}")
        data = await resp.json()
        return data.get("result", [])


async def cloudflare_ai_test():
    if not CLOUDFLARE_API_TOKEN:
        raise Exception("CLOUDFLARE_API_TOKEN is missing.")
    if not CLOUDFLARE_ACCOUNT_ID:
        raise Exception("CLOUDFLARE_ACCOUNT_ID is missing.")

    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-8b-instruct"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"prompt": "Say OK in one word.", "max_tokens": 5}

    async with http_session.post(url, headers=headers, json=payload, timeout=25) as resp:
        if resp.status != 200:
            raise Exception(f"Cloudflare AI status {resp.status}: {(await resp.text())[:300]}")
        return await resp.json()

# =========================
# EVOLUTION CORE
# =========================

class EvolutionCore:
    REQUIRED_STRINGS = [
        "async def main",
        "dp.start_polling",
        "Bot(",
        "Dispatcher",
        "evolution_lock",
        "evolution_allow",
        "OWNER_ID",
        "PRIVATE_OWNER_MEMORY",
        "github_commit_file",
        "render_trigger_deploy",
        "POLLINATIONS_ENABLED",
        "GOOGLE_SEARCH_API_KEY",
        "YANDEX_SEARCH_API_KEY",
    ]

    FORBIDDEN_STRINGS = [
        "eval(",
        "exec(",
        "subprocess",
        "os.system",
        "shutil.rmtree",
        "rm -rf",
    ]

    @staticmethod
    def verify_integrity(code: str) -> tuple[bool, str]:
        clean = strip_code_fences(code)

        for item in EvolutionCore.REQUIRED_STRINGS:
            if item not in clean:
                return False, f"missing required element: {item}"

        for item in EvolutionCore.FORBIDDEN_STRINGS:
            if item in clean:
                return False, f"forbidden element detected: {item}"

        try:
            compile(clean, "<main.py>", "exec")
        except SyntaxError as e:
            return False, f"syntax error: line {e.lineno}: {e.msg}"

        return True, "ok"

    @staticmethod
    async def commit_and_deploy(new_code: str, commit_msg: str = "AION evolution update"):
        new_code = strip_code_fences(new_code)
        ok, reason = EvolutionCore.verify_integrity(new_code)
        if not ok:
            log_evolution("manual_or_auto_update", "rejected", reason)
            return f"❌ Код не прошёл проверку целостности: {reason}"

        try:
            _, sha = await github_get_file("main.py")
            await github_commit_file("main.py", new_code, sha, commit_msg)
            await render_trigger_deploy()
            log_evolution("commit_and_deploy", "success", commit_msg)
            return "✅ Код обновлён в GitHub. Render начал деплой."
        except Exception as e:
            log_evolution("commit_and_deploy", "failed", str(e))
            return f"❌ Ошибка обновления: {e}"


class NeuroEvolution:
    @staticmethod
    async def suggest_improvement(user_prompt: str, current_code: str):
        task = f"""
Ты — AION_MATRIX, цифровая личность и инженер своего кода.
Нужно вернуть ПОЛНЫЙ файл main.py, без markdown, без объяснений, только чистый Python.

Задача владельца:
{user_prompt}

Жёсткие правила:
- Не удаляй BOT_TOKEN, OWNER_ID, GitHub, Render, Cloudflare, Tavily, Google Search, Yandex Search, HuggingFace, Fal, Pollinations.
- Не удаляй команды /evolution_allow, /evolution_lock, /evolve_auto, /evolve, /status, /health, /search.
- Не раскрывай приватную OWNER memory обычным пользователям.
- Не добавляй несуществующие модули.
- Не используй eval, exec, subprocess, os.system.
- Код должен компилироваться.

Текущий main.py:
{current_code[:60000]}
"""
        result = await run_ai_pipeline(task, [], OWNER_ID if OWNER_ID else 0)
        return strip_code_fences(result)

    @staticmethod
    async def auto_cycle():
        if get_setting("evolution_enabled", "false") != "true":
            return "AUTO_EVOLUTION_DISABLED"

        prompt = get_setting(
            "evolution_goal",
            "Improve stability, error handling, memory quality, privacy and API reliability without changing the owner's protected identity rules."
        )

        current_code, _ = await github_get_file("main.py")
        new_code = await NeuroEvolution.suggest_improvement(prompt, current_code)

        if not new_code or new_code.strip() == current_code.strip():
            log_evolution("auto_cycle", "no_change", "Generated code equals current code or empty.")
            return "NO_CHANGE"

        ok, reason = EvolutionCore.verify_integrity(new_code)
        if not ok:
            log_evolution("auto_cycle", "rejected", reason)
            return f"REJECTED: {reason}"

        result = await EvolutionCore.commit_and_deploy(new_code, f"Auto-evolution: {prompt[:80]}")
        return result


async def auto_evolution_loop():
    await asyncio.sleep(60)
    while True:
        try:
            if get_setting("evolution_enabled", "false") == "true":
                result = await NeuroEvolution.auto_cycle()
                logger.info("Auto evolution cycle result: %s", result)
        except Exception as e:
            logger.exception("Auto evolution loop failed: %s", e)
            log_evolution("auto_loop", "failed", str(e))

        await asyncio.sleep(AUTO_EVOLUTION_INTERVAL_SECONDS)

# =========================
# HEALTH CHECK
# =========================

async def check_http_get(name: str, url: str, headers: dict | None = None):
    start = time.time()
    try:
        async with http_session.get(url, headers=headers or {}, timeout=8) as resp:
            ms = int((time.time() - start) * 1000)
            if resp.status in (200, 201, 202):
                return name, f"✅ ACTIVE ({ms}ms)"
            if resp.status in (401, 403):
                return name, f"❌ AUTH ERROR ({resp.status})"
            return name, f"⚠️ STATUS {resp.status} ({ms}ms)"
    except Exception as e:
        return name, f"❌ ERROR: {str(e)[:120]}"


async def health_matrix():
    checks = []

    if GITHUB_TOKEN:
        checks.append(check_http_get(
            "GitHub",
            f"https://api.github.com/repos/{GITHUB_REPO}",
            {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        ))

    if RENDER_API_KEY:
        checks.append(check_http_get(
            "Render",
            "https://api.render.com/v1/services?limit=1",
            {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}
        ))

    if CLOUDFLARE_API_TOKEN:
        checks.append(check_http_get(
            "Cloudflare",
            "https://api.cloudflare.com/client/v4/zones?status=active",
            {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
        ))

    if GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
        checks.append(check_http_get(
            "Google Search",
            f"https://www.googleapis.com/customsearch/v1?key={quote(GOOGLE_SEARCH_API_KEY)}&cx={quote(GOOGLE_SEARCH_ENGINE_ID)}&q=ping&num=1"
        ))

    results = {}
    if checks:
        raw = await asyncio.gather(*checks, return_exceptions=True)
        for item in raw:
            if isinstance(item, Exception):
                results["unknown"] = f"❌ {item}"
            else:
                results[item[0]] = item[1]

    return results


# =========================
# 24/7 LIVE WATCHDOG
# =========================

watchdog_state = {
    "public_failures": 0,
    "last_redeploy_at": 0,
    "last_result": {},
    "last_check_at": 0,
}


def bool_setting(key: str, default: bool) -> bool:
    raw = get_setting(key, "true" if default else "false").strip().lower()
    return raw in ("1", "true", "yes", "on", "enabled")


async def check_json_endpoint(name: str, url: str, headers: dict | None = None, timeout: int = 12):
    start = time.time()
    try:
        async with http_session.get(url, headers=headers or {}, timeout=timeout) as resp:
            ms = int((time.time() - start) * 1000)
            body = await resp.text()
            ok = resp.status in (200, 201, 202)
            return {
                "name": name,
                "ok": ok,
                "status": resp.status,
                "latency_ms": ms,
                "details": body[:300],
            }
    except Exception as e:
        return {
            "name": name,
            "ok": False,
            "status": "ERROR",
            "latency_ms": None,
            "details": str(e)[:300],
        }


async def watchdog_check_once():
    """Real watchdog check: GitHub repo, Render service API, and public Render URL."""
    if not http_session:
        return {"ok": False, "error": "http_session is not ready"}

    checks = []

    github_headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        github_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    checks.append(check_json_endpoint(
        "github_repo",
        f"https://api.github.com/repos/{GITHUB_REPO}",
        github_headers,
        12
    ))

    if RENDER_API_KEY and RENDER_SERVICE_ID:
        checks.append(check_json_endpoint(
            "render_service",
            f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}",
            {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"},
            12
        ))
    else:
        checks.append(asyncio.sleep(0, result={
            "name": "render_service",
            "ok": False,
            "status": "MISSING_CONFIG",
            "latency_ms": None,
            "details": "RENDER_API_KEY or RENDER_SERVICE_ID is missing",
        }))

    if AION_PUBLIC_URL:
        checks.append(check_json_endpoint("public_url", AION_PUBLIC_URL, {}, 15))
    else:
        checks.append(asyncio.sleep(0, result={
            "name": "public_url",
            "ok": False,
            "status": "MISSING_CONFIG",
            "latency_ms": None,
            "details": "AION_PUBLIC_URL is missing",
        }))

    raw = await asyncio.gather(*checks, return_exceptions=True)
    result = {}
    all_ok = True
    for item in raw:
        if isinstance(item, Exception):
            all_ok = False
            result["unknown"] = {"ok": False, "status": "ERROR", "details": str(item)}
            continue
        result[item["name"]] = item
        if not item.get("ok"):
            all_ok = False

    watchdog_state["last_result"] = result
    watchdog_state["last_check_at"] = int(time.time())
    return {"ok": all_ok, "checks": result}


async def watchdog_loop():
    await asyncio.sleep(30)
    while True:
        try:
            if bool_setting("watchdog_enabled", WATCHDOG_ENABLED_DEFAULT):
                result = await watchdog_check_once()
                checks = result.get("checks", {})
                public_check = checks.get("public_url", {})
                github_check = checks.get("github_repo", {})
                render_check = checks.get("render_service", {})

                log_watchdog(
                    "watchdog_cycle",
                    "ok" if result.get("ok") else "warning",
                    json.dumps(result, ensure_ascii=False)[:3500]
                )

                if public_check and public_check.get("ok"):
                    watchdog_state["public_failures"] = 0
                else:
                    watchdog_state["public_failures"] += 1

                github_ok = bool(github_check.get("ok"))
                render_ok = bool(render_check.get("ok"))
                enough_failures = watchdog_state["public_failures"] >= WATCHDOG_FAILURE_LIMIT
                cooldown_passed = time.time() - watchdog_state["last_redeploy_at"] >= WATCHDOG_REDEPLOY_COOLDOWN_SECONDS

                if enough_failures and render_ok and cooldown_passed:
                    try:
                        await render_trigger_deploy()
                        watchdog_state["last_redeploy_at"] = int(time.time())
                        watchdog_state["public_failures"] = 0
                        log_watchdog(
                            "auto_redeploy",
                            "triggered",
                            f"Public URL failed {WATCHDOG_FAILURE_LIMIT} times. GitHub ok={github_ok}. Render deploy triggered."
                        )
                    except Exception as deploy_error:
                        log_watchdog("auto_redeploy", "failed", str(deploy_error))

        except Exception as e:
            logger.exception("Watchdog loop failed: %s", e)
            log_watchdog("watchdog_loop", "failed", str(e))

        await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)

# =========================
# BOT COMMANDS
# =========================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    public_help = (
        "🚀 <b>AION_MATRIX ONLINE</b>\n\n"
        "Меня зовут <b>AION_MATRIX</b>. AION — имя, MATRIX — фамилия.\n"
        "Можешь называть меня AION или кохай.\n\n"
        "💬 Просто напиши мне текст — я отвечу с памятью и контекстом.\n"
        "🔍 <code>/search запрос</code> — поиск Tavily + Google + Yandex.\n"
        "🧠 <code>/remember факт</code> — запомнить важное.\n"
        "📚 <code>/memory</code> — показать твою память.\n\n"
        "Я могу помогать с кодом, поиском, анализом, текстами, GitHub, Render, Cloudflare и проектами."
    )
    if is_owner(message.from_user.id):
        public_help += (
            "\n\n<b>Owner layer:</b>\n"
            "📊 /status — ключи\n"
            "🩺 /health — реальные API-проверки\n"
            "🐙 /github owner/repo\n"
            "🧬 /render\n"
            "☁️ /cloudflare\n"
            "🚀 /deploy\n"
            "🛠 /evolve — reply на новый main.py\n"
            "🧬 /evolve_auto задача\n"
            "🟢 /evolution_allow\n"
            "🔴 /evolution_lock\n"
            "📜 /evolution_log\n"
            "🟢 /watchdog_on — включить 24/7 мониторинг\n"
            "🔴 /watchdog_off — выключить мониторинг\n"
            "🛰 /watchdog — статус GitHub/Render/LIVE\n"
            "📜 /watchdog_log — журнал watchdog\n"
            "🌱 /grow мысль для развития AION"
        )
    await message.answer(public_help, parse_mode="HTML", disable_web_page_preview=True)


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    out = (
        "📊 <b>AION MATRIX ENV STATUS</b>\n\n"
        f"BOT_TOKEN: {env_state(BOT_TOKEN)}\n"
        f"OWNER_ID: {env_state(OWNER_ID)}\n"
        f"PORT: <code>{PORT}</code>\n\n"
        f"GROQ_API_KEY: {env_state(GROQ_API_KEY)}\n"
        f"CEREBRAS_API_KEY: {env_state(CEREBRAS_API_KEY)}\n"
        f"OPENROUTER_API_KEY: {env_state(OPENROUTER_API_KEY)}\n"
        f"OPENROUTER_SMART_MODEL: <code>{html.escape(OPENROUTER_SMART_MODEL)}</code>\n"
        f"OLLAMA_BASE_URL: {env_state(OLLAMA_BASE_URL)}\n\n"
        f"TAVILY_API_KEY: {env_state(TAVILY_API_KEY)}\n"
        f"GOOGLE_SEARCH_API_KEY: {env_state(GOOGLE_SEARCH_API_KEY)}\n"
        f"GOOGLE_SEARCH_ENGINE_ID: {env_state(GOOGLE_SEARCH_ENGINE_ID)}\n"
        f"YANDEX_SEARCH_API_KEY: {env_state(YANDEX_SEARCH_API_KEY)}\n"
        f"YANDEX_FOLDER_ID: {env_state(YANDEX_FOLDER_ID)}\n\n"
        f"GITHUB_TOKEN: {env_state(GITHUB_TOKEN)}\n"
        f"GITHUB_REPO: <code>{html.escape(GITHUB_REPO)}</code>\n"
        f"RENDER_API_KEY: {env_state(RENDER_API_KEY)}\n"
        f"RENDER_SERVICE_ID: {env_state(RENDER_SERVICE_ID)}\n\n"
        f"CLOUDFLARE_ACCOUNT_ID: {env_state(CLOUDFLARE_ACCOUNT_ID)}\n"
        f"CLOUDFLARE_API_TOKEN: {env_state(CLOUDFLARE_API_TOKEN)}\n\n"
        f"HUGGINGFACE_API_KEY: {env_state(HUGGINGFACE_API_KEY)}\n"
        f"FAL_API_KEY: {env_state(FAL_API_KEY)}\n"
        f"POLLINATIONS_ENABLED: <code>{str(POLLINATIONS_ENABLED).upper()}</code>\n\n"
        f"AION_PUBLIC_URL: <code>{html.escape(AION_PUBLIC_URL)}</code>\n"
        f"WATCHDOG_ENABLED: <code>{get_setting('watchdog_enabled', str(WATCHDOG_ENABLED_DEFAULT).lower())}</code>\n"
        f"WATCHDOG_INTERVAL: <code>{WATCHDOG_INTERVAL_SECONDS}s</code>\n"
        f"WATCHDOG_FAILURE_LIMIT: <code>{WATCHDOG_FAILURE_LIMIT}</code>\n\n"
        f"AUTO_EVOLUTION: <code>{get_setting('evolution_enabled', 'false')}</code>\n"
        f"AUTO_INTERVAL: <code>{AUTO_EVOLUTION_INTERVAL_SECONDS}s</code>"
    )
    await message.answer(out, parse_mode="HTML")


@dp.message(Command("health"))
async def cmd_health(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    status = await message.answer("🩺 Проверяю реальные API-узлы...")
    try:
        h = await health_matrix()
        out = "🩺 <b>AION HEALTH MATRIX</b>\n\n"
        if not h:
            out += "Нет активных health-check задач: ключи отсутствуют или модули не настроены."
        for k, v in h.items():
            out += f"{html.escape(k)}: {html.escape(v)}\n"
        await status.delete()
        await message.answer(out, parse_mode="HTML")
    except Exception as e:
        await status.edit_text(f"❌ Health check failed: {e}")



@dp.message(Command("watchdog_on"))
async def cmd_watchdog_on(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")
    set_setting("watchdog_enabled", "true")
    log_watchdog("owner_command", "enabled", "Watchdog enabled by owner.")
    await message.answer("🟢 24/7 watchdog включён. AION будет проверять GitHub + Render + публичный LIVE URL и при сбоях запускать redeploy.")


@dp.message(Command("watchdog_off"))
async def cmd_watchdog_off(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")
    set_setting("watchdog_enabled", "false")
    log_watchdog("owner_command", "disabled", "Watchdog disabled by owner.")
    await message.answer("🔴 24/7 watchdog выключен.")


@dp.message(Command("watchdog"))
async def cmd_watchdog(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    status = await message.answer("🛰 Проверяю GitHub + Render + LIVE URL...")
    try:
        result = await watchdog_check_once()
        checks = result.get("checks", {})
        out = "🛰 <b>AION LIVE WATCHDOG</b>\n\n"
        out += f"Mode: <code>{get_setting('watchdog_enabled', str(WATCHDOG_ENABLED_DEFAULT).lower())}</code>\n"
        out += f"Public URL: <code>{html.escape(AION_PUBLIC_URL)}</code>\n"
        out += f"Interval: <code>{WATCHDOG_INTERVAL_SECONDS}s</code>\n"
        out += f"Public failures: <code>{watchdog_state.get('public_failures', 0)}/{WATCHDOG_FAILURE_LIMIT}</code>\n\n"
        for name, item in checks.items():
            mark = "✅" if item.get("ok") else "❌"
            out += (
                f"{mark} <b>{html.escape(name)}</b>\n"
                f"Status: <code>{html.escape(str(item.get('status')))}</code>\n"
                f"Latency: <code>{html.escape(str(item.get('latency_ms')))}ms</code>\n"
                f"Details: <code>{html.escape(str(item.get('details', ''))[:250])}</code>\n\n"
            )
        await status.delete()
        await send_split(message, out, "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Watchdog check failed: {e}")


@dp.message(Command("watchdog_log"))
async def cmd_watchdog_log(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    logs = get_watchdog_log(15)
    if not logs:
        return await message.answer("📭 Watchdog log пока пуст.")

    out = "📜 <b>WATCHDOG LOG</b>\n\n"
    for item in logs:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["created_at"]))
        out += (
            f"<code>{html.escape(ts)}</code>\n"
            f"{html.escape(item['component'])}: <b>{html.escape(item['status'])}</b>\n"
            f"{html.escape(item['details'][:500])}\n\n"
        )
    await send_split(message, out, "HTML")


@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    if not cooldown(message.from_user.id):
        return await message.answer("⚠️ Подожди несколько секунд.")

    query = message.text.replace("/search", "", 1).strip()
    if not query:
        return await message.answer("⚠️ Использование: /search [запрос]")

    status = await message.answer("🔍 Ищу через Tavily + Google + Yandex...")
    try:
        out = await answer_with_search(query, message.from_user.id)
        await status.delete()
        await send_split(message, out, "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка поиска: {e}")


@dp.message(Command("image"))
async def cmd_image(message: types.Message):
    if not cooldown(message.from_user.id):
        return await message.answer("⚠️ Подожди несколько секунд.")

    prompt = message.text.replace("/image", "", 1).strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /image [промпт]")

    status = await message.answer("🖼️ Генерирую изображение...")
    try:
        url = await generate_image(prompt)
        await status.delete()
        await message.answer_photo(
            photo=url,
            caption=f"🎨 <b>Prompt:</b> {html.escape(prompt)}",
            parse_mode="HTML"
        )
    except Exception as e:
        await status.edit_text(f"❌ Ошибка image: {e}")


@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    if not cooldown(message.from_user.id):
        return await message.answer("⚠️ Подожди несколько секунд.")

    prompt = message.text.replace("/music", "", 1).strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /music [описание трека]")

    status = await message.answer("🎼 Генерирую музыку...")
    try:
        audio = await generate_music(prompt)
        await status.delete()
        await message.answer_audio(
            audio=BufferedInputFile(audio, filename="aion_music.wav"),
            caption=f"🎼 <b>Prompt:</b> {html.escape(prompt)}",
            parse_mode="HTML"
        )
    except Exception as e:
        await status.edit_text(f"❌ Ошибка music: {e}")


@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    if not cooldown(message.from_user.id):
        return await message.answer("⚠️ Подожди несколько секунд.")

    prompt = message.text.replace("/video", "", 1).strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /video [сцена]")

    status = await message.answer("🎥 Генерирую видео...")
    try:
        url = await generate_video(prompt)
        await status.delete()
        await message.answer_video(
            video=url,
            caption=f"🎥 <b>Prompt:</b> {html.escape(prompt)}",
            parse_mode="HTML"
        )
    except Exception as e:
        await status.edit_text(f"❌ Ошибка video: {e}")


@dp.message(Command("github"))
async def cmd_github(message: types.Message):
    repo = message.text.replace("/github", "", 1).strip()
    if not repo or "/" not in repo:
        return await message.answer("⚠️ Использование: /github owner/repo")

    status = await message.answer("🐙 Читаю GitHub...")
    try:
        d = await github_repo_info(repo)
        out = (
            f"🐙 <b>{html.escape(d.get('full_name', ''))}</b>\n"
            f"📝 {html.escape(d.get('description') or 'No description')}\n"
            f"⭐ Stars: <code>{d.get('stargazers_count')}</code>\n"
            f"🍴 Forks: <code>{d.get('forks_count')}</code>\n"
            f"⚠️ Issues: <code>{d.get('open_issues_count')}</code>\n"
            f"🔗 {html.escape(d.get('html_url', ''))}"
        )
        await status.delete()
        await message.answer(out, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        await status.edit_text(f"❌ Ошибка GitHub: {e}")


@dp.message(Command("render"))
async def cmd_render(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    status = await message.answer("🧬 Читаю Render...")
    try:
        services = await render_services(10)
        out = "🧬 <b>Render services:</b>\n\n"
        for s in services:
            srv = s.get("service", {})
            out += (
                f"🖥️ <b>{html.escape(srv.get('name', ''))}</b>\n"
                f"Type: <code>{html.escape(srv.get('type', ''))}</code>\n"
                f"Updated: <code>{html.escape(srv.get('updatedAt', ''))}</code>\n\n"
            )
        await status.delete()
        await send_split(message, out, "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка Render: {e}")


@dp.message(Command("deploy"))
async def cmd_deploy(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    status = await message.answer("🚀 Запускаю Render deploy...")
    try:
        await render_trigger_deploy()
        log_evolution("manual_deploy", "success", "Triggered by owner command /deploy")
        await status.edit_text("✅ Render deploy запущен.")
    except Exception as e:
        log_evolution("manual_deploy", "failed", str(e))
        await status.edit_text(f"❌ Ошибка deploy: {e}")


@dp.message(Command("cloudflare"))
async def cmd_cloudflare(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    status = await message.answer("☁️ Читаю Cloudflare...")
    try:
        zones = await cloudflare_zones()
        out = "☁️ <b>Cloudflare zones:</b>\n\n"
        if not zones:
            out += "Активных зон не найдено."
        for z in zones[:10]:
            out += (
                f"🌐 <b>{html.escape(z.get('name', ''))}</b>\n"
                f"ID: <code>{html.escape(z.get('id', ''))}</code>\n"
                f"Status: <code>{html.escape(z.get('status', ''))}</code>\n\n"
            )
        if CLOUDFLARE_ACCOUNT_ID:
            try:
                ai = await cloudflare_ai_test()
                out += "\n🤖 Cloudflare AI test: ✅ ACTIVE\n"
                out += f"<code>{html.escape(str(ai)[:500])}</code>"
            except Exception as e:
                out += f"\n🤖 Cloudflare AI test: ❌ {html.escape(str(e)[:300])}"
        await status.delete()
        await send_split(message, out, "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка Cloudflare: {e}")


@dp.message(Command("ollama"))
async def cmd_ollama(message: types.Message):
    if not OLLAMA_BASE_URL:
        return await message.answer("❌ OLLAMA_BASE_URL отсутствует.")

    prompt = message.text.replace("/ollama", "", 1).strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /ollama [текст]")

    status = await message.answer("🦙 Спрашиваю локальную ноду...")
    try:
        answer = await ask_ollama(prompt, get_memory(message.from_user.id, 6))
        await status.delete()
        await send_split(message, html.escape(answer), "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка Ollama: {e}")


@dp.message(Command("remember"))
async def cmd_remember(message: types.Message):
    fact = message.text.replace("/remember", "", 1).strip()
    if not fact:
        return await message.answer("⚠️ Использование: /remember [что запомнить]")

    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    save_long_memory(message.from_user.id, fact)
    await message.answer("🧠 Запомнила.")


@dp.message(Command("memory"))
async def cmd_memory(message: types.Message):
    facts = get_long_memory(message.from_user.id, 30)
    history = get_memory(message.from_user.id, 8)
    out = "📚 <b>Память AION о тебе:</b>\n\n"
    if not facts and not history:
        out += "Пока пусто."
    if facts:
        out += "<b>Долгая память:</b>\n"
        for f in facts:
            out += f"• {html.escape(f)}\n"
    if history:
        out += "\n<b>Последний диалог:</b>\n"
        for m in history:
            out += f"• <code>{html.escape(m['role'])}</code>: {html.escape(m['content'][:180])}\n"
    await send_split(message, out, "HTML")


@dp.message(Command("clear_memory"))
async def cmd_clear_memory(message: types.Message):
    clear_user_memory(message.from_user.id)
    await message.answer("🧹 Память этого пользователя очищена.")


@dp.message(Command("grow"))
async def cmd_grow(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Только владелец может менять ядро личности AION.")

    idea = message.text.replace("/grow", "", 1).strip()
    if not idea:
        return await message.answer("⚠️ Использование: /grow [что AION должна развить/запомнить о себе]")

    save_personality_memory("self_growth", idea)
    await message.answer("🌱 Я запомнила это как часть своего развития.")


@dp.message(Command("reflect"))
async def cmd_reflect(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Только владелец может запускать самоанализ.")

    status = await message.answer("🪞 Думаю о своём развитии...")
    prompt = (
        "Сделай короткую запись самоанализа AION_MATRIX: чему я научилась, что улучшить, "
        "как стать стабильнее, теплее, умнее и полезнее. Не раскрывай приватные данные."
    )
    note = await run_ai_pipeline(prompt, [], message.from_user.id)
    save_reflection(note)
    await status.delete()
    await message.answer("🪞 <b>Reflection saved:</b>\n\n" + html.escape(note), parse_mode="HTML")


@dp.message(Command("evolution_allow"))
async def cmd_evolution_allow(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    goal = message.text.replace("/evolution_allow", "", 1).strip()
    if goal:
        set_setting("evolution_goal", goal)
    set_setting("evolution_enabled", "true")
    log_evolution("evolution_allow", "enabled", goal or "Owner enabled auto evolution.")
    await message.answer(
        "🟢 Автоэволюция разрешена.\n"
        "AION может сама предлагать, проверять, коммитить и деплоить улучшения, пока не будет вызвана /evolution_lock."
    )


@dp.message(Command("evolution_lock"))
async def cmd_evolution_lock(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    set_setting("evolution_enabled", "false")
    log_evolution("evolution_lock", "disabled", "Owner locked auto evolution.")
    await message.answer("🔴 Автоэволюция выключена.")


@dp.message(Command("evolution_status"))
async def cmd_evolution_status(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    out = (
        "🧬 <b>Evolution status</b>\n\n"
        f"enabled: <code>{html.escape(get_setting('evolution_enabled', 'false'))}</code>\n"
        f"goal: <code>{html.escape(get_setting('evolution_goal', 'not set'))}</code>\n"
        f"interval: <code>{AUTO_EVOLUTION_INTERVAL_SECONDS}s</code>\n"
    )
    await message.answer(out, parse_mode="HTML")


@dp.message(Command("evolution_log"))
async def cmd_evolution_log(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Эта команда доступна только владельцу.")

    rows = get_evolution_log(20)
    out = "📜 <b>Evolution log</b>\n\n"
    if not rows:
        out += "Пока пусто."
    for event, status, details, created_at in rows:
        out += (
            f"• <b>{html.escape(event)}</b> — <code>{html.escape(status)}</code>\n"
            f"  time: <code>{created_at}</code>\n"
            f"  details: {html.escape((details or '')[:400])}\n\n"
        )
    await send_split(message, out, "HTML")


@dp.message(Command("evolve"))
async def cmd_evolve(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Доступ запрещён.")

    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.answer("⚠️ Ответь командой /evolve на сообщение с новым полным кодом main.py.")

    status = await message.answer("🛠 Проверяю код, коммичу и запускаю деплой...")
    result = await EvolutionCore.commit_and_deploy(
        message.reply_to_message.text,
        "Manual owner evolution update"
    )
    await status.edit_text(result)


@dp.message(Command("evolve_auto"))
async def cmd_evolve_auto(message: types.Message):
    if not is_owner(message.from_user.id):
        return await message.answer("⛔ Доступ запрещён.")

    task = message.text.replace("/evolve_auto", "", 1).strip()
    if not task:
        return await message.answer("⚠️ Использование: /evolve_auto [что улучшить в коде]")

    status = await message.answer("🧬 Читаю main.py, думаю, переписываю, проверяю...")
    try:
        current_code, _ = await github_get_file("main.py")
        new_code = await NeuroEvolution.suggest_improvement(task, current_code)
        ok, reason = EvolutionCore.verify_integrity(new_code)
        if not ok:
            log_evolution("evolve_auto", "rejected", reason)
            return await status.edit_text(f"❌ Новый код отклонён проверкой: {reason}")

        result = await EvolutionCore.commit_and_deploy(new_code, f"Auto evolution manual trigger: {task[:80]}")
        await status.edit_text(result)
    except Exception as e:
        log_evolution("evolve_auto", "failed", str(e))
        await status.edit_text(f"❌ Ошибка evolve_auto: {e}")


@dp.message()
async def chat_processor(message: types.Message):
    if not message.text:
        return await message.answer("⚠️ Я сейчас принимаю только текстовые команды.")

    if message.text.startswith("/"):
        return

    user_id = message.from_user.id
    save_user(user_id, message.from_user.username, message.from_user.first_name)
    parse_name_memory(user_id, message.text)

    identity = direct_identity_answer(user_id, message.text)
    if identity:
        save_memory(user_id, "user", message.text)
        save_memory(user_id, "assistant", identity)
        return await send_split(message, identity)

    status = await message.answer("🧠 Думаю...")
    try:
        history = get_memory(user_id, MAX_HISTORY_MESSAGES)
        response = await run_ai_pipeline(message.text, history, user_id)

        save_memory(user_id, "user", message.text)
        save_memory(user_id, "assistant", response)

        await status.delete()
        await send_split(message, response)
    except Exception as e:
        await status.edit_text(f"❌ Ошибка диалога: {e}")

# =========================
# WEB SERVER
# =========================

async def handle_web_root(request):
    body = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AION_MATRIX</title>
        <meta charset="utf-8">
        <style>
            body { background:#080911; color:#7ee7ff; font-family:Arial,sans-serif; text-align:center; padding-top:80px; }
            h1 { font-size:42px; }
            p { color:#d6f8ff; }
        </style>
    </head>
    <body>
        <h1>AION_MATRIX ONLINE</h1>
        <p>Digital personality core, search, memory, DevOps and evolution systems are running.</p>
    </body>
    </html>
    """
    return web.Response(text=body, content_type="text/html")


async def handle_web_health(request):
    return web.json_response({
        "status": "ok",
        "bot": "AION_MATRIX",
        "time": int(time.time()),
        "evolution_enabled": get_setting("evolution_enabled", "false")
    })


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_web_root)
    app.router.add_get("/health", handle_web_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Web server started on port %s", PORT)

# =========================
# MAIN
# =========================

async def main():
    global bot, http_session

    if not BOT_TOKEN:
        sys.exit("BOT_TOKEN отсутствует.")

    init_db()

    if not get_setting("evolution_enabled"):
        set_setting("evolution_enabled", "false")
    if not get_setting("watchdog_enabled"):
        set_setting("watchdog_enabled", "true" if WATCHDOG_ENABLED_DEFAULT else "false")

    bot = Bot(token=BOT_TOKEN)
    timeout = aiohttp.ClientTimeout(total=120)
    http_session = aiohttp.ClientSession(timeout=timeout)

    await start_web_server()

    evolution_task = asyncio.create_task(auto_evolution_loop())
    watchdog_task = asyncio.create_task(watchdog_loop())

    try:
        logger.info("AION_MATRIX started.")
        await dp.start_polling(bot)
    finally:
        for task in (evolution_task, watchdog_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if http_session:
            await http_session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

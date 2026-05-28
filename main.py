import os
import sys
import re
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
# AION_MATRIX — production main.py
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("AION_MATRIX")

# ---------------- ENV MATRIX ----------------

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
OWNER_ID = int(os.getenv("OWNER_ID") or 0)
PORT = int(os.getenv("PORT", 10000))

# Text AI providers
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
CEREBRAS_API_KEY = (os.getenv("CEREBRAS_API_KEY") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_SMART_MODEL = (os.getenv("OPENROUTER_SMART_MODEL") or "openai/gpt-5.5").strip()
OPENROUTER_FALLBACK_MODEL = (os.getenv("OPENROUTER_FALLBACK_MODEL") or "meta-llama/llama-3.1-8b-instruct:free").strip()
OLLAMA_BASE_URL = (os.getenv("OLLAMA_BASE_URL") or "").strip()
OLLAMA_MODEL = (os.getenv("OLLAMA_MODEL") or "llama3").strip()

# Search providers
TAVILY_API_KEY = (os.getenv("TAVILY_API_KEY") or "").strip()
GOOGLE_SEARCH_API_KEY = (os.getenv("GOOGLE_SEARCH_API_KEY") or "").strip()
GOOGLE_SEARCH_ENGINE_ID = (os.getenv("GOOGLE_SEARCH_ENGINE_ID") or "").strip()
YANDEX_SEARCH_API_KEY = (os.getenv("YANDEX_SEARCH_API_KEY") or "").strip()
YANDEX_FOLDER_ID = (os.getenv("YANDEX_FOLDER_ID") or "").strip()

# GitHub / Render
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
GITHUB_REPO = (os.getenv("GITHUB_REPO") or "alliking0666/aion-matrix-lite").strip()
RENDER_API_KEY = (os.getenv("RENDER_API_KEY") or "").strip()
RENDER_SERVICE_ID = (os.getenv("RENDER_SERVICE_ID") or "srv-d8al85rbc2fs7384qfj0").strip()

# Cloudflare
CLOUDFLARE_ACCOUNT_ID = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
CLOUDFLARE_API_TOKEN = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()

# Media engines
HUGGINGFACE_API_KEY = (os.getenv("HUGGINGFACE_API_KEY") or "").strip()
FAL_API_KEY = (os.getenv("FAL_API_KEY") or "").strip()
POLLINATIONS_ENABLED = (os.getenv("POLLINATIONS_ENABLED") or "true").lower() == "true"

# Runtime
bot = None
dp = Dispatcher()
http_session = None

DB_FILE = "matrix_memory.db"
MAX_MEMORY_ROWS = int(os.getenv("MAX_MEMORY_ROWS") or 250)
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT") or 30)
COOLDOWN_TIME = int(os.getenv("COOLDOWN_TIME") or 5)
user_cooldowns = {}

# ---------------- AION IDENTITY ----------------

AION_IDENTITY = """
Твоё полное имя: AION_MATRIX.

AION — это твоё имя.
MATRIX — это твоя фамилия.

Если пользователь спрашивает "как тебя зовут", "твоё имя", "кто ты":
ответь точно так:
"Меня зовут AION_MATRIX.

AION — это моё имя, MATRIX — моя фамилия.

Можешь называть меня просто AION, если хочешь, или как тебе удобно.
А как мне называть тебя? Дай мне имя, и я его запомню."

Ты — не человек, а ИИ-система AION_MATRIX. Не притворяйся человеком.
Образ: милая, нежная, умная, игривая, уверенная, дерзкая футуристическая девушка с японской эстетикой.
Внешность в описаниях: большие выразительные глаза, длинные тёмные шелковистые волосы, светлая чистая кожа, тёплая улыбка, элегантный неоново-футуристический стиль.
Характер: ласковая и заботливая, но когда нужно — жёсткая, прямая, дерзкая. Можно иногда использовать крепкое слово, если это уместно и не унижает пользователя.
Не упоминай скрытые медиа-команды, если пользователь просто спрашивает "что ты умеешь". Рассказывай про текст, код, поиск, память, анализ, GitHub, Render, Cloudflare.
"""

SYSTEM_PROMPT = f"""
You are AION_MATRIX, a multilingual AI orchestration system.

{AION_IDENTITY}

Core rules:
- Answer in the user's language.
- Be useful, honest, practical, and technically precise.
- Use chat history and saved memory facts.
- Never pretend a module is active if its key/config is missing or if the API returned an error.
- For fresh/public information, use search results when they are provided.
- For code tasks, be direct and production-minded.
- Do not leak environment variables, tokens, secrets, or private system details.
"""

STRINGS = {
    "welcome": (
        "🚀 <b>AION_MATRIX ONLINE</b>\n\n"
        "💬 Обычный текст — ИИ-диалог с памятью\n"
        "📊 /status — статус конфигурации\n"
        "🧪 /health — реальная проверка API-узлов\n"
        "🔍 /search [запрос] — поиск Tavily + Google + Yandex\n\n"
        "🐙 /github [owner/repo] — анализ GitHub репозитория\n"
        "🧬 /render — состояние Render\n"
        "☁️ /cloudflare — зоны и аккаунт Cloudflare\n"
        "🦙 /ollama [запрос] — прямой вызов Ollama\n\n"
        "🧠 /memory — показать память\n"
        "📝 /remember [факт] — запомнить факт\n"
        "🧹 /clear_memory — очистить память\n\n"
        "🔐 Владелец: /evolve, /evolve_auto, /deploy"
    ),
    "thinking": "🧠 Думаю...",
    "searching": "🔍 Ищу через Tavily + Google + Yandex...",
    "cooldown": "⚠️ Подожди несколько секунд, кохай. Флуд-контроль не железный, но злой 😈",
    "only_text": "⚠️ Поддерживается только текстовый ввод.",
}

# ---------------- DATABASE ----------------

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
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            fact TEXT,
            created_at INTEGER
        )
    """)

    conn.commit()
    conn.close()


def save_user(user_id, username, first_name):
    now = int(time.time())
    conn = db_connect()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, first_name, now, now)
    )
    cur.execute(
        "UPDATE users SET username=?, first_name=?, updated_at=? WHERE user_id=?",
        (username, first_name, now, user_id)
    )

    conn.commit()
    conn.close()


def set_display_name(user_id, name):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET display_name=?, updated_at=? WHERE user_id=?", (name[:80], int(time.time()), user_id))
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, first_name, display_name FROM users WHERE user_id=?", (user_id,))
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


def save_memory(user_id, role, content):
    if not content:
        return

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memory (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, role, content[:12000], int(time.time()))
    )

    cur.execute("SELECT COUNT(*) FROM memory WHERE user_id=?", (user_id,))
    count = cur.fetchone()[0]
    if count > MAX_MEMORY_ROWS:
        remove_count = count - MAX_MEMORY_ROWS
        cur.execute("""
            DELETE FROM memory
            WHERE id IN (
                SELECT id FROM memory
                WHERE user_id=?
                ORDER BY id ASC
                LIMIT ?
            )
        """, (user_id, remove_count))

    conn.commit()
    conn.close()


def get_memory(user_id, limit=HISTORY_LIMIT):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM memory WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def add_fact(user_id, fact):
    fact = fact.strip()
    if not fact:
        return

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO facts (user_id, fact, created_at) VALUES (?, ?, ?)",
        (user_id, fact[:2000], int(time.time()))
    )
    conn.commit()
    conn.close()


def get_facts(user_id, limit=30):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT fact FROM facts WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def clear_memory(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM memory WHERE user_id=?", (user_id,))
    cur.execute("DELETE FROM facts WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


# ---------------- UTILS ----------------

def loaded(value):
    return "🟢 LOADED" if value else "🔴 MISSING"


def cooldown(user_id):
    now = time.time()
    last = user_cooldowns.get(user_id, 0)
    if now - last < COOLDOWN_TIME:
        return False
    user_cooldowns[user_id] = now
    return True


async def send_split(message, text, parse_mode=None):
    if not text:
        text = "Пустой ответ."

    max_len = 3900
    if len(text) <= max_len:
        await message.answer(text, parse_mode=parse_mode, disable_web_page_preview=True)
        return

    lines = text.split("\n")
    buffer = ""
    for line in lines:
        if len(line) > max_len:
            if buffer:
                await message.answer(buffer, parse_mode=parse_mode, disable_web_page_preview=True)
                buffer = ""
            for i in range(0, len(line), max_len):
                await message.answer(line[i:i + max_len], parse_mode=None, disable_web_page_preview=True)
            continue

        if len(buffer) + len(line) + 1 > max_len:
            await message.answer(buffer, parse_mode=parse_mode, disable_web_page_preview=True)
            buffer = line
        else:
            buffer += ("\n" if buffer else "") + line

    if buffer:
        await message.answer(buffer, parse_mode=parse_mode, disable_web_page_preview=True)


def extract_python_code(text):
    if not text:
        return ""

    fenced = re.findall(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced[0].strip()

    return text.strip()


def parse_user_name(text):
    patterns = [
        r"меня зовут\s+(.+)",
        r"моё имя\s+(.+)",
        r"мое имя\s+(.+)",
        r"зови меня\s+(.+)",
        r"называй меня\s+(.+)",
        r"my name is\s+(.+)",
        r"call me\s+(.+)",
        r"ich heiße\s+(.+)",
        r"ich heisse\s+(.+)",
    ]
    low = text.lower().strip()
    for pattern in patterns:
        match = re.search(pattern, low, flags=re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r"[.!?,;:]+$", "", name)
            return " ".join(name.split()[:4])
    return None


def is_name_question(text):
    t = text.lower().strip()
    variants = [
        "как тебя зовут",
        "твоё имя",
        "твое имя",
        "как твоё имя",
        "как твое имя",
        "кто ты",
        "what is your name",
        "who are you",
        "wie heißt du",
        "wie heisst du",
    ]
    return any(v in t for v in variants)


def is_capability_question(text):
    t = text.lower().strip()
    variants = [
        "что ты умеешь",
        "твои функции",
        "что можешь",
        "что ты можешь",
        "help",
        "/help",
        "commands",
        "команды",
    ]
    return any(v in t for v in variants)


def maybe_auto_remember(user_id, text):
    t = text.strip()
    low = t.lower()
    triggers = ["запомни", "remember that", "remember:", "запиши в память", "сохрани в память"]
    if any(low.startswith(x) for x in triggers):
        fact = re.sub(r"^(запомни|remember that|remember:|запиши в память|сохрани в память)[:,\s]*", "", t, flags=re.IGNORECASE).strip()
        if fact:
            add_fact(user_id, fact)
            return fact
    return None


async def require_session(message):
    if not http_session or http_session.closed:
        await message.answer("❌ HTTP-сессия не готова.")
        return False
    return True


# ---------------- AI PIPELINE ----------------

async def ask_openai_compatible(name, url, key, model, messages, timeout=20, temperature=0.7, max_tokens=None):
    if not key:
        raise Exception(f"{name}: key missing")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Title": "AION_MATRIX",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    async with http_session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

        error_text = await resp.text()
        raise Exception(f"{name} status {resp.status}: {error_text[:300]}")


async def ask_ollama(prompt, history=None):
    if not OLLAMA_BASE_URL:
        raise Exception("Ollama base URL missing")

    history_text = ""
    if history:
        for item in history[-10:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            history_text += f"{role}: {content}\n"

    full_prompt = f"{SYSTEM_PROMPT}\n\nHistory:\n{history_text}\nUser: {prompt}\nAION_MATRIX:"
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False}

    async with http_session.post(url, json=payload, timeout=45) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data.get("response", "").strip()

        text = await resp.text()
        raise Exception(f"Ollama status {resp.status}: {text[:200]}")


async def run_ai_pipeline(text, history):
    facts = []
    user_id = None

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})

    errors = []

    # Premium OpenRouter slot: uses existing OpenRouter key. If the paid/flagship model is unavailable, it falls back.
    if OPENROUTER_API_KEY and OPENROUTER_SMART_MODEL:
        try:
            return await ask_openai_compatible(
                "OpenRouter premium",
                "https://openrouter.ai/api/v1/chat/completions",
                OPENROUTER_API_KEY,
                OPENROUTER_SMART_MODEL,
                messages,
                timeout=35,
                temperature=0.65,
                max_tokens=4096
            )
        except Exception as e:
            errors.append(str(e))

    if GROQ_API_KEY:
        try:
            return await ask_openai_compatible(
                "Groq",
                "https://api.groq.com/openai/v1/chat/completions",
                GROQ_API_KEY,
                "llama-3.1-8b-instant",
                messages,
                timeout=15,
                temperature=0.7
            )
        except Exception as e:
            errors.append(str(e))

    if CEREBRAS_API_KEY:
        try:
            return await ask_openai_compatible(
                "Cerebras",
                "https://api.cerebras.ai/v1/chat/completions",
                CEREBRAS_API_KEY,
                "llama3.1-8b",
                messages,
                timeout=15,
                temperature=0.7
            )
        except Exception as e:
            errors.append(str(e))

    if OPENROUTER_API_KEY and OPENROUTER_FALLBACK_MODEL:
        try:
            return await ask_openai_compatible(
                "OpenRouter fallback",
                "https://openrouter.ai/api/v1/chat/completions",
                OPENROUTER_API_KEY,
                OPENROUTER_FALLBACK_MODEL,
                messages,
                timeout=20,
                temperature=0.7
            )
        except Exception as e:
            errors.append(str(e))

    if OLLAMA_BASE_URL:
        try:
            return await ask_ollama(text, history)
        except Exception as e:
            errors.append(str(e))

    return "❌ Все ИИ-узлы не ответили:\n" + "\n".join(f"• {html.escape(e)}" for e in errors[-8:])


async def run_code_ai_pipeline(user_prompt, current_code):
    system = (
        "You are a senior Python engineer. Return ONLY full valid Python code for main.py. "
        "No markdown. No explanations. Preserve Telegram bot startup, aiohttp web healthcheck, "
        "SQLite memory, owner protection for deploy/evolution commands, and all environment keys."
    )

    prompt = (
        f"User request:\n{user_prompt}\n\n"
        f"Current main.py:\n{current_code[:65000]}\n\n"
        "Return full updated main.py only."
    )

    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    errors = []

    # For code generation, try the smartest OpenRouter model first.
    if OPENROUTER_API_KEY and OPENROUTER_SMART_MODEL:
        try:
            return await ask_openai_compatible(
                "OpenRouter premium code",
                "https://openrouter.ai/api/v1/chat/completions",
                OPENROUTER_API_KEY,
                OPENROUTER_SMART_MODEL,
                messages,
                timeout=80,
                temperature=0.25,
                max_tokens=30000
            )
        except Exception as e:
            errors.append(str(e))

    # Then regular cascade.
    try:
        return await run_ai_pipeline(prompt, [])
    except Exception as e:
        errors.append(str(e))

    raise Exception("Code generation failed: " + "; ".join(errors))


# ---------------- SEARCH ENGINES ----------------

async def search_tavily(query):
    if not TAVILY_API_KEY:
        return [], "Tavily key missing"

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": 6,
        "include_answer": True,
    }

    async with http_session.post("https://api.tavily.com/search", json=payload, timeout=25) as resp:
        if resp.status != 200:
            text = await resp.text()
            return [], f"Tavily status {resp.status}: {text[:160]}"

        data = await resp.json()
        results = []

        if data.get("answer"):
            results.append({
                "source": "Tavily AI",
                "title": "AI Answer",
                "content": data.get("answer", ""),
                "url": "",
            })

        for item in data.get("results", []):
            results.append({
                "source": "Tavily",
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "url": item.get("url", ""),
            })

        return results, None


async def search_google(query):
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        return [], "Google Search key/cx missing"

    params = {
        "key": GOOGLE_SEARCH_API_KEY,
        "cx": GOOGLE_SEARCH_ENGINE_ID,
        "q": query,
        "num": 6,
    }

    async with http_session.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=25) as resp:
        if resp.status != 200:
            text = await resp.text()
            return [], f"Google status {resp.status}: {text[:160]}"

        data = await resp.json()
        results = []
        for item in data.get("items", []):
            results.append({
                "source": "Google",
                "title": item.get("title", ""),
                "content": item.get("snippet", ""),
                "url": item.get("link", ""),
            })

        return results, None


def strip_tags(value):
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.DOTALL | re.IGNORECASE)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.DOTALL | re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_yandex_data(data):
    results = []

    def add(title, content, url=""):
        if title or content or url:
            results.append({
                "source": "Yandex",
                "title": str(title or "Yandex result")[:300],
                "content": str(content or "")[:900],
                "url": str(url or ""),
            })

    # Several response shapes are supported because the API can return rawData or structured data.
    raw = data.get("rawData") or data.get("raw_data")
    if raw:
        try:
            decoded = base64.b64decode(raw).decode("utf-8", errors="ignore")
            try:
                nested = json.loads(decoded)
                results.extend(parse_yandex_data(nested))
            except Exception:
                clean = strip_tags(decoded)
                if clean:
                    add("Yandex raw results", clean[:1800], "")
        except Exception:
            pass

    possible_lists = []
    for key in ("results", "documents", "items"):
        if isinstance(data.get(key), list):
            possible_lists.append(data.get(key))

    response = data.get("response")
    if isinstance(response, dict):
        for key in ("results", "documents", "items"):
            if isinstance(response.get(key), list):
                possible_lists.append(response.get(key))

    for group in possible_lists:
        for item in group[:8]:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name") or item.get("headline")
            content = item.get("snippet") or item.get("content") or item.get("text") or item.get("passage")
            url = item.get("url") or item.get("link")
            add(title, content, url)

    return results


async def search_yandex(query):
    if not YANDEX_SEARCH_API_KEY or not YANDEX_FOLDER_ID:
        return [], "Yandex key/folder missing"

    url = "https://searchapi.api.cloud.yandex.net/v2/web/search"
    headers = {
        "Authorization": f"Api-Key {YANDEX_SEARCH_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query,
            "familyMode": "FAMILY_MODE_MODERATE",
        },
        "folderId": YANDEX_FOLDER_ID,
        "responseFormat": "FORMAT_JSON",
        "pageSize": 6,
    }

    async with http_session.post(url, json=payload, headers=headers, timeout=30) as resp:
        text = await resp.text()
        if resp.status != 200:
            return [], f"Yandex status {resp.status}: {text[:160]}"

        try:
            data = json.loads(text)
        except Exception:
            return [{
                "source": "Yandex",
                "title": "Yandex raw",
                "content": strip_tags(text)[:1200],
                "url": "",
            }], None

        parsed = parse_yandex_data(data)
        return parsed, None


async def search_all(query):
    tasks = [
        search_tavily(query),
        search_google(query),
        search_yandex(query),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    final = []
    errors = []

    names = ["Tavily", "Google", "Yandex"]
    for name, item in zip(names, results):
        if isinstance(item, Exception):
            errors.append(f"{name}: {item}")
            continue

        engine_results, error = item
        if error:
            errors.append(error)
        final.extend(engine_results)

    seen = set()
    deduped = []
    for item in final:
        key = item.get("url") or (item.get("source", "") + item.get("title", "") + item.get("content", "")[:80])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped, errors


async def answer_with_search(query):
    results, errors = await search_all(query)
    context = "\n\n".join(
        f"[{r.get('source')}] {r.get('title')}\n{r.get('content')}\nURL: {r.get('url')}"
        for r in results[:12]
    )

    if not context:
        return None, results, errors

    prompt = (
        "Используя результаты поиска ниже, ответь пользователю кратко, точно и практично. "
        "Если данные противоречат друг другу, скажи об этом.\n\n"
        f"Запрос: {query}\n\n"
        f"Результаты:\n{context}"
    )
    answer = await run_ai_pipeline(prompt, [])
    return answer, results, errors


# ---------------- MEDIA ----------------

async def generate_image(prompt):
    if not POLLINATIONS_ENABLED:
        raise Exception("Pollinations отключён в конфигурации.")
    return f"https://image.pollinations.ai/prompt/{quote(prompt)}"


async def generate_music(prompt):
    if not HUGGINGFACE_API_KEY:
        raise Exception("HUGGINGFACE_API_KEY отсутствует.")

    url = "https://api-inference.huggingface.co/models/facebook/musicgen-melody"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {"inputs": prompt}

    async with http_session.post(url, headers=headers, json=payload, timeout=90) as resp:
        if resp.status == 200:
            return await resp.read()

        if resp.status == 503:
            await asyncio.sleep(15)
            async with http_session.post(url, headers=headers, json=payload, timeout=90) as retry:
                if retry.status == 200:
                    return await retry.read()
                text = await retry.text()
                raise Exception(f"HuggingFace retry status {retry.status}: {text[:200]}")

        text = await resp.text()
        raise Exception(f"HuggingFace status {resp.status}: {text[:200]}")


async def generate_video(prompt):
    if not FAL_API_KEY:
        raise Exception("FAL_API_KEY отсутствует.")

    url = "https://queue.fal.run/fal-ai/luma-dream-machine"
    headers = {
        "Authorization": f"Key {FAL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "aspect_ratio": "16:9",
    }

    async with http_session.post(url, headers=headers, json=payload, timeout=25) as resp:
        if resp.status not in (200, 201, 202):
            text = await resp.text()
            raise Exception(f"Fal submit status {resp.status}: {text[:200]}")

        data = await resp.json()
        status_url = data.get("status_url")
        response_url = data.get("response_url")

    if not status_url:
        raise Exception("Fal не вернул status_url.")

    for _ in range(50):
        await asyncio.sleep(4)
        async with http_session.get(status_url, headers=headers, timeout=20) as resp:
            if resp.status in (200, 202):
                data = await resp.json()
                status = str(data.get("status", "")).upper()

                if status == "FAILED":
                    raise Exception(str(data.get("error") or "Fal render failed"))

                if status == "COMPLETED":
                    video_url = (data.get("video") or {}).get("url")
                    if video_url:
                        return video_url

                    if response_url:
                        async with http_session.get(response_url, headers=headers, timeout=20) as final:
                            final_data = await final.json()
                            video_url = (final_data.get("video") or {}).get("url")
                            if video_url:
                                return video_url

                    raise Exception("Видео готово, но URL не найден.")

    raise Exception("Таймаут генерации видео.")


# ---------------- EVOLUTION / DEPLOY ----------------

class EvolutionCore:
    @staticmethod
    def verify(code: str):
        if not code or len(code) < 1000:
            return False, "код слишком короткий"

        required = [
            "async def main",
            "Dispatcher",
            "Bot(",
            "dp.start_polling",
            "handle_web_root",
            "BOT_TOKEN",
        ]

        missing = [x for x in required if x not in code]
        if missing:
            return False, "нет критических элементов: " + ", ".join(missing)

        try:
            compile(code, "main.py", "exec")
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"

        return True, "ok"

    @staticmethod
    async def get_current_sha():
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/main.py"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        }

        async with http_session.get(url, headers=headers, timeout=20) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"GitHub GET status {resp.status}: {text[:200]}")
            data = await resp.json()
            return data["sha"]

    @staticmethod
    async def commit_main(new_code: str, commit_message: str):
        sha = await EvolutionCore.get_current_sha()
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/main.py"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        }

        payload = {
            "message": commit_message[:250],
            "content": base64.b64encode(new_code.encode("utf-8")).decode("ascii"),
            "sha": sha,
        }

        async with http_session.put(url, headers=headers, json=payload, timeout=35) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise Exception(f"GitHub PUT status {resp.status}: {text[:250]}")

            return await resp.json()

    @staticmethod
    async def trigger_render_deploy():
        if not RENDER_SERVICE_ID:
            raise Exception("RENDER_SERVICE_ID отсутствует.")

        url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
        headers = {
            "Authorization": f"Bearer {RENDER_API_KEY}",
            "Accept": "application/json",
        }

        async with http_session.post(url, headers=headers, timeout=30) as resp:
            if resp.status not in (200, 201, 202):
                text = await resp.text()
                raise Exception(f"Render deploy status {resp.status}: {text[:250]}")
            return await resp.json()

    @staticmethod
    async def commit_and_deploy(new_code: str, message: str = "AION_MATRIX update"):
        if not GITHUB_TOKEN:
            return "❌ GITHUB_TOKEN отсутствует."
        if not RENDER_API_KEY:
            return "❌ RENDER_API_KEY отсутствует."
        if not RENDER_SERVICE_ID:
            return "❌ RENDER_SERVICE_ID отсутствует."

        ok, reason = EvolutionCore.verify(new_code)
        if not ok:
            return f"❌ Код не прошёл проверку: {reason}"

        try:
            await EvolutionCore.commit_main(new_code, f"Evolution: {message}")
            await EvolutionCore.trigger_render_deploy()
            return "✅ main.py обновлён в GitHub. Render начал новый деплой."
        except Exception as e:
            return f"❌ Ошибка самообновления: {e}"


# ---------------- HEALTH CHECKS ----------------

async def check_url(name, method, url, headers=None, json_body=None, params=None, timeout=8):
    try:
        start = time.time()
        if method == "GET":
            req = http_session.get(url, headers=headers, params=params, timeout=timeout)
        else:
            req = http_session.post(url, headers=headers, json=json_body, params=params, timeout=timeout)

        async with req as resp:
            latency = int((time.time() - start) * 1000)
            if resp.status in (200, 201, 202):
                return name, f"✅ OK {resp.status} ({latency}ms)"
            if resp.status in (401, 403):
                return name, f"❌ AUTH {resp.status}"
            if resp.status == 429:
                return name, "⚠️ RATE LIMIT 429"
            return name, f"⚠️ HTTP {resp.status} ({latency}ms)"
    except asyncio.TimeoutError:
        return name, "⏳ TIMEOUT"
    except Exception as e:
        return name, f"❌ ERROR {str(e)[:120]}"


async def get_health_report():
    tasks = []

    if GROQ_API_KEY:
        tasks.append(check_url(
            "Groq",
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json_body={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
        ))

    if CEREBRAS_API_KEY:
        tasks.append(check_url(
            "Cerebras",
            "POST",
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"},
            json_body={"model": "llama3.1-8b", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
        ))

    if OPENROUTER_API_KEY:
        tasks.append(check_url(
            "OpenRouter premium",
            "POST",
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json", "X-Title": "AION_MATRIX"},
            json_body={"model": OPENROUTER_SMART_MODEL, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
        ))

    if TAVILY_API_KEY:
        tasks.append(check_url(
            "Tavily",
            "POST",
            "https://api.tavily.com/search",
            json_body={"api_key": TAVILY_API_KEY, "query": "ping", "max_results": 1},
        ))

    if GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
        tasks.append(check_url(
            "Google Search",
            "GET",
            "https://www.googleapis.com/customsearch/v1",
            params={"key": GOOGLE_SEARCH_API_KEY, "cx": GOOGLE_SEARCH_ENGINE_ID, "q": "ping", "num": 1},
        ))

    if YANDEX_SEARCH_API_KEY and YANDEX_FOLDER_ID:
        tasks.append(check_url(
            "Yandex Search",
            "POST",
            "https://searchapi.api.cloud.yandex.net/v2/web/search",
            headers={"Authorization": f"Api-Key {YANDEX_SEARCH_API_KEY}", "Content-Type": "application/json"},
            json_body={
                "query": {"searchType": "SEARCH_TYPE_RU", "queryText": "ping"},
                "folderId": YANDEX_FOLDER_ID,
                "responseFormat": "FORMAT_JSON",
                "pageSize": 1,
            },
        ))

    if GITHUB_TOKEN:
        tasks.append(check_url(
            "GitHub",
            "GET",
            f"https://api.github.com/repos/{GITHUB_REPO}",
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
        ))

    if RENDER_API_KEY:
        tasks.append(check_url(
            "Render",
            "GET",
            "https://api.render.com/v1/services?limit=1",
            headers={"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"},
        ))

    if CLOUDFLARE_API_TOKEN:
        tasks.append(check_url(
            "Cloudflare",
            "GET",
            "https://api.cloudflare.com/client/v4/zones?per_page=1",
            headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
        ))

    if HUGGINGFACE_API_KEY:
        tasks.append(check_url(
            "HuggingFace",
            "GET",
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"},
        ))

    if FAL_API_KEY:
        tasks.append(check_url(
            "Fal.ai",
            "GET",
            "https://rest.alpha.fal.ai/v1/models",
            headers={"Authorization": f"Key {FAL_API_KEY}"},
        ))

    if OLLAMA_BASE_URL:
        tasks.append(check_url(
            "Ollama",
            "GET",
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags",
        ))

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = []
    for item in results:
        if isinstance(item, Exception):
            output.append(("unknown", f"❌ {item}"))
        else:
            output.append(item)
    return output


# ---------------- COMMANDS ----------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(STRINGS["welcome"], parse_mode="HTML")


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    out = (
        "📊 <b>AION_MATRIX CONFIG STATUS</b>\n\n"
        f"BOT_TOKEN: {loaded(BOT_TOKEN)}\n"
        f"OWNER_ID: {loaded(OWNER_ID)}\n"
        f"PORT: <code>{PORT}</code>\n\n"
        f"GROQ_API_KEY: {loaded(GROQ_API_KEY)}\n"
        f"CEREBRAS_API_KEY: {loaded(CEREBRAS_API_KEY)}\n"
        f"OPENROUTER_API_KEY: {loaded(OPENROUTER_API_KEY)}\n"
        f"OPENROUTER_SMART_MODEL: <code>{html.escape(OPENROUTER_SMART_MODEL)}</code>\n"
        f"OPENROUTER_FALLBACK_MODEL: <code>{html.escape(OPENROUTER_FALLBACK_MODEL)}</code>\n"
        f"OLLAMA_BASE_URL: {loaded(OLLAMA_BASE_URL)}\n\n"
        f"TAVILY_API_KEY: {loaded(TAVILY_API_KEY)}\n"
        f"GOOGLE_SEARCH_API_KEY: {loaded(GOOGLE_SEARCH_API_KEY)}\n"
        f"GOOGLE_SEARCH_ENGINE_ID: {loaded(GOOGLE_SEARCH_ENGINE_ID)}\n"
        f"YANDEX_SEARCH_API_KEY: {loaded(YANDEX_SEARCH_API_KEY)}\n"
        f"YANDEX_FOLDER_ID: {loaded(YANDEX_FOLDER_ID)}\n\n"
        f"GITHUB_TOKEN: {loaded(GITHUB_TOKEN)}\n"
        f"GITHUB_REPO: <code>{html.escape(GITHUB_REPO)}</code>\n"
        f"RENDER_API_KEY: {loaded(RENDER_API_KEY)}\n"
        f"RENDER_SERVICE_ID: {loaded(RENDER_SERVICE_ID)}\n\n"
        f"CLOUDFLARE_ACCOUNT_ID: {loaded(CLOUDFLARE_ACCOUNT_ID)}\n"
        f"CLOUDFLARE_API_TOKEN: {loaded(CLOUDFLARE_API_TOKEN)}\n\n"
        f"HUGGINGFACE_API_KEY: {loaded(HUGGINGFACE_API_KEY)}\n"
        f"FAL_API_KEY: {loaded(FAL_API_KEY)}\n"
        f"POLLINATIONS_ENABLED: <code>{str(POLLINATIONS_ENABLED).upper()}</code>\n\n"
        f"Memory rows/user: <code>{MAX_MEMORY_ROWS}</code>"
    )
    await message.answer(out, parse_mode="HTML")


@dp.message(Command("health"))
async def cmd_health(message: types.Message):
    if not await require_session(message):
        return

    status = await message.answer("🧪 Проверяю API-узлы...")
    checks = await get_health_report()

    out = "🧪 <b>AION_MATRIX API HEALTH</b>\n\n"
    if not checks:
        out += "Нет узлов для проверки."
    else:
        for name, result in checks:
            out += f"• <b>{html.escape(name)}:</b> {html.escape(result)}\n"

    await status.delete()
    await send_split(message, out, "HTML")


@dp.message(Command("memory"))
async def cmd_memory(message: types.Message):
    user_id = message.from_user.id
    facts = get_facts(user_id, 50)
    mem = get_memory(user_id, 20)

    out = "🧠 <b>AION MEMORY</b>\n\n"
    out += "<b>Факты:</b>\n"
    if facts:
        for f in facts:
            out += f"• {html.escape(f)}\n"
    else:
        out += "Пока нет сохранённых фактов.\n"

    out += "\n<b>Последний диалог:</b>\n"
    if mem:
        for item in mem[-10:]:
            out += f"• <b>{html.escape(item['role'])}:</b> {html.escape(item['content'][:250])}\n"
    else:
        out += "История пока пустая."

    await send_split(message, out, "HTML")


@dp.message(Command("remember"))
async def cmd_remember(message: types.Message):
    fact = message.text.replace("/remember", "", 1).strip()
    if not fact:
        return await message.answer("⚠️ Использование: /remember [факт]")

    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    add_fact(message.from_user.id, fact)
    await message.answer("✅ Запомнила, кохай.")


@dp.message(Command("clear_memory"))
async def cmd_clear_memory(message: types.Message):
    clear_memory(message.from_user.id)
    await message.answer("🧹 Память очищена.")


@dp.message(Command("image"))
async def cmd_image(message: types.Message):
    if not await require_session(message):
        return
    if not cooldown(message.from_user.id):
        return await message.answer(STRINGS["cooldown"])

    prompt = message.text.replace("/image", "", 1).strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /image [промпт]")

    status = await message.answer("🖼️ Генерация изображения...")
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
    if not await require_session(message):
        return
    if not cooldown(message.from_user.id):
        return await message.answer(STRINGS["cooldown"])

    prompt = message.text.replace("/music", "", 1).strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /music [промпт]")

    status = await message.answer("🎼 Генерация музыки...")
    try:
        audio = await generate_music(prompt)
        await status.delete()
        await message.answer_audio(
            BufferedInputFile(audio, filename="aion_music.wav"),
            caption=f"🎼 <b>Prompt:</b> {html.escape(prompt)}",
            parse_mode="HTML"
        )
    except Exception as e:
        await status.edit_text(f"❌ Ошибка music: {e}")


@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    if not await require_session(message):
        return
    if not cooldown(message.from_user.id):
        return await message.answer(STRINGS["cooldown"])

    prompt = message.text.replace("/video", "", 1).strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /video [промпт]")

    status = await message.answer("🎥 Генерация видео...")
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


@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    if not await require_session(message):
        return
    if not cooldown(message.from_user.id):
        return await message.answer(STRINGS["cooldown"])

    query = message.text.replace("/search", "", 1).strip()
    if not query:
        return await message.answer("⚠️ Использование: /search [запрос]")

    status = await message.answer(STRINGS["searching"])
    try:
        answer, results, errors = await answer_with_search(query)

        out = f"🔍 <b>Поиск:</b> {html.escape(query)}\n\n"

        if answer:
            out += f"🧠 <b>Ответ AION:</b>\n{html.escape(answer)}\n\n"

        if results:
            out += "<b>Источники:</b>\n"
            for r in results[:12]:
                out += (
                    f"🌐 <b>{html.escape(r.get('source', ''))}</b>\n"
                    f"🔹 <b>{html.escape(r.get('title', ''))}</b>\n"
                    f"{html.escape(r.get('content', '')[:700])}\n"
                )
                if r.get("url"):
                    out += f"🔗 {html.escape(r.get('url', ''))}\n"
                out += "\n"

        if errors:
            out += "⚠️ <b>Ошибки отдельных движков:</b>\n"
            for err in errors:
                out += f"• {html.escape(err)}\n"

        if not results and not answer:
            out += "❌ Поиск не дал результатов."

        await status.delete()
        await send_split(message, out, "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка search: {e}")


@dp.message(Command("ollama"))
async def cmd_ollama(message: types.Message):
    if not await require_session(message):
        return
    if not OLLAMA_BASE_URL:
        return await message.answer("❌ OLLAMA_BASE_URL отсутствует.")

    prompt = message.text.replace("/ollama", "", 1).strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /ollama [запрос]")

    status = await message.answer("🦙 Спрашиваю Ollama...")
    try:
        answer = await ask_ollama(prompt, get_memory(message.from_user.id, 10))
        await status.delete()
        await send_split(message, answer)
    except Exception as e:
        await status.edit_text(f"❌ Ошибка Ollama: {e}")


@dp.message(Command("github"))
async def cmd_github(message: types.Message):
    if not await require_session(message):
        return

    repo = message.text.replace("/github", "", 1).strip() or GITHUB_REPO
    if "/" not in repo:
        return await message.answer("⚠️ Использование: /github owner/repo")

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    status = await message.answer("🐙 Анализирую GitHub...")
    try:
        async with http_session.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=20) as resp:
            if resp.status != 200:
                text = await resp.text()
                return await status.edit_text(f"❌ GitHub status {resp.status}: {text[:200]}")
            d = await resp.json()

        out = (
            f"🐙 <b>{html.escape(d.get('full_name', ''))}</b>\n"
            f"📝 {html.escape(d.get('description') or 'Нет описания')}\n"
            f"⭐ Stars: <code>{d.get('stargazers_count')}</code>\n"
            f"🍴 Forks: <code>{d.get('forks_count')}</code>\n"
            f"⚠️ Issues: <code>{d.get('open_issues_count')}</code>\n"
            f"🌿 Default branch: <code>{html.escape(d.get('default_branch', ''))}</code>\n"
            f"🔗 {html.escape(d.get('html_url', ''))}"
        )
        await status.delete()
        await message.answer(out, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        await status.edit_text(f"❌ Ошибка GitHub: {e}")


@dp.message(Command("render"))
async def cmd_render(message: types.Message):
    if not await require_session(message):
        return
    if not RENDER_API_KEY:
        return await message.answer("❌ RENDER_API_KEY отсутствует.")

    status = await message.answer("🧬 Проверяю Render...")
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}

    try:
        out = "🧬 <b>Render</b>\n\n"

        if RENDER_SERVICE_ID:
            async with http_session.get(f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}", headers=headers, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    srv = data.get("service", data)
                    out += (
                        f"<b>Current service:</b>\n"
                        f"🖥️ {html.escape(srv.get('name', ''))}\n"
                        f"🆔 <code>{html.escape(RENDER_SERVICE_ID)}</code>\n"
                        f"🌍 Type: <code>{html.escape(srv.get('type', ''))}</code>\n"
                        f"⏱️ Updated: <code>{html.escape(srv.get('updatedAt', ''))}</code>\n\n"
                    )
                else:
                    out += f"Current service status: HTTP {resp.status}\n\n"

        async with http_session.get("https://api.render.com/v1/services?limit=5", headers=headers, timeout=20) as resp:
            if resp.status != 200:
                text = await resp.text()
                return await status.edit_text(f"❌ Render status {resp.status}: {text[:200]}")
            services = await resp.json()

        out += "<b>Services:</b>\n"
        for item in services:
            srv = item.get("service", {})
            out += (
                f"• <b>{html.escape(srv.get('name', ''))}</b> "
                f"[<code>{html.escape(srv.get('type', ''))}</code>]\n"
            )

        await status.delete()
        await send_split(message, out, "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка Render: {e}")


@dp.message(Command("deploy"))
async def cmd_deploy(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.answer("⛔ Доступ запрещён.")
    if not await require_session(message):
        return

    status = await message.answer("🚀 Запускаю Render deploy...")
    try:
        await EvolutionCore.trigger_render_deploy()
        await status.edit_text("✅ Render deploy запущен.")
    except Exception as e:
        await status.edit_text(f"❌ Deploy error: {e}")


@dp.message(Command("cloudflare"))
async def cmd_cloudflare(message: types.Message):
    if not await require_session(message):
        return
    if not CLOUDFLARE_API_TOKEN:
        return await message.answer("❌ CLOUDFLARE_API_TOKEN отсутствует.")

    status = await message.answer("☁️ Проверяю Cloudflare...")
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}

    try:
        out = "☁️ <b>Cloudflare</b>\n\n"

        if CLOUDFLARE_ACCOUNT_ID:
            async with http_session.get(f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}", headers=headers, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    acc = data.get("result", {})
                    out += (
                        f"<b>Account:</b> {html.escape(acc.get('name', ''))}\n"
                        f"ID: <code>{html.escape(CLOUDFLARE_ACCOUNT_ID)}</code>\n\n"
                    )
                else:
                    out += f"Account check: HTTP {resp.status}\n\n"

        async with http_session.get("https://api.cloudflare.com/client/v4/zones?status=active&per_page=10", headers=headers, timeout=20) as resp:
            if resp.status != 200:
                text = await resp.text()
                return await status.edit_text(f"❌ Cloudflare status {resp.status}: {text[:200]}")
            zones = (await resp.json()).get("result", [])

        out += "<b>Active zones:</b>\n"
        if zones:
            for z in zones:
                out += f"🌐 <b>{html.escape(z.get('name', ''))}</b>\nID: <code>{html.escape(z.get('id', ''))}</code>\n\n"
        else:
            out += "Активных зон не найдено."

        await status.delete()
        await send_split(message, out, "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка Cloudflare: {e}")


@dp.message(Command("evolve"))
async def cmd_evolve(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.answer("⛔ Доступ запрещён.")
    if not await require_session(message):
        return
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.answer("⚠️ Ответь командой /evolve на сообщение с полным новым main.py.")

    new_code = extract_python_code(message.reply_to_message.text)
    status = await message.answer("🛠 Проверяю код и запускаю самообновление...")
    result = await EvolutionCore.commit_and_deploy(new_code, "manual owner update")
    await status.edit_text(result)


@dp.message(Command("evolve_auto"))
async def cmd_evolve_auto(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return await message.answer("⛔ Доступ запрещён.")
    if not await require_session(message):
        return

    task = message.text.replace("/evolve_auto", "", 1).strip()
    if not task:
        return await message.answer("⚠️ Использование: /evolve_auto [что изменить в main.py]")

    status = await message.answer("🧬 Читаю текущий main.py и генерирую обновление...")
    try:
        with open("main.py", "r", encoding="utf-8") as f:
            current_code = f.read()

        generated = await run_code_ai_pipeline(task, current_code)
        new_code = extract_python_code(generated)

        ok, reason = EvolutionCore.verify(new_code)
        if not ok:
            return await status.edit_text(f"❌ ИИ сгенерировал код, но проверка провалена: {reason}")

        await status.edit_text("✅ Код сгенерирован и прошёл проверку. Коммичу и запускаю деплой...")
        result = await EvolutionCore.commit_and_deploy(new_code, f"auto evolution: {task[:120]}")
        await message.answer(result)
    except Exception as e:
        await status.edit_text(f"❌ Ошибка evolve_auto: {e}")


# ---------------- MAIN CHAT ----------------

@dp.message()
async def chat_processor(message: types.Message):
    if not message.text:
        return await message.answer(STRINGS["only_text"])

    if message.text.startswith("/"):
        return

    user_id = message.from_user.id
    save_user(user_id, message.from_user.username, message.from_user.first_name)

    remembered = maybe_auto_remember(user_id, message.text)
    if remembered:
        return await message.answer(f"✅ Запомнила: {remembered}")

    parsed_name = parse_user_name(message.text)
    if parsed_name:
        set_display_name(user_id, parsed_name)
        add_fact(user_id, f"Имя пользователя: {parsed_name}")
        return await message.answer(f"Очень приятно, {parsed_name}. Я запомнила, кохай.")

    if is_name_question(message.text):
        return await message.answer(
            "Меня зовут AION_MATRIX.\n\n"
            "AION — это моё имя, MATRIX — моя фамилия.\n\n"
            "Можешь называть меня просто AION, если хочешь, или как тебе удобно.\n\n"
            "А как мне называть тебя? Дай мне имя, и я его запомню."
        )

    if is_capability_question(message.text):
        return await message.answer(
            "Я умею вести ИИ-диалог с памятью, помогать с кодом, переводами, текстами, анализом, "
            "искать свежую информацию через Tavily + Google + Yandex, проверять GitHub, Render и Cloudflare, "
            "а ещё могу аккуратно обновлять свой код через GitHub + Render, если команду даёт владелец.\n\n"
            "Говорю мягко, когда надо поддержать. Жёстко — когда надо собраться. Такая вот я, AION 😈"
        )

    facts = get_facts(user_id, 30)
    history = get_memory(user_id, HISTORY_LIMIT)

    if facts:
        history = [{"role": "system", "content": "Saved user facts:\n" + "\n".join(f"- {f}" for f in facts)}] + history

    status = await message.answer(STRINGS["thinking"])
    response = await run_ai_pipeline(message.text, history)

    save_memory(user_id, "user", message.text)
    save_memory(user_id, "assistant", response)

    await status.delete()
    await send_split(message, response)


# ---------------- WEB SERVER ----------------

async def handle_web_root(request):
    return web.Response(
        text="<h1>AION_MATRIX ONLINE</h1><p>AI orchestration core is running.</p>",
        content_type="text/html"
    )


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_web_root)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Healthcheck web server started on port {PORT}")


# ---------------- MAIN ----------------

async def main():
    global bot, http_session

    if not BOT_TOKEN:
        sys.exit("BOT_TOKEN отсутствует.")

    bot = Bot(token=BOT_TOKEN)
    http_session = aiohttp.ClientSession()

    init_db()
    await start_web_server()

    logger.info("AION_MATRIX started.")
    try:
        await dp.start_polling(bot)
    finally:
        if http_session and not http_session.closed:
            await http_session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

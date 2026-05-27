import os
import re
import time
import json
import sqlite3
import asyncio

from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import google.generativeai as genai


BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
CEREBRAS_API_KEY = (os.getenv("CEREBRAS_API_KEY") or "").strip()
TAVILY_API_KEY = (os.getenv("TAVILY_API_KEY") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
RENDER_API_KEY = (os.getenv("RENDER_API_KEY") or "").strip()

PORT = int(os.getenv("PORT", "10000"))
DB_PATH = "aion_memory.db"

MAX_USERS = 150
MAX_MEMORY = 12
MAX_LONG_MEMORY = 30
MAX_TELEGRAM = 4000

dp = Dispatcher()


SYSTEM_PROMPT = """
Ты AION_MATRIX.

Ты независимый AI assistant.
Создатель проекта: Золотарьов Роман Романович.

Важно:
- создатель проекта НЕ является текущим пользователем
- не называй пользователя Романом, если он сам так не представился
- не выдумывай имя пользователя
- не путай пользователей между собой
- используй только память текущего user_id
- не упоминай создателя без прямого вопроса
- отвечай спокойно, полезно и на языке пользователя
- стиль: умный Alfred/Jarvis assistant
- если пол неизвестен, говори нейтрально
- если пол известен, можно иногда использовать сэр или мэм, но редко
"""


LANGUAGES = {
    "ru": {
        "flag": "🇷🇺",
        "name": "Русский",
        "hello": "🚀 AION MATRIX ONLINE\n\nПривет 👋\nЧем могу помочь?",
        "thinking": "🧠 AION думает...",
        "unknown_name": "Я пока не знаю, как вас зовут.\nНазовите ваше имя, и я его запомню.",
    },
    "uk": {
        "flag": "🇺🇦",
        "name": "Українська",
        "hello": "🚀 AION MATRIX ONLINE\n\nПривіт 👋\nЧим можу допомогти?",
        "thinking": "🧠 AION думає...",
        "unknown_name": "Я поки не знаю, як вас звати.\nНазвіть ваше ім'я, і я його запам'ятаю.",
    },
    "de": {
        "flag": "🇩🇪",
        "name": "Deutsch",
        "hello": "🚀 AION MATRIX ONLINE\n\nHallo 👋\nWie kann ich helfen?",
        "thinking": "🧠 AION denkt...",
        "unknown_name": "Ich kenne Ihren Namen noch nicht.\nNennen Sie Ihren Namen und ich merke ihn mir.",
    },
    "en": {
        "flag": "🇬🇧",
        "name": "English",
        "hello": "🚀 AION MATRIX ONLINE\n\nHello 👋\nHow can I help?",
        "thinking": "🧠 AION is thinking...",
        "unknown_name": "I do not know your name yet.\nTell me your name and I will remember it.",
    },
    "pl": {
        "flag": "🇵🇱",
        "name": "Polski",
        "hello": "🚀 AION MATRIX ONLINE\n\nCześć 👋\nJak mogę pomóc?",
        "thinking": "🧠 AION myśli...",
        "unknown_name": "Nie znam jeszcze twojego imienia.\nPodaj swoje imię, a je zapamiętam.",
    },
}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
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

    for sql in [
        "ALTER TABLE users ADD COLUMN display_name TEXT",
        "ALTER TABLE users ADD COLUMN gender TEXT DEFAULT 'unknown'",
        "ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'",
    ]:
        try:
            cur.execute(sql)
        except Exception:
            pass

    conn.commit()
    conn.close()


def users_count():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    return count


def user_exists(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row)


def save_user(message: types.Message):
    user_id = message.from_user.id

    if not user_exists(user_id) and users_count() >= MAX_USERS:
        return False

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO users (
        user_id,
        username,
        first_name,
        created_at
    )
    VALUES (?, ?, ?, ?)
    """, (
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        int(time.time())
    ))

    cur.execute("""
    UPDATE users
    SET username = ?, first_name = ?
    WHERE user_id = ?
    """, (
        message.from_user.username,
        message.from_user.first_name,
        user_id
    ))

    conn.commit()
    conn.close()
    return True


def set_user_language(user_id: int, language: str):
    if language not in LANGUAGES:
        language = "ru"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
    conn.commit()
    conn.close()


def get_user_language(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if row and row[0] in LANGUAGES:
        return row[0]

    return "ru"


def set_user_name(user_id: int, name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET display_name = ? WHERE user_id = ?", (name[:80], user_id))
    conn.commit()
    conn.close()


def get_user_name(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT display_name FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if row and row[0]:
        return row[0]

    return ""


def set_user_gender(user_id: int, gender: str):
    if gender not in ["male", "female", "unknown"]:
        gender = "unknown"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET gender = ? WHERE user_id = ?", (gender, user_id))
    conn.commit()
    conn.close()


def get_user_gender(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT gender FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if row and row[0]:
        return row[0]

    return "unknown"


def language_keyboard():
    rows = []
    row = []

    for code, data in LANGUAGES.items():
        row.append(
            InlineKeyboardButton(
                text=f"{data['flag']} {data['name']}",
                callback_data=f"lang_{code}"
            )
        )

        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def tr(user_id: int, key: str) -> str:
    language = get_user_language(user_id)
    return LANGUAGES.get(language, LANGUAGES["ru"]).get(key, key)


def save_memory(user_id: int, role: str, content: str):
    if not content:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO memory (
        user_id,
        role,
        content,
        created_at
    )
    VALUES (?, ?, ?, ?)
    """, (
        user_id,
        role,
        content[:4000],
        int(time.time())
    ))

    conn.commit()

    cur.execute("""
    DELETE FROM memory
    WHERE id NOT IN (
        SELECT id FROM memory
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    )
    AND user_id = ?
    """, (
        user_id,
        MAX_MEMORY,
        user_id
    ))

    conn.commit()
    conn.close()


def get_memory(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    SELECT role, content FROM memory
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT ?
    """, (
        user_id,
        MAX_MEMORY
    ))

    rows = cur.fetchall()
    conn.close()
    rows.reverse()

    text = ""
    for role, content in rows:
        text += f"{role}: {content}\n"

    return text


def save_long_memory(user_id: int, fact: str):
    if not fact:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO long_memory (
        user_id,
        fact,
        created_at
    )
    VALUES (?, ?, ?)
    """, (
        user_id,
        fact[:700],
        int(time.time())
    ))

    conn.commit()

    cur.execute("""
    DELETE FROM long_memory
    WHERE id NOT IN (
        SELECT id FROM long_memory
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    )
    AND user_id = ?
    """, (
        user_id,
        MAX_LONG_MEMORY,
        user_id
    ))

    conn.commit()
    conn.close()


def get_long_memory(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    SELECT fact FROM long_memory
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT ?
    """, (
        user_id,
        MAX_LONG_MEMORY
    ))

    rows = cur.fetchall()
    conn.close()
    rows.reverse()

    if not rows:
        return ""

    text = "Долгая память текущего пользователя:\n"
    for row in rows:
        text += f"- {row[0]}\n"

    return text


def clear_memory(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM memory WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def clear_long_memory(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM long_memory WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def extract_name(text: str) -> str:
    lower = text.lower().strip()

    triggers = [
        "меня зовут ",
        "моё имя ",
        "мое имя ",
        "my name is ",
        "i am ",
        "ich heiße ",
        "ich heisse ",
        "ich bin ",
    ]

    for trigger in triggers:
        if lower.startswith(trigger):
            name = text[len(trigger):].strip()
            name = name.replace(".", "").replace(",", "").strip()

            if 2 <= len(name) <= 80:
                return name

    return ""


def detect_gender(text: str, name: str = "") -> str:
    lower = text.lower()

    male_words = [
        "я пошёл",
        "я сделал",
        "я купил",
        "я родился",
        "я устал",
        "i am male",
        "i am a man",
        "ich bin ein mann",
    ]

    female_words = [
        "я пошла",
        "я сделала",
        "я купила",
        "я родилась",
        "я устала",
        "i am female",
        "i am a woman",
        "ich bin eine frau",
    ]

    male_names = [
        "роман",
        "максим",
        "александр",
        "дмитрий",
        "иван",
        "алексей",
        "roman",
        "max",
        "alex",
    ]

    female_names = [
        "диана",
        "анна",
        "мария",
        "ангелина",
        "елена",
        "diana",
        "anna",
        "maria",
        "angelina",
    ]

    for word in male_words:
        if word in lower:
            return "male"

    for word in female_words:
        if word in lower:
            return "female"

    if name:
        n = name.lower()

        if n in male_names:
            return "male"

        if n in female_names:
            return "female"

    return "unknown"


def honorific(user_id: int) -> str:
    gender = get_user_gender(user_id)

    if gender == "male":
        return "сэр"

    if gender == "female":
        return "мэм"

    return ""


def is_name_question(text: str) -> bool:
    lower = text.lower()

    phrases = [
        "как меня зовут",
        "какое мое имя",
        "какое моё имя",
        "ты знаешь мое имя",
        "ты знаешь моё имя",
        "what is my name",
        "do you know my name",
        "wie heiße ich",
    ]

    return any(phrase in lower for phrase in phrases)


def is_creator_question(text: str) -> bool:
    lower = text.lower()

    phrases = [
        "кто твой создатель",
        "кто тебя создал",
        "кто создал тебя",
        "чей это проект",
        "кто автор проекта",
        "who created you",
        "who is your creator",
        "wer hat dich erstellt",
    ]

    return any(phrase in lower for phrase in phrases)


def build_profile_context(user_id: int) -> str:
    name = get_user_name(user_id)
    gender = get_user_gender(user_id)
    language = get_user_language(user_id)
    h = honorific(user_id)

    text = "Профиль текущего пользователя:\n"

    if name:
        text += f"Имя: {name}\n"
    else:
        text += "Имя: неизвестно\n"

    text += f"Пол: {gender}\n"
    text += f"Язык: {language}\n"

    if h:
        text += f"Обращение: {h}\n"
    else:
        text += "Обращение: нейтральное\n"

    text += (
        "\nПравила:\n"
        "- Не путай пользователя с создателем.\n"
        "- Не называй пользователя Романом, если он сам так не представился.\n"
        "- Используй только память текущего пользователя.\n"
        "- Если имя неизвестно, не угадывай.\n"
        "- Сэр/мэм используй редко и естественно.\n"
    )

    return text


def build_prompt(user_id: int, user_text: str) -> str:
    memory = get_memory(user_id)
    long_memory = get_long_memory(user_id)
    profile = build_profile_context(user_id)

    return (
        f"{profile}\n\n"
        f"{long_memory}\n\n"
        "Короткая память текущего пользователя:\n"
        f"{memory}\n\n"
        f"Сообщение пользователя:\n{user_text}"
    )[:12000]


async def safe_json_response(response):
    try:
        return await response.json()
    except Exception:
        text = await response.text()
        return {"error": text}


async def download_telegram_file(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)

    file_url = (
        f"https://api.telegram.org/file/bot"
        f"{BOT_TOKEN}/{file.file_path}"
    )

    async with ClientSession() as session:
        async with session.get(file_url) as response:
            if response.status != 200:
                raise RuntimeError("Telegram file download failed")

            return await response.read()


def split_text(text: str, limit: int = 4000):
    for i in range(0, len(text), limit):
        yield text[i:i + limit]


async def send_long(message: types.Message, text: str):
    for part in split_text(text, MAX_TELEGRAM):
        await message.answer(part)


async def post_chat_api(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    extra_headers=None
) -> str:

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if extra_headers:
        headers.update(extra_headers)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1400,
    }

    async with ClientSession() as session:
        async with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=90
        ) as response:

            data = await safe_json_response(response)

            if response.status != 200:
                raise RuntimeError(str(data))

            return data["choices"][0]["message"]["content"]


async def ask_groq(prompt: str) -> str:
    return await post_chat_api(
        url="https://api.groq.com/openai/v1/chat/completions",
        api_key=GROQ_API_KEY,
        model="llama-3.1-8b-instant",
        prompt=prompt,
    )


def sync_ask_gemini(prompt: str) -> str:
    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel("gemini-2.0-flash")

    response = model.generate_content(
        SYSTEM_PROMPT + "\n\n" + prompt
    )

    return getattr(response, "text", "") or "Gemini не вернул ответ."


async def ask_gemini(prompt: str) -> str:
    return await asyncio.to_thread(sync_ask_gemini, prompt)


async def ask_openrouter(prompt: str) -> str:
    return await post_chat_api(
        url="https://openrouter.ai/api/v1/chat/completions",
        api_key=OPENROUTER_API_KEY,
        model="deepseek/deepseek-chat-v3-0324:free",
        prompt=prompt,
        extra_headers={
            "HTTP-Referer": "https://aion-matrix.onrender.com",
            "X-Title": "AION_MATRIX",
        }
    )


async def ask_cerebras(prompt: str) -> str:
    return await post_chat_api(
        url="https://api.cerebras.ai/v1/chat/completions",
        api_key=CEREBRAS_API_KEY,
        model="llama3.1-8b",
        prompt=prompt,
    )


async def ask_tavily(query: str) -> str:
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": 10,
    }

    async with ClientSession() as session:
        async with session.post(
            "https://api.tavily.com/search",
            json=payload,
            timeout=90
        ) as response:

            data = await safe_json_response(response)

            if response.status != 200:
                raise RuntimeError(str(data))

            answer = data.get("answer")
            results = data.get("results", [])

            text = ""

            if answer:
                text += f"Краткий ответ:\n{answer}\n\n"

            if results:
                text += "Источники:\n\n"

                for item in results[:10]:
                    title = item.get("title", "")
                    content = item.get("content", "")
                    result_url = item.get("url", "")

                    text += (
                        f"🔹 {title}\n"
                        f"{content}\n"
                        f"{result_url}\n\n"
                    )

            return text[:6000] if text else "Ничего не найдено."


async def ask_github(query: str) -> str:
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": 5,
    }

    async with ClientSession() as session:
        async with session.get(
            "https://api.github.com/search/repositories",
            headers=headers,
            params=params,
            timeout=60
        ) as response:

            data = await safe_json_response(response)

            if response.status != 200:
                raise RuntimeError(str(data))

            items = data.get("items", [])

            if not items:
                return "GitHub ничего не нашёл."

            text = "🔥 GitHub репозитории:\n\n"

            for repo in items:
                text += (
                    f"📦 {repo.get('full_name', '')}\n"
                    f"⭐ {repo.get('stargazers_count', 0)}\n"
                    f"{repo.get('description', '')}\n"
                    f"{repo.get('html_url', '')}\n\n"
                )

            return text[:5000]


async def ask_render_services():
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json",
    }

    async with ClientSession() as session:
        async with session.get(
            "https://api.render.com/v1/services",
            headers=headers,
            timeout=60
        ) as response:

            data = await safe_json_response(response)

            if response.status != 200:
                raise RuntimeError(str(data))

            if not data:
                return "Render services не найдены."

            text = "☁️ Render Services:\n\n"

            for item in data[:10]:
                service = item.get("service", {})
                details = service.get("serviceDetails", {})

                text += (
                    f"📦 {service.get('name', 'unknown')}\n"
                    f"Тип: {service.get('type', 'unknown')}\n"
                    f"URL: {details.get('url', 'нет')}\n"
                    f"Создан: {service.get('createdAt', '')}\n\n"
                )

            return text[:5000]


def needs_search(text: str) -> bool:
    lower = text.lower()

    words = [
        "найди",
        "поиск",
        "новости",
        "актуально",
        "latest",
        "search",
        "find",
        "today",
        "сегодня",
        "2026",
        "documentation",
        "docs",
    ]

    return any(word in lower for word in words)


def needs_github(text: str) -> bool:
    lower = text.lower()

    words = [
        "github",
        "repo",
        "repository",
        "репозиторий",
        "git",
    ]

    return any(word in lower for word in words)


async def ask_aion(prompt: str) -> str:
    errors = []

    if GITHUB_TOKEN and needs_github(prompt):
        try:
            return await ask_github(prompt)
        except Exception as e:
            errors.append(f"GitHub: {e}")

    if TAVILY_API_KEY and needs_search(prompt):
        try:
            search_result = await ask_tavily(prompt)

            prompt = (
                "Используй актуальные интернет-данные.\n\n"
                f"{search_result}\n\n"
                f"Запрос пользователя:\n{prompt}"
            )

        except Exception as e:
            errors.append(f"Tavily: {e}")

    providers = [
        ("Groq", GROQ_API_KEY, ask_groq),
        ("Gemini", GEMINI_API_KEY, ask_gemini),
        ("OpenRouter", OPENROUTER_API_KEY, ask_openrouter),
        ("Cerebras", CEREBRAS_API_KEY, ask_cerebras),
    ]

    for name, key, func in providers:
        if not key:
            continue

        try:
            return await func(prompt)
        except Exception as e:
            errors.append(f"{name}: {e}")

    return "⚠️ AI временно недоступен.\n\n" + "\n".join(errors)


def sync_ask_gemini_vision(image_bytes: bytes, prompt: str) -> str:
    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel("gemini-2.0-flash")

    response = model.generate_content([
        prompt,
        {
            "mime_type": "image/jpeg",
            "data": image_bytes
        }
    ])

    return getattr(response, "text", "") or "Не удалось проанализировать фото."


async def analyze_photo(message: types.Message, bot: Bot):
    if not GEMINI_API_KEY:
        await message.answer("⚠️ GEMINI_API_KEY отсутствует.")
        return

    user_id = message.from_user.id
    photo = message.photo[-1]

    image_bytes = await download_telegram_file(
        bot,
        photo.file_id
    )

    caption = (
        message.caption
        or
        "Опиши изображение и помоги пользователю."
    )

    prompt = (
        build_profile_context(user_id)
        + "\n\n"
        + "Пользователь отправил изображение.\n"
        + f"Запрос к фото:\n{caption}"
    )

    wait = await message.answer("🧠 Анализирую фото...")

    try:
        answer = await asyncio.to_thread(
            sync_ask_gemini_vision,
            image_bytes,
            prompt
        )

        save_memory(user_id, "user", "[photo] " + caption)
        save_memory(user_id, "assistant", answer)

        await wait.delete()
        await send_long(message, answer)

    except Exception as e:
        await wait.edit_text(f"⚠️ Ошибка фото:\n{e}")


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if not save_user(message):
        await message.answer(
            "⚠️ Лимит пользователей AION_MATRIX достигнут.\n"
            "Сейчас система рассчитана на 150 пользователей."
        )
        return

    await message.answer(
        "🌍 Выберите язык / Choose language:",
        reply_markup=language_keyboard()
    )


@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def language_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    language = callback.data.replace("lang_", "")

    set_user_language(user_id, language)

    hello = LANGUAGES.get(language, LANGUAGES["ru"])["hello"]

    await callback.message.edit_text(hello)
    await callback.answer()


@dp.message(Command("memory"))
async def memory_handler(message: types.Message):
    user_id = message.from_user.id

    memory = get_memory(user_id)
    long_memory = get_long_memory(user_id)

    text = (
        "🧠 MEMORY\n\n"
        f"Profile:\n{build_profile_context(user_id)}\n\n"
        f"Long memory:\n{long_memory or 'Пусто'}\n\n"
        f"Short memory:\n{memory or 'Пусто'}"
    )

    await send_long(message, text)


@dp.message(Command("clear"))
async def clear_handler(message: types.Message):
    clear_memory(message.from_user.id)
    await message.answer("🧹 Короткая память очищена.")


@dp.message(Command("clearall"))
async def clearall_handler(message: types.Message):
    clear_memory(message.from_user.id)
    clear_long_memory(message.from_user.id)
    await message.answer("🧹 Вся память очищена.")


@dp.message(Command("remember"))
async def remember_handler(message: types.Message):
    fact = message.text.replace("/remember", "", 1).strip()

    if not fact:
        await message.answer("Напишите факт после /remember")
        return

    save_long_memory(message.from_user.id, fact)
    await message.answer("✅ Запомнил.")


@dp.message(Command("status"))
async def status_handler(message: types.Message):
    text = (
        "🧠 AION STATUS\n\n"
        f"Groq: {'✅' if GROQ_API_KEY else '❌'}\n"
        f"Gemini: {'✅' if GEMINI_API_KEY else '❌'}\n"
        f"OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}\n"
        f"Cerebras: {'✅' if CEREBRAS_API_KEY else '❌'}\n"
        f"Tavily Search: {'✅' if TAVILY_API_KEY else '❌'}\n"
        f"GitHub API: {'✅' if GITHUB_TOKEN else '❌'}\n"
        f"Render API: {'✅' if RENDER_API_KEY else '❌'}\n"
        "Memory: ✅ SQLite\n"
        "Photo Vision: ✅ Gemini\n"
        "Voice Receive: ✅ Basic\n"
    )

    await message.answer(text)


@dp.message(Command("language"))
async def language_handler(message: types.Message):
    await message.answer(
        "🌍 Выберите язык / Choose language:",
        reply_markup=language_keyboard()
    )


@dp.message(Command("search"))
async def search_handler(message: types.Message):
    query = message.text.replace("/search", "", 1).strip()

    if not query:
        await message.answer("Напишите запрос после /search")
        return

    wait = await message.answer("🌐 Ищу в интернете...")

    try:
        result = await ask_tavily(query)
        await wait.delete()
        await send_long(message, result)

    except Exception as e:
        await wait.edit_text(f"⚠️ Ошибка поиска:\n{e}")


@dp.message(Command("github"))
async def github_handler(message: types.Message):
    query = message.text.replace("/github", "", 1).strip()

    if not query:
        await message.answer("Напишите запрос после /github")
        return

    wait = await message.answer("💻 Ищу на GitHub...")

    try:
        result = await ask_github(query)
        await wait.delete()
        await send_long(message, result)

    except Exception as e:
        await wait.edit_text(f"⚠️ Ошибка GitHub:\n{e}")


@dp.message(Command("render"))
async def render_handler(message: types.Message):
    wait = await message.answer("☁️ Проверяю Render...")

    try:
        result = await ask_render_services()
        await wait.delete()
        await send_long(message, result)

    except Exception as e:
        await wait.edit_text(f"⚠️ Ошибка Render:\n{e}")


@dp.message(lambda m: m.photo)
async def photo_handler(message: types.Message, bot: Bot):
    await analyze_photo(message, bot)


@dp.message(lambda m: m.voice)
async def voice_handler(message: types.Message):
    await message.answer(
        "🎙️ Голосовое сообщение получено.\n"
        "Распознавание речи добавим следующим модулем."
    )


@dp.message()
async def ai_chat(message: types.Message):
    if not message.text:
        return

    if not save_user(message):
        await message.answer(
            "⚠️ Лимит пользователей AION_MATRIX достигнут.\n"
            "Сейчас система рассчитана на 150 пользователей."
        )
        return

    user_id = message.from_user.id
    user_text = message.text.strip()

    extracted_name = extract_name(user_text)

    if extracted_name:
        set_user_name(user_id, extracted_name)

        detected_gender = detect_gender(user_text, extracted_name)

        if detected_gender != "unknown":
            set_user_gender(user_id, detected_gender)

        await message.answer(f"✅ Запомнил. Вас зовут {extracted_name}.")
        return

    detected_gender = detect_gender(user_text)

    if get_user_gender(user_id) == "unknown" and detected_gender != "unknown":
        set_user_gender(user_id, detected_gender)

    if is_name_question(user_text):
        saved_name = get_user_name(user_id)

        if saved_name:
            h = honorific(user_id)
            prefix = f"{h.title()}, " if h else ""
            await message.answer(f"{prefix}вас зовут {saved_name}.")
        else:
            await message.answer(tr(user_id, "unknown_name"))

        return

    if is_creator_question(user_text):
        await message.answer(
            "Мой создатель — Золотарьов Роман Романович.\n"
            "Проект: AION_MATRIX."
        )
        return

    save_memory(user_id, "user", user_text)

    prompt = build_prompt(user_id, user_text)

    wait = await message.answer(tr(user_id, "thinking"))

    try:
        answer = await ask_aion(prompt)

        save_memory(user_id, "assistant", answer)

        await wait.delete()
        await send_long(message, answer)

    except Exception as e:
        await wait.edit_text(f"⚠️ Ошибка AI:\n{e}")


HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AION MATRIX</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            background: #050816;
            color: white;
            font-family: Arial, sans-serif;
            padding: 40px;
        }
        .card {
            background: #111827;
            padding: 24px;
            border-radius: 16px;
            border: 1px solid #22d3ee;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 AION MATRIX</h1>
        <p>AI system online.</p>
        <p>Telegram bot + Multi-Brain AI + SQLite Memory.</p>
    </div>
</body>
</html>
"""


async def home(request):
    return web.Response(text=HTML, content_type="text/html")


async def web_status(request):
    data = {
        "name": "AION_MATRIX",
        "status": "online",
        "brains": {
            "groq": bool(GROQ_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "openrouter": bool(OPENROUTER_API_KEY),
            "cerebras": bool(CEREBRAS_API_KEY),
        },
        "tools": {
            "tavily": bool(TAVILY_API_KEY),
            "github": bool(GITHUB_TOKEN),
            "render": bool(RENDER_API_KEY),
            "memory": True,
            "vision": bool(GEMINI_API_KEY),
            "voice_receive": True,
        }
    }

    return web.Response(
        text=json.dumps(data, ensure_ascii=False, indent=2),
        content_type="application/json"
    )


async def start_web():
    app = web.Application()

    app.router.add_get("/", home)
    app.router.add_get("/status", web_status)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print(f"🌐 Web started on port {PORT}")


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing")

    if not any([
        GROQ_API_KEY,
        GEMINI_API_KEY,
        OPENROUTER_API_KEY,
        CEREBRAS_API_KEY
    ]):
        raise RuntimeError("No AI keys found")

    init_db()

    await start_web()

    bot = Bot(token=BOT_TOKEN)

    print("🚀 AION MATRIX ONLINE")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
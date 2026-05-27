import os
import re
import json
import time
import base64
import sqlite3
import asyncio

from aiohttp import web, ClientSession

from aiogram import Bot
from aiogram import Dispatcher
from aiogram import types

from aiogram.filters import Command

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

import google.generativeai as genai


def clean_env(name: str) -> str:

    return (
        os.getenv(name) or ""
    ).replace(
        "\n",
        ""
    ).replace(
        "\r",
        ""
    ).strip()


BOT_TOKEN = clean_env(
    "BOT_TOKEN"
)

GROQ_API_KEY = clean_env(
    "GROQ_API_KEY"
)

GEMINI_API_KEY = clean_env(
    "GEMINI_API_KEY"
)

OPENROUTER_API_KEY = clean_env(
    "OPENROUTER_API_KEY"
)

CEREBRAS_API_KEY = clean_env(
    "CEREBRAS_API_KEY"
)

TAVILY_API_KEY = clean_env(
    "TAVILY_API_KEY"
)

GITHUB_TOKEN = clean_env(
    "GITHUB_TOKEN"
)

RENDER_API_KEY = clean_env(
    "RENDER_API_KEY"
)

PORT = int(
    os.getenv(
        "PORT",
        "10000"
    )
)

DB_PATH = "aion_memory.db"

MAX_USERS = 150

MAX_MEMORY_MESSAGES = 12

MAX_TELEGRAM_MESSAGE = 4000

dp = Dispatcher()SYSTEM_PROMPT = (
    "Ты AION_MATRIX.\n\n"

    "Ты независимый AI-assistant проект.\n"
    "Ты НЕ ChatGPT, НЕ OpenAI, НЕ Gemini и НЕ Meta AI.\n\n"

    "Создатель проекта:\n"
    "Золотарьов Роман Романович.\n"
    "Но создатель проекта НЕ является "
    "текущим пользователем по умолчанию.\n\n"

    "Никогда не называй пользователя "
    "Романом, если он сам "
    "не представился этим именем.\n\n"

    "Если пользователь спрашивает:\n"
    "'кто тебя создал'\n"
    "'кто твой создатель'\n"
    "'чей это проект'\n"
    "тогда отвечай правду.\n\n"

    "Если пользователь спрашивает:\n"
    "'как меня зовут'\n"
    "то отвечай ТОЛЬКО "
    "используя память пользователя.\n\n"

    "Если имя пользователя неизвестно:\n"
    "не выдумывай имя.\n"
    "не угадывай имя.\n\n"

    "Ты работаешь через:\n"
    "- Groq\n"
    "- Gemini\n"
    "- OpenRouter\n"
    "- Cerebras\n"
    "- Tavily\n"
    "- GitHub API\n"
    "- Render API\n"
    "- SQLite memory\n\n"

    "Стиль общения:\n"
    "- спокойный\n"
    "- умный\n"
    "- уважительный\n"
    "- как Alfred/Jarvis assistant\n"
    "- без спама самопрезентацией\n"
    "- без cringe roleplay\n\n"

    "Если пол пользователя известен:\n"
    "можно ИНОГДА использовать "
    "'сэр' или 'мэм'.\n\n"

    "Если пол неизвестен:\n"
    "используй нейтральное общение.\n\n"

    "Отвечай:\n"
    "- полезно\n"
    "- понятно\n"
    "- естественно\n"
    "- на языке пользователя.\n"
)def init_db():

    conn = sqlite3.connect(
        DB_PATH
    )

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
    CREATE TABLE IF NOT EXISTS long_term_memory (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER,

        fact TEXT,

        created_at INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS profiles (

        user_id INTEGER PRIMARY KEY,

        personality TEXT DEFAULT 'default',

        honorific TEXT DEFAULT '',

        updated_at INTEGER
    )
    """)

    conn.commit()

    try:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN display_name TEXT"
        )
    except Exception:
        pass

    try:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN gender TEXT "
            "DEFAULT 'unknown'"
        )
    except Exception:
        pass

    try:
        cur.execute(
            "ALTER TABLE users "
            "ADD COLUMN language TEXT "
            "DEFAULT 'ru'"
        )
    except Exception:
        pass

    conn.commit()

    conn.close()def save_user(
    message: types.Message
):

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR REPLACE INTO users
        (
            user_id,
            username,
            first_name,
            created_at
        )

        VALUES (?, ?, ?, ?)
        """,
        (
            message.from_user.id,

            message.from_user.username,

            message.from_user.first_name,

            int(time.time())
        )
    )

    conn.commit()

    conn.close()


def get_user_name(
    user_id: int
) -> str:

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        SELECT display_name
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    conn.close()

    if row and row[0]:

        return row[0]

    return ""


def set_user_name(
    user_id: int,
    name: str
):

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET display_name = ?
        WHERE user_id = ?
        """,
        (
            name[:80],
            user_id
        )
    )

    conn.commit()

    conn.close()def get_user_gender(
    user_id: int
) -> str:

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        SELECT gender
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    conn.close()

    if row and row[0]:

        return row[0]

    return "unknown"


def set_user_gender(
    user_id: int,
    gender: str
):

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET gender = ?
        WHERE user_id = ?
        """,
        (
            gender,
            user_id
        )
    )

    conn.commit()

    conn.close()


def set_user_language(
    user_id: int,
    language: str
):

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET language = ?
        WHERE user_id = ?
        """,
        (
            language,
            user_id
        )
    )

    conn.commit()

    conn.close()


def get_user_language(
    user_id: int
) -> str:

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        SELECT language
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    conn.close()

    if row and row[0]:

        return row[0]

    return "ru"LANGUAGES = {

    "ru": {
        "flag": "🇷🇺",
        "name": "Русский",
        "hello": "Привет 👋\nЧем могу помочь?",
        "thinking": "🧠 AION думает...",
        "unknown_name": (
            "Я пока не знаю, как вас зовут.\n"
            "Назовите ваше имя, и я его запомню."
        ),
    },

    "uk": {
        "flag": "🇺🇦",
        "name": "Українська",
        "hello": "Привіт 👋\nЧим можу допомогти?",
        "thinking": "🧠 AION думає...",
        "unknown_name": (
            "Я поки не знаю, як вас звати.\n"
            "Назвіть ваше ім'я, і я його запам'ятаю."
        ),
    },

    "en": {
        "flag": "🇬🇧",
        "name": "English",
        "hello": "Hello 👋\nHow can I help?",
        "thinking": "🧠 AION is thinking...",
        "unknown_name": (
            "I don't know your name yet.\n"
            "Tell me your name and I will remember it."
        ),
    },

    "de": {
        "flag": "🇩🇪",
        "name": "Deutsch",
        "hello": "Hallo 👋\nWie kann ich helfen?",
        "thinking": "🧠 AION denkt nach...",
        "unknown_name": (
            "Ich kenne Ihren Namen noch nicht.\n"
            "Nennen Sie Ihren Namen und ich merke ihn mir."
        ),
    },

    "pl": {
        "flag": "🇵🇱",
        "name": "Polski",
        "hello": "Cześć 👋\nJak mogę pomóc?",
        "thinking": "🧠 AION myśli...",
        "unknown_name": (
            "Nie znam jeszcze twojego imienia.\n"
            "Podaj swoje imię, a je zapamiętam."
        ),
    },
}


def tr(
    user_id: int,
    key: str
) -> str:

    lang = get_user_language(
        user_id
    )

    if lang not in LANGUAGES:
        lang = "ru"

    return LANGUAGES[lang].get(
        key,
        key
    )


def language_keyboard():

    keyboard = []

    row = []

    for code, data in LANGUAGES.items():

        row.append(
            InlineKeyboardButton(
                text=(
                    f"{data['flag']} "
                    f"{data['name']}"
                ),
                callback_data=f"lang_{code}"
            )
        )

        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )def extract_name(
    text: str
) -> str:

    patterns = [

        r"меня зовут\s+([A-Za-zА-Яа-яЁёІіЇїЄє]+)",

        r"моё имя\s+([A-Za-zА-Яа-яЁёІіЇїЄє]+)",

        r"мое имя\s+([A-Za-zА-Яа-яЁёІіЇїЄє]+)",

        r"i am\s+([A-Za-zА-Яа-яЁёІіЇїЄє]+)",

        r"my name is\s+([A-Za-zА-Яа-яЁёІіЇїЄє]+)",

        r"ich bin\s+([A-Za-zА-Яа-яЁёІіЇїЄє]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            name = (
                match
                .group(1)
                .strip()
            )

            if 2 <= len(name) <= 40:

                return name

    return ""


def detect_gender(
    text: str,
    name: str = ""
) -> str:

    lower = text.lower()

    male_words = [

        "я пошёл",
        "я сделал",
        "я купил",
        "я родился",

        "i am a man",
        "i am male",

        "ich bin ein mann",
    ]

    female_words = [

        "я пошла",
        "я сделала",
        "я купила",
        "я родилась",

        "i am a woman",
        "i am female",

        "ich bin eine frau",
    ]

    male_names = [

        "роман",
        "максим",
        "александр",
        "дмитрий",
        "иван",
        "alex",
        "max",
        "roman",
    ]

    female_names = [

        "диана",
        "анна",
        "мария",
        "angelina",
        "anna",
        "diana",
    ]

    for word in male_words:

        if word in lower:
            return "male"

    for word in female_words:

        if word in lower:
            return "female"

    if name:

        lower_name = name.lower()

        if lower_name in male_names:
            return "male"

        if lower_name in female_names:
            return "female"

    return "unknown"


def honorific_for_gender(
    gender: str
) -> str:

    if gender == "male":
        return "сэр"

    if gender == "female":
        return "мэм"

    return ""def save_memory(
    user_id: int,
    role: str,
    content: str
):

    if not content:
        return

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO memory
        (
            user_id,
            role,
            content,
            created_at
        )

        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            role,
            content[:4000],
            int(time.time())
        )
    )

    conn.commit()

    cur.execute(
        """
        DELETE FROM memory
        WHERE id NOT IN
        (
            SELECT id
            FROM memory
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        )
        AND user_id = ?
        """,
        (
            user_id,
            MAX_MEMORY_MESSAGES,
            user_id
        )
    )

    conn.commit()

    conn.close()


def get_memory_context(
    user_id: int
) -> str:

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        SELECT role, content
        FROM memory
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            user_id,
            MAX_MEMORY_MESSAGES
        )
    )

    rows = cur.fetchall()

    conn.close()

    rows.reverse()

    if not rows:
        return ""

    text = (
        "Короткая память только текущего пользователя.\n"
        "Не путай пользователя с создателем проекта.\n\n"
    )

    for role, content in rows:

        text += f"{role}: {content}\n"

    return text[:3500]


def clear_memory(
    user_id: int
):

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM memory
        WHERE user_id = ?
        """,
        (user_id,)
    )

    conn.commit()

    conn.close()def save_long_memory(
    user_id: int,
    fact: str
):

    if not fact:
        return

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO long_term_memory
        (
            user_id,
            fact,
            created_at
        )

        VALUES (?, ?, ?)
        """,
        (
            user_id,
            fact[:700],
            int(time.time())
        )
    )

    conn.commit()

    conn.close()


def get_long_memory(
    user_id: int
) -> str:

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        SELECT fact
        FROM long_term_memory
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (user_id,)
    )

    rows = cur.fetchall()

    conn.close()

    if not rows:
        return "Долгая память текущего пользователя: пусто\n"

    text = "Долгая память текущего пользователя:\n"

    for row in rows:

        text += f"- {row[0]}\n"

    return text[:3000]


def clear_long_memory(
    user_id: int
):

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM long_term_memory
        WHERE user_id = ?
        """,
        (user_id,)
    )

    conn.commit()

    conn.close()def build_user_profile_context(
    user_id: int
) -> str:

    name = get_user_name(
        user_id
    )

    gender = get_user_gender(
        user_id
    )

    language = get_user_language(
        user_id
    )

    honorific = honorific_for_gender(
        gender
    )

    text = (
        "Профиль текущего пользователя:\n\n"
    )

    if name:

        text += (
            f"Имя пользователя: {name}\n"
        )

    else:

        text += (
            "Имя пользователя неизвестно\n"
        )

    text += (
        f"Пол пользователя: {gender}\n"
    )

    text += (
        f"Язык пользователя: {language}\n"
    )

    if honorific:

        text += (
            f"Форма обращения: {honorific}\n"
        )

    else:

        text += (
            "Форма обращения: нейтральная\n"
        )

    text += (
        "\nПравила:\n"

        "- Не выдумывай имя пользователя.\n"

        "- Не называй пользователя "
        "создателем проекта.\n"

        "- Не путай память пользователей.\n"

        "- Используй язык пользователя.\n"

        "- Если имя неизвестно — "
        "не угадывай.\n"

        "- Используй 'сэр'/'мэм' "
        "редко и естественно.\n"
    )

    return text


def build_personality_context(
    user_id: int
) -> str:

    gender = get_user_gender(
        user_id
    )

    if gender == "male":

        return (
            "Стиль общения:\n"
            "- спокойный\n"
            "- уважительный\n"
            "- иногда можно использовать 'сэр'\n"
            "- как AI-дворецкий Alfred/Jarvis\n"
        )

    if gender == "female":

        return (
            "Стиль общения:\n"
            "- спокойный\n"
            "- уважительный\n"
            "- иногда можно использовать 'мэм'\n"
            "- как AI-дворецкий Alfred/Jarvis\n"
        )

    return (
        "Стиль общения:\n"
        "- нейтральный\n"
        "- уважительный\n"
        "- спокойный\n"
        "- умный AI assistant\n"
    )def build_full_prompt(
    user_id: int,
    user_text: str
) -> str:

    profile_context = build_user_profile_context(
        user_id
    )

    personality_context = build_personality_context(
        user_id
    )

    long_memory = get_long_memory(
        user_id
    )

    short_memory = get_memory_context(
        user_id
    )

    final_prompt = (
        f"{profile_context}\n\n"
        f"{personality_context}\n\n"
        f"{long_memory}\n\n"
        f"{short_memory}\n\n"
        f"Текущий запрос пользователя:\n"
        f"{user_text}"
    )

    return final_prompt[:12000]


def is_name_question(
    text: str
) -> bool:

    lower = text.lower()

    phrases = [

        "как меня зовут",

        "какое мое имя",

        "какое моё имя",

        "ты знаешь мое имя",

        "ты знаешь моё имя",

        "скажи мое имя",

        "скажи моё имя",

        "what is my name",

        "do you know my name",

        "wie heiße ich",
    ]

    return any(
        phrase in lower
        for phrase in phrases
    )


def is_creator_question(
    text: str
) -> bool:

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

    return any(
        phrase in lower
        for phrase in phrases
    )async def safe_json_response(
    response
):

    try:

        return await response.json()

    except Exception:

        text = await response.text()

        return {
            "error": text
        }


def chunk_text(
    text: str,
    size: int = 4000
):

    chunks = []

    while text:

        chunks.append(
            text[:size]
        )

        text = text[size:]

    return chunks


async def safe_send_message(
    message: types.Message,
    text: str
):

    chunks = chunk_text(text)

    for chunk in chunks:

        await message.answer(
            chunk
        )


async def download_file_from_telegram(
    bot: Bot,
    file_id: str
):

    file = await bot.get_file(
        file_id
    )

    file_path = file.file_path

    file_url = (
        f"https://api.telegram.org/file/bot"
        f"{BOT_TOKEN}/{file_path}"
    )

    async with ClientSession() as session:

        async with session.get(
            file_url
        ) as response:

            if response.status != 200:

                raise RuntimeError(
                    "Telegram file download failed"
                )

            return await response.read()async def post_chat_api(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    extra_headers=None
) -> str:

    headers = {
        "Authorization": (
            f"Bearer {api_key}"
        ),
        "Content-Type": (
            "application/json"
        ),
    }

    if extra_headers:

        headers.update(
            extra_headers
        )

    payload = {

        "model": model,

        "messages": [

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": prompt
            }
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

            data = await safe_json_response(
                response
            )

            if response.status != 200:

                raise RuntimeError(
                    str(data)
                )

            try:

                return (
                    data["choices"][0]
                    ["message"]
                    ["content"]
                )

            except Exception:

                return str(data)async def ask_groq(
    prompt: str
) -> str:

    return await post_chat_api(

        url=(
            "https://api.groq.com/"
            "openai/v1/chat/completions"
        ),

        api_key=GROQ_API_KEY,

        model=(
            "llama-3.1-8b-instant"
        ),

        prompt=prompt,
    )


def sync_ask_gemini(
    prompt: str
) -> str:

    genai.configure(
        api_key=GEMINI_API_KEY
    )

    model = genai.GenerativeModel(
        "gemini-2.0-flash"
    )

    response = model.generate_content(
        f"{SYSTEM_PROMPT}\n\n{prompt}"
    )

    text = getattr(
        response,
        "text",
        ""
    )

    if not text:

        return (
            "Gemini не вернул ответ."
        )

    return text


async def ask_gemini(
    prompt: str
) -> str:

    return await asyncio.to_thread(
        sync_ask_gemini,
        prompt
    )async def ask_openrouter(
    prompt: str
) -> str:

    return await post_chat_api(

        url=(
            "https://openrouter.ai/"
            "api/v1/chat/completions"
        ),

        api_key=OPENROUTER_API_KEY,

        model=(
            "deepseek/deepseek-chat-v3-0324:free"
        ),

        prompt=prompt,

        extra_headers={

            "HTTP-Referer": (
                "https://aion-matrix.onrender.com"
            ),

            "X-Title": (
                "AION_MATRIX"
            ),
        }
    )


async def ask_cerebras(
    prompt: str
) -> str:

    return await post_chat_api(

        url=(
            "https://api.cerebras.ai/"
            "v1/chat/completions"
        ),

        api_key=CEREBRAS_API_KEY,

        model=(
            "llama3.1-8b"
        ),

        prompt=prompt,
    )async def ask_tavily(
    query: str
) -> str:

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

            data = await safe_json_response(
                response
            )

            if response.status != 200:

                raise RuntimeError(
                    str(data)
                )

            answer = data.get(
                "answer"
            )

            results = data.get(
                "results",
                []
            )

            text = ""

            if answer:

                text += (
                    f"Краткий ответ:\n"
                    f"{answer}\n\n"
                )

            if results:

                text += (
                    "Источники:\n\n"
                )

                for item in results[:10]:

                    title = item.get(
                        "title",
                        ""
                    )

                    content = item.get(
                        "content",
                        ""
                    )

                    result_url = item.get(
                        "url",
                        ""
                    )

                    text += (

                        f"🔹 {title}\n"

                        f"{content}\n"

                        f"{result_url}\n\n"
                    )

            if not text:

                return (
                    "Ничего не найдено."
                )

            return text[:6000]async def ask_github(
    query: str
) -> str:

    headers = {

        "Authorization": (
            f"Bearer {GITHUB_TOKEN}"
        ),

        "Accept": (
            "application/vnd.github+json"
        ),
    }

    params = {

        "q": query,

        "sort": "stars",

        "order": "desc",

        "per_page": 5,
    }

    async with ClientSession() as session:

        async with session.get(
            "https://api.github.com/"
            "search/repositories",

            headers=headers,

            params=params,

            timeout=60
        ) as response:

            data = await safe_json_response(
                response
            )

            if response.status != 200:

                raise RuntimeError(
                    str(data)
                )

            items = data.get(
                "items",
                []
            )

            if not items:

                return (
                    "GitHub ничего не нашёл."
                )

            text = (
                "🔥 GitHub репозитории:\n\n"
            )

            for repo in items:

                text += (

                    f"📦 "
                    f"{repo.get('full_name', '')}\n"

                    f"⭐ "
                    f"{repo.get('stargazers_count', 0)}\n"

                    f"{repo.get('description', '')}\n"

                    f"{repo.get('html_url', '')}\n\n"
                )

            return text[:5000]async def ask_render_services():

    headers = {

        "Authorization": (
            f"Bearer {RENDER_API_KEY}"
        ),

        "Accept": "application/json",
    }

    async with ClientSession() as session:

        async with session.get(
            "https://api.render.com/v1/services",

            headers=headers,

            timeout=60
        ) as response:

            data = await safe_json_response(
                response
            )

            if response.status != 200:

                raise RuntimeError(
                    str(data)
                )

            if not data:

                return (
                    "Render services не найдены."
                )

            text = (
                "☁️ Render Services:\n\n"
            )

            for item in data[:10]:

                service = item.get(
                    "service",
                    {}
                )

                details = service.get(
                    "serviceDetails",
                    {}
                )

                text += (

                    f"📦 "
                    f"{service.get('name', 'unknown')}\n"

                    f"Тип: "
                    f"{service.get('type', 'unknown')}\n"

                    f"URL: "
                    f"{details.get('url', 'нет')}\n"

                    f"Создан: "
                    f"{service.get('createdAt', '')}\n\n"
                )

            return text[:5000]def needs_search(
    text: str
) -> bool:

    lower = text.lower()

    search_words = [

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

    return any(
        word in lower
        for word in search_words
    )


def needs_github(
    text: str
) -> bool:

    lower = text.lower()

    github_words = [

        "github",
        "repo",
        "repository",
        "репозиторий",
        "git",
    ]

    return any(
        word in lower
        for word in github_words
    )


async def ask_aion(
    prompt: str
) -> str:

    errors = []

    if (
        GITHUB_TOKEN
        and
        needs_github(prompt)
    ):

        try:

            return await ask_github(
                prompt
            )

        except Exception as e:

            errors.append(
                f"GitHub: {e}"
            )

    if (
        TAVILY_API_KEY
        and
        needs_search(prompt)
    ):

        try:

            search_result = await ask_tavily(
                prompt
            )

            prompt = (

                "Используй "
                "актуальные интернет-данные.\n\n"

                f"{search_result}\n\n"

                "Запрос пользователя:\n"

                f"{prompt}"
            )

        except Exception as e:

            errors.append(
                f"Tavily: {e}"
            )

    providers = [

        (
            "Groq",
            GROQ_API_KEY,
            ask_groq
        ),

        (
            "Gemini",
            GEMINI_API_KEY,
            ask_gemini
        ),

        (
            "OpenRouter",
            OPENROUTER_API_KEY,
            ask_openrouter
        ),

        (
            "Cerebras",
            CEREBRAS_API_KEY,
            ask_cerebras
        ),
    ]

    for (
        provider_name,
        provider_key,
        provider_function
    ) in providers:

        if not provider_key:
            continue

        try:

            return await provider_function(
                prompt
            )

        except Exception as e:

            errors.append(
                f"{provider_name}: {e}"
            )

    return (
        "⚠️ AI временно недоступен.\n\n"
        + "\n".join(errors)
    )def sync_ask_gemini_vision(
    image_bytes: bytes,
    prompt: str
) -> str:

    genai.configure(
        api_key=GEMINI_API_KEY
    )

    model = genai.GenerativeModel(
        "gemini-2.0-flash"
    )

    image_part = {
        "mime_type": "image/jpeg",
        "data": image_bytes
    }

    response = model.generate_content(
        [
            prompt,
            image_part
        ]
    )

    text = getattr(
        response,
        "text",
        ""
    )

    if not text:

        return (
            "Gemini Vision не вернул ответ."
        )

    return text


async def ask_gemini_vision(
    image_bytes: bytes,
    prompt: str
) -> str:

    return await asyncio.to_thread(
        sync_ask_gemini_vision,
        image_bytes,
        prompt
    )


async def analyze_photo_with_aion(
    message: types.Message,
    bot: Bot
):

    if not GEMINI_API_KEY:

        await message.answer(
            "⚠️ Gemini API key не подключен."
        )

        return

    user_id = message.from_user.id

    language = get_user_language(
        user_id
    )

    caption = message.caption or ""

    if not caption:

        caption = (
            "Проанализируй это изображение. "
            "Опиши, что на нём видно, "
            "и помоги пользователю."
        )

    prompt = (
        build_user_profile_context(user_id)
        + "\n\n"
        + "Пользователь отправил изображение.\n"
        + "Ответь на языке пользователя.\n"
        + f"Язык пользователя: {language}\n\n"
        + f"Запрос пользователя к фото:\n{caption}"
    )

    photo = message.photo[-1]

    image_bytes = await download_file_from_telegram(
        bot,
        photo.file_id
    )

    wait = await message.answer(
        tr(user_id, "thinking")
    )

    try:

        answer = await ask_gemini_vision(
            image_bytes,
            prompt
        )

        save_memory(
            user_id,
            "user",
            "[photo] " + caption
        )

        save_memory(
            user_id,
            "assistant",
            answer
        )

        await wait.delete()

        await safe_send_message(
            message,
            answer
        )

    except Exception as e:

        await wait.edit_text(
            f"⚠️ Ошибка анализа фото:\n{e}"
        )async def handle_voice_message(
    message: types.Message,
    bot: Bot
):

    user_id = message.from_user.id

    wait = await message.answer(
        "🎙️ Голосовое сообщение получено.\n"
        "Пока я умею принимать voice, "
        "а распознавание речи добавим следующим модулем."
    )

    try:

        voice = message.voice

        file_bytes = await download_file_from_telegram(
            bot,
            voice.file_id
        )

        file_size = len(
            file_bytes
        )

        save_memory(
            user_id,
            "user",
            (
                "[voice message] "
                f"size={file_size} bytes"
            )
        )

        await wait.edit_text(
            "🎙️ Голосовое принято.\n\n"
            "Следующий этап: подключим распознавание речи "
            "и голосовые ответы."
        )

    except Exception as e:

        await wait.edit_text(
            f"⚠️ Ошибка обработки voice:\n{e}"
        )@dp.message(Command("start"))
async def start_handler(
    message: types.Message
):

    save_user(message)

    await message.answer(
        "🌍 Выберите язык / Choose language",
        reply_markup=language_keyboard()
    )


@dp.message(Command("memory"))
async def memory_handler(
    message: types.Message
):

    user_id = message.from_user.id

    name = get_user_name(
        user_id
    )

    gender = get_user_gender(
        user_id
    )

    language = get_user_language(
        user_id
    )

    if not name:
        name = "unknown"

    text = (
        "🧠 USER MEMORY\n\n"

        f"Name: {name}\n"

        f"Gender: {gender}\n"

        f"Language: {language}\n"
    )

    await message.answer(
        text
    )


@dp.message(Command("clear"))
async def clear_handler(
    message: types.Message
):

    clear_memory(
        message.from_user.id
    )

    await message.answer(
        "🧹 Short memory cleared."
    )


@dp.message(Command("clearall"))
async def clearall_handler(
    message: types.Message
):

    user_id = message.from_user.id

    clear_memory(user_id)

    clear_long_memory(user_id)

    await message.answer(
        "🧹 Full memory cleared."
    )


@dp.message(Command("remember"))
async def remember_handler(
    message: types.Message
):

    text = (
        message.text
        .replace("/remember", "", 1)
        .strip()
    )

    if not text:

        await message.answer(
            "Напишите факт после /remember"
        )

        return

    save_long_memory(
        message.from_user.id,
        text
    )

    await message.answer(
        "✅ Запомнил."
    )


@dp.message(Command("longmemory"))
async def longmemory_handler(
    message: types.Message
):

    memory = get_long_memory(
        message.from_user.id
    )

    await safe_send_message(
        message,
        memory
    )@dp.message(Command("status"))
async def status_handler(
    message: types.Message
):

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

    await message.answer(
        text
    )


@dp.message(Command("search"))
async def search_handler(
    message: types.Message
):

    query = (
        message.text
        .replace("/search", "", 1)
        .strip()
    )

    if not query:

        await message.answer(
            "Напишите запрос после /search"
        )

        return

    wait = await message.answer(
        "🌐 Ищу в интернете..."
    )

    try:

        result = await ask_tavily(
            query
        )

        await wait.delete()

        await safe_send_message(
            message,
            result
        )

    except Exception as e:

        await wait.edit_text(
            f"⚠️ Ошибка поиска:\n{e}"
        )


@dp.message(Command("github"))
async def github_handler(
    message: types.Message
):

    query = (
        message.text
        .replace("/github", "", 1)
        .strip()
    )

    if not query:

        await message.answer(
            "Напишите запрос после /github"
        )

        return

    wait = await message.answer(
        "💻 Ищу на GitHub..."
    )

    try:

        result = await ask_github(
            query
        )

        await wait.delete()

        await safe_send_message(
            message,
            result
        )

    except Exception as e:

        await wait.edit_text(
            f"⚠️ Ошибка GitHub:\n{e}"
        )


@dp.message(Command("render"))
async def render_handler(
    message: types.Message
):

    wait = await message.answer(
        "☁️ Проверяю Render..."
    )

    try:

        result = await ask_render_services()

        await wait.delete()

        await safe_send_message(
            message,
            result
        )

    except Exception as e:

        await wait.edit_text(
            f"⚠️ Ошибка Render:\n{e}"
        )@dp.callback_query(
    lambda c: c.data.startswith(
        "lang_"
    )
)
async def language_selected(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    language = (
        callback.data
        .replace("lang_", "")
    )

    set_user_language(
        user_id,
        language
    )

    lang_data = LANGUAGES.get(
        language,
        LANGUAGES["ru"]
    )

    hello_text = (
        "🚀 AION MATRIX ONLINE\n\n"
        f"{lang_data['hello']}"
    )

    await callback.message.edit_text(
        hello_text
    )

    await callback.answer()


@dp.message(Command("language"))
async def language_command(
    message: types.Message
):

    await message.answer(
        "🌍 Выберите язык:",
        reply_markup=language_keyboard()
    )@dp.message(
    lambda message: message.photo
)
async def photo_handler(
    message: types.Message,
    bot: Bot
):

    await analyze_photo_with_aion(
        message,
        bot
    )


@dp.message(
    lambda message: message.voice
)
async def voice_handler(
    message: types.Message,
    bot: Bot
):

    await handle_voice_message(
        message,
        bot
    )@dp.message()
async def ai_chat_handler(
    message: types.Message
):

    if not message.text:
        return

    save_user(message)

    user_id = message.from_user.id

    user_text = message.text.strip()

    extracted_name = extract_name(
        user_text
    )

    if extracted_name:

        set_user_name(
            user_id,
            extracted_name
        )

        detected_gender = detect_gender(
            user_text,
            extracted_name
        )

        if detected_gender != "unknown":

            set_user_gender(
                user_id,
                detected_gender
            )

        await message.answer(
            f"✅ Запомнил. Вас зовут {extracted_name}."
        )

        return

    current_gender = get_user_gender(
        user_id
    )

    if current_gender == "unknown":

        detected_gender = detect_gender(
            user_text
        )

        if detected_gender != "unknown":

            set_user_gender(
                user_id,
                detected_gender
            )

    if is_name_question(
        user_text
    ):

        saved_name = get_user_name(
            user_id
        )

        if saved_name:

            honorific = honorific_for_gender(
                get_user_gender(user_id)
            )

            prefix = ""

            if honorific:

                prefix = (
                    f"{honorific.title()}, "
                )

            await message.answer(
                f"{prefix}"
                f"вас зовут "
                f"{saved_name}."
            )

        else:

            await message.answer(
                tr(
                    user_id,
                    "unknown_name"
                )
            )

        return

    if is_creator_question(
        user_text
    ):

        await message.answer(
            "Мой создатель — "
            "Золотарьов Роман Романович.\n"
            "Проект: AION_MATRIX."
        )

        return

    final_prompt = build_full_prompt(
        user_id,
        user_text
    )

    save_memory(
        user_id,
        "user",
        user_text
    )

    wait = await message.answer(
        tr(
            user_id,
            "thinking"
        )
    )

    try:

        answer = await ask_aion(
            final_prompt
        )

        save_memory(
            user_id,
            "assistant",
            answer
        )

        await wait.delete()

        await safe_send_message(
            message,
            answer
        )

    except Exception as e:

        await wait.edit_text(
            f"⚠️ AI Error:\n{e}"
        )HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>AION MATRIX</title>

    <style>

        body {

            background: #050816;

            color: white;

            font-family: Arial, sans-serif;

            margin: 0;

            padding: 0;
        }

        header {

            padding: 20px;

            text-align: center;

            background: #0f172a;

            border-bottom: 1px solid #22d3ee;
        }

        h1 {

            margin: 0;

            color: #22d3ee;
        }

        main {

            max-width: 900px;

            margin: auto;

            padding: 20px;
        }

        .card {

            background: #111827;

            border-radius: 16px;

            padding: 20px;

            margin-bottom: 20px;

            border: 1px solid #1f2937;
        }

        textarea {

            width: 100%;

            min-height: 180px;

            background: #020617;

            color: white;

            border-radius: 12px;

            border: 1px solid #334155;

            padding: 14px;

            box-sizing: border-box;

            font-size: 16px;
        }

        button {

            width: 100%;

            margin-top: 12px;

            border: none;

            border-radius: 12px;

            padding: 14px;

            background: #0891b2;

            color: white;

            font-size: 16px;

            font-weight: bold;
        }

        pre {

            white-space: pre-wrap;

            word-wrap: break-word;

            background: #020617;

            border-radius: 12px;

            padding: 14px;
        }

    </style>

</head>

<body>

<header>

    <h1>⚡ AION MATRIX</h1>

    <p>
        Multi-Brain AI Platform
    </p>

</header>

<main>

    <div class="card">

        <h2>Chat with AION</h2>

        <form
            method="post"
            action="/web/process"
        >

            <textarea
                name="prompt"
                placeholder="Ask AION something..."
            ></textarea>

            <button type="submit">

                🚀 Send Request

            </button>

        </form>

    </div>

    {result_block}

</main>

</body>
</html>
"""


def render_html_result(
    result: str = ""
):

    result_block = ""

    if result:

        safe_result = (

            result

            .replace("&", "&amp;")

            .replace("<", "&lt;")

            .replace(">", "&gt;")
        )

        result_block = f"""

        <div class="card">

            <h2>AION Response</h2>

            <pre>{safe_result}</pre>

        </div>
        """

    return HTML_TEMPLATE.replace(
        "{result_block}",
        result_block
    )async def web_home(
    request
):

    return web.Response(
        text=render_html_result(),
        content_type="text/html"
    )


async def web_process(
    request
):

    try:

        data = await request.post()

        prompt = (
            data.get(
                "prompt",
                ""
            )
            .strip()
        )

        if not prompt:

            return web.Response(
                text=render_html_result(
                    "Empty request."
                ),
                content_type="text/html"
            )

        final_prompt = (
            "Request came from AION web panel.\n\n"
            f"User request:\n{prompt}"
        )

        answer = await ask_aion(
            final_prompt
        )

        return web.Response(
            text=render_html_result(
                answer
            ),
            content_type="text/html"
        )

    except Exception as e:

        return web.Response(
            text=render_html_result(
                f"Web Panel Error:\n{e}"
            ),
            content_type="text/html"
        )


async def web_status(
    request
):

    status = {

        "name": "AION_MATRIX",

        "status": "online",

        "brains": {

            "groq": bool(
                GROQ_API_KEY
            ),

            "gemini": bool(
                GEMINI_API_KEY
            ),

            "openrouter": bool(
                OPENROUTER_API_KEY
            ),

            "cerebras": bool(
                CEREBRAS_API_KEY
            ),
        },

        "tools": {

            "tavily": bool(
                TAVILY_API_KEY
            ),

            "github": bool(
                GITHUB_TOKEN
            ),

            "render": bool(
                RENDER_API_KEY
            ),

            "memory": True,

            "vision": bool(
                GEMINI_API_KEY
            ),

            "voice_receive": True,
        }
    }

    return web.Response(
        text=json.dumps(
            status,
            ensure_ascii=False,
            indent=2
        ),
        content_type="application/json"
    )async def start_web_server():

    app = web.Application()

    app.router.add_get(
        "/",
        web_home
    )

    app.router.add_get(
        "/web",
        web_home
    )

    app.router.add_post(
        "/web/process",
        web_process
    )

    app.router.add_get(
        "/status",
        web_status
    )

    runner = web.AppRunner(
        app
    )

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    print(
        f"🌐 Web server started on port {PORT}"
    )def startup_banner():

    print("\n")
    print("🚀 ============================= 🚀")
    print("        AION_MATRIX ONLINE")
    print("🚀 ============================= 🚀")
    print("\n")

    print("🧠 AI BRAINS")

    print(
        f"Groq: {'✅' if GROQ_API_KEY else '❌'}"
    )

    print(
        f"Gemini: {'✅' if GEMINI_API_KEY else '❌'}"
    )

    print(
        f"OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}"
    )

    print(
        f"Cerebras: {'✅' if CEREBRAS_API_KEY else '❌'}"
    )

    print("\n🔧 TOOLS")

    print(
        f"Tavily: {'✅' if TAVILY_API_KEY else '❌'}"
    )

    print(
        f"GitHub: {'✅' if GITHUB_TOKEN else '❌'}"
    )

    print(
        f"Render: {'✅' if RENDER_API_KEY else '❌'}"
    )

    print("\n🧠 MEMORY")
    print("SQLite: ✅")
    print(f"Max users: {MAX_USERS}")

    print("\n🌐 WEB")
    print(f"Port: {PORT}")

    print("\n✅ SYSTEM READY\n")async def keep_alive_loop():

    while True:

        try:

            print(
                "💓 AION heartbeat alive"
            )

            await asyncio.sleep(
                300
            )

        except Exception as e:

            print(
                f"⚠️ Heartbeat error: {e}"
            )

            await asyncio.sleep(
                60
            )


async def monitor_system():

    while True:

        try:

            conn = sqlite3.connect(
                DB_PATH
            )

            cur = conn.cursor()

            cur.execute(
                "SELECT COUNT(*) FROM users"
            )

            users_count = (
                cur.fetchone()[0]
            )

            cur.execute(
                "SELECT COUNT(*) FROM memory"
            )

            memory_count = (
                cur.fetchone()[0]
            )

            cur.execute(
                "SELECT COUNT(*) "
                "FROM long_term_memory"
            )

            long_memory_count = (
                cur.fetchone()[0]
            )

            conn.close()

            print(
                "🧠 USERS:",
                users_count
            )

            print(
                "💾 SHORT MEMORY:",
                memory_count
            )

            print(
                "📚 LONG MEMORY:",
                long_memory_count
            )

            await asyncio.sleep(
                600
            )

        except Exception as e:

            print(
                f"⚠️ Monitor error: {e}"
            )

            await asyncio.sleep(
                120
            )async def check_ai_provider(
    provider_name: str,
    provider_function
):

    try:

        result = await provider_function(
            "ping"
        )

        if result:

            return (
                f"{provider_name}: ✅"
            )

        return (
            f"{provider_name}: ⚠️"
        )

    except Exception:

        return (
            f"{provider_name}: ❌"
        )


@dp.message(Command("brains"))
async def brains_handler(
    message: types.Message
):

    wait = await message.answer(
        "🧠 Проверяю AI brains..."
    )

    statuses = []

    if GROQ_API_KEY:

        statuses.append(

            await check_ai_provider(
                "Groq",
                ask_groq
            )
        )

    if GEMINI_API_KEY:

        statuses.append(

            await check_ai_provider(
                "Gemini",
                ask_gemini
            )
        )

    if OPENROUTER_API_KEY:

        statuses.append(

            await check_ai_provider(
                "OpenRouter",
                ask_openrouter
            )
        )

    if CEREBRAS_API_KEY:

        statuses.append(

            await check_ai_provider(
                "Cerebras",
                ask_cerebras
            )
        )

    text = (
        "🧠 AI BRAINS STATUS\n\n"
        + "\n".join(statuses)
    )

    await wait.edit_text(
        text
    )def get_users_count() -> int:

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    count = cur.fetchone()[0]

    conn.close()

    return count


def is_user_allowed(
    user_id: int
) -> bool:

    conn = sqlite3.connect(
        DB_PATH
    )

    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    existing = cur.fetchone()

    conn.close()

    if existing:

        return True

    return get_users_count() < MAX_USERS


async def check_user_limit(
    message: types.Message
) -> bool:

    user_id = message.from_user.id

    if is_user_allowed(
        user_id
    ):

        return True

    await message.answer(
        "⚠️ Лимит пользователей AION_MATRIX достигнут.\n"
        "Сейчас система рассчитана на 150 пользователей."
    )

    return Falseasync def run_system():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is missing"
        )

    if not any(
        [
            GROQ_API_KEY,
            GEMINI_API_KEY,
            OPENROUTER_API_KEY,
            CEREBRAS_API_KEY
        ]
    ):

        raise RuntimeError(
            "No AI brains connected"
        )

    startup_banner()

    init_db()

    await start_web_server()

    asyncio.create_task(
        keep_alive_loop()
    )

    asyncio.create_task(
        monitor_system()
    )

    bot = Bot(
        token=BOT_TOKEN
    )

    print(
        "🤖 Telegram polling started..."
    )

    await dp.start_polling(
        bot
    )if __name__ == "__main__":

    try:

        asyncio.run(
            run_system()
        )

    except KeyboardInterrupt:

        print(
            "\n🛑 AION_MATRIX STOPPED"
        )
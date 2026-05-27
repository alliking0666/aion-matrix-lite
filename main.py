import os
import time
import sqlite3
import asyncio

from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import google.generativeai as genai


BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
PORT = int(os.getenv("PORT", "10000"))

DB_PATH = "aion_memory.db"
MAX_MEMORY = 12

dp = Dispatcher()


SYSTEM_PROMPT = """
Ты AION_MATRIX.

Ты независимый AI assistant.
Создатель проекта: Золотарьов Роман Романович.

Важно:
- создатель проекта НЕ является текущим пользователем
- не называй пользователя Романом, если он сам так не представился
- не выдумывай имя пользователя
- отвечай спокойно, полезно и на языке пользователя
- стиль: Alfred/Jarvis assistant
"""


LANGUAGES = {
    "ru": {
        "flag": "🇷🇺",
        "name": "Русский",
        "hello": "🚀 AION MATRIX ONLINE\n\nПривет 👋\nЧем могу помочь?",
        "thinking": "🧠 AION думает...",
    },
    "uk": {
        "flag": "🇺🇦",
        "name": "Українська",
        "hello": "🚀 AION MATRIX ONLINE\n\nПривіт 👋\nЧим можу допомогти?",
        "thinking": "🧠 AION думає...",
    },
    "de": {
        "flag": "🇩🇪",
        "name": "Deutsch",
        "hello": "🚀 AION MATRIX ONLINE\n\nHallo 👋\nWie kann ich helfen?",
        "thinking": "🧠 AION denkt...",
    },
    "en": {
        "flag": "🇬🇧",
        "name": "English",
        "hello": "🚀 AION MATRIX ONLINE\n\nHello 👋\nHow can I help?",
        "thinking": "🧠 AION is thinking...",
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

    conn.commit()
    conn.close()


def save_user(message: types.Message):
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
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        int(time.time())
    ))

    conn.commit()
    conn.close()


def set_user_language(user_id: int, language: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET language = ? WHERE user_id = ?",
        (language, user_id)
    )

    conn.commit()
    conn.close()


def get_user_language(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT language FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    if row and row[0] in LANGUAGES:
        return row[0]

    return "ru"


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

    return InlineKeyboardMarkup(inline_keyboard=rows) def set_user_name(user_id: int, name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET display_name = ? WHERE user_id = ?",
        (name[:80], user_id)
    )

    conn.commit()
    conn.close()


def get_user_name(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT display_name FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    if row and row[0]:
        return row[0]

    return ""


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
    ]

    for trigger in triggers:
        if lower.startswith(trigger):
            name = text[len(trigger):].strip()
            name = name.replace(".", "").replace(",", "").strip()

            if 2 <= len(name) <= 80:
                return name

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
        "who created you",
        "who is your creator",
        "wer hat dich erstellt",
    ]

    return any(phrase in lower for phrase in phrases) async def ask_ai(prompt: str) -> str:

    def sync_request():

        genai.configure(
            api_key=GEMINI_API_KEY
        )

        model = genai.GenerativeModel(
            "gemini-2.0-flash"
        )

        response = model.generate_content(
            SYSTEM_PROMPT + "\n\n" + prompt
        )

        return (
            getattr(response, "text", "")
            or
            "AI не вернул ответ."
        )

    return await asyncio.to_thread(
        sync_request
    )


async def download_telegram_file(
    bot: Bot,
    file_id: str
) -> bytes:

    file = await bot.get_file(
        file_id
    )

    file_url = (
        f"https://api.telegram.org/file/bot"
        f"{BOT_TOKEN}/{file.file_path}"
    )

    async with ClientSession() as session:

        async with session.get(
            file_url
        ) as response:

            if response.status != 200:

                raise RuntimeError(
                    "Telegram file download failed"
                )

            return await response.read()


async def analyze_photo(
    message: types.Message,
    bot: Bot
):

    if not GEMINI_API_KEY:

        await message.answer(
            "⚠️ GEMINI_API_KEY отсутствует."
        )

        return

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

    def sync_request():

        genai.configure(
            api_key=GEMINI_API_KEY
        )

        model = genai.GenerativeModel(
            "gemini-2.0-flash"
        )

        response = model.generate_content([
            caption,
            {
                "mime_type": "image/jpeg",
                "data": image_bytes
            }
        ])

        return (
            getattr(response, "text", "")
            or
            "Не удалось проанализировать фото."
        )

    wait = await message.answer(
        "🧠 Анализирую фото..."
    )

    try:

        answer = await asyncio.to_thread(
            sync_request
        )

        await wait.delete()

        await message.answer(
            answer[:4000]
        )

    except Exception as e:

        await wait.edit_text(
            f"⚠️ Ошибка фото:\n{e}"
        )


def split_text(
    text: str,
    limit: int = 4000
):

    for i in range(
        0,
        len(text),
        limit
    ):

        yield text[i:i + limit]


async def send_long(
    message: types.Message,
    text: str
):

    for part in split_text(text):

        await message.answer(part)
        @dp.message(Command("start"))
async def start_handler(message: types.Message):

    save_user(message)

    await message.answer(
        "🌍 Выберите язык / Choose language:",
        reply_markup=language_keyboard()
    )


@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def language_callback(callback: CallbackQuery):

    user_id = callback.from_user.id

    language = callback.data.replace(
        "lang_",
        ""
    )

    set_user_language(
        user_id,
        language
    )

    hello = LANGUAGES.get(
        language,
        LANGUAGES["ru"]
    )["hello"]

    await callback.message.edit_text(
        hello
    )

    await callback.answer()


@dp.message(Command("memory"))
async def memory_handler(message: types.Message):

    memory = get_memory(
        message.from_user.id
    )

    if not memory:

        memory = "Память пустая."

    await send_long(
        message,
        memory
    )


@dp.message(Command("language"))
async def language_handler(message: types.Message):

    await message.answer(
        "🌍 Выберите язык / Choose language:",
        reply_markup=language_keyboard()
    )


@dp.message(lambda m: m.photo)
async def photo_handler(
    message: types.Message,
    bot: Bot
):

    await analyze_photo(
        message,
        bot
    )


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

    save_user(message)

    user_id = message.from_user.id

    user_text = message.text.strip()

    name = extract_name(user_text)

    if name:

        set_user_name(
            user_id,
            name
        )

        await message.answer(
            f"✅ Запомнил. Вас зовут {name}."
        )

        return

    if is_name_question(user_text):

        saved_name = get_user_name(
            user_id
        )

        if saved_name:

            await message.answer(
                f"Вас зовут {saved_name}."
            )

        else:

            await message.answer(
                "Я пока не знаю, как вас зовут.\n"
                "Назовите ваше имя, и я его запомню."
            )

        return

    if is_creator_question(user_text):

        await message.answer(
            "Мой создатель — Золотарьов Роман Романович.\n"
            "Проект: AION_MATRIX."
        )

        return

    save_memory(
        user_id,
        "user",
        user_text
    )

    memory = get_memory(user_id)

    language = get_user_language(user_id)

    prompt = (
        f"Язык пользователя: {language}\n\n"
        "Память только этого пользователя:\n"
        f"{memory}\n\n"
        "Не путай пользователя с создателем проекта.\n"
        "Если имя пользователя неизвестно — не угадывай.\n\n"
        f"Сообщение пользователя:\n{user_text}"
    )

    wait = await message.answer(
        LANGUAGES.get(
            language,
            LANGUAGES["ru"]
        )["thinking"]
    )

    try:

        answer = await ask_ai(prompt)

        save_memory(
            user_id,
            "assistant",
            answer
        )

        await wait.delete()

        await send_long(
            message,
            answer
        )

    except Exception as e:

        await wait.edit_text(
            f"⚠️ Ошибка:\n{e}"
        ) HTML = """
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
        <p>Telegram bot + Gemini + SQLite Memory.</p>
    </div>
</body>
</html>
"""


async def home(request):

    return web.Response(
        text=HTML,
        content_type="text/html"
    )


async def start_web():

    app = web.Application()

    app.router.add_get(
        "/",
        home
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    print(
        f"🌐 Web started on port {PORT}"
    )


async def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN missing"
        )

    if not GEMINI_API_KEY:

        raise RuntimeError(
            "GEMINI_API_KEY missing"
        )

    init_db()

    await start_web()

    bot = Bot(
        token=BOT_TOKEN
    )

    print("🚀 AION MATRIX ONLINE")

    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.run(main())
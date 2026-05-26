import os
import asyncio
from aiohttp import web, ClientSession

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

import google.generativeai as genai


BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PORT = int(os.getenv("PORT", 10000))

dp = Dispatcher()

SYSTEM_PROMPT = (
    "Ты AION MATRIX LITE — полезный AI-помощник. "
    "Отвечай понятно, кратко и на языке пользователя."
)


async def ask_groq(text: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "temperature": 0.7,
        "max_tokens": 800
    }

    async with ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            data = await response.json()

            if response.status != 200:
                raise Exception(str(data))

            return data["choices"][0]["message"]["content"]


async def ask_gemini(text: str) -> str:
    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel("gemini-2.0-flash")

    response = model.generate_content(
        f"{SYSTEM_PROMPT}\n\nПользователь: {text}"
    )

    return response.text or "Gemini не вернул текстовый ответ."


async def ask_aion(text: str) -> str:
    errors = []

    if GROQ_API_KEY:
        try:
            return await ask_groq(text)
        except Exception as e:
            errors.append(f"Groq: {e}")

    if GEMINI_API_KEY:
        try:
            return await ask_gemini(text)
        except Exception as e:
            errors.append(f"Gemini: {e}")

    return "⚠️ AI временно не ответил.\n\n" + "\n".join(errors)


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🚀 AION MATRIX LITE ONLINE\n\n"
        "Напиши любой вопрос."
    )


@dp.message()
async def ai_chat(message: types.Message):
    if not message.text:
        await message.answer("⚠️ Пока поддерживается только текст.")
        return

    thinking = await message.answer("🧠 Думаю...")

    try:
        answer = await ask_aion(message.text)

        if len(answer) > 4000:
            answer = answer[:4000]

        await thinking.delete()
        await message.answer(answer)

    except Exception as e:
        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(f"⚠️ Ошибка:\n{e}")


async def health(request):
    return web.Response(text="AION MATRIX LITE ONLINE")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    if not GROQ_API_KEY and not GEMINI_API_KEY:
        raise RuntimeError("GROQ_API_KEY or GEMINI_API_KEY is missing")

    print("🚀 AION MATRIX LITE STARTED")

    bot = Bot(token=BOT_TOKEN)

    await start_web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
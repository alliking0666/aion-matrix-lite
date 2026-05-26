import os
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from openai import OpenAI
import google.generativeai as genai


BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

PORT = int(os.getenv("PORT", 10000))


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# GEMINI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    gemini_model = None


# GROQ
if GROQ_API_KEY:
    groq = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
else:
    groq = None


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🚀 AION MATRIX LITE ONLINE\n\n"
        "🧠 Groq + Gemini активны.\n"
        "Напиши любой вопрос."
    )


async def ask_groq(text):
    response = groq.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {
                "role": "system",
                "content": "Ты AION MATRIX LITE — мощный AI помощник."
            },
            {
                "role": "user",
                "content": text
            }
        ]
    )

    return response.choices[0].message.content


async def ask_gemini(text):
    response = gemini_model.generate_content(text)
    return response.text


@dp.message()
async def ai_chat(message: types.Message):

    if not message.text:
        await message.answer("⚠️ Пока поддерживается только текст.")
        return

    await message.answer("🧠 Думаю...")

    # 1. ПРОБУЕМ GROQ
    if groq:
        try:
            answer = await ask_groq(message.text)

            if answer:
                await message.answer(answer[:4000])
                return

        except Exception as e:
            print("GROQ ERROR:", e)

    # 2. FALLBACK GEMINI
    if gemini_model:
        try:
            answer = await ask_gemini(message.text)

            if answer:
                await message.answer(answer[:4000])
                return

        except Exception as e:
            print("GEMINI ERROR:", e)

    await message.answer("⚠️ AI временно недоступен.")


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
    print("🚀 AION MATRIX LITE STARTED")

    await start_web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
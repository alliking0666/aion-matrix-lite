import os
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

import google.generativeai as genai


BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🚀 AION MATRIX LITE запущен.\n\n"
        "Напиши мне любой вопрос — я отвечу через Gemini AI."
    )


@dp.message()
async def ai_chat(message: types.Message):
    if not message.text:
        await message.answer("Пока я понимаю только текст.")
        return

    try:
        await message.answer("🧠 Думаю...")

        response = model.generate_content(
            "Ты AION MATRIX LITE — полезный AI-помощник. "
            "Отвечай понятно, коротко и на языке пользователя.\n\n"
            f"Пользователь: {message.text}"
        )

        answer = response.text or "Не смог получить ответ от Gemini."

        if len(answer) > 4000:
            answer = answer[:4000]

        await message.answer(answer)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка Gemini: {e}")


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

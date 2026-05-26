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

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)

# Актуальная модель
model = genai.GenerativeModel("gemini-2.0-flash")


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🚀 AION MATRIX LITE ONLINE\n\n"
        "Напиши любой вопрос."
    )


@dp.message()
async def ai_chat(message: types.Message):

    if not message.text:
        await message.answer("⚠️ Поддерживается только текст.")
        return

    thinking = await message.answer("🧠 Думаю...")

    try:
        prompt = (
            "Ты AION MATRIX LITE — умный AI помощник. "
            "Отвечай понятно, кратко и на языке пользователя.\n\n"
            f"Пользователь: {message.text}"
        )

        response = model.generate_content(prompt)

        answer = "⚠️ Gemini не вернул ответ."

        if response and hasattr(response, "text"):
            answer = response.text

        if len(answer) > 4000:
            answer = answer[:4000]

        await thinking.delete()

        await message.answer(answer)

    except Exception as e:
        await thinking.delete()
        await message.answer(f"⚠️ Ошибка Gemini:\n{e}")


# Health check for Render
async def health(request):
    return web.Response(text="AION MATRIX LITE ONLINE")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=PORT
    )

    await site.start()


async def main():
    print("🚀 AION MATRIX LITE STARTED")

    await start_web_server()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

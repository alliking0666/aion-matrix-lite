import os
import asyncio

from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from openai import OpenAI


BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

PORT = int(os.getenv("PORT", 10000))


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)


@dp.message(Command("start"))
async def start(message: types.Message):

    await message.answer(
        "🚀 AION MATRIX LITE ONLINE\n\n"
        "Groq AI подключен."
    )


@dp.message()
async def ai_chat(message: types.Message):

    if not message.text:
        await message.answer(
            "⚠️ Поддерживается только текст."
        )
        return

    thinking = await message.answer(
        "🧠 Думаю..."
    )

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты AION MATRIX LITE — "
                        "полезный AI помощник. "
                        "Отвечай кратко и понятно."
                    )
                },

                {
                    "role": "user",
                    "content": message.text
                }
            ]
        )

        answer = response.choices[0].message.content

        if len(answer) > 4000:
            answer = answer[:4000]

        await thinking.delete()

        await message.answer(answer)

    except Exception as e:

        await thinking.delete()

        await message.answer(
            f"⚠️ Ошибка:\n{e}"
        )


async def health(request):

    return web.Response(
        text="AION MATRIX LITE ONLINE"
    )


async def start_web_server():

    app = web.Application()

    app.router.add_get("/", health)

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()


async def main():

    print("🚀 AION MATRIX LITE STARTED")

    await start_web_server()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
import os
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from openai import OpenAI
import google.generativeai as genai


BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

groq_client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
) if GROQ_API_KEY else None


SYSTEM_PROMPT = (
    "Ты AION MATRIX LITE — полезный AI-помощник. "
    "Отвечай понятно, кратко и на языке пользователя."
)


async def ask_gemini(text: str) -> str:
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(
        f"{SYSTEM_PROMPT}\n\nПользователь: {text}"
    )
    return response.text


async def ask_groq(text: str) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content


async def ask_aion(text: str) -> str:
    errors = []

    if GEMINI_API_KEY:
        try:
            return await ask_gemini(text)
        except Exception as e:
            errors.append(f"Gemini: {e}")

    if GROQ_API_KEY and groq_client:
        try:
            return await ask_groq(text)
        except Exception as e:
            errors.append(f"Groq: {e}")

    return "⚠️ Оба AI-мозга не ответили.\n\n" + "\n".join(errors)


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🚀 AION MATRIX LITE ONLINE\n\n"
        "🧠 Gemini + Groq подключены.\n"
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
        await thinking.delete()
        await message.answer(f"⚠️ Ошибка:\n{e}")


async def health(request):
    return web.Response(text="AION MATRIX LITE ONLINE")


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
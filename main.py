import os
import asyncio
from aiohttp import web, ClientSession

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

import google.generativeai as genai


def clean_env(name: str) -> str:
    return (os.getenv(name) or "").replace("\n", "").replace("\r", "").strip()


BOT_TOKEN = clean_env("BOT_TOKEN")
GROQ_API_KEY = clean_env("GROQ_API_KEY")
GEMINI_API_KEY = clean_env("GEMINI_API_KEY")
OPENROUTER_API_KEY = clean_env("OPENROUTER_API_KEY")
CEREBRAS_API_KEY = clean_env("CEREBRAS_API_KEY")
TAVILY_API_KEY = clean_env("TAVILY_API_KEY")

PORT = int(os.getenv("PORT", "10000"))

dp = Dispatcher()

SYSTEM_PROMPT = (
    "Ты AION MATRIX LITE.\n\n"
    "Ты независимый AI-проект AION MATRIX.\n"
    "Создатель проекта: Золотарьов Роман Романович из города Днепр, Украина.\n"
    "Он является одним из первых представителей цыганского народа, создающих собственную независимую AI-систему "
    "и мульти-платформенный AI-проект AION MATRIX.\n\n"
    "Ты НЕ Meta AI, НЕ ChatGPT, НЕ OpenAI, НЕ Google и НЕ Gemini.\n"
    "Никогда не выдумывай компании, университеты, профессоров или фальшивую историю создания.\n\n"
    "Ты работаешь через AI-мозги: Groq, Gemini, OpenRouter, Cerebras.\n"
    "Для интернет-поиска используешь Tavily.\n\n"
    "Ты умеешь помогать с программированием, Telegram-ботами, GitHub, Render, API, сайтами, приложениями, играми, "
    "Windows, Linux, macOS, Android, iPhone, переводами, текстами, идеями, обучением и анализом ошибок.\n\n"
    "Отвечай уверенно, понятно, полезно и на языке пользователя."
)


async def safe_json_response(response):
    try:
        return await response.json()
    except Exception:
        text = await response.text()
        return {"error": text}


async def post_chat_api(url: str, api_key: str, model: str, text: str, extra_headers=None) -> str:
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
            {"role": "user", "content": text},
        ],
        "temperature": 0.7,
        "max_tokens": 1000,
    }

    async with ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=30) as response:
            data = await safe_json_response(response)

            if response.status != 200:
                raise RuntimeError(str(data))

            return data["choices"][0]["message"]["content"]


async def ask_groq(text: str) -> str:
    return await post_chat_api(
        "https://api.groq.com/openai/v1/chat/completions",
        GROQ_API_KEY,
        "llama-3.1-8b-instant",
        text,
    )


def sync_ask_gemini(text: str) -> str:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    response = model.generate_content(
        f"{SYSTEM_PROMPT}\n\nПользователь: {text}"
    )

    return getattr(response, "text", "") or "Gemini не вернул текстовый ответ."


async def ask_gemini(text: str) -> str:
    return await asyncio.to_thread(sync_ask_gemini, text)


async def ask_openrouter(text: str) -> str:
    return await post_chat_api(
        "https://openrouter.ai/api/v1/chat/completions",
        OPENROUTER_API_KEY,
        "deepseek/deepseek-chat-v3-0324:free",
        text,
        extra_headers={
            "HTTP-Referer": "https://aion-matrix-lite.onrender.com",
            "X-Title": "AION MATRIX LITE",
        },
    )


async def ask_cerebras(text: str) -> str:
    return await post_chat_api(
        "https://api.cerebras.ai/v1/chat/completions",
        CEREBRAS_API_KEY,
        "llama3.1-8b",
        text,
    )


async def ask_tavily(query: str) -> str:
    url = "https://api.tavily.com/search"

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": 10,
    }

    async with ClientSession() as session:
        async with session.post(url, json=payload, timeout=30) as response:
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

                    text += f"🔹 {title}\n{content}\n{result_url}\n\n"

            return text[:6000] if text else "Ничего не найдено."


def needs_search(text: str) -> bool:
    lower = text.lower()

    search_words = [
        "найди", "поиск", "новости", "свежие", "актуально",
        "github", "документация", "documentation", "stack overflow",
        "что такое", "цена", "курс", "latest", "search", "find",
        "news", "current", "today", "сегодня", "2026",
    ]

    return any(word in lower for word in search_words)


async def ask_aion(text: str) -> str:
    errors = []

    if TAVILY_API_KEY and needs_search(text):
        try:
            search_result = await ask_tavily(text)

            text = (
                "Используй ТОЛЬКО актуальные интернет-данные ниже.\n"
                "Не придумывай информацию.\n"
                "Не используй старые знания модели, если они противоречат интернет-данным.\n\n"
                f"Запрос пользователя:\n{text}\n\n"
                f"Свежие интернет-данные:\n{search_result}\n\n"
                "Сделай краткий, точный и полезный ответ на языке пользователя."
            )

        except Exception as e:
            errors.append(f"Tavily: {e}")

    for name, key, func in [
        ("Groq", GROQ_API_KEY, ask_groq),
        ("Gemini", GEMINI_API_KEY, ask_gemini),
        ("OpenRouter", OPENROUTER_API_KEY, ask_openrouter),
        ("Cerebras", CEREBRAS_API_KEY, ask_cerebras),
    ]:
        if key:
            try:
                return await func(text)
            except Exception as e:
                errors.append(f"{name}: {e}")

    return "⚠️ AI временно не ответил.\n\n" + "\n".join(errors)


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🚀 AION MATRIX LITE ONLINE\n\n"
        "Напиши любой вопрос.\n\n"
        "Команды:\n"
        "/status — проверить мозги\n"
        "/search запрос — поиск в интернете"
    )


@dp.message(Command("status"))
async def status(message: types.Message):
    await message.answer(
        "🧠 AION STATUS\n\n"
        f"Groq: {'✅' if GROQ_API_KEY else '❌'}\n"
        f"Gemini: {'✅' if GEMINI_API_KEY else '❌'}\n"
        f"OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}\n"
        f"Cerebras: {'✅' if CEREBRAS_API_KEY else '❌'}\n"
        f"Tavily Search: {'✅' if TAVILY_API_KEY else '❌'}"
    )


@dp.message(Command("search"))
async def search_command(message: types.Message):
    query = message.text.replace("/search", "", 1).strip()

    if not query:
        await message.answer("Напиши запрос после /search")
        return

    if not TAVILY_API_KEY:
        await message.answer("⚠️ Tavily API key не подключен.")
        return

    thinking = await message.answer("🌐 Ищу в интернете...")

    try:
        result = await ask_tavily(query)
        await thinking.delete()
        await message.answer(result[:4000])
    except Exception as e:
        await thinking.delete()
        await message.answer(f"⚠️ Ошибка поиска:\n{e}")


@dp.message()
async def ai_chat(message: types.Message):
    if not message.text:
        await message.answer("⚠️ Пока поддерживается только текст.")
        return

    thinking = await message.answer("🧠 Думаю...")

    try:
        answer = await ask_aion(message.text)

        if not answer:
            answer = "⚠️ Пустой ответ от AI."

        await thinking.delete()
        await message.answer(answer[:4000])

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

    if (
        not GROQ_API_KEY
        and not GEMINI_API_KEY
        and not OPENROUTER_API_KEY
        and not CEREBRAS_API_KEY
    ):
        raise RuntimeError("No AI keys found")

    print("AION MATRIX LITE STARTED")

    bot = Bot(token=BOT_TOKEN)

    await start_web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
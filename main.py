import os
import asyncio
import sqlite3
import time
import base64
import json

from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

import google.generativeai as genai


def clean_env(name: str) -> str:
    return (
        os.getenv(name) or ""
    ).replace("\n", "").replace("\r", "").strip()


BOT_TOKEN = clean_env("BOT_TOKEN")

# AI brains
GROQ_API_KEY = clean_env("GROQ_API_KEY")
GEMINI_API_KEY = clean_env("GEMINI_API_KEY")
OPENROUTER_API_KEY = clean_env("OPENROUTER_API_KEY")
CEREBRAS_API_KEY = clean_env("CEREBRAS_API_KEY")

# Tools
TAVILY_API_KEY = clean_env("TAVILY_API_KEY")
GITHUB_TOKEN = clean_env("GITHUB_TOKEN")
RENDER_API_KEY = clean_env("RENDER_API_KEY")

PORT = int(os.getenv("PORT", "10000"))

DB_PATH = "aion_memory.db"
MAX_MEMORY_MESSAGES = 12
MAX_TELEGRAM_MESSAGE = 4000

dp = Dispatcher()


SYSTEM_PROMPT = (
    "Ты AION_MATRIX.\n\n"
    "Ты независимый AI-проект AION_MATRIX.\n"
    "Создатель проекта: Золотарьов Роман Романович из города Днепр, Украина.\n"
    "Он является одним из первых представителей цыганского народа, создающих собственную независимую AI-систему "
    "и мульти-платформенный AI-проект AION_MATRIX.\n\n"

    "Ты НЕ Meta AI, НЕ ChatGPT, НЕ OpenAI, НЕ Google и НЕ Gemini.\n"
    "Никогда не выдумывай компании, университеты, профессоров или фальшивую историю создания.\n\n"

    "Ты работаешь через AI-мозги: Groq, Gemini, OpenRouter, Cerebras.\n"
    "Для интернет-поиска используешь Tavily.\n"
    "Для GitHub используешь GitHub API.\n"
    "Для Render используешь Render API.\n"
    "У тебя есть SQLite-память.\n\n"

    "Ты умеешь помогать с программированием, Telegram-ботами, GitHub, Render, API, сайтами, приложениями, играми, "
    "Windows, Linux, macOS, Android, iPhone, переводами, текстами, идеями, обучением и анализом ошибок.\n\n"

    "Если ты не знаешь точных деталей — говори честно: 'Точных деталей у меня нет.' "
    "Не используй фразы 'могу предположить', 'вероятно', 'скорее всего' о своей истории создания.\n\n"

    "Отвечай уверенно, понятно, полезно и на языке пользователя."
) def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
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
    if not message.from_user:
        return

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
        content[:2000],
        int(time.time())
    ))

    cur.execute("""
    DELETE FROM memory
    WHERE user_id = ?
    AND id NOT IN (
        SELECT id FROM memory
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    )
    """, (
        user_id,
        user_id,
        MAX_MEMORY_MESSAGES
    ))

    conn.commit()
    conn.close()


def get_memory_context(user_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    SELECT role, content FROM memory
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT ?
    """, (
        user_id,
        MAX_MEMORY_MESSAGES
    ))

    rows = cur.fetchall()
    conn.close()

    rows.reverse()

    if not rows:
        return ""

    text = "Контекст последних сообщений пользователя:\n"

    for role, content in rows:
        text += f"{role}: {content}\n"

    return text[:3500]


def clear_memory(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM memory WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close() async def safe_json_response(response):
    try:
        return await response.json()
    except Exception:
        text = await response.text()
        return {"error": text}


async def post_chat_api(
    url: str,
    api_key: str,
    model: str,
    text: str,
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
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.7,
        "max_tokens": 1200,
    }

    async with ClientSession() as session:
        async with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=60
        ) as response:

            data = await safe_json_response(response)

            if response.status != 200:
                raise RuntimeError(str(data))

            return (
                data["choices"][0]
                ["message"]
                ["content"]
            )


async def ask_groq(text: str) -> str:
    return await post_chat_api(
        url="https://api.groq.com/openai/v1/chat/completions",
        api_key=GROQ_API_KEY,
        model="llama-3.1-8b-instant",
        text=text,
    )


def sync_ask_gemini(text: str) -> str:
    genai.configure(
        api_key=GEMINI_API_KEY
    )

    model = genai.GenerativeModel(
        "gemini-2.0-flash"
    )

    response = model.generate_content(
        f"{SYSTEM_PROMPT}\n\n{text}"
    )

    return (
        getattr(response, "text", "")
        or "Gemini не вернул ответ."
    )


async def ask_gemini(text: str) -> str:
    return await asyncio.to_thread(
        sync_ask_gemini,
        text
    )


async def ask_openrouter(text: str) -> str:
    return await post_chat_api(
        url="https://openrouter.ai/api/v1/chat/completions",
        api_key=OPENROUTER_API_KEY,
        model="deepseek/deepseek-chat-v3-0324:free",
        text=text,
        extra_headers={
            "HTTP-Referer": "https://aion-matrix-lite.onrender.com",
            "X-Title": "AION_MATRIX",
        },
    )


async def ask_cerebras(text: str) -> str:
    return await post_chat_api(
        url="https://api.cerebras.ai/v1/chat/completions",
        api_key=CEREBRAS_API_KEY,
        model="llama3.1-8b",
        text=text,
    ) async def ask_tavily(query: str) -> str:
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
            timeout=60
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
            timeout=30
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

            return text[:4000]


async def ask_render_services() -> str:
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Accept": "application/json",
    }

    async with ClientSession() as session:
        async with session.get(
            "https://api.render.com/v1/services",
            headers=headers,
            timeout=30
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

            return text[:4000] def needs_search(text: str) -> bool:
    lower = text.lower()

    search_words = [
        "найди",
        "поиск",
        "новости",
        "свежие",
        "актуально",
        "документация",
        "documentation",
        "stack overflow",
        "что такое",
        "цена",
        "курс",
        "latest",
        "search",
        "find",
        "news",
        "current",
        "today",
        "сегодня",
        "2026",
    ]

    return any(word in lower for word in search_words)


def needs_github(text: str) -> bool:
    lower = text.lower()

    github_words = [
        "github",
        "repo",
        "repository",
        "репозиторий",
        "репозитории",
        "найди репозиторий",
        "найди github",
    ]

    return any(word in lower for word in github_words)


async def ask_aion(text: str) -> str:
    errors = []

    if GITHUB_TOKEN and needs_github(text):
        try:
            return await ask_github(text)
        except Exception as e:
            errors.append(f"GitHub: {e}")

    if TAVILY_API_KEY and needs_search(text):
        try:
            search_result = await ask_tavily(text)

            text = (
                "Используй ТОЛЬКО актуальные интернет-данные ниже.\n"
                "Не придумывай информацию.\n\n"
                f"Запрос пользователя:\n{text}\n\n"
                f"Свежие интернет-данные:\n{search_result}\n\n"
                "Сделай краткий, точный и полезный ответ."
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
        if key:
            try:
                return await func(text)
            except Exception as e:
                errors.append(f"{name}: {e}")

    return (
        "⚠️ AI временно не ответил.\n\n"
        + "\n".join(errors)
    ) HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AION_MATRIX Control Panel</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>

<body class="bg-gray-950 text-gray-100 min-h-screen">

    <header class="bg-gray-900 p-4 text-center border-b border-cyan-500">
        <h1 class="text-2xl font-bold text-cyan-400">
            ⚡ AION_MATRIX
        </h1>

        <p class="text-xs text-gray-400 mt-1">
            Multi-Brain AI Platform
        </p>
    </header>

    <main class="p-6 max-w-4xl mx-auto">

        <section class="bg-gray-900 p-6 rounded-xl border border-gray-800 shadow-xl">
            <h2 class="text-lg font-semibold text-cyan-300 mb-4">
                Запрос для AION_MATRIX
            </h2>

            <form action="/web/process" method="post" class="space-y-4">
                <textarea
                    name="user_request"
                    rows="5"
                    class="w-full p-3 bg-gray-800 rounded border border-gray-700 text-white"
                    placeholder="Например: создай лендинг, найди новости Python, найди GitHub repo..."
                    required
                ></textarea>

                <button
                    type="submit"
                    class="w-full bg-cyan-600 hover:bg-cyan-700 text-white font-bold py-3 rounded"
                >
                    🚀 Запустить AION_MATRIX
                </button>
            </form>
        </section>

        {result_block}

        <section class="mt-6 bg-gray-900 p-4 rounded-xl border border-gray-800 text-sm text-gray-300">
            <p>🧠 Groq + Gemini + OpenRouter + Cerebras</p>
            <p>🌐 Tavily Search</p>
            <p>💻 GitHub API</p>
            <p>☁️ Render API</p>
            <p>🧩 SQLite Memory</p>
        </section>

    </main>

    <footer class="text-center text-xs text-gray-500 p-4">
        AION_MATRIX © 2026 — проект Золотарьова Романа Романовича
    </footer>

</body>
</html>
"""


def render_web_page(result: str = "", title: str = "Результат") -> str:
    if result:
        safe_result = (
            result
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        result_block = f"""
        <section class="mt-6 bg-gray-900 p-6 rounded-xl border border-green-600 shadow-xl">
            <h3 class="text-md font-semibold text-green-400 mb-3">
                ⚡ {title}
            </h3>

            <pre class="whitespace-pre-wrap text-gray-200 text-sm overflow-x-auto">
{safe_result}
            </pre>
        </section>
        """
    else:
        result_block = ""

    return HTML_TEMPLATE.replace(
        "{result_block}",
        result_block
    ) async def web_index(request):
    return web.Response(
        text=render_web_page(),
        content_type="text/html"
    )


async def web_process(request):
    try:
        data = await request.post()
        user_request = data.get("user_request", "").strip()

        if not user_request:
            return web.Response(
                text=render_web_page(
                    "Пустой запрос.",
                    "Ошибка"
                ),
                content_type="text/html"
            )

        answer = await ask_aion(
            "Запрос пришёл из Web Panel AION_MATRIX.\n\n"
            f"Пользователь просит:\n{user_request}"
        )

        return web.Response(
            text=render_web_page(
                answer,
                "Ответ AION_MATRIX"
            ),
            content_type="text/html"
        )

    except Exception as e:
        return web.Response(
            text=render_web_page(
                f"Ошибка Web Panel:\n{e}",
                "Системная ошибка"
            ),
            content_type="text/html"
        )


async def web_status(request):
    status_text = (
        "AION_MATRIX STATUS\n\n"
        f"Groq: {'ON' if GROQ_API_KEY else 'OFF'}\n"
        f"Gemini: {'ON' if GEMINI_API_KEY else 'OFF'}\n"
        f"OpenRouter: {'ON' if OPENROUTER_API_KEY else 'OFF'}\n"
        f"Cerebras: {'ON' if CEREBRAS_API_KEY else 'OFF'}\n"
        f"Tavily Search: {'ON' if TAVILY_API_KEY else 'OFF'}\n"
        f"GitHub API: {'ON' if GITHUB_TOKEN else 'OFF'}\n"
        f"Render API: {'ON' if RENDER_API_KEY else 'OFF'}\n"
        "Memory: ON SQLite\n"
    )

    return web.Response(
        text=status_text,
        content_type="text/plain"
    ) def extract_json_block(text: str):
    try:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            return None

        raw_json = text[start:end + 1]
        return json.loads(raw_json)

    except Exception:
        return None


async def generate_project_files(user_request: str) -> dict:
    prompt = (
        "Ты AION_MATRIX Project Generator.\n\n"
        "Создай маленький рабочий проект по запросу пользователя.\n"
        "Верни СТРОГО JSON без markdown.\n\n"
        "Формат:\n"
        "{\n"
        '  "project_name": "aion-generated-project",\n'
        '  "description": "Описание проекта",\n'
        '  "files": {\n'
        '    "README.md": "текст",\n'
        '    "index.html": "код",\n'
        '    "style.css": "код",\n'
        '    "script.js": "код"\n'
        "  }\n"
        "}\n\n"
        "Правила:\n"
        "- Делай проект простым и рабочим.\n"
        "- Для сайта используй HTML/CSS/JS.\n"
        "- Не добавляй платные API.\n"
        "- Не добавляй опасный код.\n\n"
        f"Запрос пользователя:\n{user_request}"
    )

    response = await ask_aion(prompt)
    data = extract_json_block(response)

    if not data:
        raise RuntimeError(
            "AI не вернул правильный JSON проекта."
        )

    if "files" not in data:
        raise RuntimeError(
            "В JSON нет поля files."
        )

    return data


def build_project_preview(project: dict) -> str:
    name = project.get("project_name", "aion-project")
    description = project.get("description", "")
    files = project.get("files", {})

    text = (
        f"📦 Проект: {name}\n"
        f"📝 Описание: {description}\n\n"
        "Файлы:\n"
    )

    for filename in files.keys():
        text += f"• {filename}\n"

    return text[:4000] def encode_base64(content: str) -> str:
    return base64.b64encode(
        content.encode("utf-8")
    ).decode("utf-8")


def normalize_repo_name(name: str) -> str:
    safe = (
        name.lower()
        .replace(" ", "-")
        .replace("_", "-")
    )

    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"

    safe = "".join(
        char for char in safe
        if char in allowed
    )

    safe = safe.strip("-")

    if not safe:
        safe = "aion-generated-project"

    return safe[:60]


async def github_create_repo(repo_name: str, description: str = "") -> str:
    if not GITHUB_TOKEN:
        raise RuntimeError("GitHub token не подключен.")

    url = "https://api.github.com/user/repos"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    payload = {
        "name": repo_name,
        "description": description[:250],
        "private": False,
        "auto_init": True,
    }

    async with ClientSession() as session:
        async with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        ) as response:

            data = await safe_json_response(response)

            if response.status not in [200, 201]:
                raise RuntimeError(str(data))

            return data.get("html_url", "")


async def github_put_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str = "Add file by AION_MATRIX"
):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    payload = {
        "message": message,
        "content": encode_base64(content),
    }

    async with ClientSession() as session:
        async with session.put(
            url,
            headers=headers,
            json=payload,
            timeout=30
        ) as response:

            data = await safe_json_response(response)

            if response.status not in [200, 201]:
                raise RuntimeError(str(data))

            return data


async def create_project_on_github(user_request: str) -> str:
    project = await generate_project_files(user_request)

    repo_name = normalize_repo_name(
        project.get("project_name", "aion-generated-project")
    )

    description = project.get(
        "description",
        "Generated by AION_MATRIX"
    )

    repo_url = await github_create_repo(
        repo_name,
        description
    )

    owner = repo_url.rstrip("/").split("/")[-2]
    repo = repo_url.rstrip("/").split("/")[-1]

    files = project.get("files", {})

    for filename, content in files.items():
        await github_put_file(
            owner=owner,
            repo=repo,
            path=filename,
            content=str(content),
            message=f"Add {filename}"
        )

    preview = build_project_preview(project)

    return (
        f"{preview}\n\n"
        f"✅ Репозиторий создан:\n{repo_url}"
    ) @dp.message(Command("start"))
async def start(message: types.Message):
    save_user(message)

    await message.answer(
        "🚀 AION_MATRIX ONLINE\n\n"
        "Напиши любой вопрос.\n\n"
        "Команды:\n"
        "/status — проверить модули\n"
        "/memory — показать память\n"
        "/forget — очистить память\n"
        "/search запрос — поиск в интернете\n"
        "/github запрос — поиск репозиториев\n"
        "/render — проверить Render services\n"
        "/create_project запрос — создать проект на GitHub"
    )


@dp.message(Command("status"))
async def status(message: types.Message):
    await message.answer(
        "🧠 AION STATUS\n\n"
        f"Groq: {'✅' if GROQ_API_KEY else '❌'}\n"
        f"Gemini: {'✅' if GEMINI_API_KEY else '❌'}\n"
        f"OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}\n"
        f"Cerebras: {'✅' if CEREBRAS_API_KEY else '❌'}\n"
        f"Tavily Search: {'✅' if TAVILY_API_KEY else '❌'}\n"
        f"GitHub API: {'✅' if GITHUB_TOKEN else '❌'}\n"
        f"Render API: {'✅' if RENDER_API_KEY else '❌'}\n"
        f"Memory: ✅ SQLite\n"
        f"Web Panel: ✅\n"
        f"Project Generator: ✅"
    )


@dp.message(Command("memory"))
async def memory_command(message: types.Message):
    memory = get_memory_context(message.from_user.id)

    if not memory:
        await message.answer("🧠 Память пока пустая.")
        return

    await message.answer(memory[:MAX_TELEGRAM_MESSAGE])


@dp.message(Command("forget"))
async def forget_command(message: types.Message):
    clear_memory(message.from_user.id)
    await message.answer("🧹 Память очищена.")


@dp.message(Command("search"))
async def search_command(message: types.Message):
    query = message.text.replace("/search", "", 1).strip()

    if not query:
        await message.answer("Напиши запрос после /search")
        return

    thinking = await message.answer("🌐 Ищу в интернете...")

    try:
        result = await ask_tavily(query)

        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(result[:MAX_TELEGRAM_MESSAGE])

    except Exception as e:
        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(f"⚠️ Ошибка поиска:\n{e}")


@dp.message(Command("github"))
async def github_command(message: types.Message):
    query = message.text.replace("/github", "", 1).strip()

    if not query:
        await message.answer("Напиши запрос после /github")
        return

    thinking = await message.answer("💻 Ищу на GitHub...")

    try:
        result = await ask_github(query)

        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(result[:MAX_TELEGRAM_MESSAGE])

    except Exception as e:
        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(f"⚠️ Ошибка GitHub:\n{e}")


@dp.message(Command("render"))
async def render_command(message: types.Message):
    thinking = await message.answer("☁️ Проверяю Render...")

    try:
        result = await ask_render_services()

        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(result[:MAX_TELEGRAM_MESSAGE])

    except Exception as e:
        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(f"⚠️ Ошибка Render API:\n{e}")


@dp.message(Command("create_project"))
async def create_project_command(message: types.Message):
    query = message.text.replace("/create_project", "", 1).strip()

    if not query:
        await message.answer(
            "Напиши запрос после /create_project\n\n"
            "Пример:\n"
            "/create_project создай лендинг для автосервиса"
        )
        return

    if not GITHUB_TOKEN:
        await message.answer("⚠️ GitHub token не подключен.")
        return

    thinking = await message.answer("🧱 Создаю проект и загружаю на GitHub...")

    try:
        result = await create_project_on_github(query)

        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(result[:MAX_TELEGRAM_MESSAGE])

    except Exception as e:
        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(f"⚠️ Ошибка создания проекта:\n{e}") @dp.message()
async def ai_chat(message: types.Message):

    if not message.text:
        await message.answer(
            "⚠️ Пока поддерживается только текст."
        )
        return

    save_user(message)

    save_memory(
        message.from_user.id,
        "user",
        message.text
    )

    thinking = await message.answer("🧠 Думаю...")

    try:
        memory_context = get_memory_context(
            message.from_user.id
        )

        full_prompt = (
            f"{memory_context}\n\n"
            f"Новое сообщение пользователя:\n"
            f"{message.text}"
        )

        answer = await ask_aion(full_prompt)

        if not answer:
            answer = "⚠️ Пустой ответ от AI."

        save_memory(
            message.from_user.id,
            "assistant",
            answer
        )

        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(
            answer[:MAX_TELEGRAM_MESSAGE]
        )

    except Exception as e:

        try:
            await thinking.delete()
        except Exception:
            pass

        await message.answer(
            f"⚠️ Ошибка:\n{e}"
        ) async def health(request):
    return web.Response(
        text="AION_MATRIX ONLINE"
    )


async def start_web_server():
    app = web.Application()

    # health
    app.router.add_get("/", health)

    # web panel
    app.router.add_get(
        "/web",
        web_index
    )

    app.router.add_post(
        "/web/process",
        web_process
    )

    app.router.add_get(
        "/web/status",
        web_status
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()


async def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing"
        )

    if not any([
        GROQ_API_KEY,
        GEMINI_API_KEY,
        OPENROUTER_API_KEY,
        CEREBRAS_API_KEY
    ]):
        raise RuntimeError(
            "No AI keys found"
        )

    init_db()

    print("🚀 AION_MATRIX STARTED")

    print("🧠 AI Brains:")
    print(f"Groq: {'ON' if GROQ_API_KEY else 'OFF'}")
    print(f"Gemini: {'ON' if GEMINI_API_KEY else 'OFF'}")
    print(f"OpenRouter: {'ON' if OPENROUTER_API_KEY else 'OFF'}")
    print(f"Cerebras: {'ON' if CEREBRAS_API_KEY else 'OFF'}")

    print("🌐 Tools:")
    print(f"Tavily: {'ON' if TAVILY_API_KEY else 'OFF'}")
    print(f"GitHub: {'ON' if GITHUB_TOKEN else 'OFF'}")
    print(f"Render: {'ON' if RENDER_API_KEY else 'OFF'}")

    bot = Bot(token=BOT_TOKEN)

    await start_web_server()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main()) 
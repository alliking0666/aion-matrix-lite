import os
import sys
import time
import html
import json
import base64
import sqlite3
import asyncio
import aiohttp
import logging
from aiohttp import web
from urllib.parse import quote

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AION_MATRIX")

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
OWNER_ID = int(os.getenv("OWNER_ID") or 0)
PORT = int(os.getenv("PORT", 10000))

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()
CEREBRAS_API_KEY = (os.getenv("CEREBRAS_API_KEY") or "").strip()
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()

TAVILY_API_KEY = (os.getenv("TAVILY_API_KEY") or "").strip()
GITHUB_TOKEN = (os.getenv("GITHUB_TOKEN") or "").strip()
GITHUB_REPO = (os.getenv("GITHUB_REPO") or "alliking0666/aion-matrix-lite").strip()

RENDER_API_KEY = (os.getenv("RENDER_API_KEY") or "").strip()
RENDER_SERVICE_ID = (os.getenv("RENDER_SERVICE_ID") or "").strip()

CLOUDFLARE_API_TOKEN = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()

HUGGINGFACE_API_KEY = (os.getenv("HUGGINGFACE_API_KEY") or "").strip()
FAL_API_KEY = (os.getenv("FAL_API_KEY") or "").strip()

POLLINATIONS_ENABLED = (os.getenv("POLLINATIONS_ENABLED") or "true").lower() == "true"

bot = None
dp = Dispatcher()
http_session = None

DB_FILE = "matrix_memory.db"
COOLDOWN_TIME = 5
user_cooldowns = {}

SYSTEM_PROMPT = """
You are AION MATRIX — a multilingual AI orchestration system.
You answer clearly, honestly, technically, and practically.
Never pretend that inactive modules are active.
Use chat history for context.
"""

STRINGS = {
    "welcome": (
        "🚀 <b>AION MATRIX ONLINE</b>\n\n"
        "💬 Обычный текст — ИИ-диалог\n"
        "📊 /status — статус ключей\n\n"
        "🎨 /image [prompt] — создать изображение\n"
        "🎼 /music [prompt] — создать музыку\n"
        "🎥 /video [prompt] — создать видео\n"
        "🔍 /search [query] — веб-поиск\n\n"
        "🐙 /github owner/repo — GitHub анализ\n"
        "🧬 /render — Render сервисы\n"
        "☁️ /cloudflare — Cloudflare зоны\n"
        "🛠 /evolve — обновить main.py через GitHub + Render"
    ),
    "thinking": "🧠 Вычисление...",
    "cooldown": "⚠️ Подожди несколько секунд.",
    "only_text": "⚠️ Поддерживается только текст.",
}


def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
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


def save_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?)",
        (user_id, username, first_name, int(time.time()))
    )
    cur.execute(
        "UPDATE users SET username=?, first_name=? WHERE user_id=?",
        (username, first_name, user_id)
    )
    conn.commit()
    conn.close()


def save_memory(user_id, role, content):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO memory (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, role, content, int(time.time()))
    )
    conn.commit()
    conn.close()


def get_memory(user_id, limit=8):
    conn = sqlite3.connect(DB_FILE, timeout=30)
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content FROM memory WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def cooldown(user_id):
    now = time.time()
    if user_id in user_cooldowns and now - user_cooldowns[user_id] < COOLDOWN_TIME:
        return False
    user_cooldowns[user_id] = now
    return True


async def send_split(message, text, parse_mode=None):
    if len(text) <= 3900:
        await message.answer(text, parse_mode=parse_mode)
        return

    block = ""
    for line in text.split("\n"):
        if len(block) + len(line) + 1 > 3900:
            await message.answer(block, parse_mode=parse_mode)
            block = line
        else:
            block += ("\n" if block else "") + line

    if block:
        await message.answer(block, parse_mode=parse_mode)


async def ask_openai_compatible(url, key, model, messages, timeout=12):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages}

    async with http_session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

        error_text = await resp.text()
        raise Exception(f"status {resp.status}: {error_text[:250]}")


async def run_ai_pipeline(text, history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})

    errors = []

    if GROQ_API_KEY:
        try:
            return await ask_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions",
                GROQ_API_KEY,
                "llama-3.1-8b-instant",
                messages,
                10
            )
        except Exception as e:
            errors.append(f"Groq: {e}")

    if CEREBRAS_API_KEY:
        try:
            return await ask_openai_compatible(
                "https://api.cerebras.ai/v1/chat/completions",
                CEREBRAS_API_KEY,
                "llama3.1-8b",
                messages,
                10
            )
        except Exception as e:
            errors.append(f"Cerebras: {e}")

    if OPENROUTER_API_KEY:
        try:
            return await ask_openai_compatible(
                "https://openrouter.ai/api/v1/chat/completions",
                OPENROUTER_API_KEY,
                "meta-llama/llama-3.1-8b-instruct:free",
                messages,
                12
            )
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    return "❌ Все текстовые ИИ-провайдеры недоступны:\n" + "\n".join(errors)


async def generate_image(prompt):
    if not POLLINATIONS_ENABLED:
        raise Exception("Pollinations отключён.")
    return f"https://image.pollinations.ai/prompt/{quote(prompt)}"


async def generate_music(prompt):
    if not HUGGINGFACE_API_KEY:
        raise Exception("HUGGINGFACE_API_KEY отсутствует.")

    url = "https://api-inference.huggingface.co/models/facebook/musicgen-melody"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}

    async with http_session.post(url, headers=headers, json={"inputs": prompt}, timeout=75) as resp:
        if resp.status == 200:
            return await resp.read()

        if resp.status == 503:
            await asyncio.sleep(15)
            async with http_session.post(url, headers=headers, json={"inputs": prompt}, timeout=75) as retry:
                if retry.status == 200:
                    return await retry.read()

        raise Exception(f"HuggingFace status {resp.status}: {(await resp.text())[:200]}")


async def generate_video(prompt):
    if not FAL_API_KEY:
        raise Exception("FAL_API_KEY отсутствует.")

    url = "https://queue.fal.run/fal-ai/luma-dream-machine"
    headers = {"Authorization": f"Key {FAL_API_KEY}", "Content-Type": "application/json"}
    payload = {"prompt": prompt, "aspect_ratio": "16:9"}

    async with http_session.post(url, json=payload, headers=headers, timeout=20) as resp:
        if resp.status not in (200, 201):
            raise Exception(f"Fal submit status {resp.status}: {(await resp.text())[:200]}")
        data = await resp.json()
        status_url = data.get("status_url")
        response_url = data.get("response_url")

    if not status_url:
        raise Exception("Fal не вернул status_url.")

    for _ in range(45):
        await asyncio.sleep(4)
        async with http_session.get(status_url, headers=headers, timeout=15) as resp:
            if resp.status == 200:
                data = await resp.json()

                if data.get("status", "").upper() == "COMPLETED":
                    video_url = (data.get("video") or {}).get("url")
                    if video_url:
                        return video_url

                    if response_url:
                        async with http_session.get(response_url, headers=headers, timeout=15) as final:
                            final_data = await final.json()
                            video_url = (final_data.get("video") or {}).get("url")
                            if video_url:
                                return video_url

                    raise Exception("Видео готово, но URL не найден.")

                if data.get("status", "").upper() == "FAILED":
                    raise Exception(str(data.get("error", "Fal render failed")))

    raise Exception("Таймаут генерации видео.")


class EvolutionCore:
    @staticmethod
    def verify(code: str) -> bool:
        required = ["async def main", "Dispatcher", "Bot", "dp.start_polling"]
        if not all(x in code for x in required):
            return False
        try:
            compile(code, "<main.py>", "exec")
            return True
        except SyntaxError:
            return False

    @staticmethod
    async def commit_and_deploy(new_code: str):
        if not GITHUB_TOKEN:
            return "❌ GITHUB_TOKEN отсутствует."
        if not RENDER_API_KEY:
            return "❌ RENDER_API_KEY отсутствует."
        if not RENDER_SERVICE_ID:
            return "❌ RENDER_SERVICE_ID отсутствует."
        if not EvolutionCore.verify(new_code):
            return "❌ Код не прошёл проверку целостности."

        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/main.py"
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

        async with http_session.get(url, headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return f"❌ GitHub GET ошибка: {resp.status}"
            sha = (await resp.json())["sha"]

        payload = {
            "message": "Evolution: update main.py",
            "content": base64.b64encode(new_code.encode()).decode(),
            "sha": sha
        }

        async with http_session.put(url, headers=headers, json=payload, timeout=20) as resp:
            if resp.status not in (200, 201):
                return f"❌ GitHub commit ошибка: {resp.status}"

        deploy_url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
        deploy_headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}

        async with http_session.post(deploy_url, headers=deploy_headers, timeout=20) as resp:
            if resp.status not in (200, 201, 202):
                return f"❌ Render deploy ошибка: {resp.status}"

        return "✅ Код обновлён в GitHub. Render начал деплой."


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(STRINGS["welcome"], parse_mode="HTML")


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    def c(v): return "🟢 LOADED" if v else "🔴 MISSING"

    out = (
        "📊 <b>AION MATRIX STATUS</b>\n\n"
        f"1 BOT_TOKEN: {c(BOT_TOKEN)}\n"
        f"2 OWNER_ID: {c(OWNER_ID)}\n"
        f"3 GROQ_API_KEY: {c(GROQ_API_KEY)}\n"
        f"4 CEREBRAS_API_KEY: {c(CEREBRAS_API_KEY)}\n"
        f"5 OPENROUTER_API_KEY: {c(OPENROUTER_API_KEY)}\n"
        f"6 TAVILY_API_KEY: {c(TAVILY_API_KEY)}\n"
        f"7 GITHUB_TOKEN: {c(GITHUB_TOKEN)}\n"
        f"8 RENDER_API_KEY: {c(RENDER_API_KEY)}\n"
        f"9 RENDER_SERVICE_ID: {c(RENDER_SERVICE_ID)}\n"
        f"10 CLOUDFLARE_API_TOKEN: {c(CLOUDFLARE_API_TOKEN)}\n"
        f"11 HUGGINGFACE_API_KEY: {c(HUGGINGFACE_API_KEY)}\n"
        f"12 FAL_API_KEY: {c(FAL_API_KEY)}\n\n"
        f"POLLINATIONS_ENABLED: {POLLINATIONS_ENABLED}\n"
        f"PORT: {PORT}"
    )
    await message.answer(out, parse_mode="HTML")


@dp.message(Command("image"))
async def cmd_image(message: types.Message):
    if not cooldown(message.from_user.id):
        return await message.answer(STRINGS["cooldown"])

    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /image [промпт]")

    status = await message.answer("🖼️ Генерация изображения...")
    try:
        url = await generate_image(prompt)
        await status.delete()
        await message.answer_photo(url, caption=f"🎨 <b>Prompt:</b> {html.escape(prompt)}", parse_mode="HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка image: {e}")


@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    if not cooldown(message.from_user.id):
        return await message.answer(STRINGS["cooldown"])

    prompt = message.text.replace("/music", "").strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /music [промпт]")

    status = await message.answer("🎼 Генерация музыки...")
    try:
        audio = await generate_music(prompt)
        await status.delete()
        await message.answer_audio(
            BufferedInputFile(audio, filename="aion_music.wav"),
            caption=f"🎼 <b>Prompt:</b> {html.escape(prompt)}",
            parse_mode="HTML"
        )
    except Exception as e:
        await status.edit_text(f"❌ Ошибка music: {e}")


@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    if not cooldown(message.from_user.id):
        return await message.answer(STRINGS["cooldown"])

    prompt = message.text.replace("/video", "").strip()
    if not prompt:
        return await message.answer("⚠️ Использование: /video [промпт]")

    status = await message.answer("🎥 Генерация видео...")
    try:
        url = await generate_video(prompt)
        await status.delete()
        await message.answer_video(url, caption=f"🎥 <b>Prompt:</b> {html.escape(prompt)}", parse_mode="HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка video: {e}")


@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    if not TAVILY_API_KEY:
        return await message.answer("❌ TAVILY_API_KEY отсутствует.")

    query = message.text.replace("/search", "").strip()
    if not query:
        return await message.answer("⚠️ Использование: /search [запрос]")

    status = await message.answer("🔍 Поиск...")
    try:
        payload = {"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 5}
        async with http_session.post("https://api.tavily.com/search", json=payload, timeout=20) as resp:
            data = await resp.json()

        out = f"🔍 <b>Результаты:</b> {html.escape(query)}\n\n"
        for r in data.get("results", []):
            out += f"🔹 <b>{html.escape(r.get('title', ''))}</b>\n{html.escape(r.get('content', ''))}\n{html.escape(r.get('url', ''))}\n\n"

        await status.delete()
        await send_split(message, out, "HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка search: {e}")


@dp.message(Command("github"))
async def cmd_github(message: types.Message):
    repo = message.text.replace("/github", "").strip()
    if not repo or "/" not in repo:
        return await message.answer("⚠️ Использование: /github owner/repo")

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    status = await message.answer("🐙 GitHub анализ...")
    try:
        async with http_session.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return await status.edit_text(f"❌ GitHub status {resp.status}")
            d = await resp.json()

        out = (
            f"🐙 <b>{html.escape(d.get('full_name', ''))}</b>\n"
            f"⭐ Stars: {d.get('stargazers_count')}\n"
            f"🍴 Forks: {d.get('forks_count')}\n"
            f"⚠️ Issues: {d.get('open_issues_count')}\n"
            f"🔗 {html.escape(d.get('html_url', ''))}"
        )
        await status.delete()
        await message.answer(out, parse_mode="HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка GitHub: {e}")


@dp.message(Command("render"))
async def cmd_render(message: types.Message):
    if not RENDER_API_KEY:
        return await message.answer("❌ RENDER_API_KEY отсутствует.")

    status = await message.answer("🧬 Render API...")
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}", "Accept": "application/json"}

    try:
        async with http_session.get("https://api.render.com/v1/services?limit=5", headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return await status.edit_text(f"❌ Render status {resp.status}")
            services = await resp.json()

        out = "🧬 <b>Render services:</b>\n\n"
        for s in services:
            srv = s.get("service", {})
            out += f"🖥️ <b>{html.escape(srv.get('name', ''))}</b>\nType: {html.escape(srv.get('type', ''))}\n\n"

        await status.delete()
        await message.answer(out, parse_mode="HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка Render: {e}")


@dp.message(Command("cloudflare"))
async def cmd_cloudflare(message: types.Message):
    if not CLOUDFLARE_API_TOKEN:
        return await message.answer("❌ CLOUDFLARE_API_TOKEN отсутствует.")

    status = await message.answer("☁️ Cloudflare API...")
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}

    try:
        async with http_session.get("https://api.cloudflare.com/client/v4/zones?status=active", headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return await status.edit_text(f"❌ Cloudflare status {resp.status}")
            zones = (await resp.json()).get("result", [])

        out = "☁️ <b>Cloudflare zones:</b>\n\n"
        for z in zones[:5]:
            out += f"🌐 <b>{html.escape(z.get('name', ''))}</b>\nID: <code>{html.escape(z.get('id', ''))}</code>\n\n"

        await status.delete()
        await message.answer(out or "Зон не найдено.", parse_mode="HTML")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка Cloudflare: {e}")


@dp.message(Command("evolve"))
async def cmd_evolve(message: types.Message):
    if not OWNER_ID:
        return await message.answer("❌ OWNER_ID не настроен.")
    if message.from_user.id != OWNER_ID:
        return await message.answer("⛔ Доступ запрещён.")
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.answer("⚠️ Ответь командой /evolve на сообщение с новым кодом main.py.")

    status = await message.answer("🛠 Проверка и деплой...")
    result = await EvolutionCore.commit_and_deploy(message.reply_to_message.text)
    await status.edit_text(result)


@dp.message()
async def chat_processor(message: types.Message):
    if not message.text:
        return await message.answer(STRINGS["only_text"])

    if message.text.startswith("/"):
        return

    save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)

    status = await message.answer(STRINGS["thinking"])
    history = get_memory(message.from_user.id)
    response = await run_ai_pipeline(message.text, history)

    save_memory(message.from_user.id, "user", message.text)
    save_memory(message.from_user.id, "assistant", response)

    await status.delete()
    await send_split(message, response)


async def handle_web_root(request):
    return web.Response(text="<h1>AION MATRIX ONLINE</h1>", content_type="text/html")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_web_root)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()


async def main():
    global bot, http_session

    if not BOT_TOKEN:
        sys.exit("BOT_TOKEN отсутствует.")

    bot = Bot(token=BOT_TOKEN)
    http_session = aiohttp.ClientSession()

    init_db()
    await start_web_server()

    try:
        await dp.start_polling(bot)
    finally:
        await http_session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

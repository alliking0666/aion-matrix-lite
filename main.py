from aiohttp import web
import os

PORT = int(os.getenv("PORT", 10000))

async def health(request):
    return web.Response(text="AION MATRIX LITE ONLINE")

app = web.Application()
app.router.add_get("/", health)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
import discord
from discord.ext import commands
import os
import asyncio
import logging
from aiohttp import web

# 👇【変更点1】パスを変更 (utilsフォルダから読み込む)
from utils.database import Database 

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord")

# --- 定数 ---
TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", 8000))
DATABASE_URL = os.getenv("DATABASE_URL") # DBのURLを取得しておく

class RumiaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix="/",
            intents=intents,
            help_command=None,
            activity=discord.Game(name="/help | 起動中...")
        )
        
        # 👇【変更点2】URLを引数として渡す
        self.db = Database(DATABASE_URL)
        
        self.start_time = discord.utils.utcnow()

    async def setup_hook(self):
        # 👇【変更点3】メソッド名を connect に変更
        await self.db.connect()
        
        self.prepare_fonts()
        self.create_cookie_file()
        self.loop.create_task(self.start_web_server())

        initial_extensions = [
            "cogs.basic",
            "cogs.moderation",
            "cogs.economy",
            "cogs.entertainment",
            "cogs.games",
            "cogs.voice_music",
            "cogs.general",
        ]
        
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                print(f"✅ Loaded {ext}")
            except Exception as e:
                print(f"❌ Failed to load {ext}: {e}")

        try:
            synced = await self.tree.sync()
            print(f"🔁 Synced {len(synced)} commands")
        except Exception as e:
            print(f"❌ Sync failed: {e}")

    async def on_ready(self):
        print(f"🚀 {self.user} としてログインしました (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name=f"/help | {len(self.guilds)} servers"))

    def prepare_fonts(self):
        if not os.path.exists("fonts"):
            os.makedirs("fonts")
        font_path = "fonts/NotoSansJP-Bold.ttf"
        if not os.path.exists(font_path):
            try:
                with open(font_path, "wb") as f:
                    f.write(b"") 
                print("✅ フォント準備完了 (ダミー)")
            except Exception as e:
                print(f"⚠️ フォント準備エラー: {e}")

    def create_cookie_file(self):
        cookies_env = os.getenv("COOKIES")
        if cookies_env:
            try:
                with open("cookies.txt", "w") as f:
                    f.write(cookies_env)
                print("✅ cookies.txt を環境変数から生成しました")
            except Exception as e:
                print(f"❌ cookies.txt 生成エラー: {e}")

    async def start_web_server(self):
        app = web.Application()
        app.router.add_get('/', self.handle_health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        print(f"🌍 Web Server started on port {PORT}")

    async def handle_health_check(self, request):
        return web.Response(text="OK", status=200)

if __name__ == "__main__":
    bot = RumiaBot()
    if not TOKEN:
        print("❌ エラー: DISCORD_TOKEN が設定されていません。")
    else:
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                import sys
                sys.exit(1)
            else:
                raise e

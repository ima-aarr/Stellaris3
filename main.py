import discord
from discord.ext import commands
import os
import sys
import asyncio
import base64
import aiohttp
from utils.database import Database
from utils.constants import COLOR_ERROR

# --- 環境設定 ---
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.isdigit()]

# --- YouTube Cookie 生成 (環境変数 -> ファイル) ---
# Koyeb等で環境変数にBase64エンコードしたCookieを入れることでファイルを生成
cookie_env = os.getenv("YOUTUBE_COOKIES")
if cookie_env:
    try:
        with open("cookies.txt", "wb") as f:
            f.write(base64.b64decode(cookie_env))
        print("✅ cookies.txt を環境変数から生成しました")
    except Exception as e:
        print(f"⚠️ Cookie生成エラー: {e}")

# --- フォント自動ダウンロード (日本語対応) ---
FONT_URL = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
FONT_PATH = "fonts/NotoSansJP-Bold.ttf"

async def download_font():
    if not os.path.exists("fonts"):
        os.makedirs("fonts")
    if not os.path.exists(FONT_PATH):
        print("📥 日本語フォントをダウンロード中...")
        async with aiohttp.ClientSession() as session:
            async with session.get(FONT_URL) as resp:
                if resp.status == 200:
                    with open(FONT_PATH, "wb") as f:
                        f.write(await resp.read())
                    print("✅ フォントダウンロード完了")
                else:
                    print("❌ フォントダウンロード失敗")

# --- Bot設定 ---
intents = discord.Intents.all()
intents.message_content = True

class RumiaBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or("r!"),
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        self.db = Database(DATABASE_URL)
        self.admin_ids = ADMIN_IDS
        self.start_time = discord.utils.utcnow()

    async def setup_hook(self):
        # データベース接続
        if DATABASE_URL:
            await self.db.connect()
        else:
            print("⚠️ DATABASE_URL が設定されていません。一部機能が動作しません。")

        # フォント準備
        await download_font()

        # Cogs読み込み
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

        # コマンド同期
        try:
            synced = await self.tree.sync()
            print(f"🔁 Synced {len(synced)} commands")
        except Exception as e:
            print(f"❌ Sync failed: {e}")

    async def on_ready(self):
        print(f"🚀 {self.user} としてログインしました (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="/help | Rumia Bot"))

bot = RumiaBot()

# --- グローバルエラーハンドリング ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if interaction.response.is_done():
        func = interaction.followup.send
    else:
        func = interaction.response.send_message

    if isinstance(error, discord.app_commands.CommandOnCooldown):
        await func(f"⏳ クールダウン中: あと {error.retry_after:.2f}秒待ってください。", ephemeral=True)
    elif isinstance(error, discord.app_commands.MissingPermissions):
        await func("❌ 権限がありません。", ephemeral=True)
    else:
        embed = discord.Embed(title="エラーが発生しました", description=f"```\n{error}\n```", color=COLOR_ERROR)
        await func(embed=embed, ephemeral=True)
        # エラーログ出力
        print(f"❌ Error in {interaction.command.name}: {error}")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN が設定されていません。")
    else:
        bot.run(TOKEN)

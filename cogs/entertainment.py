import discord
from discord import app_commands
from discord.ext import commands
import random
import io
import aiohttp
import textwrap
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
from utils.constants import get_topic, get_punishment, OMIKUJI_RESULTS, COLOR_MAIN

class Entertainment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Fakeコマンド用クールダウン管理 {user_id: timestamp}
        self.fake_cooldowns = {}

    # --- おみくじ機能 (カスタム設定対応) ---
    omikuji_group = app_commands.Group(name="omikuji", description="おみくじ機能")

    @omikuji_group.command(name="draw", description="おみくじを引きます")
    async def omikuji_draw(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # カスタム設定があるか確認 (DB実装想定だが今回は簡易化のためデフォルト使用)
        # 本来はDBからguild_idでSELECTする
        weights = [x['prob'] for x in OMIKUJI_RESULTS]
        result = random.choices(OMIKUJI_RESULTS, weights=weights, k=1)[0]
        
        embed = discord.Embed(title="⛩️ おみくじ結果", color=0xff0000)
        embed.add_field(name=result['name'], value=result['desc'])
        embed.set_footer(text=f"運勢: {result['name']} | {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    @omikuji_group.command(name="list", description="現在のおみくじ確率一覧")
    async def omikuji_list(self, interaction: discord.Interaction):
        text = ""
        for item in OMIKUJI_RESULTS:
            text += f"・**{item['name']}**: {item['prob']}% - {item['desc']}\n"
        embed = discord.Embed(title="📜 おみくじ設定一覧 (デフォルト)", description=text, color=COLOR_MAIN)
        await interaction.response.send_message(embed=embed)

    # --- Make it Quote (日本語完全対応版) ---
    @app_commands.command(name="makeitquote", description="名言画像を生成します (日本語対応)")
    @app_commands.describe(user="名言を言わせたいユーザー", text="内容")
    async def makeitquote(self, interaction: discord.Interaction, user: discord.Member, text: str):
        await interaction.response.defer()
        
        try:
            # アバター取得
            async with aiohttp.ClientSession() as session:
                async with session.get(user.display_avatar.url) as resp:
                    avatar_bytes = await resp.read()
            
            # 画像生成 (ブロッキング回避のためExecutorで実行)
            loop = self.bot.loop
            img_bytes = await loop.run_in_executor(None, self._generate_quote_image, avatar_bytes, user.display_name, text, user)
            
            file = discord.File(fp=io.BytesIO(img_bytes), filename="quote.png")
            await interaction.followup.send(file=file)
        except Exception as e:
            await interaction.followup.send(f"❌ 生成エラー: {e}")

    def _generate_quote_image(self, avatar_bytes, username, text, user_obj):
        # 1. ベースキャンバス (黒背景)
        W, H = 1200, 630
        base = Image.new("RGB", (W, H), (20, 20, 20))
        draw = ImageDraw.Draw(base)

        # 2. アバター背景 (拡大・ぼかし・暗転)
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        bg_avatar = avatar.resize((W, W))
        bg_avatar = bg_avatar.crop((0, (W-H)//2, W, (W-H)//2 + H))
        bg_avatar = bg_avatar.filter(ImageFilter.GaussianBlur(25)) # ぼかし
        
        # オーバーレイ (暗くする)
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 150))
        base.paste(bg_avatar, (0, 0))
        base.paste(overlay, (0, 0), overlay)

        # 3. メインアバター (円形切り抜き)
        icon_size = 250
        avatar = avatar.resize((icon_size, icon_size))
        mask = Image.new("L", (icon_size, icon_size), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, icon_size, icon_size), fill=255)
        
        # 配置: 左側中央
        icon_x = 100
        icon_y = (H - icon_size) // 2
        base.paste(avatar, (icon_x, icon_y), mask)

        # 4. テキスト描画 (フォント設定)
        # main.pyでダウンロードしたフォントを使用
        font_path = "fonts/NotoSansJP-Bold.ttf"
        try:
            # テキスト量に応じてフォントサイズ調整
            font_size = 60 if len(text) < 50 else 45
            font = ImageFont.truetype(font_path, font_size)
            name_font = ImageFont.truetype(font_path, 35)
            watermark_font = ImageFont.truetype(font_path, 20)
        except:
            font = ImageFont.load_default()
            name_font = font
            watermark_font = font

        # テキスト折り返し処理
        text_area_width = 700
        text_x = 400
        wrapper = textwrap.TextWrapper(width=18 if font_size > 50 else 25) 
        lines = wrapper.wrap(text)
        
        # テキストの高さ計算して中央揃え
        total_text_h = len(lines) * (font_size * 1.5)
        current_y = (H - total_text_h) // 2 - 20

        for line in lines:
            # 影付き
            draw.text((text_x + 3, current_y + 3), line, font=font, fill=(0, 0, 0))
            draw.text((text_x, current_y), line, font=font, fill=(255, 255, 255))
            current_y += font_size * 1.5

        # 名前
        name_text = f"- {username}"
        draw.text((text_x, current_y + 20), name_text, font=name_font, fill=(180, 180, 180))

        # Watermark (Rumia Bot) 右下
        draw.text((W - 150, H - 40), "Lumina", font=watermark_font, fill=(100, 100, 100))
        
        # バイト列へ
        buffer = io.BytesIO()
        base.save(buffer, format="PNG")
        return buffer.getvalue()

    # --- Fake Webhook (なりすまし) ---
    @app_commands.command(name="fake", description="ユーザーになりすまして発言します")
    async def fake(self, interaction: discord.Interaction, user: discord.Member, message: str):
        # クールダウンチェック (5秒)
        now = discord.utils.utcnow().timestamp()
        last_time = self.fake_cooldowns.get(interaction.user.id, 0)
        if now - last_time < 5:
            return await interaction.response.send_message(f"⏳ クールダウン中です。あと {5 - int(now - last_time)}秒待ってください。", ephemeral=True)
        
        self.fake_cooldowns[interaction.user.id] = now
        await interaction.response.defer(ephemeral=True)

        try:
            # Webhook取得または作成
            webhooks = await interaction.channel.webhooks()
            webhook = discord.utils.get(webhooks, name="RumiaFake")
            if not webhook:
                webhook = await interaction.channel.create_webhook(name="RumiaFake")

            await webhook.send(
                content=message,
                username=user.display_name,
                avatar_url=user.display_avatar.url,
                allowed_mentions=discord.AllowedMentions.none() # メンション無効化
            )
            await interaction.followup.send("✅ 送信しました", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 送信失敗: {e}", ephemeral=True)

    # --- その他エンタメ ---
    @app_commands.command(name="topic", description="話題を提供します (700種以上)")
    async def topic(self, interaction: discord.Interaction):
        # constants.pyのロジックでランダム生成
        t = get_topic() 
        embed = discord.Embed(title="💡 話題の提案", description=t, color=COLOR_MAIN)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="punishment", description="罰ゲームをランダム表示")
    async def punishment(self, interaction: discord.Interaction):
        p = get_punishment()
        embed = discord.Embed(title="☠️ 罰ゲーム命令", description=f"# {p}", color=0x000000)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Entertainment(bot))

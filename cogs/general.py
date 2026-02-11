import discord
from discord import app_commands
from discord.ext import commands
import datetime
from deep_translator import GoogleTranslator
from utils.constants import COLOR_MAIN

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- ℹ️ 情報取得系 ---
    
    @app_commands.command(name="serverinfo", description="サーバーの詳細情報を表示します")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=f"🏰 {guild.name} の情報", color=COLOR_MAIN)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)

        # メンバー内訳
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        online = len([m for m in guild.members if m.status != discord.Status.offline])

        embed.add_field(name="🆔 サーバーID", value=guild.id, inline=True)
        embed.add_field(name="👑 オーナー", value=guild.owner.mention, inline=True)
        embed.add_field(name="📅 作成日", value=guild.created_at.strftime('%Y/%m/%d'), inline=True)
        
        embed.add_field(name="👥 メンバー", value=f"合計: {guild.member_count}\n(人: {humans} / Bot: {bots})", inline=True)
        embed.add_field(name="🟢 アクティブ", value=f"{online} 人", inline=True)
        embed.add_field(name="🛡️ セキュリティ", value=str(guild.verification_level).title(), inline=True)
        
        embed.add_field(name="💬 チャンネル", value=f"Text: {len(guild.text_channels)} | Voice: {len(guild.voice_channels)}", inline=True)
        embed.add_field(name="🎭 ロール数", value=len(guild.roles), inline=True)
        embed.add_field(name="🚀 ブースト", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} Boosts)", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="ユーザーの詳細情報を表示します")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        
        roles = [role.mention for role in target.roles if role.name != "@everyone"]
        roles.reverse() # 上位ロールから表示
        role_str = ", ".join(roles[:10]) # 多すぎる場合は省略
        if len(roles) > 10: role_str += f" 他 {len(roles)-10}個"
        if not role_str: role_str = "なし"

        embed = discord.Embed(title=f"👤 {target.display_name} の情報", color=target.color)
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(name="ユーザーID", value=target.id, inline=True)
        embed.add_field(name="アカウント作成", value=target.created_at.strftime('%Y/%m/%d'), inline=True)
        embed.add_field(name="サーバー参加", value=target.joined_at.strftime('%Y/%m/%d'), inline=True)
        
        embed.add_field(name=f"ロール ({len(roles)})", value=role_str, inline=False)
        
        # 権限チェック
        key_perms = []
        if target.guild_permissions.administrator: key_perms.append("管理者")
        if target.guild_permissions.ban_members: key_perms.append("BAN権限")
        if target.guild_permissions.manage_guild: key_perms.append("サーバー管理")
        
        if key_perms:
            embed.add_field(name="🔑 主な権限", value=", ".join(key_perms), inline=False)

        await interaction.response.send_message(embed=embed)

    # --- 🌐 翻訳機能 ---

    @app_commands.command(name="translate", description="テキストを翻訳します")
    @app_commands.describe(text="翻訳したい文章", target="言語コード (例: en, ja, ko, zh-CN)")
    async def translate(self, interaction: discord.Interaction, text: str, target: str = "ja"):
        await interaction.response.defer()
        try:
            # deep-translatorを使用
            translator = GoogleTranslator(source='auto', target=target)
            result = translator.translate(text)
            
            embed = discord.Embed(color=COLOR_MAIN)
            embed.add_field(name="原文", value=text, inline=False)
            embed.add_field(name=f"翻訳 ({target})", value=result, inline=False)
            embed.set_footer(text=f"Translated by Google Translate API")
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ 翻訳エラー: 言語コードが間違っている可能性があります。\n(例: 日本語=ja, 英語=en, 韓国語=ko)\nエラー: {e}")

    # --- 🛠️ ユーティリティ ---

    @app_commands.command(name="say", description="Botに好きな言葉を言わせます")
    @app_commands.describe(message="言わせる内容", channel="送信先チャンネル(省略可)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(self, interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        await target_channel.send(message)
        await interaction.response.send_message("✅ 送信しました", ephemeral=True)

    @app_commands.command(name="embed_create", description="リッチな埋め込みメッセージを作成します")
    async def embed_create(self, interaction: discord.Interaction):
        # モーダルウィンドウを表示
        await interaction.response.send_modal(EmbedModal())

# --- Embed作成用モーダル ---
class EmbedModal(discord.ui.Modal, title="Embed作成ツール"):
    title_input = discord.ui.TextInput(label="タイトル", placeholder="タイトルを入力...", required=True)
    description_input = discord.ui.TextInput(label="本文", style=discord.TextStyle.paragraph, placeholder="本文を入力...", required=True)
    color_input = discord.ui.TextInput(label="カラーコード (HEX)", placeholder="#ff0000", required=False, max_length=7)
    footer_input = discord.ui.TextInput(label="フッター (省略可)", required=False)
    image_input = discord.ui.TextInput(label="画像URL (省略可)", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # カラーコード処理
            color_val = 0x2f3136 # デフォルトグレー
            if self.color_input.value:
                color_str = self.color_input.value.replace("#", "")
                color_val = int(color_str, 16)
            
            embed = discord.Embed(title=self.title_input.value, description=self.description_input.value, color=color_val)
            
            if self.footer_input.value:
                embed.set_footer(text=self.footer_input.value)
            
            if self.image_input.value:
                embed.set_image(url=self.image_input.value)
            
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("✅ Embedを作成しました", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ エラーが発生しました: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(General(bot))

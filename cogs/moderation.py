import discord
from discord import app_commands
from discord.ext import commands
import datetime
import re
from collections import defaultdict, deque
from utils.constants import COLOR_ERROR, COLOR_WARN, COLOR_SUCCESS

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # スパム検知用キャッシュ {guild_id: {user_id: deque([timestamp, ...])}}
        self.spam_check = defaultdict(lambda: defaultdict(lambda: deque(maxlen=10)))
        # ホワイトリストキャッシュ {guild_id: [user_ids]}
        self.whitelists = defaultdict(list)

    # --- 🛡️ 基本処罰コマンド ---

    @app_commands.command(name="kick", description="ユーザーをサーバーからキックします")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ 自分より上位のメンバーはキックできません。", ephemeral=True)
        
        await member.kick(reason=reason)
        await interaction.response.send_message(f"🚪 **{member}** をキックしました。\n理由: {reason}")
        await self.log_action(interaction.guild, "キック", f"対象: {member}\n実行者: {interaction.user}\n理由: {reason}", COLOR_ERROR)

    @app_commands.command(name="ban", description="ユーザーを永久BANします")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "理由なし"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ 自分より上位のメンバーはBANできません。", ephemeral=True)

        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 **{member}** をBANしました。\n理由: {reason}")
        await self.log_action(interaction.guild, "BAN", f"対象: {member}\n実行者: {interaction.user}\n理由: {reason}", COLOR_ERROR)

    @app_commands.command(name="unban", description="ユーザーのBANを解除します")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(f"✅ **{user}** のBANを解除しました。")
            await self.log_action(interaction.guild, "BAN解除", f"対象: {user}\n実行者: {interaction.user}", COLOR_SUCCESS)
        except:
            await interaction.response.send_message("❌ ユーザーが見つからないか、解除できませんでした。", ephemeral=True)

    @app_commands.command(name="timeout", description="ユーザーをタイムアウト(ミュート)します")
    @app_commands.describe(minutes="分数 (例: 10, 60, 1440)")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "理由なし"):
        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message("❌ 上位メンバーはタイムアウトできません。", ephemeral=True)

        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🤐 **{member}** を {minutes}分間 タイムアウトしました。")
        await self.log_action(interaction.guild, "タイムアウト", f"対象: {member}\n時間: {minutes}分\n理由: {reason}", COLOR_WARN)

    @app_commands.command(name="untimeout", description="タイムアウトを解除します")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(f"🗣️ **{member}** のタイムアウトを解除しました。")

    @app_commands.command(name="delete", description="メッセージを一括削除します (Clear)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        if amount > 100: amount = 100
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ {len(deleted)}件のメッセージを削除しました。", ephemeral=True)
        await self.log_action(interaction.guild, "メッセージ削除", f"チャンネル: {interaction.channel.mention}\n件数: {len(deleted)}\n実行者: {interaction.user}", COLOR_WARN)

    # --- ⚙️ 設定コマンド (ログ・AutoMod) ---

    @app_commands.command(name="logs_setting", description="ログチャンネルを設定します")
    @app_commands.checks.has_permissions(administrator=True)
    async def logs_setting(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.bot.db.execute(
            "INSERT INTO guild_settings (guild_id, log_channel_id) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET log_channel_id = $2",
            interaction.guild.id, channel.id
        )
        await interaction.response.send_message(f"✅ ログチャンネルを {channel.mention} に設定しました。")

    @app_commands.command(name="automod_setting", description="AutoMod(荒らし対策)の設定")
    @app_commands.choices(feature=[
        app_commands.Choice(name="禁止用語フィルター", value="bad_words"),
        app_commands.Choice(name="スパム(連投)フィルター", value="spam")
    ])
    @app_commands.describe(enabled="有効/無効", content="禁止用語を設定する場合のみ単語をカンマ区切りで入力")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_setting(self, interaction: discord.Interaction, feature: str, enabled: bool, content: str = None):
        if feature == "bad_words":
            await self.bot.db.execute(
                "INSERT INTO guild_settings (guild_id, bad_words) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET bad_words = $2",
                interaction.guild.id, content or ""
            )
            # 有効化フラグは別途管理しても良いが、ここでは単語があるかないかで判定簡易化も可。
            # 今回は明示的な有効化フラグも更新
            await self.bot.db.execute("UPDATE guild_settings SET automod_enabled = $1 WHERE guild_id = $2", enabled, interaction.guild.id)
            msg = f"禁止用語を更新: {content}" if content else "禁止用語設定を変更"
            
        elif feature == "spam":
            await self.bot.db.execute(
                "INSERT INTO guild_settings (guild_id, spam_filter_enabled) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET spam_filter_enabled = $2",
                interaction.guild.id, enabled
            )
            msg = "スパムフィルターを有効化" if enabled else "スパムフィルターを無効化"

        await interaction.response.send_message(f"🛡️ **AutoMod設定**: {msg}")

    # --- 🚨 イベントリスナー (AutoMod & Log) ---

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        # 設定取得 (キャッシュ推奨だが簡易実装としてDB都度確認または内部キャッシュ)
        # 本格運用では on_ready で全サーバー設定をメモリに乗せるのが良い
        settings = await self.bot.db.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", message.guild.id)
        if not settings:
            return

        # 1. 禁止用語チェック
        if settings['bad_words']:
            bad_words = settings['bad_words'].split(',')
            if any(word.strip() in message.content for word in bad_words if word.strip()):
                try:
                    await message.delete()
                    await message.channel.send(f"⚠️ {message.author.mention} 禁止用語が含まれています！", delete_after=5)
                    await self.log_action(message.guild, "AutoMod削除", f"ユーザー: {message.author}\n内容: {message.content}", COLOR_ERROR)
                    return # 処理終了
                except:
                    pass

        # 2. 重複文字・連投スパムチェック (簡易版)
        if settings['spam_filter_enabled']:
            # 10文字以上の同じ文字が5回以上連続 -> 単純な正規表現でチェック
            if re.search(r'(.)\1{9,}', message.content):
                try:
                    await message.delete()
                    await message.channel.send(f"⚠️ {message.author.mention} 文字の繰り返しが多すぎます。", delete_after=3)
                    return
                except:
                    pass
            
            # 連投検知
            now = datetime.datetime.now().timestamp()
            history = self.spam_check[message.guild.id][message.author.id]
            history.append(now)
            
            # 過去5秒以内に5件以上
            if len(history) >= 5 and (history[-1] - history[0] < 5):
                try:
                    await message.channel.send(f"🚫 {message.author.mention} 連投をやめてください！ (タイムアウト)", delete_after=5)
                    # 1分タイムアウト
                    await message.author.timeout(datetime.timedelta(minutes=1), reason="AutoMod: スパム検知")
                    history.clear()
                    await self.log_action(message.guild, "AutoMod処罰", f"ユーザー: {message.author}\n理由: 連投スパム", COLOR_ERROR)
                except:
                    pass

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild: return
        await self.log_action(message.guild, "メッセージ削除", f"場所: {message.channel.mention}\nユーザー: {message.author}\n内容: {message.content}", COLOR_WARN)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild or before.content == after.content: return
        await self.log_action(before.guild, "メッセージ編集", f"場所: {before.channel.mention}\nユーザー: {before.author}\n[前]: {before.content}\n[後]: {after.content}", 0x3498db)

    async def log_action(self, guild, action, details, color):
        """ログチャンネルにEmbedを送信"""
        row = await self.bot.db.fetchrow("SELECT log_channel_id FROM guild_settings WHERE guild_id = $1", guild.id)
        if row and row['log_channel_id']:
            channel = guild.get_channel(row['log_channel_id'])
            if channel:
                embed = discord.Embed(title=f"📝 {action}", description=details, color=color, timestamp=discord.utils.utcnow())
                embed.set_footer(text=f"Server: {guild.name}")
                await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))

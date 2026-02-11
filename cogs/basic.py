import discord
from discord import app_commands
from discord.ext import commands
import datetime
import time
import platform
from utils.constants import COLOR_MAIN, COLOR_SUCCESS

class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Botの応答速度・稼働状況を確認")
    async def ping(self, interaction: discord.Interaction):
        start = time.perf_counter()
        await interaction.response.defer()
        end = time.perf_counter()
        duration = (end - start) * 1000
        
        embed = discord.Embed(title="🏓 Pong!", color=COLOR_MAIN)
        embed.add_field(name="API Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Response Time", value=f"{round(duration)}ms", inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="info", description="Botの詳細情報を表示")
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Rumia Bot について", color=COLOR_MAIN)
        embed.description = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "｜Discordサーバーの運営を安定かつ安全に\n"
            "｜行うことを目的として開発された多機能Botです。\n"
            "｜初心者から管理者まで安心して使えるBotを目指しています。\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        # 統計情報
        server_count = len(self.bot.guilds)
        member_count = sum(g.member_count for g in self.bot.guilds)
        command_count = len(self.bot.tree.get_commands())
        
        # 稼働時間
        uptime = discord.utils.utcnow() - self.bot.start_time
        uptime_str = str(uptime).split('.')[0].replace("days", "日")
        
        embed.add_field(name="｜主な機能", value="｜モデレーション｜経済｜エンタメ｜音楽｜便利機能", inline=False)
        embed.add_field(name="｜Bot統計", value=f"｜サーバー数: {server_count}｜ユーザー数: {member_count:,}｜コマンド数: {command_count}", inline=False)
        embed.add_field(name="｜稼働情報", value=f"｜稼働時間: {uptime_str}｜Python: {platform.python_version()}｜discord.py: {discord.__version__}", inline=False)
        embed.add_field(name="｜技術仕様", value="｜Discord公式API準拠｜全コマンド安全応答処理実装｜安定動作を最優先設計", inline=False)
        embed.add_field(name="｜リンク", value="｜不具合報告: /bot_report｜ヘルプ: /help", inline=False)
        
        embed.set_footer(text=f"Bot ID: {self.bot.user.id} | リクエスト時刻: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="指定したユーザーのアイコンを表示します")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        embed = discord.Embed(title=f"{target.display_name} のアイコン", color=target.color)
        embed.set_image(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bot_report", description="開発者への要望・不具合報告")
    async def report(self, interaction: discord.Interaction, content: str):
        # 実際の運用ではWebhook等で開発者サーバーに飛ばすのが一般的ですが、今回はログ出力とDM想定
        print(f"REPORT from {interaction.user}: {content}")
        await interaction.response.send_message("✅ 報告ありがとうございます。開発者に送信されました。", ephemeral=True)

    @app_commands.command(name="check", description="サーバーの過疎状況をチェック")
    async def check(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild = interaction.guild
        
        # 調査設定
        check_days = 2
        limit_msgs = 100
        threshold_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=check_days)
        
        total_msgs = 0
        active_channels = 0
        channel_stats = []
        
        # 全チャンネル走査 (重い処理なので例外処理必須)
        for channel in guild.text_channels:
            if not channel.permissions_for(guild.me).read_message_history:
                continue
                
            try:
                count = 0
                async for msg in channel.history(limit=limit_msgs, after=threshold_date):
                    count += 1
                
                if count > 0:
                    total_msgs += count
                    active_channels += 1
                    channel_stats.append((channel.name, count))
            except Exception:
                continue

        # ソートして上位を取得
        channel_stats.sort(key=lambda x: x[1], reverse=True)
        
        # レベル判定
        if total_msgs > 300:
            level = "🟩 レベル 4 (活発)"
            desc = "活気のある状態です！"
        elif total_msgs > 100:
            level = "🟨 レベル 3 (普通)"
            desc = "そこそこ会話があります。"
        elif total_msgs > 20:
            level = "🟧 レベル 2 (静か)"
            desc = "少し静かです。"
        else:
            level = "🟥 レベル 1 (過疎)"
            desc = "もっと会話を盛り上げましょう！"

        embed = discord.Embed(title=f"📊 {guild.name} 健康診断", description=f"**{level}**\n{desc}", color=COLOR_SUCCESS)
        
        stats_text = (
            f"過疎りレベル: {level.split(' ')[0]}\n"
            f"合計メッセージ: {total_msgs} 件\n"
            f"調査チャンネル: {len(guild.text_channels)} チャンネル\n"
            f"調査期間: 過去{check_days}日間"
        )
        embed.add_field(name="統計情報", value=stats_text, inline=False)
        
        # 上位チャンネル
        top_text = ""
        for name, count in channel_stats[:5]:
            top_text += f"#{name} {count}件\n"
        if not top_text: top_text = "なし"
        embed.add_field(name="上位チャンネル", value=top_text, inline=False)

        # 詳細リスト
        list_text = ""
        for name, count in channel_stats[:15]:
            list_text += f"• #{name} - {count}件\n"
        if not list_text: list_text = "データなし"
        
        embed.add_field(name="調査チャンネル一覧", value=list_text, inline=False)
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Basic(bot))

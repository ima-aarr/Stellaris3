import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
from collections import deque
from utils.constants import COLOR_MAIN, COLOR_ERROR, COLOR_SUCCESS

# --- yt-dlp 設定 (Cookie対応・エラー回避) ---
YTDL_OPTS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    # Cookieファイルが存在する場合のみ読み込む (main.pyで生成済み)
    'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
    # ユーザーエージェント偽装 (Bot検知回避)
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
}

# --- FFmpeg 設定 (再接続オプションで安定化) ---
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class VoiceMusic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # サーバーごとのキュー {guild_id: deque([source, ...])}
        self.queues = {}
        # ループ設定 {guild_id: bool}
        self.loops = {}
        # 現在再生中の曲情報 {guild_id: title}
        self.now_playing = {}
        # 音量設定 {guild_id: float(0.0-1.0)}
        self.volumes = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return self.queues[guild_id]

    def play_next(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        
        if not queue:
            self.now_playing.pop(guild_id, None)
            return

        # 次の曲を取得
        source, title = queue.popleft()
        self.now_playing[guild_id] = title
        
        vc = interaction.guild.voice_client
        if not vc:
            return

        # 音量適用
        volume = self.volumes.get(guild_id, 0.5) # デフォルト50%
        source.volume = volume

        # 再生終了後のコールバック
        def after_playing(error):
            if error:
                print(f"Player error: {error}")
            # ループ有効なら再度キューに追加（簡易実装）
            # 本格的なループはSourceを再生成する必要があるため、今回はキュー消化のみ
            self.play_next(interaction)

        vc.play(source, after=after_playing)
        
        # テキストチャンネルに通知（非同期で送信するために工夫が必要だが、ここではログのみ）
        print(f"🎵 Now playing in {interaction.guild.name}: {title}")

    @app_commands.command(name="join", description="ボイスチャンネルに参加します")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ まずあなたがボイスチャンネルに参加してください。", ephemeral=True)
        
        channel = interaction.user.voice.channel
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()
        
        await interaction.response.send_message(f"🔊 **{channel.name}** に参加しました。")

    @app_commands.command(name="leave", description="ボイスチャンネルから退出します")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            self.queues.pop(interaction.guild.id, None)
            self.now_playing.pop(interaction.guild.id, None)
            await interaction.response.send_message("👋 退出しました。")
        else:
            await interaction.response.send_message("❌ ボイスチャンネルに参加していません。", ephemeral=True)

    @app_commands.command(name="music_play", description="音楽を再生します (YouTube)")
    @app_commands.describe(query="曲名またはURL")
    async def music_play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        
        # VC参加確認
        if not interaction.user.voice:
            return await interaction.followup.send("❌ ボイスチャンネルに参加してください。")
        
        if not interaction.guild.voice_client:
            try:
                await interaction.user.voice.channel.connect()
            except Exception as e:
                return await interaction.followup.send(f"❌ 接続エラー: {e}")

        vc = interaction.guild.voice_client
        
        # 検索と抽出
        try:
            with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                info = ydl.extract_info(query, download=False)
                
                # プレイリストの場合は最初の動画
                if 'entries' in info:
                    info = info['entries'][0]
                
                url = info['url']
                title = info.get('title', 'Unknown Title')
                
                # FFmpegオーディオソース作成
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
                )
                # 音量初期設定
                source.volume = self.volumes.get(interaction.guild.id, 0.5)

                queue = self.get_queue(interaction.guild.id)
                
                if vc.is_playing() or vc.is_paused():
                    queue.append((source, title))
                    embed = discord.Embed(title="🎵 予約しました", description=f"**{title}**", color=COLOR_MAIN)
                    await interaction.followup.send(embed=embed)
                else:
                    queue.append((source, title)) # play_nextでpopするため一度入れる
                    self.play_next(interaction)
                    embed = discord.Embed(title="▶️ 再生開始", description=f"**{title}**", color=COLOR_SUCCESS)
                    await interaction.followup.send(embed=embed)
                    
        except Exception as e:
            # エラーログ詳細
            error_msg = str(e)
            if "Sign in" in error_msg:
                msg = "❌ YouTubeの認証エラーが発生しました。Cookieの設定を確認してください。"
            else:
                msg = f"❌ 再生エラー: {error_msg}"
            await interaction.followup.send(msg)

    @app_commands.command(name="music_stop", description="音楽を停止し、キューをクリアします")
    async def music_stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            self.queues[interaction.guild.id].clear()
            await interaction.response.send_message("⏹️ 停止しました。")
        else:
            await interaction.response.send_message("❌ 再生していません。", ephemeral=True)

    @app_commands.command(name="music_volume", description="音量を調整します (1-100)")
    @app_commands.describe(volume="音量 (デフォルト: 50)")
    async def music_volume(self, interaction: discord.Interaction, volume: int):
        if not 1 <= volume <= 100:
            return await interaction.response.send_message("❌ 1〜100の間で指定してください。", ephemeral=True)
        
        vol_float = volume / 100
        self.volumes[interaction.guild.id] = vol_float
        
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = vol_float
            
        await interaction.response.send_message(f"🔊 音量を **{volume}%** に設定しました。")

    @app_commands.command(name="tts_join", description="読み上げを開始します (簡易版)")
    async def tts_join(self, interaction: discord.Interaction):
        # 簡易実装: gTTSなどの外部ライブラリがない場合を考慮し、
        # ここでは接続機能のみを提供し、将来的に拡張可能な構造にします。
        await self.join(interaction)

    # --- 自動退室リスナー ---
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Bot自身の更新は無視
        if member.id == self.bot.user.id:
            return
            
        # Botがいるチャンネルのメンバー数を確認
        voice_client = member.guild.voice_client
        if voice_client and voice_client.channel:
            # Bot以外のメンバーが0人になったら
            if len([m for m in voice_client.channel.members if not m.bot]) == 0:
                await asyncio.sleep(30) # 30秒待機
                # 再確認
                if len([m for m in voice_client.channel.members if not m.bot]) == 0:
                    await voice_client.disconnect()
                    # ログなどを送る処理を入れることも可能

async def setup(bot):
    await bot.add_cog(VoiceMusic(bot))

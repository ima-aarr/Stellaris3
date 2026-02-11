import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
from utils.constants import COLOR_MAIN, QUESTS, OMIKUJI_RESULTS

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    game_group = app_commands.Group(name="game", description="ミニゲーム集")

    # --- 1. Bot Quest (RPG) ---
    @game_group.command(name="bot-quest", description="Botからのクエストに挑戦 (RPG)")
    async def bot_quest(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # ランダムにクエスト選出
        quest = random.choice(QUESTS)
        
        embed = discord.Embed(title=f"🛡️ クエスト受注: {quest['name']}", color=COLOR_MAIN)
        embed.add_field(name="ランク", value=quest['rank'], inline=True)
        embed.add_field(name="成功率", value=f"{quest['success_rate']}%", inline=True)
        embed.add_field(name="報酬", value=f"¥{quest['reward_min']} - ¥{quest['reward_max']}", inline=True)
        
        view = QuestView(interaction.user.id, quest, self.bot)
        await interaction.followup.send(embed=embed, view=view)

    # --- 2. Emerald (宝探し) ---
    @game_group.command(name="emerald", description="エメラルドを探します")
    async def emerald(self, interaction: discord.Interaction):
        # 3つの箱から1つ選ぶイメージ
        result = random.choices(["ハズレ", "エメラルド", "ダイヤモンド"], weights=[60, 30, 10], k=1)[0]
        
        if result == "ハズレ":
            msg = "🕸️ 何もありませんでした..."
            color = 0x95a5a6
        elif result == "エメラルド":
            amt = random.randint(500, 1000)
            await self.bot.db.update_money(interaction.user.id, cash=amt)
            msg = f"🟢 **エメラルド発見！** ¥{amt:,} で売れました！"
            color = 0x2ecc71
        else:
            amt = random.randint(2000, 5000)
            await self.bot.db.update_money(interaction.user.id, cash=amt)
            msg = f"💎 **ダイヤモンド発見！** ¥{amt:,} の大金です！"
            color = 0x3498db
            
        embed = discord.Embed(description=msg, color=color)
        await interaction.response.send_message(embed=embed)

    # --- 3. Math Quiz (計算) ---
    @game_group.command(name="math-quiz", description="算数クイズを出題")
    async def math_quiz(self, interaction: discord.Interaction):
        ops = ['+', '-', '*']
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        op = random.choice(ops)
        
        expr = f"{a} {op} {b}"
        answer = eval(expr)
        
        await interaction.response.send_message(f"🧠 **問題**: `{expr} = ?` (10秒以内に数字のみ入力)")
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=10.0)
            if int(msg.content) == answer:
                # 正解報酬
                reward = 300
                await self.bot.db.update_money(interaction.user.id, cash=reward)
                await msg.reply(f"⭕ **正解！** 報酬: ¥{reward}")
            else:
                await msg.reply(f"❌ **不正解...** 答えは `{answer}` でした。")
        except asyncio.TimeoutError:
            await interaction.followup.send(f"⏰ 時間切れ！ 答えは `{answer}` でした。")

    # --- 4. Guess (数当て) ---
    @game_group.command(name="guess", description="1〜10の数字を当ててください")
    async def guess(self, interaction: discord.Interaction):
        target = random.randint(1, 10)
        await interaction.response.send_message("🔢 1から10の数字を思い浮かべました。何でしょう？ (1回勝負)")
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel and m.content.isdigit()

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=10.0)
            val = int(msg.content)
            if val == target:
                await self.bot.db.update_money(interaction.user.id, cash=500)
                await msg.reply("🎯 **大当たり！** ¥500 ゲット！")
            else:
                await msg.reply(f"💨 ハズレ... 正解は `{target}` でした。")
        except asyncio.TimeoutError:
            await interaction.followup.send(f"⏰ 時間切れ！ 正解は `{target}` でした。")

    # --- 5. Love Calc (恋愛計算) ---
    @game_group.command(name="lovecalc", description="二人の相性を計算します")
    async def lovecalc(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        # 名前を使ってハッシュ計算風にランダム度を固定する（簡易的にランダムでも可）
        # ここでは楽しさ重視で完全ランダム
        score = random.randint(0, 100)
        
        if score == 100: msg = "💑 結婚レベル！運命の二人です！"
        elif score >= 80: msg = "💖 かなりラブラブです！"
        elif score >= 50: msg = "🤔 まあまあの相性です。"
        else: msg = "💔 前途多難かも..."
        
        # ゲージ作成
        bar_len = 20
        fill = int(score / 100 * bar_len)
        bar = "█" * fill + "░" * (bar_len - fill)
        
        embed = discord.Embed(title="💘 恋愛計算機", color=0xff69b4)
        embed.description = f"**{user1.display_name}** & **{user2.display_name}**\n\n**{score}%**\n`{bar}`\n\n{msg}"
        await interaction.response.send_message(embed=embed)

    # --- 6. 8ball (水晶玉) ---
    @game_group.command(name="8ball", description="質問に対してYes/Noで答えます")
    async def eightball(self, interaction: discord.Interaction, question: str):
        answers = ["確かにそうです。", "間違いありません。", "おそらくそうです。", "今は分かりません。", "やめておいた方がいいでしょう。", "絶対に違います。"]
        await interaction.response.send_message(f"🎱 質問: {question}\n**答え**: {random.choice(answers)}")

    # --- 7. Shiritori (簡易しりとり) ---
    @game_group.command(name="shiritori", description="Botとしりとりをします (日本語)")
    async def shiritori(self, interaction: discord.Interaction):
        # 簡易的な単語リスト
        bot_words = ["りんご", "ごりら", "らっぱ", "ぱんだ", "だちょう", "うし", "しか", "からす", "すいか"]
        start_word = random.choice(bot_words)
        
        await interaction.response.send_message(f"しりとりスタート！ Bot: **{start_word}**\n（「{start_word[-1]}」から始まる単語をひらがなで入力してね！）")
        
        target_char = start_word[-1]
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
            
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=20.0)
            content = msg.content
            
            # 簡易チェック: 最後の文字が合っているか、"ん"で終わっていないか
            if not content.startswith(target_char):
                await msg.reply(f"❌ 「{target_char}」から始まっていません！ ゲームオーバー！")
            elif content.endswith("ん"):
                await msg.reply("❌ 「ん」がつきました！ あなたの負けです！")
            else:
                # Botは適当に返して終わる (無限ループ防止のため簡易版)
                end_word = "ん" # Botが負ける演出
                await msg.reply(f"Bot: **{random.choice(['みかん', 'きりん', 'ラーメン'])}**... あっ！「ん」がついちゃった！\n🎉 あなたの勝ちです！")
                await self.bot.db.update_money(interaction.user.id, cash=100)
                
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ 時間切れです！")

# --- Quest用 View (ボタン処理) ---
class QuestView(discord.ui.View):
    def __init__(self, user_id, quest_data, bot):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.quest = quest_data
        self.bot = bot

    @discord.ui.button(label="挑戦する", style=discord.ButtonStyle.danger, emoji="⚔️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("他の人のクエストです。", ephemeral=True)
            
        # 結果判定
        if random.randint(1, 100) <= self.quest['success_rate']:
            reward = random.randint(self.quest['reward_min'], self.quest['reward_max'])
            await self.bot.db.update_money(self.user_id, cash=reward)
            
            embed = discord.Embed(title="🎉 クエスト成功！", color=COLOR_MAIN)
            embed.description = f"無事に{self.quest['name']}を達成しました。\n報酬: **¥{reward:,}** 獲得！"
        else:
            embed = discord.Embed(title="💀 クエスト失敗...", color=0x2c3e50)
            embed.description = f"{self.quest['fail_msg']}\n報酬は得られませんでした。"
            
        # ボタン無効化
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

async def setup(bot):
    await bot.add_cog(Games(bot))

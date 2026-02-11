import discord
from discord import app_commands
from discord.ext import commands
import random
from utils.constants import JOBS, COLOR_MAIN, COLOR_ERROR, COLOR_SUCCESS

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_balance_data(self, user_id):
        """ユーザーデータを取得。なければ作成"""
        return await self.bot.db.get_user(user_id)

    # --- グループコマンド: /s (System Economy) ---
    s_group = app_commands.Group(name="s", description="経済システムコマンド")

    @s_group.command(name="bal", description="所持金、銀行、借金を確認します")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        target = user or interaction.user
        data = await self.get_balance_data(target.id)

        cash = data['cash']
        bank = data['bank']
        debt = data['debt']
        net_worth = cash + bank - debt

        embed = discord.Embed(title=f"💰 {target.display_name} の資産状況", color=COLOR_MAIN)
        embed.add_field(name="現金 (Cash)", value=f"¥{cash:,}", inline=True)
        embed.add_field(name="銀行 (Bank)", value=f"¥{bank:,}", inline=True)
        embed.add_field(name="借金 (Debt)", value=f"¥{debt:,}", inline=True)
        embed.add_field(name="純資産 (Net Worth)", value=f"¥{net_worth:,}", inline=False)
        
        job = data['job']
        embed.set_footer(text=f"職業: {job} | 働いて返そう！ /s work")
        await interaction.followup.send(embed=embed)

    @s_group.command(name="work", description="仕事をしてお金を稼ぎます")
    async def work(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        data = await self.get_balance_data(user_id)
        
        job_name = data['job']
        # 職業データ取得 (存在しない場合はニート扱い)
        job_info = JOBS.get(job_name, JOBS["ニート"])
        
        # 給料計算: 基本給 + ランダムボーナス * 倍率
        base_salary = job_info['salary']
        multiplier = job_info['multiplier']
        
        # ランダム要素 (50%〜150%のブレ幅)
        variance = random.uniform(0.5, 1.5)
        
        # ニートの場合の最低保証
        if base_salary == 0:
            earnings = random.randint(100, 500)
        else:
            earnings = int(base_salary * variance * multiplier)

        await self.bot.db.update_money(user_id, cash=earnings)
        
        embed = discord.Embed(title="👔 お仕事完了！", description=f"**{job_name}** として働きました。", color=COLOR_SUCCESS)
        embed.add_field(name="給料", value=f"¥{earnings:,}", inline=True)
        embed.add_field(name="現在の所持金", value=f"¥{data['cash'] + earnings:,}", inline=True)
        await interaction.followup.send(embed=embed)

    @s_group.command(name="slot", description="スロットでお金を増やします (賭け金指定)")
    @app_commands.describe(bet="賭ける金額")
    async def slot(self, interaction: discord.Interaction, bet: int):
        await interaction.response.defer()
        user_id = interaction.user.id
        data = await self.get_balance_data(user_id)

        if bet < 100:
            return await interaction.followup.send("❌ 最低賭け金は ¥100 です。", ephemeral=True)
        if data['cash'] < bet:
            return await interaction.followup.send("❌ 現金が足りません！", ephemeral=True)

        # 絵柄定義
        emojis = ["🍒", "🍋", "🍇", "🍉", "🔔", "💎", "7️⃣"]
        # 確率操作: 7️⃣ は出にくい
        weights = [20, 20, 20, 15, 15, 8, 2]
        
        # 3つ抽選
        result = random.choices(emojis, weights=weights, k=3)
        
        # 判定ロジック
        win_amt = 0
        if result[0] == result[1] == result[2]: # 3つ揃い
            if result[0] == "7️⃣":
                win_amt = bet * 77 # ジャックポット
            elif result[0] == "💎":
                win_amt = bet * 50
            else:
                win_amt = bet * 10
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]: # 2つ揃い
            win_amt = int(bet * 1.5)

        # DB更新
        if win_amt > 0:
            profit = win_amt
            await self.bot.db.update_money(user_id, cash=profit)
            msg = f"🎉 **大当たり！** ¥{profit:,} 獲得！"
            color = COLOR_SUCCESS
        else:
            await self.bot.db.update_money(user_id, cash=-bet)
            msg = "💀 **ハズレ...** お金が吸い込まれました。"
            color = COLOR_ERROR

        embed = discord.Embed(title="🎰 スロットマシン", color=color)
        embed.description = f"**| {result[0]} | {result[1]} | {result[2]} |**\n\n{msg}"
        await interaction.followup.send(embed=embed)

    @s_group.command(name="send", description="他のユーザーに送金します")
    async def send_money(self, interaction: discord.Interaction, to_user: discord.Member, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send("❌ 1円以上指定してください。", ephemeral=True)
        if to_user.bot:
            return await interaction.followup.send("❌ Botには送金できません。", ephemeral=True)
        
        sender_data = await self.get_balance_data(interaction.user.id)
        if sender_data['cash'] < amount:
            return await interaction.followup.send("❌ 現金が足りません。", ephemeral=True)

        # トランザクション的に処理 (簡易実装)
        await self.bot.db.update_money(interaction.user.id, cash=-amount)
        await self.bot.db.update_money(to_user.id, cash=amount)

        embed = discord.Embed(description=f"💸 {to_user.mention} に ¥{amount:,} 送金しました。", color=COLOR_SUCCESS)
        await interaction.followup.send(embed=embed)

    @s_group.command(name="borrow", description="コインを借ります（借金）")
    async def borrow(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        if amount <= 0: return await interaction.followup.send("❌ 1円以上指定してください。", ephemeral=True)
        
        # 借金上限チェック (例: 1000万まで)
        limit = 10000000
        data = await self.get_balance_data(interaction.user.id)
        if data['debt'] + amount > limit:
             return await interaction.followup.send(f"❌ 借金限度額を超えています (上限: ¥{limit:,})", ephemeral=True)

        # 現金と借金を増やす
        await self.bot.db.update_money(interaction.user.id, cash=amount, debt=amount)
        await interaction.followup.send(f"💳 ¥{amount:,} 借りました。ご利用は計画的に！ (現在の借金: ¥{data['debt'] + amount:,})")

    @s_group.command(name="repay", description="借金を返済します")
    async def repay(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        if amount <= 0: return await interaction.followup.send("❌ 1円以上指定してください。", ephemeral=True)
        
        user_id = interaction.user.id
        data = await self.get_balance_data(user_id)
        
        if data['debt'] <= 0:
            return await interaction.followup.send("✅ 借金はありません！", ephemeral=True)
        if data['cash'] < amount:
            return await interaction.followup.send("❌ 現金が足りません。", ephemeral=True)
        
        # 返済額が借金より多い場合は借金の額だけ返す
        pay_amount = min(amount, data['debt'])
        
        # 現金と借金を減らす
        await self.bot.db.update_money(user_id, cash=-pay_amount, debt=-pay_amount)
        
        remaining_debt = data['debt'] - pay_amount
        await interaction.followup.send(f"💸 借金を ¥{pay_amount:,} 返済しました！ (残り: ¥{remaining_debt:,})")

    @s_group.command(name="ranking", description="所持金ランキングを表示")
    async def ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # 純資産 (現金+銀行-借金) でソート
        query = """
            SELECT user_id, (cash + bank - debt) as net_worth 
            FROM users 
            ORDER BY net_worth DESC 
            LIMIT 10
        """
        rows = await self.bot.db.fetch(query)
        
        embed = discord.Embed(title="🏆 億万長者ランキング", color=0xFFD700)
        text = ""
        for i, row in enumerate(rows, 1):
            user = self.bot.get_user(row['user_id'])
            # ユーザーが見つからない場合はID表示 (キャッシュにない場合があるため)
            name = user.display_name if user else f"User ID: {row['user_id']}"
            
            medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
            text += f"**{medal} {name}**: ¥{row['net_worth']:,}\n"
        
        embed.description = text if text else "まだデータがありません。"
        await interaction.followup.send(embed=embed)

    @s_group.command(name="info", description="今日のスロット情報を表示")
    async def slot_info(self, interaction: discord.Interaction):
        # 演出用
        embed = discord.Embed(title="🎰 本日のスロット設定", color=COLOR_MAIN)
        embed.add_field(name="ジャックポット確率", value="0.5%", inline=True)
        embed.add_field(name="還元率", value="95%", inline=True)
        embed.add_field(name="イベント", value="7のつく日は激アツ！？", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="job_change", description="職業を変更します（転職）")
    async def job_change(self, interaction: discord.Interaction, job_name: str):
        """オートコンプリート対応の転職コマンド"""
        await interaction.response.defer()
        if job_name not in JOBS:
            return await interaction.followup.send("❌ その職業は存在しません。", ephemeral=True)
        
        target_job = JOBS[job_name]
        cost = target_job['cost']
        user_data = await self.get_balance_data(interaction.user.id)
        
        if user_data['cash'] < cost:
            return await interaction.followup.send(f"❌ 転職費用 ¥{cost:,} が足りません。", ephemeral=True)
            
        await self.bot.db.update_money(interaction.user.id, cash=-cost)
        await self.bot.db.execute("UPDATE users SET job = $1 WHERE user_id = $2", job_name, interaction.user.id)
        
        await interaction.followup.send(f"🎉 おめでとうございます！ **{job_name}** に転職しました！\n給料倍率: {target_job['multiplier']}倍")

    @job_change.autocomplete('job_name')
    async def job_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=f"{k} (費用: ¥{v['cost']:,})", value=k)
            for k, v in JOBS.items() if current in k
        ][:25]

async def setup(bot):
    await bot.add_cog(Economy(bot))

import asyncpg
import os

class Database:
    def __init__(self):
        self.pool = None
        self.url = os.getenv("DATABASE_URL")

    async def init(self):
        if not self.url:
            print("⚠️ DATABASE_URL が設定されていません。データベース機能は動作しません。")
            return
        
        try:
            self.pool = await asyncpg.create_pool(self.url)
            
            # --- テーブル作成 (初回起動時のみ実行される) ---
            
            # ユーザーデータ (所持金など)
            await self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                cash BIGINT DEFAULT 0,
                bank BIGINT DEFAULT 0,
                last_daily TIMESTAMP,
                last_rob TIMESTAMP
            );
            """)
            
            # サーバー設定 (ログチャンネル、AutoModなど)
            await self.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id BIGINT PRIMARY KEY,
                log_channel_id BIGINT,
                bad_words TEXT,
                spam_filter_enabled BOOLEAN DEFAULT FALSE,
                automod_enabled BOOLEAN DEFAULT FALSE
            );
            """)
            
            print("✅ データベース接続成功")
        except Exception as e:
            print(f"❌ データベース接続エラー: {e}")

    # --- 基本操作メソッド ---

    async def execute(self, query, *args):
        """データの挿入・更新・削除"""
        if not self.pool: return
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetchrow(self, query, *args):
        """1行だけ取得"""
        if not self.pool: return None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query, *args):
        """複数行取得"""
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    # --- 便利機能メソッド (Economyなどで使用) ---

    async def get_balance(self, user_id):
        """ユーザーの残高を取得 (いなければ作成)"""
        row = await self.fetchrow("SELECT cash, bank FROM users WHERE user_id = $1", user_id)
        if not row:
            await self.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
            return {'cash': 0, 'bank': 0}
        return row

    async def update_money(self, user_id, cash=0, bank=0):
        """所持金・銀行預金を増減させる"""
        # ユーザーが存在するか確認して作成
        await self.get_balance(user_id)
        
        if cash != 0:
            await self.execute("UPDATE users SET cash = cash + $1 WHERE user_id = $2", cash, user_id)
        if bank != 0:
            await self.execute("UPDATE users SET bank = bank + $1 WHERE user_id = $2", bank, user_id)

    async def get_leaderboard(self):
        """所持金ランキング用"""
        return await self.fetch("SELECT user_id, cash, bank FROM users ORDER BY (cash + bank) DESC LIMIT 10")

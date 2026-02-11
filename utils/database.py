import asyncpg
import os
import json

class Database:
    def __init__(self, db_url):
        self.db_url = db_url
        self.pool = None

    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(self.db_url)
            await self.initialize_tables()
            print("✅ データベース接続成功")
        except Exception as e:
            print(f"❌ データベース接続エラー: {e}")
            raise e

    async def initialize_tables(self):
        """テーブル初期化。ここでdebtカラムなどを確実に作成します"""
        async with self.pool.acquire() as conn:
            # ユーザー経済データ
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    cash BIGINT DEFAULT 0,
                    bank BIGINT DEFAULT 0,
                    debt BIGINT DEFAULT 0,
                    job TEXT DEFAULT 'ニート',
                    xp BIGINT DEFAULT 0,
                    level INT DEFAULT 1,
                    last_daily TIMESTAMP,
                    last_work TIMESTAMP,
                    last_rob TIMESTAMP
                );
            """)
            
            # サーバー設定 (AutoModなど)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id BIGINT PRIMARY KEY,
                    automod_enabled BOOLEAN DEFAULT FALSE,
                    spam_filter_enabled BOOLEAN DEFAULT FALSE,
                    bad_words TEXT DEFAULT '',
                    log_channel_id BIGINT DEFAULT 0,
                    verify_role_id BIGINT DEFAULT 0
                );
            """)

            # 自動応答
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS auto_responses (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT,
                    trigger TEXT,
                    response TEXT,
                    creator_id BIGINT
                );
            """)
            
            # 警告管理
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT,
                    user_id BIGINT,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    moderator_id BIGINT
                );
            """)

            # AutoMod設定詳細
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS automod_config (
                    guild_id BIGINT PRIMARY KEY,
                    spam_threshold INT DEFAULT 10,
                    mute_duration INT DEFAULT 60,
                    ignored_channels TEXT DEFAULT '',
                    ignored_roles TEXT DEFAULT ''
                );
            """)

    async def get_user(self, user_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not row:
                await conn.execute("INSERT INTO users (user_id) VALUES ($1)", user_id)
                return {"cash": 0, "bank": 0, "debt": 0, "job": "ニート", "xp": 0, "level": 1}
            return row

    async def update_money(self, user_id, cash=0, bank=0, debt=0):
        async with self.pool.acquire() as conn:
            # Upsert logic
            await conn.execute("""
                INSERT INTO users (user_id, cash, bank, debt) VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE 
                SET cash = users.cash + $2, 
                    bank = users.bank + $3,
                    debt = users.debt + $4
            """, user_id, cash, bank, debt)

    # 汎用実行メソッド
    async def execute(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

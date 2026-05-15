import os
import requests
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time

# --- 初期設定 ---
load_dotenv()
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
DB_PATH = 'twitch_data.db'

# --- アクセストークン取得 ---
def get_app_access_token():
    try:
        url = 'https://id.twitch.tv/oauth2/token'
        params = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'client_credentials'
        }
        res = requests.post(url, params=params)
        res.raise_for_status()
        data = res.json()
        return data['access_token'], int(data['expires_in'])
    except requests.RequestException as e:
        print(f"⚠️ トークン取得に失敗しました: {e}")
        raise

# --- リトライ付きトークン読み込み・更新 ---
def load_or_refresh_token(retries=15, delay=3):
    for attempt in range(retries):
        try:
            return _load_or_refresh_token_internal()
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                print(f"⚠️ DBロック中、{delay}秒待機して再試行...（{attempt+1}/{retries}）")
                time.sleep(delay)
            else:
                raise
    raise Exception("❌ トークン取得失敗：DBロックが解除されませんでした。")

# --- 内部処理本体（timeout付き） ---
def _load_or_refresh_token_internal():
    now = datetime.utcnow()

    # timeout を 10 秒に設定
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT token, issued_at, expires_in FROM access_token ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()

        if row:
            token, issued_at_str, expires_in = row
            issued_at = datetime.fromisoformat(issued_at_str)
            if now < issued_at + timedelta(seconds=expires_in - 86400):  # 1日余裕を持って更新
                return token

        # 有効期限切れまたはトークンなし → 再取得
        new_token, expires_in = get_app_access_token()
        issued_at_str = now.isoformat()

        cursor.execute("DELETE FROM access_token")
        cursor.execute(
            "INSERT INTO access_token (token, issued_at, expires_in) VALUES (?, ?, ?)",
            (new_token, issued_at_str, expires_in)
        )
        conn.commit()
        return new_token

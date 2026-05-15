import os
import sqlite3
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from itertools import islice
from token_manager import load_or_refresh_token

# --- 環境変数読み込み ---
load_dotenv()
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
DB_PATH = 'twitch_data.db'
INTERVAL_SECONDS = 300  # 5分おき

# --- チャンク化ユーティリティ ---
def chunked(iterable, size):
    """イテレータを size ごとのチャンクに分割"""
    it = iter(iterable)
    return iter(lambda: list(islice(it, size)), [])

# --- 複数ユーザーの配信情報を取得 ---
def get_multiple_streams_info(access_token, user_logins):
    url = 'https://api.twitch.tv/helix/streams'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    params = [('user_login', login) for login in user_logins]
    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    return res.json()['data']

# --- stream_stats テーブルに保存 ---
def save_stream_snapshot(stream_data):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        user_id = stream_data['user_id']
        twitch_id = stream_data['user_login']
        viewer_count = stream_data['viewer_count']
        title = stream_data['title']
        game_name = stream_data['game_name']
        started_at = stream_data['started_at']
        collected_at = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO stream_stats (
                user_id, twitch_id, viewer_count, title, game_name, started_at, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, twitch_id, viewer_count, title, game_name, started_at, collected_at
        ))

    print(f"📡 {twitch_id} の配信データを記録しました（視聴者数: {viewer_count}）")

# --- 監視ループ ---
def monitor_loop():
    while True:
        token = load_or_refresh_token()
        try:
            # DBからstreamersのtwitch_id一覧を取得
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT twitch_id FROM streamers")
                twitch_ids = [row[0] for row in cursor.fetchall()]

            # 100件ずつ分割してAPIリクエスト
            for chunk in chunked(twitch_ids, 100):
                try:
                    stream_data_list = get_multiple_streams_info(token, chunk)
                    online_ids = {stream['user_login'] for stream in stream_data_list}

                    # 配信中ユーザーの情報を保存
                    for stream_data in stream_data_list:
                        save_stream_snapshot(stream_data)

                    # オフラインユーザーをログ出力
                    for login in chunk:
                        if login not in online_ids:
                            print(f"🔕 {login} は現在オフラインです。")

                except Exception as e:
                    print(f"❌ チャンク取得中にエラー: {e}")

        except Exception as e:
            print(f"‼️ 全体処理エラー: {e}")

        print(f"⏱ 次のチェックまで {INTERVAL_SECONDS // 60} 分待機...\n")
        time.sleep(INTERVAL_SECONDS)

# --- 実行エントリーポイント ---
if __name__ == "__main__":
    monitor_loop()

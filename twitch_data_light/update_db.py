import os
import sqlite3
import requests
from dotenv import load_dotenv
from datetime import datetime
from time import sleep
from itertools import islice
from token_manager import load_or_refresh_token

# --- 環境変数読み込み ---
load_dotenv()
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
DB_PATH = os.getenv("DB_PATH")
SLEEP_SECONDS = 30  # チャンク間での待機時間

# --- チャンク化ユーティリティ ---
def chunked(iterable, size):
    it = iter(iterable)
    return iter(lambda: list(islice(it, size)), [])

# --- 100件まとめてユーザー情報取得 ---
def get_users_info_batch(access_token, twitch_ids):
    url = 'https://api.twitch.tv/helix/users'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    params = [('login', login) for login in twitch_ids]
    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    return res.json()['data']

def get_follower_count(access_token, user_id):
    url = 'https://api.twitch.tv/helix/channels/followers'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    params = {'broadcaster_id': user_id}
    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    return res.json()['total']

def get_vods(access_token, user_id, first=100):
    url = 'https://api.twitch.tv/helix/videos'
    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'user_id': user_id,
        'first': first
    }
    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    return res.json()['data']

def update_streamer_info(twitch_id, user_id, display_name, profile_image_url, description, created_at, follower_count):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE streamers
        SET user_id = ?, display_name = ?, profile_image_url = ?, description = ?, created_at = ?, followers = ?
        WHERE twitch_id = ?
    """, (
        user_id, display_name, profile_image_url, description, created_at, follower_count, twitch_id
    ))
    conn.commit()
    conn.close()
    print(f"✅ {twitch_id} を更新しました。")

def save_vod_to_db(vod, user_id):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    cursor = conn.cursor()
    thumbnail_url = vod['thumbnail_url'].replace('{width}', '320').replace('{height}', '180') if vod['thumbnail_url'] else ''
    cursor.execute("""
        INSERT OR IGNORE INTO vods (id, user_id, title, created_at, duration, view_count, url, thumbnail_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        vod['id'], user_id, vod['title'], vod['created_at'], vod['duration'],
        vod['view_count'], vod['url'], thumbnail_url
    ))
    conn.commit()
    conn.close()

def save_follower_history(user_id, twitch_id, followers):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        INSERT OR IGNORE INTO followers_history (user_id, twitch_id, followers, collected_at, collected_date)
        VALUES (?, ?, ?, datetime('now'), ?)
    """, (user_id, twitch_id, followers, today_str))
    conn.commit()
    conn.close()

# --- メイン処理 ---
def run_update():
    token = load_or_refresh_token()

    # 全streamers取得
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    cursor = conn.cursor()
    cursor.execute("SELECT twitch_id FROM streamers")
    twitch_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    for chunk in chunked(twitch_ids, 100):
        try:
            print(f"🔄 チャンク処理中（{len(chunk)} 件）...")
            users_info = get_users_info_batch(token, chunk)
            users_info_dict = {u['login'].lower(): u for u in users_info}

            for twitch_id in chunk:
                user_info = users_info_dict.get(twitch_id.lower())
                if not user_info:
                    print(f"⚠️ {twitch_id} のユーザー情報が取得できませんでした。")
                    continue

                try:
                    user_id = user_info['id']
                    follower_count = get_follower_count(token, user_id)

                    update_streamer_info(
                        twitch_id, user_id, user_info['display_name'],
                        user_info['profile_image_url'], user_info.get('description', ''),
                        user_info.get('created_at', ''), follower_count
                    )

                    save_follower_history(user_id, twitch_id, follower_count)

                    vods = get_vods(token, user_id)
                    for vod in vods:
                        save_vod_to_db(vod, user_id)

                    print(f"✅ {twitch_id} のVOD {len(vods)}件を保存しました。")

                except Exception as e:
                    print(f"❌ {twitch_id} 処理中にエラー: {e}")

        except Exception as e:
            print(f"❌ チャンク全体でエラー: {e}")

        # レート制限対策
        print(f"🕒 {SLEEP_SECONDS}秒間の待機中...")
        sleep(SLEEP_SECONDS)

# 永続ループ
if __name__ == "__main__":
    while True:
        print("🔁 24時間バッチ処理を開始します...")
        try:
            run_update()
        except Exception as e:
            print(f"❌ 実行中にエラーが発生しました: {e}")
        print("✅ 完了しました。次回は24時間後に実行されます。\n")
        sleep(86400)  # 24時間待機（秒単位）
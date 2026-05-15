import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv('DB_PATH')

TEXT_FILE_PATH = 'streamer_ids.txt'  # 1行に1つtwitch_idがあるテキストファイル

def insert_twitch_ids(db_path, txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        twitch_ids = [line.strip() for line in f if line.strip()]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    count_inserted = 0
    for twitch_id in twitch_ids:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO streamers (twitch_id)
                VALUES (?)
            """, (twitch_id,))
            count_inserted += 1
        except Exception as e:
            print(f"❌ {twitch_id} の挿入時にエラー: {e}")

    conn.commit()
    conn.close()
    print(f"✅ 挿入完了：{count_inserted} 件")

if __name__ == "__main__":
    insert_twitch_ids(DB_PATH, TEXT_FILE_PATH)

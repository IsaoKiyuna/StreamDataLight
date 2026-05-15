import os
import sqlite3
import time
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()
DB_PATH = os.getenv("DB_PATH")

def clean_old_stream_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 削除前に件数を確認
    cursor.execute("""
        SELECT COUNT(*) FROM stream_stats
        WHERE datetime(collected_at) < datetime('now', '-5 days')
    """)
    count = cursor.fetchone()[0]

    if count == 0:
        print("🟢 削除対象のレコードはありませんでした。")
    else:
        print(f"⚠️ 削除対象のレコード数: {count} 件")
        cursor.execute("""
            DELETE FROM stream_stats
            WHERE datetime(collected_at) < datetime('now', '-5 days')
        """)
        conn.commit()
        print(f"✅ {count} 件の古いレコードを削除しました。")

    conn.close()

if __name__ == "__main__":
    while True:
        print("🧹 古いstream_statsレコードの削除バッチを開始します...")
        try:
            clean_old_stream_stats()
        except Exception as e:
            print(f"❌ エラーが発生しました: {e}")
        print("⏱ 次の実行まで24時間待機します...\n")
        time.sleep(86400)  # 24時間 = 86400秒

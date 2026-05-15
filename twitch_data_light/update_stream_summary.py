import os
import sqlite3
import time
import pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()
DB_PATH = os.getenv("DB_PATH")

def update_stream_summary():
    conn = sqlite3.connect(DB_PATH)

    # すでに summary に登録されている started_at を取得
    existing = pd.read_sql_query("SELECT user_id, started_at FROM stream_summary", conn)

    # 全stream_statsをDataFrameで取得
    df = pd.read_sql_query("SELECT * FROM stream_stats", conn)

    # すでに集計済みのデータを除外
    if not existing.empty:
        df = df.merge(existing, on=["user_id", "started_at"], how="left", indicator=True)
        df = df[df["_merge"] == "left_only"]

    if df.empty:
        print("🔁 新しい配信セッションは見つかりませんでした。")
        conn.close()
        return

    # 集計処理（game_nameは最頻値を採用）
    summary = (
        df.groupby(['user_id', 'twitch_id', 'started_at'])
          .agg(
              average_viewers=('viewer_count', 'mean'),
              peak_viewers=('viewer_count', 'max'),
              ended_at=('collected_at', 'max'),
              game_name=('game_name', lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0])
          )
          .reset_index()
    )

    # 四捨五入
    summary["average_viewers"] = summary["average_viewers"].round().astype(int)
    summary["peak_viewers"] = summary["peak_viewers"].astype(int)

    # UTCとしてdatetime変換
    started_dt = pd.to_datetime(summary["started_at"], utc=True)
    ended_dt = pd.to_datetime(summary["ended_at"], utc=True)

    # duration（分）
    summary["duration"] = ((ended_dt - started_dt).dt.total_seconds() // 60).astype(int)

    # ✅ ここで現在時刻との差を確認して、終了が20分以内のセッションを除外
    now_utc = datetime.now(timezone.utc)
    cutoff_time = now_utc - timedelta(minutes=20)
    summary = summary[ended_dt < cutoff_time]

    # ✅ 配信時間が20分未満のものを除外
    summary = summary[summary["duration"] >= 20]

    if summary.empty:
        print("⚠️ 有効な（終了済みの）セッションがありませんでした。")
        conn.close()
        return

    # カラム順調整
    summary = summary[[
        'user_id', 'twitch_id', 'started_at', 'ended_at',
        'average_viewers', 'peak_viewers', 'game_name', 'duration'
    ]]

    # 保存
    summary.to_sql("stream_summary", conn, if_exists="append", index=False)
    conn.close()

    print(f"✅ {len(summary)} 件の配信セッションを集計して保存しました。")

if __name__ == "__main__":
    while True:
        print("🔁 配信サマリー集計バッチを実行します...")
        try:
            update_stream_summary()
        except Exception as e:
            print(f"❌ 実行中にエラーが発生しました: {e}")
        print("⏱ 次の実行まで24時間待機...\n")
        time.sleep(86400)

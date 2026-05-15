import os
import sqlite3
import zoneinfo
from datetime import datetime, timezone
from dotenv import load_dotenv
import time

# .env 読み込み
load_dotenv()
DB_PATH = os.getenv("DB_PATH")

JST = zoneinfo.ZoneInfo("Asia/Tokyo")

def to_jst(iso_str):
    """ISO8601文字列をJSTに変換（UTC想定）、YYYY-MM-DD HH:MM形式で返す"""
    try:
        if 'Z' in iso_str or '+' in iso_str:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        else:
            # タイムゾーンがない場合はUTCとして扱う
            dt = datetime.fromisoformat(iso_str).replace(tzinfo=timezone.utc)
        return dt.astimezone(JST).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return iso_str


def minutes_to_hour_minute(minutes: int) -> str:
    """分を「X時間Y分」の形式に変換"""
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours}時間{mins}分"
    elif hours:
        return f"{hours}時間"
    else:
        return f"{mins}分"


def add_comma(n):
    """数値をカンマ付き文字列に変換する（例: 12345 → '12,345'）"""
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)


def get_top_streamers(retries=3, delay=1):
    for i in range(retries):
        try:
            conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT display_name, twitch_id, profile_image_url, followers
                FROM streamers
                ORDER BY followers DESC
                LIMIT 10;
            """)
            top_streamers = cur.fetchall()
            conn.close()
            return top_streamers
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                if i < retries - 1:
                    time.sleep(delay)
                    continue
                else:
                    raise
            else:
                raise
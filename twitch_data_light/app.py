import calendar
import os
import sqlite3
from datetime import date
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from utils import to_jst, minutes_to_hour_minute, add_comma, get_top_streamers
from datetime import datetime, timedelta

app = Flask(__name__)

load_dotenv()
DB_PATH = os.getenv('DB_PATH')

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        search_term = request.form['search'].strip()
        return redirect(url_for('streamer_detail', twitch_id=search_term))

    # CSV読み込み
    df = pd.read_csv('fastest_growing_channels.csv')
    table_html = df.to_html(classes='table table-striped', index=False, border=0)

    # フォロワー数上位10人を取得
    top_streamers = get_top_streamers()

    # 30日前の日付を計算
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()

    # 最大視聴者数が高いゲームランキング取得(過去３０日間)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT game_name, MAX(peak_viewers) as max_peak
        FROM stream_summary
        WHERE game_name IS NOT NULL AND game_name != ''
          AND started_at >= ?
        GROUP BY game_name
        ORDER BY max_peak DESC
        LIMIT 10;
    """, (thirty_days_ago,))
    top_games_by_peak = cur.fetchall()
    conn.close()

    return render_template(
        "index.html",
        table_html=table_html,
        top_streamers=top_streamers,
        top_games_by_peak=top_games_by_peak
    )

@app.route('/streamer/<twitch_id>')
def streamer_detail(twitch_id):
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    cursor = conn.cursor()

    # streamer情報取得
    cursor.execute("""
        SELECT user_id, twitch_id, display_name, description, profile_image_url, followers, created_at
        FROM streamers WHERE twitch_id = ?
    """, (twitch_id,))
    row = cursor.fetchone()
    if not row:
        return f"<h1>{twitch_id} は見つかりませんでした。または入力ミスの可能性があります。新規ストリーマー等の一部のチャンネルはデータ準備中です。</h1>", 404

    streamer = {
        'user_id': row[0],
        'twitch_id': row[1],
        'display_name': row[2],
        'description': row[3],
        'profile_image_url': row[4],
        'followers': row[5],
        'followers_display': add_comma(row[5]), #表示用
        'created_at': row[6]
    }

    # VOD情報取得
    cursor.execute("""
        SELECT title, created_at, view_count, url
        FROM vods WHERE user_id = ?
        ORDER BY created_at DESC LIMIT 5
    """, (streamer['user_id'],))
    vods = [{
        'title': r[0],
        'created_at': to_jst(r[1]),
        'view_count': r[2],
        'url': r[3],
        # 'thumbnail_url': r[4] 後で直す　# Fix it later
    } for r in cursor.fetchall()]

    # 月の配信日カレンダー用データ取得
    today = date.today()
    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    cursor.execute("""
        SELECT DISTINCT DATE(datetime(created_at, '+9 hours'))
        FROM vods
        WHERE user_id = ? AND strftime('%Y', datetime(created_at, '+9 hours')) = ? AND strftime('%m', datetime(created_at, '+9 hours')) = ?
    """, (streamer['user_id'], str(year), f"{month:02d}"))
    stream_dates = {row[0] for row in cursor.fetchall()}
    stream_count = len(stream_dates)

    # カレンダーの日付一覧を作成
    cal = calendar.Calendar(firstweekday=6)
    month_days = []
    for day in cal.itermonthdates(year, month):
        day_str = day.isoformat()
        month_days.append({
            'day': day,
            'is_current_month': day.month == month,
            'is_streaming': day_str in stream_dates
        })

    # stream_summary（過去10件の配信統計）を取得　LIMITがゲームごとの平均視聴者数のグラフともリンクしている
    cursor.execute("""
        SELECT started_at, ended_at, average_viewers, peak_viewers, game_name, duration
        FROM stream_summary
        WHERE user_id = ?
        ORDER BY started_at DESC
        LIMIT 10
    """, (streamer['user_id'],))

    rows = cursor.fetchall()

    stream_summaries = []
    chart_labels = []
    chart_avg_viewers=[]

    for r in rows:
        # 表示用データ（JST変換、カンマなど）
        stream_summaries.append({
            'started_at': to_jst(r[0]),
            'ended_at': to_jst(r[1]),
            'average_viewers': r[2],
            'average_viewers_display': add_comma(r[2]),
            'peak_viewers': r[3],
            'peak_viewers_display': add_comma(r[3]),
            'game_name': r[4],
            'duration': r[5],
            'duration_display': minutes_to_hour_minute(r[5])
        })

    # グラフ用（UTCのまま reversed）
    for r in reversed(rows):
        dt = to_jst(r[0])
        chart_labels.append(dt[:16])  # JST時刻に変換してから表示
        chart_avg_viewers.append(r[2])


    # フォロワー推移データを取得（最新30件など）
    cursor.execute("""
        SELECT collected_date, followers
        FROM followers_history
        WHERE twitch_id = ?
        ORDER BY collected_date DESC
        LIMIT 30
    """, (streamer['twitch_id'],))
    follower_history = cursor.fetchall()
    follower_history.reverse()  # 最新→古い順から、古い→新しい順に戻す

    follower_dates = [r[0] for r in follower_history]
    follower_counts = [r[1] for r in follower_history]

    conn.close()


    # ゲームごとの平均視聴者数（棒グラフ用）
    from collections import defaultdict
    game_stats = defaultdict(list)
    for s in stream_summaries:
        if s['game_name']:
            game_stats[s['game_name']].append(s['average_viewers'])
    game_labels = list(game_stats.keys())
    game_avg_viewers = [round(sum(v) / len(v)) for v in game_stats.values()]

    # フォロワー数推移の差分（前日比）を算出
    follower_diffs = [0]  # 最初は差分なし
    for i in range(1, len(follower_counts)):
        diff = follower_counts[i] - follower_counts[i - 1]
        follower_diffs.append(diff)

    return render_template(
        'streamer_detail.html',
        streamer=streamer,
        vods=vods,
        year=year, month=month,
        month_days=month_days,
        stream_count=stream_count,
        stream_summaries=stream_summaries,
        game_labels=game_labels,
        game_avg_viewers=game_avg_viewers,
        chart_labels=chart_labels,
        chart_avg_viewers=chart_avg_viewers,
        follower_dates=follower_dates,
        follower_counts=follower_counts,
        follower_diffs = follower_diffs
    )

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

if __name__ == '__main__':
    app.run(debug=False)

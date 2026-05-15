import sqlite3


conn = sqlite3.connect('twitch_data.db')
cursor = conn.cursor()

cursor.execute('SELECT * FROM streamers')
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()

import requests

# Twitchtrackerで平均視聴者数と最大視聴者数を取得できるみたい。
url = "https://twitchtracker.com/api/channels/summary/nemuyamane"
try:
    response = requests.get(url)
    if response.status_code == 200:
        print("Success:", response.json())
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print("Exception:", e)

url2 = "https://twitchtracker.com/api/games/summary/180211914"
try:
    response = requests.get(url2)
    if response.status_code == 200:
        print("Success:", response.json())
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print("Exception:", e)

try:
    x = 1 / 0  # ゼロ除算エラーを引き起こす
except Exception as e:
    print("Exception:", e)


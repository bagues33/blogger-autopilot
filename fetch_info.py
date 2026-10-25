import sqlite3
import json
from db import DB_PATH
from blogger_client import get_posts

print('=== LIVE POSTS ===')
try:
    posts = get_posts()
    for p in posts:
        print(f"- {p.get('title')} | {p.get('url')}")
    if not posts:
        print('(No live posts found)')
except Exception as e:
    print('Error get_posts:', e)

print('=== DATABASE ===')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
print('Keywords:', c.execute('SELECT id, keyword, search_intent, status FROM keywords').fetchall())
print('Articles:', c.execute('SELECT id, title, target_keyword, status, blogger_url FROM articles').fetchall())
conn.close()

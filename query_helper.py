import sqlite3
from db import DB_PATH

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print('=== ARTICLES COLUMNS ===')
print([c[1] for c in cur.execute('PRAGMA table_info(articles)').fetchall()])

print('=== ARTICLES ROWS ===')
for row in cur.execute('SELECT id, title, status FROM articles').fetchall():
    print(row)

print('=== PLANNED KEYWORD ===')
row = cur.execute("SELECT id, keyword, search_intent FROM keywords WHERE status = 'planned' ORDER BY id ASC LIMIT 1").fetchone()
print(row)

conn.close()

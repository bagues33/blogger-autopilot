import sqlite3
from db import DB_PATH

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
row = cur.execute('SELECT created_at, updated_at FROM articles WHERE id = 1').fetchone()
print('Dates:', row)
conn.close()

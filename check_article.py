import sqlite3

conn = sqlite3.connect('/opt/data/blogger-agent/data.db')
cur = conn.cursor()
row = cur.execute('SELECT created_at, updated_at FROM articles WHERE id = 1').fetchone()
print('Dates:', row)
conn.close()

import sqlite3
import os

from db import DB_PATH, BASE_DIR

def migrate():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    c = conn.cursor()
    
    # 1. Create blogs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS blogs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT,
            account_name TEXT DEFAULT 'Akun Utama',
            token_file TEXT NOT NULL,
            client_secret_file TEXT,
            niche_description TEXT,
            is_active INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Check if default blog Bagus Tech exists
    row = c.execute('SELECT id FROM blogs WHERE id = ?', ('2940095957137948013',)).fetchone()
    if not row:
        default_token = os.path.join(BASE_DIR, 'token.json')
        default_secret = os.path.join(BASE_DIR, 'client_secret.json')
        c.execute('''
            INSERT INTO blogs (id, name, url, account_name, token_file, client_secret_file, niche_description, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            '2940095957137948013',
            'Bagus Tech',
            'https://bagustechnologia.blogspot.com/',
            'Akun Utama',
            default_token,
            default_secret,
            'Web Development, AI, Cloud & Modern Tech',
            1
        ))
        print('Default blog Bagus Tech seeded.')
    else:
        c.execute('UPDATE blogs SET is_active = 1 WHERE id = ?', ('2940095957137948013',))
        
    # 3. Add blog_id to articles if not present
    article_cols = [col[1] for col in c.execute('PRAGMA table_info(articles)').fetchall()]
    if 'blog_id' not in article_cols:
        c.execute("ALTER TABLE articles ADD COLUMN blog_id TEXT DEFAULT '2940095957137948013'")
        print('Added blog_id column to articles table.')
    else:
        c.execute("UPDATE articles SET blog_id = '2940095957137948013' WHERE blog_id IS NULL")
        
    # 4. Add blog_id to keywords if not present
    kw_cols = [col[1] for col in c.execute('PRAGMA table_info(keywords)').fetchall()]
    if 'blog_id' not in kw_cols:
        c.execute("ALTER TABLE keywords ADD COLUMN blog_id TEXT DEFAULT '2940095957137948013'")
        print('Added blog_id column to keywords table.')
    else:
        c.execute("UPDATE keywords SET blog_id = '2940095957137948013' WHERE blog_id IS NULL")
        
    conn.commit()
    
    # Display current blogs
    blogs = c.execute('SELECT id, name, url, account_name, is_active FROM blogs').fetchall()
    print('Current blogs in DB:', blogs)
    conn.close()

if __name__ == '__main__':
    migrate()

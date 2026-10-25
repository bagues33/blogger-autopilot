import sqlite3
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('BLOGGER_DB_PATH', os.path.join(BASE_DIR, 'data.db'))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    c = conn.cursor()
    
    # 1. Articles table
    c.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            target_keyword TEXT,
            meta_description TEXT,
            content_html TEXT NOT NULL,
            labels TEXT,
            status TEXT DEFAULT 'draft', -- draft, approved, published
            blogger_post_id TEXT,
            blogger_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            blog_id TEXT
        )
    ''')
    
    # 2. Keywords table
    c.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            search_intent TEXT DEFAULT 'Informational',
            status TEXT DEFAULT 'planned', -- planned, in_progress, used
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            blog_id TEXT
        )
    ''')
    
    # 3. Blogs table
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
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print('Database initialized at', DB_PATH)

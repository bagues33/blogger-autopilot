import os
import sys
import json
import sqlite3
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from crypto_service import encrypt_token_data, decrypt_token_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get('BLOGGER_CONFIG_FILE', os.path.join(BASE_DIR, 'config.json'))
DB_PATH = os.environ.get('BLOGGER_DB_PATH', os.path.join(BASE_DIR, 'data.db'))
DEFAULT_TOKEN_FILE = os.environ.get('GOOGLE_TOKEN_FILE', os.path.join(BASE_DIR, 'token.json'))

def resolve_file_path(path_str):
    if not path_str:
        return None
    if os.path.isabs(path_str) and os.path.exists(path_str):
        return path_str
    candidate = os.path.join(BASE_DIR, path_str)
    if os.path.exists(candidate):
        return candidate
    candidate_base = os.path.join(BASE_DIR, os.path.basename(path_str))
    if os.path.exists(candidate_base):
        return candidate_base
    candidate_tokens = os.path.join(BASE_DIR, 'tokens', os.path.basename(path_str))
    if os.path.exists(candidate_tokens):
        return candidate_tokens
    return path_str

def get_active_blog_info():
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            c = conn.cursor()
            row = c.execute('SELECT id, token_file, name, url FROM blogs WHERE is_active = 1 LIMIT 1').fetchone()
            conn.close()
            if row:
                return row[0], resolve_file_path(row[1]) or DEFAULT_TOKEN_FILE, row[2], row[3]
    except Exception:
        pass
        
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            return config.get('blog_id'), resolve_file_path(config.get('token_file')) or DEFAULT_TOKEN_FILE, config.get('blog_name', 'Bagus Tech'), config.get('blog_url', '')
        except Exception:
            pass
            
    return '2940095957137948013', DEFAULT_TOKEN_FILE, 'Bagus Tech', ''

def get_service(token_file=None, blog_id=None, encrypted_token=None, db_session=None, blog_model=None):
    active_id, active_token, _, _ = get_active_blog_info()
    target_blog_id = blog_id or active_id

    # Priority 1: In-memory decrypted OAuth token (Multi-Tenant SaaS ready)
    if encrypted_token:
        token_info = decrypt_token_data(encrypted_token)
        if token_info:
            creds = Credentials.from_authorized_user_info(token_info)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                if db_session and blog_model:
                    blog_model.encrypted_token = encrypt_token_data(creds.to_json())
                    db_session.commit()
            return build('blogger', 'v3', credentials=creds), target_blog_id

    # Priority 2: File-based token (Local / Legacy dev)
    raw_token_file = token_file or active_token
    target_token_file = resolve_file_path(raw_token_file) or DEFAULT_TOKEN_FILE
    
    if not target_token_file or not os.path.exists(target_token_file):
        raise FileNotFoundError(f"Token file '{raw_token_file}' tidak ditemukan. Silakan hubungkan blog Anda melalui dashboard.")
        
    creds = Credentials.from_authorized_user_file(target_token_file)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(target_token_file, 'w') as f:
            f.write(creds.to_json())
            
    return build('blogger', 'v3', credentials=creds), target_blog_id

def get_posts(max_results=20, token_file=None, blog_id=None, encrypted_token=None):
    service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
    res = service.posts().list(blogId=b_id, maxResults=max_results, status=['LIVE']).execute()
    return res.get('items', [])

def fetch_blogger_posts_sync(token_file=None, blog_id=None, encrypted_token=None, max_results=50, status_list=None):
    """
    Fetches both LIVE and DRAFT posts from Blogger API for two-way synchronization.
    """
    if status_list is None:
        status_list = ['LIVE', 'DRAFT']
    service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
    res = service.posts().list(
        blogId=b_id,
        maxResults=max_results,
        status=status_list,
        fetchBodies=True
    ).execute()
    return res.get('items', [])

def create_post(title, content_html, labels=None, is_draft=True, token_file=None, blog_id=None, encrypted_token=None):
    service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
    body = {
        'kind': 'blogger#post',
        'title': title,
        'content': content_html,
    }
    if labels:
        body['labels'] = labels if isinstance(labels, list) else [l.strip() for l in labels.split(',') if l.strip()]
        
    post = service.posts().insert(blogId=b_id, body=body, isDraft=is_draft).execute()
    return post

def update_post(post_id, title, content_html, labels=None, is_draft=False, token_file=None, blog_id=None, encrypted_token=None):
    service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
    body = {
        'kind': 'blogger#post',
        'id': str(post_id),
        'title': title,
        'content': content_html,
    }
    if labels:
        body['labels'] = labels if isinstance(labels, list) else [l.strip() for l in labels.split(',') if l.strip()]
        
    kwargs = {
        'blogId': b_id,
        'postId': str(post_id),
        'body': body,
    }
    if is_draft:
        kwargs['revert'] = True
    else:
        kwargs['publish'] = True

    post = service.posts().update(**kwargs).execute()
    return post

def get_post(post_id, token_file=None, blog_id=None, encrypted_token=None):
    service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
    return service.posts().get(blogId=b_id, postId=str(post_id)).execute()

def delete_post(post_id, token_file=None, blog_id=None, encrypted_token=None):
    service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
    return service.posts().delete(blogId=b_id, postId=str(post_id)).execute()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--test-info':
        service, b_id = get_service()
        blog = service.blogs().get(blogId=b_id).execute()
        print(f"Connected to: {blog.get('name')} ({blog.get('url')})")
    else:
        posts = get_posts(5)
        print(f"Found {len(posts)} live posts.")

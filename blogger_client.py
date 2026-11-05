import os
import sys
import json
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from crypto_service import encrypt_token_data, decrypt_token_data
from db_saas import SessionLocal
from models_saas import Blog

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get('BLOGGER_CONFIG_FILE', os.path.join(BASE_DIR, 'config.json'))
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

def get_active_blog_info(user_id: Optional[str] = None, db_session=None):
    session = db_session or SessionLocal()
    try:
        query = session.query(Blog)
        if user_id:
            query = query.filter(Blog.user_id == user_id)
        active_blog = query.filter(Blog.is_active == 1).first()
        if not active_blog:
            active_blog = query.first()
        if active_blog:
            return (
                active_blog.id,
                resolve_file_path(active_blog.token_file) or DEFAULT_TOKEN_FILE,
                active_blog.name,
                active_blog.url or ''
            )
    except Exception:
        pass
    finally:
        if not db_session:
            session.close()
        
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            return (
                config.get('blog_id', '2940095957137948013'),
                resolve_file_path(config.get('token_file')) or DEFAULT_TOKEN_FILE,
                config.get('blog_name', 'Bagus Tech'),
                config.get('blog_url', '')
            )
        except Exception:
            pass
            
    return '2940095957137948013', DEFAULT_TOKEN_FILE, 'Bagus Tech', ''

def get_service(token_file=None, blog_id=None, encrypted_token=None, db_session=None, blog_model=None, user_id=None):
    active_id, active_token, _, _ = get_active_blog_info(user_id=user_id, db_session=db_session)
    target_blog_id = blog_id or active_id
    effective_enc_token = encrypted_token
    
    if not effective_enc_token:
        session = db_session or SessionLocal()
        try:
            blog_record = session.query(Blog).filter(Blog.id == target_blog_id).first()
            if blog_record and blog_record.encrypted_token:
                effective_enc_token = blog_record.encrypted_token
        except Exception:
            pass
        finally:
            if not db_session:
                session.close()

    # Priority 1: In-memory decrypted OAuth token (Multi-Tenant SaaS ready)
    if effective_enc_token:
        token_info = decrypt_token_data(effective_enc_token)
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
        raise FileNotFoundError("Sesi Google Blogger belum terhubung atau perlu login ulang. Silakan klik 'Hubungkan Akun Google' di dashboard.")
        
    creds = Credentials.from_authorized_user_file(target_token_file)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(target_token_file, 'w') as f:
            f.write(creds.to_json())
            
    return build('blogger', 'v3', credentials=creds), target_blog_id

# =====================================================================
# Blogger Publisher Seam & Adapters (Two adapters justify the seam)
# =====================================================================

class BaseBloggerAdapter:
    """
    Interface for publishing and syncing posts with Google Blogger.
    """
    def fetch_posts(self, token_file=None, blog_id=None, encrypted_token=None, max_results=50, status_list=None) -> list:
        raise NotImplementedError

    def create_post(self, title: str, content_html: str, labels=None, is_draft=True, token_file=None, blog_id=None, encrypted_token=None) -> dict:
        raise NotImplementedError

    def update_post(self, post_id: str, title: str, content_html: str, labels=None, is_draft=False, token_file=None, blog_id=None, encrypted_token=None) -> dict:
        raise NotImplementedError

    def get_post(self, post_id: str, token_file=None, blog_id=None, encrypted_token=None) -> dict:
        raise NotImplementedError

    def delete_post(self, post_id: str, token_file=None, blog_id=None, encrypted_token=None):
        raise NotImplementedError

class GoogleBloggerLiveAdapter(BaseBloggerAdapter):
    """
    Production adapter: Executes live Google Blogger v3 REST API calls.
    """
    def fetch_posts(self, token_file=None, blog_id=None, encrypted_token=None, max_results=50, status_list=None) -> list:
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

    def create_post(self, title: str, content_html: str, labels=None, is_draft=True, token_file=None, blog_id=None, encrypted_token=None) -> dict:
        service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
        body = {
            'kind': 'blogger#post',
            'title': title,
            'content': content_html,
        }
        if labels:
            body['labels'] = labels if isinstance(labels, list) else [l.strip() for l in labels.split(',') if l.strip()]
        return service.posts().insert(blogId=b_id, body=body, isDraft=is_draft).execute()

    def update_post(self, post_id: str, title: str, content_html: str, labels=None, is_draft=False, token_file=None, blog_id=None, encrypted_token=None) -> dict:
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

        return service.posts().update(**kwargs).execute()

    def get_post(self, post_id: str, token_file=None, blog_id=None, encrypted_token=None) -> dict:
        service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
        return service.posts().get(blogId=b_id, postId=str(post_id)).execute()

    def delete_post(self, post_id: str, token_file=None, blog_id=None, encrypted_token=None):
        service, b_id = get_service(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)
        return service.posts().delete(blogId=b_id, postId=str(post_id)).execute()

class InMemoryBloggerAdapter(BaseBloggerAdapter):
    """
    Test adapter: In-memory simulation of Blogger posts for offline testing.
    """
    def __init__(self):
        self.posts_by_blog: dict = {}
        self._next_id = 1000

    def _ensure_blog(self, blog_id: str):
        if blog_id not in self.posts_by_blog:
            self.posts_by_blog[blog_id] = {}

    def fetch_posts(self, token_file=None, blog_id=None, encrypted_token=None, max_results=50, status_list=None) -> list:
        target_id = blog_id or 'default_blog'
        self._ensure_blog(target_id)
        posts = list(self.posts_by_blog[target_id].values())
        if status_list:
            posts = [p for p in posts if p.get('status') in status_list]
        return posts[:max_results]

    def create_post(self, title: str, content_html: str, labels=None, is_draft=True, token_file=None, blog_id=None, encrypted_token=None) -> dict:
        target_id = blog_id or 'default_blog'
        self._ensure_blog(target_id)
        post_id = str(self._next_id)
        self._next_id += 1
        parsed_labels = labels if isinstance(labels, list) else ([l.strip() for l in labels.split(',') if l.strip()] if labels else [])
        slug = title.lower().replace(' ', '-')[:30]
        post = {
            'id': post_id,
            'blog_id': target_id,
            'title': title,
            'content': content_html,
            'labels': parsed_labels,
            'status': 'DRAFT' if is_draft else 'LIVE',
            'url': f"https://bagustechnologia.blogspot.com/{slug}.html"
        }
        self.posts_by_blog[target_id][post_id] = post
        return post

    def update_post(self, post_id: str, title: str, content_html: str, labels=None, is_draft=False, token_file=None, blog_id=None, encrypted_token=None) -> dict:
        target_id = blog_id or 'default_blog'
        self._ensure_blog(target_id)
        str_id = str(post_id)
        existing = self.posts_by_blog[target_id].get(str_id, {})
        parsed_labels = labels if isinstance(labels, list) else ([l.strip() for l in labels.split(',') if l.strip()] if labels else [])
        existing.update({
            'title': title,
            'content': content_html,
            'labels': parsed_labels,
            'status': 'DRAFT' if is_draft else 'LIVE'
        })
        self.posts_by_blog[target_id][str_id] = existing
        return existing

    def get_post(self, post_id: str, token_file=None, blog_id=None, encrypted_token=None) -> dict:
        target_id = blog_id or 'default_blog'
        self._ensure_blog(target_id)
        return self.posts_by_blog[target_id].get(str(post_id), {'id': str(post_id), 'title': 'Mock Post', 'content': ''})

    def delete_post(self, post_id: str, token_file=None, blog_id=None, encrypted_token=None):
        target_id = blog_id or 'default_blog'
        self._ensure_blog(target_id)
        self.posts_by_blog[target_id].pop(str(post_id), None)

# Active adapter holder
_active_blogger_adapter: BaseBloggerAdapter = None

def get_blogger_adapter() -> BaseBloggerAdapter:
    global _active_blogger_adapter
    if _active_blogger_adapter is None:
        if os.environ.get('USE_MOCK_BLOGGER', 'false').lower() in ('true', '1'):
            _active_blogger_adapter = InMemoryBloggerAdapter()
        else:
            _active_blogger_adapter = GoogleBloggerLiveAdapter()
    return _active_blogger_adapter

def set_blogger_adapter(adapter: BaseBloggerAdapter):
    global _active_blogger_adapter
    _active_blogger_adapter = adapter

def get_posts(max_results=20, token_file=None, blog_id=None, encrypted_token=None):
    return get_blogger_adapter().fetch_posts(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token, max_results=max_results, status_list=['LIVE'])

def fetch_blogger_posts_sync(token_file=None, blog_id=None, encrypted_token=None, max_results=50, status_list=None):
    return get_blogger_adapter().fetch_posts(token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token, max_results=max_results, status_list=status_list)

def create_post(title, content_html, labels=None, is_draft=True, token_file=None, blog_id=None, encrypted_token=None):
    return get_blogger_adapter().create_post(title=title, content_html=content_html, labels=labels, is_draft=is_draft, token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)

def update_post(post_id, title, content_html, labels=None, is_draft=False, token_file=None, blog_id=None, encrypted_token=None):
    return get_blogger_adapter().update_post(post_id=post_id, title=title, content_html=content_html, labels=labels, is_draft=is_draft, token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)

def get_post(post_id, token_file=None, blog_id=None, encrypted_token=None):
    return get_blogger_adapter().get_post(post_id=post_id, token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)

def delete_post(post_id, token_file=None, blog_id=None, encrypted_token=None):
    return get_blogger_adapter().delete_post(post_id=post_id, token_file=token_file, blog_id=blog_id, encrypted_token=encrypted_token)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--test-info':
        service, b_id = get_service()
        blog = service.blogs().get(blogId=b_id).execute()
        print(f"Connected to: {blog.get('name')} ({blog.get('url')})")
    else:
        posts = get_posts(5)
        print(f"Found {len(posts)} live posts.")

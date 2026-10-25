import os
import sys
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOPES = ['https://www.googleapis.com/auth/blogger']
CLIENT_SECRET_FILE = os.environ.get('GOOGLE_CLIENT_SECRETS_FILE', os.path.join(BASE_DIR, 'client_secret.json'))
TOKEN_FILE = os.environ.get('GOOGLE_TOKEN_FILE', os.path.join(BASE_DIR, 'token.json'))
STATE_FILE = os.path.join(BASE_DIR, 'auth_state.json')

def get_auth_url():
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise FileNotFoundError(f"File '{CLIENT_SECRET_FILE}' tidak ditemukan! Silakan salin client_secret.json dari Google Cloud Console ke direktori ini.")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES, redirect_uri='http://localhost')
    auth_url, state = flow.authorization_url(prompt='consent', access_type='offline')
    code_verifier = getattr(flow, 'code_verifier', None)
    with open(STATE_FILE, 'w') as f:
        json.dump({'state': state, 'code_verifier': code_verifier}, f)
    print("AUTH_URL:", auth_url)
    return auth_url

def exchange_code(auth_code_or_url):
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise FileNotFoundError(f"File '{CLIENT_SECRET_FILE}' tidak ditemukan!")
    state = None
    code_verifier = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                state = data.get('state')
                code_verifier = data.get('code_verifier')
        except Exception:
            pass
            
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES, redirect_uri='http://localhost', state=state)
    if code_verifier:
        flow.code_verifier = code_verifier
        
    if 'code=' in auth_code_or_url:
        from urllib.parse import urlparse, parse_qs
        query = urlparse(auth_code_or_url).query
        code = parse_qs(query)['code'][0]
    else:
        code = auth_code_or_url.strip()
        
    flow.fetch_token(code=code)
    creds = flow.credentials
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    print("SUCCESS: Token saved to", TOKEN_FILE)
    return TOKEN_FILE

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--url':
        get_auth_url()
    elif len(sys.argv) > 1 and sys.argv[1] == '--code':
        exchange_code(sys.argv[2])
    else:
        print('Usage: auth.py --url OR auth.py --code <code_or_redirect_url>')

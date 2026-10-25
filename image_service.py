"""
Image optimization and Cloud CDN service for Blogger Auto-Pilot
Converts images to high-efficiency WebP format and uploads to public Cloud CDN (Cloudinary)
with graceful local fallback.
"""

import os
import io
import time
import uuid
import hashlib
import urllib.parse
from PIL import Image
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.environ.get('BLOGGER_UPLOADS_DIR', os.path.join(BASE_DIR, 'uploads'))

def get_cloudinary_credentials():
    url_str = os.environ.get('CLOUDINARY_URL', '').strip()
    if url_str:
        parsed = urllib.parse.urlparse(url_str)
        cloud_name = parsed.hostname
        api_key = parsed.username
        api_secret = parsed.password
        if cloud_name and api_key and api_secret:
            return cloud_name, api_key, api_secret

    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', '').strip()
    api_key = os.environ.get('CLOUDINARY_API_KEY', '').strip()
    api_secret = os.environ.get('CLOUDINARY_API_SECRET', '').strip()

    if cloud_name and api_key and api_secret:
        return cloud_name, api_key, api_secret

    return None, None, None

def optimize_to_webp(image_bytes: bytes, max_width: int = 1200, quality: int = 82) -> bytes:
    """
    Resizes image if wider than max_width and converts to highly efficient WebP format.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Resize if image exceeds max_width
    if img.width > max_width:
        ratio = max_width / float(img.width)
        target_height = int(float(img.height) * ratio)
        img = img.resize((max_width, target_height), Image.Resampling.LANCZOS)

    # Handle image color modes
    if img.mode in ('RGBA', 'LA'):
        # Keep RGBA for transparent images
        pass
    elif img.mode == 'P':
        img = img.convert('RGBA')
    else:
        img = img.convert('RGB')

    out_io = io.BytesIO()
    img.save(out_io, format='WEBP', quality=quality, method=6)
    return out_io.getvalue()

def upload_to_cloudinary(webp_bytes: bytes, original_name: str) -> str:
    cloud_name, api_key, api_secret = get_cloudinary_credentials()
    if not (cloud_name and api_key and api_secret):
        return None

    timestamp = str(int(time.time()))
    folder = "blogger_autopilot"
    
    # Generate signature: parameters sorted alphabetically
    to_sign = f"folder={folder}&timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(to_sign.encode('utf-8')).hexdigest()

    endpoint = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    files = {
        'file': (f"{uuid.uuid4().hex[:8]}.webp", webp_bytes, 'image/webp')
    }
    data = {
        'api_key': api_key,
        'timestamp': timestamp,
        'folder': folder,
        'signature': signature
    }

    resp = requests.post(endpoint, files=files, data=data, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    return payload.get('secure_url') or payload.get('url')

def process_and_upload_image(file_bytes: bytes, filename: str) -> dict:
    """
    Full pipeline: optimize image to WebP, then upload to public Cloudinary CDN.
    Falls back to local /uploads/ if Cloudinary is unconfigured.
    """
    base_name = os.path.splitext(filename)[0].replace(' ', '_')
    webp_filename = f"{uuid.uuid4().hex[:10]}_{base_name}.webp"

    # 1. Optimize and convert to WebP
    webp_bytes = optimize_to_webp(file_bytes)

    # 2. Try upload to Cloudinary (Public CDN)
    try:
        cdn_url = upload_to_cloudinary(webp_bytes, filename)
        if cdn_url:
            return {
                'success': True,
                'url': cdn_url,
                'filename': webp_filename,
                'is_cdn': True,
                'cdn_provider': 'Cloudinary',
                'format': 'webp',
                'size_bytes': len(webp_bytes)
            }
    except Exception as e:
        print(f"Cloudinary upload failed: {e}. Falling back to local storage.")

    # 3. Fallback to local storage
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    local_path = os.path.join(UPLOADS_DIR, webp_filename)
    with open(local_path, 'wb') as f:
        f.write(webp_bytes)

    local_url = f"/uploads/{webp_filename}"
    return {
        'success': True,
        'url': local_url,
        'filename': webp_filename,
        'is_cdn': False,
        'warning': 'Gambar disimpan secara lokal. Agar gambar tampil di blog publik tanpa broken image, konfigurasikan CLOUDINARY_URL di .env.',
        'format': 'webp',
        'size_bytes': len(webp_bytes)
    }

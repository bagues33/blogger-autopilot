"""
Settings Router for Blogger Auto-Pilot SaaS
Handles prompt templates, SEO knowledge base saves, PDF ingestion, and tenant notification preferences.
"""

import os
import io
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pypdf import PdfReader

from db_saas import get_saas_db
from models_saas import NotificationSetting
from notification_service import send_telegram_message, send_webhook_event
from dependencies import (
    get_session_user,
    get_or_create_default_admin,
    SEO_KB_PATH,
    SEO_PROMPT_PATH
)

router = APIRouter(tags=['Settings'])

# --- Request Schemas ---

class PromptSaveReq(BaseModel):
    content: str

class KbSaveReq(BaseModel):
    content: str

class NotificationSettingsReq(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_url: Optional[str] = None
    notify_on_draft: Optional[bool] = True
    notify_on_publish: Optional[bool] = True
    notify_on_credit_low: Optional[bool] = True
    is_active: Optional[bool] = True

class NotificationTestReq(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_url: Optional[str] = None

# --- Endpoints ---

@router.get('/api/prompt')
def api_get_prompt(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    if user and user.custom_prompt:
        return {'success': True, 'content': user.custom_prompt}
    default_prompt = ''
    if os.path.exists(SEO_PROMPT_PATH):
        with open(SEO_PROMPT_PATH, 'r', encoding='utf-8') as f:
            default_prompt = f.read()
    return {'success': True, 'content': default_prompt}

@router.post('/api/prompt/save')
def api_save_prompt(req: PromptSaveReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    if user:
        user.custom_prompt = req.content
        db.commit()
    return {'success': True}

@router.get('/api/kb')
def api_get_kb(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    if user and user.custom_kb:
        return {'success': True, 'content': user.custom_kb}
    default_kb = ''
    if os.path.exists(SEO_KB_PATH):
        with open(SEO_KB_PATH, 'r', encoding='utf-8') as f:
            default_kb = f.read()
    return {'success': True, 'content': default_kb}

@router.post('/api/kb/save')
def api_save_kb(req: KbSaveReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    if user:
        user.custom_kb = req.content
        db.commit()
    return {'success': True}

@router.post('/api/kb/upload-pdf')
async def api_upload_pdf(request: Request, files: List[UploadFile] = File(...), db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    try:
        total_pages = 0
        added_texts = []
        for file in files:
            contents = await file.read()
            if len(contents) > 25 * 1024 * 1024:
                return {'success': False, 'error': f"Ukuran file {file.filename} melebihi batas maksimal 25MB."}
            reader = PdfReader(io.BytesIO(contents))
            total_pages += len(reader.pages)
            extracted_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    extracted_text.append(f"\n--- [{file.filename} - Halaman {i+1}] ---\n" + text.strip())
            if extracted_text:
                added_texts.append(f"\n\n## Materi Tambahan dari Dokumen PDF: {file.filename}\n" + "\n".join(extracted_text))
                
        existing_content = user.custom_kb if (user and user.custom_kb) else ''
        if not existing_content and os.path.exists(SEO_KB_PATH):
            with open(SEO_KB_PATH, 'r', encoding='utf-8') as f:
                existing_content = f.read()
                
        new_content = existing_content + "".join(added_texts)
        if user:
            user.custom_kb = new_content
            db.commit()
            
        return {'success': True, 'total_files': len(files), 'total_pages': total_pages, 'content': new_content}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@router.get('/api/notifications/settings')
def api_get_notification_settings(request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    setting = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    
    if not setting:
        return {
            'telegram_bot_token': '',
            'telegram_chat_id': '',
            'webhook_url': '',
            'notify_on_draft': True,
            'notify_on_publish': True,
            'notify_on_credit_low': True,
            'is_active': True
        }
    
    return {
        'telegram_bot_token': setting.telegram_bot_token or '',
        'telegram_chat_id': setting.telegram_chat_id or '',
        'webhook_url': setting.webhook_url or '',
        'notify_on_draft': setting.notify_on_draft,
        'notify_on_publish': setting.notify_on_publish,
        'notify_on_credit_low': setting.notify_on_credit_low,
        'is_active': setting.is_active
    }

@router.post('/api/notifications/settings')
def api_save_notification_settings(req: NotificationSettingsReq, request: Request, db: Session = Depends(get_saas_db)):
    user = get_session_user(request, db) or get_or_create_default_admin(db)
    setting = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    
    if not setting:
        setting = NotificationSetting(
            user_id=user.id,
            telegram_bot_token=req.telegram_bot_token,
            telegram_chat_id=req.telegram_chat_id,
            webhook_url=req.webhook_url,
            notify_on_draft=req.notify_on_draft if req.notify_on_draft is not None else True,
            notify_on_publish=req.notify_on_publish if req.notify_on_publish is not None else True,
            notify_on_credit_low=req.notify_on_credit_low if req.notify_on_credit_low is not None else True,
            is_active=req.is_active if req.is_active is not None else True
        )
        db.add(setting)
    else:
        if req.telegram_bot_token is not None:
            setting.telegram_bot_token = req.telegram_bot_token
        if req.telegram_chat_id is not None:
            setting.telegram_chat_id = req.telegram_chat_id
        if req.webhook_url is not None:
            setting.webhook_url = req.webhook_url
        if req.notify_on_draft is not None:
            setting.notify_on_draft = req.notify_on_draft
        if req.notify_on_publish is not None:
            setting.notify_on_publish = req.notify_on_publish
        if req.notify_on_credit_low is not None:
            setting.notify_on_credit_low = req.notify_on_credit_low
        if req.is_active is not None:
            setting.is_active = req.is_active
            
    db.commit()
    return {'success': True, 'message': 'Pengaturan notifikasi berhasil disimpan.'}

@router.post('/api/notifications/test')
def api_test_notification(req: NotificationTestReq):
    results = {}
    
    if req.telegram_bot_token and req.telegram_chat_id:
        test_msg = (
            "✅ <b>Blogger Auto-Pilot: Tes Notifikasi Berhasil!</b>\n\n"
            "Bot Telegram Anda telah terhubung secara sukses dengan Blogger Auto-Pilot SaaS.\n"
            "Notifikasi artikel otomatis akan dikirim ke sini."
        )
        results['telegram'] = send_telegram_message(req.telegram_bot_token, req.telegram_chat_id, test_msg)
        
    if req.webhook_url:
        results['webhook'] = send_webhook_event(
            req.webhook_url,
            "test_notification",
            {"message": "Tes webhook berhasil dari Blogger Auto-Pilot SaaS!"}
        )
        
    if not results:
        return {'success': False, 'error': 'Harap masukkan Telegram Bot Token & Chat ID atau Webhook URL untuk diuji.'}
        
    return {'success': True, 'results': results}

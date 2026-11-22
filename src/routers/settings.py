"""
Settings Router for Blogger Auto-Pilot SaaS
Handles prompt templates, SEO knowledge base saves, PDF ingestion, and tenant notification preferences.
"""

import os
import io
from typing import Optional, List
from fastapi import APIRouter, Request, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pypdf import PdfReader

from src.core.database import get_saas_db
from src.models.models import NotificationSetting
from src.services.notifications import send_telegram_message, send_webhook_event, validate_safe_webhook_url
from src.services.audit import record_audit_log
from src.core.dependencies import (
    get_session_user,
    get_current_user,
    get_optional_user,
    check_feature_access,
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

class ByokSettingsReq(BaseModel):
    custom_gemini_key: Optional[str] = None
    custom_openai_key: Optional[str] = None
    custom_groq_key: Optional[str] = None

# --- Endpoints ---

@router.get('/api/prompt')
def api_get_prompt(user: Optional[User] = Depends(get_optional_user), db: Session = Depends(get_saas_db)):
    if user and user.custom_prompt:
        return {'success': True, 'content': user.custom_prompt}
    default_prompt = ''
    if os.path.exists(SEO_PROMPT_PATH):
        with open(SEO_PROMPT_PATH, 'r', encoding='utf-8') as f:
            default_prompt = f.read()
    return {'success': True, 'content': default_prompt}

@router.post('/api/prompt/save')
def api_save_prompt(req: PromptSaveReq, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    user.custom_prompt = req.content
    db.commit()
    return {'success': True}

@router.get('/api/kb')
def api_get_kb(user: Optional[User] = Depends(get_optional_user), db: Session = Depends(get_saas_db)):
    if user and user.custom_kb:
        return {'success': True, 'content': user.custom_kb}
    default_kb = ''
    if os.path.exists(SEO_KB_PATH):
        with open(SEO_KB_PATH, 'r', encoding='utf-8') as f:
            default_kb = f.read()
    return {'success': True, 'content': default_kb}

@router.post('/api/kb/save')
def api_save_kb(req: KbSaveReq, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    if not check_feature_access(user, 'custom_kb'):
        raise HTTPException(
            status_code=403,
            detail="Fitur Custom Knowledge Base domain memerlukan paket Pro Publisher atau Agency Network. Silakan upgrade paket Anda."
        )
    user.custom_kb = req.content
    db.commit()
    return {'success': True}

@router.post('/api/kb/upload-pdf')
async def api_upload_pdf(files: List[UploadFile] = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    if not check_feature_access(user, 'custom_kb'):
        raise HTTPException(
            status_code=403,
            detail="Ingest dokumen PDF untuk Knowledge Base memerlukan paket Pro Publisher atau Agency Network. Silakan upgrade paket Anda."
        )
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
def api_get_notification_settings(user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
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
def api_save_notification_settings(req: NotificationSettingsReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    if req.webhook_url:
        try:
            req.webhook_url = validate_safe_webhook_url(req.webhook_url)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

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
def api_test_notification(req: NotificationTestReq, user: User = Depends(get_current_user)):
    results = {}
    
    if req.telegram_bot_token and req.telegram_chat_id:
        test_msg = (
            "✅ <b>Blogger Auto-Pilot: Tes Notifikasi Berhasil!</b>\n\n"
            "Bot Telegram Anda telah terhubung secara sukses dengan Blogger Auto-Pilot SaaS.\n"
            "Notifikasi artikel otomatis akan dikirim ke sini."
        )
        results['telegram'] = send_telegram_message(req.telegram_bot_token, req.telegram_chat_id, test_msg)
        
    if req.webhook_url:
        try:
            safe_url = validate_safe_webhook_url(req.webhook_url)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        results['webhook'] = send_webhook_event(
            safe_url,
            "test_notification",
            {"message": "Tes webhook berhasil dari Blogger Auto-Pilot SaaS!"}
        )
        
    if not results:
        return {'success': False, 'error': 'Harap masukkan Telegram Bot Token & Chat ID atau Webhook URL untuk diuji.'}
        
    return {'success': True, 'results': results}

def mask_key(k: Optional[str]) -> Optional[str]:
    if not k:
        return None
    k_str = k.strip()
    if len(k_str) <= 8:
        return "********"
    return f"{k_str[:4]}...{k_str[-4:]}"

@router.get('/api/settings/byok')
def api_get_byok(user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    allowed = check_feature_access(user, 'byok')
    return {
        'success': True,
        'allowed': allowed,
        'byok_active': allowed and bool(user.custom_gemini_key or user.custom_openai_key or user.custom_groq_key),
        'has_gemini': bool(user.custom_gemini_key),
        'has_openai': bool(user.custom_openai_key),
        'has_groq': bool(user.custom_groq_key),
        'masked_gemini': mask_key(user.custom_gemini_key),
        'masked_openai': mask_key(user.custom_openai_key),
        'masked_groq': mask_key(user.custom_groq_key),
    }

@router.post('/api/settings/byok')
def api_save_byok(req: ByokSettingsReq, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_saas_db)):
    if not check_feature_access(user, 'byok'):
        raise HTTPException(
            status_code=403,
            detail="Fitur BYOK (Bring Your Own Key) memerlukan paket Pro Publisher atau Agency Network. Silakan upgrade paket Anda."
        )
    
    updated_providers = []
    if req.custom_gemini_key is not None:
        val = req.custom_gemini_key.strip()
        user.custom_gemini_key = val if val else None
        updated_providers.append("gemini")
    if req.custom_openai_key is not None:
        val = req.custom_openai_key.strip()
        user.custom_openai_key = val if val else None
        updated_providers.append("openai")
    if req.custom_groq_key is not None:
        val = req.custom_groq_key.strip()
        user.custom_groq_key = val if val else None
        updated_providers.append("groq")

    db.commit()

    record_audit_log(
        db=db,
        event_type="byok.updated",
        user_id=user.id,
        metadata={"providers": updated_providers, "byok_active": bool(user.custom_gemini_key or user.custom_openai_key or user.custom_groq_key)},
        ip_address=request.client.host if request.client else None
    )

    return {
        'success': True,
        'message': 'Kunci API LLM pribadi (BYOK) berhasil diperbarui.',
        'byok_active': bool(user.custom_gemini_key or user.custom_openai_key or user.custom_groq_key)
    }


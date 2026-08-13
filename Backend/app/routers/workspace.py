import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_token_payload
from app.models.api_key_request import APIKey
from app.models.employee import Employee
from app.models.workspace import ChatMessage, ChatSession, PersonalAPIKey, WorkspaceFile
from app.schemas.workspace import ChatInput, FileInput, FileUpdate, PersonalKeyInput, RenameInput
from app.ai import ChatService
from app.ai.routing import ProviderCandidate
from app.providers.registry import configured_model
from app.cache import response_cache
from app.services.api_key_workflow import _cipher
from app.services.analytics_service import descendants

router = APIRouter(prefix="/workspace", tags=["AI Workspace"])
logger = logging.getLogger(__name__)


def _key_fingerprint(secret: str) -> str:
    if not secret:
        return "<missing>"
    return f"{secret[:8]}...{secret[-4:]}"


def _log_key_selection(source: str, record_id, provider: str, model: str, secret: str):
    source_label = {"personal": "Personal API key", "organization": "Organization API key"}.get(source, source)
    logger.warning("API_KEY_SELECTION source=%s record_id=%s provider=%s model=%s fingerprint=%s", source_label, record_id, provider, model, _key_fingerprint(secret))

def principal(payload, db):
    kind = payload.get("type")
    if kind == "company": return "company", payload["company_id"], payload["company_id"]
    if kind == "employee":
        employee = db.get(Employee, payload["employee_id"])
        if not employee: raise HTTPException(401, "Account not found")
        return "employee", employee.id, employee.company_id
    raise HTTPException(401, "Invalid account")


def owned(query, model, actor):
    return query.filter(model.owner_type == actor[0], model.owner_id == actor[1])


def company_keys(db, actor):
    kind, owner_id, company_id = actor
    approved = db.query(APIKey).filter(APIKey.is_active.is_(True), APIKey.company_id == company_id)
    # Company admins manage approvals through the company API-key endpoints,
    # but member/manager keys are not company chat credentials. Employees can
    # only use keys created for their own approved request.
    if kind == "company":
        return approved.filter(False)
    if kind == "employee":
        approved = approved.filter(APIKey.employee_id == owner_id)
    return approved.order_by(case((APIKey.employee_id == owner_id, 0), else_=1), APIKey.created_at.desc())


def source(db, actor, key_id=None, key_source=None):
    if key_id is not None and key_source == "organization":
        key = company_keys(db, actor).filter(APIKey.id == key_id).first()
        if not key: return None
        secret = _cipher().decrypt(key.encrypted_api_key.encode()).decode()
        _log_key_selection("organization", key.id, key.provider, key.model, secret)
        return key.provider, configured_model(key.provider, key.model), secret, "organization", key.remaining_budget, None

    personal_query = owned(db.query(PersonalAPIKey).filter(PersonalAPIKey.is_active.is_(True)), PersonalAPIKey, actor)
    if key_id is not None and key_source == "personal":
        personal_query = personal_query.filter(PersonalAPIKey.id == key_id)
        personal = personal_query.first()
        if not personal: return None
        secret = _cipher().decrypt(personal.encrypted_api_key.encode()).decode()
        _log_key_selection("personal", personal.id, personal.provider, personal.model, secret)
        return personal.provider, configured_model(personal.provider, personal.model), secret, "personal", None, personal.api_base_url

    if key_id is not None:
        # Backward compatibility for older clients that only send an ID.
        personal = personal_query.filter(PersonalAPIKey.id == key_id).first()
        if personal:
            secret = _cipher().decrypt(personal.encrypted_api_key.encode()).decode()
            _log_key_selection("personal", personal.id, personal.provider, personal.model, secret)
            return personal.provider, configured_model(personal.provider, personal.model), secret, "personal", None, personal.api_base_url
        key = company_keys(db, actor).filter(APIKey.id == key_id).first()
        if key:
            secret = _cipher().decrypt(key.encrypted_api_key.encode()).decode()
            _log_key_selection("organization", key.id, key.provider, key.model, secret)
            return key.provider, configured_model(key.provider, key.model), secret, "organization", key.remaining_budget, None
        return None

    key = company_keys(db, actor).first()
    if key:
        secret = _cipher().decrypt(key.encrypted_api_key.encode()).decode()
        _log_key_selection("organization", key.id, key.provider, key.model, secret)
        return key.provider, configured_model(key.provider, key.model), secret, "organization", key.remaining_budget, None

    if key_id is None:
        personal_query = personal_query.order_by(PersonalAPIKey.is_default.desc(), PersonalAPIKey.last_used_at.desc().nullslast(), PersonalAPIKey.updated_at.desc())
    personal = personal_query.first()
    if personal:
        secret = _cipher().decrypt(personal.encrypted_api_key.encode()).decode()
        _log_key_selection("personal", personal.id, personal.provider, personal.model, secret)
        return personal.provider, configured_model(personal.provider, personal.model), secret, "personal", None, personal.api_base_url
    return None


def credential_candidates(db, actor):
    candidates = []
    for key in company_keys(db, actor).all():
        candidates.append(ProviderCandidate(key.provider, configured_model(key.provider, key.model), _cipher().decrypt(key.encrypted_api_key.encode()).decode(), "organization", key.id))
    personal = owned(db.query(PersonalAPIKey).filter(PersonalAPIKey.is_active.is_(True)), PersonalAPIKey, actor).order_by(PersonalAPIKey.is_default.desc(), PersonalAPIKey.updated_at.desc()).all()
    for key in personal:
        candidates.append(ProviderCandidate(key.provider, configured_model(key.provider, key.model), _cipher().decrypt(key.encrypted_api_key.encode()).decode(), "personal", key.id, key.api_base_url))
    return candidates


@router.get("/connection")
def connection(db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    resolved = source(db, principal(payload, db))
    if not resolved: return {"status": "setup_required", "provider": None, "model": None, "remaining_quota": None}
    provider, model, _, origin, quota, _ = resolved
    return {"status": "connected", "provider": provider, "model": model, "source": origin, "remaining_quota": quota}


@router.put("/personal-key")
def set_personal_key(data: PersonalKeyInput, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db)
    record = owned(db.query(PersonalAPIKey), PersonalAPIKey, actor).first()
    if not record:
        record = PersonalAPIKey(owner_type=actor[0], owner_id=actor[1], provider=data.provider, model=data.model, label=data.label or f"{data.provider} · {data.model}", api_base_url=str(data.api_base_url) if data.api_base_url else None, encrypted_api_key="")
        db.add(record)
    effective_model = configured_model(data.provider, data.model)
    record.provider, record.model, record.label, record.api_base_url, record.encrypted_api_key, record.is_active = data.provider, effective_model, data.label or record.label or f"{data.provider} · {effective_model}", str(data.api_base_url) if data.api_base_url else None, _cipher().encrypt(data.api_key.get_secret_value().strip().encode()).decode(), True
    db.commit()
    return {"status": "connected", "provider": record.provider, "model": record.model, "source": "personal"}


@router.post("/personal-key")
def add_personal_key(data: PersonalKeyInput, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db)
    record = PersonalAPIKey(
        owner_type=actor[0],
        owner_id=actor[1],
        provider=data.provider,
        model=configured_model(data.provider, data.model),
        label=data.label or f"{data.provider} · {data.model}",
        api_base_url=str(data.api_base_url) if data.api_base_url else None,
        encrypted_api_key=_cipher().encrypt(data.api_key.get_secret_value().strip().encode()).decode(),
        is_active=True,
    )
    db.add(record)
    db.commit()
    return {"status": "connected", "provider": record.provider, "model": record.model, "source": "personal"}


@router.get("/personal-keys")
def personal_keys(db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db)
    records = owned(db.query(PersonalAPIKey).filter(PersonalAPIKey.is_active.is_(True)), PersonalAPIKey, actor).order_by(PersonalAPIKey.is_default.desc(), PersonalAPIKey.updated_at.desc()).all()
    return [{"id": key.id, "source": "personal", "label": key.label or f"{key.provider} · {key.model}", "provider": key.provider, "model": key.model, "is_default": key.is_default, "last_used_at": key.last_used_at, "encrypted": True} for key in records]


@router.get("/connections")
def connections(db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db)
    personal = owned(db.query(PersonalAPIKey).filter(PersonalAPIKey.is_active.is_(True)), PersonalAPIKey, actor).order_by(PersonalAPIKey.is_default.desc(), PersonalAPIKey.updated_at.desc()).all()
    organization = company_keys(db, actor).all()
    company_label = "Company" if actor[0] == "company" else "Organization"
    return {
        "personal": [{"id": key.id, "source": "personal", "label": key.label or f"{key.provider} · {key.model}", "provider": key.provider, "model": key.model, "is_default": key.is_default, "last_used_at": key.last_used_at, "encrypted": True} for key in personal],
        "organization": [{"id": key.id, "source": "organization", "label": f"{company_label} {key.provider}", "provider": key.provider, "model": key.model, "is_default": False, "last_used_at": None, "encrypted": True, "remaining_budget": key.remaining_budget} for key in organization],
    }


@router.patch("/personal-keys/{key_id}")
def update_personal_key(key_id: int, data: dict, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db)
    key = owned(db.query(PersonalAPIKey).filter(PersonalAPIKey.id == key_id, PersonalAPIKey.is_active.is_(True)), PersonalAPIKey, actor).first()
    if not key: raise HTTPException(404, "API key not found")
    if "label" in data: key.label = str(data["label"]).strip()[:100] or key.label
    if data.get("is_default"):
        owned(db.query(PersonalAPIKey), PersonalAPIKey, actor).update({PersonalAPIKey.is_default: False}, synchronize_session=False)
        key.is_default = True
    db.commit()
    return {"id": key.id, "label": key.label, "provider": key.provider, "model": key.model, "is_default": key.is_default}


@router.delete("/personal-keys/{key_id}")
def delete_personal_key(key_id: int, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db)
    key = owned(db.query(PersonalAPIKey).filter(PersonalAPIKey.id == key_id), PersonalAPIKey, actor).first()
    if not key: raise HTTPException(404, "API key not found")
    db.delete(key); db.commit(); return {"ok": True}


@router.get("/chats")
def chats(q: str | None = None, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); query = owned(db.query(ChatSession), ChatSession, actor)
    if q: query = query.filter(ChatSession.title.ilike(f"%{q}%"))
    return [{"id": x.id, "title": x.title, "updated_at": x.updated_at} for x in query.order_by(ChatSession.updated_at.desc()).all()]


@router.post("/chats")
def create_chat(db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    raise HTTPException(422, "A conversation is created when its first message is submitted.")


@router.get("/chats/{chat_id}")
def get_chat(chat_id: int, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); chat = owned(db.query(ChatSession).filter(ChatSession.id == chat_id), ChatSession, actor).first()
    if not chat: raise HTTPException(404, "Chat not found")
    return {"id": chat.id, "title": chat.title, "messages": [{"id": m.id, "role": m.role, "content": m.content, "images": m.attachments or [], "provider": m.provider, "model": m.model, "api_key_id": m.api_key_id, "api_key_source": m.api_key_source, "token_usage": m.token_usage, "estimated_cost": m.estimated_cost, "latency_ms": m.latency_ms, "optimization": m.optimization_report, "created_at": m.created_at} for m in db.query(ChatMessage).filter(ChatMessage.session_id == chat.id).order_by(ChatMessage.created_at).all()]}


@router.patch("/chats/{chat_id}")
def rename_chat(chat_id: int, data: RenameInput, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); chat = owned(db.query(ChatSession).filter(ChatSession.id == chat_id), ChatSession, actor).first()
    if not chat: raise HTTPException(404, "Chat not found")
    chat.title = data.title; db.commit(); return {"id": chat.id, "title": chat.title}


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); chat = owned(db.query(ChatSession).filter(ChatSession.id == chat_id), ChatSession, actor).first()
    if not chat: raise HTTPException(404, "Chat not found")
    db.query(ChatMessage).filter(ChatMessage.session_id == chat.id).delete(); db.delete(chat); db.commit(); return {"ok": True}


def _send_message(chat_id: int | None, data: ChatInput, db: Session, payload):
    actor = principal(payload, db)
    chat = owned(db.query(ChatSession).filter(ChatSession.id == chat_id), ChatSession, actor).first() if chat_id is not None else None
    if chat_id is not None and not chat: raise HTTPException(404, "Chat not found")

    selected = source(db, actor, data.key_id, data.key_source)
    if not selected:
        raise HTTPException(428, "Add a personal API key or request organization access to start chatting.")
    if chat is None:
        chat = ChatSession(owner_type=actor[0], owner_id=actor[1], company_id=actor[2])
        db.add(chat); db.flush()
    selected_candidate = ProviderCandidate(selected[0], selected[1], selected[2], selected[3], data.key_id, selected[5])
    history = [{"role": item.role, "content": item.content, "images": item.attachments or []} for item in db.query(ChatMessage).filter(ChatMessage.session_id == chat.id).order_by(ChatMessage.created_at, ChatMessage.id).all()]
    images = [image.model_dump() for image in data.images]
    user_content = data.content.strip() or ("[Image attachment]" if data.images else "[Attached document]")
    documents = [document.model_dump() for document in data.documents]
    code_files = [code_file.model_dump() for code_file in data.code_files]
    result = ChatService().generate(user_content, history, images, selected_candidate, credential_candidates(db, actor), documents, code_files, cache_scope=f"{actor[0]}:{actor[1]}", tenant_scope=f"company:{actor[2]}" if actor[2] else f"{actor[0]}:{actor[1]}")
    user_message = ChatMessage(session_id=chat.id, role="user", content=user_content, attachments=images or None)
    assistant_message = ChatMessage(session_id=chat.id, role="assistant", content=result.content, provider=result.provider, model=result.model, api_key_id=data.key_id, api_key_source=data.key_source, token_usage=result.estimated_tokens, estimated_cost=str(result.optimization.get("cost_after", 0)), latency_ms=result.latency_ms, optimization_report=result.optimization)
    db.add_all([user_message, assistant_message])
    if chat.title == "New conversation":
        chat.title = user_content[:60]
    db.commit(); db.refresh(assistant_message)
    return {"id": assistant_message.id, "chat_id": chat.id, "role": "assistant", "content": result.content, "images": [], "provider": result.provider, "model": result.model, "api_key_id": assistant_message.api_key_id, "api_key_source": assistant_message.api_key_source, "token_usage": result.estimated_tokens, "estimated_cost": assistant_message.estimated_cost, "latency_ms": result.latency_ms, "optimization": result.optimization, "request_id": result.request_id, "complexity": result.complexity, "confidence": result.confidence}


@router.post("/chats/messages")
def send_message_to_new_chat(data: ChatInput, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    return _send_message(None, data, db, payload)


@router.post("/chats/{chat_id}/messages")
def send_message(chat_id: int, data: ChatInput, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    return _send_message(chat_id, data, db, payload)

@router.get("/files")
def files(db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); return owned(db.query(WorkspaceFile), WorkspaceFile, actor).order_by(WorkspaceFile.updated_at.desc()).all()


@router.post("/files")
def create_file(data: FileInput, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); file = WorkspaceFile(owner_type=actor[0], owner_id=actor[1], company_id=actor[2], **data.model_dump()); db.add(file); db.commit(); db.refresh(file); return file


@router.patch("/files/{file_id}")
def update_file(file_id: int, data: FileUpdate, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); file = owned(db.query(WorkspaceFile).filter(WorkspaceFile.id == file_id), WorkspaceFile, actor).first()
    if not file: raise HTTPException(404, "File not found")
    for key, value in data.model_dump(exclude_none=True).items(): setattr(file, key, value)
    db.commit(); db.refresh(file); return file


@router.delete("/files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); file = owned(db.query(WorkspaceFile).filter(WorkspaceFile.id == file_id), WorkspaceFile, actor).first()
    if not file: raise HTTPException(404, "File not found")
    db.delete(file); db.commit(); return {"ok": True}


@router.get("/optimization/settings")
def get_optimization_settings():
    return {"prompt_enabled": True, "document_enabled": True, "code_enabled": True, "context_enabled": True, "smart_cache_enabled": True, "similarity_threshold": 0.0, "optimization_level": "prompt-context-document-code-response-cache"}


@router.patch("/optimization/settings")
def update_optimization_settings(data: dict):
    return {"prompt_enabled": True, "document_enabled": True, "code_enabled": True, "context_enabled": True, "smart_cache_enabled": True, "similarity_threshold": 0.0, "optimization_level": "prompt-context-document-code-response-cache"}


@router.get("/optimization/analytics")
def optimization_analytics(db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db)
    if actor[0] == "company":
        sessions = db.query(ChatSession.id).filter(ChatSession.company_id == actor[2]).subquery()
    elif actor[0] == "employee":
        employee = db.get(Employee, actor[1])
        ids = [actor[1], *[item.id for item in descendants(employee)]] if employee and employee.role.value == "manager" else [actor[1]]
        sessions = db.query(ChatSession.id).filter(ChatSession.owner_type == "employee", ChatSession.owner_id.in_(ids)).subquery()
    else:
        sessions = db.query(ChatSession.id).filter(ChatSession.owner_type == actor[0], ChatSession.owner_id == actor[1]).subquery()

    messages = db.query(ChatMessage).filter(ChatMessage.session_id.in_(db.query(sessions.c.id)), ChatMessage.role == "assistant", ChatMessage.optimization_report.isnot(None)).order_by(ChatMessage.created_at.desc()).all()
    reports = [item.optimization_report for item in messages if item.optimization_report]
    total = len(reports)
    original_tokens = sum(int(item.get("overall_original_tokens", item.get("original_tokens", 0))) for item in reports)
    optimized_tokens = sum(int(item.get("overall_optimized_tokens", item.get("optimized_tokens", 0))) for item in reports)
    saved_tokens = sum(int(item.get("overall_tokens_saved", item.get("saved_tokens", 0))) for item in reports)
    cost_before = sum(float(item.get("overall_cost_before", item.get("cost_before", 0))) for item in reports)
    cost_after = sum(float(item.get("overall_cost_after", item.get("cost_after", 0))) for item in reports)
    cost_saved = sum(float(item.get("overall_cost_saved", item.get("cost_saved", 0))) for item in reports)
    context_original_tokens = sum(int(item.get("original_context_tokens", 0)) for item in reports)
    context_optimized_tokens = sum(int(item.get("optimized_context_tokens", 0)) for item in reports)
    context_saved_tokens = sum(int(item.get("context_saved_tokens", 0)) for item in reports)
    context_cost_before = sum(float(item.get("context_cost_before", 0)) for item in reports)
    context_cost_after = sum(float(item.get("context_cost_after", 0)) for item in reports)
    context_cost_saved = sum(float(item.get("context_cost_saved", 0)) for item in reports)
    context_requests = sum(1 for item in reports if "original_context_tokens" in item)
    document_original_tokens = sum(int(item.get("document_original_tokens", 0)) for item in reports)
    document_optimized_tokens = sum(int(item.get("document_optimized_tokens", 0)) for item in reports)
    document_saved_tokens = sum(int(item.get("document_tokens_saved", 0)) for item in reports)
    document_cost_before = sum(float(item.get("document_cost_before", 0)) for item in reports)
    document_cost_after = sum(float(item.get("document_cost_after", 0)) for item in reports)
    document_cost_saved = sum(float(item.get("document_cost_saved", 0)) for item in reports)
    document_requests = sum(1 for item in reports if "document_original_tokens" in item and item.get("document_original_tokens", 0) > 0)
    code_original_tokens = sum(int(item.get("code_original_tokens", 0)) for item in reports)
    code_optimized_tokens = sum(int(item.get("code_optimized_tokens", 0)) for item in reports)
    code_saved_tokens = sum(int(item.get("code_tokens_saved", 0)) for item in reports)
    code_cost_before = sum(float(item.get("code_cost_before", 0)) for item in reports)
    code_cost_after = sum(float(item.get("code_cost_after", 0)) for item in reports)
    code_cost_saved = sum(float(item.get("code_cost_saved", 0)) for item in reports)
    code_requests = sum(1 for item in reports if item.get("code_original_tokens", 0) > 0)
    cache_stats = response_cache.stats()
    cache_dashboard = response_cache.tenant_stats(f"company:{actor[2]}" if actor[2] else f"{actor[0]}:{actor[1]}")
    return {
        "original_tokens": original_tokens,
        "optimized_tokens": optimized_tokens,
        "total_tokens_saved": saved_tokens,
        "tokens_saved": saved_tokens,
        "percentage_saved": round((saved_tokens / original_tokens) * 100, 2) if original_tokens else 0,
        "average_token_reduction": round((saved_tokens / original_tokens) * 100, 2) if original_tokens else 0,
        "estimated_cost_before": round(cost_before, 8),
        "estimated_cost_after": round(cost_after, 8),
        "estimated_cost_saved": round(cost_saved, 8),
        "context_original_tokens": context_original_tokens,
        "context_optimized_tokens": context_optimized_tokens,
        "context_tokens_saved": context_saved_tokens,
        "context_percentage_saved": round((context_saved_tokens / context_original_tokens) * 100, 2) if context_original_tokens else 0,
        "context_estimated_cost_before": round(context_cost_before, 8),
        "context_estimated_cost_after": round(context_cost_after, 8),
        "context_estimated_cost_saved": round(context_cost_saved, 8),
        "average_context_reduction": round((context_saved_tokens / context_original_tokens) * 100, 2) if context_original_tokens else 0,
        "context_optimization_success_rate": 100 if context_requests else 0,
        "context_optimized_requests": context_requests,
        "document_original_tokens": document_original_tokens,
        "document_optimized_tokens": document_optimized_tokens,
        "document_tokens_saved": document_saved_tokens,
        "document_percentage_saved": round((document_saved_tokens / document_original_tokens) * 100, 2) if document_original_tokens else 0,
        "document_estimated_cost_before": round(document_cost_before, 8),
        "document_estimated_cost_after": round(document_cost_after, 8),
        "document_estimated_cost_saved": round(document_cost_saved, 8),
        "average_document_tokens_saved": round(document_saved_tokens / document_requests, 2) if document_requests else 0,
        "average_document_cost_saved": round(document_cost_saved / document_requests, 8) if document_requests else 0,
        "document_optimization_success_rate": 100 if document_requests else 0,
        "document_optimized_requests": document_requests,
        "code_original_tokens": code_original_tokens,
        "code_optimized_tokens": code_optimized_tokens,
        "code_tokens_saved": code_saved_tokens,
        "code_percentage_saved": round((code_saved_tokens / code_original_tokens) * 100, 2) if code_original_tokens else 0,
        "code_estimated_cost_before": round(code_cost_before, 8),
        "code_estimated_cost_after": round(code_cost_after, 8),
        "code_estimated_cost_saved": round(code_cost_saved, 8),
        "average_code_tokens_saved": round(code_saved_tokens / code_requests, 2) if code_requests else 0,
        "average_code_cost_saved": round(code_cost_saved / code_requests, 8) if code_requests else 0,
        "code_optimization_success_rate": 100 if code_requests else 0,
        "code_optimized_requests": code_requests,
        "average_cost_saved_per_request": round(cost_saved / total, 8) if total else 0,
        "number_of_optimized_requests": total,
        "optimization_success_rate": 100 if total else 0,
        "total_requests": total,
        "chat_requests": total,
        "ide_requests": 0,
        "total_tokens_processed": original_tokens,
        "average_tokens_saved_per_request": round(saved_tokens / total, 2) if total else 0,
        "cache_hits": cache_dashboard["total_optimization"]["cache_hits"],
        "cache_misses": cache_dashboard["global_cache"]["misses"] + cache_dashboard["private_cache"]["misses"],
        "semantic_cache_hits": cache_dashboard["global_cache"]["semantic_hits"] + cache_dashboard["private_cache"]["semantic_hits"],
        "semantic_cache_misses": cache_dashboard["global_cache"]["semantic_misses"] + cache_dashboard["private_cache"]["semantic_misses"],
        "cache_hit_rate": cache_dashboard["total_optimization"]["cache_hit_rate"],
        "api_calls_avoided": cache_dashboard["total_optimization"]["api_calls_avoided"],
        "average_response_time_saved_ms": cache_stats["average_response_time_saved_ms"],
        "cache_dashboard": cache_dashboard,
        "breakdown": {
            "prompt": sum(int(item.get("prompt_tokens_saved", 0)) for item in reports),
            "context": context_saved_tokens,
            "document": document_saved_tokens,
            "code": code_saved_tokens,
        },
        "recent": [{"id": message.id, "module": "prompt", "report": report, "created_at": message.created_at} for message, report in zip(messages[:10], reports[:10])],
    }

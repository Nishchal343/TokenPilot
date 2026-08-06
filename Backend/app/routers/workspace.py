import logging
from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_token_payload
from app.models.api_key_request import APIKey
from app.models.employee import Employee
from app.models.workspace import ChatMessage, ChatSession, PersonalAPIKey, WorkspaceFile
from app.schemas.workspace import ChatInput, FileInput, FileUpdate, PersonalKeyInput, RenameInput
from app.services.ai_providers import ProviderRequestError, provider_for
from app.services.api_key_workflow import _cipher

router = APIRouter(prefix="/workspace", tags=["AI Workspace"])
logger = logging.getLogger(__name__)

AGENT_INSTRUCTION = """You are the TokenPilot IDE coding agent. When the user asks you to create, modify, fix, or run code, perform the work-oriented response immediately. Always return the complete file contents in fenced code blocks, with the language after the opening fence. If a filename is known, mention it before the block. Do not only describe what you would do or say that you will do it. Use the supplied workspace context to understand the project and preserve existing behavior. If a terminal command is required (npm, pip, uvicorn, docker, git, tests, builds, or similar), NEVER execute it and NEVER claim it was executed. Instead provide one fenced block tagged bash or powershell containing only the command, explain its purpose, and ask the user to run it locally and paste the output. Analyze only terminal output the user actually provides. If the user supplies logs, identify errors, warnings, missing dependencies, stack traces, and success messages in simple language, then suggest fixes or generate required code changes. If the user asks to run or preview a file, say exactly which file should be run after providing its contents."""


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
    if kind == "employee": approved = approved.filter(APIKey.employee_id == owner_id)
    return approved.order_by(APIKey.created_at.desc())


def source(db, actor, key_id=None, key_source=None):
    if key_id is not None and key_source == "organization":
        key = company_keys(db, actor).filter(APIKey.id == key_id).first()
        if not key: return None
        return key.provider, key.model, _cipher().decrypt(key.encrypted_api_key.encode()).decode(), "organization", key.remaining_budget, None

    personal_query = owned(db.query(PersonalAPIKey).filter(PersonalAPIKey.is_active.is_(True)), PersonalAPIKey, actor)
    if key_id is not None and key_source == "personal":
        personal_query = personal_query.filter(PersonalAPIKey.id == key_id)
        personal = personal_query.first()
        if not personal: return None
        return personal.provider, personal.model, _cipher().decrypt(personal.encrypted_api_key.encode()).decode(), "personal", None, personal.api_base_url

    if key_id is not None:
        # Backward compatibility for older clients that only send an ID.
        personal = personal_query.filter(PersonalAPIKey.id == key_id).first()
        if personal: return personal.provider, personal.model, _cipher().decrypt(personal.encrypted_api_key.encode()).decode(), "personal", None, personal.api_base_url
        key = company_keys(db, actor).filter(APIKey.id == key_id).first()
        if key: return key.provider, key.model, _cipher().decrypt(key.encrypted_api_key.encode()).decode(), "organization", key.remaining_budget, None
        return None

    key = company_keys(db, actor).first()
    if key: return key.provider, key.model, _cipher().decrypt(key.encrypted_api_key.encode()).decode(), "organization", key.remaining_budget, None

    if key_id is None:
        personal_query = personal_query.order_by(PersonalAPIKey.is_default.desc(), PersonalAPIKey.last_used_at.desc().nullslast(), PersonalAPIKey.updated_at.desc())
    personal = personal_query.first()
    if personal: return personal.provider, personal.model, _cipher().decrypt(personal.encrypted_api_key.encode()).decode(), "personal", None, personal.api_base_url
    return None


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
    record.provider, record.model, record.label, record.api_base_url, record.encrypted_api_key, record.is_active = data.provider, data.model, data.label or record.label or f"{data.provider} · {data.model}", str(data.api_base_url) if data.api_base_url else None, _cipher().encrypt(data.api_key.get_secret_value().strip().encode()).decode(), True
    db.commit()
    return {"status": "connected", "provider": record.provider, "model": record.model, "source": "personal"}


@router.post("/personal-key")
def add_personal_key(data: PersonalKeyInput, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db)
    record = PersonalAPIKey(
        owner_type=actor[0],
        owner_id=actor[1],
        provider=data.provider,
        model=data.model,
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
    actor = principal(payload, db); chat = ChatSession(owner_type=actor[0], owner_id=actor[1], company_id=actor[2])
    db.add(chat); db.commit(); db.refresh(chat); return {"id": chat.id, "title": chat.title}


@router.get("/chats/{chat_id}")
def get_chat(chat_id: int, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); chat = owned(db.query(ChatSession).filter(ChatSession.id == chat_id), ChatSession, actor).first()
    if not chat: raise HTTPException(404, "Chat not found")
    return {"id": chat.id, "title": chat.title, "messages": [{"id": m.id, "role": m.role, "content": m.content, "images": m.attachments or [], "provider": m.provider, "model": m.model, "api_key_id": m.api_key_id, "api_key_source": m.api_key_source, "token_usage": m.token_usage, "estimated_cost": m.estimated_cost, "latency_ms": m.latency_ms, "created_at": m.created_at} for m in db.query(ChatMessage).filter(ChatMessage.session_id == chat.id).order_by(ChatMessage.created_at).all()]}


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


@router.post("/chats/{chat_id}/messages")
def send_message(chat_id: int, data: ChatInput, db: Session = Depends(get_db), payload=Depends(get_current_token_payload)):
    actor = principal(payload, db); chat = owned(db.query(ChatSession).filter(ChatSession.id == chat_id), ChatSession, actor).first()
    if not chat: raise HTTPException(404, "Chat not found")
    resolved = source(db, actor, data.key_id, data.key_source)
    if not resolved: raise HTTPException(428, "Add a personal API key or request organization access to start chatting.")
    images = [image.model_dump() for image in data.images]
    user_content = data.content.strip() or "[Image attachment]"
    user_message = ChatMessage(session_id=chat.id, role="user", content=user_content, attachments=images or None); db.add(user_message); db.flush()
    history = db.query(ChatMessage).filter(ChatMessage.session_id == chat.id).order_by(ChatMessage.created_at).all()
    provider, model, secret, _, _, base_url = resolved
    try:
        selected_key = owned(db.query(PersonalAPIKey), PersonalAPIKey, actor).filter(PersonalAPIKey.id == data.key_id).first() if data.key_id and data.key_source == "personal" else None
        if selected_key:
            selected_key.last_used_at = datetime.now(timezone.utc)
        started = perf_counter()
        provider_history = [{"role": x.role, "content": x.content, "images": x.attachments or []} for x in history]
        if provider_history and provider_history[-1]["role"] == "user":
            provider_history[-1]["content"] = f"{AGENT_INSTRUCTION}\n\nUser request:\n{provider_history[-1]['content']}"
        answer = provider_for(provider, base_url).complete(secret, model, provider_history)
        latency_ms = round((perf_counter() - started) * 1000)
    except ProviderRequestError as exc:
        logger.exception(
            "Chat provider exception provider=%s model=%s url=%s status=%s request_payload=%s response_body=%s exception=%s traceback=%s",
            exc.provider, exc.model or model, exc.url, exc.status_code, exc.request_payload, exc.response_body, exc, exc.traceback_text,
        )
        print(f"CHAT COMPLETE PROVIDER EXCEPTION provider={exc.provider} model={exc.model or model} url={exc.url} status={exc.status_code} request_payload={exc.request_payload} response_body={exc.response_body} exception={exc}\n{exc.traceback_text or ''}", flush=True)
        status_code = exc.status_code if exc.status_code and 400 <= exc.status_code <= 599 else 502
        raise HTTPException(status_code, {"provider": exc.provider, "status": exc.status_code, "url": exc.url, "request_payload": exc.request_payload, "response_body": exc.response_body, "exception": str(exc), "traceback": exc.traceback_text}) from exc
    except Exception as exc:
        raise HTTPException(502, "The AI provider could not process the request. Please try again.") from exc
    estimated_tokens = max(1, (len(data.content) + len(answer)) // 4)
    assistant_message = ChatMessage(session_id=chat.id, role="assistant", content=answer, provider=provider, model=model, api_key_id=data.key_id, api_key_source=data.key_source, token_usage=estimated_tokens, estimated_cost=f"{estimated_tokens * 0.0000008:.6f}", latency_ms=latency_ms); db.add(assistant_message)
    if chat.title == "New conversation": chat.title = user_content[:60]
    db.commit(); db.refresh(assistant_message)
    return {"id": assistant_message.id, "role": "assistant", "content": answer, "images": [], "provider": assistant_message.provider, "model": assistant_message.model, "api_key_id": assistant_message.api_key_id, "api_key_source": assistant_message.api_key_source, "token_usage": assistant_message.token_usage, "estimated_cost": assistant_message.estimated_cost, "latency_ms": assistant_message.latency_ms, "created_at": assistant_message.created_at}


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

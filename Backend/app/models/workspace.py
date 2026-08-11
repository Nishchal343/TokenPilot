from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    owner_type = Column(String(20), nullable=False, index=True)
    owner_id = Column(Integer, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="New conversation")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    provider = Column(String(50), nullable=True)
    model = Column(String(120), nullable=True)
    api_key_id = Column(Integer, nullable=True)
    api_key_source = Column(String(20), nullable=True)
    token_usage = Column(Integer, nullable=True)
    estimated_cost = Column(String(32), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    attachments = Column(JSON, nullable=True)
    optimization_report = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WorkspaceFolder(Base):
    __tablename__ = "workspace_folders"

    id = Column(Integer, primary_key=True, index=True)
    owner_type = Column(String(20), nullable=False, index=True)
    owner_id = Column(Integer, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("workspace_folders.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WorkspaceFile(Base):
    __tablename__ = "workspace_files"

    id = Column(Integer, primary_key=True, index=True)
    owner_type = Column(String(20), nullable=False, index=True)
    owner_id = Column(Integer, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    folder_id = Column(Integer, ForeignKey("workspace_folders.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False, default="")
    language = Column(String(50), nullable=False, default="plaintext")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PersonalAPIKey(Base):
    __tablename__ = "personal_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    owner_type = Column(String(20), nullable=False, index=True)
    owner_id = Column(Integer, nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(120), nullable=False)
    label = Column(String(100), nullable=True)
    api_base_url = Column(String(500), nullable=True)
    encrypted_api_key = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

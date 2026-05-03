from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    banks: Mapped[list[Bank]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Aggregated style + topic profile (set by ingestion pipeline in M3).
    analysis_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    analysis_status: Mapped[str] = mapped_column(String(16), default="idle")
    analysis_error: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="banks")
    samples: Mapped[list[SampleExam]] = relationship(
        back_populates="bank", cascade="all, delete-orphan", order_by="SampleExam.created_at.desc()"
    )


class SampleExam(Base):
    __tablename__ = "sample_exams"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    bank_id: Mapped[str] = mapped_column(
        ForeignKey("banks.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    page_count: Mapped[int] = mapped_column(default=0)

    # uploaded → extracting → analyzing → done | error
    status: Mapped[str] = mapped_column(String(16), default="uploaded")
    error: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    bank: Mapped[Bank] = relationship(back_populates="samples")
    pages: Mapped[list[SampleExamPage]] = relationship(
        back_populates="sample", cascade="all, delete-orphan", order_by="SampleExamPage.page_number"
    )


class SampleExamPage(Base):
    __tablename__ = "sample_exam_pages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    sample_id: Mapped[str] = mapped_column(
        ForeignKey("sample_exams.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int]
    image_path: Mapped[str] = mapped_column(String(500))
    vision_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    sample: Mapped[SampleExam] = relationship(back_populates="pages")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    bank_id: Mapped[str] = mapped_column(
        ForeignKey("banks.id", ondelete="CASCADE"), index=True
    )

    # queued → running → done | failed
    status: Mapped[str] = mapped_column(String(16), default="queued")
    progress_pct: Mapped[float] = mapped_column(default=0.0)
    current_step: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None)
    error: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    # The structured exam — source of truth.
    spec_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    pages: Mapped[list[GeneratedPage]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="GeneratedPage.page_number",
    )
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class GeneratedPage(Base):
    __tablename__ = "generated_pages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int]
    prompt: Mapped[str] = mapped_column(String)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)

    # queued → done | error
    status: Mapped[str] = mapped_column(String(16), default="queued")
    error: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    job: Mapped[GenerationJob] = relationship(back_populates="pages")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(String)
    spec_diff_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    job: Mapped[GenerationJob] = relationship(back_populates="messages")

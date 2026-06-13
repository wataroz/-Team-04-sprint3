"""SQLAlchemy ORM models for MoneyMind.

Schema is designed to be portable to Postgres later (Supabase/Neon):
- No SQLite-only types
- All timestamps as DateTime (UTC)
- i18n payloads stored as JSON
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Optional friendly display name (Sprint 5 — Settings page). Falls back to
    # ``name`` in the UI when empty so existing users see no change.
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    # Hard-delete grace period (Sprint 5). When set, the daily cron will purge
    # this user + all FK data once ``utcnow() >= delete_scheduled_at``. NULL =
    # account is active. Indexed so the cleanup query stays cheap on Postgres.
    delete_scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    imports: Mapped[list["Import"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preference: Mapped[Optional["Preference"]] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "display_name": self.display_name,
        }


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    bank: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="imports")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="source_import")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "bank": self.bank,
            "count": self.count,
            "imported_at": self.imported_at.isoformat(),
        }


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_import_id: Mapped[Optional[int]] = mapped_column(ForeignKey("imports.id"), nullable=True)

    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    merchant: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="other", index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="transactions")
    source_import: Mapped[Optional[Import]] = relationship(back_populates="transactions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "merchant": self.merchant,
            "amount": self.amount,
            "type": self.type,
            "category": self.category,
            "note": self.note,
        }


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="info")  # good|warn|info
    icon: Mapped[str] = mapped_column(String(32), nullable=False, default="bell")

    # i18n payloads — {th: "...", en: "..."}
    title: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    desc: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    unread: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="notifications")

    def to_dict(self) -> dict:
        # Frontend expects {type, icon, unread, title, desc, time}
        return {
            "id": self.id,
            "type": self.kind,
            "icon": self.icon,
            "unread": self.unread,
            "title": self.title,
            "desc": self.desc,
            "time": _humanize_ago(self.created_at),
        }


class Preference(Base):
    __tablename__ = "preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    accent: Mapped[str] = mapped_column(String(16), default="#D4B978", nullable=False)
    density: Mapped[str] = mapped_column(String(16), default="regular", nullable=False)
    lang: Mapped[str] = mapped_column(String(8), default="th", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="THB", nullable=False)
    show_ambient: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category_budgets: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Notification toggles (Sprint 5 — Settings page). Default TRUE so the
    # existing behaviour (push budget alerts via LINE) keeps working for all
    # current users; they can opt out from Settings → Notifications.
    budget_alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    line_notify_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Light/dark theme preference (post-Sprint 5 brand refresh). Default
    # "light" to match the cream logo background; users can toggle from
    # Settings → Appearance. Stored server-side so the choice follows the
    # user across devices/sessions.
    theme: Mapped[str] = mapped_column(String(16), default="light", nullable=False)

    user: Mapped[User] = relationship(back_populates="preference")

    def to_dict(self) -> dict:
        return {
            "accent": self.accent,
            "density": self.density,
            "lang": self.lang,
            "currency": self.currency,
            "showAmbient": self.show_ambient,
            "categoryBudgets": self.category_budgets or {},
            "budgetAlertEnabled": bool(self.budget_alert_enabled),
            "lineNotifyEnabled": bool(self.line_notify_enabled),
            "theme": self.theme or "light",
        }


class LineUser(Base):
    """Maps a LINE userId to a MoneyMind user account."""
    __tablename__ = "line_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    user: Mapped[User] = relationship()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "line_user_id": self.line_user_id,
            "user_id": self.user_id,
            "display_name": self.display_name,
        }


class MerchantOverride(Base):
    """User-specific merchant→category override (Learning Loop, Day 5).

    When the user manually re-categorises a transaction with
    ``save_pattern=true``, we persist the (normalised) merchant→category
    mapping here. Subsequent imports look up the merchant fingerprint and
    apply the override automatically so the user never has to re-tag the
    same merchant twice.

    ``merchant_norm`` is the merchant string after lowercase + strip +
    collapse-internal-whitespace — same fingerprint shape as the dedup
    path in ``app._dedup_build_rows``.
    """

    __tablename__ = "merchant_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", "merchant_norm", name="uq_user_merchant_norm"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    merchant_norm: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "merchant_norm": self.merchant_norm,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
        }


class LinePendingPdf(Base):
    """Encrypted PDF buffered while waiting for the user's password via chat.

    The LINE bot can't ask for input mid-handler the way the web flow can.
    When a user uploads a password-protected PDF, we stash the raw bytes
    here keyed by their LINE userId, reply asking for the password, and
    treat their next text message as the password.

    Lifecycle / safety rules (enforced in ``backend.line_bot``):
      * Single slot per LINE user — ``line_user_id`` is unique. Uploading a
        new locked PDF replaces (delete-then-insert) any previous pending
        row so abandoned uploads never block a fresh attempt.
      * TTL = 5 minutes from ``created_at`` (checked in ``_get_pending_pdf``).
        Expired rows are deleted on next access; no cron needed.
      * ``attempts`` is bumped on each wrong password and the row is deleted
        after 3 failures to discourage brute force.
      * Row is also deleted on successful unlock and on explicit cancel.
      * The password value itself is **never** persisted or logged — only
        the wrong-attempt counter is stored.
    """

    __tablename__ = "line_pending_pdfs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


def _humanize_ago(dt: datetime) -> dict:
    """Return an i18n 'time' label like the frontend expects."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return {"th": "เมื่อสักครู่", "en": "Just now"}
    mins = secs // 60
    if mins < 60:
        return {"th": f"{mins} นาทีที่แล้ว", "en": f"{mins}m ago"}
    hours = mins // 60
    if hours < 24:
        return {"th": f"{hours} ชม.ที่แล้ว", "en": f"{hours}h ago"}
    days = hours // 24
    return {"th": f"{days} วันที่แล้ว", "en": f"{days}d ago"}

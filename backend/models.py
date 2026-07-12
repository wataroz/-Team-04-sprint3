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
    # คืนเวลาปัจจุบันแบบ UTC (timezone-aware) — เก็บทุก timestamp เป็น UTC
    # ให้เป็นมาตรฐานเดียว แล้วค่อยแปลงเป็นเวลาไทยตอนแสดงผลฝั่ง frontend.
    return datetime.now(timezone.utc)


# ============================================================
# Core account & statement models
# บัญชีผู้ใช้ + ข้อมูล statement (User → Import → Transaction) + Notification/Preference
# ============================================================

class User(Base):
    # ตาราง "ผู้ใช้" — 1 แถว = 1 บัญชี. ทุกตารางอื่นผูกกลับมาที่ users.id
    # ผ่าน foreign key (FK). login = upsert by email (ไม่มี password ในเดโมนี้).
    __tablename__ = "users"

    # id = primary key (PK) — เลขประจำแถว รันอัตโนมัติ (autoincrement).
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # email = ตัวระบุตัวตนหลัก unique (ห้ามซ้ำ) + index (ค้นเร็ว) เพราะ login
    # ค้นด้วย email ทุกครั้ง.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # name = ชื่อจริงที่ตั้งตอนสมัคร (default ว่าง ถ้าไม่ส่งมาใช้ prefix ของ email).
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Optional friendly display name (Sprint 5 — Settings page). Falls back to
    # ``name`` in the UI when empty so existing users see no change.
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # created_at = วันเวลาที่สร้างบัญชี (default = เวลาปัจจุบัน UTC ตอน insert).
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    # Hard-delete grace period (Sprint 5). When set, the daily cron will purge
    # this user + all FK data once ``utcnow() >= delete_scheduled_at``. NULL =
    # account is active. Indexed so the cleanup query stays cheap on Postgres.
    delete_scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    # relationship = ทางลัด ORM ให้เข้าถึงแถวลูกได้เหมือน attribute (เช่น
    # user.transactions คืน list ของ Transaction ที่เป็นของ user นี้) โดยไม่ต้อง
    # เขียน JOIN เอง. cascade="all, delete-orphan" = ถ้าลบ user ผ่าน ORM ให้ลบ
    # แถวลูกตามไปด้วย (แต่โค้ด grace-cleanup เราลบเองแบบ bulk เพื่อความเร็ว/ชัวร์).
    # uselist=False = ความสัมพันธ์ 1-ต่อ-1 (user มี preference ได้แถวเดียว).
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    imports: Mapped[list["Import"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    preference: Mapped[Optional["Preference"]] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)

    def to_dict(self) -> dict:
        # แปลง ORM object → dict ธรรมดา เพื่อส่งเป็น JSON กลับให้ frontend
        # (ส่งเฉพาะ field ปลอดภัย ไม่หลุด delete_scheduled_at ที่ endpoint อื่นดูแล).
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "display_name": self.display_name,
        }


class Import(Base):
    # ตาราง "ประวัติการนำเข้า" — 1 แถว = อัปโหลด statement PDF 1 ครั้ง.
    # ใช้เป็น audit log + ให้ผู้ใช้กด Undo (ลบ import + tx ที่มาจาก import นั้น).
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # user_id = FK ชี้ไป users.id (import นี้เป็นของใคร) + index เพราะ query
    # ประวัติมักกรองด้วย user_id.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # filename = ชื่อไฟล์ที่อัปโหลด (โชว์ในหน้าประวัติ)
    filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # bank = โค้ดธนาคารที่ parser ตรวจได้ (kbank/scb/ktb/gsb หรือ unknown)
    bank: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    # count = จำนวนรายการที่ insert จริงหลัง dedup (อัปเดตหลังบันทึกเสร็จ)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # imported_at = เวลาที่อัปโหลด (ใช้เรียงประวัติล่าสุดก่อน)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    # back_populates = ผูก 2 ทางกับ User.imports (แก้ฝั่งไหน อีกฝั่งเห็นด้วย)
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
    # ตาราง "รายการเดินบัญชี" — หัวใจของแอป. 1 แถว = รายรับ/รายจ่าย 1 รายการ.
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # user_id = เจ้าของรายการ (index — ทุก query กรองด้วย user_id)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # source_import_id = มาจากการอัปโหลดครั้งไหน (nullable — รายการที่เพิ่มมือ
    # หรือ migrate มาอาจไม่มี import ต้นทาง). ใช้ตอน Undo import.
    source_import_id: Mapped[Optional[int]] = mapped_column(ForeignKey("imports.id"), nullable=True)

    # date = วันที่รายการ เก็บเป็น string "YYYY-MM-DD" (เทียบ/กรองเดือนด้วย LIKE
    # ได้ง่าย) + index เพราะเรียงตามวันที่บ่อย
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    # merchant = ชื่อร้าน/คู่ค้า (ใช้ทำ fingerprint กันซ้ำ + จับคู่ Learning Loop)
    merchant: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # amount = จำนวนเงิน: บวก = รายรับ, ลบ = รายจ่าย (เก็บเครื่องหมายไว้ในตัวเลข)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # type = ประเภทดิบจาก statement (เช่น โอน/ถอน) — ข้อความช่วยอ้างอิง
    type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # category = หมวดที่จัดให้ (food/transport/... 9 หมวด) default "other" +
    # index เพราะหน้า insights สรุปยอดตามหมวด
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="other", index=True)
    # note = โน้ตเพิ่มเติม (ข้อความยาวได้ → ใช้ Text ไม่จำกัดความยาวเท่า String)
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
    # ตาราง "การแจ้งเตือน" — โชว์ในกระดิ่งบนเว็บ (นำเข้าสำเร็จ / เกินงบ ฯลฯ).
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # kind = ชนิด/สีของ noti (good=เขียว, warn=เหลือง, info=ฟ้า) frontend ใช้เลือกสี
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="info")  # good|warn|info
    # icon = ชื่อไอคอนที่จะแสดง (bell/check/...)
    icon: Mapped[str] = mapped_column(String(32), nullable=False, default="bell")

    # i18n payloads — {th: "...", en: "..."}
    # title/desc เก็บเป็น JSON 2 ภาษา {th, en} ในคอลัมน์เดียว → frontend เลือก
    # ภาษาตอนแสดงผลได้เอง ไม่ต้องแยกตาราง/คอลัมน์ต่อภาษา (i18n = internationalization).
    title: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    desc: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # unread = ยังไม่อ่าน (True) — endpoint mark-read เปลี่ยนเป็น False ทีเดียวทั้งชุด
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
    # ตาราง "การตั้งค่าผู้ใช้" — 1 แถวต่อ 1 user (user_id เป็น PK เอง = 1-ต่อ-1,
    # ไม่มี id แยก). เก็บ theme/สี/ภาษา/งบรายหมวด/สวิตช์แจ้งเตือน.
    __tablename__ = "preferences"

    # user_id เป็นทั้ง PK และ FK พร้อมกัน → บังคับ 1 user มี preference ได้แถวเดียว
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    # accent = สีเน้น (hex) default ทอง #D4B978 ตามโลโก้
    accent: Mapped[str] = mapped_column(String(16), default="#D4B978", nullable=False)
    # density = ความหนาแน่น layout (regular/compact)
    density: Mapped[str] = mapped_column(String(16), default="regular", nullable=False)
    # lang = ภาษา UI (th/en), currency = สกุลเงินที่แสดง (THB)
    lang: Mapped[str] = mapped_column(String(8), default="th", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="THB", nullable=False)
    # show_ambient = เปิด/ปิด effect พื้นหลังเคลื่อนไหว
    show_ambient: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # category_budgets = งบต่อหมวด เก็บเป็น JSON {"food": 3000, ...} — ใช้เช็ค
    # "เกินงบ" ตอน push budget alert เข้า LINE
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


# ============================================================
# LINE integration + Learning Loop state
# ตารางฝั่ง LINE (mapping/pending PDF) + override หมวดที่ user สอนไว้
# ============================================================

class LineUser(Base):
    """Maps a LINE userId to a MoneyMind user account."""
    __tablename__ = "line_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # line_user_id = รหัสผู้ใช้ฝั่ง LINE (ขึ้นต้น "U...") — unique เพราะ 1 LINE
    # account ผูกได้กับเว็บ user เดียว + index (webhook ค้นด้วยตัวนี้ทุกครั้ง)
    line_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # user_id = ผูกไปยังเว็บ user คนไหน (หัวใจของการ "เชื่อมบัญชี")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # display_name = ชื่อโปรไฟล์ LINE (ดึงมาโชว์/ทักทาย)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # linked_at = เวลาที่เชื่อมล่าสุด (อัปเดตใหม่ทุกครั้งที่ re-link)
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
    # UniqueConstraint = บังคับว่า (user_id + merchant_norm) ห้ามซ้ำในตาราง →
    # 1 ร้านต่อ 1 user มี override ได้แค่หมวดเดียว. ช่วยกัน race condition
    # (ถ้า 2 request บันทึกพร้อมกัน DB จะ reject ตัวที่ 2 แทนที่จะได้ 2 แถวซ้ำ).
    __table_args__ = (
        UniqueConstraint("user_id", "merchant_norm", name="uq_user_merchant_norm"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # user_id = override นี้เป็นของ user คนไหน (แต่ละคนสอนหมวดของตัวเอง)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # merchant_norm = ชื่อร้านหลัง normalize (lowercase+ตัดช่องว่าง) — "ลายนิ้วมือ"
    # ที่ใช้จับคู่ตอน import ครั้งถัดไป + index เพื่อ lookup เร็ว
    merchant_norm: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    # category = หมวดที่ user เลือกไว้ → เอาไป override หมวดที่ parser เดา
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
    # line_user_id = ของใคร (unique → 1 คนมี PDF ค้างรอรหัสได้ทีละไฟล์เดียว)
    line_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # pdf_bytes = ไบต์ดิบของ PDF ที่ติดรหัส (LargeBinary = BLOB เก็บ binary ใน DB)
    # — เก็บชั่วคราวรอ user พิมพ์รหัสในข้อความถัดไป (TTL 5 นาที ตามกฎด้านบน)
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # attempts = นับจำนวนครั้งที่ใส่รหัสผิด (ครบ 3 → ลบทิ้ง กัน brute force)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # created_at = ใช้เช็ค TTL (เกิน 5 นาที = หมดอายุ ลบทิ้งตอนเข้าถึงครั้งถัดไป)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


# ============================================================
# Helpers
# ============================================================

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

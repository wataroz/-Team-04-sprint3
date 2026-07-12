"""SQLAlchemy engine + session setup for MoneyMind.

Database selection (in priority order):
  1. DATABASE_URL env var  → use it (Postgres on Render/Supabase/Neon)
  2. Otherwise              → SQLite at <project_root>/data/moneymind.db

Heroku/Render-style postgres:// URLs are auto-rewritten to postgresql://
so SQLAlchemy 2.0 accepts them.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "moneymind.db")

# ─── Pick the database backend ─────────────────────────────────────────────
# เจตนา: ตั้ง DATABASE_URL (prod บน Render/Supabase) → ใช้ Postgres, ไม่ตั้ง
# (เครื่อง dev) → SQLite ที่ data/moneymind.db อัตโนมัติ — ไม่ต้องแก้โค้ดสลับ.
_env_url = os.environ.get("DATABASE_URL", "").strip()

if _env_url:
    # Render/Heroku give postgres:// but SQLAlchemy 2.0 wants postgresql://
    if _env_url.startswith("postgres://"):
        _env_url = _env_url.replace("postgres://", "postgresql://", 1)
    DB_URL = _env_url
    _is_sqlite = False
else:
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_URL = f"sqlite:///{DB_PATH}"
    _is_sqlite = True

# `check_same_thread=False` only applies to SQLite. For Postgres we pass {}.
# check_same_thread=False = อนุญาตให้ใช้ connection เดียวข้าม thread ได้ (Flask dev
# server เป็น multi-thread) — จำเป็นเฉพาะ SQLite; Postgres ไม่ต้องตั้ง ส่ง {} ว่างไป.
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# engine = ตัวจัดการ connection pool ไปยัง DB (สร้างครั้งเดียว ใช้ทั้งแอป).
engine = create_engine(
    DB_URL,
    echo=False,   # True = print ทุก SQL ที่รัน ( debug); prod ปิดไว้กัน log บวม
    future=True,  # เปิดโหมด API แบบ SQLAlchemy 2.0 (style ใหม่)
    pool_pre_ping=True,   # auto-reconnect dropped Postgres connections
    # pool_pre_ping = ก่อนหยิบ connection จาก pool มาใช้ จะ ping เช็คว่ายังไม่ตาย
    # (Postgres ฝั่ง Render/Supabase อาจตัด idle connection ทิ้ง) → กัน error
    # "server closed the connection" หลังแอป idle นานๆ.
    connect_args=_connect_args,
)

# SessionLocal = "โรงงาน" สร้าง Session (1 หน่วยงานคุยกับ DB ต่อ 1 request).
# แต่ละ route จะเรียก SessionLocal() เปิด session ใหม่ แล้ว .close() ตอนจบเสมอ.
#   autoflush=False  → ไม่ auto-sync ค้างไปยัง DB ก่อน query (เรา commit เองชัดเจน)
#   autocommit=False → ต้องเรียก .commit() เอง ถึงจะบันทึกจริง (ปลอดภัยกว่า)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# Base = คลาสแม่ของทุก ORM model (ตารางใน models.py สืบทอดจากตัวนี้).
# ORM (Object-Relational Mapping) = เขียน Python class แทนตาราง SQL แล้ว
# SQLAlchemy แปลงให้เป็น SQL ให้อัตโนมัติ — ไม่ต้องเขียน CREATE TABLE เอง.
class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they don't exist."""
    # สร้างตารางทั้งหมดถ้ายังไม่มี (เรียกตอน import app) — idempotent รันซ้ำได้.
    # หมายเหตุ migration: create_all "เพิ่มตารางใหม่" ให้ แต่ "ไม่ ALTER คอลัมน์เดิม"
    # → ถ้าเพิ่ม field ในตารางเดิมต้องใช้ scripts/run_migration.py แยก.
    # Import here so models register on Base.metadata before create_all.
    # ต้อง import models ตรงนี้ก่อน create_all เพื่อให้ทุก model ลงทะเบียนใน
    # Base.metadata ก่อน (ไม่งั้นจะไม่รู้ว่ามีตารางอะไรบ้างให้สร้าง).
    from backend import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_session():
    """Yield a session; caller responsible for closing (or use a context manager)."""
    # generator helper สำหรับใช้กับ `with`/dependency — yield session ออกไป
    # แล้วปิดให้เองใน finally (ปัจจุบัน route ส่วนใหญ่เรียก SessionLocal() ตรงๆ).
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

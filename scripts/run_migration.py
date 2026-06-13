"""
One-time migration script — Sprint 5 Settings page schema
(เพิ่ม columns สำหรับ notification toggle + display_name + soft-delete grace period)

วิธีใช้:
  1. เปิด Render Dashboard → Postgres `moneymind-test-db` → Info tab
  2. Copy "External Database URL" (ขึ้นต้นด้วย postgres:// หรือ postgresql://)
  3. รันใน PowerShell ที่ folder MoneyMind:

     $env:DATABASE_URL = "postgresql://..."
     py scripts/run_migration.py

  4. ถ้าเห็น "Migration complete" + 5/5 statements = สำเร็จ
  5. ลบ env var ทันที (กัน leak): Remove-Item env:DATABASE_URL

Idempotent — รันซ้ำได้ปลอดภัย (ใช้ IF NOT EXISTS ทุก statement)

ทำไมต้องใช้ script นี้:
  Render Free tier ไม่มี shell ให้ exec psql → เลยรัน local แทน
  Script ใช้ psycopg2 ตรงๆ (ไม่ผ่าน SQLAlchemy) เพื่อเห็น error ตรงไปตรงมา
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse


# Windows console default codepage (cp874 บน Thai locale) encode emoji ไม่ได้
# → reconfigure stdout/stderr เป็น UTF-8 ก่อน print อะไรเลย กัน UnicodeEncodeError
# Python 3.7+ มี ``sys.stdout.reconfigure`` — guarded กัน fail บน stream แปลกๆ
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


# ─── Migration statements ─────────────────────────────────────────────────
# แต่ละ tuple คือ (label, sql). ทุกตัว idempotent ด้วย IF NOT EXISTS
# label ใช้แสดง progress แบบสั้น user อ่านง่าย
_STATEMENTS: list[tuple[str, str]] = [
    (
        "preferences.budget_alert_enabled",
        "ALTER TABLE preferences ADD COLUMN IF NOT EXISTS "
        "budget_alert_enabled BOOLEAN DEFAULT TRUE;",
    ),
    (
        "preferences.line_notify_enabled",
        "ALTER TABLE preferences ADD COLUMN IF NOT EXISTS "
        "line_notify_enabled BOOLEAN DEFAULT TRUE;",
    ),
    (
        "users.display_name",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "display_name VARCHAR(100);",
    ),
    (
        "users.delete_scheduled_at",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "delete_scheduled_at TIMESTAMP NULL;",
    ),
    (
        "idx_users_delete_scheduled",
        "CREATE INDEX IF NOT EXISTS idx_users_delete_scheduled "
        "ON users(delete_scheduled_at) WHERE delete_scheduled_at IS NOT NULL;",
    ),
    # Post-Sprint 5 brand refresh — light/dark theme toggle. Default 'light'
    # to match the cream logo background so existing users see the new
    # default the first time they hit Settings → Appearance.
    (
        "preferences.theme",
        "ALTER TABLE preferences ADD COLUMN IF NOT EXISTS "
        "theme VARCHAR(16) NOT NULL DEFAULT 'light';",
    ),
]


def _safe_host_label(url: str) -> str:
    """Return ``host:port`` slice of a DATABASE_URL — never the password.

    Falls back to a generic label if parsing fails so we never accidentally
    leak the raw URL to stdout.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "?"
        port = parsed.port or 5432
        return f"{host}:{port}"
    except Exception:
        return "<unparseable-host>"


def _load_database_url() -> str:
    """Read DATABASE_URL from env + rewrite ``postgres://`` → ``postgresql://``.

    Mirrors the logic in ``backend/db.py`` so this script behaves the same as
    the live app. Exits cleanly (with instructions) if the env var is missing
    or obviously wrong.
    """
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        print("❌ DATABASE_URL ไม่ได้ตั้งใน environment")
        print()
        print("วิธีตั้ง:")
        print("  1. เปิด Render Dashboard → Postgres `moneymind-test-db` → Info")
        print("  2. Copy 'External Database URL'")
        print("  3. รันใน PowerShell:")
        print('     $env:DATABASE_URL = "postgresql://..."')
        print("     py scripts/run_migration.py")
        print()
        print("  หลังเสร็จอย่าลืม: Remove-Item env:DATABASE_URL")
        sys.exit(1)

    # SQLAlchemy 2.0 + psycopg2 ต้องการ postgresql:// (postgres:// ใช้ไม่ได้)
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql://", 1)

    if not raw.startswith("postgresql://"):
        print("❌ DATABASE_URL หน้าตาแปลก (ต้องขึ้นต้นด้วย postgres:// หรือ postgresql://)")
        print(f"   เห็นเป็น: {raw.split(':', 1)[0]}://...")
        sys.exit(1)

    return raw


def main() -> int:
    print("🔗 MoneyMind Sprint 5 — Settings page migration")
    print()

    db_url = _load_database_url()
    host_label = _safe_host_label(db_url)
    print(f"🔗 Target: {host_label}")
    print()

    # Lazy import → ถ้า psycopg2 ไม่ได้ติดตั้งจะได้ error message ที่ user เข้าใจ
    try:
        import psycopg2  # type: ignore
    except ImportError:
        print("❌ psycopg2 ไม่ได้ติดตั้ง")
        print("   ลง deps ก่อน: py -m pip install -r requirements.txt")
        return 1

    # ─── Connect ─────────────────────────────────────────────────────────
    try:
        conn = psycopg2.connect(db_url)
    except Exception as exc:
        # psycopg2.OperationalError มัก carry credential ใน repr — print แบบ str() พอ
        msg = str(exc).strip() or exc.__class__.__name__
        print(f"❌ Connect failed: {msg}")
        print()
        print("ลองเช็ค:")
        print("  • External Database URL ถูกต้อง (copy ทั้ง string)")
        print("  • Render Postgres ยังไม่หมดอายุ (test DB ~27 มิ.ย. 2026)")
        print("  • Network / firewall ไม่บล็อก port 5432")
        return 1

    print(f"✅ Connected — รัน {len(_STATEMENTS)} statements")
    print()

    # ─── Run statements ──────────────────────────────────────────────────
    # autocommit=True → แต่ละ DDL commit ทันที (ไม่ทำให้ทั้งงานพังถ้าตัวนึงล่ม)
    conn.autocommit = True
    cur = conn.cursor()

    successes = 0
    failures: list[tuple[str, str]] = []  # (label, error_message)

    for label, sql in _STATEMENTS:
        try:
            cur.execute(sql)
            print(f"  ✅ {label}")
            successes += 1
        except Exception as exc:
            err = str(exc).strip() or exc.__class__.__name__
            # PostgreSQL warning เช่น duplicate column ถูก ADD COLUMN IF NOT EXISTS
            # ดักไว้แล้ว — ถ้า error จริงคืออะไรอื่น report และทำตัวถัดไป
            print(f"  ❌ {label}: {err}")
            failures.append((label, err))

    # ─── Cleanup ─────────────────────────────────────────────────────────
    try:
        cur.close()
        conn.close()
    except Exception:
        pass  # connection อาจถูก server ปิดแล้ว — ไม่ใช่ปัญหา

    # ─── Summary ─────────────────────────────────────────────────────────
    total = len(_STATEMENTS)
    print()
    if failures:
        print(f"⚠️  Migration partial — สำเร็จ {successes}/{total} statements")
        print()
        print("รายการที่ล้มเหลว:")
        for label, err in failures:
            print(f"  • {label}: {err}")
        print()
        print("ลองรันซ้ำได้ (idempotent) — หรือเปิด Render Postgres console ตรวจ schema")
        return 1

    print(f"🎉 Migration complete — สำเร็จ {successes}/{total} statements")
    print()
    print("ขั้นต่อไป:")
    print("  • Remove-Item env:DATABASE_URL  (ลบ secret ออกจาก shell)")
    print("  • Restart Render service เพื่อ pick up schema ใหม่ (ถ้ายังไม่ auto)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

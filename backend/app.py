"""MoneyMind Flask backend.

Routes:
    GET    /                              - serve the React-via-Babel SPA (frontend/index.html)
    GET    /fe/<path>                     - serve frontend assets (src/*.jsx, src/*.js)
    GET    /ui/<path>                     - serve UX/UI assets (styles.css, src/ui.jsx, ...)
    POST   /api/parse-pdf                 - parse a bank statement PDF, return transactions
    POST   /api/auth/login                - upsert user by email, return user record
    GET    /api/users/<id>                - get user profile + grace-period status (Sprint 5)
    PATCH  /api/users/<id>                - update name / display_name (Sprint 5)
    DELETE /api/users/<id>                - schedule 30-day grace hard-delete (Sprint 5)
    POST   /api/users/<id>/cancel-delete  - abort a scheduled hard-delete (Sprint 5)
    GET    /api/users/<id>/export-csv     - download all txs as CSV (Sprint 5)
    GET    /api/line/status               - is the web user linked to a LINE account? (Sprint 5)
    POST   /api/line/unlink               - remove the LINE↔web link (Sprint 5)
    GET    /api/line/oauth/url            - build LINE Login authorise URL (verified linking)
    GET    /api/line/oauth/callback       - LINE Login OAuth 2.0 / OIDC callback
    GET    /api/transactions              - list a user's transactions
    POST   /api/transactions              - bulk-create transactions
    PATCH  /api/transactions/<id>         - re-categorise one tx (Learning Loop)
    POST   /api/imports                   - create an import record
    GET    /api/imports                   - list a user's imports
    DELETE /api/imports/<id>              - undo last import
    GET    /api/notifications             - list a user's notifications
    POST   /api/notifications             - create a notification
    POST   /api/notifications/mark-read   - mark notifications as read
    GET    /api/preferences/<uid>         - get a user's preferences
    PUT    /api/preferences/<uid>         - update a user's preferences
    POST   /api/reset                     - wipe a user's txs/imports/notifications
    POST   /api/ai/complete               - AI proxy (Gemini → Anthropic fallback)
    POST   /webhook/line                  - LINE Messaging API webhook
    POST   /api/admin/run-grace-cleanup   - manual cron trigger (token-gated, Sprint 5)
    GET    /api/health                    - liveness check

Run with:  python backend/app.py   (from the project root)
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from threading import Timer

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

# Make sibling packages importable when running `python backend/app.py` directly.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load .env file if present (LINE tokens, etc.)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass  # python-dotenv not installed yet; env vars must be set manually

from backend.db import SessionLocal, init_db  # noqa: E402
from backend.models import (  # noqa: E402
    Import,
    LinePendingPdf,
    LineUser,
    MerchantOverride,
    Notification,
    Preference,
    Transaction,
    User,
)
from logic_ai.pdf_parser import parse_statement  # noqa: E402

# LINE Bot — loaded lazily so missing env vars don't crash startup
_line_handler = None

def _get_line_handler():
    global _line_handler
    if _line_handler is None:
        try:
            from backend.line_bot import handler as lh
            _line_handler = lh
        except Exception as exc:
            log.warning("LINE bot not loaded: %s", exc)
    return _line_handler

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
UX_UI_DIR = os.path.join(PROJECT_ROOT, "ux_ui")

app = Flask(
    __name__,
    template_folder=FRONTEND_DIR,
    static_folder=FRONTEND_DIR,
    static_url_path="/fe",
)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB upload cap

# Configure logging at import time so log records are visible under gunicorn
# (production) as well as the Flask dev server. Previously this lived inside
# `if __name__ == "__main__"`, so gunicorn-launched workers never set it up
# and log.info/log.exception output was swallowed.
logging.basicConfig(level=logging.INFO)

log = logging.getLogger("moneymind")

# Create tables (and the data/ folder) on import.
init_db()


# ─── Static / SPA ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    # หน้าแรก — ส่ง index.html (React SPA ที่รันผ่าน Babel CDN ในเบราว์เซอร์
    # ไม่มี build step) กลับไปให้ผู้ใช้.
    return render_template("index.html")


@app.route("/ui/<path:filename>")
def ux_ui_static(filename: str):
    """Serve files from the ux_ui/ folder (styles.css, ui.jsx, tweaks-panel.jsx)."""
    return send_from_directory(UX_UI_DIR, filename)


# ─── PDF parsing (logic_ai) ──────────────────────────────────────────────────

@app.route("/api/parse-pdf", methods=["POST"])
def api_parse_pdf():
    """รับไฟล์ statement PDF (multipart form field 'file') → แกะรายการออกมา.

    รับ: ไฟล์ PDF (+ optional 'password' ถ้าไฟล์ติดรหัส)
    คืน: {bank, count, filename, transactions[]} — ยังไม่บันทึกลง DB
         (frontend เอาไปแสดง preview แล้วค่อยยิง POST /api/transactions บันทึก).
    ด่านตรวจก่อนแกะ: ต้องมี field 'file' + นามสกุล .pdf + ไม่ว่าง + ไม่เกิน 10MB.
    """
    # ไม่มี field 'file' ในฟอร์ม → ปฏิเสธทันที (400 = client ส่งมาผิด)
    if "file" not in request.files:
        return jsonify({"error": "no file uploaded (field 'file' required)"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "only .pdf files are supported"}), 400

    data = f.read()
    if not data:
        return jsonify({"error": "empty file"}), 400
    # Explicit 10 MB guard — กัน worker timeout/OOM ก่อนเข้า pdfplumber
    if len(data) > 10 * 1024 * 1024:
        return jsonify({"error": "ไฟล์ใหญ่เกิน 10 MB"}), 413

    # multipart form field — empty string treated as no password.
    # NEVER log the password value (PII / security).
    password = request.form.get("password", "") or None

    log.info("parse-pdf start: size=%d bytes has_password=%s",
             len(data), bool(password))
    t0 = time.perf_counter()
    try:
        bank, txs = parse_statement(data, password=password)
    except ValueError as exc:
        # ValueError dispatch:
        #   * password errors  → 400 (credentials wrong, client must fix)
        #   * size/page guards → 413 (payload too large)
        msg = str(exc)
        log.warning("parse-pdf rejected: %s", msg)
        if msg.startswith("PDF นี้ติดรหัส") or msg.startswith("รหัส PDF ไม่ถูกต้อง"):
            return jsonify({"error": msg}), 400
        return jsonify({"error": msg}), 413
    except Exception as exc:
        log.exception("parse_statement failed")
        return jsonify({"error": f"parse failed: {exc}"}), 500
    dt = time.perf_counter() - t0
    log.info(
        "parse-pdf done: bank=%s txs=%d duration=%.2fs",
        bank, len(txs), dt,
    )

    return jsonify({
        "bank": bank,
        "count": len(txs),
        "filename": f.filename,
        "transactions": txs,
    })


# ─── Auth (lightweight: upsert by email, no password) ────────────────────────

def _user_payload(user: User) -> dict:
    """Build the JSON shape returned by every user-facing endpoint.

    Extends ``User.to_dict()`` with grace-period fields so the frontend can
    show a "Cancel delete" banner without a second round-trip. ``days_until_delete``
    is a positive int when the grace window is still open, 0 on the day it
    expires, and ``None`` when no delete is scheduled.
    """
    sched = user.delete_scheduled_at
    days = None
    # ถ้ามีนัดลบไว้ → คำนวณว่าเหลือกี่วันถึงกำหนดลบ (max(0,..) กันค่าติดลบวันที่เลย
    # กำหนดแล้วแต่ cron ยังไม่ทันรัน) เพื่อให้ frontend โชว์ countdown ได้เลย.
    if sched is not None:
        delta = sched - datetime.utcnow()
        days = max(0, delta.days)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "display_name": user.display_name,
        "delete_scheduled_at": sched.isoformat() if sched else None,
        "days_until_delete": days,
    }


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """login แบบเบา (เดโม): upsert ด้วย email อย่างเดียว ไม่มีรหัสผ่าน.

    รับ: {email, name?}  คืน: user payload (+ สถานะ grace-delete).
    upsert = ถ้ามี user อยู่แล้ว → ใช้ตัวเดิม (update), ถ้ายังไม่มี → สร้างใหม่
    (insert). "up-sert" = update-or-insert.
    """
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    # ถ้าไม่ส่ง name มา ใช้ส่วนหน้า @ ของ email เป็นชื่อ default
    name = (body.get("name") or "").strip() or (email.split("@")[0] if email else "User")
    if not email:
        return jsonify({"error": "email required"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).first()
        if user is None:
            # ยังไม่มี user email นี้ → สร้างใหม่ + สร้างแถว Preference default ให้เลย
            # (commit 2 รอบเพราะต้องได้ user.id ก่อน ถึงจะผูก Preference.user_id ได้)
            user = User(email=email, name=name)
            db.add(user)
            db.commit()
            db.refresh(user)  # refresh = ดึงค่าที่ DB สร้างให้ (เช่น id) กลับเข้า object
            # Seed default preferences row
            db.add(Preference(user_id=user.id))
            db.commit()
        elif name and not user.name:
            # user เดิมมีอยู่แต่ยังไม่มีชื่อ → เติมชื่อให้ (ไม่ทับของเดิมถ้ามีแล้ว)
            user.name = name
            db.commit()
        # NOTE: we intentionally do NOT block login when delete_scheduled_at is
        # set — the user must be able to sign in to hit "Cancel delete". The
        # grace-period UI is the frontend's responsibility (banner + countdown).
        payload = _user_payload(user)
    finally:
        db.close()

    # Lazy grace-period cleanup — รันหลังปิด DB session ของ login เพื่อกัน
    # lock contention. _maybe_run_auto_cleanup() self-throttle (วันละครั้ง)
    # และ swallow exception ภายใน → login ของ user ไม่พังแน่นอน.
    _maybe_run_auto_cleanup()
    return jsonify(payload)


# ─── User Settings (Sprint 5) ────────────────────────────────────────────────

_GRACE_PERIOD_DAYS = 30


@app.route("/api/users/<int:user_id>", methods=["GET"])
def api_get_user(user_id: int):
    """คืนโปรไฟล์ user + สถานะนัดลบบัญชี (ถ้ามี). 404 ถ้าไม่พบ id.

    Return the user's profile + grace-period status.

    Used by the Settings page (Profile section) and the post-login Cancel-Delete
    banner. See ``_user_payload`` for the response shape.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user is None:
            return jsonify({"error": "user not found"}), 404
        return jsonify(_user_payload(user))
    finally:
        db.close()


@app.route("/api/users/<int:user_id>", methods=["PATCH"])
def api_patch_user(user_id: int):
    """แก้ไขชื่อ user (name และ/หรือ display_name) — ส่งมาแค่ field ที่จะแก้.

    Update mutable user fields: ``name`` and/or ``display_name``.

    Body (all fields optional — at least one required):
      ``{"name": "...", "display_name": "..."}``

    Validation:
      * ``name`` — 1..100 chars after strip. Empty string rejected to keep the
        legacy invariant ("users always have a non-empty name").
      * ``display_name`` — 0..100 chars after strip. Empty string is allowed
        and clears the field (falls back to ``name`` in the UI).
    """
    body = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user is None:
            return jsonify({"error": "user not found"}), 404

        # touched = ธงว่ามี field ที่แก้จริงไหม — ถ้าไม่มีเลยจะตอบ 400
        # (กันกรณี client ส่ง body ว่างมาแล้ว commit เปล่าๆ)
        touched = False
        if "name" in body:
            new_name = (body.get("name") or "").strip()
            if not (1 <= len(new_name) <= 100):
                return jsonify({"error": "name must be 1-100 chars"}), 400
            user.name = new_name
            touched = True
        if "display_name" in body:
            new_display = (body.get("display_name") or "").strip()
            if len(new_display) > 100:
                return jsonify({"error": "display_name max 100 chars"}), 400
            # Empty string → clear the override (UI falls back to ``name``).
            user.display_name = new_display or None
            touched = True

        if not touched:
            return jsonify({"error": "no fields to update"}), 400

        db.commit()
        return jsonify({"ok": True, "user": _user_payload(user)})
    except Exception as exc:
        db.rollback()
        log.exception("patch user failed for id=%s", user_id)
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def api_delete_user(user_id: int):
    """ตั้งเวลาลบบัญชีถาวร (grace period 30 วัน) — ยังไม่ลบทันที.

    ต้องยืนยัน 2 ชั้น (พิมพ์คำว่า DELETE + email ตรงกับบัญชี) กันกดพลาด/วางผิด.
    ลบจริงเกิดใน cron (_run_grace_period_cleanup) หลังครบ 30 วัน — ระหว่างนั้น
    login แล้วกด cancel-delete ยกเลิกได้ (pattern เดียวกับ Google/Facebook).

    Schedule a hard-delete with a 30-day grace period.

    Body: ``{"confirm_text": "DELETE", "email": "<user.email>"}``

    Both confirmations must match exactly — defence-in-depth so a stray click
    or pasted email can't nuke the account. Actual deletion happens in
    ``_run_grace_period_cleanup`` once the timer expires; until then the user
    can log in and hit ``POST /api/users/<id>/cancel-delete`` to abort.

    Errors:
      400 — confirm_text != "DELETE"          → ``"confirm_text_invalid"``
      400 — email mismatch                    → ``"email_mismatch"``
      404 — user not found
    """
    body = request.get_json(silent=True) or {}
    confirm_text = (body.get("confirm_text") or "").strip()
    typed_email = (body.get("email") or "").strip().lower()

    if confirm_text != "DELETE":
        return jsonify({"error": "confirm_text_invalid"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user is None:
            return jsonify({"error": "user not found"}), 404
        if typed_email != (user.email or "").lower():
            return jsonify({"error": "email_mismatch"}), 400

        user.delete_scheduled_at = datetime.utcnow() + timedelta(days=_GRACE_PERIOD_DAYS)
        db.commit()

        log.info(
            "delete scheduled for user_id=%s at=%s (grace=%dd)",
            user_id, user.delete_scheduled_at.isoformat(), _GRACE_PERIOD_DAYS,
        )
        return jsonify({
            "ok": True,
            "delete_scheduled_at": user.delete_scheduled_at.isoformat(),
            "days_until_delete": _GRACE_PERIOD_DAYS,
        })
    except Exception as exc:
        db.rollback()
        log.exception("delete user failed for id=%s", user_id)
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/users/<int:user_id>/cancel-delete", methods=["POST"])
def api_cancel_delete_user(user_id: int):
    """ยกเลิกนัดลบบัญชี (เคลียร์ delete_scheduled_at กลับเป็น NULL).

    Idempotent = เรียกซ้ำได้ปลอดภัย ถึงจะไม่มีนัดลบค้างอยู่ก็ตอบ ok
    (was_scheduled บอกว่าตอนกดมีนัดค้างจริงไหม).

    Abort a pending hard-delete. Idempotent — safe to call when no delete
    is scheduled (returns ok=true, was_scheduled=false)."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user is None:
            return jsonify({"error": "user not found"}), 404
        was_scheduled = user.delete_scheduled_at is not None
        user.delete_scheduled_at = None
        db.commit()
        if was_scheduled:
            log.info("delete cancelled for user_id=%s", user_id)
        return jsonify({"ok": True, "was_scheduled": was_scheduled})
    except Exception as exc:
        db.rollback()
        log.exception("cancel delete failed for id=%s", user_id)
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/users/<int:user_id>/export-csv", methods=["GET"])
def api_export_user_csv(user_id: int):
    """ดาวน์โหลดรายการทั้งหมดของ user เป็นไฟล์ CSV (สิทธิ์ portability ตาม PDPA).

    Stream all of a user's transactions as a downloadable CSV.

    Format: ``date,merchant,amount,type,category,note`` with a header row.
    Sorted by date desc (matches the Transactions view ordering). Uses
    ``csv.writer`` so embedded commas / quotes / newlines are escaped
    correctly — pasting into Excel/Sheets just works.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user is None:
            return jsonify({"error": "user not found"}), 404

        rows = (
            db.query(Transaction)
            .filter_by(user_id=user_id)
            .order_by(Transaction.date.desc(), Transaction.id.desc())
            .all()
        )

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["date", "merchant", "amount", "type", "category", "note"])
        for r in rows:
            writer.writerow([
                r.date or "",
                r.merchant or "",
                f"{r.amount:.2f}" if r.amount is not None else "0.00",
                r.type or "",
                r.category or "",
                r.note or "",
            ])

        csv_text = buf.getvalue()
        # UTF-8 BOM so Excel on Windows opens Thai text correctly without
        # forcing the user to do an Import → encoding step.
        body = "﻿" + csv_text
        filename = f"moneymind-{user_id}.csv"
        # mimetype="text/csv" — let Flask auto-append "; charset=utf-8" so we
        # don't get a duplicated charset segment in the header.
        return Response(
            body,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    finally:
        db.close()


# ─── LINE link status / unlink (Sprint 5) ───────────────────────────────────

@app.route("/api/line/status", methods=["GET"])
def api_line_status():
    """เช็คว่า user (จาก ?user_id=) ผูกบัญชี LINE ไว้หรือยัง (ใช้ในหน้า Settings).

    Return whether ``user_id`` has a LINE account linked.

    Response shape:
      linked    → ``{"linked": true, "display_name": "...", "line_user_id": "U...", "linked_at": "..."}``
      unlinked  → ``{"linked": false}``
    """
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    db = SessionLocal()
    try:
        link = db.query(LineUser).filter_by(user_id=user_id).first()
        if link is None:
            return jsonify({"linked": False})
        return jsonify({
            "linked": True,
            "display_name": link.display_name,
            "line_user_id": link.line_user_id,
            "linked_at": link.linked_at.isoformat() if link.linked_at else None,
        })
    finally:
        db.close()


# ─── LINE Login OAuth 2.0 / OIDC ────────────────────────────────────────────
# Adds a "1-click verified link" alternative to the existing
# `เชื่อม <email>` LINE-bot command. The chat command is kept as a fallback so
# users who don't want to leave LINE still have a path.
#
# Flow:
#   1. Frontend GETs /api/line/oauth/url?user_id=<web_user_id>
#      → backend signs a short-lived state JWT embedding user_id, returns
#        a fully-formed LINE authorise URL.
#   2. User clicks → LINE consent screen → redirect back to
#      /api/line/oauth/callback?code=...&state=...
#   3. Backend verifies state JWT (signature + exp + matches our user_id),
#      exchanges `code` for tokens, verifies the id_token (HS256 — LINE
#      uses a symmetric key, NOT RS256), pulls `sub` (= line_user_id),
#      and reuses backend.line_bot._link_line_to_user to actually wire
#      LineUser ↔ web user (same safety guard + data-move + cleanup as the
#      email command, kept in one place).
#   4. Redirect → /?line_linked=1 (success) or /?line_error=<code> (failure)
#      so the React SPA can show a toast and refresh the link status.

_LINE_OAUTH_AUTHORIZE_URL = "https://access.line.me/oauth2/v2.1/authorize"
_LINE_OAUTH_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
_LINE_OAUTH_SCOPES = "openid profile"
# Short window — the round trip is "user clicks → LINE consent → back".
# Anything beyond 10 minutes is almost certainly a replay / abandoned tab.
_OAUTH_STATE_TTL_SECONDS = 10 * 60


def _flask_signing_secret() -> str:
    """Return the secret used to HS256-sign our OAuth state tokens.

    Prefers FLASK_SECRET_KEY (proper signing key); falls back to
    ADMIN_CLEANUP_TOKEN so a single mis-set env var doesn't crash the route
    for ops. We log a one-shot warning when FLASK_SECRET_KEY is missing so
    it's obvious in prod logs.
    """
    secret = (os.environ.get("FLASK_SECRET_KEY") or "").strip()
    if not secret:
        secret = (os.environ.get("ADMIN_CLEANUP_TOKEN") or "").strip()
    return secret


def _make_oauth_state(user_id: int) -> str:
    """สร้าง state token (JWT อายุสั้น 10 นาที) ที่ฝัง user_id ไว้ข้างใน.

    JWT (JSON Web Token) = ก้อนข้อมูล JSON ที่ถูก "เซ็นชื่อ" ด้วย secret ของเรา
    → ใครแก้ข้างในลายเซ็นจะเพี้ยนทันที ตรวจจับได้ว่าถูกปลอม. ใช้เป็นเกราะกัน
    CSRF: ตอน LINE ส่ง callback กลับมา เราถอด token นี้เพื่อยืนยันว่า "คำขอนี้
    เราเป็นคนเริ่มเอง + ผูกกับ user คนนี้จริง" (แฮกเกอร์ปลอม state ไม่ได้เพราะ
    ไม่มี secret ไปเซ็น).

    Sign a short-lived state JWT carrying ``user_id``.

    Algorithm: HS256 with FLASK_SECRET_KEY. The state parameter is LINE's
    primary CSRF defence — by binding it to a server-signed JWT with a 10-min
    expiry, an attacker can't craft a callback that links someone else's
    LINE account to the victim's web user.
    """
    # lazy import = import ตรงจุดที่ใช้จริง (ไม่ import บนหัวไฟล์) → ถ้าเครื่องยัง
    # ไม่ได้ลง PyJWT แอปก็ยัง start ได้ พังเฉพาะตอนเรียก route นี้ ไม่ล้มทั้งระบบ.
    import jwt  # lazy — keeps startup clean if PyJWT isn't installed yet

    secret = _flask_signing_secret()
    if not secret:
        raise RuntimeError("FLASK_SECRET_KEY (or ADMIN_CLEANUP_TOKEN) not set")
    now = datetime.utcnow()
    payload = {
        "sub": int(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=_OAUTH_STATE_TTL_SECONDS),
        "purpose": "line_oauth_link",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _verify_oauth_state(token: str) -> int:
    """Verify an OAuth state JWT and return the embedded ``user_id``.

    Raises ``ValueError`` on any failure (expired, bad signature, wrong
    purpose claim, missing user_id) so the callback handler can map it to a
    single ``line_error=state_invalid`` redirect without leaking specifics.
    """
    import jwt

    secret = _flask_signing_secret()
    if not secret:
        raise ValueError("signing secret not configured")
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except Exception as exc:
        raise ValueError(f"state decode failed: {exc}") from exc

    if payload.get("purpose") != "line_oauth_link":
        raise ValueError("state purpose mismatch")
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("state missing user_id") from exc


def _verify_line_id_token(id_token: str, channel_id: str, channel_secret: str) -> dict:
    """ตรวจ id_token ของ LINE (HS256) แล้วคืน claims — ห้าม fetch JWKS.

    จุดพลาดง่าย: LINE เซ็น id_token ด้วย HS256 (symmetric key = channel_secret)
    ไม่ใช่ RS256 + public key เหมือน Google/Apple → ห้ามไปดึง JWKS endpoint.

    LINE uses HS256 with the channel secret as the shared key — NOT RS256
    with a JWKS endpoint. Reference:
    https://developers.line.biz/en/docs/line-login/verify-id-token/

    Claims we explicitly check:
      * ``iss`` == ``https://access.line.me``  (spec)
      * ``aud`` == channel_id                 (token was issued for our app)
      * ``exp`` > now                          (not expired — PyJWT enforces)

    Returns the decoded claim dict on success; raises ``ValueError`` on any
    verification failure.
    """
    import jwt

    if not (channel_id and channel_secret):
        raise ValueError("LINE Login channel id/secret not configured")
    try:
        claims = jwt.decode(
            id_token,
            channel_secret,
            algorithms=["HS256"],
            audience=channel_id,
            issuer="https://access.line.me",
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except Exception as exc:
        raise ValueError(f"id_token verify failed: {exc}") from exc
    return claims


def _line_oauth_callback_url() -> str:
    """Derive the registered LINE Login callback URL.

    Prefers the explicit env var (must match the LINE Console value exactly —
    LINE rejects trailing-slash mismatches). Falls back to ``request.host_url``
    so local dev works without touching .env.
    """
    explicit = (os.environ.get("LINE_LOGIN_CALLBACK_URL") or "").strip()
    if explicit:
        return explicit
    # request.host_url ends with "/", strip it then append the path.
    return request.host_url.rstrip("/") + "/api/line/oauth/callback"


def _line_link_redirect(success: bool, error_code: str = "") -> Response:
    """คืน redirect 302 กลับหน้าเว็บ พร้อมแปะผลลัพธ์ไว้ใน query string.

    ทุกเส้นทาง (สำเร็จ/ล้มเหลว) จบที่ redirect เดียว → SPA อ่าน ?line_linked=1
    หรือ ?line_error=<code> แล้วเด้ง toast. ไม่ตอบ JSON เพราะ ณ จุดนี้เบราว์เซอร์
    กำลังตามลิงก์ redirect จาก LINE อยู่ (ไม่ใช่ fetch จาก JS).

    Return a 302 back to the SPA with a result marker in the query string."""
    if success:
        target = "/?line_linked=1"
    else:
        # error_code is a short token only; never echoes user input or PII.
        # sanitize: เหลือแค่ a-z0-9_ + ตัดยาว 32 ตัว → กัน error string แปลกปลอม
        # (หรือ PII) หลุดไปโผล่บน URL ฝั่ง client.
        safe = re.sub(r"[^a-z0-9_]", "", (error_code or "unknown").lower())[:32] or "unknown"
        target = f"/?line_error={safe}"
    resp = Response(status=302)
    resp.headers["Location"] = target
    return resp


@app.route("/api/line/oauth/url", methods=["GET"])
def api_line_oauth_url():
    """สร้าง URL หน้าขออนุญาต LINE Login สำหรับ user (ปุ่ม "เชื่อมด้วย LINE").

    รับ: ?user_id=<id>  คืน: {"url": "https://access.line.me/..."} ให้ frontend
    พาผู้ใช้ไปกดอนุญาตที่ LINE. ใน URL มี state JWT ฝังไว้ (กัน CSRF).

    Build the LINE Login authorise URL for ``user_id``.

    Returns ``{"url": "<https://access.line.me/...>"}``. The frontend should
    open this URL (full navigation, not popup) so the LINE redirect callback
    lands on our backend with a fresh document context.

    Errors:
      400 — user_id missing
      404 — user_id not in DB
      503 — LINE Login env vars not configured (signals ops misconfiguration)
    """
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    channel_id = (os.environ.get("LINE_LOGIN_CHANNEL_ID") or "").strip()
    channel_secret = (os.environ.get("LINE_LOGIN_CHANNEL_SECRET") or "").strip()
    if not (channel_id and channel_secret):
        return jsonify({"error": "LINE Login not configured"}), 503

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if user is None:
            return jsonify({"error": "user not found"}), 404
    finally:
        db.close()

    try:
        state = _make_oauth_state(user_id)
    except RuntimeError as exc:
        log.error("OAuth state signing failed: %s", exc)
        return jsonify({"error": "signing key not configured"}), 503

    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": channel_id,
        "redirect_uri": _line_oauth_callback_url(),
        "state": state,
        "scope": _LINE_OAUTH_SCOPES,
        # Force the consent screen so the user always sees what they're
        # approving (and so re-links work after an unlink).
        "prompt": "consent",
        "bot_prompt": "normal",
    }
    return jsonify({"url": f"{_LINE_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"})


@app.route("/api/line/oauth/callback", methods=["GET"])
def api_line_oauth_callback():
    """ปลายทางที่ LINE เด้งกลับมาหลังผู้ใช้กดอนุญาต (หรือกดยกเลิก).

    ขั้นตอนใน route นี้ (4 สเต็ป): (1) ตรวจ state JWT ว่าเราเซ็นเองและยังไม่หมดอายุ
    → (2) เอา code ไปแลก token กับ LINE → (3) ตรวจ id_token ว่าของจริง แล้วดึง
    line_user_id ออกมา → (4) เรียก _link_line_to_user ผูกบัญชี แล้ว redirect กลับ
    เว็บพร้อมผลลัพธ์. ทุก error เด้งกลับ /?line_error=<code> (ไม่โยน 4xx/5xx JSON).

    Handle LINE's redirect after the user grants consent.

    LINE sends ``?code=...&state=...`` on success, or
    ``?error=...&error_description=...&state=...`` on user-cancel / failure.
    Either way we resolve to a single SPA redirect — success path goes to
    ``/?line_linked=1``; every failure mode maps to ``/?line_error=<code>``.

    We deliberately avoid raising 4xx/5xx here: the browser is showing the
    LINE redirect, not a JSON client, so the SPA toast is the right surface.
    """
    err_param = request.args.get("error", "")
    if err_param:
        # User clicked "Cancel" on the LINE consent screen, or LINE itself
        # rejected the request. Bounce back with a marker; never echo the
        # error_description as it can contain provider-side detail we'd
        # rather keep out of the SPA URL.
        log.info("LINE OAuth user-cancel / provider error: %s", err_param)
        return _line_link_redirect(False, "user_cancelled")

    code = (request.args.get("code") or "").strip()
    state = (request.args.get("state") or "").strip()
    if not (code and state):
        return _line_link_redirect(False, "missing_params")

    # 1) Verify state — must be a JWT we signed within the last 10 min.
    try:
        web_user_id = _verify_oauth_state(state)
    except ValueError as exc:
        log.warning("OAuth state invalid: %s", exc)
        return _line_link_redirect(False, "state_invalid")

    channel_id = (os.environ.get("LINE_LOGIN_CHANNEL_ID") or "").strip()
    channel_secret = (os.environ.get("LINE_LOGIN_CHANNEL_SECRET") or "").strip()
    if not (channel_id and channel_secret):
        log.error("OAuth callback hit but LINE Login env vars are unset")
        return _line_link_redirect(False, "not_configured")

    # 2) Exchange the authorisation code for tokens. LINE requires
    # application/x-www-form-urlencoded — NOT JSON.
    try:
        import requests as _requests  # lazy — only this route needs it
        resp = _requests.post(
            _LINE_OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _line_oauth_callback_url(),
                "client_id": channel_id,
                "client_secret": channel_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except Exception as exc:
        log.exception("LINE token exchange network error: %s", exc)
        return _line_link_redirect(False, "exchange_failed")

    if resp.status_code != 200:
        # Don't log the full body — it can include short-lived tokens on
        # success paths and noisy error blobs on failure. Status code is enough
        # for ops; details live in LINE's own dashboard.
        log.warning("LINE token exchange returned HTTP %s", resp.status_code)
        return _line_link_redirect(False, "exchange_failed")

    try:
        payload = resp.json()
    except Exception:
        log.warning("LINE token exchange returned non-JSON body")
        return _line_link_redirect(False, "exchange_failed")

    id_token = (payload.get("id_token") or "").strip()
    if not id_token:
        log.warning("LINE token exchange OK but no id_token in body")
        return _line_link_redirect(False, "exchange_failed")

    # 3) Verify id_token signature + standard claims.
    try:
        claims = _verify_line_id_token(id_token, channel_id, channel_secret)
    except ValueError as exc:
        log.warning("id_token verify failed: %s", exc)
        return _line_link_redirect(False, "invalid_token")

    line_user_id = (claims.get("sub") or "").strip()
    if not line_user_id:
        return _line_link_redirect(False, "invalid_token")
    display_name = (claims.get("name") or "").strip()

    # 4) ใช้ตรรกะผูกบัญชีตัวเดียวกับคำสั่ง "เชื่อม <email>" (DRY — เขียนที่เดียว)
    # เพื่อให้ safety guard (ย้ายข้อมูล auto-user + เคลียร์ MerchantOverride) อยู่จุดเดียว.
    from backend.line_bot import _link_line_to_user

    db = SessionLocal()
    try:
        result = _link_line_to_user(
            db,
            web_user_id=web_user_id,
            line_user_id=line_user_id,
            display_name=display_name,
        )
        db.commit()
        log.info(
            "LINE OAuth link OK: web_user_id=%s line_user_id=%s status=%s moved_tx=%s",
            web_user_id, line_user_id, result["status"], result["moved_tx"],
        )
    except ValueError as exc:
        db.rollback()
        log.warning("LINE OAuth link target missing: %s", exc)
        return _line_link_redirect(False, "user_missing")
    except Exception:
        db.rollback()
        log.exception("LINE OAuth link DB error")
        return _line_link_redirect(False, "link_failed")
    finally:
        db.close()

    return _line_link_redirect(True)


@app.route("/api/line/unlink", methods=["POST"])
def api_line_unlink():
    """ยกเลิกการเชื่อม LINE ของ user (ลบเฉพาะแถว LineUser).

    ไม่แตะ transactions/imports/notifications — ข้อมูลยังอยู่กับบัญชีเว็บครบ
    (เชื่อมใหม่ทีหลังได้). รับ body {user_id}.

    Remove the LINE↔MoneyMind link for ``user_id``.

    After unlink the LINE user can re-link by sending ``เชื่อม <email>`` to the
    bot again. We do NOT touch transactions/imports/notifications — they stay
    with the web account.
    """
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    db = SessionLocal()
    try:
        deleted = db.query(LineUser).filter_by(user_id=int(user_id)).delete(synchronize_session=False)
        db.commit()
        return jsonify({"ok": True, "unlinked": int(deleted)})
    except Exception as exc:
        db.rollback()
        log.exception("line unlink failed for user_id=%s", user_id)
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()


# ─── Transactions ────────────────────────────────────────────────────────────

@app.route("/api/transactions", methods=["GET"])
def api_list_transactions():
    """คืนรายการ transaction ทั้งหมดของ user เรียงวันที่ล่าสุดก่อน (ใช้ index user_id)."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    db = SessionLocal()
    try:
        rows = (
            db.query(Transaction)
            .filter_by(user_id=user_id)
            .order_by(Transaction.date.desc(), Transaction.id.desc())
            .all()
        )
        return jsonify([r.to_dict() for r in rows])
    finally:
        db.close()


# ─── Learning Loop helpers (merchant→category overrides) ────────────────────

_WS_RE = re.compile(r"\s+")


def _normalize_merchant(m) -> str:
    """Normalise a merchant string for override fingerprinting.

    Lowercase + strip + collapse internal whitespace runs to a single space.
    Returns ``""`` for empty / None input so callers can short-circuit
    cheaply.  Mirrors the merchant side of ``_dedup_build_rows``'s
    fingerprint (case-insensitive, whitespace-tolerant) so the same string
    that dedups also matches a saved override.
    """
    if not m:
        return ""
    return _WS_RE.sub(" ", str(m).strip().lower())


def _apply_overrides(db, user_id: int, txs: list[dict]) -> list[dict]:
    """จัดหมวดใหม่ให้ tx ที่ merchant ตรงกับ override ที่ user เคยสอนไว้ (Learning Loop).

    Re-categorise tx dicts whose merchant matches a saved override.

    Mutates each tx dict in place (setting ``tx['category']``) and returns
    the same list for chaining. Uses a single indexed query on
    ``MerchantOverride.user_id`` — O(N + M) for N overrides + M txs, no N+1.

    Called BEFORE dedup at every insert site so the categories that land
    in the DB already reflect the user's learned preferences. Safe no-op
    when the user has no overrides yet.
    """
    if not txs:
        return txs
    rows = (
        db.query(MerchantOverride.merchant_norm, MerchantOverride.category)
        .filter(MerchantOverride.user_id == user_id)
        .all()
    )
    if not rows:
        return txs
    mapping = {norm: cat for norm, cat in rows}
    for tx in txs:
        norm = _normalize_merchant(tx.get("merchant"))
        if norm and norm in mapping:
            tx["category"] = mapping[norm]
    return txs


def _dedup_build_rows(db, user_id: int, txs: list[dict], import_id):
    """Build Transaction ORM rows from a payload, skipping duplicates.

    A transaction is considered a duplicate when its fingerprint
    ``(date[:10], round(amount, 2), merchant.strip().lower())`` already
    exists in the DB for this user, OR when the same fingerprint appeared
    earlier in the current batch.

    Existing fingerprints are loaded with a single query that uses the
    ``user_id`` index, so this is O(N + M) for N existing + M payload rows
    and avoids the N+1 / per-row roundtrip trap.

    Returns: ``(rows_to_insert, skipped_count)``.

    Shared by ``POST /api/transactions`` (web) and ``_handle_pdf`` (LINE).
    """
    # ดึงเฉพาะ 3 คอลัมน์ที่ใช้ทำ fingerprint (ไม่ดึงทั้งแถว) ด้วย query เดียว
    # → เอามาทำเป็น set เพื่อเช็คซ้ำแบบ O(1) ต่อรายการ (ไม่ยิง DB ทีละแถว = กัน N+1).
    existing_rows = (
        db.query(Transaction.date, Transaction.amount, Transaction.merchant)
        .filter(Transaction.user_id == user_id)
        .all()
    )
    # fingerprint = (วันที่ 10 ตัวแรก, ยอดปัดทศนิยม 2, ชื่อร้าน lowercase+trim)
    # → 3 อย่างนี้ตรงกันเมื่อไหร่ถือว่า "รายการเดียวกัน" (กันอัปโหลดไฟล์ทับซ้ำ)
    existing: set[tuple[str, float, str]] = {
        ((d or "")[:10], round(float(a or 0), 2), (m or "").strip().lower())
        for d, a, m in existing_rows
    }

    rows: list[Transaction] = []
    seen_in_batch: set[tuple[str, float, str]] = set()
    skipped = 0

    for tx in txs:
        date = (tx.get("date") or "")[:10]
        merchant = tx.get("merchant") or ""
        try:
            amount = float(tx.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        fp = (date, round(amount, 2), merchant.strip().lower())

        # ซ้ำกับที่มีใน DB อยู่แล้ว หรือ ซ้ำกับรายการก่อนหน้าในไฟล์ชุดเดียวกันนี้
        # → ข้าม (นับ skipped). seen_in_batch กันซ้ำภายในไฟล์เดียวกันด้วย.
        if fp in existing or fp in seen_in_batch:
            skipped += 1
            continue
        seen_in_batch.add(fp)

        rows.append(Transaction(
            user_id=user_id,
            source_import_id=import_id,
            date=date,
            merchant=merchant,
            amount=amount,
            type=tx.get("type") or "",
            category=tx.get("category") or "other",
            note=tx.get("note") or "",
        ))

    return rows, skipped


@app.route("/api/transactions", methods=["POST"])
def api_create_transactions():
    """Bulk-insert transaction: apply Learning Loop overrides → dedup → บันทึก.

    หลัง insert ถ้ามีรายการใหม่ (created>0) จะ push budget alert เข้า LINE ให้ด้วย
    (ข้ามถ้าเป็นซ้ำทั้งหมด — ยอดรวมไม่ขยับ ไม่มีอะไรต้องเตือน).
    """
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    txs = body.get("transactions") or []
    import_id = body.get("import_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    if not isinstance(txs, list) or not txs:
        return jsonify({"error": "transactions list required"}), 400

    db = SessionLocal()
    try:
        # Apply Learning Loop overrides BEFORE dedup so the categories the
        # user has previously taught us land in the DB instead of whatever
        # the PDF parser inferred. Mutates txs in place.
        _apply_overrides(db, int(user_id), txs)
        rows, skipped = _dedup_build_rows(db, int(user_id), txs, import_id)
        if rows:
            db.bulk_save_objects(rows)
        db.commit()
    except Exception as exc:
        db.rollback()
        log.exception("bulk insert failed")
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()

    created = len(rows)

    # Skip the budget-alert push when nothing new was inserted — totals
    # cannot have moved, so there is nothing fresh to warn about.
    if created > 0:
        try:
            from backend.line_bot import _push_budget_alerts
            _push_budget_alerts(int(user_id))
        except Exception:
            log.exception("budget alert after web bulk insert failed")

    return jsonify({"created": created, "skipped": skipped})


@app.route("/api/transactions/<int:tx_id>", methods=["PATCH"])
def api_patch_transaction(tx_id: int):
    """เปลี่ยนหมวดของ tx 1 รายการ + (option) จำไว้สอนระบบ (Learning Loop).

    ถ้า save_pattern=true จะ upsert MerchantOverride → ครั้งหน้า import ร้านเดิม
    ระบบจัดหมวดนี้ให้อัตโนมัติ. มี ownership check (403 ถ้า tx ไม่ใช่ของ user นี้)
    กันคนแก้ข้อมูลคนอื่นด้วยการเดา id.

    Re-categorise a single transaction (Learning Loop, Day 5).

    Body: ``{"user_id": int, "category": str, "save_pattern": bool}``
    Response: ``{"updated": 1, "override_saved": true|false}``

    When ``save_pattern`` is true and the transaction has a non-empty
    merchant, we upsert a ``MerchantOverride`` row so future imports of the
    same merchant auto-apply this category. ``override_saved`` reflects
    whether that upsert actually happened (false if save_pattern was off,
    or if the merchant string was empty).

    Errors:
      400 — user_id or category missing
      403 — tx.user_id != body user_id (ownership guard)
      404 — tx not found
    """
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    new_category = (body.get("category") or "").strip()
    save_pattern = bool(body.get("save_pattern"))

    if not user_id or not new_category:
        return jsonify({"error": "user_id and category required"}), 400

    db = SessionLocal()
    try:
        tx = db.query(Transaction).filter_by(id=tx_id).first()
        if tx is None:
            return jsonify({"error": "not found"}), 404
        # ownership guard — tx นี้ต้องเป็นของ user ที่ส่งมา ไม่งั้น 403 (ห้ามแก้ของคนอื่น)
        if tx.user_id != int(user_id):
            return jsonify({"error": "forbidden"}), 403

        tx.category = new_category

        override_saved = False
        if save_pattern:
            merchant_norm = _normalize_merchant(tx.merchant)
            if merchant_norm:
                # upsert MerchantOverride แบบ manual: หาแถวเดิมก่อน — มีแล้วก็ update
                # หมวด, ไม่มีก็ insert ใหม่ (กันสร้างซ้ำ + เคารพ UniqueConstraint)
                existing = (
                    db.query(MerchantOverride)
                    .filter_by(user_id=int(user_id), merchant_norm=merchant_norm)
                    .first()
                )
                if existing:
                    existing.category = new_category
                else:
                    db.add(MerchantOverride(
                        user_id=int(user_id),
                        merchant_norm=merchant_norm,
                        category=new_category,
                    ))
                override_saved = True

        db.commit()
        return jsonify({"updated": 1, "override_saved": override_saved})
    except Exception as exc:
        db.rollback()
        log.exception("patch transaction failed for tx_id=%s", tx_id)
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()


# ─── Imports (audit log of statement uploads) ───────────────────────────────

@app.route("/api/imports", methods=["POST"])
def api_create_import():
    """สร้าง audit record ของการอัปโหลด statement 1 ครั้ง (filename/bank/count)."""
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    db = SessionLocal()
    try:
        imp = Import(
            user_id=user_id,
            filename=body.get("filename") or "",
            bank=body.get("bank") or "unknown",
            count=int(body.get("count") or 0),
        )
        db.add(imp)
        db.commit()
        db.refresh(imp)
        return jsonify(imp.to_dict())
    finally:
        db.close()


@app.route("/api/imports", methods=["GET"])
def api_list_imports():
    """คืนประวัติการอัปโหลด statement ของ user เรียงล่าสุดก่อน."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    db = SessionLocal()
    try:
        rows = db.query(Import).filter_by(user_id=user_id).order_by(Import.imported_at.desc()).all()
        return jsonify([r.to_dict() for r in rows])
    finally:
        db.close()


@app.route("/api/imports/<int:import_id>", methods=["DELETE"])
def api_delete_import(import_id: int):
    """Undo การนำเข้า: ลบแถว Import + tx ทุกตัวที่มาจาก import นั้น (source_import_id).

    ต้องส่ง ?user_id เพื่อเช็คความเป็นเจ้าของ (403 ถ้าไม่ตรง) — กันคนเดา id
    แล้วลบ import ของคนอื่น.

    Undo an import: delete the Import row plus every Transaction whose
    source_import_id matches.

    Requires ``?user_id=<int>`` to verify ownership — without this anyone
    could delete anyone else's import by guessing the id.
    """
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    db = SessionLocal()
    try:
        imp = db.query(Import).filter_by(id=import_id).first()
        if imp is None:
            return jsonify({"error": "import not found"}), 404
        if imp.user_id != user_id:
            return jsonify({"error": "forbidden"}), 403

        removed_txs = (
            db.query(Transaction)
            .filter_by(source_import_id=import_id, user_id=user_id)
            .delete(synchronize_session=False)
        )
        db.delete(imp)
        db.commit()
        return jsonify({"deleted": 1, "removed_txs": int(removed_txs)})
    except Exception as exc:
        db.rollback()
        log.exception("delete import failed for id=%s", import_id)
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()


# ─── Reset (destructive: wipe a user's statement data) ──────────────────────

@app.route("/api/reset", methods=["POST"])
def api_reset_user_data():
    """ล้างข้อมูล statement ของ user (tx + imports + notifications) แบบเริ่มใหม่.

    เก็บบัญชี/งบ/การเชื่อม LINE ไว้ ลบเฉพาะข้อมูลรายการ. ต้องส่ง ?user_id.
    หมายเหตุ FK: ต้องลบ Transaction ก่อน Import เพราะ tx อ้าง imports.id อยู่
    (ลบพ่อก่อนลูก Postgres จะ error).

    Wipe all statement-related data for a user (Day 4 feature).

    Deletes every Transaction, Import, and Notification owned by ``user_id``.
    Keeps the User row, Preference (incl. category_budgets) and any LineUser
    link so the account + LINE pairing survive the reset.

    Requires ``?user_id=<int>`` in the query string — body is ignored to
    follow the destructive-endpoint pattern used by ``DELETE /api/imports``.
    """
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    db = SessionLocal()
    try:
        # Verify the user exists so callers can't fish with random ids.
        user = db.query(User).filter_by(id=user_id).first()
        if user is None:
            return jsonify({"error": "user not found"}), 404

        # Delete Transactions before Imports — Transaction.source_import_id is
        # a FK to imports.id, so wiping the parent first would violate the FK
        # constraint on Postgres.
        deleted_txs = (
            db.query(Transaction)
            .filter_by(user_id=user_id)
            .delete(synchronize_session=False)
        )
        deleted_imports = (
            db.query(Import)
            .filter_by(user_id=user_id)
            .delete(synchronize_session=False)
        )
        deleted_notifications = (
            db.query(Notification)
            .filter_by(user_id=user_id)
            .delete(synchronize_session=False)
        )
        db.commit()

        log.info(
            "reset user_id=%s — deleted_txs=%s deleted_imports=%s deleted_notifications=%s",
            user_id, deleted_txs, deleted_imports, deleted_notifications,
        )
        return jsonify({
            "deleted_txs": int(deleted_txs),
            "deleted_imports": int(deleted_imports),
            "deleted_notifications": int(deleted_notifications),
        })
    except Exception as exc:
        db.rollback()
        log.exception("reset failed for user_id=%s", user_id)
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()


# ─── Notifications ───────────────────────────────────────────────────────────

@app.route("/api/notifications", methods=["GET"])
def api_list_notifications():
    """คืนการแจ้งเตือนล่าสุด 50 รายการของ user (เรียงใหม่ไปเก่า)."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    db = SessionLocal()
    try:
        rows = (
            db.query(Notification)
            .filter_by(user_id=user_id)
            .order_by(Notification.created_at.desc())
            .limit(50)
            .all()
        )
        return jsonify([r.to_dict() for r in rows])
    finally:
        db.close()


@app.route("/api/notifications", methods=["POST"])
def api_create_notification():
    """สร้างการแจ้งเตือน 1 รายการ (title/desc เก็บเป็น i18n JSON {th,en})."""
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    db = SessionLocal()
    try:
        n = Notification(
            user_id=user_id,
            kind=body.get("type") or "info",
            icon=body.get("icon") or "bell",
            title=body.get("title") or {},
            desc=body.get("desc") or {},
            unread=bool(body.get("unread", True)),
        )
        db.add(n)
        db.commit()
        db.refresh(n)
        return jsonify(n.to_dict())
    finally:
        db.close()


@app.route("/api/notifications/mark-read", methods=["POST"])
def api_mark_read():
    """mark การแจ้งเตือนที่ยังไม่อ่านของ user ทั้งหมดเป็นอ่านแล้ว (bulk update)."""
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    db = SessionLocal()
    try:
        db.query(Notification).filter_by(user_id=user_id, unread=True).update({"unread": False})
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


# ─── Preferences ────────────────────────────────────────────────────────────

@app.route("/api/preferences/<int:user_id>", methods=["GET"])
def api_get_prefs(user_id: int):
    """คืน preferences ของ user — สร้าง row default ให้อัตโนมัติถ้ายังไม่มี."""
    db = SessionLocal()
    try:
        p = db.query(Preference).filter_by(user_id=user_id).first()
        if p is None:
            p = Preference(user_id=user_id)
            db.add(p)
            db.commit()
            db.refresh(p)
        return jsonify(p.to_dict())
    finally:
        db.close()


@app.route("/api/preferences/<int:user_id>", methods=["PUT"])
def api_set_prefs(user_id: int):
    """อัปเดต preferences แบบ partial — เขียนเฉพาะ key ที่ส่งมาใน body.

    หมายเหตุ: ``theme`` ผ่าน whitelist เข้ม 'light'/'dark' เท่านั้น
    (กันค่าแปลกปลอมหลุดเข้าไปใน CSS selector/class ฝั่ง frontend).
    """
    body = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        p = db.query(Preference).filter_by(user_id=user_id).first()
        if p is None:
            p = Preference(user_id=user_id)
            db.add(p)
        for key, attr in [
            ("accent", "accent"),
            ("density", "density"),
            ("lang", "lang"),
            ("currency", "currency"),
            ("showAmbient", "show_ambient"),
            ("categoryBudgets", "category_budgets"),
            # Sprint 5 — Settings → Notifications toggles. Cast to bool so
            # truthy strings ("false" / 0) from a misbehaving client don't
            # silently flip the flag the wrong way.
            ("budgetAlertEnabled", "budget_alert_enabled"),
            ("lineNotifyEnabled", "line_notify_enabled"),
            # Light/dark theme (post-Sprint 5). Whitelisted strictly so a
            # buggy / malicious client can't smuggle an arbitrary value into
            # a CSS selector or class name down the line.
            ("theme", "theme"),
        ]:
            if key in body:
                val = body[key]
                if attr in ("budget_alert_enabled", "line_notify_enabled"):
                    val = bool(val)
                if attr == "theme":
                    if val not in ("light", "dark"):
                        return jsonify({"error": "theme must be 'light' or 'dark'"}), 400
                setattr(p, attr, val)
        db.commit()
        db.refresh(p)
        return jsonify(p.to_dict())
    finally:
        db.close()


# ─── AI (Gemini default, Anthropic fallback) ─────────────────────────────────

# Locked API contract (do NOT change — ACHI's frontend depends on it):
#   POST /api/ai/complete   body {"prompt": "<string>"}  →  {"text": "<string>"}
#
# Used by the web "AI Insights" (derived → real) and the "คุยกับ Mind" chat
# panel, replacing the old window.claude.complete() that only existed inside
# the Claude.ai artifact sandbox (undefined on Render → silent failures).
#
# Provider priority:
#   1) GEMINI_API_KEY set    → try Gemini first (free tier — preferred)
#   2) ANTHROPIC_API_KEY set → fall back to Anthropic (paid)
#   3) Neither set / both fail → return {"text": ""} so the frontend's
#      null-fallback path renders cleanly instead of throwing.

# NOTE: pin model "gemini-2.5-flash" ตรงๆ — เลิกใช้ alias "gemini-flash-latest"
# เพราะ Google เปลี่ยน route alias ไป gemini-3.5-flash (preview) ที่ daily
# quota แค่ 20 req/วัน (จากเดิม 1500) → ใช้งาน demo จริงไม่พอ.
# 2.5-flash = stable model + free tier RPD 1500 + RPM 15 (พอสำหรับ demo).
# 1.5/2.0 ใช้ไม่ได้แล้ว (Google ถอน endpoint v1beta ตั้งแต่ Sprint 3).
# ถ้าวันหลัง 2.5-flash ถูก deprecate → ตรวจ https://ai.google.dev/models
# แล้ว bump เป็น 3.5-flash-stable หรือใหม่กว่า (ห้ามใช้ -latest alias อีก).
_GEMINI_MODEL = "gemini-2.5-flash"
_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
_AI_MAX_TOKENS = 2048
_AI_MAX_PROMPT_CHARS = 12000  # guard against runaway / abusive prompts


def _call_gemini(prompt: str) -> str:
    """Call Google Gemini and return the response text.

    Raises on any failure (missing SDK, auth error, network, quota) so the
    route handler can fall back to the next provider in the chain.

    Quota note: free tier daily quota can be exhausted (429
    RESOURCE_EXHAUSTED). We detect that specific case and log a clear
    warning so ops can distinguish "quota issue" from generic errors —
    behaviour is unchanged (re-raise → fallback to Anthropic).
    """
    import google.generativeai as genai  # lazy import — never crash startup

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(_GEMINI_MODEL)
    try:
        resp = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": _AI_MAX_TOKENS},
        )
    except Exception as exc:
        # Detect quota exhaustion specifically to give ops a clear signal.
        # google-generativeai surfaces this as ResourceExhausted / 429 with
        # the string "quota" / "RESOURCE_EXHAUSTED" in the message.
        msg = str(exc)
        lowered = msg.lower()
        if (
            "resource_exhausted" in lowered
            or "quota" in lowered
            or "429" in msg
        ):
            log.warning(
                "Gemini quota exceeded for model=%s (free tier daily limit "
                "likely hit) — falling back to next provider. detail=%s",
                _GEMINI_MODEL,
                msg,
            )
        # Re-raise so the route handler's provider chain falls back as usual.
        raise

    # `resp.text` concatenates all text parts; guard for empty/blocked responses.
    text = (getattr(resp, "text", "") or "").strip()

    # Detect MAX_TOKENS truncation so ops can spot when _AI_MAX_TOKENS is too
    # small (Gemini cuts mid-sentence — user sees half a reply). We still
    # return whatever text we got — a truncated answer is better than none.
    # SDK shape varies between versions, so wrap in try/except to stay safe.
    try:
        candidates = getattr(resp, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
            # finish_reason may be an enum (.name == "MAX_TOKENS"), a string,
            # or an int (2 in some SDK builds). Normalise all three.
            fr_name = getattr(finish_reason, "name", None) or str(finish_reason)
            if fr_name == "MAX_TOKENS" or finish_reason == 2:
                log.warning(
                    "Gemini response truncated by max_tokens=%d — "
                    "consider raising _AI_MAX_TOKENS",
                    _AI_MAX_TOKENS,
                )
    except Exception:
        pass  # never let telemetry crash the response path

    return text


def _call_anthropic(prompt: str) -> str:
    """Call Anthropic Claude and return the response text.

    Raises on any failure so the route handler can fall back.
    """
    import anthropic  # lazy import — never crash startup

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=_AI_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    # resp.content is a list of content blocks; concatenate text blocks.
    text = "".join(
        getattr(block, "text", "") for block in (resp.content or [])
    ).strip()
    return text


@app.route("/api/ai/complete", methods=["POST"])
def api_ai_complete():
    """พร็อกซี AI: รับ {prompt} → ลอง Gemini ก่อน ไม่ได้ค่อย fallback Anthropic.

    คืน {"text": "..."} เสมอ (แม้ไม่มี key/ล้มทั้งคู่ก็คืน text ว่าง 200/502)
    เพื่อให้ frontend มี null-fallback แสดงผลได้ ไม่ crash. ใช้โดยปุ่ม "วิเคราะห์
    ด้วย AI" + ChatPanel "คุยกับ Mind".
    """
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()

    # Empty prompt → nothing to do. Return 200 + empty text so the frontend
    # (which falls back to null / an apology message) handles it gracefully.
    if not prompt:
        return jsonify({"text": ""})

    # Clamp overly long prompts instead of rejecting — keeps the UX working
    # while capping token cost on the provider bill.
    if len(prompt) > _AI_MAX_PROMPT_CHARS:
        prompt = prompt[:_AI_MAX_PROMPT_CHARS]

    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    # Build the ordered provider chain. Gemini first (free tier preferred),
    # Anthropic as fallback. Skipping providers whose key is missing avoids
    # a guaranteed-fail attempt + a noisy stack trace in the logs.
    providers: list[tuple[str, callable]] = []
    if has_gemini:
        providers.append(("gemini", _call_gemini))
    if has_anthropic:
        providers.append(("anthropic", _call_anthropic))

    if not providers:
        log.warning(
            "/api/ai/complete: no AI provider key set "
            "(GEMINI_API_KEY / ANTHROPIC_API_KEY) — returning empty text"
        )
        return jsonify({"text": ""})

    last_error: str | None = None
    for name, fn in providers:
        log.info("/api/ai/complete: trying provider=%s", name)
        try:
            text = fn(prompt)
            log.info("/api/ai/complete: provider=%s succeeded (%d chars)", name, len(text))
            return jsonify({"text": text})
        except ImportError as exc:
            last_error = f"{name}: SDK not installed ({exc})"
            log.error(
                "/api/ai/complete: provider=%s SDK missing — run pip install -r requirements.txt",
                name,
            )
        except Exception as exc:
            last_error = f"{name}: {exc}"
            log.warning("/api/ai/complete: provider=%s failed: %s", name, exc)

    # All providers exhausted. 502 + empty text so the frontend's null-fallback
    # path still renders cleanly (no crash) but ops can see the error in DevTools.
    log.error("/api/ai/complete: all providers failed; last_error=%s", last_error)
    return jsonify({"text": "", "error": last_error or "all providers failed"}), 502


# ─── LINE Webhook ────────────────────────────────────────────────────────────

@app.route("/webhook/line", methods=["POST"])
def line_webhook():
    """รับ event จาก LINE (ข้อความ/ไฟล์/เพิ่มเพื่อน) แล้วส่งต่อให้ handler ประมวลผล.

    Receives LINE Messaging API webhook events.
    """
    line_handler = _get_line_handler()
    if line_handler is None:
        return jsonify({"error": "LINE bot not configured"}), 503

    # X-Line-Signature = ลายเซ็นที่ LINE แนบมากับทุก request (HMAC ด้วย channel
    # secret). handler.handle() จะตรวจว่า body ตรงกับลายเซ็นไหม — ด่านความปลอดภัย
    # สำคัญ กันคนปลอม request ยิงเข้ามา. ห้ามข้ามการตรวจนี้เด็ดขาด.
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        from linebot.v3.exceptions import InvalidSignatureError
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        # ลายเซ็นไม่ตรง = request ไม่ได้มาจาก LINE จริง → ปฏิเสธ 400
        log.warning("LINE webhook: invalid signature")
        return jsonify({"error": "invalid signature"}), 400
    except Exception as exc:
        log.exception("LINE webhook handler error")
        return jsonify({"error": str(exc)}), 500

    return jsonify({"ok": True})


# ─── Grace Period Cleanup (Sprint 5) ────────────────────────────────────────

def _run_grace_period_cleanup() -> int:
    """ลบถาวร user ที่หมด grace period 30 วันแล้ว + ข้อมูลลูกทั้งหมด (cascade).

    ลำดับ cascade สำคัญมาก: ต้องลบตารางลูก (FK → users.id) ให้หมดก่อนค่อยลบ
    แถว ``users`` ไม่งั้น Postgres จะ reject ด้วย FK constraint. ลำดับที่ใช้:
    MerchantOverride → Transaction → Import → Notification → Preference →
    LinePendingPdf (resolve ผ่าน line_user_id ก่อน) → LineUser → User.

    Cascade order matters: child rows (FK → users.id) must be removed before
    the parent ``users`` row, otherwise Postgres' foreign-key constraints
    reject the parent delete. We do this explicitly instead of relying on
    SQLAlchemy's ``cascade="all, delete-orphan"`` because (a) some tables —
    notably ``merchant_overrides`` and ``line_users`` — don't carry that
    cascade on the relationship side, and (b) bulk ``DELETE WHERE user_id=?``
    is dramatically faster than loading each child into the session.

    Returns the number of users hard-deleted (for logging / admin endpoint).

    Hosting note: Render Free tier has no native cron. Trigger this from an
    external scheduler (e.g. cron-job.org, GitHub Actions, or a paid Render
    cron service) once every 24h by calling
    ``POST /api/admin/run-grace-cleanup?token=<ADMIN_CLEANUP_TOKEN>``.
    """
    db = SessionLocal()
    try:
        expired = (
            db.query(User)
            .filter(
                User.delete_scheduled_at.isnot(None),
                User.delete_scheduled_at < datetime.utcnow(),
            )
            .all()
        )
        count = 0
        for user in expired:
            uid = user.id
            # FK-safe order: children before parent. synchronize_session=False
            # because we're not reading these rows back in this transaction —
            # avoids SQLAlchemy's "expire" overhead for the bulk delete.
            db.query(MerchantOverride).filter_by(user_id=uid).delete(synchronize_session=False)
            db.query(Transaction).filter_by(user_id=uid).delete(synchronize_session=False)
            db.query(Import).filter_by(user_id=uid).delete(synchronize_session=False)
            db.query(Notification).filter_by(user_id=uid).delete(synchronize_session=False)
            db.query(Preference).filter_by(user_id=uid).delete(synchronize_session=False)
            # Privacy — clear pending PDF bytes (อาจมี PII จาก statement) ก่อนลบ LineUser
            # LinePendingPdf ผูก line_user_id ไม่ใช่ user_id → ต้อง resolve ก่อน
            line_uids = [
                lu.line_user_id
                for lu in db.query(LineUser).filter_by(user_id=uid).all()
            ]
            if line_uids:
                db.query(LinePendingPdf).filter(
                    LinePendingPdf.line_user_id.in_(line_uids)
                ).delete(synchronize_session=False)
            db.query(LineUser).filter_by(user_id=uid).delete(synchronize_session=False)
            db.delete(user)
            count += 1
        db.commit()
        if count:
            log.info("grace cleanup: hard-deleted %d user(s)", count)
        return count
    except Exception:
        db.rollback()
        log.exception("grace cleanup failed")
        raise
    finally:
        db.close()


# ─── Lazy grace-period cleanup ───────────────────────────────────────────────
# แทนที่จะใช้ external cron (cron-job.org / GitHub Actions / Render Cron)
# เราใช้ pattern "ลบเมื่อมีคน login ครั้งแรกของวัน" — zero external dep.
# Trade-off: ถ้าไม่มีใคร login เลย 30+ วัน → cleanup ไม่ทำงาน
# (acceptable สำหรับ demo/staging — production ควรพิจารณา external cron)
#
# Multi-worker note: Render รัน gunicorn --workers 2 → _LAST_AUTO_CLEANUP
# เป็น per-process state ไม่ shared ระหว่าง workers. Worst case อาจรัน
# cleanup 2 ครั้ง/วัน (1 ครั้งต่อ worker). DELETE query ใน
# _run_grace_period_cleanup() เป็น idempotent (filter
# delete_scheduled_at < utcnow()) → รันซ้ำไม่พัง ไม่ผลิตข้อมูลซ้ำ.

# Lazy cleanup throttle — รันได้สูงสุดวันละ 1 ครั้ง (per worker process)
_LAST_AUTO_CLEANUP: datetime | None = None
_AUTO_CLEANUP_INTERVAL = timedelta(hours=24)


def _maybe_run_auto_cleanup() -> None:
    """รัน grace cleanup อัตโนมัติ — throttle 24 ชม.

    เรียกจาก /api/auth/login (และ endpoint อื่นที่เหมาะสมในอนาคต).
    Non-blocking: ถ้า cleanup error → log + continue (ไม่ raise)
    Idempotent: ถ้ารันแล้วใน 24 ชม. → skip
    """
    global _LAST_AUTO_CLEANUP
    now = datetime.utcnow()
    if _LAST_AUTO_CLEANUP and (now - _LAST_AUTO_CLEANUP) < _AUTO_CLEANUP_INTERVAL:
        return  # รันแล้วใน 24 ชม. → skip
    # Update timestamp ก่อนรัน → กัน race condition (multiple threads ใน
    # process เดียวกันเรียกพร้อมกัน). ถ้า cleanup fail timestamp ยัง update
    # แล้ว → จะ retry อีก 24 ชม. ข้างหน้า (admin endpoint ใช้ debug ได้ทันที)
    _LAST_AUTO_CLEANUP = now
    try:
        deleted = _run_grace_period_cleanup()
        if deleted:
            log.info("lazy cleanup: hard-deleted %d expired user(s)", deleted)
    except Exception:
        log.exception("lazy cleanup failed (non-blocking)")
        # ไม่ raise — login ของ user ต้องสำเร็จเสมอ


@app.route("/api/admin/run-grace-cleanup", methods=["POST"])
def api_run_grace_cleanup():
    """Manual trigger for the grace-period cleanup job.

    Protected by a shared-secret query param ``?token=<ADMIN_CLEANUP_TOKEN>``.
    If the env var is unset, the route returns 404 so a curious scanner sees
    nothing — there's no safe default token to fall back to.
    """
    expected = (os.environ.get("ADMIN_CLEANUP_TOKEN") or "").strip()
    if not expected:
        # No token configured → endpoint disabled. 404 (not 403) so it's
        # indistinguishable from a non-existent route from the outside.
        return jsonify({"error": "not found"}), 404
    if request.args.get("token", "") != expected:
        return jsonify({"error": "forbidden"}), 403

    try:
        deleted = _run_grace_period_cleanup()
        return jsonify({"ok": True, "deleted_users": deleted})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ─── Health ─────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    # liveness check — ให้ Render/uptime monitor ยิงมาเช็คว่าแอปยังตอบอยู่ (200 = ยังมีชีวิต)
    return jsonify({"ok": True})


def _open_browser():
    webbrowser.open_new("http://localhost:5000/")


if __name__ == "__main__":
    # On Render (or any cloud host), PORT env var is set and we bind 0.0.0.0
    # so traffic can reach the container. Locally we keep 127.0.0.1 + browser.
    port = int(os.environ.get("PORT", "5000"))
    is_cloud = os.environ.get("RENDER") or os.environ.get("PORT")

    if not is_cloud and not os.environ.get("WERKZEUG_RUN_MAIN"):
        Timer(1.0, _open_browser).start()

    host = "0.0.0.0" if is_cloud else "127.0.0.1"
    app.run(host=host, port=port, debug=False)

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
    return render_template("index.html")


@app.route("/ui/<path:filename>")
def ux_ui_static(filename: str):
    """Serve files from the ux_ui/ folder (styles.css, ui.jsx, tweaks-panel.jsx)."""
    return send_from_directory(UX_UI_DIR, filename)


# ─── PDF parsing (logic_ai) ──────────────────────────────────────────────────

@app.route("/api/parse-pdf", methods=["POST"])
def api_parse_pdf():
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
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip() or (email.split("@")[0] if email else "User")
    if not email:
        return jsonify({"error": "email required"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).first()
        if user is None:
            user = User(email=email, name=name)
            db.add(user)
            db.commit()
            db.refresh(user)
            # Seed default preferences row
            db.add(Preference(user_id=user.id))
            db.commit()
        elif name and not user.name:
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
    """Return the user's profile + grace-period status.

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
    """Update mutable user fields: ``name`` and/or ``display_name``.

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
    """Schedule a hard-delete with a 30-day grace period.

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
    """Abort a pending hard-delete. Idempotent — safe to call when no delete
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
    """Stream all of a user's transactions as a downloadable CSV.

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
    """Return whether ``user_id`` has a LINE account linked.

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


@app.route("/api/line/unlink", methods=["POST"])
def api_line_unlink():
    """Remove the LINE↔MoneyMind link for ``user_id``.

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
    """Re-categorise tx dicts whose merchant matches a saved override.

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
    existing_rows = (
        db.query(Transaction.date, Transaction.amount, Transaction.merchant)
        .filter(Transaction.user_id == user_id)
        .all()
    )
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
    """Re-categorise a single transaction (Learning Loop, Day 5).

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
        if tx.user_id != int(user_id):
            return jsonify({"error": "forbidden"}), 403

        tx.category = new_category

        override_saved = False
        if save_pattern:
            merchant_norm = _normalize_merchant(tx.merchant)
            if merchant_norm:
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
    """Undo an import: delete the Import row plus every Transaction whose
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
    """Wipe all statement-related data for a user (Day 4 feature).

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

# NOTE: ใช้ gemini-flash-latest alias เพราะ google-generativeai SDK
# (legacy, deprecated โดย Google เอง) ใช้ endpoint v1beta ซึ่ง Google
# ถอน gemini-1.5-flash-002 และ gemini-1.5-flash ออกแล้ว (ทดสอบบน
# production แล้วเจอ 404). 2.0-flash ใช้ได้แต่ free tier daily quota
# ตึงเกินไป (เคยเจอ 429). flash-latest = alias ที่ Google เลือก model
# ปัจจุบันให้ ทำให้รอด deprecation. ถ้าอยาก pin model จริงต้องอัปเกรด
# SDK เป็น google-genai ใหม่ (ดู docs ของ Google).
_GEMINI_MODEL = "gemini-flash-latest"
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
    """Receives LINE Messaging API webhook events."""
    line_handler = _get_line_handler()
    if line_handler is None:
        return jsonify({"error": "LINE bot not configured"}), 503

    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        from linebot.v3.exceptions import InvalidSignatureError
        line_handler.handle(body, signature)
    except InvalidSignatureError:
        log.warning("LINE webhook: invalid signature")
        return jsonify({"error": "invalid signature"}), 400
    except Exception as exc:
        log.exception("LINE webhook handler error")
        return jsonify({"error": str(exc)}), 500

    return jsonify({"ok": True})


# ─── Grace Period Cleanup (Sprint 5) ────────────────────────────────────────

def _run_grace_period_cleanup() -> int:
    """Hard-delete every user whose 30-day grace period has expired.

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

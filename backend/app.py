"""MoneyMind Flask backend.

Routes:
    GET  /                       - serve the React-via-Babel SPA (frontend/index.html)
    GET  /fe/<path>              - serve frontend assets (src/*.jsx, src/*.js)
    GET  /ui/<path>              - serve UX/UI assets (styles.css, src/ui.jsx, ...)
    POST /api/parse-pdf          - parse a bank statement PDF, return transactions
    POST /api/auth/login         - upsert user by email, return user record
    GET  /api/transactions       - list a user's transactions
    POST /api/transactions       - bulk-create transactions
    POST /api/imports            - create an import record
    GET  /api/imports            - list a user's imports
    GET  /api/notifications      - list a user's notifications
    POST /api/notifications      - create a notification
    POST /api/notifications/mark-read - mark notifications as read
    GET  /api/preferences/<uid>  - get a user's preferences
    PUT  /api/preferences/<uid>  - update a user's preferences
    POST /api/reset              - wipe a user's txs/imports/notifications
    GET  /api/health             - liveness check

Run with:  python backend/app.py   (from the project root)
"""

from __future__ import annotations

import logging
import os
import sys
import webbrowser
from threading import Timer

from flask import Flask, jsonify, render_template, request, send_from_directory

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

    try:
        bank, txs = parse_statement(data)
    except Exception as exc:
        log.exception("parse_statement failed")
        return jsonify({"error": f"parse failed: {exc}"}), 500

    return jsonify({
        "bank": bank,
        "count": len(txs),
        "filename": f.filename,
        "transactions": txs,
    })


# ─── Auth (lightweight: upsert by email, no password) ────────────────────────

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
        return jsonify(user.to_dict())
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
        ]:
            if key in body:
                setattr(p, attr, body[key])
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

# NOTE: ใช้ gemini-flash-latest alias เพื่อให้ Google ชี้ไป model ล่าสุด
# อัตโนมัติ (กัน 404 จาก model deprecation) — เดิมใช้ gemini-1.5-flash แบบ
# pinned แต่ Google ปลด model นั้นออกจาก v1beta endpoint แล้ว ทำให้เจอ
# `404 models/gemini-1.5-flash is not found` บน production. ใช้ alias
# จะตามอัปเดต model ล่าสุดที่รองรับ free tier ให้เอง ไม่ต้องไล่แก้โค้ด.
_GEMINI_MODEL = "gemini-flash-latest"
_ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
_AI_MAX_TOKENS = 1024
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

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
        rows: list[Transaction] = []
        for tx in txs:
            rows.append(Transaction(
                user_id=user_id,
                source_import_id=import_id,
                date=(tx.get("date") or "")[:10],
                merchant=tx.get("merchant") or "",
                amount=float(tx.get("amount") or 0),
                type=tx.get("type") or "",
                category=tx.get("category") or "other",
                note=tx.get("note") or "",
            ))
        db.bulk_save_objects(rows)
        db.commit()
    except Exception as exc:
        db.rollback()
        log.exception("bulk insert failed")
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()

    # After committing new transactions, push a LINE budget alert if this user
    # has a linked LINE account and any category is now over budget. Done after
    # the session closes (and outside the try so it never affects the insert
    # result). Lazy import keeps app startup independent of the LINE bot.
    try:
        from backend.line_bot import _push_budget_alerts
        _push_budget_alerts(int(user_id))
    except Exception:
        log.exception("budget alert after web bulk insert failed")

    return jsonify({"created": len(rows)})


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


# ─── AI (Anthropic) ──────────────────────────────────────────────────────────

# Locked API contract (do NOT change — ACHI's frontend depends on it):
#   POST /api/ai/complete   body {"prompt": "<string>"}  →  {"text": "<string>"}
#
# Used by the web "AI Insights" (derived → real) and the "คุยกับ Mind" chat
# panel, replacing the old window.claude.complete() that only existed inside
# the Claude.ai artifact sandbox (undefined on Render → silent failures).

_AI_MODEL = "claude-3-5-sonnet-latest"
_AI_MAX_TOKENS = 1024
_AI_MAX_PROMPT_CHARS = 12000  # guard against runaway / abusive prompts


@app.route("/api/ai/complete", methods=["POST"])
def api_ai_complete():
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()

    # Empty prompt → nothing to do. Return 200 + empty text so the frontend
    # (which falls back to null / an apology message) handles it gracefully.
    if not prompt:
        return jsonify({"text": ""})

    # Clamp overly long prompts instead of rejecting — keeps the UX working
    # while capping token cost on the Anthropic bill.
    if len(prompt) > _AI_MAX_PROMPT_CHARS:
        prompt = prompt[:_AI_MAX_PROMPT_CHARS]

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — /api/ai/complete returning empty text")
        return jsonify({"text": ""})

    try:
        import anthropic  # lazy import so a missing lib never crashes startup
    except ImportError:
        log.error("anthropic package not installed — run pip install -r requirements.txt")
        return jsonify({"text": ""})

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=_AI_MODEL,
            max_tokens=_AI_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        # resp.content is a list of content blocks; concatenate text blocks.
        text = "".join(
            getattr(block, "text", "") for block in (resp.content or [])
        ).strip()
        return jsonify({"text": text})
    except Exception as exc:
        log.exception("Anthropic API call failed")
        # 502 + empty text: frontend already falls back to null / apology.
        return jsonify({"text": "", "error": str(exc)}), 502


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

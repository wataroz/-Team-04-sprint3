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
        return jsonify({"created": len(rows)})
    except Exception as exc:
        db.rollback()
        log.exception("bulk insert failed")
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
    logging.basicConfig(level=logging.INFO)

    # On Render (or any cloud host), PORT env var is set and we bind 0.0.0.0
    # so traffic can reach the container. Locally we keep 127.0.0.1 + browser.
    port = int(os.environ.get("PORT", "5000"))
    is_cloud = os.environ.get("RENDER") or os.environ.get("PORT")

    if not is_cloud and not os.environ.get("WERKZEUG_RUN_MAIN"):
        Timer(1.0, _open_browser).start()

    host = "0.0.0.0" if is_cloud else "127.0.0.1"
    app.run(host=host, port=port, debug=False)

"""MoneyMind LINE Bot handler.

Handles LINE Messaging API webhook events.

Supported commands (Thai / English):
  สรุป / summary      → monthly spending summary
  ยอด / balance       → total income vs expense this month
  เดือนนี้ / thismonth → category breakdown
  วิเคราะห์ / analyze  → top 3 spending categories
  ช่วย / help         → command list

PDF upload (as file message) → parse and save transactions.

Environment variables required (put in .env):
  LINE_CHANNEL_SECRET
  LINE_CHANNEL_ACCESS_TOKEN
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from base64 import b64decode
from datetime import datetime, timezone

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    FileMessageContent,
    FollowEvent,
    MessageEvent,
    TextMessageContent,
)

from backend.db import SessionLocal
from backend.models import LineUser, Notification, Transaction, User
from logic_ai.pdf_parser import parse_statement

log = logging.getLogger("moneymind.line")

# ─── SDK setup (reads from env at import time) ─────────────────────────────

_secret = os.environ.get("LINE_CHANNEL_SECRET", "")
_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
APP_URL = os.environ.get("APP_URL", "https://moneymind-team-04-sprint3.onrender.com").rstrip("/")

handler = WebhookHandler(_secret)

_configuration = Configuration(access_token=_token)


def _api() -> MessagingApi:
    return MessagingApi(ApiClient(_configuration))


def _blob_api() -> MessagingApiBlob:
    return MessagingApiBlob(ApiClient(_configuration))


# ─── Helpers ───────────────────────────────────────────────────────────────

def _reply(reply_token: str, text: str) -> None:
    _api().reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=text)],
        )
    )


def _get_or_create_user(line_user_id: str, display_name: str) -> User:
    """Return MoneyMind User linked to this LINE userId, creating if needed."""
    db = SessionLocal()
    try:
        lu = db.query(LineUser).filter_by(line_user_id=line_user_id).first()
        if lu:
            return db.query(User).filter_by(id=lu.user_id).first()

        # Create a new MoneyMind user linked to this LINE account
        fake_email = f"line_{line_user_id}@line.local"
        user = db.query(User).filter_by(email=fake_email).first()
        if user is None:
            user = User(email=fake_email, name=display_name or "LINE User")
            db.add(user)
            db.commit()
            db.refresh(user)

        lu = LineUser(
            line_user_id=line_user_id,
            user_id=user.id,
            display_name=display_name or "",
        )
        db.add(lu)
        db.commit()
        log.info("Linked LINE %s → user_id=%s", line_user_id, user.id)
        return user
    finally:
        db.close()


def _month_transactions(user_id: int) -> list[Transaction]:
    """All transactions for the current calendar month."""
    now = datetime.now(timezone.utc)
    prefix = now.strftime("%Y-%m")
    db = SessionLocal()
    try:
        return (
            db.query(Transaction)
            .filter(Transaction.user_id == user_id, Transaction.date.like(f"{prefix}%"))
            .order_by(Transaction.date.desc())
            .all()
        )
    finally:
        db.close()


def _format_thb(amount: float) -> str:
    return f"฿{amount:,.2f}"


# ─── Command handlers ──────────────────────────────────────────────────────

def _cmd_summary(user_id: int) -> str:
    txs = _month_transactions(user_id)
    if not txs:
        return "ยังไม่มีรายการในเดือนนี้ครับ\nอัปโหลด statement PDF มาได้เลย 📄"

    income = sum(t.amount for t in txs if t.amount > 0)
    expense = sum(abs(t.amount) for t in txs if t.amount < 0)
    net = income - expense
    now = datetime.now(timezone.utc)
    month_th = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
                "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."][now.month]

    lines = [
        f"📊 สรุปเดือน {month_th} {now.year + 543}",
        f"รายรับ  : {_format_thb(income)}",
        f"รายจ่าย : {_format_thb(expense)}",
        f"คงเหลือ : {_format_thb(net)}",
        f"รายการ  : {len(txs)} รายการ",
    ]
    return "\n".join(lines)


def _cmd_balance(user_id: int) -> str:
    return _cmd_summary(user_id)


def _cmd_categories(user_id: int) -> str:
    txs = [t for t in _month_transactions(user_id) if t.amount < 0]
    if not txs:
        return "ยังไม่มีรายจ่ายในเดือนนี้ครับ 🎉"

    cat_map: dict[str, float] = {}
    for t in txs:
        cat_map[t.category] = cat_map.get(t.category, 0) + abs(t.amount)

    icons = {
        "food": "🍜", "transport": "🚗", "shopping": "🛍️",
        "home": "🏠", "entertain": "🎮", "groceries": "🛒",
        "health": "💊", "other": "📦",
    }
    total = sum(cat_map.values())
    lines = ["📂 หมวดหมู่รายจ่ายเดือนนี้:"]
    for cat, amt in sorted(cat_map.items(), key=lambda x: -x[1]):
        pct = amt / total * 100 if total else 0
        icon = icons.get(cat, "📦")
        lines.append(f"{icon} {cat}: {_format_thb(amt)} ({pct:.0f}%)")
    return "\n".join(lines)


def _cmd_analyze(user_id: int) -> str:
    txs = [t for t in _month_transactions(user_id) if t.amount < 0]
    if not txs:
        return "ยังไม่มีข้อมูลเพียงพอสำหรับการวิเคราะห์ครับ"

    cat_map: dict[str, float] = {}
    for t in txs:
        cat_map[t.category] = cat_map.get(t.category, 0) + abs(t.amount)

    top3 = sorted(cat_map.items(), key=lambda x: -x[1])[:3]
    total = sum(cat_map.values())

    advice = {
        "food": "ลองทำอาหารกินเองบ้างอาจช่วยประหยัดได้ครับ 🍳",
        "transport": "พิจารณาขนส่งสาธารณะหรือ carpool ได้ครับ 🚌",
        "shopping": "ลองทำ wish list ก่อนซื้อเพื่อลด impulse buy ครับ 🛍️",
        "entertain": "กำหนด budget ความบันเทิงต่อเดือนจะช่วยได้ครับ 🎯",
        "groceries": "วางแผนเมนูล่วงหน้าช่วยลดของเหลือทิ้งได้ครับ 📋",
        "home": "เปรียบเทียบราคาก่อนซ่อมแซมช่วยประหยัดได้ครับ 🔧",
        "health": "ดูแลสุขภาพป้องกันไว้ก่อนประหยัดกว่าการรักษาครับ 💪",
        "other": "ลองจัดหมวดหมู่รายจ่ายให้ชัดขึ้นเพื่อวิเคราะห์ได้แม่นยำครับ 📊",
    }

    lines = ["🔍 วิเคราะห์การใช้จ่าย:", f"รายจ่ายรวม: {_format_thb(total)}", ""]
    lines.append("Top 3 หมวดที่ใช้มากสุด:")
    for i, (cat, amt) in enumerate(top3, 1):
        pct = amt / total * 100
        lines.append(f"{i}. {cat}: {_format_thb(amt)} ({pct:.0f}%)")

    main_cat = top3[0][0] if top3 else "other"
    lines.append("")
    lines.append("💡 คำแนะนำ:")
    lines.append(advice.get(main_cat, "ติดตามรายจ่ายต่อเนื่องจะช่วยวางแผนได้ดีขึ้นครับ"))
    return "\n".join(lines)


def _cmd_help() -> str:
    return (
        "🤖 MoneyMind Bot — คำสั่งที่ใช้ได้:\n\n"
        "📊 สรุป — สรุปรายรับ/รายจ่ายเดือนนี้\n"
        "💰 ยอด — ยอดรวมรายรับและรายจ่าย\n"
        "📂 เดือนนี้ — แยกหมวดหมู่รายจ่าย\n"
        "🔍 วิเคราะห์ — วิเคราะห์การใช้จ่ายและคำแนะนำ\n"
        "📄 ส่งไฟล์ PDF — อัปโหลด statement อัตโนมัติ\n\n"
        f"🌐 เข้าใช้งานเว็บ:\n{APP_URL}"
    )


# ─── PDF file handler ──────────────────────────────────────────────────────

def _handle_pdf(reply_token: str, message_id: str, user: User) -> None:
    try:
        blob_content = _blob_api().get_message_content(message_id=message_id)
        # blob_content is bytes-like
        if hasattr(blob_content, 'read'):
            pdf_bytes = blob_content.read()
        else:
            pdf_bytes = bytes(blob_content)

        bank, txs = parse_statement(pdf_bytes)

        if not txs:
            _reply(reply_token, "ไม่พบรายการในไฟล์ PDF นี้ครับ\nลองส่งไฟล์ statement จากธนาคารอีกครั้งนะครับ")
            return

        db = SessionLocal()
        try:
            from backend.models import Import as ImportModel
            imp = ImportModel(
                user_id=user.id,
                filename="line_upload.pdf",
                bank=bank,
                count=len(txs),
            )
            db.add(imp)
            db.commit()
            db.refresh(imp)

            rows = []
            for tx in txs:
                rows.append(Transaction(
                    user_id=user.id,
                    source_import_id=imp.id,
                    date=(tx.get("date") or "")[:10],
                    merchant=tx.get("merchant") or "",
                    amount=float(tx.get("amount") or 0),
                    type=tx.get("type") or "",
                    category=tx.get("category") or "other",
                    note=tx.get("note") or "",
                ))
            db.bulk_save_objects(rows)

            # Create notification
            n = Notification(
                user_id=user.id,
                kind="good",
                icon="check",
                title={"th": "นำเข้าสำเร็จ (LINE)", "en": "Import success (LINE)"},
                desc={
                    "th": f"เพิ่ม {len(txs)} รายการจาก {bank.upper()} ผ่าน LINE",
                    "en": f"Added {len(txs)} transactions from {bank.upper()} via LINE",
                },
                unread=True,
            )
            db.add(n)
            db.commit()
        finally:
            db.close()

        bank_name = {"kbank": "กสิกรไทย", "scb": "ไทยพาณิชย์",
                     "ktb": "กรุงไทย", "gsb": "ออมสิน"}.get(bank, bank.upper())
        _reply(
            reply_token,
            f"✅ นำเข้าสำเร็จครับ!\n"
            f"ธนาคาร: {bank_name}\n"
            f"จำนวน: {len(txs)} รายการ\n\n"
            f"พิมพ์ 'สรุป' เพื่อดูยอดได้เลยครับ 📊",
        )

    except Exception as exc:
        log.exception("PDF parse failed for LINE user %s", user.id)
        _reply(reply_token, f"❌ ไม่สามารถอ่านไฟล์ได้ครับ: {exc}\nลองส่งไฟล์ PDF จากธนาคารที่รองรับใหม่นะครับ")


# ─── LINE SDK event handlers ───────────────────────────────────────────────

@handler.add(FollowEvent)
def on_follow(event: FollowEvent):
    """User adds the bot as a friend."""
    line_user_id = event.source.user_id
    display_name = ""
    try:
        profile = _api().get_profile(line_user_id)
        display_name = profile.display_name or ""
    except Exception:
        pass

    _get_or_create_user(line_user_id, display_name)
    _reply(
        event.reply_token,
        f"สวัสดีครับ {display_name or 'คุณ'} 👋\n\n"
        "ยินดีต้อนรับสู่ MoneyMind Bot!\n"
        "ผมช่วยวิเคราะห์การใช้จ่ายของคุณได้ครับ\n\n"
        "พิมพ์ 'ช่วย' เพื่อดูคำสั่งทั้งหมด หรือ\n"
        "ส่งไฟล์ PDF statement มาเลยครับ 📄\n\n"
        f"🌐 เว็บแอป: {APP_URL}",
    )


@handler.add(MessageEvent, message=TextMessageContent)
def on_text(event: MessageEvent):
    line_user_id = event.source.user_id
    text = event.message.text.strip().lower()

    # Try to get profile for display name
    display_name = ""
    try:
        profile = _api().get_profile(line_user_id)
        display_name = profile.display_name or ""
    except Exception:
        pass

    user = _get_or_create_user(line_user_id, display_name)

    COMMANDS = {
        ("สรุป", "summary", "สรุปยอด"): lambda: _cmd_summary(user.id),
        ("ยอด", "balance", "ยอดเงิน"): lambda: _cmd_balance(user.id),
        ("เดือนนี้", "thismonth", "this month", "หมวด", "หมวดหมู่"): lambda: _cmd_categories(user.id),
        ("วิเคราะห์", "analyze", "analyse", "analysis"): lambda: _cmd_analyze(user.id),
        ("ช่วย", "help", "คำสั่ง", "?"): lambda: _cmd_help(),
    }

    for keywords, fn in COMMANDS.items():
        if text in keywords:
            _reply(event.reply_token, fn())
            return

    # Default: suggest help
    _reply(
        event.reply_token,
        "ไม่เข้าใจคำสั่งครับ 😅\nพิมพ์ 'ช่วย' เพื่อดูคำสั่งที่ใช้ได้นะครับ",
    )


@handler.add(MessageEvent, message=FileMessageContent)
def on_file(event: MessageEvent):
    """User sends a file — try to parse as PDF bank statement."""
    file_msg: FileMessageContent = event.message
    line_user_id = event.source.user_id

    display_name = ""
    try:
        profile = _api().get_profile(line_user_id)
        display_name = profile.display_name or ""
    except Exception:
        pass

    user = _get_or_create_user(line_user_id, display_name)

    filename = getattr(file_msg, "file_name", "") or ""
    if not filename.lower().endswith(".pdf"):
        _reply(
            event.reply_token,
            "รองรับเฉพาะไฟล์ PDF ครับ\nส่งไฟล์ statement PDF จากธนาคารได้เลย 📄",
        )
        return

    _reply(event.reply_token, "⏳ กำลังอ่านข้อมูลครับ...")
    _handle_pdf(event.reply_token, file_msg.id, user)

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
import re
from base64 import b64decode
from datetime import datetime, timezone

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessagingApiBlob,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    AudioMessageContent,
    FileMessageContent,
    FollowEvent,
    ImageMessageContent,
    LocationMessageContent,
    MessageEvent,
    StickerMessageContent,
    TextMessageContent,
    VideoMessageContent,
)

from backend.db import SessionLocal
from backend.models import Import, LineUser, Notification, Preference, Transaction, User
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

def _reply(reply_token: str, text, user_id: str | None = None) -> None:
    """Reply with one text message, or a list of texts (up to 5).

    On Render Free tier the container may cold-start (30-60s) before this
    code runs, by which point the LINE reply token has already expired
    (reply tokens are single-use and valid only a few seconds). When
    reply_message fails we fall back to push_message, which needs only the
    user_id and has no token-expiry problem. Pass user_id from
    event.source.user_id to enable the fallback.
    """
    if isinstance(text, str):
        msgs = [TextMessage(text=text)]
    else:
        msgs = [TextMessage(text=t) for t in text[:5]]
    try:
        _api().reply_message(
            ReplyMessageRequest(reply_token=reply_token, messages=msgs)
        )
    except Exception as exc:
        log.exception("reply_message failed (token may be expired): %s", exc)
        if not user_id:
            log.error("No user_id available - cannot fall back to push_message")
            return
        try:
            _api().push_message(
                PushMessageRequest(to=user_id, messages=msgs)
            )
            log.info("Fallback push_message succeeded for user %s", user_id)
        except Exception as push_exc:
            log.exception("Fallback push_message also failed: %s", push_exc)


def _try_get_display_name(line_user_id: str) -> str:
    """Best-effort LINE profile lookup. Returns "" on any failure.

    This is a blocking network call, so call it only when the display name
    is actually needed (e.g. onboarding) - never on the command hot path.
    """
    try:
        profile = _api().get_profile(line_user_id)
        return profile.display_name or ""
    except Exception:
        return ""


# ─── Shared intro / onboarding messages ────────────────────────────────────

def _full_intro(display_name: str = "") -> list[str]:
    """Comprehensive onboarding: welcome + tutorial + commands.

    Returns a list of 2 messages so LINE can show them as separate bubbles
    (better mobile UX than one giant wall of text).
    """
    name = display_name or "คุณ"

    welcome_and_tutorial = (
        f"สวัสดีครับ {name} 👋\n"
        "ยินดีต้อนรับสู่ MoneyMind Bot!\n\n"
        "ผมเป็นผู้ช่วยจัดการการเงินส่วนตัว\n"
        "ช่วย:\n"
        "  ✓ อ่าน Statement PDF อัตโนมัติ\n"
        "  ✓ จัดหมวดหมู่รายจ่ายให้\n"
        "  ✓ สรุป + วิเคราะห์การใช้เงิน\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📖 วิธีใช้ 3 ขั้นตอน\n"
        "━━━━━━━━━━━━━━━\n\n"
        "1️⃣  ดาวน์โหลด Statement PDF\n"
        "      จากแอปธนาคาร → เมนู Statement\n"
        "      ✅ รองรับ:\n"
        "         • กสิกรไทย (K PLUS)\n"
        "         • ไทยพาณิชย์ (SCB Easy)\n"
        "         • กรุงไทย (Krungthai NEXT)\n"
        "         • ออมสิน (MyMo)\n\n"
        "2️⃣  ส่งไฟล์ PDF เข้าแชทนี้\n"
        "      กด ➕ ที่ช่องพิมพ์ → เลือกไฟล์\n"
        "      ผมจะอ่าน + จัดหมวดหมู่ให้อัตโนมัติ ⚡\n\n"
        "3️⃣  ถามผมได้ทุกเรื่อง\n"
        "      พิมพ์คำสั่งดูข้อความถัดไป 👇"
    )

    commands = (
        "🎯 คำสั่ง MoneyMind Bot ที่ใช้ได้\n"
        "━━━━━━━━━━━━━━━\n\n"
        "📊 \"สรุป\"\n"
        "      สรุปยอดรับ-จ่ายเดือนนี้\n\n"
        "💰 \"ยอด\"\n"
        "      ยอดรวมรายรับและรายจ่าย\n\n"
        "📂 \"เดือนนี้\"\n"
        "      แยกหมวดหมู่รายจ่าย\n\n"
        "🔍 \"วิเคราะห์\"\n"
        "      Top 3 หมวด + คำแนะนำประหยัด\n\n"
        "📖 \"วิธีใช้\"\n"
        "      แสดงคู่มือนี้อีกครั้ง\n\n"
        "📄 ส่งไฟล์ PDF\n"
        "      อัปโหลด Statement อัตโนมัติ\n\n"
        "🔗 \"เชื่อม <email>\"\n"
        "      ผูกบัญชี LINE กับเว็บ (ใช้ email ที่ login เว็บ)\n\n"
        "━━━━━━━━━━━━━━━\n"
        f"🌐 เว็บแอป:\n{APP_URL}"
    )

    return [welcome_and_tutorial, commands]


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


def _push(line_user_id: str, text) -> None:
    """Fire-and-forget push to a LINE user (no reply token needed).

    Used by budget alerts which can be triggered from the web (where there is
    no reply token at all). Mirrors the push fallback inside _reply().
    """
    if not line_user_id:
        return
    if isinstance(text, str):
        msgs = [TextMessage(text=text)]
    else:
        msgs = [TextMessage(text=t) for t in text[:5]]
    try:
        _api().push_message(PushMessageRequest(to=line_user_id, messages=msgs))
    except Exception as exc:
        log.exception("push_message failed for %s: %s", line_user_id, exc)


# ─── Account linking (Web ↔ LINE via email) ────────────────────────────────

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _extract_link_email(raw_text: str) -> str | None:
    """Return an email if the message is a link request, else None.

    Accepts:  "เชื่อม you@mail.com" / "link you@mail.com" / a bare email.
    Ignores LINE's own fake addresses (line_<id>@line.local) so a user can't
    re-link themselves into the auto-account.
    """
    m = _EMAIL_RE.search(raw_text or "")
    if not m:
        return None
    email = m.group(0).strip().lower()
    if email.endswith("@line.local"):
        return None
    return email


def _link_account(line_user_id: str, email: str) -> str:
    """Link this LINE account to an existing web User (by email).

    Security guard (P0): only emails that already have a User row (i.e. the
    person has logged into the web app at least once) can be linked. We never
    create a new web account here.

    On success we MOVE the LINE auto-user's existing data (transactions,
    imports, notifications) onto the web user so nothing is lost, then point
    LineUser.user_id at the web user.
    """
    db = SessionLocal()
    # Track whether linking actually succeeded so we can fire budget alerts
    # AFTER the DB session is fully closed (mirrors the _handle_pdf pattern).
    linked_user_id: int | None = None
    try:
        target = db.query(User).filter_by(email=email).first()
        if target is None:
            return (
                "ไม่พบบัญชีนี้ครับ 🙏\n"
                f"({email})\n"
                "กรุณาเข้าเว็บแล้ว login ด้วย email นี้ก่อน\n"
                "แล้วพิมพ์ \"เชื่อม <email>\" อีกครั้งนะครับ\n\n"
                f"🌐 {APP_URL}"
            )

        lu = db.query(LineUser).filter_by(line_user_id=line_user_id).first()
        if lu is None:
            # No LineUser row yet — create one pointing straight at the target.
            lu = LineUser(
                line_user_id=line_user_id,
                user_id=target.id,
                display_name=_try_get_display_name(line_user_id),
                linked_at=datetime.now(timezone.utc),
            )
            db.add(lu)
            db.commit()
            linked_user_id = target.id
            return _link_success_msg(email)

        if lu.user_id == target.id:
            return (
                f"บัญชีนี้เชื่อมกับ {email} อยู่แล้วครับ ✅\n"
                "ข้อมูล LINE กับเว็บเป็นชุดเดียวกันอยู่แล้ว"
            )

        old_user_id = lu.user_id

        # Fetch the old user first so we can decide whether moving data is safe.
        old_user = db.query(User).filter_by(id=old_user_id).first()
        is_auto_user = (
            old_user is not None
            and old_user.email.endswith("@line.local")
            and old_user.id != target.id
        )

        moved_tx = 0
        if is_auto_user:
            # Old user is the throwaway LINE auto-account (@line.local) → it only
            # holds data that came in via LINE before linking, so it's safe to
            # MOVE that data onto the target web user, then delete the orphan.
            moved_tx = db.query(Transaction).filter_by(user_id=old_user_id).update(
                {"user_id": target.id}, synchronize_session=False
            )
            db.query(Import).filter_by(user_id=old_user_id).update(
                {"user_id": target.id}, synchronize_session=False
            )
            db.query(Notification).filter_by(user_id=old_user_id).update(
                {"user_id": target.id}, synchronize_session=False
            )
            # Clean up the orphaned auto-user (and its preference) so it doesn't
            # linger. Only the throwaway LINE-local account is ever deleted here.
            db.query(Preference).filter_by(user_id=old_user_id).delete(
                synchronize_session=False
            )
            db.delete(old_user)
        # else: old user is a real web account (normal email) — DO NOT move or
        # delete anything. Account A keeps all of its own data; we only re-point
        # the LINE mapping to B below (latest explicit link wins).

        # Re-point the LINE mapping to the web user (always, both cases).
        lu.user_id = target.id
        lu.linked_at = datetime.now(timezone.utc)

        db.commit()
        log.info(
            "Linked LINE %s → user_id=%s (%s), moved %s txs from old user_id=%s",
            line_user_id, target.id, email, moved_tx, old_user_id,
        )
        linked_user_id = target.id
        return _link_success_msg(email)
    except Exception as exc:
        db.rollback()
        log.exception("Account link failed for %s → %s", line_user_id, email)
        return f"❌ เชื่อมบัญชีไม่สำเร็จครับ: {exc}\nลองใหม่อีกครั้งนะครับ"
    finally:
        db.close()
        # Fire budget alerts only after the link session is closed, so
        # _push_budget_alerts can open its own clean session. Any failure here
        # must NOT mask the success message already queued for return.
        if linked_user_id is not None:
            try:
                _push_budget_alerts(linked_user_id)
            except Exception:
                log.exception(
                    "budget alert after LINE link failed (user_id=%s)",
                    linked_user_id,
                )


def _link_success_msg(email: str) -> str:
    return (
        "เชื่อมบัญชีสำเร็จ! ✅\n"
        f"({email})\n"
        "ตอนนี้ข้อมูลใน LINE กับเว็บเป็นชุดเดียวกันแล้วครับ\n\n"
        "💡 ตั้งงบในเว็บไว้ → ถ้าใช้เกินงบ ผมจะเตือนใน LINE ให้เลย"
    )


# ─── Budget alerts ──────────────────────────────────────────────────────────

_CAT_TH = {
    "food": "อาหาร", "transport": "เดินทาง", "shopping": "ช้อปปิ้ง",
    "home": "ที่พัก/บ้าน", "entertain": "บันเทิง", "groceries": "ของใช้",
    "health": "สุขภาพ", "other": "อื่นๆ",
}


def _push_budget_alerts(user_id: int) -> None:
    """Check this user's current-month spending vs their category budgets and
    push a LINE alert for any category that is over budget.

    Silent no-op when: the user has no linked LINE account, no budgets set, or
    nothing is over. Safe to call from both the LINE PDF flow and the web
    bulk-insert route.
    """
    db = SessionLocal()
    try:
        lu = db.query(LineUser).filter_by(user_id=user_id).first()
        if lu is None:
            return  # not linked to LINE → nothing to push

        pref = db.query(Preference).filter_by(user_id=user_id).first()
        budgets = (pref.category_budgets if pref else None) or {}
        if not budgets:
            return  # no budgets configured

        now = datetime.now(timezone.utc)
        prefix = now.strftime("%Y-%m")
        txs = (
            db.query(Transaction)
            .filter(
                Transaction.user_id == user_id,
                Transaction.date.like(f"{prefix}%"),
                Transaction.amount < 0,
            )
            .all()
        )
        spent: dict[str, float] = {}
        for t in txs:
            spent[t.category] = spent.get(t.category, 0) + abs(t.amount)

        over_lines: list[str] = []
        for cat, budget in budgets.items():
            try:
                budget = float(budget)
            except (TypeError, ValueError):
                continue
            if budget <= 0:
                continue
            used = spent.get(cat, 0)
            if used > budget:
                name = _CAT_TH.get(cat, cat)
                over_lines.append(
                    f"• {name}: ใช้ {_format_thb(used)} / งบ {_format_thb(budget)} "
                    f"(เกิน {_format_thb(used - budget)})"
                )

        if not over_lines:
            return

        msg = (
            "⚠️ แจ้งเตือนใช้เกินงบเดือนนี้\n"
            "━━━━━━━━━━━━━━━\n"
            + "\n".join(over_lines)
            + "\n\nลองดู \"วิเคราะห์\" เพื่อหาวิธีประหยัดครับ 💡"
        )
        line_user_id = lu.line_user_id
    finally:
        db.close()

    # Push outside the DB session (network call).
    _push(line_user_id, msg)


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
        "📄 ส่งไฟล์ PDF — อัปโหลด statement อัตโนมัติ\n"
        "🔗 เชื่อม <email> — ผูกบัญชี LINE กับเว็บ\n"
        "📖 วิธีใช้ — คู่มือใช้งานแบบละเอียด\n\n"
        f"🌐 เข้าใช้งานเว็บ:\n{APP_URL}"
    )


def _cmd_tutorial() -> str:
    """Step-by-step tutorial for new users."""
    return (
        "📖 วิธีใช้ MoneyMind Bot\n"
        "━━━━━━━━━━━━━━━\n\n"
        "1️⃣  ดาวน์โหลด Statement PDF\n"
        "      เปิดแอปธนาคาร → เมนู Statement\n"
        "      เลือกเดือนที่ต้องการ → ดาวน์โหลด PDF\n\n"
        "      ✅ ธนาคารที่รองรับ:\n"
        "         • กสิกรไทย (K PLUS)\n"
        "         • ไทยพาณิชย์ (SCB Easy)\n"
        "         • กรุงไทย (Krungthai NEXT)\n"
        "         • ออมสิน (MyMo)\n\n"
        "2️⃣  ส่งไฟล์ PDF เข้าแชทนี้\n"
        "      กด ➕ ที่ช่องพิมพ์ → เลือกไฟล์\n"
        "      ผมจะอ่าน + จัดหมวดหมู่ให้อัตโนมัติ ⚡\n\n"
        "3️⃣  ถามผมได้ทุกเรื่อง\n"
        "      💬 \"สรุป\" → ดูยอดเดือนนี้\n"
        "      💬 \"เดือนนี้\" → แยกหมวดหมู่\n"
        "      💬 \"วิเคราะห์\" → คำแนะนำประหยัด\n\n"
        "━━━━━━━━━━━━━━━\n"
        "💡 Tip: พิมพ์ \"ช่วย\" ดูคำสั่งทั้งหมด\n\n"
        f"🌐 เว็บแอป:\n{APP_URL}"
    )


# ─── PDF file handler ──────────────────────────────────────────────────────

def _handle_pdf(reply_token: str, message_id: str, user: User,
                line_user_id: str | None = None) -> None:
    try:
        blob_content = _blob_api().get_message_content(message_id=message_id)
        # blob_content is bytes-like
        if hasattr(blob_content, 'read'):
            pdf_bytes = blob_content.read()
        else:
            pdf_bytes = bytes(blob_content)

        bank, txs = parse_statement(pdf_bytes)

        if not txs:
            _reply(reply_token, "ไม่พบรายการในไฟล์ PDF นี้ครับ\nลองส่งไฟล์ statement จากธนาคารอีกครั้งนะครับ", user_id=line_user_id)
            return

        # Lazy import to avoid the circular: app.py imports line_bot for the
        # webhook route, so importing app at module load would break startup.
        from backend.app import _dedup_build_rows

        created = 0
        skipped = 0
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

            rows, skipped = _dedup_build_rows(db, user.id, txs, imp.id)
            created = len(rows)
            if rows:
                db.bulk_save_objects(rows)

            # Reflect the actually-inserted count on the Import audit row so
            # the imports list doesn't lie about how much was added.
            imp.count = created

            # Create notification — describe what actually landed in DB.
            if created > 0:
                desc_th = f"เพิ่ม {created} รายการจาก {bank.upper()} ผ่าน LINE"
                desc_en = f"Added {created} transactions from {bank.upper()} via LINE"
                if skipped:
                    desc_th += f" (ข้ามซ้ำ {skipped})"
                    desc_en += f" (skipped {skipped} duplicates)"
                title = {"th": "นำเข้าสำเร็จ (LINE)", "en": "Import success (LINE)"}
                kind = "good"
            else:
                desc_th = f"ไม่มีรายการใหม่ — ข้ามซ้ำทั้งหมด {skipped} รายการ"
                desc_en = f"No new transactions — {skipped} duplicates skipped"
                title = {"th": "ไม่มีรายการใหม่ (LINE)", "en": "No new transactions (LINE)"}
                kind = "info"

            n = Notification(
                user_id=user.id,
                kind=kind,
                icon="check" if created > 0 else "bell",
                title=title,
                desc={"th": desc_th, "en": desc_en},
                unread=True,
            )
            db.add(n)
            db.commit()
        finally:
            db.close()

        # Only push budget alerts when we actually added new spending — if
        # everything was a duplicate, monthly totals didn't change.
        if created > 0:
            try:
                _push_budget_alerts(user.id)
            except Exception:
                log.exception("budget alert after LINE PDF import failed")

        bank_name = {"kbank": "กสิกรไทย", "scb": "ไทยพาณิชย์",
                     "ktb": "กรุงไทย", "gsb": "ออมสิน"}.get(bank, bank.upper())

        if created > 0:
            dup_line = f"\nข้ามรายการซ้ำ: {skipped} รายการ" if skipped else ""
            _reply(
                reply_token,
                f"✅ นำเข้าสำเร็จครับ!\n"
                f"ธนาคาร: {bank_name}\n"
                f"จำนวน: {created} รายการ"
                f"{dup_line}\n\n"
                f"━━━━━━━━━━━━━━━\n"
                f"ลองพิมพ์ดูครับ:\n"
                f"  📊 \"สรุป\" — ดูยอดรับ-จ่าย\n"
                f"  📂 \"เดือนนี้\" — แยกหมวดหมู่\n"
                f"  🔍 \"วิเคราะห์\" — คำแนะนำประหยัด",
                user_id=line_user_id,
            )
        else:
            _reply(
                reply_token,
                f"ℹ️ ไฟล์นี้เคยนำเข้าแล้วครับ\n"
                f"ธนาคาร: {bank_name}\n"
                f"ข้ามรายการซ้ำทั้งหมด: {skipped} รายการ\n\n"
                f"ลองพิมพ์ \"สรุป\" เพื่อดูยอดเดิมได้เลย",
                user_id=line_user_id,
            )

    except Exception as exc:
        log.exception("PDF parse failed for LINE user %s", user.id)
        _reply(reply_token, f"❌ ไม่สามารถอ่านไฟล์ได้ครับ: {exc}\nลองส่งไฟล์ PDF จากธนาคารที่รองรับใหม่นะครับ", user_id=line_user_id)


# ─── LINE SDK event handlers ───────────────────────────────────────────────

@handler.add(FollowEvent)
def on_follow(event: FollowEvent):
    """User adds the bot as a friend."""
    line_user_id = event.source.user_id
    # On follow we DO want the real display name (only chance to capture it
    # for new accounts), so the profile lookup here is justified.
    display_name = _try_get_display_name(line_user_id)

    _get_or_create_user(line_user_id, display_name)
    # Send full intro: welcome + tutorial + commands (as 2 bubbles)
    _reply(event.reply_token, _full_intro(display_name), user_id=line_user_id)


@handler.add(MessageEvent, message=TextMessageContent)
def on_text(event: MessageEvent):
    line_user_id = event.source.user_id
    raw_text = event.message.text.strip()
    text = raw_text.lower()

    # Account linking: "เชื่อม <email>" / "link <email>" / a bare email.
    # Handled before commands so an email message never falls through to the
    # generic intro. Use raw_text so the email keeps its original casing for
    # the regex (we lowercase the email inside _extract_link_email anyway).
    link_email = _extract_link_email(raw_text)
    if link_email is not None:
        _reply(event.reply_token, _link_account(line_user_id, link_email),
               user_id=line_user_id)
        return

    # NOTE: do NOT call get_profile() here. It's a blocking network call that
    # adds latency on the command hot path. On Render Free cold-starts every
    # millisecond counts before the reply token expires. Commands below don't
    # need the display name; _get_or_create_user only uses it when creating a
    # brand-new account (existing users are returned without touching the
    # name), and the _full_intro fallback fetches the profile lazily.
    user = _get_or_create_user(line_user_id, "")

    COMMANDS = {
        ("สรุป", "summary", "สรุปยอด"): lambda: _cmd_summary(user.id),
        ("ยอด", "balance", "ยอดเงิน"): lambda: _cmd_balance(user.id),
        ("เดือนนี้", "thismonth", "this month", "หมวด", "หมวดหมู่"): lambda: _cmd_categories(user.id),
        ("วิเคราะห์", "analyze", "analyse", "analysis"): lambda: _cmd_analyze(user.id),
        ("ช่วย", "help", "คำสั่ง", "?"): lambda: _cmd_help(),
        ("วิธีใช้", "เริ่ม", "เริ่มต้น", "tutorial", "guide", "start", "เริ่มใช้งาน"): lambda: _cmd_tutorial(),
    }

    for keywords, fn in COMMANDS.items():
        if text in keywords:
            _reply(event.reply_token, fn(), user_id=line_user_id)
            return

    # Unknown message → send the full intro (welcome + tutorial + commands)
    # so users always see how to use the bot regardless of what they type.
    # Only here do we need the display name, so fetch it lazily off the
    # command hot path.
    display_name = _try_get_display_name(line_user_id)
    _reply(event.reply_token, _full_intro(display_name), user_id=line_user_id)


@handler.add(MessageEvent, message=FileMessageContent)
def on_file(event: MessageEvent):
    """User sends a file — try to parse as PDF bank statement."""
    file_msg: FileMessageContent = event.message
    line_user_id = event.source.user_id

    # PDF handling does not need the display name → skip get_profile() here.
    user = _get_or_create_user(line_user_id, "")

    filename = getattr(file_msg, "file_name", "") or ""
    if not filename.lower().endswith(".pdf"):
        _reply(
            event.reply_token,
            "รองรับเฉพาะไฟล์ PDF ครับ\nส่งไฟล์ statement PDF จากธนาคารได้เลย 📄",
            user_id=line_user_id,
        )
        return

    _reply(event.reply_token, "⏳ กำลังอ่านข้อมูลครับ...", user_id=line_user_id)
    _handle_pdf(event.reply_token, file_msg.id, user, line_user_id=line_user_id)


# ─── Fallback handlers — sticker, image, video, audio, location ────────────
# When user sends non-text, non-file content, still reply with the intro so
# they understand how to use the bot instead of seeing the bot stay silent.

def _generic_intro_reply(event: MessageEvent) -> None:
    line_user_id = event.source.user_id
    display_name = _try_get_display_name(line_user_id)
    _get_or_create_user(line_user_id, display_name)
    _reply(event.reply_token, _full_intro(display_name), user_id=line_user_id)


@handler.add(MessageEvent, message=StickerMessageContent)
def on_sticker(event: MessageEvent):
    _generic_intro_reply(event)


@handler.add(MessageEvent, message=ImageMessageContent)
def on_image(event: MessageEvent):
    line_user_id = event.source.user_id
    display_name = _try_get_display_name(line_user_id)
    _get_or_create_user(line_user_id, display_name)
    # Hint: images of statements need to be PDF, not photo
    _reply(event.reply_token, [
        "ขออภัยครับ รูปภาพยังไม่รองรับ 📷\n"
        "กรุณาส่งเป็นไฟล์ PDF จากแอปธนาคารแทนนะครับ 📄",
        *_full_intro(display_name),
    ], user_id=line_user_id)


@handler.add(MessageEvent, message=VideoMessageContent)
def on_video(event: MessageEvent):
    _generic_intro_reply(event)


@handler.add(MessageEvent, message=AudioMessageContent)
def on_audio(event: MessageEvent):
    _generic_intro_reply(event)


@handler.add(MessageEvent, message=LocationMessageContent)
def on_location(event: MessageEvent):
    _generic_intro_reply(event)

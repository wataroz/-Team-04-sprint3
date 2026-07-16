"""
MoneyMind — Bank statement PDF parser (Python port of src/pdf-parser.js).

Supports:
    - K-Bank (กสิกร)
    - GSB (ออมสิน)
    - KTB (กรุงไทย)
    - SCB (ไทยพาณิชย์)

Uses pdfplumber for text extraction. The text-extraction step groups items by
Y coordinate then sorts by X, mirroring the JS implementation.
"""

from __future__ import annotations

import io
import logging
import re
import time
from typing import Iterable

import pdfplumber

from logic_ai.seed_merchants import AMBIGUOUS_SEED_KEYS, SEED_MERCHANTS

try:
    from pdfminer.pdfdocument import PDFPasswordIncorrect
except ImportError:
    # pdfminer.six may rename/move this class in future versions.
    # Fall back to a private sentinel class so `isinstance()` checks below
    # never crash; password-error detection then degrades to the message
    # sniffing layer inside `_is_password_error()`.
    class PDFPasswordIncorrect(Exception):  # type: ignore[no-redef]
        """Fallback sentinel — real class missing from this pdfminer version."""


log = logging.getLogger(__name__)


# ============================================================
# Password error detection (รหัส PDF)
# ------------------------------------------------------------
# ธนาคารบางเจ้าส่ง statement เป็น PDF ที่ล็อกรหัส (เช่น เลขบัตร ปชช.
# 4 ตัวท้าย / วันเกิด). pdfminer โยน error ต่างรูปแบบกันตามเวอร์ชัน
# เราจึงตรวจหลายชั้น (isinstance → __cause__ → args → sniff ข้อความ)
# เพื่อให้แยกได้ว่า "ติดรหัสแต่ยังไม่ใส่" กับ "ใส่รหัสผิด" แล้วบอก user
# เป็นภาษาไทย. ห้าม log ค่ารหัสเด็ดขาด (อ่านแค่ข้อความ exception).
# ============================================================

# Substrings (lowercase) used to detect password errors when the real
# pdfminer class is unavailable or wrapped in a generic exception.
# Each tuple = AND-group; any tuple matching → password error.
_PASSWORD_ERROR_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("pdfpasswordincorrect",),
    ("password", "incorrect"),
    ("password", "invalid"),
    ("password", "wrong"),
    ("password", "required"),
)


def _is_password_error(exc: BaseException) -> bool:
    """True if ``exc`` (or any wrapped cause/arg) signals a PDF password error.

    Detection layers (in order):
        1. ``isinstance(exc, PDFPasswordIncorrect)``
        2. ``__cause__`` chain
        3. ``exc.args`` scan for wrapped instances
        4. **String sniff** — last-resort message inspection, robust against
           pdfminer renaming/moving the class in future versions.

    pdfplumber 0.11.x wraps pdfminer's PDFPasswordIncorrect in its own
    ``PdfminerException`` and stores the original as the first positional
    arg (not ``__cause__``), so we sniff both spots.
    """
    if isinstance(exc, PDFPasswordIncorrect):
        return True
    if exc.__cause__ and isinstance(exc.__cause__, PDFPasswordIncorrect):
        return True
    for a in getattr(exc, "args", ()) or ():
        if isinstance(a, PDFPasswordIncorrect):
            return True
    # Layer 4: degrade gracefully — sniff the exception class name + message.
    # Never logs or reads the password value itself; only the exception text.
    try:
        haystack = (type(exc).__name__ + " " + str(exc)).lower()
    except Exception:
        return False
    for group in _PASSWORD_ERROR_PATTERNS:
        if all(token in haystack for token in group):
            return True
    return False


# ============================================================
# Text extraction (ดึงข้อความจาก PDF)
# ------------------------------------------------------------
# หัวใจของ parser: pdfplumber ให้ "คำ" พร้อมพิกัด (x,y) มา เราจับกลุ่ม
# คำที่อยู่บรรทัดเดียวกันด้วยพิกัด Y (ปัดเศษ) แล้วเรียงซ้าย→ขวาด้วย X
# เพื่อประกอบกลับเป็นบรรทัดข้อความ (เลียนแบบ layout ของ pdf.js ฝั่ง JS).
# statement ไทยมักปนเลขไทย/อังกฤษ + ช่องว่างเพี้ยน → normalize \s+ เป็น
# ช่องว่างเดียวก่อนเสมอ. NOTE: PDF ที่เป็นภาพสแกน pdfplumber อ่านไม่ออก
# → จะได้ข้อความว่าง (parser คืน list ว่าง ไม่ crash).
# ============================================================

def extract_pdf_text(file_bytes: bytes, password: str | None = None) -> str:
    """Extract text from PDF, line-grouped by Y coordinate (matches pdf.js layout).

    Supports password-protected PDFs via the ``password`` parameter, which is
    forwarded to ``pdfplumber.open``. The password value is never logged.

    Raises:
        ValueError: ``"PDF นี้ติดรหัส — กรุณาใส่รหัส"`` if the PDF is encrypted
            but no password was supplied; ``"รหัส PDF ไม่ถูกต้อง"`` if the
            supplied password does not unlock the PDF.
    """
    out: list[str] = []
    try:
        pdf_ctx = pdfplumber.open(io.BytesIO(file_bytes), password=password or "")
    except Exception as e:
        # pdfminer raises PDFPasswordIncorrect for both the "encrypted but no
        # password supplied" and the "wrong password" cases. Distinguish via
        # the caller-supplied ``password`` arg so the user message is useful.
        if _is_password_error(e):
            if not password:
                raise ValueError("PDF นี้ติดรหัส — กรุณาใส่รหัส")
            raise ValueError("รหัส PDF ไม่ถูกต้อง")
        raise

    with pdf_ctx as pdf:
        # Guard: กัน worker timeout/OOM จาก PDF เล่มยักษ์
        if len(pdf.pages) > 50:
            raise ValueError("PDF เกิน 50 หน้า — กรุณาแยกไฟล์")
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            log.info("extract page %d/%d start", page_num, total_pages)
            t0 = time.perf_counter()
            # extract_words = ดึง "คำ" ทีละคำพร้อมพิกัด (x0 = ขอบซ้าย, top = ขอบบน).
            # x_tolerance/y_tolerance = 2 → คำที่ห่างกัน ≤ 2px ถือว่าอยู่ติดกัน/
            # บรรทัดเดียวกัน (เผื่อสระ-วรรณยุกต์ไทยทำให้ระยะเพี้ยนเล็กน้อย).
            # keep_blank_chars=False = ทิ้งช่องว่างเปล่า, use_text_flow=False =
            # ไม่เชื่ออันดับการอ่านจากไฟล์ (จัดเรียงเองด้วยพิกัดด้านล่างแทน).
            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=2,
                keep_blank_chars=False,
                use_text_flow=False,
            )
            duration = time.perf_counter() - t0
            log.info(
                "extract page %d done: %d words, %.2fs",
                page_num, len(words), duration,
            )
            # จับกลุ่มคำเป็น "บรรทัด" ด้วยพิกัด Y: round(top) ปัดเศษให้คำที่อยู่
            # ระดับเดียวกัน (ต่างกันแค่เศษ px) ตกลง key เดียวกัน. dict นี้ =
            # {ค่า y : [(x0, ข้อความ), ...]}. setdefault สร้าง list ว่างถ้ายังไม่มี key.
            lines: dict[int, list[tuple[float, str]]] = {}
            for w in words:
                y = round(w["top"])
                lines.setdefault(y, []).append((w["x0"], w["text"]))
            # ไล่ทีละบรรทัดจากบนลงล่าง (sorted keys) → ในบรรทัดเรียงคำซ้าย→ขวา
            # ด้วย x0 → ต่อเป็นสตริงเดียว. re.sub(r"\s+", " ", ...) = normalize
            # ช่องว่าง (ยุบ space/tab/ซ้อนหลายตัวให้เหลือช่องเดียว) กัน layout เพี้ยน.
            for y in sorted(lines.keys()):
                items = sorted(lines[y], key=lambda t: t[0])
                line = re.sub(r"\s+", " ", " ".join(t[1] for t in items)).strip()
                if line:
                    out.append(line)
            out.append("")
    return "\n".join(out)


# ============================================================
# Bank detection (ระบุว่าเป็น statement ธนาคารไหน)
# ------------------------------------------------------------
# ต้อง deterministic เสมอ — จับด้วย keyword เฉพาะจากหัวกระดาษ (1000
# ตัวอักษรแรก) ของแต่ละธนาคาร (ชื่อธนาคารไทย/อังกฤษ + ชื่อระบบ เช่น
# K PLUS, MyMo). ห้ามใช้ random/LLM เด็ดขาด เพราะผลต้องคงที่ทุกครั้ง.
# ลำดับการเช็ก: SCB → KTB → GSB → KBank; keyword แต่ละเจ้าไม่ทับกัน
# จึงไม่กำกวม. ไม่เข้าเงื่อนไขใด → "unknown" (ปล่อยให้ fallback ลองทุก
# parser ใน parse_statement).
# ============================================================

def detect_bank(text: str) -> str:
    # head = 1000 ตัวอักษรแรกพอ (keyword ชื่อธนาคารอยู่หัวกระดาษเสมอ + เร็วกว่า
    # สแกนทั้งเล่ม). re.search หาที่ไหนก็ได้ในสตริง, `|` = "หรือ" (จับตัวใดตัวหนึ่ง),
    # re.I = IGNORECASE ไม่สนตัวพิมพ์เล็ก/ใหญ่ (BANK = bank).
    head = text[:1000]
    if re.search(r"ธนาคารไทยพาณิชย์|THE SIAM COMMERCIAL BANK|STATEMENT OF SAVING ACCOUNT", head, re.I):
        return "scb"
    if re.search(r"กรุงไทย|Krungthai|รายการบัญชีระหว่างวันที่", head, re.I):
        return "ktb"
    if re.search(r"เดินบัญชีเงินฝาก|ออมสิน|Government Savings Bank|MyMo Transfer|C Scan B Transaction", head, re.I):
        return "gsb"
    if re.search(r"กสิกรไทย|KBPDF|K PLUS|MAKE by KBank", head, re.I):
        return "kbank"
    return "unknown"


# ============================================================
# Category inference (จัดหมวดอัตโนมัติ)
# ------------------------------------------------------------
# _CATEGORY_RULES เป็น list เรียงลำดับของ (หมวด, regex) — "แมตช์ตัวแรก
# ชนะ" ดังนั้น "ลำดับ = ความสำคัญ" ห้ามสลับมั่ว. เหตุผลของลำดับ:
#   health → food → transport → entertain → home → groceries → shopping
#   - health มาก่อน groceries: ร้านยา (เช่น วัตสัน/บูทส์) ขายของชำด้วย
#     ถ้าไม่ดักก่อนจะโดน groceries กลืน → จัดเป็น "สุขภาพ" ถูกกว่า
#   - food มาก่อน transport: food-delivery หลายเจ้าใช้แบรนด์เดียวกับ
#     ride-hailing (เช่น "Grab Food" vs "Grab") → ต้องดัก *Food ก่อน
#     ไม่งั้นไปตกหมวดเดินทาง
#   - groceries มาก่อน shopping: ร้านสะดวกซื้อ/ซูเปอร์ทับกับคำ generic
#     ("market"/"store") ที่ shopping จับ → ให้ตัวเฉพาะกว่าชนะก่อน
# สัญญา (contract): 8 หมวดนี้ผูกกับ frontend/data.js + DB — ห้ามเพิ่ม/ลบ
# หมวดในไฟล์นี้คนเดียว ต้องคุยกับ ACHI/AJ ก่อน. กำกวม → ตกไป "other".
# ============================================================

# Ordered list of (category, regex) pairs. First match wins, so put more
# specific / higher-priority patterns first (e.g. health before groceries so
# Watsons/Boots don't get mis-tagged, food-delivery before ride-hailing).
#
# Notes:
#   - Patterns are compiled with re.IGNORECASE; we lowercase + strip extras
#     before matching so both Thai and English work.
#   - Use _LB/_RB boundaries on short English tokens to avoid false positives
#     (see rationale below — NOT plain \b).
#   - 8-category contract shared with frontend/data.js — DO NOT add/remove
#     categories here without coordinating with the frontend.

# ------------------------------------------------------------
# Custom English-only boundary (asymmetric boundary gap fix, 16 ก.ค. 2026)
# ------------------------------------------------------------
# Plain `\b` treats Thai script as a Unicode word character in Python's `re`
# (it isn't ASCII-only), so `\b` right next to Thai text is *inconsistent*:
# verified by running actual `re.search()` calls (not guessed — see team
# lesson about not trusting "looks like a boundary bug" without testing):
#   \bcentral\b vs "CENTRALเวิลด์"     -> NOT matched (เ is a Thai letter = \w)
#   \btops\b    vs "ซื้อของที่TOPS"     -> matched   (ที่'s last glyph, the ่
#                                                     tone mark, is a Unicode
#                                                     *combining mark* — NOT
#                                                     \w — so a boundary
#                                                     exists there "by luck")
#   \btops\b    vs "TOPSมาร์เก็ต"       -> NOT matched (ม is a Thai letter = \w)
#   \blawson\b  vs "LAWSON108"         -> NOT matched (digits are \w too, in
#                                                     any regex flavor)
# So whether an English brand keyword matches next to Thai text depends on
# the accident of which Thai glyph sits next to it, and digit-glued branch
# numbers (e.g. "LAWSON108") never match at all. Both are silent "other"
# fallbacks for real merchant strings — bad for coverage but never crashes
# (safe fallback contract still holds).
#
# Fix: stop relying on \w-based \b entirely for these tokens. Define the
# boundary ourselves in terms of ASCII letters only. Anything that is NOT
# an ASCII letter — digit, punctuation, whitespace, or Thai script — now
# counts as a valid edge on that side, in both directions, consistently.
# This closes the coverage gap (LAWSON108, CENTRALเวิลด์, TOPSมาร์เก็ต all
# match now) while still rejecting keyword-inside-another-English-word
# false positives (e.g. "topspin", "bootstrap", "centralize", "bnhx99")
# because ASCII-letter-to-ASCII-letter adjacency still blocks the match on
# that side exactly like \b did. Locked in by the regression suite in
# test_parser.ipynb §12/§13 (false-positive set + true-positive set +
# new asymmetric-gap set all pass).
_LB = r"(?<![a-zA-Z])"  # left edge: previous char must not be an ASCII letter
_RB = r"(?![a-zA-Z])"   # right edge: next char must not be an ASCII letter

_CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    # Health & pharmacy (priority over groceries so Watsons/Boots win)
    (
        "health",
        # จับ: ร้านยา/โรงพยาบาล/คลินิก/ประกันสุขภาพ (ทั้งอังกฤษและไทย).
        # ตัวอย่างที่ match: "ร้านยาตัวอย่าง", "คลินิกทันตกรรม", "hospital".
        # _LB/_RB = ขอบคำแบบ ASCII-letter-only (ดูคำอธิบายเต็มด้านบน
        # _CATEGORY_RULES) — กันคำสั้นอังกฤษไปโดนกลางคำอื่นโดยบังเอิญ (เช่น
        # "bootstrap") โดยไม่พลาดเคสที่ติดไทย/เลขไม่มีช่องว่าง (เช่น "BOOTSสาขา").
        # ฝั่งไทยไม่ใส่ boundary เพราะอักษรไทยไม่มีขอบคำแบบ ASCII อยู่แล้ว.
        re.compile(
            _LB + r"(watsons?|boots|pharmacy|drug\s*store|hospital|clinic|dental|"
            r"bumrungrad|samitivej|bnh|bangkok\s*hospital|mahidol|rama|"
            r"siriraj|chula|aia|allianz|axa|prudential|insurance)" + _RB + r"|"
            r"วัตสัน|บูทส์|ร้านยา|ยา\s|โรงพยาบาล|รพ\.|คลินิก|ทันต|"
            r"บำรุงราษฎร์|สมิติเวช|รามา(?:ธิบดี)?|ศิริราช|จุฬา|ประกัน(?:สุขภาพ|ชีวิต)?",
            re.IGNORECASE,
        ),
    ),

    # Food delivery & food-court / restaurants / cafes (must come before
    # transport so "Bolt Food", "Grab Food", "Lineman" land in food)
    (
        "food",
        # จับ: ฟู้ดเดลิเวอรี/ร้านอาหาร/คาเฟ่/เครื่องดื่ม.
        # ตัวอย่าง: "ร้านอาหารตัวอย่าง", "กาแฟเย็น", "grab food".
        # บรรทัด "เซเว่น(?=.*(?:ร้าน|อาหาร))" = lookahead (?=...) จับ "เซเว่น"
        # เฉพาะเมื่อมีคำว่า ร้าน/อาหาร ตามหลัง กัน 7-11 ทั่วไปหลุดมาเป็น food
        # (ปกติ 7-11 ต้องตกหมวด groceries).
        re.compile(
            _LB + r"(grab\s*food|grabfood|food\s*panda|foodpanda|line\s*man|lineman|"
            r"robinhood|bolt\s*food|wongnai|food\s*court|"
            r"starbucks|café|cafe|coffee|amazon|mcdonald'?s?|mcdo|kfc|burger\s*king|"
            r"pizza(?:\s*hut|\s*company)?|sushi|ramen|noodle|"
            r"after\s*you|dessert|bingsu|bakery|donut|krispy|swensen'?s?|"
            r"shabu|sukishi|mk\s*restaurant|mk\s*gold|mk\s*live|hotpot|yakiniku|"
            r"texas\s*chicken|bonchon|chester'?s?|santa\s*fe|s&p|sizzler|"
            r"smoothie|juice\s*bar)" + _RB + r"|"
            r"กาแฟ(?:เย็น|สด|ดำ|โบราณ|นม)?|อะเมซอน|อเมซอน|สตาร์บัค|เคเอฟซี|แมค|"
            r"เบเกอรี่|เค้ก|โดนัท|ขนมปัง|บิงซู|ลูกชิ้น|ปิ้งย่าง|"
            r"ร้านอาหาร|อาหาร(?:ตามสั่ง|จานเดียว)?|กระเพรา|กะเพรา|ส้มตำ|"
            r"ก๋วยเตี๋ยว(?:เรือ)?|สุกี้|ชาบู|หม่าล่า|ราเมง|ราเมน|ข้าวมันไก่|ข้าวขาหมู|"
            r"ข้าวแกง|ผัดไทย|ผัดซีอิ๊ว|ราดหน้า|โจ๊ก|ก๋วยจั๊บ|"
            r"ขนมจีน|เย็นตาโฟ|หมูแดง|หมูกรอบ|หมูกระทะ|"
            r"มาม่า(?:ผัด|ต้มยำ|หมูสับ|คัพ)?|บะหมี่(?:กึ่งสำเร็จรูป|น้ำ|แห้ง|เกี๊ยว|หมูแดง)?|"
            # Tea variants — no \b because Thai script has no ASCII word
            # boundaries. Bare "ชา" alone won't match (suffix is required),
            # so "ชายชาตรี"/"ชา (พ.ศ.)" stay safe.
            r"ชา(?:นม(?:ไข่มุก)?|เย็น|ไทย|เขียว|มะนาว|ดำ)|"
            r"ชานมไข่มุก|น้ำหวาน|น้ำผลไม้|สมูทตี้|"
            r"ครัว(?:คุณ|บ้าน|แม่|ป้า|ลุง|พี่|น้อง)|"
            r"อิ่มอร่อย|เคียงมอ|"
            r"เซเว่น(?=.*(?:ร้าน|อาหาร))",
            re.IGNORECASE,
        ),
    ),

    # Transport / fuel / ride-hailing / airlines (grab/bolt only if not "food")
    (
        "transport",
        # จับ: แท็กซี่/รถไฟฟ้า/ปั๊มน้ำมัน/สายการบิน.
        # ตัวอย่าง: "แท็กซี่", "ปั๊มน้ำมัน", "bts", "thai airways".
        # grab(?!\s*food) = negative lookahead (?!...) จับ "grab" เฉพาะที่
        # *ไม่* ตามด้วย "food" (คู่กับหมวด food ด้านบนที่ดัก Grab Food ไปแล้ว).
        re.compile(
            _LB + r"(grab(?!\s*food)|bolt(?!\s*food)|taxi|uber|gojek|"
            r"bts|mrt|arl|airport\s*rail|skytrain|sky\s*train|expressway|tollway|"
            r"shell|esso|ptt|caltex|bangchak|fuel|gasoline|petrol|"
            r"thai\s*airways|air\s*asia|airasia|nok\s*air|bangkok\s*airways|"
            r"thai\s*smile|thai\s*lion|vietjet|emirates|"
            r"airline|airways|airport|flight)" + _RB + r"|"
            r"แท็กซี่|รถไฟ(?:ฟ้า)?|รถเมล์|รถตู้|รถทัวร์|วินมอเตอร์ไซค์|"
            r"พีทีที|บางจาก|เชลล์|เอสโซ่|คาลเท็กซ์|น้ำมัน|ปั๊ม(?:น้ำมัน)?|"
            r"ทางด่วน|ค่าทาง|ตั๋วเครื่องบิน|สายการบิน|การบินไทย|แอร์เอเชีย|นกแอร์",
            re.IGNORECASE,
        ),
    ),

    # Entertainment / subscriptions / cinema / gaming
    (
        "entertain",
        # จับ: สตรีมมิ่ง/โรงหนัง/เกม/คอนเสิร์ต/คาราโอเกะ.
        # ตัวอย่าง: "netflix", "โรงหนังเมเจอร์", "steam", "คอนเสิร์ต".
        # (?:...)? = non-capturing group + optional เช่น "youtube premium" หรือ
        # "youtube" เฉยๆ ก็ match (?: คือกลุ่มที่ไม่เก็บค่าไว้ ใช้แค่จัดกลุ่ม).
        re.compile(
            _LB + r"(netflix|spotify|youtube(?:\s*premium|\s*music)?|disney\+?|"
            r"disney\s*plus|hbo|apple\s*music|apple\s*tv|prime\s*video|"
            r"iqiyi|we\s*tv|wetv|viu|joox|tidal|"
            r"major\s*cineplex|major|sf\s*cinema|sfx|sfw|cineplex|cinema|imax|"
            r"steam(?:powered)?|ps\s*store|playstation|psn|nintendo|"
            r"xbox|epic\s*games|garena|riot\s*games|"
            r"karaoke|concert)" + _RB + r"|"
            r"โรงหนัง|โรงภาพยนตร์|เมเจอร์|หนัง|ภาพยนตร์|เกม|คอนเสิร์ต|คาราโอเกะ",
            re.IGNORECASE,
        ),
    ),

    # Home & bills / utilities / rent / internet / mobile
    (
        "home",
        # จับ: ค่าน้ำ/ค่าไฟ/เน็ต/ค่าเช่า/บิลมือถือ/ค่าธรรมเนียมธนาคาร.
        # ตัวอย่าง: "ค่าไฟฟ้า", "ค่าเช่าหอพัก", "ais fibre", "จ่ายบิล".
        # electric(?:ity)? = จับได้ทั้ง "electric" และ "electricity".
        re.compile(
            _LB + r"(rent|electric(?:ity)?\s*bill|water\s*bill|wifi|internet|"
            r"tot|ais(?:\s*fibre|\s*postpaid|\s*prepaid)?|true(?:move|\s*online|"
            # true(...) บังคับต้องมี suffix เสมอ (ไม่มี "?" ต่อท้ายกลุ่ม) — กัน
            # "true" คำเดี่ยวๆ (บูลีน/สถานะทั่วไป เช่น "สถานะ true ปกติ") หลุดมา
            # ตกหมวด home ผิดๆ. ถ้า merchant ทั้งสตริงเป็น "True" เป๊ะจริงๆ (ไม่มี
            # suffix) seed dictionary exact-match layer จะดักไว้แทน (ดู
            # AMBIGUOUS_SEED_KEYS ใน seed_merchants.py — "True" อยู่ในลิสต์นี้).
            r"\s*vision|\s*id)|dtac|3bb|nt\s*broadband|"
            r"pea|mea|metropolitan\s*electricity|provincial\s*electricity|"
            r"apartment|condo|condominium|dormitory|"
            r"bill\s*payment|utility|utilities)" + _RB + r"|"
            r"กฟน|กฟภ|การประปา|ประปา|ค่าไฟ(?:ฟ้า)?|ค่าน้ำ|ค่าเช่า|ค่าเน็ต|"
            r"ทรูมูฟ|ทรูออนไลน์|ทรูวิชั่นส์|เอไอเอส|ดีแทค|"
            r"เน็ตบ้าน|นิติบุคคล|ชำระบิล|จ่ายบิล|ค่าก๊าซ|หอพัก|อพาร์ทเมนท์|คอนโด|"
            r"ค่าธรรมเนียม(?:การ(?:ถอน|โอน|ใช้บริการ))?|" + _LB + r"atm\s*fee" + _RB + r"|service\s*charge|ค่าบริการธนาคาร",
            re.IGNORECASE,
        ),
    ),

    # Groceries / supermarkets / convenience stores
    (
        "groceries",
        # จับ: ร้านสะดวกซื้อ/ซูเปอร์มาร์เก็ต/ตลาด.
        # ตัวอย่าง: "เซเว่น", "โลตัส", "big c", "แม็คโคร".
        # 7[-\s]?eleven = ยอมมี "-" หรือช่องว่างคั่นหรือไม่มีก็ได้ (? = 0 หรือ 1 ตัว)
        # → match "7-eleven", "7 eleven", "7eleven".
        re.compile(
            _LB + r"(7[-\s]?eleven|7[-\s]11|seven\s*eleven|family\s*mart|familymart|lawson|"
            r"mini\s*big\s*c|"
            r"tops(?:\s*daily|\s*market|\s*super)?|big\s*c|lotus(?:\s*go\s*fresh|"
            r"\s*express|s)?|tesco(?:\s*lotus)?|makro|villa\s*market|"
            r"gourmet\s*market|foodland|home\s*fresh\s*mart|"
            r"cj\s+(?:more|supermarket|axtra|\d{2,})|"
            r"cp\s*fresh\s*mart|cp\s*axtra|cp\s*meiji|cp\s*pork|cp\s*all|"
            r"market|supermarket|grocery|groceries|minimart)" + _RB + r"|"
            r"เซเว่น|เซเว่นอีเลฟเว่น|แฟมิลี่มาร์ท|แฟมิลี่|ตลาดสด|ตลาดนัด|"
            r"ซูเปอร์มาร์เก็ต|มินิมาร์ท|แม็คโคร|ท็อปส์|โลตัส|บิ๊กซี|วิลล่า|กูร์เมต์",
            re.IGNORECASE,
        ),
    ),

    # Shopping / marketplaces / department stores / fashion
    (
        "shopping",
        # จับ: มาร์เก็ตเพลส/ห้างสรรพสินค้า/แฟชั่น/ร้านค้าทั่วไป.
        # ตัวอย่าง: "shopee", "เซ็นทรัล", "uniqlo", "ร้านค้าตัวอย่าง".
        # เป็น rule ท้ายสุด (คำ generic สุด เช่น mall/store/ร้านค้า) จึงต้องอยู่
        # หลัง groceries ที่เฉพาะเจาะจงกว่า — ไม่งั้นจะกลืนร้านสะดวกซื้อไปหมด.
        re.compile(
            _LB + r"(shopee|lazada|jd\s*central|kaidee|amazon(?:\.com)?|aliexpress|"
            r"uniqlo|h&m|zara|muji|nike|adidas|puma|new\s*balance|"
            r"central(?:world|\s*world|\s*plaza|\s*department)?|robinson|"
            r"emporium|emquartier|emsphere|paragon|siam\s*paragon|terminal\s*21|"
            r"icon\s*siam|iconsiam|mega\s*bangna|mbk|the\s*mall|"
            r"ikea|home\s*pro|homepro|do\s*home|dohome|index\s*living|"
            r"power\s*buy|j\.?\s*i\.?\s*b|jaymart|advice|banana\s*it|"
            r"daiso|miniso|loft|"
            r"mall|plaza|store|department|outlet|boutique)" + _RB + r"|"
            r"ช้อปปี้|ลาซาด้า|ห้าง(?:สรรพสินค้า)?|เซ็นทรัล|โรบินสัน|พารากอน|"
            r"เอ็มควอเทียร์|ไอคอนสยาม|โฮมโปร|โดโฮม|พาวเวอร์บาย|"
            r"ร้านค้า|ร้านขาย",
            re.IGNORECASE,
        ),
    ),
]


# _normalize เตรียม merchant ก่อนยิงเข้า regex หมวด: lowercase + ยุบช่องว่าง
# + แทนเครื่องหมายที่มักคั่นชื่อแบรนด์ (. _ / \ |) ด้วยช่องว่าง เพื่อให้
# "7-Eleven" / "7.11" / "C.P." ยังแมตช์ pattern เดิมได้.
# (คนละตัวกับ _normalize_merchant ของ Learning Loop ที่อยู่ backend/app.py —
#  ตัวนั้นใช้ทำ key จำหมวดที่ user แก้เอง; ไฟล์นี้ไม่ยุ่งกับ override hook.)
def _normalize(s: str) -> str:
    """Lowercase, collapse whitespace, strip leading/trailing punctuation."""
    if not s:
        return ""
    out = s.lower()
    # Replace common punctuation that splits brand names with a space so
    # "7-Eleven" / "7-11" / "C.P." still match their patterns.
    out = re.sub(r"[._/\\|]+", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


# ============================================================
# Seed dictionary layer (ฐานร้านดังไทย pre-load — แก้ cold start)
# ------------------------------------------------------------
# ชั้นกลางระหว่าง Learning Loop (per-user override) กับ regex keyword:
# ร้านดังสาธารณะที่ pre-load ไว้ → จัดหมวดถูกตั้งแต่รายการแรก โดยไม่ต้อง
# รอ user สอน. ดูรายการ + เหตุผลเลือกร้านใน logic_ai/seed_merchants.py.
#
# _SEED_LOOKUP = normalize key ของ SEED_MERCHANTS ครั้งเดียวตอน import
# (ด้วย _normalize เดียวกับที่ categorize ใช้กับ merchant จริง) → runtime
# lookup เป็น dict O(1). _SEED_MAX_TOKENS = เพดานความยาว window (token) ที่ลอง
# ต่อจุดเริ่มต้นหนึ่งจุด (bounded → แต่ละ dict lookup ยังคง O(1) คงที่ ไม่ scan
# ทั้ง list).
# ============================================================

_SEED_LOOKUP: dict[str, str] = {
    _normalize(k): v for k, v in SEED_MERCHANTS.items() if _normalize(k)
}
_SEED_MAX_TOKENS = 4

# Normalize AMBIGUOUS_SEED_KEYS ครั้งเดียวตอน import เหมือน _SEED_LOOKUP (ดู
# เหตุผลรายตัว + เกณฑ์คัดเข้า/ข้อยกเว้นในคอมเมนต์หัวไฟล์ seed_merchants.py).
# _seed_lookup() ใช้เซตนี้จำกัด key กำกวมให้ match ได้เฉพาะตอน exact
# full-string เท่านั้น (ไม่ให้ sliding-window จับตำแหน่งอื่นในสตริง).
_AMBIGUOUS_SEED_LOOKUP: frozenset[str] = frozenset(
    _normalize(k) for k in AMBIGUOUS_SEED_KEYS if _normalize(k)
)


def _seed_lookup(m: str) -> str | None:
    """คืนหมวดจาก seed dictionary ถ้า ``m`` (merchant ที่ normalize แล้ว) ตรงร้านดัง.

    ``m`` ต้องผ่าน ``_normalize`` มาก่อน (เหมือนที่ ``categorize`` ทำ).
    วิธีจับ 2 ชั้น:
        1. exact match — dict lookup O(1) กับทั้งสตริง.
        2. **sliding-window token match** — แบรนด์อาจอยู่ตรงไหนของสตริงก็ได้
           ไม่ใช่แค่หัว (เช่น "ชำระบิล AIS" ต้องจับ "ais" ที่ index 1 ไม่ใช่
           index 0) จึงลอง window ที่ **ทุกจุดเริ่มต้น** ในสตริง (ไม่ใช่แค่
           ``toks[0:n]``) โดยแต่ละจุดเริ่มต้นจำกัดความยาวไว้ที่
           ``_SEED_MAX_TOKENS`` token แล้วลองยาว→สั้น (เจอยาวสุดที่จุดนั้นแล้ว
           หยุด ไม่ลองสั้นกว่านี้ที่จุดเดิม — กันจับซ้ำ เช่น "grab" ใน "grab
           food" ทั้งที่ "grab food" ตรงกว่า).
           ยังใช้ **dict lookup O(1) ต่อ window เดิม** (ไม่ scan ทั้ง
           SEED_MERCHANTS) — ต้นทุนรวม = O(จำนวน token ในสตริง ×
           _SEED_MAX_TOKENS) ซึ่ง bounded และเร็ว (merchant string ปกติสั้น
           ไม่กี่ token).
           ถ้าเจอมากกว่า 1 จุดเริ่มต้น → **แมตช์ที่ยาวที่สุดทั้งสตริงชนะ**
           (ไม่ใช่แค่จุดเริ่มต้นแรกที่เจอ) เพื่อให้แบรนด์เฉพาะเจาะจงกว่าชนะเสมอ
           ไม่ว่าจะอยู่ตรงไหน — mirror เจตนาเดิมของ longest-first (เช่น
           "grab food" ชนะ "grab", "bolt food" ชนะ "bolt") แต่ตอนนี้ใช้ได้
           แม้แบรนด์ไม่ได้อยู่ที่หัวสตริง.
           การ split ด้วยช่องว่าง (whitespace token) ก็ทำหน้าที่เป็น "ขอบคำ"
           ในตัวอยู่แล้ว (ไม่ใช่ substring ดิบแบบ `in`) — กัน false positive
           ที่คำสั้นไปแมตช์กลางคำอื่นโดยบังเอิญ.

           **Ambiguous-key guard** (REW review, 14 ก.ค. 2026): sliding-window
           เปิดช่องให้ key สั้น/เป็นคำทั่วไป (เช่น "True") จับได้ทุกตำแหน่ง แม้
           ไม่เกี่ยวกับแบรนด์เลย (เช่น "สถานะ true ปกติ"). Key ที่อยู่ใน
           ``_AMBIGUOUS_SEED_LOOKUP`` (ดูเกณฑ์คัดเข้าใน seed_merchants.py) จะ
           ถูก**ข้าม**ในลูป sliding-window นี้เสมอ (ต่อให้เจอ substring ตรงกัน)
           — ให้ match ได้เฉพาะทาง exact full-string ด้านบนเท่านั้น (สตริง
           merchant ทั้งหมดตรงกับ key เป๊ะ ไม่มีคำอื่นปนเลย ถือเป็นสัญญาณที่
           น่าเชื่อถือกว่าการเป็นแค่ส่วนหนึ่งของสตริงยาว).
           ไม่พบเลย → คืน ``None`` (ให้ไปต่อ regex).
    """
    hit = _SEED_LOOKUP.get(m)
    if hit:
        return hit
    toks = m.split(" ")
    n_toks = len(toks)
    best_hit: str | None = None
    best_len = 0
    for start in range(n_toks):
        window_cap = min(_SEED_MAX_TOKENS, n_toks - start)
        for length in range(window_cap, 0, -1):
            window = " ".join(toks[start:start + length])
            hit = _SEED_LOOKUP.get(window)
            if hit:
                if window in _AMBIGUOUS_SEED_LOOKUP:
                    # key กำกวม — ไม่ยอมรับ partial match ในลูปนี้ (เคส
                    # exact full-string ถูกเช็คไปแล้วด้านบนก่อนเข้าลูป) ลอง
                    # window สั้นกว่าที่จุดเริ่มต้นเดิมต่อ (ไม่ break).
                    continue
                if length > best_len:
                    best_len = length
                    best_hit = hit
                # เจอยาวสุดที่จุดเริ่มต้นนี้แล้ว — ข้ามไปจุดเริ่มต้นถัดไป
                # (ไม่ลองสั้นกว่านี้ที่จุดเดิม กันจับซ้อนกับ window ที่ยาวกว่า).
                break
    return best_hit


def categorize(merchant: str, _type: str, incoming: bool) -> str:
    """Map a transaction merchant string to one of the 8 fixed categories.

    Returns 'income' when the transaction is incoming, otherwise tries the
    ordered keyword rules. Unknown merchants fall back to 'other' — never
    raises so callers can always trust the result.
    """
    # เงินเข้า → หมวด "income" เสมอ (ไม่ต้องเดาจากชื่อร้าน).
    if incoming:
        return "income"

    # normalize ชื่อร้านก่อน (lowercase + ยุบช่องว่าง + แทนเครื่องหมายคั่น) แล้ว
    # ยิงเข้า _CATEGORY_RULES ทีละตัวตามลำดับ — "แมตช์ตัวแรกชนะ" (return ทันที).
    m = _normalize(merchant)
    if not m:
        return "other"

    # Seed dictionary layer — ร้านดัง pre-load ชนะ regex, แพ้ MerchantOverride
    # (override เขียนทับทีหลังตอน insert ใน app.py). ต้องอยู่หลัง income guard
    # เสมอ (รายการเงินเข้า route "income" ไปแล้ว ไม่ผ่านจุดนี้).
    seed = _seed_lookup(m)
    if seed:
        return seed

    for cat, pat in _CATEGORY_RULES:
        if pat.search(m):
            return cat
    # ไม่โดน rule ไหนเลย → "other" (safe fallback — ฟังก์ชันนี้ไม่ throw เด็ดขาด).
    return "other"


# ============================================================
# K-Bank parser (กสิกร / K PLUS)
# ------------------------------------------------------------
# รูปแบบแถว KBank: <วันที่ DD-MM-YY> <เวลา> <action> <จำนวน> <ยอดคงเหลือ>
# <รายละเอียด>. จุดต่างจากธนาคารอื่น:
#   - action มีได้ 2 คำ (โดยเฉพาะ statement อังกฤษ) เช่น "Transfer
#     Withdrawal" / "QR Transfer" → group ที่ 5 (คำที่สอง) เป็นตัวบอก
#     ทิศทางเงินเข้า/ออก ถ้ามี; ถ้าไม่มีใช้ group 4
#   - รายละเอียดมักล้นไปบรรทัดถัดไป → เรา "กาว" (glue) บรรทัดถัดไปได้ไม่
#     เกิน 2 บรรทัด และหยุดเมื่อเจอบรรทัดวันที่ใหม่/บรรทัด noise/ยาวเกิน 90
#   - KBank แทรก noise หน้า merchant เยอะ (prefix ช่องทาง + "Ref X####"
#     ของ QR/bill payment) → strip ออกเป็นชั้นๆ ให้เหลือชื่อร้านจริง
#     เช่น "เพื่อชำระ Ref X#### <ร้าน>" / "Ref: #### <ร้าน>" → "<ร้าน>"
# ============================================================

# _KBANK_LINE จับทั้งแถวธุรกรรม แล้วแยกเป็น capture group (กลุ่มในวงเล็บที่ regex
# "จำ" ค่าไว้ ดึงด้วย .group(n) ทีหลัง):
#   g1-g3 = วัน-เดือน-ปี (DD-MM-YY) · g4 = action หลัก · g5 = action รอง (อาจไม่มี)
#   g6 = จำนวนเงิน · g7 = รายละเอียด (ชื่อร้าน/โน้ต)
# ตัวอย่างแถว: "01-02-24 13:45 Transfer Withdrawal 100.00 5,000.00 ร้านตัวอย่าง"
#   → g1=01 g2=02 g3=24 g4=Transfer g5=Withdrawal g6=100.00 g7=ร้านตัวอย่าง
_KBANK_LINE = re.compile(
    r"^(\d{2})-(\d{2})-(\d{2})\s+\d{2}:\d{2}\s+"
    # Primary action token: Thai keywords or English channel/action words.
    r"(รับโอนเงิน|โอนเงิน|ชำระเงิน|ถอนเงินสด|ค่าธรรมเนียม|ดอกเบี้ย|ฝากเงินสด|ฝาก|ถอน|"
    r"Transfer|Payment|Withdrawal|Withdraw|Deposit|Interest|Fee|QR|Cash)"
    # Optional secondary action token (English KBank uses 2-word actions like
    # "Transfer Withdrawal" / "Transfer Deposit" / "QR Transfer" / "Cash Withdrawal").
    r"(?:\s+(Withdrawal|Withdraw|Deposit|Transfer|Payment))?\s+"
    r"([\d,]+\.\d{2})\s+[\d,]+\.\d{2}\s+(.+)$"
)
# ใช้เช็คว่าบรรทัดถัดไปเป็น "แถววันที่ใหม่" หรือยัง (ขึ้นต้นด้วย DD-MM-YY)
# → ถ้าใช่ ต้องหยุดกาว desc ข้ามแถว ไม่งั้นชื่อร้านจะเลอะไปแถวถัดไป.
_KBANK_DATE_LINE = re.compile(r"^\d{2}-\d{2}-\d{2}\s")
# บรรทัด noise ที่ต้องข้าม (หัวตาราง/สรุปยอด/เลขหน้า) — ห้ามกาวต่อท้าย desc.
_KBANK_SKIP = re.compile(
    r"^(KBPDF|ออกโดย|หน้าที่|PAGE/OF|ที่ DD\.|ชื่อบัญชี|สาขา|เลขที่|รอบระหว่าง|รวมถอน|รวมฝาก|"
    r"ยอดยกไป|ยอดคงเหลือ|วันที่ เวลา|วันที่มีผล|ช่องทาง|\(บาท\)|รายละเอียด|--\s*\d+\s*of|\d+/\d+\(\d+\))"
)
# set ของ action ที่แปลว่า "เงินเข้า" → ใช้พลิกเครื่องหมายจำนวนให้เป็นบวก
# และ route ไปหมวด income (เช็คด้วย `in` ซึ่งเร็วเพราะเป็น set).
_KBANK_INCOMING = {"รับโอนเงิน", "ฝาก", "ฝากเงินสด", "ดอกเบี้ย", "Deposit", "Interest"}


def parse_kbank(raw: str) -> list[dict]:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    txs: list[dict] = []
    i = 0
    while i < len(lines):
        m = _KBANK_LINE.match(lines[i])
        if not m:
            i += 1
            continue

        desc = m.group(7)
        # "กาว" (glue) รายละเอียดที่ล้นไปบรรทัดถัดไป — KBank ตัดชื่อร้านยาวขึ้น
        # บรรทัดใหม่บ่อย. ต่อได้ไม่เกิน 2 บรรทัด และหยุดทันทีเมื่อเจอแถววันที่ใหม่
        # / บรรทัด noise / บรรทัดยาวเกิน 90 (น่าจะเป็นแถวอื่นไม่ใช่ส่วนต่อ desc).
        j = i + 1
        glued = 0
        while j < len(lines) and glued < 2:
            nxt = lines[j]
            if _KBANK_DATE_LINE.match(nxt) or _KBANK_SKIP.match(nxt) or len(nxt) > 90:
                break
            desc += " " + nxt
            j += 1
            glued += 1

        try:
            amount = float(m.group(6).replace(",", ""))
        except ValueError:
            i += 1
            continue
        if amount == 0:
            i += 1
            continue

        action1 = m.group(4)
        action2 = m.group(5)  # may be None
        # For English KBank 2-word actions, the second token holds direction
        # (e.g. "Transfer Deposit" = incoming, "Transfer Withdrawal" = outgoing).
        # For single-token actions (Thai or "Payment"/"Fee"), fall back to action1.
        direction_token = action2 if action2 else action1
        incoming = direction_token in _KBANK_INCOMING
        tx_type = f"{action1} {action2}" if action2 else action1
        date = f"20{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

        merchant = desc
        # ลอก noise หน้าชื่อร้านทีละชั้น (KBank ใส่ prefix ช่องทางเยอะ):
        # ชั้นที่ 1 = ชื่อแอป/ช่องทาง (K PLUS, ATM, ตู้ฯ, ชื่อธนาคารอื่น) ที่ขึ้นต้น desc.
        merchant = re.sub(
            r"^(K PLUS|EDC/K SHOP/MYQR|MAKE by KBank|Internet/Mobile [A-Z]+|ATM[^\s]*|ตู้[^\s]*|"
            r"ต่างธนาคาร|MyMo by GHB|SCB EASY|Krungthai NEXT|Bualuang mBanking)\s*",
            "", merchant, flags=re.I,
        )
        # Strip KBank QR/bill payment noise prefixes — keep real merchant name only.
        # Patterns seen on real statements: "เพื่อชำระ Ref X2225 <merchant>",
        # "Ref X1234 <merchant>", "Ref: 1234 <merchant>".
        merchant = re.sub(r"^เพื่อชำระ\s+Ref\.?\s*:?\s*X?\d+\s+", "", merchant, flags=re.I)
        merchant = re.sub(r"^Ref\.?\s*:?\s*X?\d+\s+", "", merchant, flags=re.I)
        merchant = re.sub(r"^เพื่อชำระ\s+", "", merchant, flags=re.I)
        # ชั้นถัดไป: ลบ prefix "จาก/โอนไป <ตัวย่อธนาคาร> พร้อมเพย์ X####" (เลข
        # บัญชีปิดบัง X#### ไม่ใช่ชื่อร้าน) + ลบ "(ชื่อบัญชี:...)" + สัญลักษณ์ "++".
        merchant = re.sub(r"^(จาก|โอนไป)\s+(?:[A-Z]{2,5}\s+)?(?:พร้อมเพย์\s+)?(?:X\d+\s+)?", "", merchant)
        merchant = re.sub(r"\(\s*ชื่อบัญชี:[^)]*\)?", "", merchant)
        merchant = merchant.replace("++", "")
        # ปิดท้าย: ยุบช่องว่างที่เหลือจากการลบ + ตัดหัวท้าย.
        merchant = re.sub(r"\s+", " ", merchant).strip()

        txs.append({
            "date": date,
            "merchant": merchant or ("รับโอนเงิน" if incoming else "ธุรกรรม"),
            "amount": amount if incoming else -amount,
            "type": tx_type,
            "category": categorize(merchant, tx_type, incoming),
        })
        i += 1
    return txs


# ============================================================
# GSB parser (ออมสิน / MyMo)
# ------------------------------------------------------------
# รูปแบบแถว GSB: <วันที่ DD/MM/YYYY (พ.ศ.)> <รายละเอียด> <จำนวน> <ยอด
# คงเหลือ> <เลขอ้างอิง 2 ชุด>. จุดต่าง:
#   - ปีเป็น พ.ศ. → ต้อง -543 เป็น ค.ศ.
#   - รายละเอียดเป็นรหัสช่องทาง/marker ("MyMo", "Transaction", "C Scan B",
#     "from/to SAV") ปนกับชื่อร้าน → _gsb_desc_map() แปลง label ที่อ่านง่าย
#     แล้วดึงชื่อร้านจริงที่เหลือออกมาต่อท้ายด้วย _gsb_extra() เพื่อให้
#     categorize() ยังจับแบรนด์ได้ (เช่น "C Scan B <ร้านกาแฟ>" → food)
#   - รายการเงินเข้า (SAV Deposit / Interest / Transfer+Deposit) เก็บ label
#     เปล่าๆ พอ เพราะ flag เงินเข้าจะ route ไป "income" อยู่แล้ว
# ============================================================

# _GSB_LINE: g1-g3 = วัน/เดือน/ปี(พ.ศ. 4 หลัก) · g4 = รายละเอียด · g5 = จำนวน
# · g6 = ยอดคงเหลือ · แล้วท้ายแถวมีเลขอ้างอิง 2 ชุด (\d+ \d+ — ไม่ได้ capture).
# (.+?) ที่ g4 = "ขี้เกียจ" (non-greedy) จับให้สั้นสุดพอเจอตัวเลขจำนวนถัดไป
# กันมันกินเลขจำนวนเข้าไปในรายละเอียด.
# ตัวอย่าง: "01/02/2567 C Scan B ร้านตัวอย่าง 50.00 1,000.00 123 456"
_GSB_LINE = re.compile(
    r"^(\d{2})/(\d{2})/(\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+\d+\s+\d+"
)
_GSB_DEPOSIT = re.compile(
    r"\b(Deposit|ฝาก|รับโอน|เงินเข้า|Interest|ดอกเบี้ย|Credit|CR)\b",
    re.I,
)
_GSB_NOISE = re.compile(
    r"^(ข้อมูลรายการ|โดยผู้ใช้|หน้า \d+|-- \d+|รายการเดินบัญชี|ชื่อบัญชี|ประเภทบัญชี|"
    r"เลขที่บัญชี|สาขาเจ้าของ|รอบวันที่|ยอดยกมา|วันที่\s+รายการ|สาขา\s+รายการ)"
)


# Known GSB channel/marker tokens (not human-readable merchant — strip from
# extra info so brand names remain).
_GSB_MARKERS = re.compile(
    r"\b(MyMo|Transaction)\b",
    re.I,
)


def _gsb_extra(desc: str, label_keywords: list[str]) -> str:
    """Pull human-readable extra info (merchant/payee) out of a GSB
    description after stripping channel markers ("MyMo", "Transaction"),
    SAV account hints ("from/to SAV"), and the label keywords already encoded
    into the generic label. Empty string if nothing useful remains.

    Conservative: we only strip known noise; we never invent text.
    """
    # สเต็ป: (1) ลบ marker ช่องทาง (MyMo/Transaction) (2) ลบ "from/to SAV"
    # (บัญชีภายใน ไม่ใช่ชื่อร้าน) (3) ลบโค้ดในวงเล็บสั้นๆ เช่น "(QR)" (4) ลบคำ
    # label ที่ใส่ไปในป้ายแล้ว (กันซ้ำ) (5) ยุบช่องว่าง/ตัวคั่น — ถ้าเหลือแต่
    # ตัวเลข/ว่าง คืน "" (ไม่มีข้อมูลชื่อร้านที่ใช้จัดหมวดได้).
    out = _GSB_MARKERS.sub(" ", desc)
    # Drop GSB-style SAV account hints — they're internal account tags, not
    # merchant names, so they pollute categorize() input.
    out = re.sub(r"\b(from|to)\b\s+SAV\b", " ", out, flags=re.I)
    # Drop short codes wrapped in parens like "(QR)" — they don't help
    # categorize and we add them back via the label.
    out = re.sub(r"\([^)]{1,15}\)", " ", out)
    for kw in label_keywords:
        out = re.sub(kw, " ", out, flags=re.I)
    out = re.sub(r"[\s,/\-]+", " ", out).strip()
    # Reject leftovers that are just digits or empty — not informative.
    if not out or re.fullmatch(r"[\d\s.]+", out):
        return ""
    return out


def _gsb_desc_map(desc: str) -> str:
    """Map a raw GSB description line to a human label, preserving any
    additional merchant/payee info found in the raw text so categorize() can
    still pick up brand names (e.g. "C Scan B STARBUCKS" → food).

    Income labels (SAV Deposit / Interest / Transfer+Deposit) stay as plain
    labels because the incoming flag routes them to "income" anyway.
    """
    # รับ: บรรทัด desc ดิบ · คืน: label ไทยอ่านง่าย (+ ชื่อร้านต่อท้ายถ้าดึงได้).
    # ลำดับ: เช็ครายการเงินเข้าก่อน (คืน label เปล่า เพราะ flag income จัดหมวดเอง)
    # → แล้วไล่ elif เลือก label ตามคำที่เจอ → ดึงชื่อร้านที่เหลือด้วย _gsb_extra().
    # Income paths — keep plain label (incoming flag handles categorization).
    if re.search(r"SAV Deposit", desc, re.I):
        return "รับโอนเงิน"
    if re.search(r"Interest|ดอกเบี้ย", desc, re.I):
        return "ดอกเบี้ย"
    if re.search(r"Transfer", desc, re.I) and re.search(r"Deposit", desc, re.I):
        return "รับโอนเงิน"

    label: str | None = None
    label_keywords: list[str] = []

    if re.search(r"C Scan B", desc, re.I):
        label = "C Scan B (QR)"
        label_keywords = [r"C\s*Scan\s*B"]
    elif re.search(r"Bill Payment", desc, re.I):
        label = "ชำระบิล"
        label_keywords = [r"Bill\s*Payment"]
    elif re.search(r"\bWithdraw(?:al)?\b", desc, re.I):
        label = "ถอนเงินสด"
        label_keywords = [r"Withdraw(?:al)?"]
    elif re.search(r"\bFee\b", desc, re.I):
        label = "ค่าธรรมเนียม"
        label_keywords = [r"Fee"]
    elif re.search(r"Transfer", desc, re.I):
        label = "โอนเงิน"
        label_keywords = [r"Transfer"]
    elif re.search(r"\bPay(?:ment)?\b", desc, re.I):
        label = "ชำระเงิน"
        label_keywords = [r"Pay(?:ment)?"]

    if label is not None:
        extra = _gsb_extra(desc, label_keywords)
        return f"{label} {extra}".strip() if extra else label

    # Fallback: no known label — strip generic noise only (legacy behaviour).
    out = re.sub(r"^(MyMo\s+|C Scan B\s+)", "", desc, flags=re.I)
    out = re.sub(r"\b(from|to)\b\s+SAV\b", "", out, flags=re.I)
    out = re.sub(r"\s+Transaction\s*$", "", out, flags=re.I)
    return re.sub(r"\s+", " ", out).strip()


def parse_gsb(raw: str) -> list[dict]:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    txs: list[dict] = []
    for line in lines:
        if _GSB_NOISE.match(line):
            continue
        m = _GSB_LINE.match(line)
        if not m:
            continue
        try:
            # GSB พิมพ์ปีเป็น พ.ศ. → แปลงเป็น ค.ศ. ด้วย -543 (เช่น 2567 → 2024).
            year = int(m.group(3)) - 543
            amount = float(m.group(5).replace(",", ""))
        except ValueError:
            continue
        if amount == 0:
            continue
        # จัดรูปวันที่เป็น ISO "YYYY-MM-DD"; zfill(2) เติม 0 นำหน้าให้ครบ 2 หลัก.
        date = f"{year}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        is_deposit = bool(_GSB_DEPOSIT.search(m.group(4)))
        merchant = _gsb_desc_map(m.group(4))
        tx_type = "ฝาก" if is_deposit else "ถอน"
        txs.append({
            "date": date,
            "merchant": merchant,
            "amount": amount if is_deposit else -amount,
            "type": tx_type,
            "category": categorize(merchant, tx_type, is_deposit),
        })
    return txs


# ============================================================
# KTB parser (กรุงไทย)
# ------------------------------------------------------------
# รูปแบบแถว KTB: <วันที่ DD/MM/YY (พ.ศ. 2 หลัก)> <รายละเอียด> <จำนวน>
# <ยอดคงเหลือ> <รหัส 3-4 หลัก>. จุดต่าง:
#   - ปีเป็น พ.ศ. 2 หลัก → year = 1957 + YY (เช่น 67 → 2024)
#   - รายละเอียดฝัง "marker code" ภายในของ KTB เช่น CGSWP (ชำระ QR),
#     MORWSW (โอนออกพร้อมเพย์), NMIDSD (รับโอนพร้อมเพย์) ฯลฯ — พวกนี้
#     ไม่ใช่ชื่อร้านที่คนอ่านออก. _ktb_merchant() ใช้ code เหล่านี้ (คู่กับ
#     คำไทย) เลือก label ที่อ่านง่าย แล้ว _ktb_extra() ลบ code + โค้ดใน
#     วงเล็บออก เหลือชื่อร้านจริงให้ categorize() จับ
#   - มี fallback label อังกฤษ (เผื่อ statement อังกฤษในอนาคต) เรียงจาก
#     เฉพาะเจาะจง → ทั่วไป; "Transfer" เดี่ยวๆ ถือเป็นเงินออกเพื่อความ
#     ปลอดภัย (ให้ _KTB_DEPOSIT เป็นตัวพลิกทิศเฉพาะ "Transfer In/Deposit")
# ============================================================

# _KTB_LINE: g1-g3 = วัน/เดือน/ปี(พ.ศ. 2 หลัก) · g4 = รายละเอียด · g5 = จำนวน
# · g6 = ยอดคงเหลือ (มี "-" นำหน้าได้) · g7 = รหัส 3-4 หลักท้ายแถว (ประจำ KTB).
# ตัวอย่าง: "01/02/67 CGSWP ชำระ QR ร้านตัวอย่าง 50.00 1,000.00 123"
_KTB_LINE = re.compile(
    r"^(\d{2})/(\d{2})/(\d{2})\s+(.+)\s+([\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s+(\d{3,4})\s*$"
)
# Deposit/income markers — Thai (primary) + English fallback for future
# English statement layouts. "CR" is kept short so we require a word
# boundary; "Transfer In" / "Transfer Deposit" are 2-token forms KTB has
# been seen to use on English statements. "Transfer" alone is ambiguous so
# it stays OUT of this set (default outgoing for safety).
_KTB_DEPOSIT = re.compile(
    r"^(เงินโอนเข้า|ฝากเงิน|ดอกเบี้ย|รับเงิน|รับโอน|"
    r"Transfer\s+(?:In|Deposit)|Deposit|Interest|Credit|CR\b)",
    re.IGNORECASE,
)
_KTB_NOISE = re.compile(
    r"^(รายการเดินบัญชี|รายการบัญชีระหว่าง|วันที่ส่ง|ชื่อบัญชี|ประเภทบัญชี|สาขา|เลขที่บัญชี|ที่อยู่|"
    r"วงเงิน|สกุลเงิน|วันที่/เวลา|บริษัท ธนาคาร|เลขที่ 35|ติดต่อ|-- \d+|หน้า \d+|ยอดยกมา|รวม|"
    r"จำนวนหน้า|รายการถอนทั้งหมด|รายการฝากทั้งหมด|C/F)"
)
_KTB_TIME = re.compile(r"^\d{2}:\d{2}")


# Known KTB internal marker codes (not human-readable — strip from extra info).
_KTB_MARKERS = re.compile(
    r"\b(MORISD|MORWSW|MORISW|MORPSW|NBSDT|NBSWT|NMIDSD|NMIDSW|CGSWP|CGSWD)\b",
    re.I,
)


def _ktb_extra(desc: str, label_keywords: list[str]) -> str:
    """Pull human-readable extra info (merchant name, payee) out of a KTB
    description, after stripping marker codes, paren-wrapped codes, and the
    label keywords we already encoded into the generic label. Empty string if
    nothing useful remains.

    Conservative: we only strip known noise; we never invent text.
    """
    # สเต็ป: (1) ลบ marker code ภายในของ KTB (CGSWP/MORWSW/... — รหัสระบบ ไม่ใช่
    # ชื่อร้าน) (2) ลบโค้ดในวงเล็บสั้นๆ เช่น "(NMIDSD)" (3) ลบคำ label ที่ใส่ไป
    # ในป้ายแล้ว (4) ยุบช่องว่าง/ตัดตัวคั่นท้าย — ถ้าเหลือแต่ตัวเลข/ว่าง คืน "".
    out = _KTB_MARKERS.sub(" ", desc)
    # Drop short codes wrapped in parens like "(NMIDSD)" or "(KTB)" — they
    # don't help categorize and pollute the merchant string.
    out = re.sub(r"\([^)]{1,15}\)", " ", out)
    for kw in label_keywords:
        out = re.sub(kw, " ", out, flags=re.I)
    # Collapse leftover whitespace + trim trailing punctuation/separators.
    out = re.sub(r"[\s,/\-]+", " ", out).strip()
    # Reject leftovers that are just digits or single short tokens — not
    # informative enough to categorize on.
    if not out or re.fullmatch(r"[\d\s.]+", out):
        return ""
    return out


def _ktb_merchant(desc: str) -> str:
    """Map a raw KTB description line to a human label, preserving any
    additional merchant/payee info found in the raw text so categorize() can
    still pick up brand names (e.g. "ชำระ QR Code STARBUCKS" → food).
    """
    # รับ: บรรทัด desc ดิบ · คืน: label ไทย (+ ชื่อร้านถ้าดึงได้). ไล่ elif จาก
    # marker code + คำไทยที่เฉพาะเจาะจงก่อน แล้วค่อย fallback ป้ายอังกฤษ (เผื่อ
    # statement อังกฤษในอนาคต). ไม่เข้าเงื่อนไขใด → คืนคำแรกของ desc (พฤติกรรม
    # เดิม กัน fixture เทสต์เปลี่ยน).
    label: str | None = None
    label_keywords: list[str] = []

    if re.search(r"เงินโอนเข้า.*พร้อมเพย์|MORISD|NMIDSD", desc, re.I):
        label = "รับโอน (PromptPay)"
        label_keywords = [r"เงินโอนเข้า", r"พร้อมเพย์", r"รับโอน"]
    elif re.search(r"เงินโอนเข้า|NBSDT", desc, re.I):
        label = "รับโอนเงิน"
        label_keywords = [r"เงินโอนเข้า", r"รับโอน"]
    elif re.search(r"โอนเงินออก.*พร้อมเพย์|MORWSW|MORISW|NMIDSW", desc, re.I):
        label = "โอนออก (PromptPay)"
        label_keywords = [r"โอนเงินออก", r"พร้อมเพย์", r"โอนออก"]
    elif re.search(r"โอนเงินออก|NBSWT", desc, re.I):
        label = "โอนเงินออก"
        label_keywords = [r"โอนเงินออก", r"โอนออก"]
    elif re.search(r"CGSWP", desc, re.I):
        label = "ชำระ QR Code"
        label_keywords = [r"ชำระ", r"QR\s*Code", r"QR"]
    elif re.search(r"จ่ายค่าสินค้า|MORPSW", desc, re.I):
        label = "ชำระค่าสินค้า/บริการ"
        label_keywords = [r"จ่ายค่าสินค้า", r"ชำระค่าสินค้า", r"บริการ"]
    elif re.search(r"ถอนเงิน", desc, re.I):
        label = "ถอนเงินสด"
        label_keywords = [r"ถอนเงินสด", r"ถอนเงิน"]
    elif re.search(r"ฝากเงิน", desc, re.I):
        label = "ฝากเงิน"
        label_keywords = [r"ฝากเงิน"]
    elif re.search(r"ดอกเบี้ย", desc, re.I):
        label = "ดอกเบี้ย"
        label_keywords = [r"ดอกเบี้ย"]
    elif re.search(r"ค่าธรรมเนียม", desc, re.I):
        label = "ค่าธรรมเนียม"
        label_keywords = [r"ค่าธรรมเนียม"]
    # ── English fallback labels (defensive — for future English KTB statements).
    # Order: deposit/withdraw before transfer because they're more specific;
    # bill payment before generic payment for routing into home category.
    elif re.search(r"\bBill\s*Payment\b", desc, re.I):
        label = "ชำระบิล"
        label_keywords = [r"Bill\s*Payment"]
    elif re.search(r"\bDeposit\b", desc, re.I):
        label = "ฝากเงิน"
        label_keywords = [r"Deposit"]
    elif re.search(r"\bWithdraw(?:al)?\b", desc, re.I):
        label = "ถอนเงินสด"
        label_keywords = [r"Withdraw(?:al)?"]
    elif re.search(r"\bInterest\b", desc, re.I):
        label = "ดอกเบี้ย"
        label_keywords = [r"Interest"]
    elif re.search(r"\bFee\b", desc, re.I):
        label = "ค่าธรรมเนียม"
        label_keywords = [r"Fee"]
    elif re.search(r"\bTransfer\b", desc, re.I):
        # Conservative: Transfer alone is treated as outgoing transfer; the
        # _KTB_DEPOSIT regex flips direction for "Transfer In/Deposit" forms.
        label = "โอนเงินออก"
        label_keywords = [r"Transfer"]
    elif re.search(r"\bPayment\b", desc, re.I):
        label = "ชำระเงิน"
        label_keywords = [r"Payment"]

    if label is not None:
        extra = _ktb_extra(desc, label_keywords)
        return f"{label} {extra}".strip() if extra else label

    # No known label matched — fall back to the original cleaned-first-token
    # behaviour so we don't change existing test fixtures.
    cleaned = re.sub(r"\s*\([A-Z]+\)\s*", " ", desc).split(" ")
    return cleaned[0] if cleaned and cleaned[0] else desc


def parse_ktb(raw: str) -> list[dict]:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    txs: list[dict] = []
    for line in lines:
        if _KTB_NOISE.match(line) or _KTB_TIME.match(line):
            continue
        m = _KTB_LINE.match(line)
        if not m:
            continue
        try:
            # KTB ใช้ พ.ศ. 2 หลัก → บวก 1957 ได้ ค.ศ. เต็ม (เช่น 67 → 2024;
            # 1957 = 2500 - 543).
            year = 1957 + int(m.group(3))
            amount = float(m.group(5).replace(",", ""))
        except ValueError:
            continue
        if amount == 0:
            continue
        date = f"{year}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        is_deposit = bool(_KTB_DEPOSIT.match(m.group(4).strip()))
        merchant = _ktb_merchant(m.group(4))
        tx_type = "ฝาก" if is_deposit else "ถอน"
        txs.append({
            "date": date,
            "merchant": merchant,
            "amount": amount if is_deposit else -amount,
            "type": tx_type,
            "category": categorize(merchant, tx_type, is_deposit),
        })
    return txs


# ============================================================
# SCB parser (ไทยพาณิชย์)
# ------------------------------------------------------------
# รูปแบบซับซ้อนสุด — 2 ชนิดแถว: _SCB_TX (เดบิต/เครดิตทั่วไป มี code X1/X2)
# และ _SCB_IN (รายการเงินเข้า code IN). จุดต่าง:
#   - บาง statement (OpenPDF/JasperReports) เขียนคำอธิบายไทย "ติด" กับยอด
#     คงเหลือโดยไม่มีช่องว่าง เช่น "...944.99จ่ายบิล..." → tail regex จึง
#     ตั้งแบบยอมรับกว้าง (.*)$ ไม่ใช่ \s*$ (แบบเข้มเดิม reject ~60% แถว)
#   - คำอธิบายอาจอยู่ "ในบรรทัดเดียวกัน" (inline หลังยอด) หรือ "บรรทัดก่อน
#     หน้า" (layout เก่า) → ใช้ inline ก่อน ไม่มีค่อย fallback ไป
#     _scb_prev_desc()
#   - _scb_merchant() มี ~6 รูปแบบเรียงลำดับ (สำคัญ! บางอันใช้ token
#     ร่วมกัน): (a) PAY <ref> <ร้าน> POS · (b) เติมเงิน WIDx#### <ช่องทาง>
#     · (f) "<ธนาคาร> (<CODE>) /X####" อ้างอิงข้ามธนาคาร ต้องมาก่อน (c)/(d)
#     เพราะใช้ชื่อธนาคารร่วมกัน · (e) จ่ายบิล <ผู้รับ> · (d) รับโอนจาก
#     <BANK> · (c) โอนไป <BANK> — แล้วตามด้วย fallback อังกฤษ + legacy
# ============================================================

# Note: trailing group is permissive ((.*)$ instead of \s*$) because some SCB
# statements (especially OpenPDF/JasperReports outputs) glue the Thai
# description directly onto the balance with no separating space — e.g.
# "...944.99จ่ายบิล...". The original strict tail rejected 60% of rows on
# such files. The captured tail is treated as inline description in
# parse_scb() and falls back to the previous-line heuristic when empty.
# _SCB_TX (แถวเดบิต/เครดิตทั่วไป): g1-g3 = วัน/เดือน/ปี · g4 = code (X1 = เงินเข้า,
# X2 = เงินออก) · g5 = เลขอ้างอิง · g6 = จำนวน · g7 = ยอดคงเหลือ · g8 = รายละเอียด
# inline (อาจว่าง — ดู note ด้านบนเรื่อง tail แบบ (.*)$ ที่ยอมรับกว้าง).
# ตัวอย่าง: "01/02/24 13:45 X2 REF123 100.00 5,000.00 PAY 999 ร้านตัวอย่าง"
_SCB_TX = re.compile(
    r"^(\d{2})/(\d{2})/(\d{2})\s+\d{2}:\d{2}\s+(X1|X2)\s+(\S+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})(.*)$"
)
# _SCB_IN (แถวเงินเข้า code "IN"): โครงเหมือน _SCB_TX แต่ไม่มี field X1/X2
# → g4 = เลขอ้างอิง · g5 = จำนวน · g6 = ยอดคงเหลือ · g7 = รายละเอียด inline.
_SCB_IN = re.compile(
    r"^(\d{2})/(\d{2})/(\d{2})\s+\d{2}:\d{2}\s+IN\s+(\S+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})(.*)$"
)
_SCB_NOISE = re.compile(
    r"^(ธนาคารไทยพาณิชย์|THE SIAM COMMERCIAL|ใบแจ้งรายการ|STATEMENT OF|สาขา$|ชื่อ - สกุล|Name$|"
    r"ที่อยู่$|Address$|เลขที่บัญชี$|Account No|^วันที่$|^Date$|Date Time Code|วันที่ เวลา รายการ|"
    r"ยอดเงินคงเหลือยกมา|BALANCE BROUGHT|TOTAL AMOUNTS|TOTAL ITEMS|เอกสารฉบับนี้|This document|"
    r"หน้า \d+|-- \d+ of|Balance/Baht|Debit/Credit)"
)


# Known SCB internal marker tokens — bank codes (English + Thai),
# channel/scheme tags, top-up ref ids. Not human-readable merchant info;
# strip from extra so brand names can survive the cleanup pass.
_SCB_MARKERS = re.compile(
    r"\b(KBANK|KTB|BBL|SCB|GSB|TMB|TTB|BAY|KKBANK|KK|CIMB|UOB|LH|TISCO|ICBC|TBANK|BAAC|"
    r"PromptPay|พร้อมเพย์|Transfer|TRANSFER)\b|"
    r"WIDx\d+|"
    r"กสิกรไทย|กรุงไทย|กรุงเทพ|ไทยพาณิชย์|ออมสิน|กรุงศรี|ธ\.?ก\.?ส\.?",
    re.I,
)


def _scb_extra(desc: str, label_keywords: list[str]) -> str:
    """Pull human-readable extra info (merchant/payee name) out of an SCB
    description after stripping bank codes, masked account hints ("x1234",
    "X9999", "/X1234"), long PAY ref ids, paren-wrapped codes, and the label
    keywords already encoded into the generic label. Empty string if nothing
    useful remains.

    Conservative: we only strip known noise; we never invent text. If only
    noise is left we return "" so the caller keeps the safe label.
    """
    # สเต็ป: (1) ลบรหัสธนาคาร/ช่องทาง (KBANK/พร้อมเพย์/...) (2) ลบเลขบัญชีปิดบัง
    # ทั้ง "X9999", "x9999" (พิมพ์เล็ก) และ "/X9999" (3) ลบ ref ยาว ≥10 หลัก
    # (ไม่ใช่ชื่อร้านแน่ๆ) (4) ลบโค้ดในวงเล็บสั้นๆ (5) ลบคำ label (6) ยุบช่องว่าง
    # — เหลือแต่ตัวเลข/ว่าง → คืน "" ให้ผู้เรียกใช้ label ปลอดภัยแทน.
    out = _SCB_MARKERS.sub(" ", desc)
    # Drop SCB-style masked account hints — both "X9999" (uppercase) and
    # "x9999" (lowercase, e.g. "KBANK xNNNN"), plus "/X9999" form.
    out = re.sub(r"/X\d+", " ", out)
    out = re.sub(r"\b[xX]\d{3,}\b", " ", out)
    # Drop long ref ids (PAY <10+ digit ref> …) — never merchant info.
    out = re.sub(r"\b\d{10,}\b", " ", out)
    # Drop short codes wrapped in parens like "(KBANK)" / "(X1234)" — they
    # don't help categorize and pollute the merchant string.
    out = re.sub(r"\([^)]{1,15}\)", " ", out)
    for kw in label_keywords:
        out = re.sub(kw, " ", out, flags=re.I)
    # Collapse leftover whitespace + trim separators.
    out = re.sub(r"[\s,/\-]+", " ", out).strip()
    # Reject leftovers that are just digits/dots — not informative.
    if not out or re.fullmatch(r"[\d\s.]+", out):
        return ""
    return out


# Bank-name → display label map for the "<bank> (<CODE>) /X####" pattern
# where SCB statement shows only an account ref but no person/merchant name.
_SCB_BANK_NAMES = (
    "กสิกรไทย",
    "กรุงไทย",
    "กรุงเทพ",
    "ไทยพาณิชย์",
    "ออมสิน",
    "กรุงศรี",
)


def _scb_merchant(desc: str) -> str:
    if not desc:
        return "ธุรกรรม"
    d = re.sub(r"\s+", " ", desc).strip()

    # ไล่เช็ค desc ทีละรูปแบบ (a)-(f) เรียงตามความเฉพาะเจาะจง — รูปที่ใช้ token
    # ร่วมกัน (เช่นชื่อธนาคาร) ต้องมาก่อนเสมอ. คืน label ไทย + ชื่อร้าน/ผู้รับที่
    # ดึงได้. หมายเหตุ: ตัวอย่างในคอมเมนต์ใช้ placeholder generic (เลขบัญชี
    # ปิดบัง = "X9999", ชื่อธนาคาร/ร้าน = ตัวอย่าง) — ไม่ใช่ข้อมูลจริง.
    # (a) PAY <ref> <merchant> — debit-card POS. Keep merchant name only.
    if re.match(r"^PAY\s+", d, re.I):
        m = re.match(r"^PAY\s+\d+\s*(.*)$", d, re.I)
        rest = (m.group(1) if m else "").strip()
        return rest or "ชำระเงิน"

    # Legacy: interest credit
    if re.match(r"^จากระบบเงินฝาก", d):
        return "ดอกเบี้ย"

    # (b) เติมเงิน WIDx#### <channel> — keep channel name (e.g. "K Plus W").
    m = re.match(r"^เติมเงิน\s+WIDx\d+[/\s]*(.*)$", d, re.I)
    if m:
        ch = m.group(1).strip(" /")
        return f"เติมเงิน {ch}".strip() if ch else "เติมเงิน"

    # (f) "<ธนาคารไทย> (<CODE>) /X####" — inter-bank ref only, no person.
    # MUST come before (c)/(d) because it shares bank-name tokens.
    # ไทย: อ้างอิงโอนข้ามธนาคารที่มีแต่เลขบัญชี ไม่มีชื่อคน เช่น
    #      "<ธนาคาร> (KBNK) /X9999" → คืน "รับโอน (<ธนาคาร>)".
    m = re.match(
        r"^(" + "|".join(_SCB_BANK_NAMES) + r"|ธ\.?ก\.?ส\.?)\s*"
        r"\(([A-Z]{2,6})\)\s*/X\d+\s*$",
        d,
    )
    if m:
        return f"รับโอน ({m.group(1)})"

    # (e) "จ่ายบิล <ผู้รับ>" — bill payment. Keep the "จ่ายบิล" prefix so
    # categorize() can route to home, while a merchant inside (e.g. "วัตสัน")
    # still wins via earlier ordered rules (health checked before home).
    if re.match(r"^จ่ายบิล\s+", d):
        return d

    # (d) "รับโอนจาก <BANK> x#### <ชื่อ>" — incoming transfer with payer name.
    m = re.match(r"^รับโอนจาก\s+([A-Z]{2,6})\s+x\d+\s*(.*)$", d, re.I)
    if m:
        bank = m.group(1).upper()
        name = m.group(2).strip()
        return f"รับโอนจาก ({bank}) {name}".strip() if name else f"รับโอนจาก ({bank})"

    # (c) "โอนไป <BANK> x#### <ชื่อ>" — outgoing transfer with payee name.
    m = re.match(r"^โอนไป\s+([A-Z]{2,6})\s+x\d+\s*(.*)$", d, re.I)
    if m:
        bank = m.group(1).upper()
        name = m.group(2).strip()
        return f"โอนไป ({bank}) {name}".strip() if name else f"โอนไป ({bank})"

    # ── English fallback prefixes (defensive — for future English SCB
    # statements). We rely on simple prefix matches because English SCB
    # descriptions seen elsewhere tend to start with the action verb.
    # Order: bill payment / deposit / withdraw before generic transfer/payment.
    m = re.match(r"^Bill\s*Payment\s*(.*)$", d, re.I)
    if m:
        rest = m.group(1).strip()
        return f"จ่ายบิล {rest}".strip() if rest else "จ่ายบิล"
    m = re.match(r"^Deposit\s*(.*)$", d, re.I)
    if m:
        return "ฝากเงิน"
    m = re.match(r"^Interest\s*(.*)$", d, re.I)
    if m:
        return "ดอกเบี้ย"
    m = re.match(r"^Withdraw(?:al)?\s*(.*)$", d, re.I)
    if m:
        return "ถอนเงินสด"
    m = re.match(r"^Fee\s*(.*)$", d, re.I)
    if m:
        return "ค่าธรรมเนียม"
    # Generic Transfer/Payment — conservative outgoing label; categorize()
    # falls back to "other" when no merchant keyword survives.
    m = re.match(r"^Transfer\s*(.*)$", d, re.I)
    if m:
        rest = m.group(1).strip()
        return f"โอนเงิน {rest}".strip() if rest else "โอนเงิน"
    m = re.match(r"^Payment\s*(.*)$", d, re.I)
    if m:
        rest = m.group(1).strip()
        return f"ชำระเงิน {rest}".strip() if rest else "ชำระเงิน"

    # Legacy inter-bank fallback (kept for back-compat with previous fixtures
    # where description was a free-form Thai bank name without the new
    # KBANK/KTB+xNNNN tokens). Drops "/X####" then routes via _scb_extra.
    legacy = re.sub(r"/X\d+\s*", "", d).strip()
    label: str | None = None
    label_keywords: list[str] = []
    if re.search(r"กสิกรไทย|KBANK", legacy, re.I):
        label = "รับโอน (K-Bank)"
        label_keywords = [r"กสิกรไทย", r"KBANK", r"รับโอน"]
    elif re.search(r"กรุงไทย|KTB", legacy, re.I):
        label = "รับโอน (กรุงไทย)"
        label_keywords = [r"กรุงไทย", r"KTB", r"รับโอน"]
    elif re.search(r"กรุงเทพ|BBL", legacy, re.I):
        label = "รับโอน (กรุงเทพ)"
        label_keywords = [r"กรุงเทพ", r"BBL", r"รับโอน"]

    if label is not None:
        extra = _scb_extra(legacy, label_keywords)
        return f"{label} {extra}".strip() if extra else label

    return legacy


def _scb_prev_desc(lines: list[str], i: int) -> str:
    # รับ: list บรรทัดทั้งหมด + index แถวปัจจุบัน · คืน: บรรทัด "ก่อนหน้า" เป็น
    # desc (SCB layout เก่าวางชื่อร้านไว้บรรทัดบนของแถวธุรกรรม). ถ้าไม่มีบรรทัด
    # ก่อนหน้า หรือบรรทัดนั้นเป็น noise/แถวธุรกรรมอื่น → คืน "" (ไม่ใช่ desc).
    if i <= 0:
        return ""
    p = lines[i - 1]
    if _SCB_NOISE.match(p) or _SCB_TX.match(p) or _SCB_IN.match(p):
        return ""
    return p


def parse_scb(raw: str) -> list[dict]:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    txs: list[dict] = []
    for i, line in enumerate(lines):
        if _SCB_NOISE.match(line):
            continue

        im = _SCB_IN.match(line)
        if im:
            try:
                # SCB ใช้ปี ค.ศ. 2 หลัก → บวก 2000 (เช่น 24 → 2024).
                yr = 2000 + int(im.group(3))
                amt = float(im.group(5).replace(",", ""))
            except ValueError:
                continue
            if amt > 0:
                dt = f"{yr}-{im.group(2).zfill(2)}-{im.group(1).zfill(2)}"
                inline_desc = (im.group(7) or "").strip()
                desc_source = inline_desc or _scb_prev_desc(lines, i)
                merchant = _scb_merchant(desc_source) or "ดอกเบี้ย"
                txs.append({
                    "date": dt,
                    "merchant": merchant,
                    "amount": amt,
                    "type": "ฝาก",
                    "category": "income",
                })
            continue

        m = _SCB_TX.match(line)
        if not m:
            continue
        try:
            year = 2000 + int(m.group(3))
            amount = float(m.group(6).replace(",", ""))
        except ValueError:
            continue
        if amount == 0:
            continue
        date = f"{year}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
        # Prefer inline description (same-line trailing text after balance);
        # fall back to previous-line description for older SCB layouts where
        # the merchant/payee line preceded the transaction row.
        inline_desc = (m.group(8) or "").strip()
        desc_source = inline_desc or _scb_prev_desc(lines, i)
        merchant = _scb_merchant(desc_source)
        is_credit = m.group(4) == "X1"
        tx_type = "ฝาก" if is_credit else "ถอน"
        txs.append({
            "date": date,
            "merchant": merchant or ("รับโอนเงิน" if is_credit else "ธุรกรรม"),
            "amount": amount if is_credit else -amount,
            "type": tx_type,
            "category": categorize(merchant, tx_type, is_credit),
        })
    return txs


# ============================================================
# Public API (จุดเข้าเดียวที่ภายนอกเรียกใช้)
# ------------------------------------------------------------
# parse_statement() = entry point ที่ backend (/api/parse-pdf) + LINE PDF
# handler เรียก: ดึงข้อความ → detect_bank() → เลือก parser ให้ตรงเจ้า.
# ถ้า detect ไม่ออก ("unknown") จะ fallback ลองทุก parser ตามลำดับ แล้ว
# คืนอันแรกที่ได้ผล — กัน statement รูปแบบเพี้ยนที่ header จับไม่ติด.
# ============================================================

def parse_statement(
    file_bytes: bytes,
    password: str | None = None,
) -> tuple[str, list[dict]]:
    """Parse a bank statement PDF. Returns (bank_id, transactions).

    ``password`` is forwarded to ``extract_pdf_text`` for password-protected
    PDFs and is never logged. See ``extract_pdf_text`` for the ValueError
    contract on locked / wrong-password PDFs.
    """
    text = extract_pdf_text(file_bytes, password=password)
    bank = detect_bank(text)

    if bank == "scb":
        return bank, parse_scb(text)
    if bank == "ktb":
        return bank, parse_ktb(text)
    if bank == "gsb":
        return bank, parse_gsb(text)
    if bank == "kbank":
        return bank, parse_kbank(text)

    # Fallback: try each, return first with results
    for fn, name in ((parse_kbank, "kbank"), (parse_ktb, "ktb"),
                     (parse_scb, "scb"), (parse_gsb, "gsb")):
        r = fn(text)
        if r:
            return name, r
    return "unknown", []

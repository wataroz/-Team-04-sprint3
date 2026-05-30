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
import re
from typing import Iterable

import pdfplumber


# ─── Text extraction ────────────────────────────────────────────────────────

def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from PDF, line-grouped by Y coordinate (matches pdf.js layout)."""
    out: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=2,
                keep_blank_chars=False,
                use_text_flow=False,
            )
            lines: dict[int, list[tuple[float, str]]] = {}
            for w in words:
                y = round(w["top"])
                lines.setdefault(y, []).append((w["x0"], w["text"]))
            for y in sorted(lines.keys()):
                items = sorted(lines[y], key=lambda t: t[0])
                line = re.sub(r"\s+", " ", " ".join(t[1] for t in items)).strip()
                if line:
                    out.append(line)
            out.append("")
    return "\n".join(out)


# ─── Bank detection ─────────────────────────────────────────────────────────

def detect_bank(text: str) -> str:
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


# ─── Category inference ─────────────────────────────────────────────────────

# Ordered list of (category, regex) pairs. First match wins, so put more
# specific / higher-priority patterns first (e.g. health before groceries so
# Watsons/Boots don't get mis-tagged, food-delivery before ride-hailing).
#
# Notes:
#   - Patterns are compiled with re.IGNORECASE; we lowercase + strip extras
#     before matching so both Thai and English work.
#   - Use \b boundaries on short English tokens to avoid false positives.
#   - 8-category contract shared with frontend/data.js — DO NOT add/remove
#     categories here without coordinating with the frontend.
_CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    # Health & pharmacy (priority over groceries so Watsons/Boots win)
    (
        "health",
        re.compile(
            r"\b(watsons?|boots|pharmacy|drug\s*store|hospital|clinic|dental|"
            r"bumrungrad|samitivej|bnh|bangkok\s*hospital|mahidol|rama|"
            r"siriraj|chula|aia|allianz|axa|prudential|insurance)\b|"
            r"วัตสัน|บูทส์|ร้านยา|ยา\s|โรงพยาบาล|รพ\.|คลินิก|ทันต|"
            r"บำรุงราษฎร์|สมิติเวช|รามา(?:ธิบดี)?|ศิริราช|จุฬา|ประกัน(?:สุขภาพ|ชีวิต)?",
            re.IGNORECASE,
        ),
    ),

    # Food delivery & food-court / restaurants / cafes (must come before
    # transport so "Bolt Food", "Grab Food", "Lineman" land in food)
    (
        "food",
        re.compile(
            r"\b(grab\s*food|grabfood|food\s*panda|foodpanda|line\s*man|lineman|"
            r"robinhood|bolt\s*food|wongnai|food\s*court|"
            r"starbucks|café|cafe|coffee|amazon|mcdonald'?s?|mcdo|kfc|burger\s*king|"
            r"pizza(?:\s*hut|\s*company)?|sushi|ramen|noodle|"
            r"after\s*you|dessert|bingsu|bakery|donut|krispy|swensen'?s?|"
            r"shabu|sukishi|mk\s*restaurant|mk\s*gold|mk\s*live|hotpot|yakiniku|"
            r"texas\s*chicken|bonchon|chester'?s?|santa\s*fe|s&p|sizzler)\b|"
            r"กาแฟ|อะเมซอน|อเมซอน|สตาร์บัค|เคเอฟซี|แมค|เบเกอรี่|เค้ก|"
            r"ร้านอาหาร|อาหาร(?:ตามสั่ง|จานเดียว)?|กระเพรา|กะเพรา|ส้มตำ|"
            r"ก๋วยเตี๋ยว|สุกี้|ชาบู|หม่าล่า|ราเมง|ราเมน|ข้าวมันไก่|ข้าวขาหมู|"
            r"ข้าวแกง|ผัดไทย|โจ๊ก|ก๋วยจั๊บ|เซเว่น(?=.*(?:ร้าน|อาหาร))",
            re.IGNORECASE,
        ),
    ),

    # Transport / fuel / ride-hailing / airlines (grab/bolt only if not "food")
    (
        "transport",
        re.compile(
            r"\b(grab(?!\s*food)|bolt(?!\s*food)|taxi|uber|gojek|"
            r"bts|mrt|arl|airport\s*rail|skytrain|sky\s*train|expressway|tollway|"
            r"shell|esso|ptt|caltex|bangchak|fuel|gasoline|petrol|"
            r"thai\s*airways|air\s*asia|airasia|nok\s*air|bangkok\s*airways|"
            r"thai\s*smile|thai\s*lion|vietjet|emirates|"
            r"airline|airways|airport|flight)\b|"
            r"แท็กซี่|รถไฟ(?:ฟ้า)?|รถเมล์|รถตู้|รถทัวร์|วินมอเตอร์ไซค์|"
            r"พีทีที|บางจาก|เชลล์|เอสโซ่|คาลเท็กซ์|น้ำมัน|ปั๊ม(?:น้ำมัน)?|"
            r"ทางด่วน|ค่าทาง|ตั๋วเครื่องบิน|สายการบิน|การบินไทย|แอร์เอเชีย|นกแอร์",
            re.IGNORECASE,
        ),
    ),

    # Entertainment / subscriptions / cinema / gaming
    (
        "entertain",
        re.compile(
            r"\b(netflix|spotify|youtube(?:\s*premium|\s*music)?|disney\+?|"
            r"disney\s*plus|hbo|apple\s*music|apple\s*tv|prime\s*video|"
            r"iqiyi|we\s*tv|wetv|viu|joox|tidal|"
            r"major\s*cineplex|major|sf\s*cinema|sfx|sfw|cineplex|cinema|imax|"
            r"steam(?:powered)?|ps\s*store|playstation|psn|nintendo|"
            r"xbox|epic\s*games|garena|riot\s*games|"
            r"karaoke|concert)\b|"
            r"โรงหนัง|โรงภาพยนตร์|เมเจอร์|หนัง|ภาพยนตร์|เกม|คอนเสิร์ต|คาราโอเกะ",
            re.IGNORECASE,
        ),
    ),

    # Home & bills / utilities / rent / internet / mobile
    (
        "home",
        re.compile(
            r"\b(rent|electric(?:ity)?\s*bill|water\s*bill|wifi|internet|"
            r"tot|ais(?:\s*fibre|\s*postpaid|\s*prepaid)?|true(?:move|\s*online|"
            r"\s*vision|\s*id)?|dtac|3bb|nt\s*broadband|"
            r"pea|mea|metropolitan\s*electricity|provincial\s*electricity|"
            r"apartment|condo|condominium|dormitory|"
            r"bill\s*payment|utility|utilities)\b|"
            r"กฟน|กฟภ|การประปา|ประปา|ค่าไฟ(?:ฟ้า)?|ค่าน้ำ|ค่าเช่า|ค่าเน็ต|"
            r"ทรูมูฟ|ทรูออนไลน์|ทรูวิชั่นส์|เอไอเอส|ดีแทค|"
            r"เน็ตบ้าน|นิติบุคคล|ชำระบิล|ค่าก๊าซ|หอพัก|อพาร์ทเมนท์|คอนโด",
            re.IGNORECASE,
        ),
    ),

    # Groceries / supermarkets / convenience stores
    (
        "groceries",
        re.compile(
            r"\b(7[-\s]?eleven|seven\s*eleven|family\s*mart|familymart|lawson|"
            r"mini\s*big\s*c|"
            r"tops(?:\s*daily|\s*market|\s*super)?|big\s*c|lotus(?:\s*go\s*fresh|"
            r"\s*express|s)?|tesco(?:\s*lotus)?|makro|villa\s*market|"
            r"gourmet\s*market|foodland|home\s*fresh\s*mart|cj\s*more|cj\s*supermarket|"
            r"cp\s*fresh\s*mart|cp\s*axtra|cp\s*meiji|cp\s*pork|cp\s*all|"
            r"market|supermarket|grocery|groceries|minimart)\b|"
            r"เซเว่น|เซเว่นอีเลฟเว่น|แฟมิลี่มาร์ท|แฟมิลี่|ตลาดสด|ตลาดนัด|"
            r"ซูเปอร์มาร์เก็ต|มินิมาร์ท|แม็คโคร|ท็อปส์|โลตัส|บิ๊กซี|วิลล่า|กูร์เมต์",
            re.IGNORECASE,
        ),
    ),

    # Shopping / marketplaces / department stores / fashion
    (
        "shopping",
        re.compile(
            r"\b(shopee|lazada|jd\s*central|kaidee|amazon(?:\.com)?|aliexpress|"
            r"uniqlo|h&m|zara|muji|nike|adidas|puma|new\s*balance|"
            r"central(?:world|\s*world|\s*plaza|\s*department)?|robinson|"
            r"emporium|emquartier|emsphere|paragon|siam\s*paragon|terminal\s*21|"
            r"icon\s*siam|iconsiam|mega\s*bangna|mbk|the\s*mall|"
            r"ikea|home\s*pro|homepro|do\s*home|dohome|index\s*living|"
            r"power\s*buy|j\.?\s*i\.?\s*b|jaymart|advice|banana\s*it|"
            r"daiso|miniso|loft|"
            r"mall|plaza|store|department|outlet|boutique)\b|"
            r"ช้อปปี้|ลาซาด้า|ห้าง(?:สรรพสินค้า)?|เซ็นทรัล|โรบินสัน|พารากอน|"
            r"เอ็มควอเทียร์|ไอคอนสยาม|โฮมโปร|โดโฮม|พาวเวอร์บาย|"
            r"ร้านค้า|ร้านขาย",
            re.IGNORECASE,
        ),
    ),
]


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


def categorize(merchant: str, _type: str, incoming: bool) -> str:
    """Map a transaction merchant string to one of the 8 fixed categories.

    Returns 'income' when the transaction is incoming, otherwise tries the
    ordered keyword rules. Unknown merchants fall back to 'other' — never
    raises so callers can always trust the result.
    """
    if incoming:
        return "income"

    m = _normalize(merchant)
    if not m:
        return "other"

    for cat, pat in _CATEGORY_RULES:
        if pat.search(m):
            return cat
    return "other"


# ─── K-Bank parser ──────────────────────────────────────────────────────────

_KBANK_LINE = re.compile(
    r"^(\d{2})-(\d{2})-(\d{2})\s+\d{2}:\d{2}\s+"
    r"(รับโอนเงิน|โอนเงิน|ชำระเงิน|ถอนเงินสด|ค่าธรรมเนียม|ดอกเบี้ย|ฝากเงินสด|ฝาก|ถอน)\s+"
    r"([\d,]+\.\d{2})\s+[\d,]+\.\d{2}\s+(.+)$"
)
_KBANK_DATE_LINE = re.compile(r"^\d{2}-\d{2}-\d{2}\s")
_KBANK_SKIP = re.compile(
    r"^(KBPDF|ออกโดย|หน้าที่|PAGE/OF|ที่ DD\.|ชื่อบัญชี|สาขา|เลขที่|รอบระหว่าง|รวมถอน|รวมฝาก|"
    r"ยอดยกไป|ยอดคงเหลือ|วันที่ เวลา|วันที่มีผล|ช่องทาง|\(บาท\)|รายละเอียด|--\s*\d+\s*of|\d+/\d+\(\d+\))"
)
_KBANK_INCOMING = {"รับโอนเงิน", "ฝาก", "ฝากเงินสด", "ดอกเบี้ย"}


def parse_kbank(raw: str) -> list[dict]:
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    txs: list[dict] = []
    i = 0
    while i < len(lines):
        m = _KBANK_LINE.match(lines[i])
        if not m:
            i += 1
            continue

        desc = m.group(6)
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
            amount = float(m.group(5).replace(",", ""))
        except ValueError:
            i += 1
            continue
        if amount == 0:
            i += 1
            continue

        tx_type = m.group(4)
        incoming = tx_type in _KBANK_INCOMING
        date = f"20{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

        merchant = desc
        merchant = re.sub(
            r"^(K PLUS|EDC/K SHOP/MYQR|MAKE by KBank|Internet/Mobile [A-Z]+|ATM[^\s]*|ตู้[^\s]*|"
            r"ต่างธนาคาร|MyMo by GHB|SCB EASY|Krungthai NEXT|Bualuang mBanking)\s*",
            "", merchant, flags=re.I,
        )
        merchant = re.sub(r"^(จาก|โอนไป)\s+(?:[A-Z]{2,5}\s+)?(?:พร้อมเพย์\s+)?(?:X\d+\s+)?", "", merchant)
        merchant = re.sub(r"\(\s*ชื่อบัญชี:[^)]*\)?", "", merchant)
        merchant = merchant.replace("++", "")
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


# ─── GSB parser ─────────────────────────────────────────────────────────────

_GSB_LINE = re.compile(
    r"^(\d{2})/(\d{2})/(\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+\d+\s+\d+"
)
_GSB_DEPOSIT = re.compile(r"\b(Deposit|ฝาก|รับโอน|เงินเข้า|Interest|ดอกเบี้ย)\b", re.I)
_GSB_NOISE = re.compile(
    r"^(ข้อมูลรายการ|โดยผู้ใช้|หน้า \d+|-- \d+|รายการเดินบัญชี|ชื่อบัญชี|ประเภทบัญชี|"
    r"เลขที่บัญชี|สาขาเจ้าของ|รอบวันที่|ยอดยกมา|วันที่\s+รายการ|สาขา\s+รายการ)"
)


def _gsb_desc_map(desc: str) -> str:
    if re.search(r"C Scan B", desc, re.I):
        return "C Scan B (QR)"
    if re.search(r"Bill Payment", desc, re.I):
        return "ชำระบิล"
    if re.search(r"SAV Deposit", desc, re.I):
        return "รับโอนเงิน"
    if re.search(r"Interest|ดอกเบี้ย", desc, re.I):
        return "ดอกเบี้ย"
    if re.search(r"Transfer", desc, re.I) and re.search(r"Deposit", desc, re.I):
        return "รับโอนเงิน"
    if re.search(r"Transfer", desc, re.I):
        return "โอนเงิน"
    if re.search(r"Payment", desc, re.I):
        return "ชำระเงิน"
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
            year = int(m.group(3)) - 543
            amount = float(m.group(5).replace(",", ""))
        except ValueError:
            continue
        if amount == 0:
            continue
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


# ─── KTB parser ─────────────────────────────────────────────────────────────

_KTB_LINE = re.compile(
    r"^(\d{2})/(\d{2})/(\d{2})\s+(.+)\s+([\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s+(\d{3,4})\s*$"
)
_KTB_DEPOSIT = re.compile(r"^(เงินโอนเข้า|ฝากเงิน|ดอกเบี้ย|รับเงิน|รับโอน)")
_KTB_NOISE = re.compile(
    r"^(รายการเดินบัญชี|รายการบัญชีระหว่าง|วันที่ส่ง|ชื่อบัญชี|ประเภทบัญชี|สาขา|เลขที่บัญชี|ที่อยู่|"
    r"วงเงิน|สกุลเงิน|วันที่/เวลา|บริษัท ธนาคาร|เลขที่ 35|ติดต่อ|-- \d+|หน้า \d+|ยอดยกมา|รวม|"
    r"จำนวนหน้า|รายการถอนทั้งหมด|รายการฝากทั้งหมด|C/F)"
)
_KTB_TIME = re.compile(r"^\d{2}:\d{2}")


def _ktb_merchant(desc: str) -> str:
    if re.search(r"เงินโอนเข้า.*พร้อมเพย์|MORISD|NMIDSD", desc, re.I):
        return "รับโอน (PromptPay)"
    if re.search(r"เงินโอนเข้า|NBSDT", desc, re.I):
        return "รับโอนเงิน"
    if re.search(r"โอนเงินออก.*พร้อมเพย์|MORWSW|MORISW|NMIDSW", desc, re.I):
        return "โอนออก (PromptPay)"
    if re.search(r"โอนเงินออก|NBSWT", desc, re.I):
        return "โอนเงินออก"
    if re.search(r"CGSWP", desc, re.I):
        return "ชำระ QR Code"
    if re.search(r"จ่ายค่าสินค้า|MORPSW", desc, re.I):
        return "ชำระค่าสินค้า/บริการ"
    if re.search(r"ถอนเงิน", desc, re.I):
        return "ถอนเงินสด"
    if re.search(r"ฝากเงิน", desc, re.I):
        return "ฝากเงิน"
    if re.search(r"ดอกเบี้ย", desc, re.I):
        return "ดอกเบี้ย"
    if re.search(r"ค่าธรรมเนียม", desc, re.I):
        return "ค่าธรรมเนียม"
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


# ─── SCB parser ─────────────────────────────────────────────────────────────

_SCB_TX = re.compile(
    r"^(\d{2})/(\d{2})/(\d{2})\s+\d{2}:\d{2}\s+(X1|X2)\s+(\S+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
)
_SCB_IN = re.compile(
    r"^(\d{2})/(\d{2})/(\d{2})\s+\d{2}:\d{2}\s+IN\s+\S+\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
)
_SCB_NOISE = re.compile(
    r"^(ธนาคารไทยพาณิชย์|THE SIAM COMMERCIAL|ใบแจ้งรายการ|STATEMENT OF|สาขา$|ชื่อ - สกุล|Name$|"
    r"ที่อยู่$|Address$|เลขที่บัญชี$|Account No|^วันที่$|^Date$|Date Time Code|วันที่ เวลา รายการ|"
    r"ยอดเงินคงเหลือยกมา|BALANCE BROUGHT|TOTAL AMOUNTS|TOTAL ITEMS|เอกสารฉบับนี้|This document|"
    r"หน้า \d+|-- \d+ of|Balance/Baht|Debit/Credit)"
)


def _scb_merchant(desc: str) -> str:
    if not desc:
        return "ธุรกรรม"
    d = re.sub(r"/X\d+\s*", "", desc)
    d = re.sub(r"\s+", " ", d).strip()
    if re.match(r"^PAY\s+", d, re.I):
        return re.sub(r"^PAY\s+\d+\s*", "", d, flags=re.I).strip() or "ชำระเงิน"
    if re.match(r"^จากระบบเงินฝาก", d):
        return "ดอกเบี้ย"
    if re.search(r"กสิกรไทย|KBANK", d, re.I):
        return "รับโอน (K-Bank)"
    if re.search(r"กรุงไทย|KTB", d, re.I):
        return "รับโอน (กรุงไทย)"
    if re.search(r"กรุงเทพ|BBL", d, re.I):
        return "รับโอน (กรุงเทพ)"
    return d


def _scb_prev_desc(lines: list[str], i: int) -> str:
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
                yr = 2000 + int(im.group(3))
                amt = float(im.group(4).replace(",", ""))
            except ValueError:
                continue
            if amt > 0:
                dt = f"{yr}-{im.group(2).zfill(2)}-{im.group(1).zfill(2)}"
                merchant = _scb_merchant(_scb_prev_desc(lines, i)) or "ดอกเบี้ย"
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
        merchant = _scb_merchant(_scb_prev_desc(lines, i))
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


# ─── Public API ─────────────────────────────────────────────────────────────

def parse_statement(file_bytes: bytes) -> tuple[str, list[dict]]:
    """Parse a bank statement PDF. Returns (bank_id, transactions)."""
    text = extract_pdf_text(file_bytes)
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

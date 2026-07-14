"""
MoneyMind — Seed merchant dictionary (ฐานร้านดังไทย pre-load).

แก้ปัญหา "cold start" ของ Learning Loop: user ใหม่ที่อัปโหลด statement แรก
ยังไม่มี MerchantOverride ของตัวเอง → เดิมร้านดังหลายร้านตกไป "other".
ตารางนี้ pre-load ร้านค้าสาธารณะที่รู้จักทั่วไป (~45 แบรนด์) เป็น "ชั้นกลาง"
ระหว่าง Learning Loop (per-user) กับ regex keyword เพื่อให้จัดหมวดถูกตั้งแต่
รายการแรก โดยไม่เสีย personalization.

ลำดับความสำคัญ (decision order) — ดู categorize() ใน pdf_parser.py:
    1. MerchantOverride (per-user)  ← ชนะเสมอ (เขียนทับตอน insert ใน app.py)
    2. Seed dictionary (ตารางนี้)   ← ชั้นกลาง
    3. Regex _CATEGORY_RULES
    4. "other" (fallback)

หมายเหตุ:
    - key = "ชื่อแบรนด์ดิบ" อ่านง่าย. pdf_parser.py จะ normalize ด้วย
      _normalize() (ตัวเดียวกับที่ categorize ใช้กับ merchant จริง) ตอน import
      → ได้ _SEED_LOOKUP ที่เทียบตรงกับ merchant ที่ผ่าน normalize แล้ว.
    - ร้านที่ชื่อมี "-" (เช่น 7-Eleven) เก็บหลาย variant ทั้งขีดและช่องว่าง
      เพราะ _normalize() **ไม่** แทน "-" ด้วยช่องว่าง (แทนแค่ . _ / \\ |) →
      statement จริงเขียนได้ทั้ง "7-Eleven" / "7 Eleven" / "7-11".
    - value ต้องเป็น 1 ใน 8 หมวดที่จัดจากชื่อร้าน (food/transport/shopping/
      home/entertain/groceries/health). ไม่ seed "income" (route ด้วย flag)
      และไม่ seed "other" (เป็น fallback).
    - ห้ามใส่ PII — เฉพาะแบรนด์ร้านค้าสาธารณะที่รู้จักทั่วไปเท่านั้น.
    - แบรนด์กำกวมที่ใช้ทั้ง ride-hailing และ food (Grab/Bolt): seed ทั้งคู่
      โดยให้ 2-token "Grab Food" → food และ 1-token "Grab" → transport.
      _seed_lookup() ใช้ sliding-window match ทุกจุดเริ่มต้นในสตริง + เลือก
      แมตช์ที่ยาวที่สุดทั้งสตริงชนะ จึงให้ "Grab Food" ชนะ "Grab" อัตโนมัติ
      ไม่ว่าจะอยู่ตรงไหนของสตริง (mirror เจตนาของ regex ที่ดัก *Food ก่อน ride).

    - **AMBIGUOUS_SEED_KEYS (REW review, 14 ก.ค. 2026)**: sliding-window ทำให้
      seed key จับได้ทุกตำแหน่งในสตริง (ไม่ใช่แค่หัว) — ดีสำหรับแบรนด์เฉพาะเจาะจง
      (เช่น "ชำระบิล AIS") แต่อันตรายสำหรับ key สั้น/เป็นคำทั่วไปที่อาจโผล่มาใน
      บริบทอื่นที่ไม่เกี่ยวกับแบรนด์เลย (เช่น "สถานะ true ปกติ" ไม่เกี่ยวกับ True
      Corp แต่ดันจับ "true" กลางสตริงได้). ตารางนี้แยก key เหล่านั้นเป็น
      "low-confidence" — pdf_parser.py จะให้ match ได้เฉพาะตอนที่สตริง merchant
      ทั้งหมด (หลัง normalize) ตรงกับ key **แบบเป๊ะทั้งสตริง** เท่านั้น (ยังผ่าน
      exact-match layer เดิม, ไม่เสีย) แต่จะถูกข้ามใน sliding-window layer เสมอ
      (ต่อให้เจอ substring ตรงกัน) — เพราะสตริงที่ยาวกว่าที่มี key แค่เป็นส่วนหนึ่ง
      คือสัญญาณว่าอาจเป็นคำทั่วไปที่ปนมา ไม่ใช่ตัวแบรนด์จริง.

      เกณฑ์คัดเข้า (ตรวจทั้ง SEED_MERCHANTS อย่างเป็นระบบ ไม่ใช่แค่ 8 ตัวที่ REW
      เจอตอนแรก):
        - เป็นคำอังกฤษทั่วไปที่มีความหมายอื่นนอกเหนือจากชื่อแบรนด์ (True, Shell,
          Central, Steam-like, Tops, Boots, Lotus) — เสี่ยงโผล่ในข้อความสถานะ/
          รายละเอียดทั่วไปที่ไม่เกี่ยวกับร้าน
        - เป็นอักษรย่อสั้น (≤3 ตัว) ที่ไม่เฉพาะเจาะจงพอ (NT, JIB, BNH, MEA, PEA,
          BTS) — เสี่ยงชนกับตัวย่ออื่น/ชื่อวงดนตรี(BTS)/คำละตินทั่วไป(MEA)
        - เป็นนามสกุลคนทั่วไป (Robinson, Lawson) — เสี่ยงเฉพาะเพราะ SCB parser
          (_scb_merchant) ดึง "ชื่อผู้รับ/ผู้โอน" จริงจาก desc ใส่ลง merchant field
          ตรงๆ (ดู pattern (c)/(d) ใน pdf_parser.py) → ถ้า user โอนเงินหาคนชื่อ
          Robinson/Lawson จริง จะเจอ surname ปนกับ transaction ตรงๆ ไม่ใช่แค่
          ทฤษฎี

      ข้อยกเว้น (ตั้งใจ **ไม่** ใส่ในลิสต์นี้ แม้สั้น/ดูเสี่ยงผิวเผิน):
        - **AIS** (3 ตัว, สั้นเท่า NT) — แต่ "ais" ไม่ใช่คำอังกฤษ/ไทยทั่วไป ไม่มี
          ความหมายอื่นให้ชนกัน + เป็นเคสที่ต้องคง sliding-window ไว้ตามที่ทดสอบแล้ว
          ("ชำระบิล AIS" ต้องยัง match ได้กลางสตริง)
        - **3BB** — REW เคยเอ่ยถึงเป็นตัวอย่างที่ "เสี่ยงน้อยกว่า" เพราะมีเลขนำหน้า
          ติดกับตัวอักษร (option b ในโจทย์) → ตัวเลขในสตริงสั้นแบบนี้แทบไม่ชนกับ
          คำทั่วไปโดยบังเอิญ จึงยังคง sliding-window เต็มรูปแบบ
        - **Grab / Bolt** — ก็เป็นคำอังกฤษทั่วไป (กริยา) เหมือนกัน แต่เป็นฟีเจอร์
          หลักที่ตั้งใจให้ match ได้ทุกตำแหน่ง (ambiguous ride vs food, ดู
          longest-match ด้านบน) — ความเสี่ยงที่เหลือ (คำว่า "grab"/"bolt" ในความหมาย
          ทั่วไปโผล่ในรายละเอียด statement ไทย) ถือว่าต่ำกว่าความเสี่ยงของคำอย่าง
          "true"/"boots"/"pea" มาก เพราะ statement ธนาคารเป็นข้อความสั้นแบบโค้ด
          ไม่ใช่ประโยคภาษาอังกฤษที่ใช้คำกริยาทั่วไป — ยอมรับความเสี่ยงที่เหลือนี้
          (documented trade-off, ไม่ใช่มองข้าม)
        - **MRT** — สั้นเท่า NT/JIB แต่ไม่ใช่คำ/อักษรย่อที่ชนกับความหมายอื่นที่รู้จัก
          ทั่วไป จึงยังคง sliding-window (ความเสี่ยงต่ำกว่า BTS ที่ชนกับชื่อวงดนตรี)

      **ไม่ได้แก้ทุกจุดที่เสี่ยงแบบเดียวกัน**: ระหว่างตรวจพบว่า `_CATEGORY_RULES`
      (regex ชั้นถัดไปจาก seed) ก็มี bare-word ที่ optional/ไม่บังคับ suffix แบบ
      เดียวกันสำหรับหลายคำ (เช่น "tops"/"boots"/"bnh"/"mea"/"pea"/"bts"/"shell"/
      "central"/"robinson"/"jib"/"lawson" — ทดสอบแล้วแมตช์แม้ไม่มี seed layer) —
      แก้เฉพาะ "true" (บังคับ suffix move/online/vision/id) เพราะเป็นเคสที่ระบุชัด
      ในการรีวิวรอบนี้; ที่เหลือเป็นบั๊กเดิมที่มีมาก่อน seed layer (ไม่ใช่ regression
      จากงานรอบนี้) — ปล่อยไว้เป็น backlog ให้ user ตัดสินใจแยกต่างหาก (ขอบเขต
      ใหญ่กว่าการรีวิว seed dictionary รอบนี้).
"""

from __future__ import annotations

# แบรนด์ดิบ → หมวด. pdf_parser.py จะ normalize key ตอน import.
SEED_MERCHANTS: dict[str, str] = {
    # ── food ───────────────────────────────────────────────
    "Café Amazon": "food",
    "Cafe Amazon": "food",
    "Starbucks": "food",
    "KFC": "food",
    "McDonald's": "food",
    "Pizza Hut": "food",
    "MK Restaurant": "food",
    "Sizzler": "food",
    "Bonchon": "food",
    "Swensen's": "food",
    "Burger King": "food",
    # แบรนด์กำกวม (food variant ต้องมาก่อน transport ผ่าน longest-first prefix)
    "Grab Food": "food",
    "GrabFood": "food",
    "Bolt Food": "food",

    # ── transport ──────────────────────────────────────────
    "Grab": "transport",
    "Bolt": "transport",
    "BTS": "transport",
    "MRT": "transport",
    "PTT Station": "transport",
    "Shell": "transport",
    "Esso": "transport",
    "Bangchak": "transport",
    "Thai Airways": "transport",
    "AirAsia": "transport",

    # ── shopping ───────────────────────────────────────────
    "Shopee": "shopping",
    "Lazada": "shopping",
    "Central": "shopping",
    "Robinson": "shopping",
    "Uniqlo": "shopping",
    "IKEA": "shopping",
    "HomePro": "shopping",
    "Power Buy": "shopping",
    "JIB": "shopping",

    # ── home / bills / utilities ───────────────────────────
    "AIS": "home",
    "True": "home",
    "Dtac": "home",
    "3BB": "home",
    "NT": "home",
    "MEA": "home",
    "PEA": "home",

    # ── entertain ──────────────────────────────────────────
    "Netflix": "entertain",
    "Spotify": "entertain",
    "YouTube Premium": "entertain",
    "Disney+": "entertain",
    "Disney Plus": "entertain",
    "Major Cineplex": "entertain",
    "SF Cinema": "entertain",
    "Steam": "entertain",
    "Garena": "entertain",

    # ── groceries / convenience / supermarket ──────────────
    # 7-Eleven: เก็บหลาย variant เพราะ _normalize ไม่แตะ "-"
    "7-Eleven": "groceries",
    "7 Eleven": "groceries",
    "7-11": "groceries",
    "7 11": "groceries",
    "Lotus's": "groceries",
    "Lotus": "groceries",
    "Big C": "groceries",
    "Tops": "groceries",
    "Makro": "groceries",
    "CJ More": "groceries",
    "FamilyMart": "groceries",
    "Family Mart": "groceries",
    "Lawson": "groceries",

    # ── health / pharmacy / hospital ───────────────────────
    "Watsons": "health",
    "Boots": "health",
    "Bumrungrad": "health",
    "Samitivej": "health",
    "BNH": "health",
    "Fascino": "health",
}


# Seed keys ที่ "กำกวม" (คำอังกฤษทั่วไป / อักษรย่อสั้นไม่เฉพาะเจาะจง / นามสกุลคน) —
# pdf_parser.py จะจำกัดให้ match ได้เฉพาะตอนสตริง merchant ทั้งหมดตรงกับ key
# แบบเป๊ะ (exact full-string) เท่านั้น ไม่ให้ sliding-window จับที่ตำแหน่งอื่นใน
# สตริง (ดูเหตุผลรายตัว + เกณฑ์คัดเข้า/ข้อยกเว้นในคอมเมนต์หัวไฟล์ด้านบน).
AMBIGUOUS_SEED_KEYS: frozenset[str] = frozenset({
    # home — คำอังกฤษทั่วไป / อักษรย่อสั้น
    "True", "NT", "MEA", "PEA",
    # transport — ชนชื่อวงดนตรี (BTS) / คำอังกฤษทั่วไป (Shell)
    "BTS", "Shell",
    # shopping — คำอังกฤษทั่วไป / นามสกุลคน / อักษรย่อสั้น
    "Central", "Robinson", "JIB",
    # groceries — คำอังกฤษทั่วไป / นามสกุลคน
    "Lotus", "Tops", "Lawson",
    # health — คำอังกฤษทั่วไป / อักษรย่อสั้น
    "Boots", "BNH",
})

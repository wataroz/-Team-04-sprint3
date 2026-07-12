# แผนจัดระเบียบโค้ด (Code Cleanup Plan) — Readability-Only

> เจ้าของแผน: **PM** · Sprint 3 / Team 04 · อัปเดต 12 ก.ค. 2026
> เป้าหมาย: จัดโค้ดให้ **สบายตา อ่านง่าย + เพิ่มคอมเมนต์อธิบาย** โดย **ไม่แตะ logic**

---

## 0. ขอบเขต (สำคัญที่สุด)

งานนี้เป็น **readability-only** — ทำได้แค่:
- เพิ่ม **section header comment** แบ่งโซนในไฟล์
- เพิ่มคอมเมนต์อธิบาย block / function ที่ซับซ้อน
- จัดช่องว่าง / indent ให้สม่ำเสมอ
- เรียง import ให้เป็นระเบียบ (โดยไม่เปลี่ยนลำดับที่มีผลต่อ side-effect)
- จัดกลุ่มฟังก์ชัน/ตัวแปรที่เกี่ยวข้องให้อยู่ใกล้กัน (ถ้าย้ายแล้วพฤติกรรมไม่เปลี่ยน)

**ห้ามเด็ดขาด**: เปลี่ยน logic, เปลี่ยนชื่อ variable/function ที่ถูกอ้างถึงข้ามไฟล์, ลบโค้ด, reformat จน diff บวมเกินจำเป็น, แตะ `.env` / secrets

---

## 1. แบ่งงานตาม specialist

| Specialist | โซน | ไฟล์ที่รับผิดชอบ | บรรทัด | น้ำหนัก |
|-----------|-----|-----------------|--------|--------|
| **AJ** | Backend `.py` | `backend/app.py` (1661), `backend/line_bot.py` (1227), `backend/models.py` (290), `backend/db.py` (67), `scripts/run_migration.py` (211) | ~3456 | หนักสุด |
| **WA** | Logic/AI | `logic_ai/pdf_parser.py` (987) | ~987 | กลาง |
| **ACHI** | Frontend | `frontend/src/views.jsx` (3359), `frontend/src/app.jsx` (1036), `frontend/src/auth.jsx` (493), `frontend/src/data.js` (487), `frontend/index.html` (44) | ~5419 | หนักสุด |
| **BEST** | UX/UI | `ux_ui/styles.css` (4339), `ux_ui/src/ui.jsx` (585), `ux_ui/src/tweaks-panel.jsx` (568) | ~5492 | หนักสุด |

หมายเหตุ:
- `backend/__init__.py`, `logic_ai/__init__.py` ว่าง (0 บรรทัด) — **ข้าม**
- `ux_ui/src/*.jsx` เป็นไฟล์ UI component → มอบ **BEST** (เจ้าของโซน ux_ui) ตาม mapping โปรเจกต์
- ไฟล์ config (`Procfile`, `render.yaml`, `requirements.txt`, `.env*`, `manifest.webmanifest`) — **ไม่อยู่ในขอบเขต** งานนี้

---

## 2. Convention กลาง (ทุกคนยึดเหมือนกัน)

**ภาษาคอมเมนต์**: **ไทย** เป็นหลัก (ให้ทีมนักศึกษาอ่านง่าย) — ยกเว้นศัพท์เทคนิคคงคำอังกฤษได้ (`reply token`, `stacking context`, `pool_pre_ping`)

**รูปแบบ section header** — Python (`.py`):
```python
# ============================================================
# <ชื่อโซน>  เช่น: AI Provider Chain / LINE Webhook Handlers
# ============================================================
```

**รูปแบบ section header** — JS/JSX (`.jsx`, `.js`):
```javascript
// ============================================================
// <ชื่อโซน>  เช่น: Auth State / ChatPanel / i18n keys
// ============================================================
```

**รูปแบบ section header** — CSS:
```css
/* ============================================================
   <ชื่อโซน>  เช่น: Light Tokens / Dark Tokens / Responsive ≤1024px
   ============================================================ */
```

**คอมเมนต์อธิบายฟังก์ชัน**: 1–3 บรรทัดเหนือ function บอก "ทำอะไร + ทำไม" (เน้นเจตนา ไม่ใช่แปลโค้ดทีละบรรทัด) โดยเฉพาะจุดที่มี Lesson Learned (ดู CLAUDE.md #14–#21)

**ระดับการแตะ**: เพิ่ม/จัดเท่านั้น — ไม่แก้ค่า, ไม่ย้ายข้ามไฟล์, ไม่แตะ regex/token/SQL

---

## 3. Definition of Done + ข้อห้าม

**เสร็จเมื่อ**:
- [ ] แต่ละไฟล์มี section header แบ่งโซนชัดเจน
- [ ] ฟังก์ชัน/block ซับซ้อนมีคอมเมนต์อธิบายเจตนา (โดยเฉพาะ AI chain, OAuth verify, cascade delete, Learning Loop, bank regex, theme tokens)
- [ ] indent / ช่องว่างสม่ำเสมอทั้งไฟล์
- [ ] import จัดกลุ่ม (stdlib → third-party → local) โดยไม่กระทบ side-effect order
- [ ] **local test ผ่าน** — เว็บรันได้ (`py backend/app.py`), `test_parser.ipynb` ยังผ่าน, ChatPanel/OAuth flow ไม่พัง
- [ ] **REW review ผ่าน** ก่อน push

**ข้อห้าม (fail ทันทีถ้าละเมิด)**:
- ห้ามเปลี่ยน logic / ค่า config / ลำดับที่มี side-effect
- ห้ามเปลี่ยนชื่อ symbol ที่ถูกอ้างข้ามไฟล์ (route path, i18n key, CSS class, model field, function export)
- ห้ามลบโค้ดที่ทำงานอยู่ (แม้ดูเหมือน dead code — ให้ mark `# TODO: ตรวจว่าใช้ไหม` แทน)
- ห้าม reformat ทั้งไฟล์ด้วย auto-formatter จน diff บวม — เน้น diff อ่านรู้เรื่อง reviewable
- ห้ามแตะ `.env`, secrets, tokens, DATABASE_URL

---

## 4. ลำดับงาน

```
Phase 1 (parallel — ไม่ block กัน เพราะคนละโซนไฟล์):
   AJ (backend .py) ─┐
   WA (pdf_parser)  ─┤
   ACHI (frontend)  ─┼──►  Phase 2: REW review (10 ด้าน — เน้น diff/logic-unchanged)
   BEST (css/ux_ui) ─┘              │
                                    ▼
                          Phase 3: commit + push (WA)
                                    │
                                    ▼
                          Phase 4: NOTE อัปเดต Notion (รอ user confirm)
```

- **Phase 1 ทำขนานได้เต็มที่** — 4 คนแตะคนละไฟล์ ไม่มี merge conflict
- **REW** ตรวจย้ำว่า diff = readability เท่านั้น (logic byte-identical) ก่อน push
- ไม่มี dependency ข้ามโซน → ไม่ต้องรอกัน

---

## สรุปสถานะ

| หัวข้อ | สถานะ |
|--------|-------|
| ทำแล้ว | แผนแจกจ่ายงาน + สำรวจไฟล์จริง 14 ไฟล์ + convention กลาง |
| เหลือ | ลงมือจริง (AJ / WA / ACHI / BEST) → REW → push |
| ใครค้าง | ทั้ง 4 specialist (รอ user สั่งเริ่ม) |

**Next step ที่แนะนำ**: user confirm scope แล้ว delegate **AJ + WA + ACHI + BEST พร้อมกัน** (ขนานได้ ไม่ชนกัน) → ปิดท้ายด้วย **REW** ก่อน push

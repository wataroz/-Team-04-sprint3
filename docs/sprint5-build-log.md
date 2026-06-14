# Sprint 5 — Build Log

> รายการสิ่งที่ build เสร็จใน Sprint 5 + Evidence (ทดสอบยังไง / ดูได้ที่ไหน)

**อัปเดต**: 2026-06-14

---

## Build log

| # | สิ่งที่ build เสร็จ | Evidence (ทดสอบ/ดูได้ที่ไหน) |
|---|---|---|
| 1 | หน้าจอปรับขนาดได้ 4 ระดับ (มือถือ/แท็บเล็ต/โน้ตบุ๊ก/จอใหญ่) | Screenshot 5 หน้าหลักบนจอ 375px |
| 2 | LINE Bot ไม่ส่ง PDF ซ้ำอีก | Screenshot แชท LINE + ตรวจสอบในฐานข้อมูล ไม่มีรายการซ้ำ |
| 3 | รองรับ PDF ที่ใส่รหัสผ่าน (ทั้งใน LINE และเว็บ) | Screenshot + คลิป flow ใน LINE (ใส่รหัส 3 ครั้ง, หมดเวลา 5 นาที) |
| 4 | อ่าน statement ภาษาอังกฤษ + SCB ได้ถูกต้อง | ตารางเปรียบเทียบจำนวนรายการที่อ่านได้ ก่อน-หลัง (KBank ENG 0→276 รายการ, SCB 18→45 รายการ) |
| 5 | หน้า Settings 4 หมวด | Screenshot ทั้ง 4 แท็บ (โปรไฟล์/การแสดงผล/LINE/แจ้งเตือน) |
| 6 | ลบบัญชี + พักไว้ 30 วัน + ยกเลิกได้ + ดาวน์โหลดข้อมูล (PDPA) | Screenshot ขั้นตอนยืนยันลบบัญชี (3 ขั้น) + แบนเนอร์ยกเลิกการลบ |
| 7 | โลโก้ใหม่ + ติดตั้งเป็นแอปบนมือถือได้ | Screenshot "Install MoneyMind?" บน Android Chrome + ไอคอนหน้า home screen |
| 8 | สลับธีมสว่าง/มืด — จำค่าข้ามอุปกรณ์ | Screenshot toggle + แท็บสีของระบบเปลี่ยนตามธีมอัตโนมัติ |
| 9 | ระบบจำหมวดที่ผู้ใช้แก้เอง (Learning Loop) | Screenshot ปุ่มแก้ไขหมวด + checkbox "จำตัวเลือก" — รอบหน้าจัดให้ |
| 10 | ปุ่ม "วิเคราะห์ด้วย AI" + ห้อง "คุยกับ Mind" | Screenshot หน้า Insights + กล่องแชท |
| 11 | ระบบลบ user ที่หมดอายุอัตโนมัติ (Lazy cleanup) | log บอก "รัน cleanup 1 ครั้งต่อวัน" — เรียกตอน user คนแรกของวัน login |
| 12 | ปุ่ม "เชื่อมด้วย LINE" + ระบบยืนยันตัวตนจริง | Screenshot ปุ่ม + คลิป flow OAuth (กดปุ่ม → ไป LINE → ยืนยัน → กลับมา เชื่อมสำเร็จ) |
| 13 | "ชื่อที่แสดง" ขึ้นในแอปจริงๆ (ก่อนหน้านี้กรอกได้แต่ไม่ขึ้น) | Screenshot ก่อน/หลัง — คำทักทาย "สวัสดี [ชื่อที่แสดง]" |
| 14 | แก้บั๊กมือถือ 3 จุด (ปุ่มหมวด/ปุ่ม save/แท็บ Settings) | Screenshot ก่อน/หลัง แต่ละจุด |

---

## หมายเหตุทางเทคนิค

### Item 4 — Parser EN + SCB
- เพิ่ม keyword ภาษาอังกฤษ (TRANSFER, PAYMENT, WITHDRAW, DEPOSIT) ในทุก parser
- SCB regex: เพิ่ม pattern 6 รูปแบบเพื่อรับ statement หลายเวอร์ชั่น
- ทดสอบผ่าน `logic_ai/test_parser.ipynb` (17 cells committed evidence)

### Item 12 — LINE Login OAuth
- ใช้ OAuth 2.0 + OpenID Connect — มาตรฐานเดียวกับ Login with Google
- State JWT (อายุ 10 นาที + purpose claim) → กัน CSRF (การโจมตีปลอม request ข้าม site)
- id_token verify (HS256 algorithm + LINE channel secret) → ยืนยันว่า LINE เป็นคน sign
- คงคำสั่ง `เชื่อม <email>` เดิมเป็น fallback (backward compat)

### Item 14 — Mobile UX fixes
- **ปุ่มหมวดถูกตัด** (cat-picker clip): แก้ด้วย `min-width: 0` + `overflow-wrap: anywhere` + `scrollbar-gutter: stable`
- **ปุ่ม save ถูกทับ** (stacking context trap): ลบ CSS animation `pageIn` ที่สร้าง stacking context ใหม่ ทำให้ modal overlay ขัง z-index ไว้ในกล่อง
- **แท็บ Settings เห็นแค่อันเดียว**: Grid 2x2 บน mobile ≤480px + Grid 4x1 บน tablet 481-1024px

---

## Cross-reference

- [docs/feedback-to-fix.md](feedback-to-fix.md) — Feedback ที่นำมาสู่ build log นี้
- [docs/before-after.md](before-after.md) — Before v1 vs After v2
- [docs/evidence-log-sprint5.md](evidence-log-sprint5.md) — ใครทำอะไรบ้าง

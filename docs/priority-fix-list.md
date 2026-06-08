# Priority Fix List
> Sprint 4 — MoneyMind (Team 04)
> วันที่: 2026-06-08

เอกสารนี้สรุป **รายการที่ต้องแก้** จาก User Testing รอบ Sprint 4 โดยจัดลำดับตามกรอบ Priority แบบ **Impact × Effort** เพื่อใช้วางแผน Sprint 5 ดูข้อมูล Feedback ที่มาของแต่ละ issue ได้ที่ [Feedback Summary](feedback-summary.md) และเหตุผลเชิงกลยุทธ์ที่ [Insights](insights.md)

## Priority Framework

| ระดับ | ความหมาย |
|------|----------|
| **P0** | กระทบ Core Flow ของผลิตภัณฑ์ — ต้องแก้ก่อนปล่อย Sprint 5 |
| **P1** | กระทบประสบการณ์แต่มี workaround — ทำใน Sprint 5 ถ้าเวลาพอ |
| **P2** | ปรับปรุงเล็ก ๆ — ทำเมื่อมีเวลา หรือยกไป Sprint ถัดไป |
| **Later** | Backlog ระยะยาว ไม่กระทบ Sprint 5 |

---

## Priority Table

| # | Issue | Impact | Effort | Priority | Owner |
|---|-------|--------|--------|----------|-------|
| 1 | LINE Bot ขอ PDF ซ้ำ | High | Medium | **P0** | WA |
| 2 | Mobile responsive ดูแคบ | High | Medium | **P0** | BEST |
| 3 | ขาด onboarding ตอนเริ่มต้น | Medium | Low | **P1** | ACHI |
| 4 | Cold-start ของ production deployment | Medium | High | **P1** | (ภายหลัง — รอย้าย Supabase) |
| 5 | คำถามชวนคุยของ AI ยังกว้าง | Low | Low | **P2** | NOTE |
| 6 | ขยายหมวดหมู่ 8 → 12–15 | Low | Medium | **Later** | – |

---

## P0 Details (ต้องแก้ก่อนปิด Sprint 5)

### P0 #1 — LINE Bot ขอ PDF ซ้ำ
- **ที่มา:** Feedback #2 (ตังเม), Task T3 partial 1 ครั้ง
- **ทำไม High Impact:** เป็น bug เชิง functional ที่ลดความไว้วางใจในตัวผลิตภัณฑ์ — ผู้ใช้ไม่แน่ใจว่าระบบทำงานสำเร็จหรือไม่ กระทบ Core Flow ของฝั่ง LINE โดยตรง
- **ทำไม Medium Effort:** ต้องตรวจสอบ state การ link ระหว่าง web user กับ LINE user และข้อความที่ Bot ตอบในแต่ละกรณี ไม่ต้องรื้อโครงสร้าง ระบบ LINE Bot ใหม่
- **Acceptance Criteria:**
  - หลังผู้ใช้อัปโหลด PDF ผ่านเว็บแล้ว Bot ต้อง **ไม่ขอ PDF ซ้ำ** เมื่อผู้ใช้พิมพ์คำสั่งใด ๆ
  - Bot ตอบกลับด้วยข้อความยืนยันสถานะการผูกบัญชี + จำนวน transaction ที่มีในระบบ
  - ทดสอบกับ flow: web upload → LINE link → LINE command ครบ 3 ขั้นโดยไม่มี prompt ซ้ำ
- **Owner:** **WA** (รับผิดชอบ logic ระบบ LINE Bot และระบบอ่าน PDF)

> หมายเหตุ: วันที่ 8 มิ.ย. 2026 ทีมได้ปล่อย flow ขอ password ผ่านแชทสำหรับ encrypted PDF ไปแล้ว ซึ่งช่วยลดเคส Bot "ตอบไม่ตรง" ในเคส PDF ที่ถูกล็อก แต่ปัญหา ขอ PDF ซ้ำในเคส normal upload ยังคงอยู่และต้องแก้ใน Sprint 5

### P0 #2 — Mobile responsive ดูแคบ
- **ที่มา:** Feedback #1 (พรีม), Task T2 partial 1 ครั้ง
- **ทำไม High Impact:** ผู้ใช้กลุ่มเป้าหมาย (นักศึกษา) ใช้มือถือเป็น touchpoint หลัก หากเปิดบนมือถือแล้วใช้ไม่สะดวก เท่ากับสูญเสีย Core Flow บนช่องทางหลัก
- **ทำไม Medium Effort:** ต้องไล่ดูทั้ง 5 view + ปรับ CSS / layout สำหรับ viewport ≤ 768 px ไม่ต้องเปลี่ยน architecture
- **Acceptance Criteria:**
  - ทุก view (Overview, Transactions, Upload, Budgets, Insights) อ่านได้ครบบนมือถือ viewport 360–414 px
  - ตาราง transaction ใช้ horizontal scroll หรือ stack mode ที่ยังอ่านง่าย
  - ปุ่มหลักทุกปุ่มมี tap target ≥ 44 × 44 px
  - ทดสอบจริงบน iOS Safari + Android Chrome อย่างน้อย 1 device ต่อ OS
- **Owner:** **BEST** (รับผิดชอบ UX/UI)

---

## P1 Details (ทำใน Sprint 5 ถ้าเวลาเหลือ)

### P1 #3 — ขาด onboarding ตอนเริ่มต้น
- **ที่มา:** Feedback #3 (ดิว) — "ใช้ได้ดี แต่ตอนเริ่มต้นยังสับสน"
- **ทำไม Medium Impact:** ไม่ block Core Flow แต่ลดอัตราการใช้งานครั้งแรก (first-run experience)
- **ทำไม Low Effort:** เป็นเรื่อง content / copy / tooltip / empty-state ไม่ต้องเขียน feature ใหม่
- **Acceptance Criteria เบื้องต้น:**
  - มี empty-state ที่ Overview บอกผู้ใช้ใหม่ว่า "ขั้นตอนถัดไปคืออัปโหลด statement"
  - มี tooltip หรือ guide สั้น ๆ บน Upload view ว่ารองรับธนาคารใดบ้าง
- **Owner:** **ACHI** (Frontend)

### P1 #4 — Cold-start ของ production deployment
- **ที่มา:** ปัญหาที่ทีมทราบอยู่แล้ว (Free tier hosting หลับเมื่อไม่มี traffic)
- **ทำไม High Effort:** การแก้ที่ต้นเหตุคือเปลี่ยน hosting / DB ซึ่งเป็นงานใหญ่ — ทำตอนย้าย Supabase น่าจะเหมาะกว่า
- **ตัดสินใจ:** **เลื่อน** ไปทำพร้อมตอนย้าย Supabase (DB ปัจจุบันใกล้หมดอายุอยู่แล้ว)

---

## P2 Details (ถ้าเวลาเหลือจริง ๆ)

### P2 #5 — คำถามชวนคุยของ AI ยังกว้าง
- **ที่มา:** สังเกตจากการทดสอบ — ผู้ใช้บางคนไม่รู้จะถาม AI ว่าอะไร
- **ทางเลือกที่เป็นไปได้:** เพิ่ม suggested prompts ติดท้าย ChatPanel เช่น "เดือนนี้ฉันใช้เกินงบหมวดไหน?"
- **Owner:** **NOTE** (สร้าง content/copy ของ suggestion)

---

## Later (ไม่อยู่ใน Sprint 5)

### #6 — ขยายหมวดหมู่ 8 → 12–15
- จากผลทดสอบ ผู้ใช้ไม่ได้ขอเพิ่มหมวด — ไม่ใช่ pain point ในตอนนี้
- ตรงกับยุทธศาสตร์ Sprint 5 = polish ไม่ใช่ expansion (ดู [Insights](insights.md) — Insight 3)
- เก็บไว้ใน backlog หลังเปิดใช้งานจริง

---

## สรุปการตัดสินใจ

- **2 ภารกิจหลักของ Sprint 5:** แก้ LINE Bot bug (WA) + Mobile responsive (BEST)
- **งานเสริมที่ทำได้ถ้าเวลาเหลือ:** Onboarding (ACHI), suggested prompts ของ AI (NOTE)
- **ไม่ทำใน Sprint 5:** Cold-start (รอย้าย Supabase), ขยายหมวด (ไม่ใช่ pain point)

อ้างอิงหลักฐานต้นทางทั้งหมดได้ที่ [Feedback Summary](feedback-summary.md) และเหตุผลเชิงกลยุทธ์ที่ [Insights](insights.md)

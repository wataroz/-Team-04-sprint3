# Insights from User Testing
> Sprint 4 — MoneyMind (Team 04)
> วันที่: 2026-06-08

เอกสารนี้สรุป **insight สำคัญ 3 ข้อ** ที่ได้จาก Feedback และ Task Results ใน Sprint 4 พร้อม implication ที่จะนำไปสู่ Sprint 5 ดูข้อมูลดิบของ Feedback แต่ละข้อได้ที่ [Feedback Summary](feedback-summary.md) และดูวิธีจัดลำดับการแก้ไขที่ [Priority Fix List](priority-fix-list.md)

แต่ละ insight ถูกจัดโครงสร้างเป็น 3 ส่วน:
- **Claim:** ข้อสรุปที่ได้
- **Evidence:** หลักฐานสนับสนุน (อ้าง Feedback # + ผู้ทดสอบ)
- **Implication:** สิ่งที่ทีมต้องทำใน Sprint 5

---

## Insight 1 — Mobile UX คือ Gap ใหญ่ที่สุด

### Claim
ประสบการณ์บนมือถือเป็น **จุดอ่อนที่สำคัญที่สุด** ของ MoneyMind ในตอนนี้ เพราะผู้ใช้กลุ่มเป้าหมาย (นักศึกษา) เปิดแอปบนมือถือเป็นช่องทางหลัก ไม่ใช่ desktop

### Evidence
- **Feedback #1 (พรีม):** "เว็บบนมือถือดูแคบ ปรับ responsive ด้วยจะดีมาก" — ผู้ทดสอบยกประเด็นนี้ขึ้นมาเอง
- **Task T2 (Upload Statement):** มี 1 ผู้ทดสอบที่อัปโหลดได้แต่จัดเป็น *partial* เพราะดูผลบนมือถือไม่ออก
- **บริบทผู้ใช้:** ทั้ง 5 คนเป็นนักศึกษาที่ทดสอบผ่านช่องทาง IG / LINE / Messenger ซึ่งสะท้อนว่า touchpoint หลักคือมือถือ

### Implication ต่อ Sprint 5
- ต้องยก Mobile responsive ขึ้นเป็น **P0** (กระทบ Core Flow ตรง ๆ)
- ตรวจสอบทั้ง 5 view (Overview, Transactions, Upload, Budgets, Insights) บน viewport ขนาด ≤ 768 px
- เน้นความอ่านง่ายของตาราง / chip / chart และระยะแตะปุ่ม (tap target)
- เจ้าของหลัก: **BEST** (UX/UI)

---

## Insight 2 — LINE Bot มี Functional Bug ที่ทำลายความไว้วางใจ

### Claim
LINE Bot ยังมี bug ที่ทำให้ผู้ใช้ **ไม่แน่ใจว่าระบบทำงานสำเร็จหรือไม่** ซึ่งอันตรายกว่าปัญหา UX ทั่วไป เพราะลดความเชื่อมั่นในตัวผลิตภัณฑ์โดยรวม

### Evidence
- **Feedback #2 (ตังเม):** "ใส่ PDF แล้ว LINE Bot ยังขอให้ใส่ซ้ำ ไม่แน่ใจว่าผูกบัญชีสำเร็จไหม"
- **Task T3 (LINE Bot + AI):** 1 ผู้ทดสอบจัดเป็น *partial* เพราะติดปัญหาเดียวกัน — Bot ขอ PDF ซ้ำหลังอัปโหลดไปแล้ว
- เวลาเฉลี่ยของ T3 ที่สำเร็จคือ ~1 นาที 36 วินาที สะท้อนว่า flow นี้ "ใช้พลังงาน" ของผู้ใช้สูงอยู่แล้ว — bug ยิ่งทำให้ผู้ใช้ล้มเลิกง่าย

### Implication ต่อ Sprint 5
- ต้องยกประเด็นนี้เป็น **P0** เช่นเดียวกับ Mobile responsive
- ตรวจสอบ flow ของระบบ LINE Bot ตั้งแต่ "อัปโหลด PDF" → "ผูกบัญชี" → "ตอบกลับ" ว่า state การ link ระหว่าง web user กับ LINE user สอดคล้องกันหรือไม่
- เพิ่มข้อความยืนยันให้ผู้ใช้รับรู้ชัดเจน เช่น "ผูกบัญชีสำเร็จแล้ว — ไม่ต้องอัปโหลดซ้ำ"
- เจ้าของหลัก: **WA** (logic ระบบ LINE Bot และระบบอ่าน PDF)

> หมายเหตุ: วันที่ 8 มิ.ย. 2026 ทีมได้ปล่อย flow รับ password ของ PDF ที่ถูกล็อกผ่านแชทไปแล้ว ซึ่งช่วยลดกรณีที่ Bot "ตอบไม่ตรง" ในเคส encrypted PDF แต่ bug เรื่องการขอ PDF ซ้ำในเคส normal upload ยังคงอยู่และต้องแก้ใน Sprint 5

---

## Insight 3 — Value Proposition ได้รับการยืนยัน

### Claim
จากผลทดสอบ ฟีเจอร์หลักของ MoneyMind (ภาพรวมการเงิน + AI ตอบคำถาม) **ได้รับการยอมรับจากผู้ใช้แล้ว** — ทีมไม่ต้องรื้อ feature ใน Sprint 5 ควรโฟกัสที่การขัด UX และแก้ bug แทน

### Evidence
- **Feedback #4 (นน, ต้า):** "ดูภาพรวมการเงินเข้าใจง่าย ถ้ามีจริงน่าจะใช้" — เป็นสัญญาณว่า value proposition ตรงกับ need
- **Feedback #5 (นน, พรีม, ต้า):** "AI ตอบคำถามได้ดี และเสถียรกว่าที่คิด" — ฟีเจอร์ AI ที่ทีมกังวลว่าอาจไม่เสถียรในการ demo จริง กลับได้รับ feedback บวก
- **Task T3:** ผู้ทดสอบที่ทำสำเร็จ ใช้ AI ได้จริง — ยืนยันว่า provider chain ทำงานได้ใน production

### Implication ต่อ Sprint 5
- **ไม่ต้องเพิ่ม feature ใหญ่** — Sprint 5 ควรเป็น *polish sprint* ไม่ใช่ *expansion sprint*
- งบประมาณเวลาควรไปที่: Mobile responsive (Insight 1) + LINE Bot bug (Insight 2) + Onboarding (Feedback #3)
- backlog เช่น "ขยายหมวด 8→12-15" หรือ "Hierarchical category" ถูกเลื่อนไป Later
- ยุทธศาสตร์: **ขัดของที่มี ไม่สร้างของใหม่**

---

## สรุป

| Insight | ระดับความสำคัญ | ผู้รับผิดชอบหลัก |
|---------|----------------|-------------------|
| Mobile UX = gap ใหญ่ที่สุด | P0 | BEST |
| LINE Bot bug ขอ PDF ซ้ำ | P0 | WA |
| Value proposition ยืนยันแล้ว → polish sprint | กรอบกลยุทธ์ Sprint 5 | ทีมทั้งหมด |

รายละเอียดของ task ที่ต้องทำ + acceptance criteria อยู่ที่ [Priority Fix List](priority-fix-list.md)

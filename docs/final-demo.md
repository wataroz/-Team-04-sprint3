# Final Demo Evidence — Sprint 5

> หลักฐานการ demo Prototype v2 — Live URL, Core Flow Test ที่ผ่าน, Hardware demo

**อัปเดต**: 2026-06-14

---

## Live URL

**Production**: https://moneymind-team-04-sprint3.onrender.com

**Branch**: `feature/flask-react` (auto-deploy via Render on push)

**Health check**: https://moneymind-team-04-sprint3.onrender.com/api/health → `{"ok": true}`

---

## Core Flow Test (ผ่านครบ)

### Web flow
1. ✅ **Login** ด้วย email → เข้าหน้า Overview
2. ✅ **Upload PDF statement** → parse + จัดหมวดอัตโนมัติ
3. ✅ **แก้หมวด tx** + ติ๊ก "จำตัวเลือก" → ครั้งหน้า merchant เดียวกัน จัดหมวดที่บันทึก (Learning Loop)
4. ✅ กด **"วิเคราะห์ด้วย AI"** → AI สรุปข้อมูลให้
5. ✅ เปิด **"คุยกับ Mind"** → ถามคำถาม → AI ตอบ
6. ✅ **Settings 4 แท็บ** ทำงานครบ (โปรไฟล์/การแสดงผล/LINE/แจ้งเตือน)
7. ✅ **สลับธีมสว่าง/มืด** → จำค่า → reload ก็ยังเหมือนเดิม
8. ✅ **ลบบัญชี** → modal 3 ขั้น → Export CSV → schedule delete → login กลับ → CancelDeleteBanner → ยกเลิกได้
9. ✅ **"ชื่อที่แสดง"** ขึ้นในแอป (คำทักทาย + avatar + sidebar)

### LINE Bot flow
1. ✅ Add MoneyMind bot เป็นเพื่อน → bot ทักทาย + แนะนำคำสั่ง
2. ✅ ส่ง PDF statement → bot parse + แสดงผล
3. ✅ ส่ง PDF ที่ใส่รหัสผ่าน → bot ขอรหัส → ใส่รหัส → parse สำเร็จ
4. ✅ พิมพ์คำสั่ง "สรุป", "ยอด", "เดือนนี้", "วิเคราะห์", "ช่วย" → bot ตอบถูก
5. ✅ พิมพ์ "เชื่อม email" (fallback) → bot เชื่อม LINE กับบัญชีเว็บ

### LINE Login OAuth flow (สำหรับ user ใน developer role)
1. ✅ กดปุ่ม **"เชื่อมด้วย LINE"** ใน Settings → tab LINE
2. ✅ เด้งไป LINE OAuth page → กด "อนุญาต"
3. ✅ เด้งกลับมา → toast "เชื่อม LINE สำเร็จ"
4. ✅ Status: "เชื่อมแล้ว" + กดยกเลิกได้

### Cancel path (ทดสอบ user_cancelled error)
1. ✅ กดปุ่ม "เชื่อมด้วย LINE"
2. ✅ ที่ LINE consent → กด "ยกเลิก"
3. ✅ กลับมา → toast "คุณยกเลิกการเชื่อม LINE" (ไม่ใช่ generic "ล้มเหลว")

---

## Hardware Demo (PWA install)

### Android Chrome
1. เปิด https://moneymind-team-04-sprint3.onrender.com ใน Chrome บนมือถือ Android
2. Banner เด้งขึ้น: **"Install MoneyMind?"**
3. กด **Install** → ไอคอนขึ้นที่ home screen
4. เปิดจากไอคอน → **fullscreen** ไม่มี browser bar (เหมือนแอป Play Store)

### iOS Safari
1. เปิดเว็บใน Safari
2. กดปุ่ม Share → **"Add to Home Screen"**
3. ไอคอนขึ้นที่ home screen
4. เปิดจากไอคอน → standalone mode

---

## Responsive Test (4 breakpoints)

ทดสอบผ่าน DevTools mobile mode:

| Device | Viewport | Status |
|---|---|---|
| iPhone SE (1st gen) | 320×568 | ✅ ผ่าน |
| Galaxy Fold / Pixel | 360×740 | ✅ ผ่าน |
| iPhone SE (2nd gen) | 375×667 | ✅ ผ่าน |
| iPad Air | 820×1180 | ✅ ผ่าน |
| Desktop | 1280×800 | ✅ ผ่าน |

ทุก viewport:
- ปุ่มหมวดเห็นเต็มทั้ง 2 คอลัมน์
- ปุ่ม Save ไม่ถูกแถบเมนูล่างทับ
- แท็บ Settings เห็นครบทุกแท็บ
- Modal overlay อยู่บน bottom-nav

---

## Cross-reference

- [docs/sprint5-build-log.md](sprint5-build-log.md) — รายการ build ทั้งหมด
- [docs/known-issues.md](known-issues.md) — ปัญหาที่ทราบ
- [docs/cp7-report.md](cp7-report.md) — CP7 รายงานเต็ม

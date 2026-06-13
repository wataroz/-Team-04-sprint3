# Sprint 5 — Cascade Delete Checklist (Hard Delete Account Flow)

> **เจ้าของงาน**: AJ (cron worker + DELETE /api/account endpoint)
> **ตรวจสอบโดย**: WA (Learning Loop / MerchantOverride)
> **อัปเดต**: 2026-06-11

---

## บริบท

AJ กำลังเพิ่มฟีเจอร์ "ลบบัญชี" (hard delete + 30-day grace period). เมื่อหมด grace
period → cron worker ลบทุก row ของ user คนนั้น cascade.

`MerchantOverride` ผูกกับ Learning Loop (`logic_ai/pdf_parser.py` ไม่ได้แตะ table
นี้โดยตรง — `backend/app.py::_apply_overrides` เป็นคนใช้). ถ้าไม่ลบ row พวกนี้
ตอน user หายไป → **orphan row + FK violation บน Postgres**.

---

## DELETE Order ที่บังคับ

ใน 1 transaction (rollback ถ้าผิดพลาดกลางคัน). อ้างอิง FK constraint จาก
`backend/models.py`:

```
1. MerchantOverride       WHERE user_id = :uid   ← ใหม่ ห้ามลืม
2. Transaction            WHERE user_id = :uid   (FK → users.id + source_import_id → imports.id)
3. Import                 WHERE user_id = :uid   (ลบหลัง Transaction เพราะ tx.source_import_id อ้างถึง)
4. Notification           WHERE user_id = :uid
5. Preference             WHERE user_id = :uid
6. LineUser               WHERE user_id = :uid   ← ใหม่ ห้ามลืม (ไม่ใช่ cascade ORM)
7. LinePendingPdf         WHERE line_user_id IN (LineUser.line_user_id ของ user คนนี้)   ← ลบก่อน LineUser ถ้าจะ join, หรือเก็บ line_user_id ไว้ก่อน
8. User                   WHERE id = :uid        ← สุดท้าย
```

### ทำไมต้อง MerchantOverride **ก่อน** User?

`User.relationships` ใน `models.py` ตั้ง `cascade="all, delete-orphan"` ให้แค่
**4 table**: Transaction, Import, Notification, Preference. ไม่ได้รวม:
- `MerchantOverride` (ไม่มี relationship เลย)
- `LineUser` (มี `relationship()` แบบ default — ไม่ cascade)
- `LinePendingPdf` (ไม่ผูก user_id โดยตรง — ผูก line_user_id)

ถ้า cron `db.delete(user)` โดยไม่ลบ 3 ตัวนี้ก่อน → Postgres FK violation (ForeignKey
`merchant_overrides.user_id` → `users.id`).

---

## ✅ Checklist สำหรับ AJ

- [ ] **MerchantOverride ลบเป็นอันดับ 1** (ก่อน User เสมอ) — ไม่ใช่ cascade
- [ ] **LineUser ลบ manual** — `relationship()` ไม่ได้ตั้ง cascade
- [ ] **LinePendingPdf ลบ manual** — ผูก `line_user_id` ไม่ใช่ `user_id` ตรงๆ
      ดังนั้น: `SELECT line_user_id FROM line_users WHERE user_id=:uid` ก่อน
      แล้ว `DELETE FROM line_pending_pdfs WHERE line_user_id IN (...)`
- [ ] Order DELETE ตามตาราง 8 ขั้นข้างบน (Transaction ก่อน Import เพราะ
      `transactions.source_import_id` → `imports.id`)
- [ ] ใช้ single DB transaction → rollback ทั้งหมดถ้าขั้นใดล้ม
- [ ] UniqueConstraint `(user_id, merchant_norm)` บน MerchantOverride — ไม่มีปัญหา
      เพราะลบทั้ง user ออก ไม่ได้ INSERT ใหม่
- [ ] **Post-delete verification**: รัน 4 query ต่อไปนี้ ต้องคืน **0 rows** ทุก query:
  ```sql
  SELECT COUNT(*) FROM merchant_overrides WHERE user_id = <deleted_uid>;
  SELECT COUNT(*) FROM transactions      WHERE user_id = <deleted_uid>;
  SELECT COUNT(*) FROM imports           WHERE user_id = <deleted_uid>;
  SELECT COUNT(*) FROM line_users        WHERE user_id = <deleted_uid>;
  ```
- [ ] Log line สรุป: `deleted_uid=X merchant_overrides=N txs=N imports=N ...`

---

## ⚠️ Edge Cases ที่ตรวจเจอ

### 1. Email re-link (`backend/line_bot.py::_link_account`) — **ไม่ย้าย MerchantOverride**

ปัจจุบัน (Sprint 3, b1896c3) flow re-link ย้ายแค่:
- `Transaction.user_id` (auto-user → web user)
- `Import.user_id`
- `Notification.user_id`
- ลบ `Preference` ของ auto-user
- ลบ `User` (auto-user)

แต่**ไม่แตะ `MerchantOverride`** — ถ้า auto-user เคยแก้หมวด tx ก่อน link → override
จะค้างที่ auto-user → พอ `db.delete(old_user)` ที่บรรทัด 335 → **FK violation**.

**ผลกระทบ Sprint 5**: ถ้า AJ ทำ hard delete หลัง user re-link → ไม่เจอ override แล้ว
(เพราะถูกย้าย/ลบไปกับ auto-user). แต่ **flow re-link เองพังตั้งแต่ Sprint 3** ถ้า
auto-user มี override → ต้อง **fix แยก** (WA จะแจ้ง REW/AJ).

**Mitigation ชั่วคราว**: เพิ่ม `DELETE FROM merchant_overrides WHERE user_id=old_user_id`
ก่อน `db.delete(old_user)` ใน `_link_account` (ทาง LINE ก่อนหน้านี้ยังไม่เคยมี
override เพราะ user แก้หมวดผ่านเว็บเท่านั้น — แต่ก็ควรเผื่อไว้).

### 2. UniqueConstraint(user_id, merchant_norm) — ปลอดภัย

ตอน hard delete: เราลบ row หมด ไม่ใช่ insert → UniqueConstraint ไม่บังคับ ไม่มี race.

### 3. Grace period vs. login

ถ้า user **เข้าเว็บใหม่** ระหว่าง grace period 30 วัน → ต้องมีกลไก "ยกเลิก hard delete"
(AJ ออกแบบเอง — นอกขอบเขต WA).

### 4. LineUser orphan

ถ้า user มี LINE link → cron ต้องลบ `LineUser` row ก่อน User. ถ้าไม่ลบ → FK violation
`line_users.user_id` → `users.id`.

### 5. LinePendingPdf — ผูก line_user_id ไม่ใช่ user_id

LinePendingPdf เก็บ encrypted PDF ที่รอ password (TTL 5 นาที). ไม่มี FK ไป
`users.id` แต่ผูก `line_user_id` → ต้อง cleanup คู่กับ LineUser. ถ้าลืม → orphan row
ค้าง DB (ไม่ break อะไร แต่กิน storage).

---

## 📝 Note สำหรับ AJ

1. **อย่าใช้ `db.delete(user)` ตรงๆ** — ORM cascade ไม่ครอบคลุม `MerchantOverride`,
   `LineUser`, `LinePendingPdf` → ต้องเขียน DELETE explicit ทุกตัว
2. **หรือ** เพิ่ม `cascade="all, delete-orphan"` ใน `User.merchant_overrides`,
   `User.line_users` ใน `models.py` (ต้องคุย REW/ACHI ก่อน — กระทบ schema)
3. **แนะนำ**: เขียน function `_hard_delete_user(db, user_id)` ใน `app.py` แล้วเรียก
   จาก cron worker — single source of truth + reuse กับ endpoint "Delete my account"
   ที่จะมี Sprint 5
4. **Test plan**: สร้าง user ปลอม → insert override 3-5 row, tx 10 row, import 2 row,
   notification 5 row, line_user 1 row → รัน `_hard_delete_user` → verify 4 query
   ที่ระบุข้างบนคืน 0 rows
5. **FK constraint check**: ถ้า dev บน SQLite local — FK ไม่ enforce by default!
   ต้องเปิด `PRAGMA foreign_keys = ON` ตอน test, ไม่งั้นจะไม่เจอ violation จน
   deploy ขึ้น Postgres prod

---

## 🔜 Follow-up (Post-AJ Push)

WA จะ verify อีกครั้งเมื่อ AJ push:
- [ ] อ่าน diff ของ `app.py` / cron worker
- [ ] ตรวจ order DELETE ตรงกับ checklist นี้
- [ ] รัน `_hard_delete_user` กับ test user → check 4 query
- [ ] ถ้าผ่าน → close ticket; ถ้าไม่ผ่าน → comment บน PR ระบุบรรทัด

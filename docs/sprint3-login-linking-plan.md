# Sprint 3 — แผน Account Linking (Web ↔ LINE) + AI Insight จริง + LINE แจ้งเตือนเกินงบ

> เอกสารวางแผนโดย PM (Team 04, Sprint 3). ห้ามถือเป็นโค้ด — เป็น spec ให้ AJ/ACHI/WA/BEST เอาไปทำ
> **เวอร์ชัน FINAL** — ปรับตามการตัดสินใจของ user (29 พ.ค. 2026)
> Sprint Goal: ผู้ใช้บันทึก/อัปโหลดรายจ่าย → เห็น Dashboard + insight จาก Claude API จริง + LINE Bot แจ้งเตือนเกินงบ

---

## 0. การตัดสินใจของ user (FINAL — ยึดตามนี้)

| # | ประเด็น | สิ่งที่เลือก |
|---|---------|-------------|
| 1 | วิธีเชื่อม account | **ผูกด้วย email (ตัวเลือก B)** — พิมพ์ email ใน LINE → หา User → set `LineUser.user_id` + ย้าย txs เดิม. **ตัด OTP/LinkCode ออก** |
| 2 | AI insight | **เพิ่ม backend Anthropic endpoint จริง (ตัวเลือก 2)** — `POST /api/ai/...` เรียก Anthropic ด้วย `ANTHROPIC_API_KEY` แล้วแก้ frontend ให้ fetch แทน `window.claude`. เพิ่ม scope ~1 วัน |

> ตัวเลือก A (OTP) และ C (LINE Login OAuth) **ถูกตัดออกจากแผนแล้ว** — เก็บเป็น future work เท่านั้น

---

## 1. สภาพปัจจุบัน (ยืนยันจากโค้ดจริง)

| จุด | ไฟล์/บรรทัด | สภาพ |
|-----|------------|------|
| `LineUser` มี `user_id` (FK→User) + `linked_at` | `backend/models.py:160` | โครงพร้อม link แล้ว — **ไม่ต้องเพิ่ม model ใหม่** |
| LINE auto-create user ใหม่เสมอ | `backend/line_bot.py:180` `_get_or_create_user()` | สร้าง `line_<id>@line.local` แยกทุกคน — ยังไม่เคย link เข้า web account |
| Web login = upsert by email (ไม่มี password จริง) | `backend/app.py:137` | รับแค่ email+name → return user — **email มีอยู่แล้ว ใช้ผูกได้ตรงๆ** |
| Web auth = React state ล้วน, refresh=logout | `frontend/src/auth.jsx` | ไม่มี token/session |
| Budget เก็บที่ `Preference.category_budgets` (JSON) ผูก user_id | `backend/models.py:136` | มีแล้ว |
| AI insight + ChatPanel เรียก `window.claude` | `frontend/src/views.jsx` | **บน production เงียบ** (window.claude undefined) — ต้องเปลี่ยนเป็น fetch endpoint จริง |
| LINE แจ้งเตือนเกินงบ | `backend/line_bot.py` | **ยังไม่มี** — ไม่มี push budget alert |

**ปัญหาแกนกลาง**: LINE user กับ web user เป็นคนละ `user_id` เสมอ → txs/budget แยกกัน 100%
LINE Bot ไม่รู้ว่า follower คนนี้ = account ไหนบนเว็บ → แจ้งเตือนงบข้ามแพลตฟอร์มไม่ได้

---

## 2. Flow การ link ที่เลือก — Email-based (ตัวเลือก B)

```
[LINE] ผู้ใช้พิมพ์ "เชื่อม you@email.com"  (หรือ "link you@email.com")
   → webhook จับ pattern email
   → หา User ที่มี email นั้น (User.email — unique อยู่แล้ว)
       ├─ ไม่เจอ → ตอบ "ไม่พบบัญชีนี้ กรุณา login เว็บด้วย email นี้ก่อน"
       └─ เจอ → set LineUser.user_id = user.id + linked_at = now
                 → ย้าย txs/imports/notifications เดิมของ LINE user ไปรวมที่ user เว็บ
                 → ตอบ "เชื่อมกับ <email> สำเร็จ ✅"

[ผลลัพธ์] ทั้งเว็บและ LINE อ่าน/เขียน user_id เดียวกัน
   → budget ที่ตั้งบนเว็บ → LINE เห็น → แจ้งเตือนเกินงบได้
```

**เคส txs เดิมบน LINE**: ก่อน link ผู้ใช้อาจส่ง PDF ทาง LINE ไปแล้ว (อยู่ใต้ fake-email user)
→ ตอน link ให้ **ย้าย** (UPDATE `user_id` ใน transactions/imports/notifications) ไป user เว็บ เพื่อข้อมูลไม่หาย — AJ กำหนดกฎ + ทดสอบเคสมี txs เดิม

**ไม่ต้องมีตารางใหม่ / ไม่ต้อง migration** — ใช้ `LineUser.user_id` + `User.email` ที่มีอยู่แล้ว

---

## 3. Mitigation ความปลอดภัยของ email linking (เบาๆ ตามที่ user รับ tradeoff)

> user ยอมรับว่า "ใครรู้ email ก็ผูกได้" เพราะเป็น demo sprint — แต่ PM แนะนำใส่กันชนเบาๆ ดังนี้

| มาตรการ | ระดับ | ทำไหม |
|---------|-------|-------|
| **ผูกได้เฉพาะ email ที่เคย login เว็บแล้ว** (มี User row จริง) — ถ้าไม่เคย login → ปฏิเสธ | P0 (แนะนำทำ) | ได้ฟรี เพราะ flow หา User by email อยู่แล้ว — ไม่เพิ่มงาน |
| **Confirm message ก่อนผูก** — bot ถาม "ยืนยันผูกกับ <email>? พิมพ์ ใช่" ก่อนเชื่อมจริง | P1 (stretch) | กัน fat-finger / พิมพ์ผิด เพิ่ม state นิดหน่อย |
| หมายเหตุในเดโม่อาจารย์: "เป็น demo linking — production จริงควรใช้ LINE Login OAuth" | เอกสาร | NOTE/PM ใส่ใน README ตอนส่ง |

**ความเสี่ยงที่ยอมรับ**: ไม่มี verify เจ้าของ email จริง → ผู้ไม่หวังดีที่รู้ email + login เว็บแทนได้ จะผูก LINE ตัวเองเข้าบัญชีเหยื่อได้ ยอมรับในบริบท sprint demo

---

## 4. แตกงาน (ใครทำอะไร + ขึ้นกับใคร)

### AJ (Backend) — งานหลักของ sprint นี้
| # | งาน | ไฟล์ | ขึ้นกับ |
|---|-----|------|--------|
| A1 | webhook: จับ pattern "เชื่อม/link <email>" → หา User by email → set `LineUser.user_id` + `linked_at` + ย้าย txs/imports/notifications เดิม → ตอบยืนยัน | `line_bot.py` | — |
| A2 | guard: ผูกได้เฉพาะ email ที่มี User row (เคย login เว็บ) — ไม่เจอ → ตอบ error ชัด (P0 mitigation) | `line_bot.py` | A1 |
| A3 | คำสั่ง LINE "งบ"/"budget" → อ่าน `Preference.category_budgets` แสดงสถานะใช้/งบ | `line_bot.py` | A1 |
| A4 | **Budget alert**: เมื่อ insert txs (ทั้ง web `/api/transactions` และ LINE PDF) เช็คหมวดเกินงบ → push LINE (`push_message` + line_user_id ของ user) | `app.py`, `line_bot.py` | A1 |
| A5 | **AI endpoint**: `POST /api/ai/insight` + `POST /api/ai/chat` เรียก Anthropic API (`ANTHROPIC_API_KEY` จาก env) รับ txs/คำถาม → คืนผล insight/คำตอบ | `app.py` | — (ขนานกับ A1 ได้) |
| A6 | เพิ่ม `anthropic` ลง `requirements.txt` + เตือน user ตั้ง `ANTHROPIC_API_KEY` บน Render | `requirements.txt` | A5 (เดี๋ยว AJ แก้ไฟล์เอง) |
| A7 | (P1) confirm step ก่อนผูก email | `line_bot.py` | A1 |

### ACHI (Frontend)
| # | งาน | ไฟล์ | ขึ้นกับ |
|---|-----|------|--------|
| F1 | แก้ Insights ให้ `fetch('/api/ai/insight')` แทน `window.claude.complete()` | `frontend/src/views.jsx` | A5 (ตกลง contract ก่อน) |
| F2 | แก้ ChatPanel ("คุยกับ Mind") ให้ `fetch('/api/ai/chat')` แทน `window.claude` | `views.jsx` | A5 |
| F3 | loading/error state ของปุ่ม AI (กันเงียบเหมือนเดิม — โชว์ spinner + error toast) | `views.jsx` | F1,F2 |
| F4 | เพิ่มส่วน "เชื่อมต่อ LINE" ในหน้า settings/overview — บอกวิธีพิมพ์ "เชื่อม <email>" ใน LINE OA + ปุ่มเปิด LINE | `views.jsx` | A1 ( contract) |

### BEST (UX/UI) — styling
| # | งาน | ไฟล์ | ขึ้นกับ |
|---|-----|------|--------|
| B1 | สไตล์ card "เชื่อมต่อ LINE" + badge สถานะ + ปุ่มเปิด LINE OA | `ux_ui/styles.css` | F4 (โครง markup) |
| B2 | สไตล์ loading/error ของปุ่ม AI (spinner, error toast) | `styles.css` | F3 |
| B3 | responsive ของ card บน mobile | `styles.css` | B1 |

### WA (Logic/AI) — เข้า critical path แล้ว (เพราะมี AI endpoint จริง)
| # | งาน | หมายเหตุ |
|---|-----|----------|
| W1 | ช่วยออกแบบ **prompt** สำหรับ `/api/ai/insight` + `/api/ai/chat` — ป้อน context จาก txs/category ให้ Claude ตอบแม่น | ทำคู่กับ AJ ตอน A5 |
| W2 | ให้ AJ ใช้ผล `categorize()` เดิมเป็น context ใน prompt (ไม่ต้องแก้ parser) | ใช้ของเดิม |

---

## 5. Timeline 4 วัน (รวม 3 scope: email linking + AI endpoint + budget alert)

> 4 วันค่อนข้างแน่น — PM จัด P0 (ต้องมีเพื่อปิด Sprint Goal) vs Stretch ชัดเจน

| วัน | โฟกัส | ใคร | Deliverable |
|-----|-------|-----|-------------|
| **Day 1** | email linking webhook + ตกลง contract AI endpoint | AJ (A1,A2) ∥ AJ+WA เริ่ม A5/prompt | LINE พิมพ์ "เชื่อม email" → user_id ตรงกัน + ย้าย txs สำเร็จ (ทดสอบ local) |
| **Day 2** | AI endpoint ทำงานจริง + frontend fetch | AJ (A5,A6) + WA (W1) ∥ ACHI (F1,F2) | `/api/ai/insight` + `/api/ai/chat` คืนผลจริง, ปุ่ม AI บนเว็บเรียก endpoint ได้ |
| **Day 3** | budget alert + คำสั่งงบ LINE + UI/loading + styling | AJ (A3,A4) ∥ ACHI (F3,F4) ∥ BEST (B1,B2,B3) | LINE แจ้งเตือนเกินงบจริง + card เชื่อม LINE + ปุ่ม AI มี loading/error |
| **Day 4** | ทดสอบรวม + แก้บั๊ก + เดโม่ + buffer + (stretch A7/confirm) | ทุกคน | flow ครบ: login→เชื่อม LINE→อัปโหลด→เกินงบ→LINE เด้ง + AI insight ทำงานบน production |

### P0 vs Stretch
| ระดับ | งาน |
|-------|-----|
| **P0 (ต้องมี)** | A1 email linking, A2 guard, A5 AI endpoint, F1/F2 frontend fetch, A4 budget alert, F4 UI เชื่อม LINE |
| **Stretch (ถ้าเหลือเวลา)** | A3 คำสั่ง "งบ" ใน LINE, A7 confirm step, F3 loading polish, B-styling ระดับสวยงาม |

**ถ้า 4 วันแน่นเกิน** → ตัด Stretch ก่อน (A3/A7/F3) แล้วโฟกัส P0 ให้ flow หลักครบ. เดโม่ Sprint Goal ผ่านได้ด้วย P0 ล้วน

**Note ลำดับ**:
- A1 (linking) ต้องเสร็จก่อน A4 (alert) เพราะ alert ต้องรู้ line_user_id ที่ผูกกับ user
- A5 (AI endpoint) ขนานกับ A1 ได้ (คนละไฟล์/feature) — แต่ต้องตกลง contract API กับ ACHI ตั้งแต่ Day 1 ให้ F1/F2 ทำขนานได้

---

## 6. ความเสี่ยง / Dependency

| ความเสี่ยง | ผลกระทบ | การรับมือ |
|-----------|---------|-----------|
| **`ANTHROPIC_API_KEY` ต้องตั้งบน Render** + user ต้องมี key จริง | ถ้าไม่มี key → `/api/ai/*` พัง 500 → ปุ่มยังเงียบเหมือนเดิม | **user ต้องเตรียม Anthropic API key + ตั้ง env บน Render Dashboard.** AJ ทำ error handling ให้ endpoint ตอบ message ชัดถ้า key หาย (ไม่เงียบ) |
| **Anthropic API มีค่าใช้จ่าย** ต่อ request | บิลพุ่งถ้าโดน spam | จำกัด context/tokens ใน prompt + (stretch) rate limit เบาๆ — WA/AJ คุมขนาด prompt |
| **Email linking ไม่ปลอดภัย** (ไม่ verify เจ้าของ email) | ใครรู้ email + login แทนได้ → ผูก LINE เข้าบัญชีเหยื่อ | user รับ tradeoff แล้ว. ใส่ P0 mitigation (A2: ต้องเคย login เว็บก่อน) + หมายเหตุในเดโม่ + (P1) confirm step |
| **Migration บน Postgres** | — | **ไม่ต้อง migration ใหม่** — ใช้ `LineUser.user_id` + `User.email` ที่มีอยู่แล้ว ✅ (ยืนยันแล้ว ตัด LinkCode ออก) |
| **Render Free cold-start ~30s** → reply token หมดอายุ | LINE ตอบช้า/พลาด token | โค้ดเดิมมี fallback `push_message` (line_bot.py:78) — budget alert ใช้ push อยู่แล้ว ปลอดภัย |
| **Push message ต้องมี line_user_id** | user ยังไม่ link → alert ส่งไม่ได้ | ออกแบบให้ alert ทำงานเฉพาะ user ที่ link แล้ว (มี LineUser row) — ถูกต้องตาม flow |
| txs เดิมบน LINE ก่อน link | อาจซ้ำ/หาย ตอนย้าย | A1 กำหนดกฎย้ายชัด (UPDATE user_id) + ทดสอบเคสมี txs เดิม |

---

## 7. สรุป (ทำไปแล้ว / เหลืออะไร / ใครค้าง)

- **ทำไปแล้ว (โครงที่ใช้ต่อได้)**: `LineUser.user_id`+`linked_at` + `User.email` (unique) มีในโมเดล — **ไม่ต้องเพิ่ม model/migration**, budget เก็บใน Preference, LINE webhook + push fallback พร้อม
- **เหลือ (sprint นี้)**:
  - AJ: email linking webhook (A1,A2), AI endpoint (A5,A6), budget alert (A4), คำสั่งงบ LINE (A3)
  - ACHI: frontend fetch AI endpoint (F1,F2,F3), UI เชื่อม LINE (F4)
  - WA: prompt design สำหรับ AI endpoint (W1,W2) — **เข้า critical path แล้ว**
  - BEST: styling card LINE + ปุ่ม AI loading (B1,B2,B3)
- **ค้างรอ user**: เตรียม **Anthropic API key** + ตั้ง `ANTHROPIC_API_KEY` บน Render (บล็อก A5 ตอน deploy)
- **ตัดออกจากแผนแล้ว**: LinkCode model, OTP flow, LINE Login OAuth

---

## Next step ที่แนะนำ

**งานแรก Day 1 = AJ เริ่มที่ A1 (email linking webhook)** — จับ pattern "เชื่อม <email>" → หา User → set `LineUser.user_id` + ย้าย txs เดิม. ขนานกันให้ **AJ + WA ตกลง contract ของ `/api/ai/*` (A5/W1)** เพื่อให้ ACHI ทำ F1/F2 ต่อได้ทันที Day 2.

**ก่อนเริ่ม**: เตือน user เตรียม **Anthropic API key** ให้พร้อม (ต้องใช้ตอน A5 deploy บน Render).

# Sprint 3 — Closeout Summary: Account Linking + AI Insight + Budget Alert (+ งานเสริมเกินแผน)

> เอกสารปิด Sprint โดย PM (Team 04, Sprint 3)
> **เวอร์ชัน FINAL — สรุปหลังปิด Sprint** (อัปเดต 1 มิ.ย. 2026)
> เปลี่ยนสถานะเอกสารจาก "แผน" → "สรุปสิ่งที่ทำจริง" หลังปิด Sprint Goal ครบ 6/6 ฟีเจอร์
> Sprint Goal: ผู้ใช้บันทึก/อัปโหลดรายจ่าย → เห็น Dashboard + insight จาก AI จริง + LINE Bot แจ้งเตือนเกินงบ — **ผ่านครบทุกข้อ**

---

## 0. สถานะ Sprint Goal — ครบ 6/6

| # | เป้าหมาย | สถานะ |
|---|---------|------|
| 1 | Email-based account linking (LINE ↔ web) | ผ่าน |
| 2 | AI Insight endpoint จริง (production) | ผ่าน |
| 3 | AI Chat ("คุยกับ Mind") เรียก backend จริง | ผ่าน |
| 4 | LINE Budget alert เมื่อใช้เกินงบ | ผ่าน |
| 5 | คำสั่ง "งบ"/budget ใน LINE | ผ่าน |
| 6 | UI เชื่อม LINE + loading/error states | ผ่าน |

ผลรวม: deploy ขึ้น production (Render) ใช้งานได้จริงทั้งเว็บและ LINE OA

---

## 1. การตัดสินใจของ user (FINAL — ยึดตามนี้)

| # | ประเด็น | สิ่งที่เลือก |
|---|---------|-------------|
| 1 | วิธีเชื่อม account | **ผูกด้วย email (ตัวเลือก B)** — พิมพ์ email ใน LINE → หา User → set `LineUser.user_id` + ย้าย txs เดิม. **ตัด OTP/LinkCode ออก** |
| 2 | AI insight | เพิ่ม backend endpoint จริง — `POST /api/ai/...` แทน `window.claude` |
| 3 | **AI provider** (ตัดสินกลาง Sprint) | เปลี่ยนจาก provider เดิม (เจ้าหลักที่วางแผนไว้) → ใช้ **ผู้ให้บริการ AI หลัก (มี free tier)** เป็นตัวเรียกหลัก + **ผู้ให้บริการ AI สำรอง** เป็น fallback เพื่อคุมค่าใช้จ่าย |

> ตัวเลือก OTP และ LINE Login OAuth ถูกตัดออกแล้ว — เก็บเป็น future work

---

## 2. การตัดสินใจสำคัญระหว่างทาง (Decisions Log)

| # | ประเด็น | ตัดสินเป็น | เหตุผล |
|---|---------|-----------|--------|
| D1 | AI provider | ใช้ผู้ให้บริการหลักที่มี free tier + ผู้ให้บริการสำรองเป็น fallback | คุมต้นทุน sprint demo + กันล่ม ถ้าตัวหลักโดน rate limit / โควต้าหมด ก็ยังตอบได้ |
| D2 | Conservative principle ใน parser | ถ้า merchant ไม่ match keyword ใด ๆ → คืน `other` (ไม่เดา) | กันการจัดหมวดผิดที่ทำให้ insight เพี้ยน — ดีกว่าทายผิดแล้ว user เข้าใจผิด |
| D3 | Re-link safety | ย้ายข้อมูลเฉพาะกรณี LineUser เคยเป็น auto-user (line_xxx@line.local) เท่านั้น | กันเคส user link ซ้ำหลายครั้ง / สลับบัญชี → ข้อมูลของบัญชีเว็บเดิมไม่โดนเขียนทับ |
| D4 | Dedup statement | เช็คซ้ำตอน insert txs (ไม่ใช่ตอน parse) | parse PDF เร็ว / dedup อยู่ใกล้ DB จริง — กันอัปโหลดไฟล์เดิมซ้ำ |
| D5 | Budget alert trigger point | trigger 2 จุด: หลัง insert txs **และ** หลัง link สำเร็จ | ตอน link ใหม่ ๆ ข้อมูลพึ่งโผล่มา ต้องเช็คงบทันทีไม่งั้น user ต้องอัปโหลดใหม่ถึงเด้ง |
| D6 | LINE cold-start | ใช้ push_message เป็น fallback ถ้า reply token หมดอายุ | Render Free cold-start ~30s ทำให้ reply ทันบ้างไม่ทันบ้าง — fallback กันเงียบ |

---

## 3. สิ่งที่ทำจริง — ตามแผนเดิม (P0)

### 3.1 Email account linking (LINE ↔ webapp)
- LINE OA จับ pattern `เชื่อม <email>` / `link <email>` → หา User ตาม email → set `LineUser.user_id` + `linked_at` → ตอบยืนยัน
- **Guard**: ผูกได้เฉพาะ email ที่เคย login เว็บแล้ว (มี User row จริง) — ไม่เจอ → ตอบ error ชัด
- **ย้ายข้อมูล**: ย้าย transactions/imports/notifications จาก auto-user (line_xxx@line.local) ไปรวมกับ user เว็บ
- **Re-link safety (เกินแผน)**: ถ้า LineUser คนนี้เคยถูก link มาก่อน + บัญชีเดิมไม่ใช่ auto-user → **ไม่ย้ายข้อมูล** เพื่อกันข้อมูลของบัญชีเว็บเดิมโดนเขียนทับ
- ใช้ `LineUser.user_id` + `User.email` ที่มีอยู่แล้ว — **ไม่ต้อง migration**

### 3.2 AI endpoint จริง (production)
- เพิ่ม `POST /api/ai/complete` (รวม insight + chat ใน endpoint เดียว) เรียก provider จริง
- **Multi-provider architecture**:
  - **Primary**: ผู้ให้บริการ AI หลัก (มี free tier — เลือกเพราะคุมค่าใช้จ่ายได้)
  - **Fallback**: ผู้ให้บริการ AI สำรอง (เผื่อ primary ล่ม/โควต้าหมด)
  - Logic: ลอง primary ก่อน → ถ้า error ตกชั้นไป fallback อัตโนมัติ
- Frontend (`views.jsx`) เปลี่ยนจาก `window.claude.complete()` → `fetch('/api/ai/complete')` ทั้ง Insights + ChatPanel
- error handling: ถ้า key หาย/provider ล่มทั้งคู่ → ตอบ message ชัดเจน (ไม่เงียบเหมือนเดิม)

### 3.3 Budget alert ผ่าน LINE
- เมื่อ insert txs (ทั้ง web upload และ LINE PDF) → เช็คหมวดเกินงบ (Preference.category_budgets) → push LINE ไป line_user_id ของ user
- คำสั่ง LINE "งบ"/"budget" → อ่าน Preference.category_budgets แสดงสถานะใช้/งบ
- **Trigger เพิ่มหลัง link สำเร็จ (เกินแผน)**: เผื่อ user link หลังจากมี txs ค้างอยู่แล้ว — เด้งทันทีโดยไม่ต้องอัปโหลดใหม่
- ใช้ push_message (fallback ปลอดภัยจาก reply token expire)

---

## 4. งานเสริม "เกินแผนเดิม" (Day 4–5 Additions)

> ตอนวางแผน Day 1 ยังไม่มีรายการพวกนี้ — ผุดมาระหว่าง implement เพราะเจอ edge case หรือ issue จริงตอนเทสบน production

| # | งาน | เหตุผลที่ต้องทำ |
|---|-----|----------------|
| E1 | **Fix LINE bot ไม่ตอบบน production** — push fallback + ลด latency cold-start | Render Free sleep ทำให้ reply token หมดอายุ → bot เงียบ บั๊กนี้บล็อก budget alert ทั้งระบบ |
| E2 | **Statement dedup** — กันอัปโหลดไฟล์เดิมซ้ำ + Undo last import | ตอนเทสจริง user อัปไฟล์เดิมโดยไม่ตั้งใจ → txs ซ้ำ → insight เพี้ยน |
| E3 | **Reset Statement** — ปุ่มล้างข้อมูลเริ่มใหม่ (txs + imports + notifications) | user เทสไปเทสมาข้อมูลเละ ต้องมีปุ่มรีเซ็ตเริ่มใหม่ได้ |
| E4 | **Categorization improvement ทั้ง 4 ธนาคาร** | จัดหมวดผิดในหลายเคส — ขยาย keyword + เปลี่ยน rule order + strip prefix noise |
| E4.1 | KBank — strip prefix `Ref` ก่อนจัดหมวด + ขยาย keyword หมวด food/groceries (ไทย) | merchant ที่ขึ้นต้นด้วย ref code ถูก match กับหมวดผิด |
| E4.2 | KTB + GSB — preserve "merchant extra info" ก่อนส่งเข้า `categorize()` | parser เดิม trim ทิ้งทำให้ context หายไป |
| E4.3 | SCB — ปรับ merchant extraction (6 pattern) + scrub bank markers | SCB statement มี layout หลากหลายกว่าธนาคารอื่น |
| E4.4 | Refactor `categorize()` — ordered rules + ขยายเป็น 7 หมวด | rule order เดิมทำให้ keyword ที่กว้างชนะ keyword ที่เฉพาะ |
| E5 | **PII protection sweep** — ตรวจสอบ + ล้างข้อมูลในโค้ดให้ปลอดภัยก่อนเปลี่ยน repo เป็น public | จะส่งอาจารย์ ต้องมั่นใจไม่มี email/token/PII หลุดใน commit history |
| E6 | **Multi-provider AI fallback** (ขยายจาก D1) | เพิ่ม resilience — ถ้า primary โดน rate limit → ตกไป fallback อัตโนมัติ ไม่มีดาวน์ไทม์ฝั่ง user |

**สรุปขอบเขตที่เกินแผน**: 6 หัวข้อใหญ่ (E1–E6) เกินจาก scope เริ่มต้น 3 ฟีเจอร์ — รวม Sprint 3 ส่งงาน **9 หัวข้อใหญ่** (3 ตามแผน + 6 เพิ่ม)

---

## 5. สรุปการเปลี่ยนแปลงเชิงสถาปัตยกรรม

| จุด | ก่อน Sprint 3 | หลัง Sprint 3 |
|-----|-------------|--------------|
| LINE user ↔ web user | คนละ `user_id` เสมอ (auto-create line_xxx@line.local) | link ผ่าน email → user_id เดียวกัน ใช้ budget/txs ร่วมกัน |
| AI Insight + Chat | เรียก `window.claude` (เงียบบน production) | fetch `/api/ai/complete` (provider จริง + fallback) |
| Budget alert | ไม่มี | push LINE ทันทีตอน txs เกินงบ + ตอน link สำเร็จ |
| Statement upload | อัปซ้ำได้ ไม่มี undo | dedup + undo last import + reset statement |
| Parser ความแม่นยำหมวด | จัดผิดบ่อย ในหลายธนาคาร | 7 หมวด ordered rules + ปรับ parser 4 ธนาคารแยกเคส |
| AI provider strategy | ผูกกับ provider เดียว | multi-provider พร้อม fallback |

---

## 6. ความเสี่ยง / ข้อจำกัดที่เหลือ (ตอนปิด Sprint)

| รายการ | สถานะ | หมายเหตุ |
|--------|------|---------|
| Email linking ไม่ verify เจ้าของ email | ยอมรับ tradeoff ใน demo | production จริงควรใช้ LINE Login OAuth — เป็น future work |
| Render Free cold-start ~30s | ลด impact ด้วย push fallback | ถ้าจะให้ smooth ขึ้นต้อง upgrade plan / warmer |
| AI provider key dependency | ตั้ง env บน Render dashboard | ถ้า key ทั้งสองเจ้าหาย → ปุ่ม AI ตอบ error ชัด (ไม่เงียบเหมือนก่อน Sprint 3) |
| DB เป็น Render Free Postgres | หมดอายุ ~27 มิ.ย. 2026 | user วางแผนย้าย Supabase — แค่เปลี่ยน DATABASE_URL ไม่ต้องแก้ code |

---

## 7. สรุป (ทำไปแล้ว / เหลืออะไร / ใครค้าง)

- **ทำแล้ว (P0 ตามแผน)**: email linking + AI endpoint + budget alert + UI เชื่อม LINE + loading/error — ครบ deploy บน production
- **ทำเพิ่มเกินแผน**: 6 หัวข้อ (LINE bot fix, dedup, undo, reset, parser improvement 4 ธนาคาร, PII sweep, multi-provider fallback)
- **เหลือเป็น future work** (ไม่ได้ block Sprint Goal):
  - LINE Login OAuth (แทน email-based linking)
  - Google OAuth จริง (ตอนนี้เป็น email upsert ล้วน)
  - ย้าย DB ไป Supabase (รอ user เลือก)
  - เปลี่ยน repo เป็น public ส่งอาจารย์
- **ค้างรอ user**: ไม่มี — Sprint 3 ปิดได้

---

## Next step ที่แนะนำ

Sprint 3 ปิดสมบูรณ์แล้ว ไม่มี action ค้าง. ขั้นถัดไปขึ้นกับ user เลือก:
1. ส่งงานอาจารย์ (เปลี่ยน repo เป็น public + เตรียม slide เดโม่)
2. เริ่มวางแผน Sprint 4 (Supabase migration / OAuth จริง / improve AI prompt)

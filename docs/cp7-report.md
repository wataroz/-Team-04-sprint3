# CP7 — Prototype v2 Improvement Report + Final Demo

> Sprint 5 final deliverable — ปรับ Prototype v1 → Prototype v2 ตาม feedback จาก Sprint 4 + เพิ่มงานชุดใหม่ (Settings page, PDPA, Brand v2, Theme toggle, LINE Login OAuth)

**Live demo**: https://moneymind-team-04-sprint3.onrender.com
**Branch**: `feature/flask-react`
**อัปเดต**: 2026-06-14

---

## 1.1 Sprint 5 Goal

ทีมเราเลือกปรับปรุง Prototype v2 ของ MoneyMind ให้:

1. ใช้งานได้ดีขึ้นบนมือถือ (Responsive overhaul ครบ 5 หน้าหลัก)
2. แก้บั๊ก LINE Bot ที่ส่ง PDF ซ้ำ + รองรับ PDF ที่ใส่รหัสผ่าน
3. ขยาย parser ให้อ่าน statement ภาษาอังกฤษ + SCB ได้เต็มรูปแบบ
4. เพิ่ม **หน้า Settings 4 หมวด** (โปรไฟล์/การแสดงผล/LINE/แจ้งเตือน)
5. เพิ่ม **ระบบลบบัญชีแบบมีระยะผ่อนผัน 30 วัน** (ตามกฎหมายคุ้มครองข้อมูลส่วนบุคคล — PDPA)
6. ออกแบบ **Brand v2** (โลโก้+สีใหม่) และทำให้ติดตั้งเป็นแอปบนมือถือได้ (PWA — เว็บแอปที่ลงเครื่องได้เหมือนแอปจริง)
7. เพิ่ม **สลับธีมสว่าง/มืด** (จำค่าข้ามอุปกรณ์)
8. เพิ่ม **LINE Login OAuth** (ระบบยืนยันตัวตนผ่านปุ่ม LINE คลิกเดียว — แทนการพิมพ์ email)

อ้างอิงจาก feedback ของ Sprint 4 (CP6 รอบสอง) — ผู้ใช้ขอความปลอดภัย, ความเป็นส่วนตัว, และประสบการณ์บนมือถือที่ดีขึ้น

---

## 1.2 Feedback-to-Fix Mapping

| Feedback / Insight | Priority | สิ่งที่แก้ใน Sprint 5 |
|---|---|---|
| Mobile แคบ layout พัง | P0 | ทำหน้าจอให้ปรับตามขนาดมือถือทุกขนาด (320px ถึง iPad) + เพิ่มแถบเมนูล่างบนมือถือ (เหมือนแอปทั่วไป) + กราฟปรับสีให้ชัดบนจอเล็ก |
| LINE Bot ส่ง PDF ซ้ำ | P0 | กันบอทตอบซ้ำ — แต่ละข้อความตอบได้ครั้งเดียว + ถ้าตอบไม่ทันให้ส่งแบบ push (เด้งเข้าแชทแทน) + ลบรายการ PDF ที่ค้างอัตโนมัติ |
| Parser ภาษาอังกฤษ + SCB ไม่ครบ | P1 | เพิ่มคำอ่าน statement ภาษาอังกฤษ (เช่น TRANSFER, PAYMENT) ในทุกธนาคาร + แก้รูปแบบ SCB ที่อ่านไม่ได้ |
| ผู้ใช้ขอลบบัญชี/ขอข้อมูลส่วนตัว (PDPA) | P0 | เพิ่มหน้า Settings + ปุ่มลบบัญชีแบบมีระยะผ่อนผัน 30 วัน + ปุ่มยกเลิกการลบ + ดาวน์โหลดข้อมูลตัวเองเป็น CSV ได้ |
| โลโก้/ไอคอนไม่สวย + ติดตั้งเป็นแอปไม่ได้ | P1 | ออกแบบโลโก้ใหม่ (block M สีครีม/ทอง) + ทำชุดไอคอนครบทุกขนาด + ติดตั้งเป็นแอปบนมือถือได้ + สลับธีมสว่าง/มืด |
| Login ด้วย email อย่างเดียว ไม่ปลอดภัย | P1 | เพิ่มปุ่ม "เชื่อมด้วย LINE" — กดครั้งเดียว LINE ยืนยันตัวตนให้ (เหมือน Login with Google) — ปลอดภัยกว่าพิมพ์ email เอง + คงคำสั่งเดิมเป็นทางสำรอง |

---

## 1.3 Prototype v2 Evidence

| สิ่งที่ build เสร็จ | Evidence (ทดสอบ/ดูได้ที่ไหน) |
|---|---|
| หน้าจอปรับขนาดได้ 4 ระดับ (มือถือ/แท็บเล็ต/โน้ตบุ๊ก/จอใหญ่) | Screenshot 5 หน้าหลักบนจอ 375px |
| LINE Bot ไม่ส่ง PDF ซ้ำอีก | Screenshot แชท LINE + ตรวจสอบในฐานข้อมูล ไม่มีรายการซ้ำ |
| รองรับ PDF ที่ใส่รหัสผ่าน (ทั้งใน LINE และเว็บ) | Screenshot + คลิป flow ใน LINE (ใส่รหัส 3 ครั้ง, หมดเวลา 5 นาที) |
| อ่าน statement ภาษาอังกฤษ + SCB ได้ถูกต้อง | ตารางเปรียบเทียบจำนวนรายการที่อ่านได้ ก่อน-หลัง (KBank ENG 0→276 รายการ, SCB 18→45 รายการ) |
| หน้า Settings 4 หมวด | Screenshot ทั้ง 4 แท็บ (โปรไฟล์/การแสดงผล/LINE/แจ้งเตือน) |
| ลบบัญชี + พักไว้ 30 วัน + ยกเลิกได้ + ดาวน์โหลดข้อมูล (PDPA) | Screenshot ขั้นตอนยืนยันลบบัญชี (3 ขั้น) + แบนเนอร์ยกเลิกการลบ |
| โลโก้ใหม่ + ติดตั้งเป็นแอปบนมือถือได้ | Screenshot "Install MoneyMind?" บน Android Chrome + ไอคอนหน้า home screen |
| สลับธีมสว่าง/มืด — จำค่าข้ามอุปกรณ์ | Screenshot toggle + แท็บสีของระบบเปลี่ยนตามธีมอัตโนมัติ |
| ระบบจำหมวดที่ผู้ใช้แก้เอง (Learning Loop) | Screenshot ปุ่มแก้ไขหมวด + checkbox "จำตัวเลือก" — รอบหน้าจัดให้ |
| ปุ่ม "วิเคราะห์ด้วย AI" + ห้อง "คุยกับ Mind" | Screenshot หน้า Insights + กล่องแชท |
| ระบบลบ user ที่หมดอายุอัตโนมัติ (Lazy cleanup) | log บอก "รัน cleanup 1 ครั้งต่อวัน" — เรียกตอน user คนแรกของวัน login |
| ปุ่ม "เชื่อมด้วย LINE" + ระบบยืนยันตัวตนจริง | Screenshot ปุ่ม + คลิป flow OAuth (กดปุ่ม → ไป LINE → ยืนยัน → กลับมา เชื่อมสำเร็จ) |
| "ชื่อที่แสดง" ขึ้นในแอปจริงๆ (ก่อนหน้านี้กรอกได้แต่ไม่ขึ้น) | Screenshot ก่อน/หลัง — คำทักทาย "สวัสดี [ชื่อที่แสดง]" |
| แก้บั๊กมือถือ 3 จุด (ปุ่มหมวด/ปุ่ม save/แท็บ Settings) | Screenshot ก่อน/หลัง แต่ละจุด |

---

## 1.4 Before/After Comparison

| จุดเปรียบเทียบ | v1 | v2 |
|---|---|---|
| **Mobile** | layout พังที่ ≤768px, ไม่มี bottom nav | ปรับขนาดได้ทุกหน้าจอ 320px ขึ้นไป + bottom nav อัตโนมัติ |
| **LINE Bot** | ส่ง PDF ครั้งเดียวอาจตอบซ้ำ + ไม่รับ PDF ใส่รหัส | ตอบครั้งเดียวต่อข้อความ + รับ PDF ใส่รหัสผ่านได้ |
| **Parser** | KBank EN: 0 รายการ, SCB: 18 รายการ | KBank EN: 276 รายการ, SCB: 45 รายการ |
| **Web UX** | ตั้งค่ากระจาย floating panel | หน้า Settings รวมศูนย์ 4 แท็บ |
| **Privacy / PDPA** | ลบบัญชีไม่ได้, ดาวน์โหลดข้อมูลตัวเองไม่ได้ | ลบบัญชี + พักไว้ 30 วัน + ยกเลิกการลบได้ + Export CSV |
| **Branding + PWA** | โลโก้เดิม wave M สีแชมเปญ — ติดตั้งเป็นแอปไม่ได้ | block M ครีม/ทอง + favicon ครบ + Android Chrome ติดตั้งเป็นแอปได้ |
| **Theme** | ธีมเดียว (มืด) | สลับสว่าง/มืดได้ + จำค่าในระบบ + เปิดเครื่องอื่น ธีมเหมือนเดิม |
| **LINE Linking** | พิมพ์ "เชื่อม email" — ไม่ verify ว่าเป็นเจ้าของ email จริง | ปุ่มเชื่อม 1 คลิกผ่าน LINE — verify ตัวตนจริง + คงคำสั่งเดิมเป็น fallback |

---

## 1.5 Final Demo Evidence

### Live URL
https://moneymind-team-04-sprint3.onrender.com

### Core Flow Test (ผ่านครบ)
1. ✅ Login ด้วย email → เข้าหน้า Overview
2. ✅ Upload PDF statement → parse + จัดหมวดอัตโนมัติ
3. ✅ แก้หมวด tx + "จำตัวเลือก" → ครั้งหน้า merchant เดียวกัน จัดหมวดที่บันทึก
4. ✅ กด "วิเคราะห์ด้วย AI" → AI สรุปข้อมูล
5. ✅ เปิด "คุยกับ Mind" → ถามคำถาม → AI ตอบ
6. ✅ Settings 4 แท็บ ทำงานครบ
7. ✅ สลับธีมสว่าง/มืด → จำค่า → reload ก็ยังเหมือนเดิม
8. ✅ ลบบัญชี → modal 3 ขั้น → Export CSV → schedule delete → login กลับ → ยกเลิกได้
9. ✅ LINE Login OAuth (สำหรับ user ใน developer role) — กดปุ่ม → ไป LINE → กลับมา linked
10. ✅ คำสั่ง "เชื่อม email" ใน LINE bot — ยังทำงานเป็น fallback

### Hardware Demo
- เปิดเว็บใน Android Chrome → ขึ้น banner "ติดตั้ง MoneyMind?"
- กด Install → ไอคอนขึ้นที่ home screen
- เปิดจากไอคอน → fullscreen ไม่มี browser bar

---

## 1.6 Individual Contribution

| สมาชิก | Contribution Sprint 5 |
|---|---|
| **WA** | Parser EN keywords + SCB regex fix, LINE Bot duplicate fix + password state machine, **LINE Login OAuth (state JWT 10 นาที + id_token verify) + safety guard ย้าย tx เฉพาะ auto-user, ลบ MerchantOverride ก่อน delete user (กัน FK violation — ข้อมูลอ้างอิงค้าง)** |
| **BEST** | Mobile responsive overhaul ครบ 5 views + chart polish + **Brand v2 CSS tokens (cream/gold palette) + dual-theme (สว่าง/มืด) + แก้ stacking context bug (กฎซ้อนชั้น CSS — ทำให้ปุ่ม save ใน modal ไม่ถูกแถบเมนูล่างทับ)** |
| **ACHI** | UI text polish + nav labels ย่อ + **Settings page 4 tabs (Profile / Display / LINE / Notifications) + Theme picker + active tab UX polish + Cancel Delete banner** |
| **AJ** | Web password PDF + size/page guards (กัน server crash) + Sprint 4 docs + **Hard delete 30-day grace (PDPA) + Export CSV + Lazy cleanup on login (รันงาน cleanup ตอน user คนแรกของวัน login — ไม่ต้องพึ่ง cron) + Display name field + responsive bug fix หมวดในมือถือ** |
| **REW** | Pre-push review + secret scan + **PII guard (กันใส่ commit hash/path/provider name หลุดออก Notion) + theme injection guard review** |

---

## 1.7 Known Issues

| Known Issue | กระทบ | Severity | แผน |
|---|---|---|---|
| Cold-start ~30-60 วินาที (hosting แบบ free tier) | Request แรกหลังไม่มี traffic 15 นาที ช้า | Medium | ย้าย hosting แบบจ่ายเงิน + keep-alive ping หลัง demo |
| Database sandbox หมดอายุ ~27 มิ.ย. 2569 | Database หยุดทำงาน | High | ย้ายไป Supabase (database cloud อีกเจ้า — เปลี่ยน connection string จุดเดียว) ปลายเดือน |
| LINE Channel ยัง Developing mode | ใช้งานได้เฉพาะทีม + อาจารย์ (developer role) หรือใช้คำสั่ง email fallback | Medium | ขอ publish channel หลังเตรียม Privacy Policy + ToS เสร็จ (post-graduation) |
| Google/Apple Sign-In ปุ่ม fake (ซ่อนอยู่) | SSO ของจริงยังไม่ wire | Low | OAuth จริง backlog |
| ไม่มี real authentication (ใช้แค่ email — ไม่มี password) | เหมาะเฉพาะ demo/sandbox | Medium | ทำ password + OAuth จริง post-graduation |

---

## 1.8 Next Step (Backlog post-Sprint 5)

หลัง demo จบ ทีมมีงานเก็บต่อ:

### Infrastructure
- ย้าย DB → **Supabase** (Postgres ฟรีถาวร — ก่อนหมดอายุ ~27 มิ.ย. 2569)
- เสริม **GitHub Actions cron** ยิง cleanup endpoint ทุก 24h (เผื่อไม่มี user login 30+ วัน)
- ตั้ง **UptimeRobot keep-alive** กัน cold start (ฟรี + ไม่ต้องจ่าย Render Starter)
- เสริม `ProxyFix` middleware (defense-in-depth สำหรับ HTTPS host_url)

### Security / Auth
- **Real authentication** — password (bcrypt hash) + Google Sign-In OAuth จริง (ปัจจุบันปุ่ม fake ซ่อนอยู่)
- **Publish LINE Login Channel** — ต้องเตรียม Privacy Policy + Terms of Service URL จริงก่อน
- **Rate limiting** AI endpoint
- เปลี่ยน `datetime.utcnow()` → `datetime.now(timezone.utc)` (forward-compat Python 3.12+)

### UX / Features
- **Learning Loop fuzzy match** — รุ่นปัจจุบัน exact string match จำไม่ได้ถ้าชื่อ merchant ต่างกัน (เช่น "7-11 ขนม" vs "7-11 กาแฟ") → Sprint 6+ ทำ brand prefix extract
- เพิ่มหมวด 9 → 12-15 + hierarchical (main/sub)
- **Confidence Indicator** badge (คู่ Learning Loop)
- **AI Fallback for "other"** — cache merchant→category
- **Year picker / YoY** view รายปี
- Theme เพิ่ม **"ตามระบบ" (System)** — `prefers-color-scheme`
- Settings mobile — visual scroll indicator
- **Profile avatar upload** (icon set พร้อมแล้ว)
- เพิ่ม i18n key สำหรับ error codes ที่เหลือใน LINE OAuth (`missing_params`, `not_configured`, `user_missing`, `link_failed`)

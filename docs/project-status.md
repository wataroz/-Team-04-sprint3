# MoneyMind — สรุปสถานะโปรเจกต์ (Project Status)

> เอกสารสรุปภาพรวมสำหรับอาจารย์และทีม
> **ณ วันที่**: 12 กรกฎาคม 2026
> **Sprint**: 3 (Team 04) — ปิด Sprint 5 + Post-Sprint Follow-ups ครบแล้ว

---

## 1. โปรเจกต์คืออะไร

**MoneyMind** — แอปจัดการการเงินส่วนตัวระดับ luxe:
อ่าน Statement PDF ธนาคารไทย → จัดหมวดอัตโนมัติ (+ Learning Loop) → วิเคราะห์ด้วย AI → ลบบัญชี/Export ข้อมูลเองได้ (PDPA-compliant)

เป็นได้ทั้ง **เว็บแอป (PWA ติดตั้งได้)** + **LINE Bot** ที่แชร์ข้อมูลชุดเดียวกัน

---

## 2. Tech Stack

| ส่วน | เทคโนโลยี |
|------|-----------|
| Backend | Flask 3.0 + SQLAlchemy 2.0 |
| Frontend | React 18 via Babel CDN (ไม่มี build step) |
| Database | PostgreSQL (prod / **Supabase**) — SQLite (local) |
| PDF Parser | pdfplumber |
| LINE Bot | line-bot-sdk v3 (webhook + push fallback) |
| AI | Gemini (primary, free) → Anthropic Claude (fallback) |
| Server | Gunicorn (prod, `--workers 2`) / Flask dev (local) |
| Hosting | Render Free tier (Singapore), auto-deploy on push |
| PWA | manifest.webmanifest + Apple touch + Android maskable |

---

## 3. ฟีเจอร์ที่ Live on Production

### Core — การเงิน
- Flask backend ~27 logical endpoints (29 route decorators)
- React frontend 6 views: overview / transactions / upload / budgets / insights / settings
- PDF Parser 4 ธนาคาร: **KBank | GSB/MyMo | KTB | SCB** (9 หมวด, 40-50 keywords/หมวด)
- Statement dedup + Undo (ยกเลิก import ล่าสุด) + Reset
- Category budgets + budget alert

### AI + Learning
- AI chain: **Gemini → Anthropic fallback** (ปุ่ม "วิเคราะห์ด้วย AI" + ChatPanel "คุยกับ Mind")
- **Learning Loop** — user แก้หมวด → ระบบจำ (MerchantOverride) → ครั้งหน้าจัดหมวดเดิม
- Insights **empty state** (แทน fake demo cards เมื่อยังไม่มี tx)

### LINE Bot
- Webhook + คำสั่ง (สรุป/ยอด/เดือนนี้/วิเคราะห์/ช่วย) + ส่ง PDF
- Auto-greet เมื่อ add friend
- **Push fallback** (reply token หมดอายุ → push_message)
- **Chat-driven password flow** (encrypted PDF → ใส่ password ในข้อความถัดไป, 3 attempts, TTL 5 นาที)
- **LINE Login OAuth 2.0** — primary linking surface (email command เก่าเก็บไว้เป็น fallback)
- Budget alert push

### บัญชี + PDPA
- **Settings page (4 sections)**: โปรไฟล์ / การแสดงผล / เชื่อม LINE / การแจ้งเตือน
- **Hard delete + 30-day grace period** + CancelDeleteBanner
- **Export CSV** (PDPA data portability)
- **Lazy cleanup on login** (grace period cron แบบ zero external dependency)

### UI / UX / Brand
- **Light/Dark theme toggle** (Cream Luxe ↔ Dark Luxe, persist ใน DB → cross-device)
- **Brand v2** (block M logo + cream/gold + icon bundle) — **PWA installable**
- Responsive 4 breakpoints (sidebar → bottom nav ≤1024px)
- Settings UX polish (back button + active tab indicator + scroll)
- display_name render จริงใน UI (greeting + sidebar + avatar)

---

## 4. Deployment Status

| หัวข้อ | รายละเอียด |
|--------|-----------|
| Live URL | https://moneymind-team-04-sprint3.onrender.com |
| Branch | `feature/flask-react` (Render Dashboard) |
| Start cmd | `gunicorn backend.app:app --workers 2 --timeout 120` |
| Auto-deploy | push → rebuild ~3-5 นาที |
| Database | **Supabase** (ย้ายจาก Render Postgres 3 ก.ค. 2026) — Singapore, Free NANO 500MB, Session pooler (IPv4) |
| PWA | ติดตั้งได้ (Android Chrome ขึ้น "Install MoneyMind?") |

### ข้อจำกัดระดับ demo-grade (ควรแจ้งอาจารย์)
- **Render Free cold-start** 30-60 วินาที หลัง idle 15 นาที (request แรกช้า)
- **Supabase Free pause** ถ้า inactive 7 วัน
- **ยังไม่มี Authentication เต็มระบบ** — ทุก endpoint รับ `user_id` เปิด (เหมาะแค่ demo)
- **LINE Login Channel = Developing mode** — ใช้ได้เฉพาะ developer role (ต้อง invite อาจารย์/ทีมเป็น developer หรือ Publish channel ก่อน production)

---

## 5. Backlog สำคัญ (Post-demo)

### DB / Infrastructure
- External cron สำหรับ grace cleanup (GitHub Actions — กันเคส "ไม่มี login 30+ วัน")
- UptimeRobot keep-alive ping (กัน Render cold-start)
- อัปเกรด SDK `google-generativeai` → `google-genai`
- เปลี่ยน `datetime.utcnow()` → `datetime.now(timezone.utc)` (Python 3.12+)
- เสริม `ProxyFix` middleware (HTTPS host_url — defense-in-depth)

### Security / Auth
- Authentication เต็มระบบ (ทุก endpoint)
- **Publish LINE Login Channel** + Privacy Policy + ToS URLs
- Google Sign-In OAuth จริง (ปุ่ม fake ซ่อนอยู่)
- Rate limiting AI endpoint
- PDPA consent UI ก่อน OAuth

### UX / Features
- **Learning Loop fuzzy match** (ปัจจุบัน exact match — จำไม่ได้ถ้า merchant มี detail ต่างกัน)
- เพิ่มหมวด 9 → 12-15 + hierarchical main/sub
- Confidence Indicator badge
- มุมมองรายปี (Year picker, YoY)
- Theme "ตามระบบ (System)" (`prefers-color-scheme`)
- Profile avatar upload (มี profile-*.png set รอใช้)

### Project
- เปลี่ยน repo เป็น **Public** (สำหรับส่งอาจารย์)
- Custom domain แทน `.onrender.com`

---

## 6. สรุป Commit ล่าสุดที่สำคัญ

| Commit | สรุป |
|--------|------|
| `88e753d` | docs(infra): mark Supabase migration complete + ignore preview/pptx |
| `45e190c` | fix(ai): pin Gemini เป็น `gemini-2.5-flash` (เลิกใช้ `-latest` alias ที่ route ไป quota ต่ำ) |
| `92de348` | fix(insights): แสดง empty state แทน fake demo cards เมื่อยังไม่มี tx |
| `c148a05` | docs(sprint5): เพิ่ม CP7 report + 6 supporting docs + README highlights |
| `7a34dc2` | feat(line): เพิ่ม LINE Login OAuth 2.0 เป็น primary linking surface |
| `732c7c1` | fix(ui): ลบ pageIn animation → modal หลุด stacking-context trap |
| `77b3514` | fix(ui): แก้ cat-picker ถูก clip บนมือถือเล็ก (min-width:0 + scrollbar-gutter) |
| `3ad41be` | feat(ui): render display_name ใน greeting + sidebar (name fallback) |

---

## 7. สรุปภาพรวม

| หัวข้อ | สถานะ |
|--------|-------|
| Sprint 5 + Post-Sprint Follow-ups | ✅ ปิดครบ |
| ระบบ Live on production | ✅ ใช้งานได้จริง |
| DB migration → Supabase | ✅ เสร็จ (3 ก.ค. 2026) |
| CP7 deliverable + docs | ✅ ครบ 7 เอกสาร |
| งานที่รอ | Backlog post-demo (auth เต็มระบบ, public repo, LINE Publish, fuzzy match) |

> เอกสารนี้อ้างอิงข้อมูลจาก `CLAUDE.md` (Current Status 3 ก.ค. 2026) + `git log` ล่าสุด ณ 12 ก.ค. 2026

# Known Issues — Sprint 5 (Demo-grade vs Production-grade)

> ปัญหาที่ทราบใน Prototype v2 — โปร่งใสว่าอะไรเหมาะกับ demo, อะไรต้องแก้ก่อนใช้จริง

**อัปเดต**: 2026-06-14

---

## Known Issues

| # | Issue | กระทบ | Severity | แผน |
|---|---|---|---|---|
| 1 | Cold-start ~30-60 วินาที (hosting แบบ free tier) | Request แรกหลังไม่มี traffic 15 นาที ช้า | Medium | ย้าย hosting แบบจ่ายเงิน + keep-alive ping หลัง demo |
| 2 | ~~Database sandbox หมดอายุ ~27 มิ.ย. 2569~~ ✅ **ย้าย Supabase สำเร็จ 3 ก.ค. 2569** | (แก้แล้ว) — DB ใหม่บน Supabase Singapore Free tier | ~~High~~ Resolved | ย้ายเสร็จ (fresh start, Session pooler IPv4) — smoke test login/AI ผ่าน |
| 3 | LINE Channel ยัง Developing mode | ใช้งานได้เฉพาะทีม + อาจารย์ (developer role) หรือใช้คำสั่ง email fallback | Medium | ขอ publish channel หลังเตรียม Privacy Policy + ToS เสร็จ (post-graduation) |
| 4 | Google/Apple Sign-In ปุ่ม fake (ซ่อนอยู่) | SSO ของจริงยังไม่ wire | Low | OAuth จริง backlog |
| 5 | ไม่มี real authentication (ใช้แค่ email — ไม่มี password) | เหมาะเฉพาะ demo/sandbox | Medium | ทำ password + OAuth จริง post-graduation |

---

## Demo-grade vs Production-grade

ทีมแยกชัดว่าอะไรเหมาะกับ demo, อะไรต้องแก้ก่อนใช้กับ user จริง:

### ตอนนี้ — Demo-grade (เหมาะกับ Sprint review + อาจารย์ทดสอบ)
- LINE Channel: Developing mode
- ไม่มี real authentication (ใช้แค่ email — ไม่มี password)
- Google/Apple Sign-in ปุ่ม fake (UI พร้อม OAuth flow ยังไม่ wire)
- Render Free tier (มี cold start 30-60 วินาที)
- Privacy Policy + ToS ยังไม่มี

### Production-grade — Backlog post-graduation
- LINE Channel published + Privacy Policy + ToS
- Real authentication (password + Google OAuth wired จริง)
- Custom domain + Render Starter plan ($7/month no cold start)
- ~~Supabase migration~~ ✅ **ทำแล้ว 3 ก.ค. 2569** (fresh start, Session pooler Singapore)
- Rate limit + monitoring (Sentry)
- ProxyFix middleware (defense-in-depth สำหรับ HTTPS host_url)

---

## Minor warnings (ไม่ block)

### `user_cancelled` toast wording (แก้แล้ว Sprint 5)
- เดิม: ตก fallback "ล้มเหลว" — ทำให้ user คิดว่าระบบพัง
- ตอนนี้: toast "คุณยกเลิกการเชื่อม LINE" ตรงประเด็น

### `datetime.utcnow()` deprecation Python 3.12+
- ปัจจุบันใช้ Python 3.11 → ยังไม่เตือน
- เมื่ออัปเกรด Python 3.12+ จะมี DeprecationWarning → เปลี่ยน → `datetime.now(timezone.utc)` ในงาน rount-cleanup

### ProxyFix middleware (defense-in-depth)
- ปัจจุบัน user ตั้ง `LINE_LOGIN_CALLBACK_URL` ใน env แล้ว → fallback ไม่ถูกเรียก
- เผื่อ deploy environment ใหม่ที่ลืมตั้ง env → fallback `request.host_url` อาจคืน `http://` (เพราะ Render proxy strip HTTPS)
- เพิ่ม `werkzeug.middleware.proxy_fix.ProxyFix` → safe fallback

---

## Cross-reference

- [docs/cp7-report.md](cp7-report.md) — CP7 รายงานเต็ม (section 1.7 + 1.8)
- [docs/final-demo.md](final-demo.md) — Demo evidence ที่ผ่าน

# Individual Contribution — Sprint 5

> Evidence log ของสมาชิกแต่ละคนใน Sprint 5

**อัปเดต**: 2026-06-14

---

## Contribution table

| สมาชิก | Contribution Sprint 5 |
|---|---|
| **WA** | Parser EN keywords + SCB regex fix, LINE Bot duplicate fix + password state machine, **LINE Login OAuth (state JWT 10 นาที + id_token verify) + safety guard ย้าย tx เฉพาะ auto-user, ลบ MerchantOverride ก่อน delete user (กัน FK violation — ข้อมูลอ้างอิงค้าง)** |
| **BEST** | Mobile responsive overhaul ครบ 5 views + chart polish + **Brand v2 CSS tokens (cream/gold palette) + dual-theme (สว่าง/มืด) + แก้ stacking context bug (กฎซ้อนชั้น CSS — ทำให้ปุ่ม save ใน modal ไม่ถูกแถบเมนูล่างทับ)** |
| **ACHI** | UI text polish + nav labels ย่อ + **Settings page 4 tabs (Profile / Display / LINE / Notifications) + Theme picker + active tab UX polish + Cancel Delete banner** |
| **AJ** | Web password PDF + size/page guards (กัน server crash) + Sprint 4 docs + **Hard delete 30-day grace (PDPA) + Export CSV + Lazy cleanup on login (รันงาน cleanup ตอน user คนแรกของวัน login — ไม่ต้องพึ่ง cron) + Display name field + responsive bug fix หมวดในมือถือ** |
| **REW** | Pre-push review + secret scan + **PII guard (กันใส่ commit hash/path/provider name หลุดออก Notion) + theme injection guard review** |

---

## Detail ของแต่ละคน

### WA (Backend + Parser + LINE OAuth)
**Sprint 5 main**:
- Parser EN keywords สำหรับ KBank/GSB/KTB/SCB (TRANSFER, PAYMENT, WITHDRAW, DEPOSIT)
- SCB regex fix: เพิ่ม 6 patterns รับ statement หลายเวอร์ชั่น
- LINE Bot duplicate PDF fix: reply token single-use + push fallback + clear stale row
- Password state machine: encrypted PDF buffer ใน LinePendingPdf (TTL 5 นาที, max 3 attempts, "ยกเลิก" ได้)
- LINE Login OAuth implementation (Sprint 5 ปิดท้าย)
- State JWT signing + id_token verify
- Safety guard cleanup (MerchantOverride delete ก่อน FK)

### BEST (UX/UI + Theme + Mobile)
**Sprint 5 main**:
- Mobile responsive overhaul ครบ 5 views
- Chart polish (sparkline + donut + bar)
- Brand v2 CSS tokens (cream `#F5EFE3` / gold `#D4B978`)
- Dual-theme (Cream Luxe light + Dark Luxe) — toggle อยู่ใน Settings
- Smooth 220ms transition ทุก surface
- Stacking context bug fix (Lesson #14 — ลบ pageIn animation)
- Cat-picker mobile clip fix
- Settings tabs Grid 2x2 (mobile) + 4x1 (tablet)

### ACHI (Frontend + Settings)
**Sprint 5 main**:
- Settings page 4 tabs structure
- Theme picker UI (sun/moon toggle + aria-pressed)
- Active tab indicator polish (accent border + bold + soft bg)
- Back button มุมซ้ายบน + scrollIntoView mobile
- CancelDeleteBanner sticky top
- LINE Login button + URL query handler
- i18n keys (TH + EN) ~170 keys + new OAuth error mapping

### AJ (Backend + PDPA + Cleanup)
**Sprint 5 main**:
- Web password PDF + size/page guards (กัน server crash)
- PDF max size 8MB + max pages 50
- Hard delete + 30-day grace period
- Export CSV (PDPA data portability)
- Cascade delete order (FK-safe)
- Lazy cleanup on login pattern
- `_LAST_AUTO_CLEANUP` + 24h interval guard
- Display name field (User model + API)
- Mobile responsive bug fix (หมวดในมือถือ)

### REW (Pre-push Review + Security)
**Sprint 5 main**:
- Pre-push review ทุก push (10 ด้าน: secret/lint/test/.gitignore/commit msg/diff sanity/PII/migration safety/responsive/regression)
- Secret scan (LINE tokens / DATABASE_URL / API keys / FLASK_SECRET_KEY)
- PII guard catch — กันใส่ commit hash/path/provider name หลุดออก Notion
- Theme injection guard review (whitelist 'light'/'dark' strict, case-sensitive)
- Stale brand color sync (4 จุดหลัง Brand v2)
- Hardcoded `rgba(0,0,0,...)` → semantic tokens

---

## Cross-reference

- [docs/sprint5-build-log.md](sprint5-build-log.md) — Build log + Evidence
- [docs/cp7-report.md](cp7-report.md) — CP7 รายงานเต็ม (section 1.6)


<div align="center">

# 💰 MoneyMind

### AI Financial Co-pilot — ผู้ช่วยจัดการการเงินส่วนตัวที่เข้าใจคุณ

*"เงินของคุณเล่าเรื่องของมันเอง — เราแค่ช่วยฟัง"*

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![LINE](https://img.shields.io/badge/LINE_Bot-Messaging_API-00C300?logo=line&logoColor=white)](https://developers.line.biz/)
[![Render](https://img.shields.io/badge/Deployed-Render-46E3B7?logo=render&logoColor=white)](https://render.com)

**[🌐 Live Demo](https://moneymind-team-04-sprint3.onrender.com)** · **[💬 LINE Bot](#-line-bot)** · **[📖 Documentation](#-features)**

</div>

---

## 📖 Overview

**MoneyMind** เป็นแอปพลิเคชันจัดการการเงินส่วนตัวที่:

- 📄 **อ่าน Statement PDF** จากธนาคารไทย 4 แห่งโดยอัตโนมัติ (รองรับ PDF ใส่รหัสผ่าน + statement ภาษาอังกฤษ)
- 🤖 **จัดหมวดหมู่รายจ่าย** ด้วย keyword matching + Learning Loop (ระบบจำหมวดที่ผู้ใช้แก้)
- 📊 **วิเคราะห์พฤติกรรมการใช้เงิน** + แสดงเทรนด์
- 💬 **LINE Bot** ให้ใช้งานผ่านแชทได้สะดวก
- 🔐 **LINE Login OAuth** เชื่อมบัญชี 1 คลิกแบบปลอดภัย (ระบบเดียวกับ Login with Google)
- 📱 **Responsive + PWA** ใช้ได้ทั้ง Mobile / Tablet / Desktop + ติดตั้งเป็นแอปบนมือถือได้
- 🌗 **สลับธีมสว่าง/มืด** + จำค่าข้ามอุปกรณ์
- 🛡️ **PDPA-compliant** — ลบบัญชี + ระยะผ่อนผัน 30 วัน + Export ข้อมูลตัวเองเป็น CSV

---

## 🚀 Sprint 5 Updates (Prototype v2)

> ปรับ Prototype v1 → Prototype v2 ตาม feedback จาก Sprint 4 + เพิ่ม 6 features หลัก

### Highlights
1. **หน้า Settings 4 หมวด** — โปรไฟล์ / การแสดงผล / LINE / แจ้งเตือน (รวมศูนย์การตั้งค่า)
2. **PDPA Compliance** — ลบบัญชีแบบมีระยะผ่อนผัน 30 วัน + ยกเลิกการลบได้ + Export ข้อมูลเป็น CSV
3. **Brand v2 + PWA** — โลโก้ block M ครีม/ทอง + ติดตั้งเป็นแอปบนมือถือได้ (Android Chrome + iOS Safari)
4. **Light/Dark Theme** — สลับธีมได้ + จำค่าในฐานข้อมูล (เปิดเครื่องอื่นธีมเหมือนเดิม)
5. **LINE Login OAuth** — เชื่อมบัญชี 1 คลิก verify ตัวตนผ่าน LINE จริง (คงคำสั่ง `เชื่อม email` เป็น fallback)
6. **Mobile UX fixes** — แก้บั๊กปุ่มหมวด, ปุ่ม save ถูกทับ, แท็บ Settings

### Sprint 5 Documentation
- 📋 [CP7 Full Report](docs/cp7-report.md) — รายงานเต็ม 8 sections
- 🎯 [Feedback-to-Fix Mapping](docs/feedback-to-fix.md) — feedback → fix
- 🔨 [Build Log](docs/sprint5-build-log.md) — สิ่งที่ build เสร็จ + Evidence
- 🔄 [Before/After](docs/before-after.md) — Prototype v1 vs v2
- 🎬 [Final Demo Evidence](docs/final-demo.md) — Live URL + Core Flow + PWA install
- ⚠️ [Known Issues](docs/known-issues.md) — โปร่งใส demo-grade vs production-grade
- 👥 [Individual Contribution](docs/evidence-log-sprint5.md) — ใครทำอะไร

---

## ✨ Features

### 🌐 Web Application

| Feature | Description |
|---------|-------------|
| 📊 **Dashboard** | KPI cards, sparkline 30 วัน, donut chart, recent transactions |
| 💳 **Transactions** | ค้นหา/กรอง/จัดเรียงธุรกรรมทั้งหมด + แก้หมวดได้ (Learning Loop) |
| 📤 **Upload Statement** | ลากไฟล์ PDF → parse + auto-categorize (รองรับ PDF ใส่รหัสผ่าน) |
| 🔍 **AI Insights** | คะแนนการเงิน + Insight cards จากข้อมูลจริง |
| 💬 **Chat with Mind** | ถามเรื่องการเงินกับ AI assistant |
| 🔔 **Notifications** | ประวัติการแจ้งเตือนทั้งหมด + Budget alert push ผ่าน LINE |
| ⚙️ **Settings (4 tabs)** | โปรไฟล์ / การแสดงผล / LINE link / แจ้งเตือน (Sprint 5) |
| 🗑️ **Delete Account** | ลบบัญชี + 30-day grace + Export CSV (PDPA, Sprint 5) |
| 🌗 **Theme Toggle** | สลับธีมสว่าง/มืด + จำค่าในฐานข้อมูล (Sprint 5) |
| 📱 **PWA Install** | ติดตั้งเป็นแอปบนมือถือได้ (Sprint 5) |

### 🤖 LINE Bot

| Command | What it does |
|---------|-------------|
| `วิธีใช้` / `start` | คู่มือเริ่มต้น 3 ขั้นตอน |
| `สรุป` | สรุปรายรับ/รายจ่ายเดือนนี้ |
| `ยอด` | ยอดรวมรายรับและรายจ่าย |
| `เดือนนี้` | แยกหมวดหมู่รายจ่าย |
| `วิเคราะห์` | Top 3 หมวด + คำแนะนำประหยัด |
| `ช่วย` | รายการคำสั่งทั้งหมด |
| `เชื่อม <email>` | เชื่อม LINE กับบัญชีเว็บ (fallback — แนะนำใช้ LINE Login OAuth บนเว็บ) |
| 📎 ส่งไฟล์ PDF | อัปโหลด Statement อัตโนมัติ (รองรับ PDF ใส่รหัสผ่าน — bot ถามรหัสในแชท) |

### 🏦 Supported Banks

- ✅ **กสิกรไทย** (K PLUS)
- ✅ **ไทยพาณิชย์** (SCB Easy)
- ✅ **กรุงไทย** (Krungthai NEXT)
- ✅ **ออมสิน** (MyMo)

---

## 🛠️ Tech Stack

### Backend
- **Framework**: Flask 3.0
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL 18 (Production) / SQLite (Local)
- **PDF Parser**: pdfplumber
- **LINE SDK**: line-bot-sdk v3
- **WSGI Server**: Gunicorn

### Frontend
- **UI Library**: React 18 (via Babel CDN — no build step)
- **Styling**: Custom CSS (Dark Luxe aesthetic)
- **State**: React Hooks (useState / useEffect / useMemo)
- **Responsive**: 4 breakpoints (Mobile / Tablet / Desktop / Tiny)

### Infrastructure
- **Hosting**: Render (Free tier)
- **Region**: Singapore (Southeast Asia)
- **Database**: Render Free Postgres
- **CI/CD**: GitHub auto-deploy on push
- **HTTPS**: Auto-provisioned by Render

---

## 🏗️ Architecture

```
┌─────────────────┐       ┌─────────────────┐       ┌──────────────┐
│   Mobile / PC   │       │   LINE App      │       │  Bank PDF    │
│    Browser      │       │   (Chatbot)     │       │  Statement   │
└────────┬────────┘       └────────┬────────┘       └──────┬───────┘
         │                         │                       │
         │ HTTPS                   │ Webhook               │ Upload
         ▼                         ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Flask Backend (Render)                          │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────────┐   │
│  │  REST API    │  │  LINE Bot   │  │   PDF Parser         │   │
│  │  16 routes   │  │   Handler   │  │ (pdfplumber)         │   │
│  └──────┬───────┘  └──────┬──────┘  └──────────┬───────────┘   │
│         │                 │                     │                │
│         └─────────────────┴─────────────────────┘                │
│                           │                                      │
│                  ┌────────▼────────┐                            │
│                  │   SQLAlchemy    │                            │
│                  │      ORM        │                            │
│                  └────────┬────────┘                            │
└───────────────────────────┼──────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   PostgreSQL Database   │
              │  (Render Free Tier)     │
              │                         │
              │  • users                │
              │  • transactions         │
              │  • imports              │
              │  • notifications        │
              │  • preferences          │
              │  • line_users           │
              └─────────────────────────┘
```

---

## 📁 Project Structure

```
MoneyMind/
├── backend/                  # Flask backend (Python)
│   ├── app.py               # Routes + Flask app
│   ├── db.py                # SQLAlchemy engine (SQLite/Postgres switch)
│   ├── models.py            # 6 ORM models
│   └── line_bot.py          # LINE webhook handler + commands
│
├── frontend/                 # React frontend
│   ├── index.html           # Entry point + Babel
│   └── src/
│       ├── app.jsx          # App shell + routing
│       ├── auth.jsx         # Login / Register
│       ├── views.jsx        # Dashboard / Transactions / Upload / Insights
│       └── data.js          # i18n strings + helpers
│
├── logic_ai/                 # PDF parsing + categorization
│   └── pdf_parser.py        # Parsers for 4 banks
│
├── ux_ui/                    # Design system
│   ├── styles.css           # Dark luxe theme + responsive
│   └── src/
│       ├── ui.jsx           # Icons, KPI, charts
│       └── tweaks-panel.jsx # Theme controls
│
├── samples/                  # Sample data
│   └── sample-statement.csv
│
├── .env.example             # Environment template
├── .gitignore               # (.env, data/, *.pdf, secrets)
├── requirements.txt         # Python dependencies
├── render.yaml              # Render deploy config
└── Procfile                 # Gunicorn start command
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Git
- LINE Developer account (optional, for bot)

### 1. Clone
```bash
git clone https://github.com/wataroz/-Team-04-sprint3.git
cd -Team-04-sprint3
git checkout feature/flask-react
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env and fill in your LINE tokens (optional)
```

### 4. Run
```bash
python backend/app.py
```

Open http://localhost:5000

### 5. Test
- Login with any email (auto-creates account)
- Upload a bank PDF statement
- View Dashboard, Insights, Transactions

---

## 🌐 Deployment (Render)

1. **Fork this repo** to your GitHub
2. **Create Render account** at https://render.com
3. **New Web Service** → connect your fork → branch `feature/flask-react`
4. **Settings**:
   - **Language**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn backend.app:app --bind 0.0.0.0:$PORT`
5. **Environment Variables**:
   - `LINE_CHANNEL_SECRET` — from LINE Developers Console (Messaging API)
   - `LINE_CHANNEL_ACCESS_TOKEN` — from LINE Developers Console (Messaging API)
   - `LINE_LOGIN_CHANNEL_ID` — from LINE Developers Console (LINE Login, Sprint 5)
   - `LINE_LOGIN_CHANNEL_SECRET` — from LINE Developers Console (LINE Login, Sprint 5)
   - `LINE_LOGIN_CALLBACK_URL` — `https://your-app.onrender.com/api/line/oauth/callback`
   - `FLASK_SECRET_KEY` — random ≥32 chars (gen ด้วย `python -c "import secrets; print(secrets.token_urlsafe(48))"`)
   - `DATABASE_URL` — from Render Postgres (Internal URL)
   - `GEMINI_API_KEY` — (optional) for AI insights
   - `ANTHROPIC_API_KEY` — (optional) AI fallback
   - `PYTHON_VERSION` — `3.11`
6. **Create Web Service** → wait ~3 minutes for deploy
7. **Set LINE Webhook URL**: `https://your-app.onrender.com/webhook/line`

---

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve React app (SPA) |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/auth/login` | Login / register (upsert by email) + trigger lazy cleanup |
| `GET/PATCH/DELETE` | `/api/users/<id>` | Profile / update name+display_name / schedule 30-day delete |
| `POST` | `/api/users/<id>/cancel-delete` | Abort scheduled hard-delete |
| `GET` | `/api/users/<id>/export-csv` | PDPA data portability |
| `GET` | `/api/line/status` | LINE link status |
| `POST` | `/api/line/unlink` | LINE unlink |
| `GET` | `/api/line/oauth/url` | LINE Login OAuth URL (Sprint 5) |
| `GET` | `/api/line/oauth/callback` | LINE Login OAuth callback (Sprint 5) |
| `GET/POST` | `/api/transactions` | List / bulk insert + Learning Loop |
| `PATCH` | `/api/transactions/<id>` | Edit category + save override |
| `GET/POST/DELETE` | `/api/imports[/<id>]` | History / create / undo last |
| `POST` | `/api/parse-pdf` | Parse bank statement PDF (รองรับ encrypted + password) |
| `GET/POST` | `/api/notifications` | List notifications + mark-read |
| `GET/PUT` | `/api/preferences/<id>` | Get/update preferences (+ theme light/dark) |
| `POST` | `/api/reset` | Wipe txs/imports/notifs (keep budget/account/LINE) |
| `POST` | `/api/ai/complete` | AI provider chain |
| `POST` | `/webhook/line` | LINE Messaging API webhook |
| `POST` | `/api/admin/run-grace-cleanup` | Token-gated, default-closed (Sprint 5) |

---

## 🎨 Design Highlights

- **Dark Luxe Aesthetic**: Logo gold accent (#D4B978) on deep black canvas
- **Serif Typography**: Instrument Serif สำหรับ headlines
- **Fluid Scaling**: ใช้ `clamp()` ทำให้ font scale ตามขนาดหน้าจอ
- **Bottom Nav on Mobile**: Sidebar กลายเป็น bottom nav อัตโนมัติบนมือถือ
- **Safe Area Insets**: รองรับ iPhone notch + home indicator
- **Smooth Transitions**: cubic-bezier easing สำหรับ panel animations
- **Reduced Motion**: เคารพ `prefers-reduced-motion` ของผู้ใช้

---

## 🔒 Security

- ✅ `.env` ไม่เคย commit ขึ้น Git (ป้องกันด้วย `.gitignore`)
- ✅ LINE webhook ตรวจ signature ทุก request
- ✅ HTTPS-only (auto-provisioned by Render)
- ✅ Password input ใช้ `type="password"` (browser auto-mask)
- ✅ SQL injection ป้องกันโดย SQLAlchemy ORM (parameterized queries)
- ✅ CORS handled by Flask
- ✅ Database connection ใช้ Internal URL (ไม่ผ่าน public internet)
- ✅ **LINE Login OAuth** state JWT (10-min TTL + purpose claim) → กัน CSRF
- ✅ **LINE Login id_token verify** (HS256 + channel secret) → ยืนยันตัวตนจาก LINE
- ✅ **Theme injection guard** — whitelist `'light'/'dark'` strict (กัน CSS injection ผ่าน data-theme)
- ✅ **PII protection** — pre-push REW review + secret scan
- ✅ **Encrypted PDF buffer** — TTL 5 นาที + max 3 attempts (กัน brute force)

ดูเพิ่มเติม: [docs/known-issues.md](docs/known-issues.md) — Demo-grade vs Production-grade transparency

---

## 📜 License

Educational project — สำหรับการศึกษา (Sprint 3, Team 04)

---

## 👥 Team 04 — Sprint 3/5

- **WA** ([@wataroz](https://github.com/wataroz)) — Backend + Parser EN/SCB + LINE Login OAuth + Deploy
- **BEST** — UX/UI + Mobile responsive + Brand v2 + Dual-theme + Stacking context fix
- **ACHI** — Frontend + Settings 4 tabs + Theme picker + Cancel Delete banner
- **AJ** — Backend + PDPA (Hard delete + Grace + Export CSV) + Lazy cleanup + Display name
- **REW** — Pre-push review + Secret/PII guard + Theme injection guard
- **NOTE** — Notion sync + Sprint summary

ดูเพิ่ม: [Individual Contribution log](docs/evidence-log-sprint5.md)

---

<div align="center">

Made with ☕ and 💛 in Thailand

</div>

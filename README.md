
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

- 📄 **อ่าน Statement PDF** จากธนาคารไทย 4 แห่งโดยอัตโนมัติ
- 🤖 **จัดหมวดหมู่รายจ่าย** ด้วย keyword matching
- 📊 **วิเคราะห์พฤติกรรมการใช้เงิน** + แสดงเทรนด์
- 💬 **LINE Bot** ให้ใช้งานผ่านแชทได้สะดวก
- 📱 **Responsive** ใช้ได้ทั้ง Mobile / Tablet / Desktop

---

## ✨ Features

### 🌐 Web Application

| Feature | Description |
|---------|-------------|
| 📊 **Dashboard** | KPI cards, sparkline 30 วัน, donut chart, recent transactions |
| 💳 **Transactions** | ค้นหา/กรอง/จัดเรียงธุรกรรมทั้งหมด |
| 📤 **Upload Statement** | ลากไฟล์ PDF → parse + auto-categorize |
| 🔍 **AI Insights** | คะแนนการเงิน + Insight cards จากข้อมูลจริง |
| 💬 **Chat with Mind** | ถามเรื่องการเงินกับ AI assistant |
| 🔔 **Notifications** | ประวัติการแจ้งเตือนทั้งหมด |
| 🎨 **Tweaks Panel** | ปรับสี/ภาษา/สกุลเงิน/density ตามใจ |

### 🤖 LINE Bot

| Command | What it does |
|---------|-------------|
| `วิธีใช้` / `start` | คู่มือเริ่มต้น 3 ขั้นตอน |
| `สรุป` | สรุปรายรับ/รายจ่ายเดือนนี้ |
| `ยอด` | ยอดรวมรายรับและรายจ่าย |
| `เดือนนี้` | แยกหมวดหมู่รายจ่าย |
| `วิเคราะห์` | Top 3 หมวด + คำแนะนำประหยัด |
| `ช่วย` | รายการคำสั่งทั้งหมด |
| 📎 ส่งไฟล์ PDF | อัปโหลด Statement อัตโนมัติ |

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
   - `LINE_CHANNEL_SECRET` — from LINE Developers Console
   - `LINE_CHANNEL_ACCESS_TOKEN` — from LINE Developers Console
   - `DATABASE_URL` — from Render Postgres (Internal URL)
   - `PYTHON_VERSION` — `3.11`
6. **Create Web Service** → wait ~3 minutes for deploy
7. **Set LINE Webhook URL**: `https://your-app.onrender.com/webhook/line`

---

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve React app (SPA) |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/auth/login` | Login / register (upsert by email) |
| `GET` | `/api/transactions` | List user transactions |
| `POST` | `/api/transactions` | Bulk insert transactions |
| `POST` | `/api/imports` | Create import record |
| `GET` | `/api/imports` | List user imports |
| `POST` | `/api/parse-pdf` | Parse bank statement PDF |
| `GET` | `/api/notifications` | List notifications |
| `POST` | `/api/notifications` | Create notification |
| `POST` | `/api/notifications/mark-read` | Mark all as read |
| `GET` | `/api/preferences/<id>` | Get user preferences |
| `PUT` | `/api/preferences/<id>` | Update preferences |
| `POST` | `/webhook/line` | LINE Messaging API webhook |

---

## 🎨 Design Highlights

- **Dark Luxe Aesthetic**: Champagne accent (#C9B68A) on deep black canvas
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

---

## 📜 License

Educational project — สำหรับการศึกษา (Sprint 3, Team 04)

---

## 👥 Author

- **WA** ([@wataroz](https://github.com/wataroz)) — Backend + Frontend + LINE bot integration + Deploy

---

<div align="center">

Made with ☕ and 💛 in Thailand

</div>

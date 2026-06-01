# Team-04-sprint3
## Role:
1.Peerawas Kajuntug 67050161 (Backend)\
2.Chitsanupong Pealookin 67050335 (Frontend)\
3.Techit Aungkachot 67050554 (UX/UI)\
4.Peerapat Chotmanee 67050568 (Logic-ai)

## Core Flow Statement:
**Peerawas**: ผมรับผิดชอบการพัฒนาและดูแลระบบ Backend ของโปรเจค MoneyMind โดยออกแบบโครงสร้างฐานข้อมูลและสร้าง REST API สำหรับจัดเก็บข้อมูลผู้ใช้ ข้อมูลรายรับ-รายจ่าย และข้อมูลที่จำเป็นต่อการวิเคราะห์ทางการเงิน รวมถึงทำหน้าที่ Back up Data เพื่อความปลอดภัยของข้อมูล โดยส่งมอบ API Endpoint ในรูปแบบ File.json ให้กับฝั่ง Frontend (Chitsanupong) เพื่อนำไปเชื่อมต่อกับ UI และส่งข้อมูลให้ทีม Logic-AI (Peerapat) นำไปประมวลผลต่อ

**Chitsanupong**: ผมรับผิดชอบการพัฒนาส่วนติดต่อผู้ใช้ (UI) ของแอปพลิเคชัน MoneyMind โดยนำดีไซน์และ Prototype จากทีม UX/UI (Techit) มาเขียนเป็นโค้ดที่ใช้งานได้จริง พร้อมเชื่อมต่อกับ API จากฝั่ง Backend (Peerawas) เพื่อแสดงผลข้อมูลให้ผู้ใช้เห็น และเชื่อมโยงผลลัพธ์จาก AI (Peerapat) มาแสดงผลในหน้าจอ โดยส่งมอบหลักฐานเป็น Screenshot UI ของหน้าจอที่พัฒนาเสร็จในแต่ละ Sprint

**Techit**: ผมรับผิดชอบการออกแบบประสบการณ์ผู้ใช้ (UX) และหน้าตาแอปพลิเคชัน (UI) ของ MoneyMind โดยศึกษาความต้องการของผู้ใช้ ออกแบบ User Flow, Wireframe และ Prototype ใน Figma เพื่อให้ทีม Frontend (Chitsanupong) นำไปพัฒนาต่อ พร้อมทั้งจัดทำ Presentation เพื่อนำเสนอแนวคิดและดีไซน์ของโปรเจคให้ทีมและผู้เกี่ยวข้อง โดยส่งมอบ Screenshot Prototype เป็นหลักฐานในแต่ละ Sprint\

**Peerapat**: รับผิดชอบการพัฒนาส่วน AI และ Logic ของระบบ MoneyMind โดยออกแบบและพัฒนาโมเดล AI สำหรับวิเคราะห์พฤติกรรมการใช้จ่าย จัดหมวดหมู่รายการการเงิน และสร้างคำแนะนำทางการเงินให้กับผู้ใช้ โดยรับข้อมูลจากฝั่ง Backend นำมาประมวลผลด้วยอัลกอริทึม AI และส่งผลลัพธ์กลับไปแสดงผลที่ฝั่ง Frontend เพื่อให้ผู้ใช้ได้รับข้อมูลเชิงลึกที่เป็นประโยชน์

## Sprint 3 Contribution Plan

| Name | Role | Module/Task | Evidence |  Evidance location File|
|---|---|---|---|---|
| Peerawas| Backend | Back up Data | File.json(API) | branches:feature/flask-react/backend |  
| Chitsanupong | Frontend | UI | Screenshot UI | branches:feature/flask-react/frontend |
| Techit | UX/UI | Presentation | Screenshot Prototype | branches:feature/flask-react/ux_ui |  
| Peerapat | Logic-ai | Ai Dev | Notebook (.ipynb) + Model Result | branches:feature/flask-react/logic_ai |

## Day 2 Evidence Log

| Name | Role | What I did today | Evidence Link/File | Status |
|---|---|---|---|---|
| Peerawas | Backend | Setup repo | READ.md | Done:Setup repo / Doing:database schema / Blocked:- |
| Chisanupong | Frontend | Create react spa serve | branches:feature/flask-react/frontend/src/app.jsx, views.jsx, data.js, auth.jsx | Done:react spa serve / Doing:Dashboard Chart.js screenshot final + data flow test / Blocked:- |
| Techit | UX/UI | จัดทำ Figma prototype link (หรือ HTML prototype ที่ใช้งานได้), screenshot ทุก flow, เตรียม demo script เบื้องต้น | ux_ui/src/ui.jsx, styles.css, tweaks-panel.jsx + design_pkg/moneymind/project/MoneyMind Prototype.html | Done: ออกแบบ UI component (ui.jsx, styles.css, tweaks-panel.jsx) + สร้าง clickable prototype HTML พร้อม flow หลัก |  
| Peerapat | Logic-ai |  Implement parse_statement() + detect_bank() for KBank PDF  | branches:feature/flask-react/logic_ai/pdf_parser.py | | Done: KBank parser / Doing: GSB parser / Blocked:- |

## Day 3 Evidence Log

| Name | Role | What I did today | Evidence Link/File | Status |
|---|---|---|---|---|
| Peerawas | Backend | database schema | branches:feature/flask-react/backend/db.py | Done:database schema / Doing:database schema / Blocked:- |
| Chisanupong | Frontend | เชื่อมต่อ React Dashboard กับ Flask API และทดสอบการแสดงผลข้อมูลผ่าน Chart.js | Screenshot Dashboard และ GitHub commit บน branch feature/flask-react | Done:Form → API → Database → Dashboard ทำงานได้ / Doing:เก็บ Screenshot การ Integration และปรับ UI สำหรับ Demo / Blocked:- |
| Techit | UX/UI | Presentation | Screenshot Prototype | branches:feature/flask-react/ux_ui |
| Peerapat | Logic-ai | Add GSB, KTB, SCB bank parsers + categorize() with 8 categories (regex keyword matching) | branches:feature/flask-react/logic_ai/pdf_parser.py | Done: 4-bank parsers / Doing: category accuracy test / Blocked:- |

## Day 4 Evidence Log

| Name | Role | What I did today | Evidence Link/File | Status |
|---|---|---|---|---|
| Peerawas | Backend | bot line | branches:feature/flask-react/backend/line_bot.py | Done:line_bot.py / Doing:- / Blocked:- |
| Chisanupong | Frontend | ทดสอบระบบ Frontend แบบ End-to-End | Demo Website, Screenshot UI และ GitHub Repository | Done:Dashboard และ Frontend พร้อมสำหรับ Demo / Doing:- / Blocked:- |
|  |  |  |  |  |
| Peerapat | Logic-ai | Test PDF parsing with sample statements, record results in Notebook (.ipynb) + integrate with /api/parse-pdf endpoint | branches:feature/flask-react/logic_ai/ Notebook (.ipynb) + Model Result | Done: parser integration / Doing: edge case fix / Blocked:-  |

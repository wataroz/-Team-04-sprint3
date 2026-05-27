/* ============================================================
   MoneyMind — Sample data, categories, and i18n
   Plain JS attached to window so JSX files can read it.
   ============================================================ */

// Category palette (kept restrained — neutrals + small accents)
const CATEGORIES = {
  food:      { th: 'อาหารและเครื่องดื่ม', en: 'Food & Drink',   icon: '🍜', color: '#D88A8A' },
  transport: { th: 'เดินทาง',              en: 'Transport',     icon: '🚕', color: '#8AB4D8' },
  shopping:  { th: 'ช้อปปิ้ง',             en: 'Shopping',       icon: '🛍', color: '#C9B68A' },
  home:      { th: 'ค่าใช้จ่ายบ้าน',        en: 'Home & Bills',  icon: '🏠', color: '#B6A4D8' },
  entertain: { th: 'บันเทิง',              en: 'Entertainment', icon: '🎬', color: '#E5A55C' },
  groceries: { th: 'ของใช้ในบ้าน',         en: 'Groceries',     icon: '🛒', color: '#7BB7A4' },
  health:    { th: 'สุขภาพ',               en: 'Health',        icon: '💊', color: '#D88AB4' },
  income:    { th: 'รายรับ',               en: 'Income',        icon: '💼', color: '#88D4A4' },
  other:     { th: 'อื่นๆ',                en: 'Other',         icon: '✦', color: '#8A8A92' },
};

// 30-day daily expense series for the sparkline (synthetic but realistic)
const DAILY_SERIES = [
  220, 380, 145, 0, 612, 295, 410,
  185, 0, 540, 320, 275, 180, 760,
  220, 410, 0, 380, 245, 580, 195,
  120, 0, 720, 340, 480, 290, 380,
  225, 195,
];

// 90-day series (weekly aggregated — 13 points)
const SERIES_90D = [
  6420, 5980, 7250, 8120, 6840, 9320, 7480,
  6920, 8540, 7180, 8920, 9640, 7820,
];

// 12-month series
const SERIES_1Y = [
  28400, 31200, 29800, 32500, 35200, 33400,
  30800, 34100, 36800, 33900, 31600, 32619,
];

// Sample transactions — realistic Thai merchants
function makeTx(date, merchant, amount, category, note) {
  return { date, merchant, amount, category, note: note || '' };
}

const SAMPLE_TX = [
  makeTx('2026-05-15', 'Starbucks Siam Paragon', -185, 'food', 'Iced latte'),
  makeTx('2026-05-15', 'Grab to Asoke', -142, 'transport'),
  makeTx('2026-05-15', 'Tops Daily', -428, 'groceries'),
  makeTx('2026-05-14', '7-Eleven Sukhumvit', -89, 'food'),
  makeTx('2026-05-14', 'Netflix Subscription', -419, 'entertain'),
  makeTx('2026-05-14', 'Shopee Mall', -1290, 'shopping', 'Nike Air Max'),
  makeTx('2026-05-13', 'Salary - บริษัท แสงไทย', 52000, 'income'),
  makeTx('2026-05-13', 'BTS Skytrain', -52, 'transport'),
  makeTx('2026-05-12', 'CentralWorld Food Court', -245, 'food'),
  makeTx('2026-05-12', 'PEA - ค่าไฟฟ้า', -1850, 'home', 'May electric bill'),
  makeTx('2026-05-11', 'Lotus Go Fresh', -612, 'groceries'),
  makeTx('2026-05-11', 'AIS Postpaid', -799, 'home'),
  makeTx('2026-05-10', 'Bolt Food', -178, 'food'),
  makeTx('2026-05-10', 'Watsons', -340, 'health'),
  makeTx('2026-05-09', 'After You Dessert Cafe', -295, 'food'),
  makeTx('2026-05-09', 'Major Cineplex', -380, 'entertain'),
  makeTx('2026-05-08', 'Grab to Airport', -485, 'transport'),
  makeTx('2026-05-08', 'Boots Pharmacy', -220, 'health'),
  makeTx('2026-05-07', 'McDonald\'s Drive-Thru', -159, 'food'),
  makeTx('2026-05-07', 'Lazada', -890, 'shopping'),
  makeTx('2026-05-06', 'Cafe Amazon', -75, 'food'),
  makeTx('2026-05-06', 'Big C Extra', -1140, 'groceries'),
  makeTx('2026-05-05', 'Spotify Premium', -149, 'entertain'),
  makeTx('2026-05-05', 'MRT Top-up', -300, 'transport'),
  makeTx('2026-05-04', 'Sushi Hiro', -890, 'food', 'Date night'),
  makeTx('2026-05-04', 'Shell V-Power', -1200, 'transport'),
  makeTx('2026-05-03', 'IKEA Bangkok', -2480, 'home', 'Desk lamp + storage'),
  makeTx('2026-05-02', 'Freelance Project', 8500, 'income', 'Logo design'),
  makeTx('2026-05-02', 'CP Fresh Mart', -385, 'groceries'),
  makeTx('2026-05-01', 'Apartment Rent', -12000, 'home', 'May rent'),
  makeTx('2026-05-01', 'Tesco Lotus', -720, 'groceries'),
];

// AI Insights (pre-generated for demo)
const SAMPLE_INSIGHTS = {
  score: 72,
  rating: { th: 'อยู่ในเกณฑ์ดี', en: 'In good shape' },
  summary: {
    th: 'เดือนนี้คุณยังจัดการการเงินได้ค่อนข้างดี แต่ค่าอาหารกับช้อปปิ้งเริ่มสูงกว่าค่าเฉลี่ย AI แนะนำให้ตั้งงบหมวดอาหารแยกไว้',
    en: 'You\'re managing well this month — but Food and Shopping are creeping above your average. AI suggests setting a separate Food budget.',
  },
  items: [
    {
      tag: 'warn',
      tagLabel: { th: 'ใช้เยอะ', en: 'High spend' },
      title:   { th: 'ค่าอาหาร เพิ่มขึ้น 23%', en: 'Food spend up 23%' },
      body:    {
        th: 'เดือนนี้ใช้ไปกับร้านกาแฟกับ delivery มากกว่าค่าเฉลี่ย 3 เดือนก่อนถึง 23% โดยเฉพาะ Starbucks 12 ครั้ง',
        en: 'You spent 23% more on coffee and delivery vs. your 3-month average. 12 Starbucks visits stand out.',
      },
      stat: { th: '฿4,820 / 31 ครั้ง', en: '฿4,820 / 31 visits' },
    },
    {
      tag: 'good',
      tagLabel: { th: 'พฤติกรรมดี', en: 'Healthy habit' },
      title:   { th: 'เก็บออมสม่ำเสมอ', en: 'Steady savings rate' },
      body:    {
        th: 'อัตราการออมเฉลี่ย 18% ของรายรับ สูงกว่าเกณฑ์มาตรฐาน (10%) ถ้าทำได้แบบนี้ทั้งปี เก็บได้ราว 109,000 บาท',
        en: 'Your average savings rate is 18% of income — above the 10% benchmark. Keep this up and you\'ll save ~฿109K this year.',
      },
      stat: { th: '+18% ต่อเดือน', en: '+18% per month' },
    },
    {
      tag: 'info',
      tagLabel: { th: 'ข้อสังเกต', en: 'Observation' },
      title:   { th: 'Subscription รวม ฿1,367/เดือน', en: 'Subscriptions: ฿1,367/mo' },
      body:    {
        th: 'มี subscription ทั้งหมด 6 บริการ — Netflix, Spotify, AIS, iCloud, Apple Music, YouTube Premium บางบริการอาจซ้ำกัน',
        en: 'You have 6 active subscriptions — Netflix, Spotify, AIS, iCloud, Apple Music, YouTube Premium. Some may overlap.',
      },
      stat: { th: '6 บริการ', en: '6 services' },
    },
    {
      tag: 'warn',
      tagLabel: { th: 'เสี่ยง', en: 'At risk' },
      title:   { th: 'ใช้งบช้อปปิ้ง 84%', en: 'Shopping budget at 84%' },
      body:    {
        th: 'เหลือเวลาอีก 16 วันในเดือน แต่ใช้งบ ฿2,180 จาก ฿2,600 แล้ว ลองเลื่อนการซื้อที่ไม่จำเป็นไปก่อน',
        en: 'You have 16 days left but used ฿2,180 of ฿2,600. Consider deferring non-essential purchases.',
      },
      stat: { th: '฿420 เหลือ', en: '฿420 left' },
    },
    {
      tag: 'good',
      tagLabel: { th: 'ดีขึ้น', en: 'Improving' },
      title:   { th: 'ใช้ delivery น้อยลง', en: 'Less delivery use' },
      body:    {
        th: 'จำนวนครั้งสั่ง delivery ลดลงจากเดือนก่อน 4 ครั้ง — กลับมาทำอาหารเองมากขึ้นช่วยประหยัดได้ราว ฿840',
        en: 'Delivery orders down 4 from last month — cooking more saved you about ฿840.',
      },
      stat: { th: '−4 ครั้ง', en: '−4 orders' },
    },
    {
      tag: 'info',
      tagLabel: { th: 'เป้าหมาย', en: 'Goal' },
      title:   { th: 'กองทุนฉุกเฉิน 4.2 เดือน', en: 'Emergency fund: 4.2 mo' },
      body:    {
        th: 'มีเงินสำรองพอใช้ 4.2 เดือนถ้าไม่มีรายได้ ตามเกณฑ์มาตรฐาน 3-6 เดือน คุณอยู่ในจุดที่ปลอดภัย',
        en: 'You have 4.2 months of expenses in reserve. The 3–6 month benchmark says you\'re in a safe zone.',
      },
      stat: { th: '฿94,500', en: '฿94,500' },
    },
  ],
};

// i18n strings used across the app
const I18N = {
  nav: {
    overview:     { th: 'ภาพรวม',           en: 'Overview' },
    transactions: { th: 'ธุรกรรม',           en: 'Transactions' },
    upload:       { th: 'นำเข้า Statement',   en: 'Import Statement' },
    budgets:      { th: 'ตั้งงบรายหมวด',      en: 'Category Budgets' },
    insights:     { th: 'AI Insights',       en: 'AI Insights' },
  },
  brand_sub:     { th: 'ผู้ช่วยจัดการการเงิน', en: 'Personal Finance Co-pilot' },
  greeting_morn: { th: 'อรุณสวัสดิ์',         en: 'Good morning,' },
  greeting_noon: { th: 'สวัสดีตอนบ่าย',       en: 'Good afternoon,' },
  greeting_eve:  { th: 'สวัสดีตอนเย็น',       en: 'Good evening,' },
  user_name:     { th: 'คุณภวินท์',          en: 'Pawin' },
  user_role:     { th: 'แพลนฟรี',           en: 'Free plan' },
  this_month:    { th: 'เดือนนี้',           en: 'This month' },
  last_30d:      { th: '30 วันล่าสุด',       en: 'Last 30 days' },
  vs_last:       { th: 'เทียบกับเดือนก่อน',    en: 'vs. last month' },
  balance:       { th: 'ยอดคงเหลือสุทธิ',     en: 'Net balance' },
  income:        { th: 'รายรับ',            en: 'Income' },
  expense:       { th: 'รายจ่าย',           en: 'Expense' },
  savings:       { th: 'เก็บออม',           en: 'Saved' },
  budget_used:   { th: 'ใช้งบไป',           en: 'Budget used' },
  budget_left:   { th: 'เหลือ',             en: 'left' },
  search_ph:     { th: 'ค้นหาร้าน หรือหมวด...',  en: 'Search merchant or category…' },
  recent_tx:     { th: 'ธุรกรรมล่าสุด',       en: 'Recent transactions' },
  see_all:       { th: 'ดูทั้งหมด',          en: 'View all' },
  by_category:   { th: 'สัดส่วนตามหมวด',      en: 'By category' },
  spending_trend:{ th: 'แนวโน้มรายจ่าย',      en: 'Spending trend' },
  cta_analyze:   { th: 'วิเคราะห์ด้วย AI',     en: 'Analyze with AI' },
  cta_chat:      { th: 'คุยกับ AI',          en: 'Chat with AI' },
  ai_pill:       { th: 'AI INSIGHT',         en: 'AI INSIGHT' },
  health_score:  { th: 'คะแนนสุขภาพการเงิน',   en: 'Financial Health' },
  out_of:        { th: 'จาก 100',           en: 'out of 100' },
  upload_title:  { th: 'นำเข้า Statement',   en: 'Import Statement' },
  upload_sub:    { th: 'รองรับ CSV และ PDF — ระบบจะแยกธุรกรรมและจัดหมวดให้อัตโนมัติ', en: 'CSV and PDF — we\'ll extract and auto-categorise.' },
  drop_h:        { th: 'ลากไฟล์มาวาง', en: 'Drop your statement here' },
  drop_sub:      { th: 'หรือคลิกเพื่อเลือกไฟล์ (CSV / PDF สูงสุด 10MB)', en: 'or click to browse (CSV / PDF up to 10MB)' },
  parse_step_1:  { th: 'อ่านไฟล์', en: 'Reading file' },
  parse_step_2:  { th: 'แยกคอลัมน์ธุรกรรม', en: 'Parsing transactions' },
  parse_step_3:  { th: 'จัดหมวดอัตโนมัติ', en: 'Auto-categorising' },
  parse_step_4:  { th: 'พร้อมรีวิว', en: 'Ready to review' },
  preview_h:     { th: 'พบ {n} รายการ — ตรวจสอบก่อนเพิ่ม', en: 'Found {n} entries — review before importing' },
  import_btn:    { th: 'นำเข้าทั้งหมด', en: 'Import all' },
  cancel:        { th: 'ยกเลิก', en: 'Cancel' },
  loading_ai:    { th: 'กำลังให้ AI วิเคราะห์การใช้เงินของคุณ...', en: 'Analyzing your spending with AI…' },
  insights_title:{ th: 'AI วิเคราะห์การใช้เงินของคุณ', en: 'AI is analysing your spending' },
  insights_sub:  { th: 'สรุปพฤติกรรมและคำแนะนำจากข้อมูล 30 วันล่าสุด', en: 'Behaviour & recommendations from the last 30 days' },
  ask_anything:  { th: 'ถาม AI เรื่องการเงิน...', en: 'Ask AI about your money…' },
  // Chat suggested prompts
  prompt_1: { th: 'เดือนนี้ใช้เงินกับอะไรเยอะที่สุด?', en: 'What did I spend the most on?' },
  prompt_2: { th: 'แนะนำวิธีลดรายจ่ายให้หน่อย', en: 'How can I cut expenses?' },
  prompt_3: { th: 'ฉันออมพอแล้วหรือยัง?', en: 'Am I saving enough?' },
  prompt_4: { th: 'เปรียบเทียบกับเดือนก่อน', en: 'Compare to last month' },
  // Number-style helpers (no string)
};

// Currency formatter
function fmt(amount, currency, lang) {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';
  if (currency === 'USD') {
    // Approx conversion 1 USD ≈ 35 THB
    const usd = abs / 35;
    return sign + '$' + usd.toLocaleString(lang === 'th' ? 'th-TH' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return sign + '฿' + abs.toLocaleString(lang === 'th' ? 'th-TH' : 'en-US', { maximumFractionDigits: 0 });
}

function fmtParts(amount, currency, lang) {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';
  if (currency === 'USD') {
    const usd = abs / 35;
    return { sign, currency: '$', digits: usd.toLocaleString(lang === 'th' ? 'th-TH' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) };
  }
  return { sign, currency: '฿', digits: abs.toLocaleString(lang === 'th' ? 'th-TH' : 'en-US', { maximumFractionDigits: 0 }) };
}

function t(obj, lang) {
  if (!obj) return '';
  if (typeof obj === 'string') return obj;
  return obj[lang] || obj.en || '';
}

// Sample notifications (mock)
const SAMPLE_NOTIFICATIONS = [
  {
    type: 'warn',
    icon: 'target',
    title:    { th: 'ใช้งบช้อปปิ้งเกือบครบแล้ว', en: 'Shopping budget almost gone' },
    desc:     { th: 'เหลือ ฿420 จากงบ ฿2,600 — ยังเหลือเวลาอีก 16 วัน', en: '฿420 left of ฿2,600 — still 16 days to go' },
    time:     { th: 'เมื่อสักครู่', en: 'just now' },
    unread:   true,
  },
  {
    type: 'info',
    icon: 'sparkles',
    title:    { th: 'AI มี insight ใหม่ 3 ข้อ', en: '3 new AI insights for you' },
    desc:     { th: 'พบรูปแบบการใช้เงินที่น่าสนใจในเดือนนี้ — ดูสรุปได้เลย', en: 'Found interesting patterns this month — view summary' },
    time:     { th: '15 นาทีก่อน', en: '15 min ago' },
    unread:   true,
  },
  {
    type: 'good',
    icon: 'check',
    title:    { th: 'อัตราการออมเดือนนี้ดีเยี่ยม', en: 'Great savings rate this month' },
    desc:     { th: 'ออมไป 18% ของรายรับ สูงกว่าค่าเฉลี่ย 3 เดือนก่อน', en: 'Saved 18% of income — above your 3-month average' },
    time:     { th: '2 ชั่วโมงก่อน', en: '2 hrs ago' },
    unread:   true,
  },
  {
    type: 'warn',
    icon: 'bell',
    title:    { th: 'ค่าอาหารสูงผิดปกติ', en: 'Unusual food spend detected' },
    desc:     { th: 'วันนี้ใช้กับร้านอาหารไป ฿755 (สูงกว่าค่าเฉลี่ย 2.3 เท่า)', en: 'Spent ฿755 on food today — 2.3× your daily average' },
    time:     { th: 'เมื่อวาน', en: 'yesterday' },
    unread:   false,
  },
  {
    type: 'info',
    icon: 'file',
    title:    { th: 'นำเข้า Statement สำเร็จ 31 รายการ', en: 'Imported 31 statement entries' },
    desc:     { th: 'จากไฟล์ kbank-may.csv ระบบจัดหมวดให้แล้ว', en: 'From kbank-may.csv — auto-categorised' },
    time:     { th: '3 วันก่อน', en: '3 days ago' },
    unread:   false,
  },
  {
    type: 'good',
    icon: 'wallet',
    title:    { th: 'ได้รับเงินเดือนแล้ว', en: 'Salary received' },
    desc:     { th: 'รับโอน ฿52,000 จากบริษัท แสงไทย', en: '฿52,000 from Sangthai Co., Ltd.' },
    time:     { th: '13 พ.ค.', en: 'May 13' },
    unread:   false,
  },
];

// Brand glyph SVG (used in sidebar & elsewhere)
const BRAND_GLYPH = `
<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M4 18 L4 8 L8 14 L12 8 L16 14 L20 8 L20 18" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" fill="none"/>
  <circle cx="12" cy="20" r="0.9" fill="currentColor"/>
</svg>
`;

// Expose to window
Object.assign(window, {
  CATEGORIES, DAILY_SERIES, SERIES_90D, SERIES_1Y, SAMPLE_TX, SAMPLE_INSIGHTS, SAMPLE_NOTIFICATIONS,
  I18N, fmt, fmtParts, t, BRAND_GLYPH,
});

/* ============================================================
   MoneyMind — Views
   Dashboard, Transactions, Upload, Insights, ChatPanel
   ============================================================ */

const { useState, useEffect, useMemo, useRef } = React;

// ─────────────────────────────────────────────────────────────
// AI bridge — calls backend /api/ai/complete (Anthropic via Flask).
// Replaces window.claude.complete(), which only exists inside the
// Claude.ai artifact env (undefined on Render production).
// Returns plain text; throws on error so callers' existing
// try/catch fallbacks still apply.
// ─────────────────────────────────────────────────────────────
async function aiComplete(prompt) {
  const res = await fetch('/api/ai/complete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt })
  });
  if (!res.ok) throw new Error('AI request failed: ' + res.status);
  const data = await res.json();
  return data.text || '';
}

// ─────────────────────────────────────────────────────────────
// Derived data — keeps every view in sync with the live tx list
// ─────────────────────────────────────────────────────────────

// Latest tx date in the list, or "today" if empty. Returns Date.
function latestAnchor(txs) {
  if (!txs || txs.length === 0) return new Date();
  const max = txs.reduce((m, t) => t.date > m ? t.date : m, txs[0].date);
  return new Date(max + 'T12:00:00');
}

// Build the 30D / 12W / 12M expense series from the live tx list.
// Falls back to the synthetic series when the user has no expenses
// (so the demo still looks alive on the very first load).
function deriveTrendSeries(txs) {
  const byDay = {};
  for (const tx of txs) {
    if (tx.amount >= 0) continue;
    byDay[tx.date] = (byDay[tx.date] || 0) + -tx.amount;
  }
  const dateKeys = Object.keys(byDay);
  if (dateKeys.length === 0) {
    return { d30: DAILY_SERIES, w12: SERIES_90D, m12: SERIES_1Y, anchor: new Date(), real: false };
  }

  const anchor = latestAnchor(txs);
  const dayKey = (d) => d.toISOString().slice(0, 10);

  // Daily — 30 points ending on anchor
  const d30 = new Array(30).fill(0);
  for (let i = 0; i < 30; i++) {
    const d = new Date(anchor);
    d.setDate(anchor.getDate() - (29 - i));
    d30[i] = byDay[dayKey(d)] || 0;
  }

  // Weekly — 13 points ending on anchor
  const w12 = new Array(13).fill(0);
  for (const date in byDay) {
    const d = new Date(date + 'T12:00:00');
    const diffDays = Math.floor((anchor - d) / 86400000);
    const idx = 12 - Math.floor(diffDays / 7);
    if (idx >= 0 && idx < 13) w12[idx] += byDay[date];
  }

  // Monthly — 12 points ending on anchor
  const m12 = new Array(12).fill(0);
  const anchorMonth = anchor.getFullYear() * 12 + anchor.getMonth();
  for (const date in byDay) {
    const d = new Date(date + 'T12:00:00');
    const mNum = d.getFullYear() * 12 + d.getMonth();
    const idx = 11 - (anchorMonth - mNum);
    if (idx >= 0 && idx < 12) m12[idx] += byDay[date];
  }

  return { d30, w12, m12, anchor, real: true };
}

// Compare current 30-day window vs the prior 30-day window.
function derivePeriodDeltas(txs) {
  if (!txs || txs.length === 0) {
    return { income: 0, expense: 0, balance: 0, savingsRate: 0 };
  }
  const anchor = latestAnchor(txs);
  const dayKey = (d) => d.toISOString().slice(0, 10);
  const startCur = new Date(anchor); startCur.setDate(anchor.getDate() - 29);
  const startPrev = new Date(anchor); startPrev.setDate(anchor.getDate() - 59);
  const endPrev = new Date(anchor); endPrev.setDate(anchor.getDate() - 30);
  const sCur = dayKey(startCur), sPrev = dayKey(startPrev), ePrev = dayKey(endPrev), aKey = dayKey(anchor);

  let curIn = 0, curEx = 0, prevIn = 0, prevEx = 0;
  for (const tx of txs) {
    const inCur = tx.date >= sCur && tx.date <= aKey;
    const inPrev = tx.date >= sPrev && tx.date <= ePrev;
    if (tx.amount > 0) {
      if (inCur) curIn += tx.amount;
      else if (inPrev) prevIn += tx.amount;
    } else {
      const v = -tx.amount;
      if (inCur) curEx += v;
      else if (inPrev) prevEx += v;
    }
  }

  const pct = (a, b) => !b ? (a ? 100 : 0) : (a - b) / b * 100;
  const savingsRate = curIn > 0 ? (curIn - curEx) / curIn * 100 : 0;

  return {
    income: pct(curIn, prevIn),
    expense: pct(curEx, prevEx),
    balance: pct(curIn - curEx, prevIn - prevEx),
    savingsRate: Math.round(savingsRate),
  };
}

// Headline for the AI hero card on the Dashboard — pick the
// category whose share grew the most vs. prior period.
function deriveAITeaser(txs, lang) {
  if (!txs || txs.length === 0) return null;
  const anchor = latestAnchor(txs);
  const dayKey = (d) => d.toISOString().slice(0, 10);
  const startCur = new Date(anchor); startCur.setDate(anchor.getDate() - 29);
  const startPrev = new Date(anchor); startPrev.setDate(anchor.getDate() - 59);
  const endPrev = new Date(anchor); endPrev.setDate(anchor.getDate() - 30);
  const sCur = dayKey(startCur), sPrev = dayKey(startPrev), ePrev = dayKey(endPrev), aKey = dayKey(anchor);

  const cur = {}, prev = {};
  for (const tx of txs) {
    if (tx.amount >= 0) continue;
    const v = -tx.amount;
    const cat = tx.category || 'other';
    if (tx.date >= sCur && tx.date <= aKey) cur[cat] = (cur[cat] || 0) + v;
    else if (tx.date >= sPrev && tx.date <= ePrev) prev[cat] = (prev[cat] || 0) + v;
  }
  // Find category with biggest YoY % increase (min ฿500 to be meaningful)
  let best = null;
  for (const cat in cur) {
    if (cur[cat] < 500) continue;
    const p = prev[cat] || 0;
    const pct = p === 0 ? 100 : (cur[cat] - p) / p * 100;
    if (pct > 10 && (!best || pct > best.pct)) {
      best = { cat, pct: Math.round(pct), amount: cur[cat] };
    }
  }
  if (best) {
    const catObj = CATEGORIES[best.cat] || CATEGORIES.other;
    const catName = t(catObj, lang).toLowerCase();
    return { kind: 'spike', category: best.cat, categoryName: catName, pct: best.pct, amount: best.amount };
  }
  // Otherwise, surface savings rate
  const deltas = derivePeriodDeltas(txs);
  if (deltas.savingsRate > 0) {
    return { kind: 'savings', rate: deltas.savingsRate };
  }
  return null;
}

// Build the Insights page's score + cards from real tx data.
// Used when the user hasn't run the live AI analysis yet.
function deriveInsightCards(txs, lang) {
  if (!txs || txs.length === 0) return null;

  const anchor = latestAnchor(txs);
  const dayKey = (d) => d.toISOString().slice(0, 10);
  const startCur = new Date(anchor); startCur.setDate(anchor.getDate() - 29);
  const startPrev = new Date(anchor); startPrev.setDate(anchor.getDate() - 59);
  const endPrev = new Date(anchor); endPrev.setDate(anchor.getDate() - 30);
  const sCur = dayKey(startCur), sPrev = dayKey(startPrev), ePrev = dayKey(endPrev), aKey = dayKey(anchor);

  let curIn = 0, curEx = 0, prevIn = 0, prevEx = 0;
  const curByCat = {}, prevByCat = {}, curCntByCat = {};
  const merchantCount = {};
  for (const tx of txs) {
    const inCur = tx.date >= sCur && tx.date <= aKey;
    const inPrev = tx.date >= sPrev && tx.date <= ePrev;
    if (tx.amount > 0) {
      if (inCur) curIn += tx.amount;
      else if (inPrev) prevIn += tx.amount;
    } else {
      const v = -tx.amount;
      const cat = tx.category || 'other';
      if (inCur) {
        curEx += v;
        curByCat[cat] = (curByCat[cat] || 0) + v;
        curCntByCat[cat] = (curCntByCat[cat] || 0) + 1;
        const key = (tx.merchant || '').slice(0, 40);
        if (key) merchantCount[key] = (merchantCount[key] || 0) + 1;
      } else if (inPrev) {
        prevEx += v;
        prevByCat[cat] = (prevByCat[cat] || 0) + v;
      }
    }
  }

  const items = [];

  // Card 1 — biggest growing category (warn)
  let growth = null;
  for (const cat in curByCat) {
    if (curByCat[cat] < 300) continue;
    const p = prevByCat[cat] || 0;
    if (p === 0) continue;
    const pct = (curByCat[cat] - p) / p * 100;
    if (pct > 10 && (!growth || pct > growth.pct)) {
      growth = { cat, pct: Math.round(pct), amount: curByCat[cat], count: curCntByCat[cat] };
    }
  }
  if (growth) {
    const catName = t(CATEGORIES[growth.cat] || CATEGORIES.other, lang);
    items.push({
      tag: 'warn',
      tagLabel: lang === 'th' ? 'ใช้เยอะ' : 'High spend',
      title: lang === 'th' ? `${catName} เพิ่มขึ้น ${growth.pct}%` : `${catName} up ${growth.pct}%`,
      body: lang === 'th' ?
        `เดือนนี้ใช้กับ${catName}สูงกว่าค่าเฉลี่ยเดือนก่อน ${growth.pct}% — ลองตั้งงบหมวดนี้แยกไว้ดู` :
        `You're spending ${growth.pct}% more on ${catName.toLowerCase()} vs. last period — consider a dedicated budget.`,
      stat: lang === 'th' ? `${fmt(growth.amount, 'THB', lang)} / ${growth.count} ครั้ง` : `${fmt(growth.amount, 'THB', lang)} / ${growth.count} visits`,
    });
  }

  // Card 2 — savings rate (good or warn)
  const savingsRate = curIn > 0 ? Math.round((curIn - curEx) / curIn * 100) : null;
  if (savingsRate !== null) {
    const good = savingsRate >= 10;
    items.push({
      tag: good ? 'good' : 'warn',
      tagLabel: lang === 'th' ? (good ? 'พฤติกรรมดี' : 'ระวัง') : (good ? 'Healthy habit' : 'Watch out'),
      title: lang === 'th' ? (good ? `อัตราการออม ${savingsRate}%` : `อัตราการออมต่ำ ${savingsRate}%`) : `Savings rate ${savingsRate}%`,
      body: lang === 'th' ?
        (good ?
          `รายรับเข้า ${fmt(curIn, 'THB', lang)} ใช้ไป ${fmt(curEx, 'THB', lang)} เก็บออมได้ ${savingsRate}% — สูงกว่าเกณฑ์มาตรฐาน 10%` :
          `รายจ่ายเริ่มกินรายรับ — เก็บออมได้แค่ ${savingsRate}% ของรายรับ ลองดูหมวดที่ใช้เยอะที่สุดก่อน`) :
        (good ?
          `Income ${fmt(curIn, 'THB', lang)}, spending ${fmt(curEx, 'THB', lang)} → saving ${savingsRate}% — above the 10% benchmark.` :
          `Spending is eating into income — only ${savingsRate}% saved. Start with your biggest category.`),
      stat: lang === 'th' ? `${savingsRate}% ของรายรับ` : `${savingsRate}% of income`,
    });
  }

  // Card 3 — top recurring merchant (info)
  const repeats = Object.entries(merchantCount).filter(([, n]) => n >= 3).sort((a, b) => b[1] - a[1]);
  if (repeats.length > 0) {
    const [name, n] = repeats[0];
    items.push({
      tag: 'info',
      tagLabel: lang === 'th' ? 'ข้อสังเกต' : 'Observation',
      title: lang === 'th' ? `${name} ${n} ครั้งในเดือน` : `${name} · ${n} visits`,
      body: lang === 'th' ?
        `รายการนี้กลับมาบ่อย — ${n} ครั้งใน 30 วัน ลองดูว่ารวมเป็นยอดเท่าไหร่ และจำเป็นจริงไหม` :
        `This merchant shows up ${n} times in 30 days — worth checking the total and whether it's all needed.`,
      stat: lang === 'th' ? `${n} ครั้ง / 30 วัน` : `${n} times / 30d`,
    });
  }

  // Card 4 — top category by share (info)
  const topCats = Object.entries(curByCat).sort((a, b) => b[1] - a[1]);
  if (topCats.length > 0 && curEx > 0) {
    const [cat, v] = topCats[0];
    const share = Math.round(v / curEx * 100);
    const catName = t(CATEGORIES[cat] || CATEGORIES.other, lang);
    items.push({
      tag: 'info',
      tagLabel: lang === 'th' ? 'ภาพรวม' : 'Overview',
      title: lang === 'th' ? `${catName} กินสัดส่วน ${share}%` : `${catName} is ${share}% of spend`,
      body: lang === 'th' ?
        `หมวดที่ใช้มากที่สุดคือ ${catName} — ${fmt(v, 'THB', lang)} จากทั้งหมด ${fmt(curEx, 'THB', lang)}` :
        `Your biggest category is ${catName.toLowerCase()} at ${fmt(v, 'THB', lang)} of ${fmt(curEx, 'THB', lang)}.`,
      stat: lang === 'th' ? `${share}% ของรายจ่าย` : `${share}% of spend`,
    });
  }

  // Score: simple heuristic 50 + savings*1.5, capped 0-95
  let score = 50 + (savingsRate || 0) * 1.5;
  if (curEx > curIn) score -= 15;
  score = Math.max(0, Math.min(95, Math.round(score)));
  const rating = score >= 80 ?
    (lang === 'th' ? 'แข็งแรงมาก' : 'Excellent') :
    score >= 65 ?
    (lang === 'th' ? 'อยู่ในเกณฑ์ดี' : 'In good shape') :
    score >= 45 ?
    (lang === 'th' ? 'พอใช้ได้' : 'Fair') :
    (lang === 'th' ? 'ต้องระวัง' : 'Needs attention');

  return {
    score,
    rating,
    summary: lang === 'th' ?
      `สรุปจากธุรกรรม ${txs.length} รายการ — ${items[0] ? items[0].title : 'ดูรายละเอียดด้านล่าง'}` :
      `Based on ${txs.length} transactions — ${items[0] ? items[0].title : 'see details below'}.`,
    items,
    _derived: true, // mark as auto-derived (not LLM)
  };
}

// ─────────────────────────────────────────────────────────────
// Dashboard
// ─────────────────────────────────────────────────────────────
function Dashboard({ state, setView, openChat }) {
  const { txs, currency, lang, budget } = state;
  const [range, setRange] = useState('30D'); // 30D | 90D | 1Y

  // Calculations
  const totals = useMemo(() => {
    let income = 0,expense = 0;
    const byCat = {};
    for (const t of txs) {
      if (t.amount > 0) income += t.amount;else
      expense += -t.amount;
      const cat = t.category || 'other';
      if (t.amount < 0) byCat[cat] = (byCat[cat] || 0) + -t.amount;
    }
    return { income, expense, balance: income - expense, byCat };
  }, [txs]);

  // ─── Derived series + deltas — all driven by the live tx list ───
  const trend = useMemo(() => deriveTrendSeries(txs), [txs]);
  const deltas = useMemo(() => derivePeriodDeltas(txs), [txs]);
  const teaser = useMemo(() => deriveAITeaser(txs, lang), [txs, lang]);

  const budgetPct = totals.expense / budget * 100;
  const sortedCats = Object.entries(totals.byCat).sort((a, b) => b[1] - a[1]);
  const catTotal = sortedCats.reduce((a, [, v]) => a + v, 0);

  const slices = sortedCats.map(([k, v]) => ({
    label: t(CATEGORIES[k] || CATEGORIES.other, lang),
    value: v,
    color: (CATEGORIES[k] || CATEGORIES.other).color
  }));

  // ─── Labels anchored to the latest tx date ───
  const labels = useMemo(() => {
    const monthsTh = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
    const monthsEn = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const months = lang === 'th' ? monthsTh : monthsEn;
    const a = trend.anchor;

    // 30D — 5 evenly-spaced day labels
    const d30 = [];
    for (let i = 4; i >= 0; i--) {
      const d = new Date(a);
      d.setDate(a.getDate() - i * 7);
      d30.push(lang === 'th' ? `${d.getDate()} ${months[d.getMonth()]}` : `${months[d.getMonth()]} ${d.getDate()}`);
    }
    // 90D — last 4 month names
    const d90 = [];
    for (let i = 3; i >= 0; i--) {
      const d = new Date(a.getFullYear(), a.getMonth() - i, 1);
      d90.push(months[d.getMonth()]);
    }
    // 1Y — quarterly labels
    const d1y = [];
    for (let i = 4; i >= 0; i--) {
      const d = new Date(a.getFullYear(), a.getMonth() - i * 3, 1);
      d1y.push(months[d.getMonth()]);
    }
    return { d30, d90, d1y };
  }, [trend.anchor, lang]);

  const rangeConfig = {
    '30D': {
      series: trend.d30, labels: labels.d30,
      sub: t(I18N.last_30d, lang),
      tooltipLabel: (i) => {
        const d = new Date(trend.anchor); d.setDate(trend.anchor.getDate() - (29 - i));
        return lang === 'th' ? `${d.getDate()}/${d.getMonth() + 1}` : `${d.getMonth() + 1}/${d.getDate()}`;
      }
    },
    '90D': {
      series: trend.w12, labels: labels.d90,
      sub: lang === 'th' ? '90 วันล่าสุด · รายสัปดาห์' : 'Last 90 days · weekly',
      tooltipLabel: (i) => lang === 'th' ? `สัปดาห์ที่ ${i + 1}` : `Week ${i + 1}`
    },
    '1Y': {
      series: trend.m12, labels: labels.d1y,
      sub: lang === 'th' ? '12 เดือนล่าสุด · รายเดือน' : 'Last 12 months · monthly',
      tooltipLabel: (i) => {
        const monthsTh = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
        const monthsEn = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const months = lang === 'th' ? monthsTh : monthsEn;
        const d = new Date(trend.anchor.getFullYear(), trend.anchor.getMonth() - (11 - i), 1);
        return months[d.getMonth()];
      }
    }
  };
  const rc = rangeConfig[range];

  const recent = [...txs].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 6);

  // ─── Empty state ───
  if (txs.length === 0) {
    return (
      <div className="dashboard-empty">
        <div className="dashboard-empty-icon">
          <svg viewBox="0 0 48 48" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" width="56" height="56">
            <rect x="8" y="12" width="32" height="28" rx="4"/>
            <path d="M16 12V9a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v3"/>
            <line x1="24" y1="22" x2="24" y2="32"/>
            <line x1="19" y1="27" x2="29" y2="27"/>
          </svg>
        </div>
        <h2 className="dashboard-empty-title">
          {lang === 'th' ? 'ยังไม่มีข้อมูลธุรกรรม' : 'No transactions yet'}
        </h2>
        <p className="dashboard-empty-sub">
          {lang === 'th' ?
            'นำเข้า Statement จากธนาคารกสิกร, ออมสิน หรือกรุงไทย เพื่อเริ่มวิเคราะห์การเงินของคุณ' :
            'Import a bank statement from K-Bank, GSB, or KTB to start analysing your finances.'}
        </p>
        <button
          className="btn btn-accent"
          onClick={() => setView('upload')}
          style={{ marginTop: 8 }}>
          {Ic.upload}
          {lang === 'th' ? 'นำเข้า Statement' : 'Import Statement'}
        </button>
      </div>
    );
  }

  return (
    <div className="page-enter">
      {/* Hero row: balance + AI teaser */}
      <div className="hero">
        <div className="card hero-balance">
          <div className="balance-label">{t(I18N.balance, lang)}</div>
          <BalanceDisplay amount={totals.balance} currency={currency} lang={lang} />
          <div className="balance-meta">
            <span className={'delta ' + (deltas.balance >= 0 ? 'up' : 'down')}>
              {deltas.balance >= 0 ? Ic.arrUp : Ic.arrDn}{Math.abs(deltas.balance).toFixed(1)}%
            </span>
            <span className="balance-period">{t(I18N.vs_last, lang)} · {t(I18N.this_month, lang)}</span>
          </div>
          <div className="sparkline-wrap">
            <Sparkline series={trend.d30} color="var(--accent)" />
          </div>
        </div>

        <div className="card ai-hero">
          <div className="ai-pill">
            <span className="pulse"></span>
            {t(I18N.ai_pill, lang)}
          </div>
          <h2 className="ai-headline">
            {teaser && teaser.kind === 'spike' ? (
              lang === 'th' ?
                <>เดือนนี้คุณใช้ <em>{teaser.categoryName}</em> สูงกว่าเดือนก่อน <em>{teaser.pct}%</em> — ลองตั้งงบหมวดนี้แยกดู</> :
                <>You spent <em>{teaser.pct}% more</em> on {teaser.categoryName} this month — try a separate budget.</>
            ) : teaser && teaser.kind === 'savings' ? (
              lang === 'th' ?
                <>อัตราการออม <em>{teaser.rate}%</em> ของรายรับ — สูงกว่าค่าเฉลี่ย ทำต่อแบบนี้ดี</> :
                <>You're saving <em>{teaser.rate}%</em> of income — well above average. Keep it up.</>
            ) : (
              lang === 'th' ?
                <>นำเข้า statement แล้วลอง <em>วิเคราะห์</em> ดู AI จะเจอ pattern ที่ซ่อนอยู่</> :
                <>Import a statement and run <em>analysis</em> — AI will surface hidden patterns.</>
            )}
          </h2>
          <div className="ai-footer">
            <span className="ai-meta">{lang === 'th' ? '3 insight ใหม่ · เมื่อสักครู่' : '3 new insights · just now'}</span>
            <button className="btn btn-accent" onClick={() => setView('insights')}>
              {t(I18N.cta_analyze, lang)} {Ic.arrow}
            </button>
          </div>
        </div>
      </div>

      {/* KPI row */}
      <div className="kpi-grid">
        <KPI
          label={t(I18N.income, lang)}
          icon={Ic.arrUp}
          amount={totals.income}
          currency={currency}
          lang={lang}
          delta={deltas.income}
          deltaText={t(I18N.vs_last, lang)} />
        
        <KPI
          label={t(I18N.expense, lang)}
          icon={Ic.arrDn}
          amount={totals.expense}
          currency={currency}
          lang={lang}
          delta={deltas.expense}
          deltaText={t(I18N.vs_last, lang)} />
        
        <KPI
          label={t(I18N.budget_used, lang)}
          icon={Ic.target}
          amount={totals.expense}
          currency={currency}
          lang={lang}
          deltaText={`${Math.round(budgetPct)}% · ${fmt(budget - totals.expense, currency, lang)} ${t(I18N.budget_left, lang)}`}
          barPct={budgetPct}
          over={budgetPct > 90} />
        
        <KPI
          label={t(I18N.savings, lang)}
          icon={Ic.wallet}
          amount={Math.max(0, totals.balance)}
          currency={currency}
          lang={lang}
          delta={deltas.balance}
          deltaText={lang === 'th' ? `อัตราการออม ${deltas.savingsRate}%` : `Savings rate ${deltas.savingsRate}%`} />
        
      </div>

      {/* Trend + category grid */}
      <div className="dash-grid">
        <div className="card">
          <div className="card-title">
            <h3>{t(I18N.spending_trend, lang)} · {rc.sub}</h3>
            <div className="chart-tabs">
              {['30D', '90D', '1Y'].map((r) =>
              <span
                key={r}
                className={'chart-tab' + (range === r ? ' active' : '')}
                onClick={() => setRange(r)}>
                
                  {r}
                </span>
              )}
            </div>
          </div>
          <div className="chart-frame">
            <AreaChart key={range} series={rc.series} labels={rc.labels} tooltipLabel={rc.tooltipLabel} />
          </div>
        </div>

        <div className="card">
          <div className="card-title">
            <h3>{t(I18N.by_category, lang)}</h3>
            <span className="more" onClick={() => setView('transactions')}>{t(I18N.see_all, lang)} {Ic.arrow}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', margin: '4px 0 20px' }}>
            <Donut
              slices={slices}
              totalLabel={t(I18N.expense, lang)}
              totalValue={fmt(totals.expense, currency, lang)} />
            
          </div>
          {sortedCats.slice(0, 4).map(([k, v]) => {
            const cat = CATEGORIES[k] || CATEGORIES.other;
            const pct = v / catTotal * 100;
            return (
              <div key={k} className="cat-row">
                <div className="cat-dot" style={{ background: cat.color }}></div>
                <div>
                  <div className="cat-name">{t(cat, lang)}</div>
                  <div className="cat-sub">{Math.round(pct)}%</div>
                  <div className="cat-bar"><span style={{ width: `${pct}%`, background: cat.color }}></span></div>
                </div>
                <div className="cat-amount">{fmt(v, currency, lang)}</div>
              </div>);

          })}
        </div>
      </div>

      {/* Recent transactions */}
      <div className="card">
        <div className="card-title">
          <h3>{t(I18N.recent_tx, lang)}</h3>
          <span className="more" onClick={() => setView('transactions')}>{t(I18N.see_all, lang)} {Ic.arrow}</span>
        </div>
        <div>
          {recent.map((tx, i) => <TransactionRow key={i} tx={tx} currency={currency} lang={lang} />)}
        </div>
      </div>
    </div>);

}

// ─────────────────────────────────────────────────────────────
// Transactions
// ─────────────────────────────────────────────────────────────
function Transactions({ state, addTxs, editCategory }) {
  const { txs, currency, lang } = state;
  const [search, setSearch] = useState('');
  const [filterCat, setFilterCat] = useState(null);
  const [filterType, setFilterType] = useState('all'); // all | income | expense
  const [sortBy, setSortBy] = useState('date-desc'); // date-desc | date-asc | amount-desc | amount-asc
  const [filterOpen, setFilterOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  // Edit Category — Learning Loop (Day 5). Holds the tx being edited (or null).
  const [editingTx, setEditingTx] = useState(null);
  const filterRef = useRef(null);

  useEffect(() => {
    if (!filterOpen) return;
    const onClick = (e) => {
      if (filterRef.current && !filterRef.current.contains(e.target)) setFilterOpen(false);
    };
    const onKey = (e) => {if (e.key === 'Escape') setFilterOpen(false);};
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [filterOpen]);

  const filtered = useMemo(() => {
    let r = txs.filter((tx) => {
      if (filterCat && tx.category !== filterCat) return false;
      if (filterType === 'income' && tx.amount <= 0) return false;
      if (filterType === 'expense' && tx.amount >= 0) return false;
      if (search) {
        const q = search.toLowerCase();
        const cat = CATEGORIES[tx.category] || CATEGORIES.other;
        return (
          tx.merchant.toLowerCase().includes(q) ||
          (cat.th || '').toLowerCase().includes(q) ||
          (cat.en || '').toLowerCase().includes(q));

      }
      return true;
    });
    // Sort
    if (sortBy === 'date-desc') r = r.sort((a, b) => b.date.localeCompare(a.date));
    if (sortBy === 'date-asc') r = r.sort((a, b) => a.date.localeCompare(b.date));
    if (sortBy === 'amount-desc') r = r.sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount));
    if (sortBy === 'amount-asc') r = r.sort((a, b) => Math.abs(a.amount) - Math.abs(b.amount));
    return r;
  }, [txs, search, filterCat, filterType, sortBy]);

  const activeFilterCount = (filterType !== 'all' ? 1 : 0) + (sortBy !== 'date-desc' ? 1 : 0);

  // Group by date
  const groups = useMemo(() => {
    const g = {};
    for (const tx of filtered) {
      if (!g[tx.date]) g[tx.date] = [];
      g[tx.date].push(tx);
    }
    return Object.entries(g);
  }, [filtered]);

  const catKeys = Object.keys(CATEGORIES).filter((k) => k !== 'other');

  return (
    <div className="page-enter">
      <div className="topbar" style={{ marginBottom: 24 }}>
        <div>
          <div className="crumb">{t(I18N.nav.transactions, lang)}</div>
          <h1 className="greeting">
            {lang === 'th' ? <>รายการธุรกรรม <em style={{ textAlign: "left", fontFamily: "\"IBM Plex Sans Thai\"" }}>ทั้งหมด</em></> : <>All <em>transactions</em></>}
          </h1>
        </div>
      </div>

      <div className="tx-toolbar">
        <div className="search">
          {Ic.search}
          <input
            placeholder={t(I18N.search_ph, lang)}
            value={search}
            onChange={(e) => setSearch(e.target.value)} />
          
        </div>
        <div className="filter-anchor" ref={filterRef}>
          <button className="btn" onClick={() => setFilterOpen((o) => !o)}>
            {Ic.sliders}{lang === 'th' ? 'ฟิลเตอร์' : 'Filters'}
            {activeFilterCount > 0 &&
            <span style={{
              background: 'var(--accent)', color: 'var(--bg)', fontSize: 10,
              padding: '1px 6px', borderRadius: 999, fontWeight: 700, marginLeft: 2,
              fontFamily: 'var(--num)'
            }}>{activeFilterCount}</span>
            }
          </button>
          {filterOpen &&
          <FilterPopover
            lang={lang}
            filterType={filterType} setFilterType={setFilterType}
            sortBy={sortBy} setSortBy={setSortBy}
            onClear={() => {setFilterType('all');setSortBy('date-desc');}}
            onClose={() => setFilterOpen(false)}
            activeCount={activeFilterCount} />

          }
        </div>
        <button className="btn btn-primary" onClick={() => setModalOpen(true)}>
          {Ic.plus}{lang === 'th' ? 'เพิ่มรายการ' : 'Add entry'}
        </button>
      </div>

      <div className="chip-row">
        <span className={'chip' + (!filterCat ? ' active' : '')} onClick={() => setFilterCat(null)}>
          {lang === 'th' ? 'ทั้งหมด' : 'All'} <span style={{ opacity: 0.5 }}>({txs.length})</span>
        </span>
        {catKeys.map((k) => {
          const cat = CATEGORIES[k];
          const count = txs.filter((x) => x.category === k).length;
          if (count === 0) return null;
          return (
            <span
              key={k}
              className={'chip' + (filterCat === k ? ' active' : '')}
              onClick={() => setFilterCat(k)}>
              
              <span className="dot" style={{ background: cat.color }}></span>
              {t(cat, lang)} <span style={{ opacity: 0.5 }}>({count})</span>
            </span>);

        })}
      </div>

      <div className="card" style={{ fontFamily: "Manrope" }}>
        {groups.length === 0 &&
        <div style={{ padding: 60, textAlign: 'center', color: 'var(--ink-subtle)' }}>
            {lang === 'th' ? 'ไม่พบรายการที่ตรงกัน' : 'No matching entries'}
          </div>
        }
        {groups.map(([date, items]) => {
          const dayTotal = items.reduce((a, x) => a + (x.amount < 0 ? -x.amount : 0), 0);
          return (
            <div key={date}>
              <div className="tx-group-label">
                <span>{formatGroupDate(date, lang)}</span>
                <span className="total">−{fmt(dayTotal, currency, lang)}</span>
              </div>
              {items.map((tx, i) => (
                <EditableTxRow
                  key={tx.id != null ? `tx-${tx.id}` : `i-${date}-${i}`}
                  tx={tx}
                  currency={currency}
                  lang={lang}
                  canEdit={!!editCategory && tx.id != null && tx.category !== 'income'}
                  onEdit={() => setEditingTx(tx)} />
              ))}
            </div>);

        })}
      </div>

      {modalOpen &&
      <AddTxModal
        lang={lang}
        onSave={(tx) => {addTxs([tx]);setModalOpen(false);}}
        onClose={() => setModalOpen(false)} />

      }

      {editingTx &&
      <EditCategoryModal
        lang={lang}
        tx={editingTx}
        onClose={() => setEditingTx(null)}
        onSave={async (newCat, savePattern) => {
          const r = await editCategory(editingTx.id, newCat, savePattern);
          if (r && r.ok) setEditingTx(null);
          return r;
        }} />
      }
    </div>);

}

// ─────────────────────────────────────────────────────────────
// EditableTxRow — wraps the standard TransactionRow look but adds
// a small pencil button next to the category pill. Day 5 Learning Loop.
// We re-render the whole row locally (rather than monkey-patching the
// shared TransactionRow in ux_ui/) so this change stays in frontend/.
// ─────────────────────────────────────────────────────────────
function EditableTxRow({ tx, currency, lang, canEdit, onEdit }) {
  const cat = CATEGORIES[tx.category] || CATEGORIES.other;
  const isIncome = tx.amount > 0;
  const parts = fmtParts(tx.amount, currency, lang);
  return (
    <div className="tx-row">
      <div className="tx-icon" style={{ background: `${cat.color}22`, color: cat.color }}>
        <span style={{ fontSize: 16 }}>{cat.icon}</span>
      </div>
      <div>
        <div className="tx-merchant">{tx.merchant}</div>
        <div className="tx-meta">
          <span className="tx-cat-pill">{t(cat, lang)}</span>
          {canEdit &&
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onEdit(); }}
              title={t(I18N.edit_cat_btn, lang)}
              aria-label={t(I18N.edit_cat_btn, lang)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 22,
                height: 22,
                marginLeft: -2,
                padding: 0,
                border: '1px solid var(--border)',
                borderRadius: 7,
                background: 'transparent',
                color: 'var(--ink-subtle)',
                cursor: 'pointer',
                transition: 'color 160ms ease, border-color 160ms ease, background 160ms ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--accent)';
                e.currentTarget.style.borderColor = 'var(--accent)';
                e.currentTarget.style.background = 'var(--accent-soft)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--ink-subtle)';
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.background = 'transparent';
              }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="1.8"
                strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
              </svg>
            </button>
          }
          <span>·</span>
          <span>{formatDate(tx.date, lang)}</span>
          {tx.note && <><span>·</span><span style={{ fontStyle: 'italic' }}>{tx.note}</span></>}
        </div>
      </div>
      <div className={'tx-amount ' + (isIncome ? 'income' : 'expense')}>
        {isIncome ? '+' : ''}{parts.sign}{parts.currency}{parts.digits}
      </div>
      <div className="tx-arrow">{Ic.arrow}</div>
    </div>);
}

// ─────────────────────────────────────────────────────────────
// EditCategoryModal — Day 5 Learning Loop
// Lets the user pick a new category for one transaction, with an opt-in
// "remember for this merchant" checkbox (default ON).
// ─────────────────────────────────────────────────────────────
function EditCategoryModal({ lang, tx, onClose, onSave }) {
  const currentCat = CATEGORIES[tx.category] || CATEGORIES.other;
  const [selected, setSelected] = useState(tx.category && tx.category !== 'income' ? tx.category : 'food');
  const [savePattern, setSavePattern] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !saving) onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose, saving]);

  // 8 categories per spec (excludes 'income' — that's a sign, not a spend bucket)
  const catKeys = ['food', 'transport', 'shopping', 'home', 'entertain', 'groceries', 'health', 'other'];

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    const r = await onSave(selected, savePattern);
    // If save failed, keep modal open so the user can retry; toast shows reason.
    if (!r || !r.ok) setSaving(false);
  };

  const patternLabel = t(I18N.edit_cat_save_pattern, lang).replace('{merchant}', tx.merchant || '');

  return (
    <div className="modal-overlay" onClick={saving ? undefined : onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <div className="modal-head">
          <h3>{t(I18N.edit_cat_title, lang)}</h3>
          {!saving &&
            <button className="icon-btn" onClick={onClose}>{Ic.close}</button>
          }
        </div>
        <div className="modal-body">
          <div className="field">
            <label className="field-label">{t(I18N.edit_cat_current, lang)}</label>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              borderRadius: 10,
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              fontSize: 13.5,
              color: 'var(--ink)',
            }}>
              <span style={{
                display: 'inline-flex',
                width: 26, height: 26,
                alignItems: 'center', justifyContent: 'center',
                borderRadius: 8,
                background: `${currentCat.color}22`,
                color: currentCat.color,
                fontSize: 14,
              }}>{currentCat.icon}</span>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontWeight: 500 }}>{tx.merchant}</span>
                <span style={{ fontSize: 12, color: 'var(--ink-muted)' }}>{t(currentCat, lang)}</span>
              </div>
            </div>
          </div>

          <div className="field">
            <label className="field-label">{t(I18N.edit_cat_new, lang)}</label>
            <div className="cat-picker">
              {catKeys.map((k) => {
                const cat = CATEGORIES[k];
                return (
                  <div
                    key={k}
                    className={'cat-pick' + (selected === k ? ' active' : '')}
                    onClick={() => setSelected(k)}>
                    <span className="cat-pick-icon">{cat.icon}</span>
                    <span>{t(cat, lang)}</span>
                  </div>);
              })}
            </div>
          </div>

          <label
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              padding: '12px 14px',
              borderRadius: 10,
              background: savePattern ? 'var(--accent-soft)' : 'var(--surface)',
              border: '1px solid ' + (savePattern ? 'var(--accent)' : 'var(--border)'),
              cursor: 'pointer',
              transition: 'background 160ms ease, border-color 160ms ease',
            }}>
            <input
              type="checkbox"
              checked={savePattern}
              onChange={(e) => setSavePattern(e.target.checked)}
              style={{
                marginTop: 2,
                accentColor: 'var(--accent)',
                cursor: 'pointer',
                width: 16, height: 16,
                flexShrink: 0,
              }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 13.5, color: 'var(--ink)', lineHeight: 1.45 }}>{patternLabel}</span>
              <span style={{ fontSize: 11.5, color: 'var(--ink-muted)', lineHeight: 1.45 }}>
                {t(I18N.edit_cat_save_pattern_hint, lang)}
              </span>
            </div>
          </label>
        </div>
        <div className="modal-foot">
          <button
            className="btn"
            onClick={onClose}
            disabled={saving}
            style={{ opacity: saving ? 0.5 : 1 }}>
            {t(I18N.edit_cat_cancel, lang)}
          </button>
          <button
            className="btn btn-accent"
            onClick={handleSave}
            disabled={saving}
            style={{ opacity: saving ? 0.7 : 1 }}>
            {Ic.check}{saving ? t(I18N.edit_cat_saving, lang) : t(I18N.edit_cat_save, lang)}
          </button>
        </div>
      </div>
    </div>);
}

// ─────────────────────────────────────────────────────────────
// FilterPopover
// ─────────────────────────────────────────────────────────────
function FilterPopover({ lang, filterType, setFilterType, sortBy, setSortBy, onClear, onClose, activeCount }) {
  const sortOptions = [
  { id: 'date-desc', th: 'ใหม่ไปเก่า', en: 'Newest first' },
  { id: 'date-asc', th: 'เก่าไปใหม่', en: 'Oldest first' },
  { id: 'amount-desc', th: 'จำนวนมากไปน้อย', en: 'Highest amount' },
  { id: 'amount-asc', th: 'จำนวนน้อยไปมาก', en: 'Lowest amount' }];


  return (
    <div className="filter-pop" onClick={(e) => e.stopPropagation()}>
      <h5>{lang === 'th' ? 'ประเภท' : 'Type'}</h5>
      <div className="seg">
        <button className={filterType === 'all' ? 'active' : ''} onClick={() => setFilterType('all')}>
          {lang === 'th' ? 'ทั้งหมด' : 'All'}
        </button>
        <button className={filterType === 'income' ? 'active' : ''} onClick={() => setFilterType('income')}>
          {lang === 'th' ? 'รายรับ' : 'Income'}
        </button>
        <button className={filterType === 'expense' ? 'active' : ''} onClick={() => setFilterType('expense')}>
          {lang === 'th' ? 'รายจ่าย' : 'Expense'}
        </button>
      </div>

      <h5>{lang === 'th' ? 'จัดเรียง' : 'Sort by'}</h5>
      <div className="select-list">
        {sortOptions.map((o) =>
        <div key={o.id} className={'select-item' + (sortBy === o.id ? ' active' : '')} onClick={() => setSortBy(o.id)}>
            <span>{lang === 'th' ? o.th : o.en}</span>
            {Ic.check}
          </div>
        )}
      </div>

      <div className="filter-actions">
        <button className="filter-clear" onClick={onClear}>
          {lang === 'th' ? 'ล้างฟิลเตอร์' : 'Clear all'}
        </button>
        {activeCount > 0 &&
        <span className="filter-count">{activeCount} {lang === 'th' ? 'ใช้งาน' : 'active'}</span>
        }
      </div>
    </div>);

}

// ─────────────────────────────────────────────────────────────
// AddTxModal
// ─────────────────────────────────────────────────────────────
function AddTxModal({ lang, onSave, onClose }) {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [merchant, setMerchant] = useState('');
  const [amount, setAmount] = useState('');
  const [sign, setSign] = useState('expense'); // expense | income
  const [category, setCategory] = useState('food');
  const [note, setNote] = useState('');

  useEffect(() => {
    const onKey = (e) => {if (e.key === 'Escape') onClose();};
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const canSave = merchant.trim() && parseFloat(amount) > 0;

  const handleSave = () => {
    if (!canSave) return;
    const amt = parseFloat(amount);
    const tx = {
      date,
      merchant: merchant.trim(),
      amount: sign === 'income' ? amt : -amt,
      category: sign === 'income' ? 'income' : category,
      note: note.trim()
    };
    onSave(tx);
  };

  const catKeys = Object.keys(CATEGORIES).filter((k) => k !== 'income' && k !== 'other');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{lang === 'th' ? 'เพิ่มรายการธุรกรรม' : 'New transaction'}</h3>
          <button className="icon-btn" onClick={onClose}>{Ic.close}</button>
        </div>
        <div className="modal-body">
          <div className="field">
            <label className="field-label">{lang === 'th' ? 'ประเภท' : 'Type'}</label>
            <div className="seg">
              <button className={sign === 'expense' ? 'active' : ''} onClick={() => setSign('expense')}>
                {lang === 'th' ? 'รายจ่าย' : 'Expense'}
              </button>
              <button className={sign === 'income' ? 'active' : ''} onClick={() => setSign('income')}>
                {lang === 'th' ? 'รายรับ' : 'Income'}
              </button>
            </div>
          </div>

          <div className="field-row">
            <div className="field">
              <label className="field-label">{lang === 'th' ? 'วันที่' : 'Date'}</label>
              <input className="field-input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="field">
              <label className="field-label">{lang === 'th' ? 'จำนวน (฿)' : 'Amount (฿)'}</label>
              <input
                className="field-input"
                type="number"
                inputMode="decimal"
                placeholder="0"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                style={{ fontFamily: 'var(--num)' }} />
              
            </div>
          </div>

          <div className="field">
            <label className="field-label">{lang === 'th' ? 'ร้านค้า / รายการ' : 'Merchant / item'}</label>
            <input
              className="field-input"
              placeholder={lang === 'th' ? 'เช่น Starbucks Siam' : 'e.g. Starbucks Siam'}
              value={merchant}
              onChange={(e) => setMerchant(e.target.value)} />
            
          </div>

          {sign === 'expense' &&
          <div className="field">
              <label className="field-label">{lang === 'th' ? 'หมวด' : 'Category'}</label>
              <div className="cat-picker">
                {catKeys.map((k) => {
                const cat = CATEGORIES[k];
                return (
                  <div
                    key={k}
                    className={'cat-pick' + (category === k ? ' active' : '')}
                    onClick={() => setCategory(k)}>
                    
                      <span className="cat-pick-icon">{cat.icon}</span>
                      <span>{t(cat, lang)}</span>
                    </div>);

              })}
              </div>
            </div>
          }

          <div className="field">
            <label className="field-label">{lang === 'th' ? 'หมายเหตุ (ไม่บังคับ)' : 'Note (optional)'}</label>
            <input
              className="field-input"
              placeholder={lang === 'th' ? 'รายละเอียดเพิ่มเติม...' : 'Add details…'}
              value={note}
              onChange={(e) => setNote(e.target.value)} />
            
          </div>
        </div>
        <div className="modal-foot">
          <button className="btn" onClick={onClose}>{lang === 'th' ? 'ยกเลิก' : 'Cancel'}</button>
          <button className="btn btn-accent" onClick={handleSave} disabled={!canSave} style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? 'auto' : 'none' }}>
            {Ic.check}{lang === 'th' ? 'บันทึก' : 'Save entry'}
          </button>
        </div>
      </div>
    </div>);

}

// ─────────────────────────────────────────────────────────────
// Upload
// ─────────────────────────────────────────────────────────────

// Simple CSV parser — handles quoted values and commas inside quotes
function parseCSV(text) {
  // Normalize: strip BOM if present
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
  // Detect delimiter — try comma, tab, semicolon
  const firstLine = text.split(/\r?\n/)[0] || '';
  let delim = ',';
  const commaCount = (firstLine.match(/,/g) || []).length;
  const tabCount = (firstLine.match(/\t/g) || []).length;
  const semiCount = (firstLine.match(/;/g) || []).length;
  if (tabCount > commaCount && tabCount > semiCount) delim = '\t';else
  if (semiCount > commaCount) delim = ';';

  const rows = [];
  let cur = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"' && text[i + 1] === '"') {field += '"';i++;} else
      if (ch === '"') {inQuotes = false;} else
      {field += ch;}
    } else {
      if (ch === '"') inQuotes = true;else
      if (ch === delim) {cur.push(field);field = '';} else
      if (ch === '\n' || ch === '\r') {
        if (ch === '\r' && text[i + 1] === '\n') i++;
        cur.push(field);field = '';
        if (cur.length > 1 || cur[0] !== '') rows.push(cur);
        cur = [];
      } else {field += ch;}
    }
  }
  if (field || cur.length) {cur.push(field);rows.push(cur);}
  return rows;
}

// FileReader wrapped in a promise (better compat than file.text())
function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = () => reject(reader.error || new Error('read failed'));
    // Try UTF-8 first; if file has Thai but is in TIS-620 it might look garbled but won't error
    reader.readAsText(file, 'utf-8');
  });
}

// Find column index that looks like a date / merchant / amount column
function detectColumns(header, sample) {
  const lc = header.map((h) => (h || '').toLowerCase().trim());
  const find = (...keys) => lc.findIndex((h) => keys.some((k) => h.includes(k)));
  let dateIdx = find('date', 'วันที่', 'transaction date', 'posted', 'time');
  let merchantIdx = find('merchant', 'description', 'detail', 'รายละเอียด', 'ร้าน', 'narration', 'name');
  let amountIdx = find('amount', 'จำนวน', 'value', 'baht');
  // Some banks split into debit/credit columns
  const debitIdx = find('debit', 'withdraw', 'ถอน', 'รายจ่าย');
  const creditIdx = find('credit', 'deposit', 'ฝาก', 'รายรับ');

  // Heuristic fallback: scan sample row
  if (sample && (dateIdx < 0 || merchantIdx < 0 || amountIdx < 0 && debitIdx < 0)) {
    sample.forEach((val, i) => {
      const v = (val || '').trim();
      if (dateIdx < 0 && /^\d{4}[-/]\d{1,2}[-/]\d{1,2}/.test(v)) dateIdx = i;
      if (dateIdx < 0 && /^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}/.test(v)) dateIdx = i;
      if (amountIdx < 0 && /^-?[\d,]+\.?\d*$/.test(v) && v.replace(/,/g, '').length > 1) amountIdx = i;
      if (merchantIdx < 0 && v.length > 4 && /[a-zA-Zก-๛]/.test(v) && !/^\d/.test(v)) merchantIdx = i;
    });
  }

  return { dateIdx, merchantIdx, amountIdx, debitIdx, creditIdx };
}

function normalizeDate(s) {
  if (!s) return '';
  s = s.trim();
  // ISO yyyy-mm-dd
  let m = s.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
  // dd/mm/yyyy or dd-mm-yyyy
  m = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})/);
  if (m) {
    let y = m[3];
    if (y.length === 2) y = '20' + y;
    return `${y}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  }
  return s;
}

// Auto-categorise based on merchant keywords
function autoCategory(merchant) {
  const m = (merchant || '').toLowerCase();
  if (/starbucks|cafe|coffee|amazon coffee|7-eleven|7\-11|mcdonald|kfc|burger|pizza|restaurant|sushi|noodle|food|panda|bolt food|grabfood|กาแฟ|อาหาร|ร้าน/.test(m)) return 'food';
  if (/grab(?!food)|bolt(?!food)|taxi|bts|mrt|shell|esso|ptt|caltex|fuel|gas|skytrain|airport rail|รถ|แท็กซี่|น้ำมัน/.test(m)) return 'transport';
  if (/shopee|lazada|uniqlo|h&m|zara|nike|adidas|emsphere|mall|paragon|central|emporium|ikea|store|shop|ช้อป/.test(m)) return 'shopping';
  if (/rent|electric|water|wifi|tot|ais|true|dtac|aws|pea|mea|apartment|condo|บ้าน|ค่าไฟ|ค่าน้ำ|เน็ต/.test(m)) return 'home';
  if (/netflix|spotify|cineplex|cinema|youtube|disney|apple music|hbo|game|movie|บันเทิง|หนัง/.test(m)) return 'entertain';
  if (/tops|big c|lotus|tesco|makro|villa market|gourmet|mart|grocery|ของใช้|ตลาด|เซเว่น/.test(m)) return 'groceries';
  if (/pharmacy|watson|boots|hospital|clinic|aia|allianz|axa|insurance|สุขภาพ|ยา|โรงพยาบาล/.test(m)) return 'health';
  if (/salary|payroll|freelance|payout|transfer in|interest|รายรับ|เงินเดือน|โบนัส/.test(m)) return 'income';
  return 'other';
}

function Upload({ state, addTxs, setPendingImport, lastImport, deleteLastImport }) {
  const { lang, currency } = state;
  const [stage, setStage] = useState('idle'); // idle | parsing | review | done
  const [activeStep, setActiveStep] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState([]);
  const [fileName, setFileName] = useState('');
  const [fileError, setFileError] = useState('');
  // Result of the most recent POST /api/transactions:
  // {created, skipped, importId, error?} — drives the "done" message + Undo button
  const [importResult, setImportResult] = useState(null);
  const [undoing, setUndoing] = useState(false);
  const [undoMessage, setUndoMessage] = useState(''); // post-undo toast text
  // PDF password — for encrypted bank statements. Kept in React state only
  // (NEVER persisted to localStorage/sessionStorage). Cleared after a
  // successful import and on Reset.
  const [pdfPassword, setPdfPassword] = useState('');
  const [pwError, setPwError] = useState(false); // true when backend says password is wrong/missing
  const fileRef = useRef(null);
  const pwInputRef = useRef(null);

  const steps = [I18N.parse_step_1, I18N.parse_step_2, I18N.parse_step_3, I18N.parse_step_4];

  // Fallback mock entries (used for PDFs and when CSV parse yields nothing)
  const MOCK_ENTRIES = [
  { date: '2026-05-16', merchant: 'Cafe Amazon - Phrom Phong', amount: -85, category: 'food' },
  { date: '2026-05-16', merchant: 'GrabPay', amount: -135, category: 'transport' },
  { date: '2026-05-16', merchant: 'Tops Market', amount: -640, category: 'groceries' },
  { date: '2026-05-15', merchant: 'Uniqlo Emsphere', amount: -1290, category: 'shopping' },
  { date: '2026-05-15', merchant: 'BTS Skytrain', amount: -47, category: 'transport' },
  { date: '2026-05-14', merchant: 'AIA Insurance', amount: -1450, category: 'health' },
  { date: '2026-05-14', merchant: 'Lazada', amount: -380, category: 'shopping' },
  { date: '2026-05-13', merchant: 'Foodpanda', amount: -195, category: 'food' }];


  const animateThenReview = (entries) => {
    setStage('parsing');
    setActiveStep(0);
    let i = 0;
    const tick = () => {
      i++;
      if (i < 4) {
        setActiveStep(i);
        setTimeout(tick, 600);
      } else {
        setPreview(entries);
        setStage('review');
      }
    };
    setTimeout(tick, 600);
  };

  const handleFile = async (file) => {
    if (!file) return;
    setFileError('');
    setPwError(false);
    setFileName(file.name);
    console.log('[Upload] received file', file.name, file.type, file.size);

    const isCSV = /\.csv$/i.test(file.name) || /csv|excel/i.test(file.type || '');
    const isPDF = /\.pdf$/i.test(file.name) || file.type === 'application/pdf';
    const looksLikeText = !file.type || /text|json|csv/.test(file.type);

    if (!isCSV && !isPDF && !looksLikeText) {
      setFileError(lang === 'th' ?
      `ไฟล์ "${file.name}" ไม่รองรับ — ใช้ CSV หรือ PDF เท่านั้น` :
      `"${file.name}" not supported — use CSV or PDF.`);
      return;
    }

    // PDF — upload to Python backend; server parses with pdfplumber and returns rows.
    if (isPDF) {
      try {
        setStage('parsing');
        setActiveStep(0);

        // Step 1 — upload file to backend
        await new Promise((r) => setTimeout(r, 200));
        setActiveStep(1);

        // Step 2 — backend parses PDF and returns transactions
        const fd = new FormData();
        fd.append('file', file);
        // Always send the password field (empty string is fine — backend handles it).
        // Bank PDFs are often encrypted; user fills the field below the dropzone.
        fd.append('password', pdfPassword);
        const res = await fetch('/api/parse-pdf', { method: 'POST', body: fd });
        if (!res.ok) {
          const errPayload = await res.json().catch(() => ({}));
          const errMsg = errPayload.error || ('HTTP ' + res.status);
          // Password-related error → highlight the password field + focus it,
          // instead of just showing a generic file error.
          if (res.status === 400 && /ติดรหัส|รหัส|password|encrypted/i.test(errMsg)) {
            setStage('idle');
            setActiveStep(0);
            setFileError(errMsg);
            setPwError(true);
            // Defer focus so the input is mounted/visible.
            setTimeout(() => pwInputRef.current?.focus(), 0);
            return;
          }
          throw new Error(errMsg);
        }
        const payload = await res.json();
        const parsed = payload.transactions || [];
        console.log('[Upload] PDF parsed by backend', payload.bank, parsed.length, 'entries; first:', parsed[0]);
        if (typeof setPendingImport === 'function') {
          setPendingImport({ filename: file.name, bank: payload.bank || 'unknown', count: parsed.length });
        }

        if (!parsed || parsed.length === 0) {
          setStage('idle');
          setActiveStep(0);
          setFileError(lang === 'th' ?
          'ไม่พบธุรกรรมในไฟล์ PDF นี้ — รองรับ K-Bank, ออมสิน (GSB), กรุงไทย (KTB) และไทยพาณิชย์ (SCB)' :
          'No transactions found — supports K-Bank, GSB, KTB and SCB statements.');
          return;
        }

        setActiveStep(2);
        await new Promise((r) => setTimeout(r, 500));
        setActiveStep(3);
        await new Promise((r) => setTimeout(r, 400));

        // Sort newest first; cap to a sane preview size
        const sorted = parsed.slice().sort((a, b) => b.date.localeCompare(a.date));
        setPreview(sorted.slice(0, 500));
        setStage('review');
      } catch (err) {
        console.error('[Upload] PDF parse error', err);
        setStage('idle');
        setActiveStep(0);
        setFileError(lang === 'th' ?
        'อ่านไฟล์ PDF ไม่สำเร็จ — ' + (err.message || 'ลองอีกครั้ง') :
        'Could not read PDF — ' + (err.message || 'please try again.'));
      }
      return;
    }

    // CSV / text — read & parse
    let text;
    try {
      text = await readFileAsText(file);
    } catch (err) {
      console.error('[Upload] read error', err);
      setFileError(lang === 'th' ? 'อ่านไฟล์ไม่สำเร็จ — ลองอีกครั้ง' : 'Could not read file — please try again.');
      return;
    }

    if (!text || !text.trim()) {
      setFileError(lang === 'th' ? 'ไฟล์ว่าง' : 'File appears empty');
      return;
    }

    console.log('[Upload] file content preview', text.slice(0, 200));
    const rows = parseCSV(text);
    console.log('[Upload] parsed rows', rows.length, 'first:', rows[0]);

    if (rows.length < 2) {
      setFileError(lang === 'th' ? 'ไฟล์มีข้อมูลไม่พอ — ต้องมีอย่างน้อย 1 บรรทัดพร้อม header' : 'File needs at least 1 row plus a header.');
      return;
    }
    const header = rows[0];
    const dataRows = rows.slice(1);
    const cols = detectColumns(header, dataRows[0]);
    console.log('[Upload] detected columns', cols);

    const parsed = [];
    for (const row of dataRows) {
      let amount = 0;
      if (cols.amountIdx >= 0) {
        const raw = (row[cols.amountIdx] || '').replace(/[฿$, ]/g, '');
        amount = parseFloat(raw) || 0;
      } else if (cols.debitIdx >= 0 || cols.creditIdx >= 0) {
        const d = parseFloat((row[cols.debitIdx] || '').replace(/[฿$, ]/g, '')) || 0;
        const c = parseFloat((row[cols.creditIdx] || '').replace(/[฿$, ]/g, '')) || 0;
        amount = c - d;
      }
      if (amount === 0) continue;

      const merchant = (cols.merchantIdx >= 0 ? row[cols.merchantIdx] : '').trim() || 'Unknown';
      const date = cols.dateIdx >= 0 ? normalizeDate(row[cols.dateIdx]) : '';

      parsed.push({
        date: date || new Date().toISOString().slice(0, 10),
        merchant,
        amount,
        category: amount > 0 ? 'income' : autoCategory(merchant)
      });
    }

    if (parsed.length === 0) {
      setFileError(lang === 'th' ?
      'ไม่พบธุรกรรมในไฟล์นี้ — ตรวจสอบว่ามีคอลัมน์ date / merchant / amount หรือยัง' :
      'No transactions found — check the file has date / merchant / amount columns.');
      return;
    }

    console.log('[Upload] producing', parsed.length, 'entries');
    animateThenReview(parsed.slice(0, 50));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const handlePick = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = ''; // allow picking same file again
  };

  const onClickZone = () => {
    if (stage !== 'idle') return;
    fileRef.current?.click();
  };

  const handleImport = async () => {
    setStage('done');
    setUndoMessage('');
    // Wait for backend so we can show the real created/skipped numbers.
    const result = await addTxs(preview);
    setImportResult(result || { created: preview.length, skipped: 0 });
    // PDF password is no longer needed once the file has been parsed — drop it.
    setPdfPassword('');
    setPwError(false);
    // Stage stays at 'done' until the user clicks "ทำต่อ / Done" or Undo.
    // (Previously auto-reset after 2.2s — but now we need the Undo button
    // to stay visible long enough for the user to actually use it.)
  };

  const handleReset = () => {
    setStage('idle');
    setActiveStep(0);
    setPreview([]);
    setFileName('');
    setFileError('');
    setImportResult(null);
    setUndoMessage('');
    setPdfPassword('');
    setPwError(false);
  };

  const handleUndo = async () => {
    if (!lastImport || undoing) return;
    const msg = t(I18N.undo_confirm, lang);
    // Simple confirm dialog — keeps the implementation light. Could be
    // replaced with a styled modal later if design wants it.
    if (!window.confirm(msg)) return;
    setUndoing(true);
    const res = await deleteLastImport();
    setUndoing(false);
    if (res && res.ok) {
      const success = t(I18N.undo_success, lang).replace('{n}', (res.removed || 0).toLocaleString(lang === 'th' ? 'th-TH' : 'en-US'));
      setUndoMessage(success);
      // Clear the import-result message — the entries are gone now.
      setImportResult(null);
    } else {
      setUndoMessage(t(I18N.undo_failed, lang));
    }
  };

  // Load the bundled sample CSV
  const trySample = async () => {
    try {
      const res = await fetch('samples/sample-statement.csv');
      const text = await res.text();
      const blob = new Blob([text], { type: 'text/csv' });
      const file = new File([blob], 'sample-statement.csv', { type: 'text/csv' });
      handleFile(file);
    } catch (e) {
      setFileError(lang === 'th' ? 'โหลด sample ไม่สำเร็จ' : 'Could not load sample');
    }
  };

  return (
    <div className="page-enter upload-page">
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <div className="crumb">{t(I18N.upload_title, lang)}</div>
        <h1 className="section-h" style={{ fontSize: 44, marginTop: 8 }}>
          {lang === 'th' ? <>ดึง <em>ธุรกรรม</em> จากสเตทเมนต์ของคุณ</> : <>Pull <em>transactions</em> from your statement</>}
        </h1>
        <p className="section-sub" style={{ maxWidth: 520, margin: '8px auto 0' }}>{t(I18N.upload_sub, lang)}</p>
      </div>

      <div
        className={'dropzone' + (dragging ? ' dragging' : '')}
        onDragOver={(e) => {e.preventDefault();if (stage === 'idle') setDragging(true);}}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={onClickZone}
        style={{ pointerEvents: stage === 'idle' ? 'auto' : 'none', opacity: stage === 'idle' ? 1 : 0.6 }}>
        
        <div className="dropzone-icon">{Ic.upload}</div>
        <h2>{t(I18N.drop_h, lang)}</h2>
        <p>{t(I18N.drop_sub, lang)}</p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.pdf,text/csv,application/pdf"
          onChange={handlePick}
          style={{ display: 'none' }} />

      </div>

      {/* PDF password — kept always-visible so users can fill it BEFORE
          dragging an encrypted file. Empty string is fine for unencrypted PDFs. */}
      {stage === 'idle' &&
      <div className="field" style={{ maxWidth: 520, margin: '18px auto 0' }}>
        <label className="field-label" htmlFor="pdf-password">{t(I18N.upload_password_label, lang)}</label>
        <input
          ref={pwInputRef}
          id="pdf-password"
          type="password"
          autoComplete="off"
          className="field-input"
          placeholder={t(I18N.upload_password_placeholder, lang)}
          value={pdfPassword}
          onChange={(e) => { setPdfPassword(e.target.value); if (pwError) setPwError(false); }}
          style={pwError ? { borderColor: 'var(--negative)' } : undefined} />
        <span style={{ fontSize: 11.5, color: 'var(--ink-subtle)', lineHeight: 1.5, marginTop: 2 }}>
          {t(I18N.upload_password_hint, lang)}
        </span>
      </div>
      }

      {fileError &&
      <div style={{ marginTop: 16, padding: '12px 16px', background: 'var(--negative-soft)', border: '1px solid rgba(216,138,138,0.3)', color: 'var(--negative)', borderRadius: 12, fontSize: 13 }}>
          {fileError}
        </div>
      }

      {stage === 'idle' &&
      <div style={{ textAlign: 'center', marginTop: 18, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12 }}>
          <span style={{ color: 'var(--ink-subtle)', fontSize: 12.5 }}>
            {lang === 'th' ? 'อยากลองก่อน?' : 'Want to try first?'}
          </span>
          <button className="btn" onClick={trySample}>
            {Ic.file}{lang === 'th' ? 'ใช้ไฟล์ตัวอย่าง' : 'Try sample CSV'}
          </button>
        </div>
      }

      {(stage === 'parsing' || stage === 'review' || stage === 'done') &&
      <div className="card parse-stage page-enter">
          <div className="card-title" style={{ marginBottom: 12 }}>
            <h3>{lang === 'th' ? 'กำลังประมวลผลไฟล์' : 'Processing file'}</h3>
            <span className="more" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {Ic.file} {fileName || (lang === 'th' ? 'ไฟล์ของคุณ' : 'your file')}
            </span>
          </div>
          {steps.map((s, i) => {
          const done = i < activeStep || stage === 'review' || stage === 'done';
          const active = i === activeStep && stage === 'parsing';
          return (
            <div key={i} className={'parse-step' + (done ? ' done' : '') + (active ? ' active' : '')}>
                <div className="num">{done ? Ic.check : i + 1}</div>
                <div>{t(s, lang)}</div>
                <div className="status">
                  {done ? lang === 'th' ? 'เสร็จ' : 'DONE' : active ? lang === 'th' ? 'กำลังทำ...' : 'WORKING...' : lang === 'th' ? 'รอ' : 'WAITING'}
                </div>
              </div>);

        })}
        </div>
      }

      {stage === 'review' &&
      <>
          <h3 style={{ marginTop: 28, marginBottom: 14, fontFamily: 'var(--serif)', fontSize: 24, fontWeight: 400 }}>
            {t(I18N.preview_h, lang).replace('{n}', preview.length)}
          </h3>
          <div className="preview-table">
            <div className="preview-head">
              <div>{lang === 'th' ? 'วันที่' : 'Date'}</div>
              <div>{lang === 'th' ? 'รายการ' : 'Merchant'}</div>
              <div>{lang === 'th' ? 'หมวด (AI จัดให้)' : 'Category (AI)'}</div>
              <div style={{ textAlign: 'right' }}>{lang === 'th' ? 'จำนวน' : 'Amount'}</div>
            </div>
            <div className="preview-scroll">
            {preview.map((p, i) => {
            const cat = CATEGORIES[p.category] || CATEGORIES.other;
            return (
              <div key={i} className="preview-row">
                  <div style={{ color: 'var(--ink-muted)', fontFamily: 'var(--num)', fontSize: 12 }}>{p.date}</div>
                  <div style={{ fontWeight: 500 }}>{p.merchant}</div>
                  <div>
                    <span className="tx-cat-pill" style={{ borderColor: cat.color + '55', color: cat.color }}>
                      {cat.icon} {t(cat, lang)}
                    </span>
                  </div>
                  <div style={{ textAlign: 'right', fontFamily: 'var(--num)', fontSize: 13, color: p.amount > 0 ? 'var(--positive)' : 'var(--ink)' }}>
                    {p.amount > 0 ? '+' : ''}{fmt(p.amount, currency, lang)}
                  </div>
                </div>);

          })}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12, marginTop: 20, justifyContent: 'flex-end' }}>
            <button className="btn" onClick={handleReset}>{t(I18N.cancel, lang)}</button>
            <button className="btn btn-accent" onClick={handleImport}>{Ic.check}{t(I18N.import_btn, lang)} ({preview.length})</button>
          </div>
        </>
      }

      {stage === 'done' && (() => {
        // While addTxs is still in-flight, show a neutral "saving" state.
        const r = importResult;
        const loading = !r;
        const created = r ? r.created : 0;
        const skipped = r ? r.skipped : 0;
        const allDup = !loading && created === 0 && skipped > 0;
        const partial = !loading && created > 0 && skipped > 0;
        const plain = !loading && created > 0 && skipped === 0;

        // Build the headline using i18n templates ({n}, {m} placeholders)
        const fmtN = (n) => (n || 0).toLocaleString(lang === 'th' ? 'th-TH' : 'en-US');
        let headlineKey;
        if (plain) headlineKey = I18N.import_result_created;
        else if (partial) headlineKey = I18N.import_result_partial;
        else if (allDup) headlineKey = I18N.import_result_all_dup;

        const headline = headlineKey ?
          t(headlineKey, lang).replace('{n}', fmtN(created)).replace('{m}', fmtN(skipped)) :
          (lang === 'th' ? 'กำลังบันทึก...' : 'Saving…');

        const iconColor = allDup ? 'var(--ink-subtle)' : 'var(--positive)';
        const iconBg = allDup ? 'var(--accent-soft)' : 'var(--positive-soft)';

        return (
          <div className="card page-enter" style={{ marginTop: 24, padding: 32, textAlign: 'center' }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16, margin: '0 auto 18px',
              background: iconBg, display: 'grid', placeItems: 'center', color: iconColor
            }}>{allDup ? Ic.file : Ic.check}</div>
            <h2 style={{ fontFamily: 'var(--serif)', fontSize: 26, fontWeight: 400, margin: '0 0 6px' }}>
              {headline}
            </h2>
            <p style={{ color: 'var(--ink-subtle)', fontSize: 13.5, margin: 0 }}>
              {allDup ?
                (lang === 'th' ? 'ไม่มีการเปลี่ยนแปลงในข้อมูลของคุณ' : 'No changes to your data.') :
                (lang === 'th' ? 'ดูใน Dashboard และ Transactions ได้เลย' : 'Visible in Dashboard and Transactions now.')}
            </p>

            {undoMessage &&
              <div style={{
                marginTop: 18, padding: '10px 16px', display: 'inline-block',
                background: 'var(--accent-soft)', color: 'var(--ink)',
                borderRadius: 999, fontSize: 13
              }}>{undoMessage}</div>
            }

            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 22, flexWrap: 'wrap' }}>
              {/* Undo — visible only when there IS something to undo */}
              {lastImport && lastImport.id && !undoMessage &&
                <button
                  className="btn"
                  onClick={handleUndo}
                  disabled={undoing}
                  style={{ opacity: undoing ? 0.5 : 1 }}>
                  {Ic.refresh || Ic.close}
                  {undoing ?
                    (lang === 'th' ? 'กำลังยกเลิก...' : 'Undoing…') :
                    t(I18N.undo_import, lang)}
                </button>
              }
              <button className="btn btn-accent" onClick={handleReset}>
                {Ic.check}{lang === 'th' ? 'เสร็จสิ้น' : 'Done'}
              </button>
            </div>
          </div>
        );
      })()}
    </div>);

}

// ─────────────────────────────────────────────────────────────
// AI Insights
// ─────────────────────────────────────────────────────────────
function Insights({ state, openChat, aiResult, setAiResult, analyzing, setAnalyzing }) {
  const { lang, currency } = state;

  // Auto-derive insights from the live tx list so this page stays in sync
  // with Dashboard / Transactions after a statement import. AI result
  // (when present) wins; otherwise compute from real data; otherwise demo.
  const derived = useMemo(() => deriveInsightCards(state.txs, lang), [state.txs, lang]);
  const data = aiResult || (derived && derived.items && derived.items.length > 0 ? derived : SAMPLE_INSIGHTS);

  // Rotating "analyzing" message
  const messagesTH = [
  'กำลังให้ AI วิเคราะห์การใช้เงินของคุณ…',
  'กำลังเปรียบเทียบกับเดือนก่อน…',
  'กำลังหาพฤติกรรมที่น่าสนใจ…',
  'กำลังเรียบเรียงคำแนะนำ…'];

  const messagesEN = [
  'Letting AI read your spending…',
  'Comparing with last month…',
  'Spotting interesting patterns…',
  'Crafting recommendations…'];

  const [msgIdx, setMsgIdx] = useState(0);

  useEffect(() => {
    if (!analyzing) return;
    setMsgIdx(0);
    const iv = setInterval(() => setMsgIdx((i) => (i + 1) % 4), 900);
    return () => clearInterval(iv);
  }, [analyzing]);

  const runAnalysis = async () => {
    setAnalyzing(true);
    setAiResult(null);
    // Build context for Claude
    const summary = buildSummaryForAI(state);
    const prompt = lang === 'th' ?
    `คุณคือผู้ช่วยการเงินส่วนตัวที่ชื่อ MoneyMind วิเคราะห์การใช้เงินของผู้ใช้ต่อไปนี้ แล้วตอบเป็น JSON เท่านั้นในรูปแบบ:
{
  "score": <0-100>,
  "rating": "<คำเดียว เช่น ดีมาก/ดี/ปานกลาง/ต้องระวัง>",
  "summary": "<สรุปสั้น 1-2 ประโยค ใช้ภาษาเป็นกันเอง ไม่เป็นทางการ>",
  "items": [
    {"tag": "<warn|good|info>", "tagLabel": "<ใช้เยอะ|พฤติกรรมดี|ข้อสังเกต>", "title": "<หัวข้อสั้น>", "body": "<รายละเอียด 1-2 ประโยค>", "stat": "<ตัวเลขสั้น>"}
  ]
}
ใส่ items 4-6 อัน หลากหลายทั้ง warn good info\n\nข้อมูล:\n${summary}\n\nตอบ JSON อย่างเดียว ไม่มีคำอื่น` :
    `You are MoneyMind, a friendly personal finance assistant. Analyze the user's spending below and respond ONLY in JSON:
{
  "score": <0-100>,
  "rating": "<one word: Excellent/Good/Fair/At risk>",
  "summary": "<1-2 sentences, conversational tone>",
  "items": [
    {"tag": "<warn|good|info>", "tagLabel": "<short label>", "title": "<short title>", "body": "<1-2 sentence detail>", "stat": "<short stat>"}
  ]
}
Provide 4-6 items, varied across warn/good/info.\n\nData:\n${summary}\n\nReply with JSON only.`;

    try {
      const text = await aiComplete(prompt);
      // Try to parse JSON
      const match = text.match(/\{[\s\S]*\}/);
      if (match) {
        const parsed = JSON.parse(match[0]);
        // Normalize to expected shape (single-language strings)
        const items = (parsed.items || []).map((it) => ({
          tag: it.tag || 'info',
          tagLabel: it.tagLabel || '',
          title: it.title || '',
          body: it.body || '',
          stat: it.stat || ''
        }));
        setAiResult({
          score: parsed.score || 70,
          rating: parsed.rating || '',
          summary: parsed.summary || '',
          items,
          _lang: lang,
          _isLive: true
        });
      } else {
        setAiResult(null);
      }
    } catch (e) {
      console.warn('AI parse error', e);
      setAiResult(null);
    } finally {
      setAnalyzing(false);
    }
  };

  // helper: pick string from either {th,en} object or raw string
  const pick = (v) => typeof v === 'string' ? v : t(v, lang);

  return (
    <div className="page-enter">
      <div className="topbar" style={{ marginBottom: 26 }}>
        <div>
          <div className="crumb">{t(I18N.insights_title, lang)}</div>
          <h1 className="greeting">
            {lang === 'th' ? <>AI วิเคราะห์ <em>การใช้เงิน</em></> : <>AI <em>spending</em> review</>}
          </h1>
          <p style={{ color: 'var(--ink-subtle)', fontSize: 13.5, margin: '6px 0 0' }}>{t(I18N.insights_sub, lang)}</p>
        </div>
        <div className="topbar-actions">
          <button className="btn" onClick={openChat}>{Ic.sparkles}{t(I18N.cta_chat, lang)}</button>
          <button className="btn btn-accent" onClick={runAnalysis} disabled={analyzing}>
            {Ic.sparkles}{analyzing ? lang === 'th' ? 'กำลังคิด...' : 'Thinking…' : t(I18N.cta_analyze, lang)}
          </button>
        </div>
      </div>

      {analyzing ?
      <div className="card analyzing">
          <div className="analyzing-orb"></div>
          <div className="analyzing-text">{(lang === 'th' ? messagesTH : messagesEN)[msgIdx]}</div>
          <div style={{ marginTop: 18, color: 'var(--ink-subtle)', fontSize: 12, letterSpacing: 2, textTransform: 'uppercase' }}>
            MoneyMind
          </div>
        </div> :

      <>
          {/* Score */}
          <div className="card score-card">
            <ScoreRing score={data.score} />
            <div>
              <div className="score-label">{t(I18N.health_score, lang)} · {t(I18N.this_month, lang)}</div>
              <div className="score-rating">
                {lang === 'th' ?
              <>การเงินของคุณ <em>{pick(data.rating)}</em></> :

              <>Your finances are <em>{pick(data.rating)}</em></>
              }
              </div>
              <p className="score-desc">{pick(data.summary)}</p>
              {data._isLive &&
            <div style={{ marginTop: 14 }}>
                  <span className="ai-pill"><span className="pulse"></span>{lang === 'th' ? 'สร้างโดย AI' : 'Generated by AI'}</span>
                </div>
            }
              {data._derived && !data._isLive &&
            <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
                  <span className="ai-pill"><span className="pulse"></span>{lang === 'th' ? 'จากข้อมูลของคุณ' : 'From your data'}</span>
                  <span style={{ fontSize: 11.5, color: 'var(--ink-subtle)' }}>{lang === 'th' ? 'กด “วิเคราะห์ด้วย AI” เพื่อสรุปแบบลึก' : 'Run AI for a deeper read'}</span>
                </div>
            }
            </div>
          </div>

          {/* Insight grid */}
          <div className="insight-grid">
            {data.items.map((it, i) =>
          <div key={i} className="card insight" style={{ animationDelay: `${i * 70}ms` }}>
                <div className="insight-head">
                  <span className={'insight-tag ' + it.tag}>{pick(it.tagLabel)}</span>
                </div>
                <h4>{pick(it.title)}</h4>
                <p>{pick(it.body)}</p>
                <div className="insight-stat">{pick(it.stat)}</div>
              </div>
          )}
          </div>
        </>
      }
    </div>);

}

function buildSummaryForAI(state) {
  const { txs, budget, lang } = state;
  let income = 0,expense = 0;
  const byCat = {};
  for (const t of txs) {
    if (t.amount > 0) income += t.amount;else
    {expense += -t.amount;byCat[t.category] = (byCat[t.category] || 0) + -t.amount;}
  }
  const cats = Object.entries(byCat).sort((a, b) => b[1] - a[1]).
  map(([k, v]) => `  ${(CATEGORIES[k] || {}).th || k}: ฿${Math.round(v).toLocaleString()}`).join('\n');
  return `รายรับ: ฿${income.toLocaleString()}
รายจ่าย: ฿${expense.toLocaleString()}
ยอดคงเหลือ: ฿${(income - expense).toLocaleString()}
งบประมาณ: ฿${budget.toLocaleString()}
ใช้งบไป: ${Math.round(expense / budget * 100)}%
รายจ่ายตามหมวด:
${cats}
จำนวนธุรกรรม: ${txs.length} รายการ`;
}

// ─────────────────────────────────────────────────────────────
// Chat Panel (slide-in)
// ─────────────────────────────────────────────────────────────
function ChatPanel({ state, open, onClose }) {
  const { lang } = state;
  const [messages, setMessages] = useState(() => [{
    role: 'ai',
    text: lang === 'th' ?
    'สวัสดีค่ะ ฉันคือ Mind ผู้ช่วยการเงินส่วนตัวของคุณ\nถามอะไรเรื่องเงินของคุณก็ได้นะคะ — เดือนนี้ใช้ไปกับอะไรบ้าง ออมพอไหม วางแผนยังไงดี ฉันช่วยได้ทุกคำถาม' :
    "Hi! I'm Mind, your personal finance co-pilot.\nAsk me anything about your spending — where the money goes, whether you're saving enough, or how to plan better."
  }]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bodyRef = useRef(null);

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [messages, sending]);

  const send = async (textArg) => {
    const text = (textArg ?? input).trim();
    if (!text || sending) return;
    setInput('');
    const newMessages = [...messages, { role: 'user', text }];
    setMessages(newMessages);
    setSending(true);

    const context = buildSummaryForAI(state);
    const sys = lang === 'th' ?
    `คุณคือ Mind ผู้ช่วยการเงินส่วนตัว ตอบเป็นภาษาไทยแบบเป็นกันเอง สั้นกระชับ 2-4 ประโยค ใช้ตัวเลขจริงเมื่อจำเป็น ไม่ใส่ markdown` :
    `You are Mind, a friendly personal finance co-pilot. Reply in casual English, 2-4 short sentences. Use real numbers when relevant. No markdown.`;

    const history = newMessages.map((m) => `${m.role === 'user' ? 'User' : 'Mind'}: ${m.text}`).join('\n');
    const prompt = `${sys}\n\nUser's financial data:\n${context}\n\nConversation:\n${history}\n\nMind:`;

    try {
      const reply = await aiComplete(prompt);
      setMessages((m) => [...m, { role: 'ai', text: reply.trim() }]);
    } catch (e) {
      setMessages((m) => [...m, { role: 'ai', text: lang === 'th' ? 'ขออภัย ฉันยังตอบไม่ได้ตอนนี้' : 'Sorry, I can\'t reply right now.' }]);
    } finally {
      setSending(false);
    }
  };

  const prompts = [I18N.prompt_1, I18N.prompt_2, I18N.prompt_3, I18N.prompt_4];

  return (
    <>
      <div className={'chat-overlay' + (open ? ' open' : '')} onClick={onClose}></div>
      <aside className={'chat-panel' + (open ? ' open' : '')}>
        <div className="chat-head">
          <div>
            <h3>{lang === 'th' ? 'คุยกับ Mind' : 'Chat with Mind'}</h3>
            <span className="ai-pill" style={{ marginTop: 6 }}><span className="pulse"></span>AI · Claude</span>
          </div>
          <button className="icon-btn" onClick={onClose}>{Ic.close}</button>
        </div>

        <div className="chat-body" ref={bodyRef}>
          {messages.map((m, i) =>
          <div key={i} className={'bubble ' + m.role}>{m.text}</div>
          )}
          {sending &&
          <div className="bubble ai">
              <div className="typing-dots"><span></span><span></span><span></span></div>
            </div>
          }
          {messages.length <= 1 && !sending &&
          <div className="suggested" style={{ marginTop: 14 }}>
              {prompts.map((p, i) =>
            <span key={i} className="chip" onClick={() => send(t(p, lang))}>{t(p, lang)}</span>
            )}
            </div>
          }
        </div>

        <div className="chat-foot">
          <form className="chat-input" onSubmit={(e) => {e.preventDefault();send();}}>
            <input
              placeholder={t(I18N.ask_anything, lang)}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={sending} />
            
            <button type="submit" className="send-btn" disabled={!input.trim() || sending}>{Ic.send}</button>
          </form>
        </div>
      </aside>
    </>);

}

Object.assign(window, { Dashboard, Transactions, Upload, Insights, Budgets, ChatPanel, buildSummaryForAI });

// ─────────────────────────────────────────────────────────────
// Budgets — per-category monthly spending limits
// ─────────────────────────────────────────────────────────────
function Budgets({ state, updateCatBudget, resetCatBudgets }) {
  const { txs, currency, lang, catBudgets } = state;

  // Current-month spend per category, anchored on the latest tx date
  // (so it matches the rest of the app after a statement import).
  const monthlySpend = useMemo(() => {
    if (!txs.length) return {};
    const anchor = latestAnchor(txs);
    const monthKey = anchor.toISOString().slice(0, 7); // YYYY-MM
    const spend = {};
    for (const tx of txs) {
      if (tx.amount >= 0) continue;
      if (!tx.date.startsWith(monthKey)) continue;
      const cat = tx.category || 'other';
      spend[cat] = (spend[cat] || 0) + -tx.amount;
    }
    return spend;
  }, [txs]);

  const monthLabel = useMemo(() => {
    const anchor = latestAnchor(txs);
    const monthsTh = ['มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน', 'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'];
    const monthsEn = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    const m = (lang === 'th' ? monthsTh : monthsEn)[anchor.getMonth()];
    return `${m} ${anchor.getFullYear()}`;
  }, [txs, lang]);

  const totalBudget = Object.values(catBudgets).reduce((a, b) => a + b, 0);
  const totalSpent = Object.values(monthlySpend).reduce((a, b) => a + b, 0);
  const overallPct = totalBudget > 0 ? totalSpent / totalBudget * 100 : 0;

  // Show all spending categories (exclude "income" — not a spending bucket),
  // sorted by usage % desc so alarming ones surface at the top.
  const rows = Object.keys(CATEGORIES).filter((k) => k !== 'income').map((cat) => {
    const limit = catBudgets[cat] || 0;
    const spent = monthlySpend[cat] || 0;
    const pct = limit > 0 ? spent / limit * 100 : 0;
    return { cat, limit, spent, pct };
  }).sort((a, b) => b.pct - a.pct);

  const overCount = rows.filter((r) => r.pct > 100).length;
  const warnCount = rows.filter((r) => r.pct > 80 && r.pct <= 100).length;

  return (
    <>
      <div className="topbar" style={{ marginBottom: 24 }}>
        <div>
          <div className="crumb">{t(I18N.nav.budgets, lang)} · {monthLabel}</div>
          <h1 className="greeting">
            {lang === 'th' ?
              <>ตั้งงบรายหมวด <em style={{ fontFamily: '"Instrument Serif"' }}>ของคุณ</em></> :
              <>Set your <em>category budgets</em></>
            }
          </h1>
        </div>
        <div className="topbar-actions">
          <button className="icon-btn" onClick={resetCatBudgets} title={lang === 'th' ? 'รีเซ็ตค่าเริ่มต้น' : 'Reset to defaults'}>
            {Ic.refresh || Ic.target}
          </button>
        </div>
      </div>

      {/* Summary band */}
      <div className="budget-summary card">
        <div className="budget-summary-grid">
          <div>
            <div className="budget-summary-label">{lang === 'th' ? 'งบรวมต่อเดือน' : 'Total monthly budget'}</div>
            <div className="budget-summary-value">{fmt(totalBudget, currency, lang)}</div>
          </div>
          <div>
            <div className="budget-summary-label">{lang === 'th' ? 'ใช้ไปแล้ว' : 'Spent so far'}</div>
            <div className="budget-summary-value" style={{ color: overallPct > 100 ? 'var(--negative)' : 'var(--ink)' }}>
              {fmt(totalSpent, currency, lang)}
              <span className="budget-summary-pct"> · {Math.round(overallPct)}%</span>
            </div>
          </div>
          <div>
            <div className="budget-summary-label">{lang === 'th' ? 'คงเหลือ' : 'Remaining'}</div>
            <div className="budget-summary-value" style={{ color: totalBudget - totalSpent < 0 ? 'var(--negative)' : 'var(--positive)' }}>
              {fmt(Math.max(0, totalBudget - totalSpent), currency, lang)}
            </div>
          </div>
          <div className="budget-status">
            {overCount > 0 ? (
              <div className="budget-chip over">
                {lang === 'th' ? `${overCount} หมวดเกินงบ` : `${overCount} over budget`}
              </div>
            ) : warnCount > 0 ? (
              <div className="budget-chip warn">
                {lang === 'th' ? `${warnCount} หมวดใกล้ครบ` : `${warnCount} approaching limit`}
              </div>
            ) : (
              <div className="budget-chip good">
                {lang === 'th' ? 'อยู่ในเป้าหมาย' : 'On track'}
              </div>
            )}
          </div>
        </div>
        <div className={'budget-overall-bar' + (overallPct > 100 ? ' over' : overallPct > 80 ? ' warn' : '')}>
          <span style={{ width: `${Math.min(overallPct, 100)}%` }}></span>
        </div>
      </div>

      {/* Per-category rows */}
      <div className="budget-list">
        {rows.map(({ cat, limit, spent, pct }) => {
          const catObj = CATEGORIES[cat];
          const status = pct > 100 ? 'over' : pct > 80 ? 'warn' : 'good';
          const remaining = limit - spent;
          return (
            <BudgetRow
              key={cat}
              cat={cat}
              catObj={catObj}
              limit={limit}
              spent={spent}
              pct={pct}
              status={status}
              remaining={remaining}
              currency={currency}
              lang={lang}
              onChange={(v) => updateCatBudget(cat, v)} />
          );
        })}
      </div>

      <div className="budget-foot">
        {lang === 'th' ?
          'งบจะถูกบันทึกอัตโนมัติ ระบบจะแจ้งเตือนเมื่อใช้เกิน 80% หรือเต็มงบ' :
          'Budgets save automatically. You\'ll be alerted at 80% and 100% usage.'}
      </div>
    </>
  );
}

function BudgetRow({ cat, catObj, limit, spent, pct, status, remaining, currency, lang, onChange }) {
  // Local input state so users can type freely without React clamping on every keystroke
  const [draft, setDraft] = useState(String(limit));
  useEffect(() => { setDraft(String(limit)); }, [limit]);

  const commit = () => {
    const n = parseInt(draft.replace(/[^\d]/g, ''), 10);
    if (isFinite(n)) onChange(n);
    else setDraft(String(limit));
  };

  return (
    <div className={'budget-row ' + status}>
      <div className="budget-row-head">
        <div className="budget-row-cat">
          <span className="budget-row-icon" style={{ background: catObj.color + '22', color: catObj.color }}>
            {catObj.icon}
          </span>
          <div>
            <div className="budget-row-name">{t(catObj, lang)}</div>
            <div className="budget-row-sub">
              {fmt(spent, currency, lang)} {lang === 'th' ? 'จาก' : 'of'} {fmt(limit, currency, lang)}
              <span className={'budget-row-pct ' + status}> · {Math.round(pct)}%</span>
            </div>
          </div>
        </div>
        <div className="budget-row-input">
          <span className="budget-input-prefix">{currency === 'USD' ? '$' : '฿'}</span>
          <input
            type="text"
            inputMode="numeric"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); }}
            aria-label={lang === 'th' ? `ตั้งงบ ${t(catObj, lang)}` : `${t(catObj, lang)} budget`} />
          <span className="budget-input-suffix">/{lang === 'th' ? 'เดือน' : 'mo'}</span>
        </div>
      </div>
      <div className={'budget-row-bar ' + status}>
        <span style={{ width: `${Math.min(pct, 100)}%`, background: catObj.color }}></span>
      </div>
      <div className="budget-row-meta">
        {status === 'over' ? (
          <span className="budget-row-tag over">
            {lang === 'th' ? `เกินงบ ${fmt(Math.abs(remaining), currency, lang)}` : `Over by ${fmt(Math.abs(remaining), currency, lang)}`}
          </span>
        ) : status === 'warn' ? (
          <span className="budget-row-tag warn">
            {lang === 'th' ? `เหลือ ${fmt(remaining, currency, lang)}` : `${fmt(remaining, currency, lang)} left`}
          </span>
        ) : (
          <span className="budget-row-tag good">
            {lang === 'th' ? `เหลือ ${fmt(remaining, currency, lang)}` : `${fmt(remaining, currency, lang)} left`}
          </span>
        )}
        <span className="budget-row-quick">
          {[0.75, 1, 1.5].map((mult, i) => {
            const suggested = Math.round(spent * mult / 100) * 100 || Math.round(limit * mult / 100) * 100;
            if (suggested === 0 || suggested === limit) return null;
            return (
              <button key={i} className="budget-quick-btn" onClick={() => onChange(suggested)}>
                {fmt(suggested, currency, lang)}
              </button>
            );
          })}
        </span>
      </div>
    </div>
  );
}
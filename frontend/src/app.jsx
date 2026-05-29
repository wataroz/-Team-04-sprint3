/* ============================================================
   MoneyMind — Main App
   Composes sidebar, view router, tweaks panel.
   ============================================================ */

const { useState, useEffect, useMemo, useRef } = React;

// Default monthly limits per category (sensible Thai household defaults).
// User can edit these on the Budgets page; choice persists to localStorage.
const DEFAULT_CATEGORY_BUDGETS = {
  food: 8000,
  transport: 3000,
  shopping: 4000,
  home: 6000,
  entertain: 2000,
  groceries: 3500,
  health: 1500,
  other: 2000,
};

function loadCategoryBudgets() {
  try {
    const raw = localStorage.getItem('mm_cat_budgets');
    if (!raw) return { ...DEFAULT_CATEGORY_BUDGETS };
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_CATEGORY_BUDGETS, ...parsed };
  } catch (e) {
    return { ...DEFAULT_CATEGORY_BUDGETS };
  }
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#C9B68A",
  "lang": "th",
  "currency": "THB",
  "density": "regular",
  "showAmbient": true
} /*EDITMODE-END*/;

// Accent presets — fewer colors = more luxe.
const ACCENT_OPTIONS = [
'#C9B68A', // Champagne (default)
'#88D4A4', // Mint sage
'#B6A4D8', // Soft lilac
'#E5A55C' // Warm amber
];

function App() {
  const [tw, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // ─── Auth state ───
  const [user, setUser] = useState(null); // null = logged out
  const [authView, setAuthView] = useState('login'); // 'login' | 'register' | 'forgot'

  // ─── App state ───
  const [view, setView] = useState('overview');
  const [txs, setTxs] = useState(() => []);
  const [chatOpen, setChatOpen] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifs, setNotifs] = useState(() => []);
  const [catBudgets, setCatBudgets] = useState(() => loadCategoryBudgets());
  const [pendingImport, setPendingImport] = useState(null); // {filename, bank, count} from /api/parse-pdf
  // Last successful import — used to power the "Undo last import" UX.
  // {id, filename, bank, created, skipped} | null
  const [lastImport, setLastImport] = useState(null);
  // Reset Statement (Day 4) — destructive action with confirm modal
  const [resetOpen, setResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetMessage, setResetMessage] = useState('');
  const notifRef = useRef(null);

  // ─── Load persisted data from backend when the user logs in ───
  useEffect(() => {
    if (!user || !user.id) return;
    fetch('/api/transactions?user_id=' + user.id)
      .then((r) => r.ok ? r.json() : [])
      .then((rows) => setTxs(Array.isArray(rows) ? rows : []))
      .catch(() => {});
    fetch('/api/notifications?user_id=' + user.id)
      .then((r) => r.ok ? r.json() : [])
      .then((rows) => setNotifs(Array.isArray(rows) ? rows : []))
      .catch(() => {});
    fetch('/api/preferences/' + user.id)
      .then((r) => r.ok ? r.json() : null)
      .then((p) => {
        if (!p) return;
        if (p.accent) setTweak('accent', p.accent);
        if (p.density) setTweak('density', p.density);
        if (p.lang) setTweak('lang', p.lang);
        if (p.currency) setTweak('currency', p.currency);
        if (typeof p.showAmbient === 'boolean') setTweak('showAmbient', p.showAmbient);
        if (p.categoryBudgets && Object.keys(p.categoryBudgets).length) {
          setCatBudgets({ ...DEFAULT_CATEGORY_BUDGETS, ...p.categoryBudgets });
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user && user.id]);

  // Persist category budgets (localStorage as offline fallback + backend if logged in)
  useEffect(() => {
    try { localStorage.setItem('mm_cat_budgets', JSON.stringify(catBudgets)); } catch (e) {}
    if (!user || !user.id) return;
    const t = setTimeout(() => {
      fetch('/api/preferences/' + user.id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ categoryBudgets: catBudgets }),
      }).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catBudgets, user && user.id]);

  // Persist tweaks (accent/density/lang/currency/showAmbient) to backend, debounced.
  useEffect(() => {
    if (!user || !user.id) return;
    const t = setTimeout(() => {
      fetch('/api/preferences/' + user.id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          accent: tw.accent,
          density: tw.density,
          lang: tw.lang,
          currency: tw.currency,
          showAmbient: !!tw.showAmbient,
        }),
      }).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tw.accent, tw.density, tw.lang, tw.currency, tw.showAmbient, user && user.id]);

  const updateCatBudget = (cat, val) => {
    setCatBudgets((prev) => ({ ...prev, [cat]: Math.max(0, Math.round(val)) }));
  };
  const resetCatBudgets = () => setCatBudgets({ ...DEFAULT_CATEGORY_BUDGETS });

  // Close notif dropdown on outside click / escape
  useEffect(() => {
    if (!notifOpen) return;
    const onClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false);
    };
    const onKey = (e) => {if (e.key === 'Escape') setNotifOpen(false);};
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [notifOpen]);

  const lang = tw.lang || 'th';
  const currency = tw.currency || 'THB';
  const budget = 25000;

  // ─── Auth handlers ───
  const handleLogin = (u) => {
    setUser(u);
    setView('overview');
  };

  const handleLogout = () => {
    setUser(null);
    setAuthView('login');
    setChatOpen(false);
    setNotifOpen(false);
    setTxs([]);
    setNotifs([]);
    setAiResult(null);
  };

  // ─── Update CSS vars when accent changes ───
  useEffect(() => {
    const root = document.documentElement;
    const accent = tw.accent || '#C9B68A';
    root.style.setProperty('--accent', accent);
    // Compute soft & glow tints
    root.style.setProperty('--accent-soft', hexToRgba(accent, 0.12));
    root.style.setProperty('--accent-glow', hexToRgba(accent, 0.35));
  }, [tw.accent]);

  // Density adjustments
  useEffect(() => {
    const root = document.documentElement;
    if (tw.density === 'compact') {
      root.style.setProperty('--radius', '14px');
      root.style.setProperty('--radius-lg', '18px');
    } else {
      root.style.removeProperty('--radius');
      root.style.removeProperty('--radius-lg');
    }
  }, [tw.density]);

  // Ambient gradients toggle
  useEffect(() => {
    document.body.style.setProperty('--_ambient', tw.showAmbient ? 1 : 0);
    const before = document.body;
    if (!tw.showAmbient) {
      before.classList.add('no-ambient');
    } else {
      before.classList.remove('no-ambient');
    }
  }, [tw.showAmbient]);

  const addTxs = async (newTxs) => {
    if (!user || !user.id) {
      // Fallback: not logged in (shouldn't happen) — just keep in-memory.
      setTxs((prev) => [...newTxs, ...prev]);
      return { created: newTxs.length, skipped: 0, importId: null };
    }
    const count = newTxs.length;
    let importId = null;
    let importMeta = null;
    let created = count;
    let skipped = 0;
    try {
      // 1) Record an Import row if we know which file this came from
      if (pendingImport) {
        importMeta = { filename: pendingImport.filename || '', bank: pendingImport.bank || 'unknown' };
        const r = await fetch('/api/imports', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: user.id,
            filename: importMeta.filename,
            bank: importMeta.bank,
            count,
          }),
        });
        if (r.ok) {
          const imp = await r.json();
          importId = imp.id;
        }
        setPendingImport(null);
      }

      // 2) Persist transactions — backend now returns {created, skipped}
      //    (dedup ทำที่ฝั่ง backend หลัง AJ แก้ Sprint 3 Day 4)
      const txRes = await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id, import_id: importId, transactions: newTxs }),
      });
      if (txRes.ok) {
        const j = await txRes.json().catch(() => ({}));
        if (typeof j.created === 'number') created = j.created;
        if (typeof j.skipped === 'number') skipped = j.skipped;
      }

      // 3) Reload txs from backend so we have real IDs / canonical order
      const r2 = await fetch('/api/transactions?user_id=' + user.id);
      if (r2.ok) setTxs(await r2.json());

      // 4) Stale AI summary
      setAiResult(null);

      // 5) Surface a notification (only if something actually landed)
      if (created > 0) {
        const title = skipped > 0 ?
          { th: `นำเข้า ${created.toLocaleString()} รายการ · ข้ามซ้ำ ${skipped.toLocaleString()}`, en: `Imported ${created.toLocaleString()} · skipped ${skipped.toLocaleString()} duplicates` } :
          { th: `นำเข้า ${created.toLocaleString()} รายการสำเร็จ`, en: `Imported ${created.toLocaleString()} transactions` };
        const desc = { th: 'Dashboard และ AI Insights อัปเดตตามข้อมูลใหม่แล้ว', en: 'Dashboard and AI Insights now reflect the new data.' };
        await fetch('/api/notifications', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: user.id, type: 'good', icon: 'check', title, desc, unread: true }),
        });
        const r3 = await fetch('/api/notifications?user_id=' + user.id);
        if (r3.ok) setNotifs(await r3.json());
      }

      // 6) Record the last import so the user can Undo it
      if (importId) {
        setLastImport({
          id: importId,
          filename: importMeta ? importMeta.filename : '',
          bank: importMeta ? importMeta.bank : '',
          created,
          skipped,
        });
      }

      return { created, skipped, importId };
    } catch (err) {
      console.error('[addTxs] persist failed', err);
      // Still update local state so the user sees something
      setTxs((prev) => [...newTxs, ...prev]);
      return { created: count, skipped: 0, importId, error: true };
    }
  };

  // Delete the most recent Import (and its transactions) — powers "Undo".
  // Returns {ok, removed} so the caller can show a confirmation message.
  const deleteLastImport = async () => {
    if (!user || !user.id || !lastImport || !lastImport.id) {
      return { ok: false, removed: 0 };
    }
    try {
      const res = await fetch(`/api/imports/${lastImport.id}?user_id=${user.id}`, {
        method: 'DELETE',
      });
      if (!res.ok) return { ok: false, removed: 0 };
      const j = await res.json().catch(() => ({}));
      const removed = typeof j.removed_txs === 'number' ? j.removed_txs : 0;
      // Refresh tx list so Dashboard / Transactions reflect the rollback
      const r2 = await fetch('/api/transactions?user_id=' + user.id);
      if (r2.ok) setTxs(await r2.json());
      setAiResult(null);
      setLastImport(null);
      return { ok: true, removed };
    } catch (err) {
      console.error('[deleteLastImport] failed', err);
      return { ok: false, removed: 0 };
    }
  };

  // ─── Reset Statement (Day 4) ───
  // Calls AJ's POST /api/reset?user_id=<id> → wipes txs, imports, notifications.
  // Keeps: user account, preferences (incl. category budgets), LINE link.
  const handleReset = async () => {
    if (!user || !user.id || resetting) return;
    setResetting(true);
    try {
      const res = await fetch(`/api/reset?user_id=${user.id}`, { method: 'POST' });
      if (!res.ok) throw new Error('reset request failed');
      const j = await res.json().catch(() => ({}));
      const dTxs = typeof j.deleted_txs === 'number' ? j.deleted_txs : 0;
      const dImp = typeof j.deleted_imports === 'number' ? j.deleted_imports : 0;
      const dNot = typeof j.deleted_notifications === 'number' ? j.deleted_notifications : 0;
      // Clear local state so Dashboard / lists go empty instantly
      setTxs([]);
      setNotifs([]);
      setLastImport(null);
      setAiResult(null);
      setPendingImport(null);
      const tt = (lang === 'th' ? 'th-TH' : 'en-US');
      const msg = t(I18N.reset_success, lang)
        .replace('{n}', dTxs.toLocaleString(tt))
        .replace('{m}', dImp.toLocaleString(tt))
        .replace('{k}', dNot.toLocaleString(tt));
      setResetMessage(msg);
      setTimeout(() => setResetMessage(''), 4500);
      setResetOpen(false);
    } catch (err) {
      console.error('[handleReset] failed', err);
      setResetMessage(t(I18N.reset_failed, lang));
      setTimeout(() => setResetMessage(''), 4500);
    } finally {
      setResetting(false);
    }
  };

  const state = { txs, currency, lang, budget, catBudgets };

  // ─── Not logged in ─ show auth screens ───
  if (!user) {
    let authEl;
    if (authView === 'register') {
      authEl = <Register lang={lang} onLogin={handleLogin} goLogin={() => setAuthView('login')} />;
    } else if (authView === 'forgot') {
      authEl = <Forgot lang={lang} goLogin={() => setAuthView('login')} />;
    } else {
      authEl =
      <Login
        lang={lang}
        onLogin={handleLogin}
        goRegister={() => setAuthView('register')}
        goForgot={() => setAuthView('forgot')} />;


    }
    return (
      <>
        {authEl}
        <TweaksPanel title="Tweaks">
          <TweakSection label={lang === 'th' ? 'ลักษณะ' : 'Appearance'} />
          <TweakColor
            label={lang === 'th' ? 'สีเน้น' : 'Accent'}
            value={tw.accent}
            options={ACCENT_OPTIONS}
            onChange={(v) => setTweak('accent', v)} />
          
          <TweakSection label={lang === 'th' ? 'ภาษา' : 'Locale'} />
          <TweakRadio
            label={lang === 'th' ? 'ภาษา' : 'Language'}
            value={tw.lang}
            options={['th', 'en']}
            onChange={(v) => setTweak('lang', v)} />
          
        </TweaksPanel>
      </>);

  }

  const hour = new Date().getHours();
  const greetKey = hour < 12 ? 'greeting_morn' : hour < 17 ? 'greeting_noon' : 'greeting_eve';

  const viewTitles = {
    overview: lang === 'th' ? { crumb: 'ภาพรวม · พฤษภาคม 2026', heading: <>{t(I18N[greetKey], lang)} <em style={{ fontFamily: "\"Instrument Serif\"" }}>{user.name}</em></> } :
    { crumb: 'Overview · May 2026', heading: <>{t(I18N[greetKey], lang)} <em>{user.name}</em></> }
  };

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" dangerouslySetInnerHTML={{ __html: BRAND_GLYPH }}></div>
          <div>
            <div className="brand-name">MoneyMind</div>
            <div className="brand-sub">{t(I18N.brand_sub, lang)}</div>
          </div>
        </div>

        <div className="nav-section-label">{lang === 'th' ? 'หลัก' : 'Main'}</div>
        <div className={'nav-item' + (view === 'overview' ? ' active' : '')} onClick={() => setView('overview')}>
          {Ic.home}{t(I18N.nav.overview, lang)}
        </div>
        <div className={'nav-item' + (view === 'transactions' ? ' active' : '')} onClick={() => setView('transactions')}>
          {Ic.list}{t(I18N.nav.transactions, lang)}
        </div>
        <div className={'nav-item' + (view === 'upload' ? ' active' : '')} onClick={() => setView('upload')}>
          {Ic.upload}{t(I18N.nav.upload, lang)}
        </div>
        <div className={'nav-item' + (view === 'budgets' ? ' active' : '')} onClick={() => setView('budgets')}>
          {Ic.target}{t(I18N.nav.budgets, lang)}
        </div>

        <div className="nav-section-label">{lang === 'th' ? 'อัจฉริยะ' : 'Intelligence'}</div>
        <div className={'nav-item' + (view === 'insights' ? ' active' : '')} onClick={() => setView('insights')}>
          {Ic.spark}{t(I18N.nav.insights, lang)}
          <span className="nav-badge">3</span>
        </div>
        <div className="nav-item" onClick={() => setChatOpen(true)}>
          {Ic.sparkles}{lang === 'th' ? 'คุยกับ Mind' : 'Chat with Mind'}
        </div>

        <div className="sidebar-footer">
          <div className="avatar">{(user.name || 'P').charAt(0).toUpperCase()}</div>
          <div>
            <div className="user-name">{user.name || t(I18N.user_name, lang)}</div>
            <div className="user-meta">{user.email || t(I18N.user_role, lang)}</div>
          </div>
          <button
            className="icon-btn"
            style={{ marginLeft: 'auto', width: 32, height: 32, borderRadius: 10 }}
            onClick={handleLogout}
            title={lang === 'th' ? 'ออกจากระบบ' : 'Sign out'}>
            
            {Ic.logout}
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="main" style={{ fontWeight: "400" }}>
        {view === 'overview' &&
        <>
            <div className="topbar">
              <div>
                <div className="crumb">{viewTitles.overview.crumb}</div>
                <h1 className="greeting">{viewTitles.overview.heading}</h1>
              </div>
              <div className="topbar-actions">
                <button
                  className="icon-btn"
                  onClick={() => setResetOpen(true)}
                  title={t(I18N.reset_btn, lang)}
                  disabled={resetting || !txs.length}
                  style={{ opacity: resetting || !txs.length ? 0.45 : 1 }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2m2 0v12a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V7M10 11v6M14 11v6" />
                  </svg>
                </button>
                <button className="icon-btn" onClick={() => setChatOpen(true)} title={t(I18N.cta_chat, lang)}>{Ic.sparkles}</button>
                <div className="notif-anchor" ref={notifRef}>
                  <button className="icon-btn" onClick={() => setNotifOpen((o) => !o)} title={lang === 'th' ? 'การแจ้งเตือน' : 'Notifications'}>
                    {notifs.some((n) => n.unread) && <span className="dot"></span>}
                    {Ic.bell}
                  </button>
                  {notifOpen &&
                <NotifDropdown
                  notifs={notifs}
                  lang={lang}
                  onMarkAll={() => {
                    setNotifs((n) => n.map((x) => ({ ...x, unread: false })));
                    if (user && user.id) {
                      fetch('/api/notifications/mark-read', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: user.id }),
                      }).catch(() => {});
                    }
                  }}
                  onClickItem={(i) => {
                    setNotifs((n) => n.map((x, j) => j === i ? { ...x, unread: false } : x));
                  }}
                  onSeeAll={() => {setNotifOpen(false);setView('insights');}} />

                }
                </div>
                <button className="btn btn-accent" onClick={() => setView('upload')}>{Ic.upload}{lang === 'th' ? 'นำเข้า' : 'Import'}</button>
              </div>
            </div>
            <Dashboard state={state} setView={setView} openChat={() => setChatOpen(true)} />
          </>
        }
        {view === 'transactions' && <Transactions state={state} addTxs={addTxs} />}
        {view === 'upload' && <Upload state={state} addTxs={addTxs} setPendingImport={setPendingImport} lastImport={lastImport} deleteLastImport={deleteLastImport} />}
        {view === 'budgets' && <Budgets state={state} updateCatBudget={updateCatBudget} resetCatBudgets={resetCatBudgets} />}
        {view === 'insights' &&
        <Insights
          state={state}
          openChat={() => setChatOpen(true)}
          aiResult={aiResult}
          setAiResult={setAiResult}
          analyzing={analyzing}
          setAnalyzing={setAnalyzing} />

        }
      </main>

      {/* Chat */}
      <ChatPanel state={state} open={chatOpen} onClose={() => setChatOpen(false)} />

      {/* Tweaks */}
      <TweaksPanel title="Tweaks">
        <TweakSection label={lang === 'th' ? 'ลักษณะ' : 'Appearance'} />
        <TweakColor
          label={lang === 'th' ? 'สีเน้น' : 'Accent'}
          value={tw.accent}
          options={ACCENT_OPTIONS}
          onChange={(v) => setTweak('accent', v)} />
        
        <TweakRadio
          label={lang === 'th' ? 'ความหนาแน่น' : 'Density'}
          value={tw.density}
          options={['regular', 'compact']}
          onChange={(v) => setTweak('density', v)} />
        
        <TweakToggle
          label={lang === 'th' ? 'แสงพื้นหลัง' : 'Ambient glow'}
          value={tw.showAmbient}
          onChange={(v) => setTweak('showAmbient', v)} />
        

        <TweakSection label={lang === 'th' ? 'ภาษาและสกุลเงิน' : 'Locale'} />
        <TweakRadio
          label={lang === 'th' ? 'ภาษา' : 'Language'}
          value={tw.lang}
          options={['th', 'en']}
          onChange={(v) => setTweak('lang', v)} />
        
        <TweakRadio
          label={lang === 'th' ? 'สกุลเงิน' : 'Currency'}
          value={tw.currency}
          options={['THB', 'USD']}
          onChange={(v) => setTweak('currency', v)} />
        

        <TweakSection label="AI" />
        <TweakButton onClick={() => {setView('insights');}}>
          {lang === 'th' ? 'ไปหน้า AI Insights' : 'Go to AI Insights'}
        </TweakButton>
        <TweakButton onClick={() => setChatOpen(true)}>
          {lang === 'th' ? 'เปิด Chat กับ Mind' : 'Open Mind chat'}
        </TweakButton>
      </TweaksPanel>

      {/* Reset Statement confirm modal */}
      {resetOpen &&
        <ResetModal
          lang={lang}
          resetting={resetting}
          onClose={() => { if (!resetting) setResetOpen(false); }}
          onConfirm={handleReset} />
      }

      {/* Reset toast (post-action feedback) */}
      {resetMessage &&
        <div
          role="status"
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 250,
            background: '#111114',
            border: '1px solid var(--border-strong)',
            borderRadius: 14,
            padding: '12px 18px',
            color: 'var(--ink)',
            fontSize: 13,
            maxWidth: 380,
            boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
            animation: 'fadeIn 240ms ease-out',
          }}>
          {resetMessage}
        </div>
      }
    </div>);

}

// Convert #RRGGBB → rgba()
function hexToRgba(hex, alpha) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// ─────────────────────────────────────────────────────────────
// NotifDropdown — opens from the bell button
// ─────────────────────────────────────────────────────────────
function NotifDropdown({ notifs, lang, onMarkAll, onClickItem, onSeeAll }) {
  const unreadCount = notifs.filter((n) => n.unread).length;
  // Map icon name → SVG from Ic
  const iconFor = (name) => Ic[name] || Ic.bell;

  return (
    <div className="notif-dropdown">
      <div className="notif-head">
        <div>
          <h4>{lang === 'th' ? 'การแจ้งเตือน' : 'Notifications'}</h4>
          {unreadCount > 0 &&
          <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 2, letterSpacing: 0.3 }}>
              {lang === 'th' ? `${unreadCount} รายการใหม่` : `${unreadCount} new`}
            </div>
          }
        </div>
        {unreadCount > 0 &&
        <span className="notif-mark" onClick={onMarkAll}>
            {lang === 'th' ? 'อ่านแล้วทั้งหมด' : 'Mark all read'}
          </span>
        }
      </div>

      <div className="notif-body">
        {notifs.length === 0 ?
        <div className="notif-empty">
            {lang === 'th' ? 'ยังไม่มีการแจ้งเตือน' : 'No notifications yet'}
          </div> :
        notifs.map((n, i) =>
        <div
          key={i}
          className={'notif-item' + (n.unread ? ' unread' : '')}
          onClick={() => onClickItem(i)}>
          
            <div className={'notif-icon ' + n.type}>{iconFor(n.icon)}</div>
            <div>
              <div className="notif-title">{t(n.title, lang)}</div>
              <div className="notif-desc">{t(n.desc, lang)}</div>
            </div>
            <div className="notif-time">{t(n.time, lang)}</div>
          </div>
        )}
      </div>

      <div className="notif-foot" onClick={onSeeAll}>
        {lang === 'th' ? 'ดูทั้งหมดใน AI Insights' : 'View all in AI Insights'}
      </div>
    </div>);

}

// ─────────────────────────────────────────────────────────────
// ResetModal — destructive confirm dialog for "Reset Statement"
// Lists exactly what will be deleted vs. kept, plus an undo warning.
// ─────────────────────────────────────────────────────────────
function ResetModal({ lang, onClose, onConfirm, resetting }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !resetting) onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose, resetting]);

  const itemStyle = {
    display: 'flex',
    alignItems: 'center',
    padding: '5px 0',
    color: 'var(--ink-muted)',
    fontSize: 13.5,
    lineHeight: 1.45,
  };
  const dot = (tone) => (
    <span style={{
      display: 'inline-block',
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: tone === 'danger' ? 'var(--negative)' : '#88D4A4',
      marginRight: 12,
      flexShrink: 0,
    }} />
  );

  return (
    <div className="modal-overlay" onClick={resetting ? undefined : onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <div className="modal-head">
          <h3>{t(I18N.reset_title, lang)}</h3>
          {!resetting &&
            <button className="icon-btn" onClick={onClose}>{Ic.close}</button>
          }
        </div>
        <div className="modal-body">
          <p style={{ margin: 0, color: 'var(--ink-muted)', fontSize: 14, lineHeight: 1.55 }}>
            {t(I18N.reset_lead, lang)}
          </p>

          <div className="field">
            <label className="field-label" style={{ color: 'var(--negative)' }}>
              {t(I18N.reset_will_delete, lang)}
            </label>
            <div>
              <div style={itemStyle}>{dot('danger')}{t(I18N.reset_d_txs, lang)}</div>
              <div style={itemStyle}>{dot('danger')}{t(I18N.reset_d_imports, lang)}</div>
              <div style={itemStyle}>{dot('danger')}{t(I18N.reset_d_notifs, lang)}</div>
            </div>
          </div>

          <div className="field">
            <label className="field-label">{t(I18N.reset_will_keep, lang)}</label>
            <div>
              <div style={itemStyle}>{dot('good')}{t(I18N.reset_k_budgets, lang)}</div>
              <div style={itemStyle}>{dot('good')}{t(I18N.reset_k_account, lang)}</div>
              <div style={itemStyle}>{dot('good')}{t(I18N.reset_k_line, lang)}</div>
            </div>
          </div>

          <div style={{
            padding: '10px 14px',
            borderRadius: 10,
            background: 'var(--negative-soft)',
            border: '1px solid color-mix(in oklab, var(--negative) 30%, transparent)',
            color: 'var(--negative)',
            fontSize: 12.5,
            letterSpacing: 0.3,
          }}>
            {t(I18N.reset_warning, lang)}
          </div>
        </div>
        <div className="modal-foot">
          <button
            className="btn"
            onClick={onClose}
            disabled={resetting}
            style={{ opacity: resetting ? 0.5 : 1 }}>
            {t(I18N.reset_cancel, lang)}
          </button>
          <button
            className="btn"
            onClick={onConfirm}
            disabled={resetting}
            style={{
              background: 'var(--negative)',
              color: '#1a1010',
              border: '1px solid var(--negative)',
              fontWeight: 600,
              opacity: resetting ? 0.7 : 1,
            }}>
            {resetting ? t(I18N.reset_doing, lang) : t(I18N.reset_confirm, lang)}
          </button>
        </div>
      </div>
    </div>);

}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
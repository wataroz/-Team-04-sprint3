/* ============================================================
   MoneyMind — Auth screens (Login + Register)
   Split layout: left = brand/quote, right = form
   ============================================================ */

const { useState: useStateA } = React;

// ─────────────────────────────────────────────────────────────
// Auth Hero (left panel — shared between Login + Register)
// ─────────────────────────────────────────────────────────────
function AuthHero({ lang }) {
  const features = lang === 'th' ? [
    'นำเข้า Statement จากธนาคารอัตโนมัติ',
    'AI วิเคราะห์พฤติกรรมการใช้เงิน',
    'แจ้งเตือนเมื่อใช้เงินผิดปกติ',
  ] : [
    'Auto-import statements from any bank',
    'AI understands your spending behaviour',
    'Smart alerts on unusual spending',
  ];

  return (
    <div className="auth-hero">
      <div className="auth-brand">
        <div className="brand-mark" dangerouslySetInnerHTML={{ __html: BRAND_GLYPH }}></div>
        <div>
          <div className="auth-brand-name">MoneyMind</div>
          <div className="auth-brand-sub">{t(I18N.brand_sub, lang)}</div>
        </div>
      </div>

      <div className="auth-quote">
        <div className="auth-quote-mark">"</div>
        <h1 className="auth-quote-text">
          {lang === 'th' ? (
            <>เงินของคุณ <em>เล่าเรื่อง</em> ของมันเอง — เราแค่ช่วย <em>ฟัง</em></>
          ) : (
            <>Your money <em>tells</em> its own story — we just help you <em>listen</em>.</>
          )}
        </h1>
        <div className="auth-quote-author">— MoneyMind · est. 2026</div>
      </div>

      <div className="auth-features">
        {features.map((f, i) => (
          <div key={i} className="auth-feat">
            <div className="auth-feat-dot">{Ic.check}</div>
            <span>{f}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Login
// ─────────────────────────────────────────────────────────────
function Login({ lang, onLogin, goRegister, goForgot }) {
  const [email, setEmail] = useStateA('demo@moneymind.app');
  const [password, setPassword] = useStateA('demo1234');
  const [remember, setRemember] = useStateA(true);
  const [showPw, setShowPw] = useStateA(false);
  const [error, setError] = useStateA('');
  const [busy, setBusy] = useStateA(false);
  const [socialBusy, setSocialBusy] = useStateA(null); // 'google' | 'apple' | null

  const submit = (e) => {
    e.preventDefault();
    setError('');
    if (!email.trim() || !password) {
      setError(lang === 'th' ? 'กรุณากรอกอีเมลและรหัสผ่าน' : 'Please enter email and password');
      return;
    }
    setBusy(true);
    const name = email.split('@')[0] || 'User';
    const displayName = name.charAt(0).toUpperCase() + name.slice(1);
    fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), name: displayName }),
    })
      .then((r) => r.ok ? r.json() : r.json().then((e) => Promise.reject(e)))
      .then((u) => onLogin(u))
      .catch((err) => {
        setError((lang === 'th' ? 'เข้าสู่ระบบไม่สำเร็จ — ' : 'Login failed — ') + (err.error || 'server error'));
        setBusy(false);
      });
  };

  const social = (provider) => {
    if (busy || socialBusy) return;
    setSocialBusy(provider);
    const u = provider === 'google'
      ? { email: 'you@gmail.com',  name: 'Google User' }
      : { email: 'you@icloud.com', name: 'Apple User' };
    fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(u),
    })
      .then((r) => r.json())
      .then((row) => onLogin(row))
      .catch(() => setSocialBusy(null));
  };

  return (
    <div className="auth-shell">
      <AuthHero lang={lang} />

      <div className="auth-form-wrap">
        <form className="auth-form" onSubmit={submit}>
          <div className="auth-form-head">
            <div className="crumb">{lang === 'th' ? 'ยินดีต้อนรับกลับ' : 'Welcome back'}</div>
            <h2>{lang === 'th' ? <>เข้าสู่ <em>บัญชี</em> ของคุณ</> : <>Sign in to <em>MoneyMind</em></>}</h2>
            <p>{lang === 'th' ? 'ใช้บัญชีที่มีอยู่หรือสร้างใหม่ก็ได้' : 'Use your existing account or create a new one.'}</p>
          </div>

          {error && <div className="auth-error">{error}</div>}

          <div className="auth-fields">
            <div className="field">
              <label className="field-label">{lang === 'th' ? 'อีเมล' : 'Email'}</label>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-subtle)' }}>{Ic.mail}</span>
                <input
                  className="field-input"
                  type="email"
                  placeholder="you@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{ paddingLeft: 44 }}
                  autoFocus
                />
              </div>
            </div>

            <div className="field">
              <label className="field-label">{lang === 'th' ? 'รหัสผ่าน' : 'Password'}</label>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-subtle)' }}>{Ic.lock}</span>
                <input
                  className="field-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder={lang === 'th' ? 'รหัสผ่าน' : 'Your password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{ paddingLeft: 44, paddingRight: 44 }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    background: 'transparent', border: 0, color: 'var(--ink-subtle)', cursor: 'pointer',
                    padding: 6, borderRadius: 6,
                  }}
                  title={showPw ? 'Hide' : 'Show'}
                >
                  {showPw ? Ic.eyeOff : Ic.eye}
                </button>
              </div>
            </div>
          </div>

          <div className="auth-row">
            <label className="auth-check">
              <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
              {lang === 'th' ? 'จดจำการเข้าสู่ระบบ' : 'Remember me'}
            </label>
            <span className="auth-link" onClick={goForgot}>{lang === 'th' ? 'ลืมรหัสผ่าน?' : 'Forgot password?'}</span>
          </div>

          <button type="submit" className="btn btn-accent auth-submit" disabled={busy}>
            {busy
              ? (lang === 'th' ? 'กำลังเข้าสู่ระบบ...' : 'Signing in…')
              : (lang === 'th' ? 'เข้าสู่ระบบ' : 'Sign in')}
            {!busy && Ic.arrow}
          </button>

          <div className="auth-divider">{lang === 'th' ? 'หรือเข้าด้วย' : 'or continue with'}</div>

          <div className="auth-social">
            <button type="button" className="btn" onClick={() => social('google')} disabled={busy || socialBusy}>
              <span style={{ width: 16, height: 16, display: 'inline-block' }}>
                {socialBusy === 'google' ? <Spinner /> : Ic.google}
              </span>
              {socialBusy === 'google' ? (lang === 'th' ? 'กำลังเข้า...' : 'Connecting…') : 'Google'}
            </button>
            <button type="button" className="btn" onClick={() => social('apple')} disabled={busy || socialBusy}>
              <span style={{ width: 16, height: 16, display: 'inline-block' }}>
                {socialBusy === 'apple' ? <Spinner /> : Ic.apple}
              </span>
              {socialBusy === 'apple' ? (lang === 'th' ? 'กำลังเข้า...' : 'Connecting…') : 'Apple'}
            </button>
          </div>

          <div className="auth-foot">
            {lang === 'th' ? 'ยังไม่มีบัญชี? ' : "Don't have an account? "}
            <span className="auth-link" onClick={goRegister}>
              {lang === 'th' ? 'สร้างบัญชีใหม่' : 'Create account'} →
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Register
// ─────────────────────────────────────────────────────────────
function Register({ lang, onLogin, goLogin }) {
  const [name, setName] = useStateA('');
  const [email, setEmail] = useStateA('');
  const [password, setPassword] = useStateA('');
  const [agree, setAgree] = useStateA(false);
  const [showPw, setShowPw] = useStateA(false);
  const [error, setError] = useStateA('');
  const [busy, setBusy] = useStateA(false);

  // Password strength meter
  const strength = (() => {
    let s = 0;
    if (password.length >= 8) s++;
    if (/[A-Z]/.test(password)) s++;
    if (/\d/.test(password)) s++;
    if (/[^a-zA-Z0-9]/.test(password)) s++;
    return s;
  })();

  const strengthLabel = lang === 'th'
    ? ['อ่อนเกินไป', 'พอใช้', 'ดี', 'แข็งแกร่ง', 'แข็งแกร่งมาก']
    : ['Too weak', 'Fair', 'Good', 'Strong', 'Excellent'];

  const strengthClass = strength <= 1 ? 'weak' : strength <= 2 ? 'med' : 'strong';

  const submit = (e) => {
    e.preventDefault();
    setError('');
    if (!name.trim() || !email.trim() || !password) {
      setError(lang === 'th' ? 'กรุณากรอกข้อมูลให้ครบ' : 'Please fill in all fields');
      return;
    }
    if (password.length < 8) {
      setError(lang === 'th' ? 'รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร' : 'Password must be at least 8 characters');
      return;
    }
    if (!agree) {
      setError(lang === 'th' ? 'กรุณายอมรับข้อตกลงการใช้งาน' : 'Please agree to the terms');
      return;
    }
    setBusy(true);
    fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), name: name.trim() }),
    })
      .then((r) => r.ok ? r.json() : r.json().then((e) => Promise.reject(e)))
      .then((u) => onLogin(u))
      .catch((err) => {
        setError((lang === 'th' ? 'สมัครไม่สำเร็จ — ' : 'Register failed — ') + (err.error || 'server error'));
        setBusy(false);
      });
  };

  return (
    <div className="auth-shell">
      <AuthHero lang={lang} />

      <div className="auth-form-wrap">
        <form className="auth-form" onSubmit={submit}>
          <div className="auth-form-head">
            <div className="crumb">{lang === 'th' ? 'เริ่มต้นใช้งาน' : 'Get started'}</div>
            <h2>{lang === 'th' ? <>สร้าง <em>บัญชี</em> ใหม่</> : <>Create your <em>account</em></>}</h2>
            <p>{lang === 'th' ? 'ใช้ฟรี ไม่มีบัตรเครดิต ใช้เวลาแค่ 1 นาที' : 'Free forever. No credit card. 60 seconds.'}</p>
          </div>

          {error && <div className="auth-error">{error}</div>}

          <div className="auth-fields">
            <div className="field">
              <label className="field-label">{lang === 'th' ? 'ชื่อ' : 'Full name'}</label>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-subtle)' }}>{Ic.user}</span>
                <input
                  className="field-input"
                  placeholder={lang === 'th' ? 'ชื่อ-นามสกุล' : 'Your name'}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  style={{ paddingLeft: 44 }}
                  autoFocus
                />
              </div>
            </div>

            <div className="field">
              <label className="field-label">{lang === 'th' ? 'อีเมล' : 'Email'}</label>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-subtle)' }}>{Ic.mail}</span>
                <input
                  className="field-input"
                  type="email"
                  placeholder="you@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{ paddingLeft: 44 }}
                />
              </div>
            </div>

            <div className="field">
              <label className="field-label">{lang === 'th' ? 'รหัสผ่าน' : 'Password'}</label>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-subtle)' }}>{Ic.lock}</span>
                <input
                  className="field-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder={lang === 'th' ? 'อย่างน้อย 8 ตัวอักษร' : 'At least 8 characters'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{ paddingLeft: 44, paddingRight: 44 }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    background: 'transparent', border: 0, color: 'var(--ink-subtle)', cursor: 'pointer',
                    padding: 6, borderRadius: 6,
                  }}
                >
                  {showPw ? Ic.eyeOff : Ic.eye}
                </button>
              </div>
              {password && (
                <>
                  <div className={'auth-strength ' + strengthClass}>
                    {[0, 1, 2, 3].map(i => (
                      <span key={i} className={i < strength ? 'on' : ''}></span>
                    ))}
                  </div>
                  <div className="auth-strength-label">{strengthLabel[Math.max(0, strength - 1)]}</div>
                </>
              )}
            </div>
          </div>

          <label className="auth-check" style={{ alignItems: 'flex-start', gap: 10, fontSize: 12.5, lineHeight: 1.45 }}>
            <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} style={{ marginTop: 2 }} />
            <span>
              {lang === 'th' ? (
                <>ยอมรับ <span className="auth-link">ข้อตกลงการใช้งาน</span> และ <span className="auth-link">นโยบายความเป็นส่วนตัว</span></>
              ) : (
                <>I agree to the <span className="auth-link">Terms of Service</span> and <span className="auth-link">Privacy Policy</span></>
              )}
            </span>
          </label>

          <button type="submit" className="btn btn-accent auth-submit" disabled={busy}>
            {busy
              ? (lang === 'th' ? 'กำลังสร้างบัญชี...' : 'Creating account…')
              : (lang === 'th' ? 'สร้างบัญชี' : 'Create account')}
            {!busy && Ic.arrow}
          </button>

          <div className="auth-foot">
            {lang === 'th' ? 'มีบัญชีอยู่แล้ว? ' : 'Already have an account? '}
            <span className="auth-link" onClick={goLogin}>
              {lang === 'th' ? 'เข้าสู่ระบบ' : 'Sign in'} →
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Spinner — small loading indicator
// ─────────────────────────────────────────────────────────────
function Spinner() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" style={{ animation: 'spin 0.8s linear infinite' }}>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.2" strokeDasharray="40 60" strokeLinecap="round" opacity="0.9" />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// Forgot Password
// ─────────────────────────────────────────────────────────────
function Forgot({ lang, goLogin }) {
  const [email, setEmail] = useStateA('');
  const [busy, setBusy] = useStateA(false);
  const [sent, setSent] = useStateA(false);
  const [error, setError] = useStateA('');

  const submit = (e) => {
    e.preventDefault();
    setError('');
    if (!email.trim() || !/^\S+@\S+\.\S+$/.test(email)) {
      setError(lang === 'th' ? 'กรุณากรอกอีเมลที่ถูกต้อง' : 'Please enter a valid email');
      return;
    }
    setBusy(true);
    setTimeout(() => {
      setBusy(false);
      setSent(true);
    }, 900);
  };

  return (
    <div className="auth-shell">
      <AuthHero lang={lang} />

      <div className="auth-form-wrap">
        <form className="auth-form" onSubmit={submit}>
          <div className="auth-form-head">
            <div className="crumb" style={{ cursor: 'pointer' }} onClick={goLogin}>
              ← {lang === 'th' ? 'กลับไปหน้าเข้าระบบ' : 'Back to sign in'}
            </div>
            <h2 style={{ marginTop: 8 }}>
              {sent
                ? (lang === 'th' ? <>เช็ค <em>กล่องเมล</em></> : <>Check your <em>inbox</em></>)
                : (lang === 'th' ? <>ลืม <em>รหัสผ่าน</em>?</> : <>Forgot your <em>password</em>?</>)
              }
            </h2>
            <p>
              {sent
                ? (lang === 'th'
                    ? `เราส่งลิงก์รีเซ็ตไปที่ ${email} แล้ว — ตรวจสอบในกล่องจดหมายของคุณ (รวมถึง spam)`
                    : `We've sent a reset link to ${email}. Check your inbox (and spam folder).`)
                : (lang === 'th'
                    ? 'กรอกอีเมลของคุณ เราจะส่งลิงก์รีเซ็ตรหัสผ่านให้'
                    : "Enter your email and we'll send a reset link.")
              }
            </p>
          </div>

          {sent ? (
            <>
              <div style={{
                background: 'var(--positive-soft)',
                border: '1px solid rgba(136, 212, 164, 0.3)',
                color: 'var(--positive)',
                padding: '14px 16px',
                borderRadius: 12,
                fontSize: 13.5,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}>
                <span style={{ width: 18, height: 18, flexShrink: 0 }}>{Ic.check}</span>
                {lang === 'th' ? 'ส่งอีเมลเรียบร้อย' : 'Email sent successfully'}
              </div>
              <button type="button" className="btn btn-accent auth-submit" onClick={goLogin}>
                {lang === 'th' ? 'กลับไปหน้าเข้าระบบ' : 'Back to sign in'} {Ic.arrow}
              </button>
              <div className="auth-foot">
                {lang === 'th' ? 'ไม่ได้รับเมล? ' : "Didn't get it? "}
                <span className="auth-link" onClick={() => { setSent(false); }}>
                  {lang === 'th' ? 'ส่งอีกครั้ง' : 'Resend'}
                </span>
              </div>
            </>
          ) : (
            <>
              {error && <div className="auth-error">{error}</div>}

              <div className="auth-fields">
                <div className="field">
                  <label className="field-label">{lang === 'th' ? 'อีเมลที่ลงทะเบียน' : 'Your email'}</label>
                  <div style={{ position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-subtle)' }}>{Ic.mail}</span>
                    <input
                      className="field-input"
                      type="email"
                      placeholder="you@email.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      style={{ paddingLeft: 44 }}
                      autoFocus
                    />
                  </div>
                </div>
              </div>

              <button type="submit" className="btn btn-accent auth-submit" disabled={busy}>
                {busy
                  ? (lang === 'th' ? 'กำลังส่ง...' : 'Sending…')
                  : (lang === 'th' ? 'ส่งลิงก์รีเซ็ต' : 'Send reset link')}
                {!busy && Ic.arrow}
              </button>

              <div className="auth-foot">
                {lang === 'th' ? 'จำรหัสผ่านได้แล้ว? ' : 'Remembered it? '}
                <span className="auth-link" onClick={goLogin}>
                  {lang === 'th' ? 'เข้าสู่ระบบ' : 'Sign in'} →
                </span>
              </div>
            </>
          )}
        </form>
      </div>
    </div>
  );
}

Object.assign(window, { Login, Register, Forgot, AuthHero, Spinner });

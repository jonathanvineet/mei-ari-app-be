/* Mei Ari web client. Plain JS single-page app talking to /api/v1/. */
(function () {
  'use strict';

  const API = '/api/v1/';
  const STATUSES = ['Created', 'Completed', 'Verified', 'Signed'];
  const ROLE_LABEL = {
    Inspection_Cell_Officer: 'Inspection officer',
    Inspection_Cell_Head: 'Inspection cell head',
    Inspection_Cell_Admin: 'Inspection cell admin',
  };
  // Which role moves a report out of each status, and what the step is called.
  const REPORT_STEP = {
    Created: { next: 'Completed', verb: 'Mark completed', todo: 'mark it completed', roles: ['Inspection_Cell_Officer', 'Inspection_Cell_Admin'], who: 'Officer reviews the draft' },
    Completed: { next: 'Verified', verb: 'Verify report', todo: 'verify it', roles: ['Inspection_Cell_Head', 'Inspection_Cell_Admin'], who: 'Cell head verifies' },
    Verified: { next: 'Signed', verb: 'Sign report', todo: 'sign it', roles: ['Inspection_Cell_Admin'], who: 'Admin signs off' },
    Signed: null,
  };
  const STATUS_WHO = { Created: 'Generated, awaiting review', Completed: 'Awaiting head’s verification', Verified: 'Awaiting sign-off', Signed: 'Closed' };

  const app = document.getElementById('app');
  const toastEl = document.getElementById('toast');

  /* ---------- helpers ---------- */
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtDate = (iso) => iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  const fmtDateTime = (iso) => iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
  const stamp = (s, cls = '') => `<span class="stamp ${cls}" data-status="${esc(s)}">${esc(s)}</span>`;
  const today = () => new Date().toISOString().slice(0, 10);

  const store = {
    get(key) { try { return JSON.parse(localStorage.getItem(key)); } catch (e) { return null; } },
    set(key, val) { try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { /* storage unavailable */ } },
    del(key) { try { localStorage.removeItem(key); } catch (e) { /* storage unavailable */ } },
  };
  let session = store.get('meiari.session'); // { token, user, office }

  let toastTimer;
  function toast(msg, isError) {
    toastEl.textContent = msg;
    toastEl.className = 'show' + (isError ? ' error' : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.className = ''; }, 3600);
  }

  function errorText(data, fallback) {
    if (!data) return fallback;
    const e = data.error ?? data.message ?? data.detail;
    if (!e) return fallback;
    if (typeof e === 'string') return e;
    const parts = [];
    (function walk(obj, prefix) {
      for (const [k, v] of Object.entries(obj)) {
        const label = k === 'non_field_errors' ? '' : k.replace(/_/g, ' ');
        if (Array.isArray(v)) parts.push(`${prefix}${label ? label + ': ' : ''}${v.join(' ')}`);
        else if (v && typeof v === 'object') walk(v, `${prefix}${label} › `);
        else parts.push(`${prefix}${label}: ${v}`);
      }
    })(e, '');
    return parts.join('\n') || fallback;
  }

  async function api(path, { method = 'GET', body, raw } = {}) {
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (session?.token) headers.Authorization = `Bearer ${session.token}`;
    let res;
    try {
      res = await fetch(API + path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
    } catch (e) {
      throw new Error('Can’t reach the server. Check that it is running and try again.');
    }
    if (raw) {
      if (!res.ok) throw new Error(`Couldn’t load the file (status ${res.status}).`);
      return res.text();
    }
    const data = await res.json().catch(() => null);
    if (!res.ok) throw Object.assign(new Error(errorText(data, `Request failed (status ${res.status}).`)), { status: res.status, data });
    return data;
  }

  function formData(form) {
    const out = {};
    for (const [k, v] of new FormData(form).entries()) out[k] = typeof v === 'string' ? v.trim() : v;
    return out;
  }

  async function withBusy(button, label, fn) {
    const original = button.textContent;
    button.disabled = true; button.textContent = label;
    try { return await fn(); }
    finally { button.disabled = false; button.textContent = original; }
  }

  function showError(form, message) {
    let box = form.querySelector('.error-box');
    if (!message) { box?.remove(); return; }
    if (!box) { box = document.createElement('div'); box.className = 'error-box'; box.setAttribute('role', 'alert'); form.prepend(box); }
    box.textContent = message;
    box.style.whiteSpace = 'pre-line';
  }

  /* Minimal, safe Markdown → HTML for Gemini output (escape first, then format). */
  function markdown(src) {
    const inline = (s) => esc(s)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, '$1<em>$2</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
    const lines = src.replace(/\r\n/g, '\n').split('\n');
    const out = []; let list = null; let para = [];
    const flushPara = () => { if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para = []; } };
    const flushList = () => { if (list) { out.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join('')}</${list.tag}>`); list = null; } };
    for (const line of lines) {
      const t = line.trim();
      let m;
      if (!t) { flushPara(); flushList(); continue; }
      if ((m = t.match(/^(#{1,4})\s+(.*)$/))) { flushPara(); flushList(); const lvl = Math.min(m[1].length, 3); out.push(`<h${lvl}>${inline(m[2])}</h${lvl}>`); continue; }
      if (/^(-{3,}|\*{3,})$/.test(t)) { flushPara(); flushList(); out.push('<hr>'); continue; }
      if ((m = t.match(/^[-*•]\s+(.*)$/)) || (m = t.match(/^\d+[.)]\s+(.*)$/))) {
        flushPara();
        const tag = /^\d/.test(t) ? 'ol' : 'ul';
        if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
        list.items.push(m[1]); continue;
      }
      flushList(); para.push(t);
    }
    flushPara(); flushList();
    return out.join('\n');
  }

  /* ---------- session & shared data ---------- */
  function saveSession(s) { session = s; store.set('meiari.session', s); }
  function signOut() { session = null; store.del('meiari.session'); location.hash = '#/login'; }
  const user = () => session?.user;
  const officeId = () => session?.user?.sub_dept_office_name;
  const isAdmin = () => user()?.role === 'Inspection_Cell_Admin';

  async function loadOffice() {
    if (session?.office || !officeId()) return session?.office;
    const res = await api('subdeptofficedetails/');
    const office = (res.data || []).find((o) => String(o.id) === String(officeId()));
    if (office) saveSession({ ...session, office });
    return office;
  }

  async function loadReports() {
    const res = await api(`report-records/${officeId()}/`);
    return (res.data || []).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }

  /* ---------- routing ---------- */
  const routes = [
    [/^\/home$/, viewHome, { public: true }],
    [/^\/login$/, viewLogin, { public: true }],
    [/^\/signup$/, viewSignup, { public: true }],
    [/^\/verify\/([\w-]+)$/, viewVerify, { public: true }],
    [/^\/$/, viewDashboard],
    [/^\/inspect$/, viewInspect],
    [/^\/reports$/, viewReports],
    [/^\/reports\/([\w-]+)$/, viewReport],
    [/^\/groups$/, viewGroups],
    [/^\/groups\/([\w-]+)$/, viewGroup],
    [/^\/org$/, viewOrg],
  ];

  function parseHash() {
    const h = location.hash.replace(/^#/, '') || '/';
    const [path, qs] = h.split('?');
    return { path, query: new URLSearchParams(qs || '') };
  }

  async function router() {
    const { path, query } = parseHash();
    const match = routes.find(([re]) => re.test(path));
    if (!match) { location.hash = '#/'; return; }
    const [re, view, opts = {}] = match;
    if (!opts.public && !session?.token) { location.hash = path === '/' ? '#/home' : '#/login'; return; }
    if (opts.public && session?.token && path === '/login') { location.hash = '#/'; return; }
    const params = path.match(re).slice(1);
    try {
      if (opts.public) await view(...params, query);
      else { await loadOffice(); await view(...params, query); }
    } catch (e) {
      console.error(e);
      renderShell(`<div class="page"><div class="error-box" role="alert">${esc(e.message)}</div></div>`);
    }
    window.scrollTo(0, 0);
  }
  window.addEventListener('hashchange', router);

  /* ---------- shell ---------- */
  const NAV = [
    ['#/', 'Overview', /^\/$/],
    ['#/inspect', 'New inspection', /^\/inspect/],
    ['#/reports', 'Reports', /^\/reports/],
    ['#/groups', 'Work groups', /^\/groups/],
  ];

  function renderShell(content) {
    const { path } = parseHash();
    const nav = NAV.concat(isAdmin() ? [['#/org', 'Organisation', /^\/org/]] : []);
    const link = ([href, label, re]) => `<a href="${href}" ${re.test(path) ? 'aria-current="page"' : ''}>${label}</a>`;
    const office = session?.office;
    const u = user() || {};
    app.innerHTML = `
      <div class="shell">
        <aside class="rail">
          <a class="wordmark" href="#/"><span class="seal" aria-hidden="true">MA</span><strong>Mei Ari</strong></a>
          <div class="office-card">
            <div class="name">${esc(office?.sub_dept_office_location || 'Your office')}</div>
            <div class="small muted">${esc(u.sub_department_name || '')}</div>
            <div class="small muted">${esc(office ? `${office.sub_dept_district} district` : '')}</div>
          </div>
          <nav class="nav" aria-label="Main">${nav.map(link).join('')}</nav>
          <div class="rail-foot">
            <div class="me"><div>${esc(u.email || '')}</div><div class="role">${esc(ROLE_LABEL[u.role] || u.role || '')}</div><div class="role">Access ID ${esc(u.access_id || '—')}</div></div>
            <a class="small" href="#/home">How Mei Ari works</a>
            <button class="btn quiet small" data-action="signout">Sign out</button>
          </div>
        </aside>
        <header class="mobile-bar">
          <a class="wordmark" href="#/"><span class="seal" aria-hidden="true">MA</span><strong>Mei Ari</strong></a>
          <div class="office">${esc(office?.sub_dept_office_location || '')}<br><button class="linkish small" data-action="signout">Sign out</button></div>
        </header>
        <main class="main" id="main">${content}</main>
        <nav class="tabbar" aria-label="Main">${nav.map(([h, l, re]) => link([h, l.replace('New inspection', 'Inspect').replace('Work groups', 'Groups').replace('Organisation', 'Org'), re])).join('')}</nav>
      </div>`;
    app.querySelectorAll('[data-action="signout"]').forEach((b) => b.addEventListener('click', signOut));
  }

  function loadingShell(text = 'Loading…') { renderShell(`<div class="loading">${esc(text)}</div>`); }


  /* ---------- home (public) ---------- */
  const HOW = [
    { status: 'Created', who: 'Inspection officer, on site', title: 'Record what you find',
      body: 'Open a new inspection at the office you are visiting. Your location is captured from your phone, and you note what you inspected, what you observed, any issues, and what should be done about them.' },
    { status: 'Created', who: 'Mei Ari, in about a minute', title: 'Get a formal report drafted', draft: true,
      body: 'Your notes are turned into a structured report with a summary, observations, issues, recommended actions and a conclusion. The draft uses only what you wrote, and it is filed against your office with your access ID.' },
    { status: 'Completed', who: 'Inspection officer', title: 'Review the draft and mark it completed',
      body: 'Read the report before it goes anywhere. Once you are satisfied it reflects the inspection, mark it completed and it moves to your cell head.' },
    { status: 'Verified', who: 'Inspection cell head', title: 'Verify the findings',
      body: 'The cell head sees every completed report waiting for them on their overview, reads it, and verifies it.' },
    { status: 'Signed', who: 'Inspection cell admin', title: 'Sign it off',
      body: 'The admin signs the verified report. It is closed, and anyone in the office can read or download it.' },
  ];

  async function viewHome() {
    const signedIn = !!session?.token;
    const cta = signedIn
      ? `<a class="btn" href="#/">Go to your office</a>`
      : `<a class="btn" href="#/login">Sign in</a><a class="btn secondary on-band" href="#/signup">Create an account</a>`;
    app.innerHTML = `
      <div class="home">
        <header class="home-band">
          <nav class="home-nav" aria-label="Site">
            <a class="wordmark" href="#/home" style="color:inherit"><span class="seal" aria-hidden="true" style="--sheet:var(--band)">MA</span><strong>Mei Ari</strong></a>
            <div class="home-nav-links">${signedIn ? '<a href="#/">Your office</a>' : '<a href="#/login">Sign in</a>'}</div>
          </nav>
          <div class="home-hero">
            <div class="home-hero-copy">
              <h1>Every inspection, written up and signed off.</h1>
              <p>Mei Ari is for the Inspection Cells of Tamil Nadu government departments. Officers record what they find when they visit an office, a formal report is drafted from their notes, and the report is stamped through review, verification and sign-off, all in one place.</p>
              <div class="home-cta">${cta}</div>
            </div>
            <figure class="specimen" aria-label="Example of a signed inspection report">
              <div class="specimen-sheet">
                <p class="specimen-ref">Ref 65F03E1C, filed by Kavit1705</p>
                <h2>Inspection report, Primary Health Centre, Egmore</h2>
                <h3>Issues found</h3>
                <ul>
                  <li>Temperature log for the third vaccine refrigerator missing for five days.</li>
                  <li>ORS sachets at 40, below the minimum stock of 200.</li>
                </ul>
                <h3>Recommended actions</h3>
                <ul>
                  <li>Medical officer to restore twice-daily logging immediately.</li>
                  <li>Pharmacist to raise an indent for ORS within two days.</li>
                </ul>
                <div class="specimen-stamps" aria-hidden="true">
                  ${STATUSES.map((st, i) => `<span class="stamp" data-status="${st}" style="--i:${i}">${st}</span>`).join('')}
                </div>
              </div>
              <figcaption>An example report. Each stamp is added by a different person.</figcaption>
            </figure>
          </div>
        </header>

        <main class="home-main">
          <section class="home-section" aria-labelledby="how-h">
            <h2 id="how-h">How a report moves</h2>
            <p class="home-lede">Five steps, from the site visit to a signed report. Everyone involved can see where each report is on their overview.</p>
            <ol class="how">
              ${HOW.map((step, i) => `
                <li data-status="${step.status}">
                  <div class="how-mark"><span class="how-n">${i + 1}</span></div>
                  <div class="how-body">
                    <h3>${esc(step.title)}</h3>
                    <p class="how-who">${esc(step.who)}</p>
                    <p>${esc(step.body)}</p>
                  </div>
                  <div class="how-stamp">${step.draft ? '' : stamp(step.status)}</div>
                </li>`).join('')}
            </ol>
          </section>

          <section class="home-section" aria-labelledby="who-h">
            <h2 id="who-h">Who does what</h2>
            <div class="rows home-roles">
              <div class="row"><div><div class="title">Inspection officer</div><div class="meta">Visits offices, records findings, reviews the drafted report and marks it completed. Works through tasks assigned to their work groups.</div></div></div>
              <div class="row"><div><div class="title">Inspection cell head</div><div class="meta">Verifies completed reports and leads work groups.</div></div></div>
              <div class="row"><div><div class="title">Inspection cell admin</div><div class="meta">Signs verified reports and sets up the departments, sub-departments and offices that officers belong to.</div></div></div>
            </div>
          </section>

          <section class="home-section home-split" aria-labelledby="groups-h">
            <div>
              <h2 id="groups-h">Work groups and tasks</h2>
              <p class="home-lede">Between inspections, officers in an office can be grouped into teams, such as a monsoon readiness team. Each group has a task board, and tasks move through the same four stages as reports so follow-up work is tracked the same way.</p>
            </div>
            <div>
              <h2>Getting started</h2>
              <p class="home-lede">Create an account with your CUG email and choose your department, sub-department and office. We email you a 4-digit code to confirm your address, and you get an access ID that appears on every report you file.</p>
            </div>
          </section>

          <section class="home-close">
            <h2>${signedIn ? 'Pick up where you left off.' : 'Ready to file your first inspection?'}</h2>
            <div class="home-cta">${signedIn ? '<a class="btn" href="#/inspect">Start an inspection</a><a class="btn quiet" href="#/">Go to your office</a>' : '<a class="btn" href="#/signup">Create an account</a><a class="btn quiet" href="#/login">Sign in</a>'}</div>
          </section>
        </main>
      </div>`;
  }

  /* ---------- auth views ---------- */
  function authLayout(inner) {
    app.innerHTML = `
      <div class="auth">
        <section class="auth-side">
          <a class="wordmark" href="#/home" style="color:inherit"><span class="seal" aria-hidden="true" style="--sheet:var(--band)">MA</span><strong>Mei Ari</strong></a>
          <div>
            <h1>Inspect, report, and get it signed.</h1>
            <p>Record what you find on an inspection, get a formal report drafted for you, and track it through review, verification and sign-off.</p>
          </div>
          <div class="stamps" aria-hidden="true">${STATUSES.map((s) => stamp(s)).join('')}</div>
        </section>
        <section class="auth-main">${inner}</section>
      </div>`;
  }

  async function viewLogin() {
    authLayout(`
      <div><h2>Sign in</h2><p class="muted" style="margin-top:6px">Use your CUG email address.</p></div>
      <form class="form" id="login" novalidate>
        <div class="field"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="username" required></div>
        <div class="field"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required></div>
        <div class="form-actions"><button class="btn" type="submit">Sign in</button><span class="muted">New here? <a href="#/signup">Create an account</a></span></div>
      </form>
      <div class="demo">
        <p class="muted">Demo accounts (password <strong>MeiAri@123</strong>):</p>
        ${['officer', 'head', 'admin'].map((r) => `<button class="linkish" data-demo="${r}@demo.tn.gov.in">${r}@demo.tn.gov.in</button>`).join('')}
      </div>`);
    const form = document.getElementById('login');
    app.querySelectorAll('[data-demo]').forEach((b) => b.addEventListener('click', () => {
      form.email.value = b.dataset.demo; form.password.value = 'MeiAri@123'; form.querySelector('button[type=submit]').focus();
    }));
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const body = formData(form);
      if (!body.email || !body.password) { showError(form, 'Enter your email and password.'); return; }
      await withBusy(form.querySelector('button[type=submit]'), 'Signing in…', async () => {
        try {
          const res = await api('signin/', { method: 'POST', body });
          saveSession({ token: res.token, user: res.data });
          location.hash = '#/';
        } catch (err) { showError(form, err.message); }
      });
    });
  }

  async function viewSignup() {
    authLayout(`<div class="loading">Loading departments…</div>`);
    const depts = (await api('tngovtdept/')).data || [];
    const main = app.querySelector('.auth-main');
    main.innerHTML = `
      <div><h2>Create an account</h2><p class="muted" style="margin-top:6px">We’ll email a 4-digit code to confirm your address.</p></div>
      <form class="form" id="signup" novalidate>
        <div class="form-grid">
          <div class="field"><label for="first_name">First name</label><input id="first_name" name="first_name" required autocomplete="given-name"></div>
          <div class="field"><label for="last_name">Last name</label><input id="last_name" name="last_name" required autocomplete="family-name"></div>
          <div class="field"><label for="date_of_birth">Date of birth</label><input id="date_of_birth" name="date_of_birth" type="date" required></div>
          <div class="field"><label for="user_name">Username</label><input id="user_name" name="user_name" required autocomplete="nickname"></div>
          <div class="field full"><label for="cug_email_address">CUG email</label><input id="cug_email_address" name="cug_email_address" type="email" required autocomplete="email"></div>
          <div class="field"><label for="cug_phone_number">CUG phone</label><input id="cug_phone_number" name="cug_phone_number" type="tel" required autocomplete="tel"></div>
          <div class="field"><label for="alternative_email_address">Personal email</label><input id="alternative_email_address" name="alternative_email_address" type="email" required></div>
          <div class="field full"><label for="role">Role</label><select id="role" name="role">${Object.entries(ROLE_LABEL).map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></div>
          <div class="field full"><label for="dept_id">Department</label><select id="dept_id" name="dept_id" required><option value="">Choose a department</option>${depts.map((d) => `<option value="${d.id}">${esc(d.department_name)}</option>`).join('')}</select></div>
          <div class="field full"><label for="sub_dept_id">Sub-department</label><select id="sub_dept_id" name="sub_dept_id" required disabled><option value="">Choose a department first</option></select></div>
          <div class="field full"><label for="sub_dept_office_id">Office</label><select id="sub_dept_office_id" name="sub_dept_office_id" required disabled><option value="">Choose a sub-department first</option></select></div>
          <div class="field full"><label for="password">Password</label><input id="password" name="password" type="password" required minlength="8" autocomplete="new-password"><span class="hint">At least 8 characters.</span></div>
        </div>
        <div class="form-actions"><button class="btn" type="submit">Create account</button><span class="muted">Have an account? <a href="#/login">Sign in</a></span></div>
      </form>`;
    const form = document.getElementById('signup');
    const sub = form.sub_dept_id, office = form.sub_dept_office_id;
    form.dept_id.addEventListener('change', async () => {
      office.innerHTML = '<option value="">Choose a sub-department first</option>'; office.disabled = true;
      if (!form.dept_id.value) { sub.disabled = true; return; }
      const list = (await api(`tngovtsubdept/?department=${form.dept_id.value}`)).data || [];
      sub.innerHTML = `<option value="">${list.length ? 'Choose a sub-department' : 'No sub-departments yet'}</option>` + list.map((s) => `<option value="${s.id}">${esc(s.sub_department_name)}</option>`).join('');
      sub.disabled = !list.length;
    });
    sub.addEventListener('change', async () => {
      if (!sub.value) { office.disabled = true; return; }
      const list = (await api(`subdeptofficedetails/?sub_dept=${sub.value}`)).data || [];
      office.innerHTML = `<option value="">${list.length ? 'Choose an office' : 'No offices yet'}</option>` + list.map((o) => `<option value="${o.id}">${esc(o.sub_dept_office_location)}, ${esc(o.sub_dept_district)}</option>`).join('');
      office.disabled = !list.length;
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const f = formData(form);
      const missing = [...form.querySelectorAll('[required]')].filter((el) => !el.value.trim()).map((el) => form.querySelector(`label[for="${el.id}"]`).textContent);
      if (missing.length) { showError(form, `Fill in: ${missing.join(', ')}.`); return; }
      if (f.password.length < 8) { showError(form, 'Password must be at least 8 characters.'); return; }
      const body = {
        cug_phone_number: f.cug_phone_number, cug_email_address: f.cug_email_address, password: f.password, role: f.role,
        dept_id: f.dept_id, sub_dept_id: f.sub_dept_id, sub_dept_office_id: f.sub_dept_office_id,
        bio_data: { user_name: f.user_name, first_name: f.first_name, last_name: f.last_name, date_of_birth: f.date_of_birth, alternative_email_address: f.alternative_email_address },
      };
      await withBusy(form.querySelector('button[type=submit]'), 'Creating…', async () => {
        try {
          const res = await api('create-meiari-user/', { method: 'POST', body });
          store.set('meiari.pendingEmail', f.cug_email_address);
          location.hash = `#/verify/${res.data.user_id}`;
          if (!res.data.otp_sent) toast('Account created, but the code email failed. Use “Send a new code”.', true);
        } catch (err) { showError(form, err.message); }
      });
    });
  }

  async function viewVerify(userId) {
    const email = store.get('meiari.pendingEmail');
    authLayout(`
      <div><h2>Check your email</h2><p class="muted" style="margin-top:6px">Enter the 4-digit code we sent${email ? ` to <strong>${esc(email)}</strong>` : ''}. It expires in 10 minutes.</p></div>
      <form class="form" id="verify" novalidate>
        <div class="field"><label for="otp">Code</label><input id="otp" name="otp" class="otp-input" inputmode="numeric" pattern="\\d{4}" maxlength="4" autocomplete="one-time-code" required></div>
        <div class="form-actions"><button class="btn" type="submit">Confirm email</button><button class="linkish" type="button" id="resend">Send a new code</button></div>
      </form>`);
    const form = document.getElementById('verify');
    form.otp.focus();
    document.getElementById('resend').addEventListener('click', async (e) => {
      await withBusy(e.target, 'Sending…', async () => {
        try { await api('resend-otp/', { method: 'POST', body: { user_id: userId } }); toast('New code sent.'); }
        catch (err) { toast(err.message, true); }
      });
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const otp = form.otp.value.trim();
      if (!/^\d{4}$/.test(otp)) { showError(form, 'Enter the 4 digits from the email.'); return; }
      await withBusy(form.querySelector('button[type=submit]'), 'Confirming…', async () => {
        try {
          const res = await api('verify-otp/', { method: 'POST', body: { user_id: userId, otp } });
          store.del('meiari.pendingEmail');
          app.querySelector('.auth-main').innerHTML = `
            <div><h2>Email confirmed</h2><p class="muted" style="margin-top:6px">Your access ID is</p></div>
            <p style="font-size:2rem;font-weight:800;letter-spacing:0.04em">${esc(res.data.access_id)}</p>
            <p class="muted">You’ll see it on every report you file. Sign in to continue.</p>
            <div><a class="btn" href="#/login">Sign in</a></div>`;
        } catch (err) { showError(form, err.message); }
      });
    });
  }

  /* ---------- dashboard ---------- */
  function canAct(status) {
    const step = REPORT_STEP[status];
    return !!step && step.roles.includes(user()?.role);
  }

  const refNo = (id) => String(id).slice(0, 8).toUpperCase();

  function reportRow(r) {
    return `<a class="row" href="#/reports/${r.id}">
      <div><div class="title">Inspection at ${esc(r.city)}</div><div class="meta">Ref ${refNo(r.id)}, filed ${fmtDateTime(r.created_at)} by ${esc(r.access_id)}</div></div>
      <div>${stamp(r.ticket_status_type)}</div></a>`;
  }

  async function viewDashboard() {
    loadingShell();
    const [reports, groups] = await Promise.all([
      loadReports(),
      api(`workgroups/?sub_dept_office=${officeId()}`).then((r) => r.data || []),
    ]);
    const counts = Object.fromEntries(STATUSES.map((s) => [s, reports.filter((r) => r.ticket_status_type === s).length]));
    const mine = reports.filter((r) => canAct(r.ticket_status_type));
    const u = user();
    const office = session.office;
    renderShell(`
      <div class="page">
        <div class="page-head">
          <div><h1>${esc(office?.sub_dept_office_location || 'Overview')}</h1>
          <p>${esc([u.department_name, u.sub_department_name].filter(Boolean).join(', '))}${office ? `. ${esc(office.sub_dept_taluk)} taluk, ${esc(office.sub_dept_district)} district.` : ''}</p></div>
          <a class="btn" href="#/inspect">Start an inspection</a>
        </div>

        <section class="section" aria-labelledby="trail-h">
          <div class="section-head"><h2 id="trail-h">Approval trail</h2><span class="muted small">${reports.length} report${reports.length === 1 ? '' : 's'} in total</span></div>
          <div class="trail">${STATUSES.map((s, i) => `
            <a href="#/reports?status=${s}" data-status="${s}">
              <span class="num">Step ${i + 1}</span>
              <span class="count">${counts[s]}</span>
              <span class="label">${s}</span>
              <span class="who">${STATUS_WHO[s]}</span>
            </a>`).join('')}</div>
        </section>

        <div class="two-col section">
          <section aria-labelledby="todo-h">
            <div class="section-head"><h2 id="todo-h">Waiting on you</h2>${mine.length ? `<a href="#/reports" class="small">All reports</a>` : ''}</div>
            <div class="rows">${mine.length ? mine.slice(0, 6).map(reportRow).join('') : `
              <div class="empty"><p><strong>Nothing needs your action.</strong></p><p class="muted">Reports you need to ${u.role === 'Inspection_Cell_Head' ? 'verify' : u.role === 'Inspection_Cell_Admin' ? 'review or sign' : 'review'} will show up here.</p></div>`}</div>
          </section>
          <section aria-labelledby="groups-h">
            <div class="section-head"><h2 id="groups-h">Work groups</h2><a href="#/groups" class="small">Manage</a></div>
            <div class="rows">${groups.length ? groups.map((g) => `
              <a class="row" href="#/groups/${g.id}"><div><div class="title">${esc(g.group_name)}</div><div class="meta">${esc(g.group_description)}</div></div></a>`).join('') : `
              <div class="empty"><p><strong>No work groups yet.</strong></p><p class="muted">Group officers into teams and assign them tasks.</p><a class="btn secondary small" href="#/groups">Create a work group</a></div>`}</div>
          </section>
        </div>

        <section class="section" aria-labelledby="recent-h">
          <div class="section-head"><h2 id="recent-h">Recent reports</h2></div>
          <div class="rows">${reports.length ? reports.slice(0, 5).map(reportRow).join('') : `
            <div class="empty"><p><strong>No reports yet.</strong></p><p class="muted">Record your first inspection and a formal report is drafted for you.</p><a class="btn secondary small" href="#/inspect">Start an inspection</a></div>`}</div>
        </section>
      </div>`);
  }

  /* ---------- new inspection ---------- */
  async function viewInspect() {
    const office = session.office || {};
    const u = user();
    renderShell(`
      <div class="page" style="max-width:760px">
        <div class="page-head"><div><h1>New inspection</h1><p>Write down what you found. A formal report is drafted from your notes, then goes to review.</p></div></div>
        <form class="form panel" id="inspect" novalidate>
          <fieldset>
            <legend>Where and when</legend>
            <div class="form-grid">
              <div class="field"><label for="city">City or town</label><input id="city" name="city" required value="${esc(office.sub_dept_district || '')}"></div>
              <div class="field"><label for="date">Date of inspection</label><input id="date" name="date" type="date" required value="${today()}" max="${today()}"></div>
              <div class="full form-actions"><button type="button" class="btn quiet small" id="locate">Use my current location</button><span class="muted small" id="locate-msg"></span></div>
              <div class="field"><label for="latitude">Latitude</label><input id="latitude" name="latitude" inputmode="decimal" required></div>
              <div class="field"><label for="longitude">Longitude</label><input id="longitude" name="longitude" inputmode="decimal" required></div>
            </div>
          </fieldset>
          <fieldset>
            <legend>What you found</legend>
            <div class="field"><label for="area">What did you inspect?</label><input id="area" name="area" required placeholder="For example: pharmacy, labour ward, vaccine cold chain"></div>
            <div class="field"><label for="observations">Observations</label><textarea id="observations" name="observations" required placeholder="What you saw, checked and counted."></textarea></div>
            <div class="field"><label for="issues">Issues found</label><textarea id="issues" name="issues" placeholder="Anything that is missing, broken or not as it should be. Leave blank if none."></textarea></div>
            <div class="field"><label for="recommendations">Recommended actions</label><textarea id="recommendations" name="recommendations" placeholder="What should be done, and by whom."></textarea></div>
            <div class="field"><label for="staff">Staff present</label><input id="staff" name="staff" placeholder="Names and designations (optional)"></div>
          </fieldset>
          <div class="form-actions"><button class="btn" type="submit">Generate report</button><span class="muted small">Takes up to a minute.</span></div>
        </form>
      </div>`);
    const form = document.getElementById('inspect');
    const msg = document.getElementById('locate-msg');
    document.getElementById('locate').addEventListener('click', () => {
      if (!navigator.geolocation) { msg.textContent = 'Location isn’t available in this browser. Enter it by hand.'; return; }
      msg.textContent = 'Finding your location…';
      navigator.geolocation.getCurrentPosition(
        (pos) => { form.latitude.value = pos.coords.latitude.toFixed(6); form.longitude.value = pos.coords.longitude.toFixed(6); msg.textContent = `Located to within ${Math.round(pos.coords.accuracy)} m.`; },
        () => { msg.textContent = 'Couldn’t get your location. Allow location access or enter it by hand.'; },
        { enableHighAccuracy: true, timeout: 15000 },
      );
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const f = formData(form);
      const lat = parseFloat(f.latitude), lng = parseFloat(f.longitude);
      if (!f.city || !f.area || !f.observations) { showError(form, 'Fill in the city, what you inspected, and your observations.'); return; }
      if (!(lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) || !f.latitude || !f.longitude) { showError(form, 'Enter a valid latitude and longitude, or use your current location.'); return; }
      showError(form, null);
      const payload = {
        location: { city: f.city, latitude: lat, longitude: lng },
        departmentName: u.department_name,
        subDepartmentName: u.sub_department_name,
        accessId: u.access_id,
        subDeptOfficeName: officeId(),
        inspection: {
          office: office.sub_dept_office_location, address: office.sub_dept_street_address, taluk: office.sub_dept_taluk, district: office.sub_dept_district,
          date: f.date, inspector_access_id: u.access_id, inspector_role: ROLE_LABEL[u.role],
          area_inspected: f.area, observations: f.observations, issues_found: f.issues, recommended_actions: f.recommendations, staff_present: f.staff,
        },
      };
      const button = form.querySelector('button[type=submit]');
      const fieldsets = form.querySelectorAll('fieldset');
      fieldsets.forEach((fs) => { fs.disabled = true; });
      const writing = document.createElement('div');
      writing.className = 'writing';
      writing.innerHTML = '<p><strong>Drafting your report…</strong></p><div class="bar"></div><div class="bar"></div><div class="bar"></div><div class="bar"></div>';
      form.after(writing);
      await withBusy(button, 'Generating…', async () => {
        try {
          const res = await api('generate-and-upload-report/', { method: 'POST', body: payload });
          toast('Report generated.');
          location.hash = `#/reports/${res.report_id}`;
        } catch (err) {
          writing.remove(); fieldsets.forEach((fs) => { fs.disabled = false; });
          showError(form, `The report couldn’t be generated. ${err.message}`);
        }
      });
    });
  }

  /* ---------- reports ---------- */
  async function viewReports(query) {
    loadingShell();
    const reports = await loadReports();
    const filter = STATUSES.includes(query.get('status')) ? query.get('status') : '';
    const shown = filter ? reports.filter((r) => r.ticket_status_type === filter) : reports;
    const tab = (s, label, n) => `<a href="#/reports${s ? `?status=${s}` : ''}" aria-current="${filter === s}">${label} (${n})</a>`;
    renderShell(`
      <div class="page">
        <div class="page-head"><div><h1>Reports</h1><p>Every inspection report filed for this office.</p></div><a class="btn" href="#/inspect">Start an inspection</a></div>
        <nav class="filters" aria-label="Filter by status">${tab('', 'All', reports.length)}${STATUSES.map((s) => tab(s, s, reports.filter((r) => r.ticket_status_type === s).length)).join('')}</nav>
        <div class="rows">${shown.length ? shown.map(reportRow).join('') : `
          <div class="empty"><p><strong>${filter ? `No reports are ${filter.toLowerCase()} right now.` : 'No reports yet.'}</strong></p>${filter ? '<p class="muted"><a href="#/reports">Show all reports</a></p>' : '<a class="btn secondary small" href="#/inspect">Start an inspection</a>'}</div>`}</div>
      </div>`);
  }

  async function viewReport(id, _query, justStamped) {
    loadingShell('Loading report…');
    const reports = await loadReports();
    const r = reports.find((x) => String(x.id) === id);
    if (!r) { renderShell(`<div class="page"><h1>Report not found</h1><p class="muted" style="margin-top:8px">It may belong to another office. <a href="#/reports">Back to reports</a></p></div>`); return; }
    let text = '';
    let textError = '';
    try { text = await api(`download-report/${r.id}/`, { raw: true }); } catch (e) { textError = e.message; }
    const step = REPORT_STEP[r.ticket_status_type];
    const idx = STATUSES.indexOf(r.ticket_status_type);
    const office = session.office || {};
    const actionBar = step ? `
      <div class="action-bar">
        <p><strong>Next: ${esc(step.who.toLowerCase())}.</strong> ${canAct(r.ticket_status_type) ? `Read the report below, then ${step.todo}.` : `This is done by the ${step.roles.map((x) => ROLE_LABEL[x].toLowerCase()).join(' or ')}.`}</p>
        ${canAct(r.ticket_status_type) ? `<button class="btn" id="advance">${esc(step.verb)}</button>` : ''}
      </div>` : `<div class="action-bar"><p><strong>Signed and closed.</strong> No further action is needed.</p></div>`;
    renderShell(`
      <div class="page">
        <p class="small" style="margin-bottom:14px"><a href="#/reports">Reports</a></p>
        <div class="report-head">
          <div>
            <h1>Inspection at ${esc(r.city)}</h1>
            <p class="muted" style="margin-top:6px">${esc(office.sub_dept_office_location || '')}</p>
          </div>
          <div style="padding:8px 12px 0 0">${stamp(r.ticket_status_type, 'large' + (justStamped ? ' pressed' : ''))}</div>
        </div>
        <ol class="steps" aria-label="Approval trail">${STATUSES.map((s, i) => `<li data-status="${s}" class="${i <= idx ? 'done' : ''} ${i === idx ? 'current' : ''}" ${i === idx ? 'aria-current="step"' : ''}>${s}</li>`).join('')}</ol>
        <dl class="facts">
          <div><dt>Reference</dt><dd>${refNo(r.id)}</dd></div>
          <div><dt>Filed</dt><dd>${fmtDateTime(r.created_at)}</dd></div>
          <div><dt>Filed by</dt><dd>${esc(r.access_id)}</dd></div>
          <div><dt>Department</dt><dd>${esc(r.department_name)}</dd></div>
          <div><dt>Location</dt><dd>${Number(r.latitude).toFixed(4)}, ${Number(r.longitude).toFixed(4)} <a class="small" href="https://www.openstreetmap.org/?mlat=${r.latitude}&mlon=${r.longitude}#map=17/${r.latitude}/${r.longitude}" target="_blank" rel="noopener">Map</a></dd></div>
        </dl>
        ${actionBar}
        <article class="sheet">
          ${textError ? `<div class="error-box" role="alert">${esc(textError)}</div>` : `<div class="doc">${markdown(text)}</div>`}
        </article>
        <div class="form-actions" style="margin-top:20px"><a class="btn quiet" href="${API}download-report/${r.id}/">Download as text file</a></div>
      </div>`);
    const btn = document.getElementById('advance');
    btn?.addEventListener('click', () => withBusy(btn, 'Stamping…', async () => {
      try {
        await api(`update-status/${r.id}/?status=${step.next}`);
        toast(`Report ${step.next.toLowerCase()}.`);
        await viewReport(id, _query, true);
      } catch (err) { toast(err.message, true); }
    }));
  }

  /* ---------- work groups ---------- */
  async function viewGroups() {
    loadingShell();
    const groups = (await api(`workgroups/?sub_dept_office=${officeId()}`)).data || [];
    renderShell(`
      <div class="page">
        <div class="page-head"><div><h1>Work groups</h1><p>Teams in this office, their members and their tasks.</p></div></div>
        <div class="two-col">
          <div class="rows">${groups.length ? groups.map((g) => `
            <a class="row" href="#/groups/${g.id}"><div><div class="title">${esc(g.group_name)}</div><div class="meta">${esc(g.group_description)}</div></div></a>`).join('') : `
            <div class="empty"><p><strong>No work groups yet.</strong></p><p class="muted">Create one to start assigning tasks.</p></div>`}</div>
          <form class="form panel" id="new-group" novalidate>
            <h2>Create a work group</h2>
            <div class="field"><label for="group_name">Name</label><input id="group_name" name="group_name" required></div>
            <div class="field"><label for="group_description">What does this group do?</label><textarea id="group_description" name="group_description" required></textarea></div>
            <div><button class="btn" type="submit">Create work group</button></div>
          </form>
        </div>
      </div>`);
    const form = document.getElementById('new-group');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const f = formData(form);
      if (!f.group_name || !f.group_description) { showError(form, 'Give the group a name and a description.'); return; }
      await withBusy(form.querySelector('button[type=submit]'), 'Creating…', async () => {
        try {
          const res = await api('create-workgroup-with-details/', { method: 'POST', body: { ...f, sub_dept_office: officeId() } });
          toast('Work group created.');
          location.hash = `#/groups/${res.data.work_group}`;
        } catch (err) { showError(form, err.message); }
      });
    });
  }

  async function viewGroup(groupId) {
    loadingShell();
    const [groups, members, tickets, users] = await Promise.all([
      api(`workgroups/?sub_dept_office=${officeId()}`).then((r) => r.data || []),
      api(`workgroup/${groupId}/members/`).then((r) => r.data || []),
      api(`workgroupticket/?work_group=${groupId}`).then((r) => r.data || []),
      api(`users/?sub_dept_office=${officeId()}`).then((r) => r.data || []),
    ]);
    const group = groups.find((g) => String(g.id) === groupId);
    if (!group) { renderShell(`<div class="page"><h1>Work group not found</h1><p class="muted" style="margin-top:8px"><a href="#/groups">Back to work groups</a></p></div>`); return; }
    const memberIds = new Set(members.map((m) => String(m.user_id)));
    const addable = users.filter((x) => !memberIds.has(String(x.id)));
    const nameOf = (uid) => { const x = users.find((y) => String(y.id) === String(uid)); return x ? x.name || x.cug_email_address : 'Unassigned'; };

    const ticketCard = (t) => {
      const i = STATUSES.indexOf(t.ticket_status);
      const next = STATUSES[i + 1];
      return `<div class="ticket">
        <div class="t">${esc(t.ticket_title)}</div>
        ${t.ticket_description ? `<div class="d">${esc(t.ticket_description)}</div>` : ''}
        <div class="foot"><span><span class="prio" data-p="${esc(t.ticket_priority)}">${esc(t.ticket_priority)}</span>, ${esc(nameOf(t.ticket_owner_id))}</span>
        ${next ? `<button class="btn quiet small" data-move="${t.id}" data-to="${next}">Mark ${next.toLowerCase()}</button>` : ''}</div>
      </div>`;
    };

    renderShell(`
      <div class="page">
        <p class="small" style="margin-bottom:14px"><a href="#/groups">Work groups</a></p>
        <div class="page-head"><div><h1>${esc(group.group_name)}</h1><p>${esc(group.group_description)}</p></div></div>

        <section class="section" aria-labelledby="tasks-h">
          <div class="section-head"><h2 id="tasks-h">Tasks</h2><span class="muted small">${tickets.length} in total</span></div>
          <div class="board">${STATUSES.map((s) => {
            const list = tickets.filter((t) => t.ticket_status === s);
            return `<div class="lane"><h3>${stamp(s)}<span class="n">${list.length}</span></h3>${list.map(ticketCard).join('') || '<p class="muted small">None</p>'}</div>`;
          }).join('')}</div>
        </section>

        <div class="two-col section">
          <form class="form panel" id="new-ticket" novalidate>
            <h2>Add a task</h2>
            <div class="field"><label for="ticket_title">Task</label><input id="ticket_title" name="ticket_title" required></div>
            <div class="field"><label for="ticket_description">Details</label><textarea id="ticket_description" name="ticket_description" required></textarea></div>
            <div class="form-grid">
              <div class="field"><label for="ticket_priority">Priority</label><select id="ticket_priority" name="ticket_priority"><option>High</option><option selected>Medium</option><option>Low</option></select></div>
              <div class="field"><label for="ticket_type">Type</label><select id="ticket_type" name="ticket_type"><option value="TaskAssign">Assigned task</option><option value="PreBuiltTemplate">Standard checklist</option><option value="CustomTemplate">Custom checklist</option></select></div>
              <div class="field full"><label for="ticket_owner_id">Assign to</label><select id="ticket_owner_id" name="ticket_owner_id">${users.map((x) => `<option value="${x.id}" ${String(x.id) === String(user().user_id) ? 'selected' : ''}>${esc(x.name || x.cug_email_address)}</option>`).join('')}</select></div>
            </div>
            <div><button class="btn" type="submit">Add task</button></div>
          </form>

          <section aria-labelledby="members-h">
            <div class="section-head"><h2 id="members-h">Members</h2></div>
            <div class="rows">${members.length ? members.map((m) => `
              <div class="row"><div><div class="title">${esc(m.name || m.email || m.user_id)}</div><div class="meta">${esc(m.role_name)}${m.role ? `, ${esc(ROLE_LABEL[m.role] || m.role)}` : ''}</div></div><div class="meta">Joined ${fmtDate(m.joined_at)}</div></div>`).join('') : '<div class="empty"><p class="muted">No members yet.</p></div>'}</div>
            ${addable.length ? `
            <form class="form" id="add-member" style="margin-top:16px" novalidate>
              <div class="form-grid">
                <div class="field"><label for="member">Add a member</label><select id="member" name="user_id">${addable.map((x) => `<option value="${x.id}">${esc(x.name || x.cug_email_address)}</option>`).join('')}</select></div>
                <div class="field"><label for="role_name">Role in group</label><input id="role_name" name="role_name" required placeholder="For example: Field inspector"></div>
              </div>
              <div><button class="btn secondary" type="submit">Add member</button></div>
            </form>` : '<p class="muted small" style="margin-top:12px">Everyone in this office is already a member.</p>'}
          </section>
        </div>
      </div>`);

    app.querySelectorAll('[data-move]').forEach((b) => b.addEventListener('click', () => withBusy(b, 'Saving…', async () => {
      try { await api(`workgroupticket/${b.dataset.move}/`, { method: 'PATCH', body: { ticket_status: b.dataset.to } }); toast(`Task marked ${b.dataset.to.toLowerCase()}.`); await viewGroup(groupId); }
      catch (err) { toast(err.message, true); }
    })));

    const tf = document.getElementById('new-ticket');
    tf.addEventListener('submit', async (e) => {
      e.preventDefault();
      const f = formData(tf);
      if (!f.ticket_title || !f.ticket_description) { showError(tf, 'Describe the task and add some details.'); return; }
      await withBusy(tf.querySelector('button[type=submit]'), 'Adding…', async () => {
        try { await api('workgroupticket/', { method: 'POST', body: { ...f, work_group: groupId, ticket_status: 'Created' } }); toast('Task added.'); await viewGroup(groupId); }
        catch (err) { showError(tf, err.message); }
      });
    });

    const mf = document.getElementById('add-member');
    mf?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const f = formData(mf);
      if (!f.role_name) { showError(mf, 'Give the member a role in this group.'); return; }
      await withBusy(mf.querySelector('button[type=submit]'), 'Adding…', async () => {
        try { await api('workgroupmembers/', { method: 'POST', body: { ...f, work_group: groupId } }); toast('Member added.'); await viewGroup(groupId); }
        catch (err) { showError(mf, err.message); }
      });
    });
  }

  /* ---------- organisation (admin) ---------- */
  async function viewOrg() {
    if (!isAdmin()) { renderShell(`<div class="page"><h1>Organisation</h1><p class="muted" style="margin-top:8px">Only an inspection cell admin can manage departments and offices.</p></div>`); return; }
    loadingShell();
    const [depts, subs, offices] = await Promise.all([
      api('tngovtdept/').then((r) => r.data || []),
      api('tngovtsubdept/').then((r) => r.data || []),
      api('subdeptofficedetails/').then((r) => r.data || []),
    ]);
    const deptName = (id) => depts.find((d) => String(d.id) === String(id))?.department_name || '';
    const subName = (id) => subs.find((s) => String(s.id) === String(id))?.sub_department_name || '';
    renderShell(`
      <div class="page">
        <div class="page-head"><div><h1>Organisation</h1><p>Departments, sub-departments and offices that officers can join.</p></div></div>
        <div class="three-col">
          <form class="form panel" data-kind="dept" novalidate>
            <h2>Add a department</h2>
            <div class="field"><label for="department_name">Name</label><input id="department_name" name="department_name" required></div>
            <div class="field"><label for="level">Level</label><select id="level" name="level"><option>State</option><option>District</option><option>Taluk</option></select></div>
            <div><button class="btn" type="submit">Add department</button></div>
          </form>
          <form class="form panel" data-kind="sub" novalidate>
            <h2>Add a sub-department</h2>
            <div class="field"><label for="department">Department</label><select id="department" name="department" required>${depts.map((d) => `<option value="${d.id}">${esc(d.department_name)}</option>`).join('')}</select></div>
            <div class="field"><label for="sub_department_name">Name</label><input id="sub_department_name" name="sub_department_name" required></div>
            <div><button class="btn" type="submit" ${depts.length ? '' : 'disabled'}>Add sub-department</button></div>
          </form>
          <form class="form panel" data-kind="office" novalidate>
            <h2>Add an office</h2>
            <div class="field"><label for="sub_dept">Sub-department</label><select id="sub_dept" name="sub_dept" required>${subs.map((s) => `<option value="${s.id}">${esc(s.sub_department_name)}</option>`).join('')}</select></div>
            <div class="field"><label for="sub_dept_office_location">Office name</label><input id="sub_dept_office_location" name="sub_dept_office_location" required></div>
            <div class="field"><label for="sub_dept_street_address">Street address</label><input id="sub_dept_street_address" name="sub_dept_street_address" required></div>
            <div class="form-grid">
              <div class="field"><label for="sub_dept_district">District</label><input id="sub_dept_district" name="sub_dept_district" required></div>
              <div class="field"><label for="sub_dept_taluk">Taluk</label><input id="sub_dept_taluk" name="sub_dept_taluk" required></div>
            </div>
            <div class="field"><label for="sub_dept_access_code">Office code</label><input id="sub_dept_access_code" name="sub_dept_access_code" required><span class="hint">Must be unique, e.g. PHC-CHN-EGM.</span></div>
            <div><button class="btn" type="submit" ${subs.length ? '' : 'disabled'}>Add office</button></div>
          </form>
        </div>
        <section class="section" aria-labelledby="offices-h">
          <div class="section-head"><h2 id="offices-h">Offices</h2><span class="muted small">${offices.length} in total</span></div>
          <div class="rows" style="overflow-x:auto">
            <table class="responsive"><thead><tr><th>Office</th><th>Sub-department</th><th>Department</th><th>District</th><th>Code</th></tr></thead>
            <tbody>${offices.map((o) => {
              const sub = subs.find((s) => String(s.id) === String(o.sub_dept));
              return `<tr><td><strong>${esc(o.sub_dept_office_location)}</strong></td><td>${esc(subName(o.sub_dept))}</td><td>${esc(deptName(sub?.department))}</td><td>${esc(o.sub_dept_district)}</td><td>${esc(o.sub_dept_access_code)}</td></tr>`;
            }).join('') || '<tr><td colspan="5" class="muted">No offices yet.</td></tr>'}</tbody></table>
          </div>
        </section>
      </div>`);
    const endpoints = { dept: ['tngovtdept/', 'Department added.'], sub: ['tngovtsubdept/', 'Sub-department added.'], office: ['subdeptofficedetails/', 'Office added.'] };
    app.querySelectorAll('form[data-kind]').forEach((form) => form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const f = formData(form);
      if ([...form.querySelectorAll('[required]')].some((el) => !el.value.trim())) { showError(form, 'Fill in every field.'); return; }
      const [path, done] = endpoints[form.dataset.kind];
      await withBusy(form.querySelector('button[type=submit]'), 'Adding…', async () => {
        try { await api(path, { method: 'POST', body: f }); toast(done); await viewOrg(); }
        catch (err) { showError(form, err.message); }
      });
    }));
  }

  router();
})();

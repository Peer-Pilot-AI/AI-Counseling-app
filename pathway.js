/* PeerPilot AI — "Pathway" layer.
   Loads AFTER app.js and peerpilot.js (see index.html). It plugs into the same
   hooks those files use (render, nav, setupNav, authPage, dashboardPage, ...), so
   nothing in app.js or peerpilot.js has to change.

   What lives here:
   1. Light / dark theme switching
   2. The 10-tab sidebar (+ sub-tabs for related pages)
   3. Login page, dashboard, and the Duolingo-style roadmap
   4. Welcome survey (first sign-in)
*/
(function () {
  if (window.__pathwayLoaded) return; /* guards against this file being loaded or pasted twice */
  window.__pathwayLoaded = true;
  /* If the page body was pasted twice, keep only the first copy of the app shell. */
  document.querySelectorAll(".app-shell").forEach((el, i) => i && el.remove());
  ["modalBackdrop", "toast"].forEach((id) => document.querySelectorAll("#" + id).forEach((el, i) => i && el.remove()));
  const arr = (v) => (Array.isArray(v) ? v : []);

  /* ================================================================
     1. ICONS
     ================================================================ */
  const svg = (d) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${d}</svg>`;
  const I = {
    home: svg('<path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>'),
    route: svg('<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>'),
    sparkles: svg('<path d="M11 3l1.9 5.4L18.5 10l-5.6 1.6L11 17l-1.9-5.4L3.5 10l5.6-1.6z"/><path d="M19 15l.8 2.2 2.2.8-2.2.8L19 21l-.8-2.2-2.2-.8 2.2-.8z"/>'),
    cap: svg('<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c0 1.5 3 3 6 3s6-1.5 6-3v-5"/>'),
    compass: svg('<circle cx="12" cy="12" r="9"/><path d="m15.6 8.4-2.1 5.1-5.1 2.1 2.1-5.1z"/>'),
    trophy: svg('<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4v1a4 4 0 0 0 4 4M16 6h4v1a4 4 0 0 1-4 4M12 13v4M8 21h8M10 17h4"/>'),
    star: svg('<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>'),
    users: svg('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><circle cx="17.5" cy="9" r="2.5"/><path d="M17 14c2.7.2 4.5 2.2 4.5 5"/>'),
    tasks: svg('<rect x="3.5" y="3.5" width="17" height="17" rx="3"/><path d="m8 12 3 3 5-6"/>'),
    user: svg('<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/>'),
    sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    moon: svg('<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'),
    logout: svg('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>'),
    menu: svg('<path d="M4 6h16M4 12h16M4 18h16"/>'),
    mail: svg('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>'),
    lock: svg('<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>'),
    eye: svg('<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
    target: svg('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>'),
    brief: svg('<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18"/>'),
    doc: svg('<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>'),
    book: svg('<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5"/>'),
    send: svg('<path d="m22 2-11 11M22 2l-7 20-4-9-9-4z"/>'),
    arrow: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
    check: svg('<path d="m5 12.5 4.5 4.5L19 7.5"/>'),
    plus: svg('<path d="M12 5v14M5 12h14"/>'),
    chest: svg('<rect x="3" y="9" width="18" height="11" rx="2"/><path d="M3 12h18M5 9a7 5 0 0 1 14 0M12 12v3"/>'),
    flag: svg('<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>'),
    flask: svg('<path d="M9 3h6M10 3v6L4.5 19a1.5 1.5 0 0 0 1.3 2h12.4a1.5 1.5 0 0 0 1.3-2L14 9V3"/><path d="M7.5 15h9"/>'),
    pen: svg('<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>'),
    cal: svg('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>'),
    dollar: svg('<circle cx="12" cy="12" r="9"/><path d="M14.5 9.2a2.6 2.1 0 0 0-2.5-1.4c-1.4 0-2.5.8-2.5 2s1.1 1.6 2.5 2 2.5.8 2.5 2-1.1 2-2.5 2a2.6 2.1 0 0 1-2.5-1.4M12 6v1.8M12 16.2V18"/>'),
    sliders: svg('<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>'),
    bell: svg('<path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7 2.5 7h-17S6 15 6 9z"/><path d="M10 20a2 2 0 0 0 4 0"/>'),
    chev: svg('<path d="m9 6 6 6-6 6"/>'),
    chevron: svg('<path d="m6 9 6 6 6-6"/>'),
  };

  /* ================================================================
     2. THEME  (light / dark, remembers the choice, follows the system on first visit)
     ================================================================ */
  const THEME_KEY = "peerpilot-theme";
  const readTheme = () => {
    try {
      const t = localStorage.getItem(THEME_KEY);
      return t === "light" || t === "dark" ? t : null;
    } catch (e) {
      return null;
    }
  };
  const systemTheme = () =>
    window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

  const pref = (k) => { try { return localStorage.getItem("peerpilot-pref-" + k) !== "off"; } catch (e) { return true; } };
  const ACCENTS = { blue: "#3d78ff", purple: "#8b5cf6", teal: "#14b8a6", pink: "#ef4f7b", orange: "#f59e0b" };
  function applyAccent(name) {
    const r = document.documentElement.style;
    const keys = ["--primary", "--primary-2", "--primary-hover", "--primary-soft", "--primary-text"];
    if (!ACCENTS[name] || name === "blue") keys.forEach((k) => r.removeProperty(k));
    else {
      const c = ACCENTS[name];
      const dark = document.documentElement.dataset.theme === "dark";
      r.setProperty("--primary", c);
      r.setProperty("--primary-2", `color-mix(in srgb, ${c} 80%, white)`);
      r.setProperty("--primary-hover", `color-mix(in srgb, ${c} 85%, black)`);
      r.setProperty("--primary-soft", `color-mix(in srgb, ${c} ${dark ? 18 : 13}%, transparent)`);
      r.setProperty("--primary-text", dark ? `color-mix(in srgb, ${c} 55%, white)` : `color-mix(in srgb, ${c} 78%, black)`);
    }
    document.querySelectorAll("[data-accent]").forEach((b) => b.setAttribute("aria-pressed", String((name || "blue") === b.dataset.accent)));
  }
  const readAccent = () => { try { return localStorage.getItem("peerpilot-accent") || "blue"; } catch (e) { return "blue"; } };
  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-accent]");
    if (a) { try { localStorage.setItem("peerpilot-accent", a.dataset.accent); } catch (x) {} applyAccent(a.dataset.accent); }
    const p = e.target.closest("[data-pref]");
    if (p) { const on = pref(p.dataset.pref); try { localStorage.setItem("peerpilot-pref-" + p.dataset.pref, on ? "off" : "on"); } catch (x) {} render(); }
  });
  const MODE_KEY = "peerpilot-theme-mode";
  const readMode = () => { try { return localStorage.getItem(MODE_KEY); } catch (e) { return null; } };
  function syncThemeButtons() {
    const mode = readMode() === "system" ? "system" : document.documentElement.dataset.theme;
    document.querySelectorAll("[data-theme-choice]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.themeChoice === mode)));
  }
  applyTheme = function (theme, announce) {
    const sys = theme === "system";
    const t = sys ? systemTheme() : theme === "light" ? "light" : "dark";
    const root = document.documentElement;
    root.dataset.theme = t;
    root.style.colorScheme = t;
    root.classList.toggle("pp-dark", t === "dark");
    if (document.body) document.body.dataset.theme = t;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", t === "dark" ? "#070d22" : "#f4f7ff");
    try {
      localStorage.setItem(THEME_KEY, t);
      localStorage.setItem(MODE_KEY, sys ? "system" : "fixed");
    } catch (e) {}
    syncThemeButtons();
    applyAccent(readAccent());
    const toggle = document.getElementById("themeToggle");
    if (toggle) toggle.setAttribute("aria-label", t === "dark" ? "Switch to light mode" : "Switch to dark mode");
    if (announce) toast(sys ? "Following your device" : `${t === "light" ? "Light" : "Dark"} mode on`);
  };
  if (window.matchMedia)
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => readMode() === "system" && applyTheme("system"));

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-theme-toggle]")) {
      applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", true);
    }
  });

  /* ================================================================
     3. SIDEBAR: 10 tabs max. Related pages share a tab and show sub-tabs.
     ================================================================ */
  const TABS = [
    { id: "dashboard", label: "Dashboard", icon: "home", pages: ["dashboard", "advisor", "calendar", "tasks"], extra: '<span class="count" id="taskCount">0</span>' },
    { id: "roadmap", label: "My Roadmap", icon: "route", pages: ["roadmap"] },
    { id: "courses", label: "Courses", icon: "book", pages: ["courses", "tutor", "studyPlan"] },
    { id: "goals", label: "Goals", icon: "target", pages: ["goals"] },
    { id: "activities", label: "Activities", icon: "star", pages: ["activities"] },
    { id: "planning", label: "College Planning", icon: "cap", pages: ["colleges", "resources"] },
    { id: "scholarships", label: "Scholarships", icon: "dollar", pages: ["deadlines"], extra: '<span class="count warn" id="ppDeadlineCount" style="display:none">0</span>' },
    { id: "applications", label: "Applications", icon: "doc", pages: ["applications", "essays"] },
    { id: "career", label: "Career", icon: "brief", pages: ["careers", "opportunities", "mentors"] },
    { id: "me", label: "Settings", icon: "sliders", pages: ["profile", "memory", "feedback", "admin"] },
  ];
  const LABELS = {
    dashboard: "Overview",
    goals: "Goals",
    courses: "Courses",
    activities: "Activities",
    roadmap: "My roadmap",
    colleges: "College list",
    opportunities: "Internships",
    careers: "Career explorer",
    applications: "Applications",
    calendar: "Calendar",
    tasks: "Tasks",
    resources: "Resources",
    deadlines: "Dates & scholarships",
    mentors: "Peer mentors",
    advisor: "AI Assistant",
    tutor: "Study tutor",
    studyPlan: "Study planner",
    essays: "Essay feedback",
    profile: "My profile",
    memory: "What AI remembers",
    feedback: "Report a problem",
    admin: "Admin",
  };

  function buildNav() {
    const navEl = document.getElementById("mainNav");
    if (!navEl) return;
    const bt = document.querySelector(".brand-text b");
    if (bt && !bt.querySelector("span")) bt.innerHTML = "PeerPilot <span>AI</span>";
    const foot = document.querySelector(".sidebar-foot");
    if (foot && !document.querySelector(".side-tag")) foot.insertAdjacentHTML("beforebegin", '<div class="side-tag"><i></i>Plan today.<br>Build tomorrow.</div>');
    const tr = document.querySelector(".topbar-right");
    if (tr && !document.getElementById("bellBtn")) tr.insertAdjacentHTML("afterbegin", `<button class="icon-btn bell" id="bellBtn" data-page="calendar" aria-label="Upcoming deadlines">${I.bell}<i hidden></i></button>`);
    const tasksCount = document.getElementById("taskCount");
    const keep = tasksCount ? tasksCount.textContent : "0";
    navEl.innerHTML = TABS.map(
      (t) =>
        `<button class="nav-item" data-page="${t.pages[0]}" data-tab="${t.id}"><span class="nav-ico">${I[t.icon]}</span><span class="nav-text">${t.label}</span>${t.extra || ""}</button>`,
    ).join("");
    const c = document.getElementById("taskCount");
    if (c) c.textContent = keep;
  }
  function bindChrome() {
    const out = document.getElementById("logoutButton");
    if (out) out.remove(); /* Sign out lives only in Settings */
    const scrim = document.getElementById("scrim");
    if (scrim && !scrim.dataset.bound) {
      scrim.dataset.bound = "1";
      scrim.addEventListener("click", closeDrawer);
    }
  }
  function closeDrawer() {
    const s = document.getElementById("sidebar");
    if (s) s.classList.remove("open");
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-signout]")) logout();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });

  setupNav = function () {
    buildNav();
    bindChrome();
  };

  function hubBar() {
    const tab = TABS.find((t) => t.pages.includes(activePage));
    if (!tab) return "";
    const pages = tab.pages.filter((p) => p !== "admin" || (currentUser && currentUser.is_admin));
    if (pages.length < 2) return "";
    return `<div class="hub-tabs" role="tablist" aria-label="${tab.label}">${pages
      .map(
        (p) =>
          `<button class="hub-tab${p === activePage ? " active" : ""}" role="tab" aria-selected="${p === activePage}" data-page="${p}">${LABELS[p]}</button>`,
      )
      .join("")}</div>`;
  }
  function decorate() {
    const tab = TABS.find((t) => t.pages.includes(activePage)) || TABS[0];
    syncThemeButtons();
    const dot = document.querySelector("#bellBtn i");
    if (dot) dot.hidden = !calEvents().some((e) => e.d >= ymd(new Date()) && e.d <= ymd(new Date(Date.now() + 7 * 864e5)));
    if (activePage === "opportunities") applyOppFilter();
    document.querySelectorAll("#mainNav .nav-item").forEach((b) => {
      const on = b.dataset.tab === tab.id;
      b.classList.toggle("active", on);
      if (on) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    const crumb = document.getElementById("crumbCurrent");
    if (crumb) crumb.textContent = LABELS[activePage] || tab.label;
    document.title = `${LABELS[activePage] || tab.label} · PeerPilot AI`;
    const root = document.getElementById("pageContainer");
    document.querySelectorAll(".hub-tabs").forEach((el) => el.remove());
    const bar = hubBar();
    if (root && bar) root.insertAdjacentHTML("afterbegin", bar);
    const hu = root && root.querySelector(":scope > .pp-heads-up");
    const ttl = root && root.querySelector(".dash-title");
    if (hu && ttl) ttl.after(hu);
  }

  /* ================================================================
     4. DATA FOR THE ROADMAP AND DASHBOARD
     ================================================================ */
  const GRADE_NAMES = { 9: "Freshman", 10: "Sophomore", 11: "Junior", 12: "Senior" };
  const GRADE_HINTS = {
    9: "Build your foundation",
    10: "Explore and get involved",
    11: "Take the lead",
    12: "Apply and make it happen",
  };
  const STEPS = {
    9: () => [
      "Build a strong academic foundation",
      "Explore subjects and activities that interest you",
      "Learn how your school's graduation path works",
      "Join one club, team or project",
      "Set a simple weekly study routine",
    ],
    10: (m) => [
      `Explore ${m} through a project or activity`,
      "Look ahead to what junior year will ask of you",
      "Start a low-pressure college exploration list",
      "Take on a role in an activity you care about",
      "Visit a college fair or take a virtual tour",
    ],
    11: () => [
      "Talk with your counselor about testing and your plan",
      "Explore colleges and compare official program information",
      "Reflect on meaningful activities and summer plans",
      "Ask teachers about recommendation letters",
      "Start scholarship research and a first essay draft",
    ],
    12: () => [
      "Build an application timeline with your counselor",
      "Review official college and scholarship deadlines",
      "Compare financial aid options and make an informed choice",
      "Draft and polish your essays",
      "Submit your applications and celebrate",
    ],
  };
  function pathProgress() {
    const p = state.profile || {};
    const grade = Number(p.grade) || 9;
    const major = String(p.major || "").trim() || "your interests";
    const years = [9, 10, 11, 12].map((g) => ({ grade: g, name: GRADE_NAMES[g], hint: GRADE_HINTS[g], items: STEPS[g](major) }));
    const done = arr(state.completedRoadmap);
    let current = null;
    let total = 0;
    let finished = 0;
    years.forEach((y) =>
      y.items.forEach((title, i) => {
        total++;
        const id = `${y.grade}-${i}`;
        if (done.includes(id)) finished++;
        else if (!current && y.grade >= grade) current = { id, title, grade: y.grade, index: i, year: y.name };
      }),
    );
    return { years, done, grade, total, finished, current, pct: total ? Math.round((finished / total) * 100) : 0 };
  }

  /* ================================================================
     5. LOGIN PAGE
     ================================================================ */
  authPage = function () {
    const mode = selectedAuthMode;
    const registering = mode === "register";
    const title = registering
      ? "Create your account"
      : mode === "reset"
        ? "Reset your password"
        : mode === "request-reset"
          ? "Forgot your password?"
          : "Welcome back";
    const sub = registering
      ? "Start planning your path from high school to college."
      : mode === "reset"
        ? "Enter your reset code and choose a new password."
        : mode === "request-reset"
          ? "Enter your email and we will send reset instructions."
          : "Log in to pick up your journey where you left off.";
    const emailField = `<div class="pwa-input">${I.mail}<input name="email" type="email" placeholder="Email address" aria-label="Email address" autocomplete="email" required></div>`;
    const eye = `<button type="button" class="pwa-eye" aria-label="Show or hide password" onclick="var i=this.parentElement.querySelector('input');i.type=i.type==='password'?'text':'password'">${I.eye}</button>`;
    const pwField = (ph, ac) =>
      `<div class="pwa-input">${I.lock}<input name="password" type="password" minlength="10" placeholder="${ph}" aria-label="${ph}" autocomplete="${ac}" required>${eye}</div>`;
    let fields = emailField;
    if (mode === "reset")
      fields += `<div class="pwa-input">${I.lock}<input name="token" placeholder="Reset code" aria-label="Reset code" autocomplete="one-time-code"></div>${pwField("New password", "new-password")}<p class="pwa-hint">At least 10 characters.</p>`;
    else if (mode !== "request-reset")
      fields +=
        pwField("Password", registering ? "new-password" : "current-password") +
        (registering ? '<p class="pwa-hint">At least 10 characters.</p>' : "");
    const consents = registering
      ? `<div class="legal-consents"><label class="consent-row"><input type="checkbox" name="legal_agreement" required><span>I agree to the <a href="/terms.html" target="_blank" rel="noopener">Terms of Service</a> and acknowledge the <a href="/privacy.html" target="_blank" rel="noopener">Privacy Notice</a> (versions ${TERMS_VERSION} and ${PRIVACY_VERSION}).</span></label><label class="consent-row"><input type="checkbox" name="age_13_plus" required><span>I am at least 13 years old. Children under 13 may not create an account.</span></label><label class="consent-row"><input type="checkbox" name="guardian_permission" required><span>If I am under 18, my parent or guardian has reviewed these documents and given permission for me to use this app.</span></label></div>`
      : "";
    const goText = registering
      ? "Create account"
      : mode === "reset"
        ? "Save new password"
        : mode === "request-reset"
          ? "Send reset instructions"
          : "Log in";
    const forgot =
      mode === "login"
        ? `<div class="pwa-row"><button type="button" class="pwa-link" data-auth-mode="request-reset">Forgot password?</button></div>`
        : "";
    const bottom =
      mode === "login"
        ? `<p class="pwa-switch">New here? <button type="button" class="pwa-link" data-auth-mode="register">Create an account</button></p>`
        : `<p class="pwa-switch"><button type="button" class="pwa-link" data-auth-mode="login">Back to log in</button>${mode === "request-reset" ? ' &nbsp;·&nbsp; <button type="button" class="pwa-link" data-auth-mode="reset">I have a reset code</button>' : ""}</p>`;
    return `<div class="pwa-shell">
      <section class="pwa-hero">
        <div class="pwa-brandline"><img src="/assets/logo.png" alt=""><span>PeerPilot AI</span></div>
        <div class="pwa-copy">
          <h1>Your future.<span>One step closer.</span></h1>
          <p>Map your path, reach your goals, and get personalized guidance from high school to college and beyond.</p>
          <ul class="pwa-feats">
            <li>${I.route}<span>Follow your<br>roadmap</span></li>
            <li>${I.target}<span>Set<br>goals</span></li>
            <li>${I.trophy}<span>Find<br>opportunities</span></li>
            <li>${I.sparkles}<span>Ask your<br>AI coach</span></li>
          </ul>
        </div>
        <div class="pwa-trail" aria-hidden="true">
          <span class="d d1">${I.check}</span><span class="d d2">${I.check}</span><span class="d d3">${I.star}</span><span class="d d4">${I.flag}</span><span class="d d5">${I.chest}</span>
        </div>
      </section>
      <section class="pwa-formside">
        <button type="button" class="icon-btn pwa-theme" data-theme-toggle aria-label="Switch theme"><span class="ico-sun">${I.sun}</span><span class="ico-moon">${I.moon}</span></button>
        <div class="pwa-card">
          <div class="pwa-usericon">${I.user}</div>
          <h2>${title}</h2>
          <p class="pwa-sub">${sub}</p>
          <form id="authForm" class="pwa-form">${fields}${consents}${forgot}<button class="pwa-go">${goText} ${I.arrow}</button></form>
          ${bottom}
          <p class="pwa-fine">Do not enter sensitive personal information. School-specific plans should be reviewed with a counselor.</p>
        </div>
      </section>
    </div>`;
  };

  /* ================================================================
     6. DASHBOARD
     ================================================================ */
  /* progress history: one snapshot per day, kept in this browser, so the chart only shows real data */
  let progRange = 30;
  function recordProgress(c, g) {
    const key = "peerpilot-progress:" + ((currentUser && (currentUser.email || currentUser.id)) || "me");
    let list = [];
    try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) {}
    const today = ymd(new Date());
    const last = list[list.length - 1];
    if (last && last.d === today) { last.c = c; last.g = g; } else list.push({ d: today, c, g });
    list = list.slice(-400);
    try { localStorage.setItem(key, JSON.stringify(list)); } catch (e) {}
    return list;
  }
  function chartSvg(list) {
    const W = 600, H = 250, L = 44, R = 14, T = 12, B = 30;
    const end = new Date(); end.setHours(12, 0, 0, 0);
    const start = new Date(end); start.setDate(end.getDate() - progRange);
    const x = (d) => L + ((parseD(d) - start) / (end - start || 1)) * (W - L - R);
    const y = (v) => T + (1 - v / 100) * (H - T - B);
    const pts = list.filter((p) => parseD(p.d) >= start);
    const grid = [0, 25, 50, 75, 100].map((v) => `<line class="gl" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="gt" x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`).join("");
    const xl = [0, 1, 2, 3, 4].map((i) => { const d = new Date(start.getTime() + ((end - start) * i) / 4); return `<text class="gt" x="${L + ((W - L - R) * i) / 4}" y="${H - 8}" text-anchor="${i === 4 ? "end" : "middle"}">${d.toLocaleString("en-US", progRange > 60 ? { month: "short" } : { month: "short", day: "numeric" })}</text>`; }).join("");
    const line = (key, cls) => {
      if (!pts.length) return "";
      const P = pts.map((p) => [x(p.d), y(p[key])]);
      if (P.length === 1) return `<circle class="dot ${cls}" cx="${P[0][0]}" cy="${P[0][1]}" r="5"/>`;
      let d = `M${P[0][0]} ${P[0][1]}`;
      for (let i = 1; i < P.length; i++) { const mx = (P[i - 1][0] + P[i][0]) / 2; d += ` C${mx} ${P[i - 1][1]} ${mx} ${P[i][1]} ${P[i][0]} ${P[i][1]}`; }
      const area = `${d} L${P[P.length - 1][0]} ${y(0)} L${P[0][0]} ${y(0)} Z`;
      return `<path class="area ${cls}" d="${area}"/><path class="ln ${cls}" d="${d}"/><circle class="dot ${cls}" cx="${P[P.length - 1][0]}" cy="${P[P.length - 1][1]}" r="4.5"/>`;
    };
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Course and goals progress over time">${grid}${xl}${line("c", "c1")}${line("g", "c2")}</svg>`;
  }
  
  const YEAR_ICON = [["cap", "y1"], ["doc", "y2"], ["user", "y3"], ["star", "y4"]];

  dashboardPage = function () {
    const p = state.profile;
    const pr = pathProgress();
    const cap = (n, max) => Math.min(100, Math.round((n / max) * 100));
    const grade = Number(p.grade) || 9;
    const courses = arr(p.courses).map((c) => norm(c, false));
    const nCourses = courses.length + arr(p.planned).length;
    const doneCourses = courses.filter((c) => Number(c.year) && Number(c.year) < grade).length;
    const coursePct = nCourses ? Math.round((doneCourses / nCourses) * 100) : 0;
    const yearsDone = pr.years.filter((y) => y.items.every((_, i) => pr.done.includes(`${y.grade}-${i}`))).length;
    const roadPct = Math.round((yearsDone / 4) * 100);
    const gpa = parseFloat(p.gpa);
    const goalPct = Math.round(((isNaN(gpa) ? 0 : cap(gpa, 3.8)) + cap(arr(state.savedColleges).length, 5) + cap(arr(p.internships).length, 2) + cap(arr(state.applications).length, 5)) / 4);
    const nSch = arr(opportunities).filter((o) => /scholar/i.test(o.category || "")).length;
    const today = new Date();
    const in30 = ymd(new Date(today.getTime() + 30 * 864e5));
    const nDue = calEvents().filter((e) => e.d >= ymd(today) && e.d <= in30).length;
    const hist = recordProgress(coursePct, goalPct);

    const stat = (cls, ic, name, big, sub, pill, bar, page) =>
      `<button class="dash-stat" data-page="${page}"><span class="dash-stat-top"><span class="dash-ico ${cls}">${I[ic]}</span><b>${name}</b></span><span class="dash-big">${big}${pill ? `<em class="dash-pill ${cls}">${pill}</em>` : ""}</span><small>${sub}</small>${bar !== null ? `<span class="dash-bar"><i class="${cls}" style="width:${bar}%"></i></span>` : `<span class="dash-go">${I.chev}</span>`}</button>`;
    const stats = [
      stat("s1", "book", "Course Progress", `${doneCourses} / ${nCourses}`, "courses completed", `${coursePct}%`, coursePct, "courses"),
      stat("s2", "target", "Roadmap Milestones", `${yearsDone} / 4`, "completed", `${roadPct}%`, roadPct, "roadmap"),
      stat("s3", "cap", "Scholarships", nSch, "matched for you", "", null, "deadlines"),
      stat("s4", "cal", "Upcoming Deadlines", nDue, "in the next 30 days", "", null, "calendar"),
    ].join("");

    const ranges = [[30, "1M"], [90, "3M"], [180, "6M"], [365, "1Y"]];
    const chart = `<section class="dash-card dash-chart"><div class="dash-head"><h2><span class="dash-h-ico">${I.route}</span>Your Progress</h2><div class="dash-range" role="group" aria-label="Time range">${ranges.map(([d, l]) => `<button data-prog-range="${d}" aria-pressed="${progRange === d}">${l}</button>`).join("")}</div></div>
      <div class="dash-chart-body"><div class="dash-svg">${chartSvg(hist)}</div><div class="dash-note"><strong><i></i>${coursePct || roadPct ? "You're on track!" : "Let's get started"}</strong><p>${nCourses ? `You've completed ${coursePct}% of your courses and ${roadPct}% of your roadmap milestones.` : `Add your courses and check off roadmap steps to see your progress here.`}</p></div></div>
      <div class="dash-legend"><span><i class="c1"></i>Course Progress</span><span><i class="c2"></i>Goals Progress</span></div></section>`;

    const road = `<section class="dash-card dash-road"><div class="dash-head"><h2><span class="dash-h-ico">${I.cap}</span>College Roadmap</h2><a href="#roadmap" data-page="roadmap">View Full Roadmap ${I.chev}</a></div><div class="dash-years">${pr.years
      .map((y, k) => {
        const [ic, c] = YEAR_ICON[k];
        const two = y.items.slice(0, 2).map((t, i) => { const d = pr.done.includes(`${y.grade}-${i}`); return `<li class="${d ? "done" : ""}"><span>${d ? I.check : ""}</span>${esc(t)}</li>`; }).join("");
        return `<div class="dash-year"><span class="dash-node ${c}">${I[ic]}</span><b>${y.name}</b><ul>${two}</ul></div>`;
      })
      .join("")}</div></section>`;

    const prompts = [["sparkles", "Help me choose the best colleges for my major"], ["book", "Create a study plan for my upcoming exams"], ["target", "Suggest scholarships I might be eligible for"], ["brief", "Explore career options based on my interests"]];
    const ai = `<aside class="dash-card dash-ai"><div class="dash-ai-head"><span class="dash-bot">${I.sparkles}</span><h2>AI Study &amp; Planning Assistant</h2><em>Powered by AI</em></div>${prompts.map(([ic, t]) => `<button class="dash-prompt" data-ai-prompt="${esc(t)}"><span>${I[ic]}</span>${t}<i>${I.chev}</i></button>`).join("")}<button class="dash-ask" data-page="advisor">${I.sparkles} Ask AI</button></aside>`;

    return `<div class="dash">
      <div class="dash-title"><h1>Welcome back, ${esc(p.firstName || "there")}</h1><p>Your next step starts here.${svFresh(p) ? ' <button class="text-link" data-pp-survey>Take the 2-minute welcome survey</button>' : ""}</p></div>
      <div class="dash-stats">${stats}</div>
      <div class="dash-cols"><div class="dash-left">${pref("tips") ? chart : ""}${road}</div>${pref("recs") ? ai : ""}</div>
    </div>`;
  };
  document.addEventListener("click", (e) => {
    const r = e.target.closest("[data-prog-range]");
    if (r) { progRange = Number(r.dataset.progRange); render(); }
    const a = e.target.closest("[data-ai-prompt]");
    if (a) {
      nav("advisor");
      const box = document.getElementById("chatInput");
      if (box) { box.value = a.dataset.aiPrompt; sendChat(); }
    }
  });

  /* ================================================================
     7. ROADMAP  (Duolingo-style path)
     ================================================================ */
  roadmapPage = function () {
    const pr = pathProgress();
    const xs = [0, 46, 78, 46, 0, -46, -78, -46];
    let k = 0;
    const nextX = () => xs[k++ % xs.length];

    const units = pr.years
      .map((y, ui) => {
        const g = y.grade;
        const isNow = g === pr.grade;
        const stepsDone = y.items.filter((_, i) => pr.done.includes(`${g}-${i}`)).length;
        const steps = y.items
          .map((title, i) => {
            const id = `${g}-${i}`;
            const isDone = pr.done.includes(id);
            const isCur = pr.current && pr.current.id === id;
            const cls = isDone ? "done" : isCur ? "now" : "todo";
            const bubble = isCur ? '<div class="cm-bubble">Start here</div>' : "";
            return `<div class="cm-n step ${cls}${g > pr.grade ? " later" : ""}" style="--x:${nextX()}px">${bubble}<button class="cm-disc" data-action="roadmap-toggle" data-id="${id}" aria-pressed="${isDone}" aria-label="${isDone ? "Mark not done" : "Mark done"}: ${esc(title)}">${isDone ? I.check : I.star}</button><div class="cm-lbl wide"><strong>${esc(title)}</strong><span>Step ${i + 1} of ${y.items.length}</span></div></div>`;
          })
          .join("");
        const unlocked = y.items.length > 0 && stepsDone === y.items.length;
        const chest = `<div class="cm-n cm-chest ${unlocked ? "done" : "next"}" style="--x:${nextX()}px"><div class="cm-disc">${I.chest}</div><div class="cm-lbl"><strong>${unlocked ? "Year complete!" : "Finish every step to unlock"}</strong></div></div>`;
        return `<section class="cm-unit-wrap"><header class="cm-unit u${ui + 1}${g > pr.grade ? " next" : ""}"><div><small>Unit ${ui + 1} · Grade ${g}${isNow ? " · you are here" : ""}</small><h2>${y.name} year</h2><p>${y.hint}</p></div><div class="cm-count"><b>${stepsDone}/${y.items.length}</b><span>steps</span></div></header><div class="cm-path">${steps}${chest}</div></section>`;
      })
      .join("");

    const allDone = pr.total > 0 && pr.finished === pr.total;
    const finale = `<section class="cm-unit-wrap"><div class="cm-path"><div class="cm-n cm-chest ${allDone ? "done" : "next"} cm-final" style="--x:0px"><div class="cm-disc">${I.trophy}</div><div class="cm-lbl"><strong>College</strong><span>${allDone ? "You made it. Your next chapter starts here." : "Your next chapter"}</span></div></div></div></section>`;

    const cy = pr.years.find((y) => y.grade === pr.grade) || pr.years[0];
    const cdone = cy.items.filter((_, i) => pr.done.includes(`${cy.grade}-${i}`)).length;
    const ci = Math.min(cy.items.findIndex((_, i) => !pr.done.includes(`${cy.grade}-${i}`)) < 0 ? cy.items.length - 1 : cy.items.findIndex((_, i) => !pr.done.includes(`${cy.grade}-${i}`)), cy.items.length - 1);
    const cid = `${cy.grade}-${ci}`;
    const cdn = pr.done.includes(cid);
    const stepper = `<section class="pw-panel cm-stepper"><div class="cm-st-row">${cy.items
      .map((t, i) => {
        const d = pr.done.includes(`${cy.grade}-${i}`);
        return `<button class="cm-st${d ? " done" : i === ci ? " now" : ""}" data-action="roadmap-toggle" data-id="${cy.grade}-${i}"><span class="cm-st-dot">${d ? I.check : i + 1}</span><small>${esc(t)}</small></button>`;
      })
      .join("")}</div><div class="cm-st-card"><div><strong>Step ${ci + 1}: ${esc(cy.items[ci])}</strong><p>${cy.name} year · ${cy.hint}</p></div><button class="btn btn-primary" data-action="roadmap-toggle" data-id="${cid}">${cdn ? "Undo" : "Mark done"}</button></div><div class="cm-st-bar"><i style="width:${Math.round((cdone / cy.items.length) * 100)}%"></i></div><small class="cm-st-count">${cdone} of ${cy.items.length} steps</small></section>`;
    const major = esc(state.profile.major || "your interests");
    return `<div class="cm-head"><div><h1 class="cm-title">My roadmap</h1><p class="cm-sub">Tap a step to mark it done. Every path is different, so adjust yours as your plans change.</p></div><button class="btn btn-primary" data-page="advisor">${I.sparkles} Ask your coach</button></div>
    ${stepper}<div class="cm-layout">
      <div class="cm-map">${units}${finale}</div>
      <aside class="cm-side">
        <section class="pw-panel rm-progress"><div class="rm-ring" style="--pct:${pr.pct}"><b>${pr.pct}%</b></div><div><strong>${pr.finished} of ${pr.total} steps</strong><p class="cm-note">${pr.pct === 100 ? "Every step is done. Nice work." : "Finish a year to open its reward chest."}</p></div></section>
        <section class="pw-panel"><div class="pw-head"><h2>Key</h2></div>
          <div class="cm-leg"><span class="d done"></span>Done</div>
          <div class="cm-leg"><span class="d now"></span>Your next step</div>
          <div class="cm-leg"><span class="d todo"></span>Still to do</div>
          <div class="cm-leg"><span class="d next"></span>Locked reward</div>
        </section>
        <section class="pw-panel"><div class="pw-head"><h2>${I.sparkles} Planning tip</h2></div><p class="cm-note">Look for classes, clubs and projects connected to ${major} if your school offers them. These are ideas, not college requirements. Check details with your counselor.</p></section>
      </aside>
    </div>`;
  };

  const sf = document.getElementById("topSearch");
  if (sf)
    sf.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = sf.querySelector("input").value.trim();
      if (!q) return;
      sf.reset();
      nav("advisor");
      const box = document.getElementById("chatInput");
      if (box) { box.value = q; sendChat(); }
    });

  /* ================================================================
     SURVEY
     ================================================================ */
  /* ---------------- WELCOME SURVEY (first sign-in) ---------------- */
  const SV_INTERESTS = ["Science & Research", "Technology & Coding", "Engineering & Robotics", "Medicine & Health", "Business & Entrepreneurship", "Law & Public Policy", "Arts & Design", "Writing & Media", "Music & Performance", "Education & Teaching", "Environment & Sustainability", "Sports & Fitness", "Math & Data", "History & Culture", "Languages & Global Studies", "Social Impact"];
  const SV_ACTIVITIES = ["Sports team", "Band or orchestra", "Choir or theater", "Robotics or engineering club", "Debate or Model UN", "Student government", "Volunteering", "Part-time job", "Art or photography", "Coding or hackathons", "Science fair or research", "Newspaper or yearbook", "Tutoring or mentoring", "Community group"];
  const SV_HELP = [
    ["Planning my path", "route", "Build a roadmap that fits your goals"],
    ["Finding colleges", "cap", "Build a list that fits you"],
    ["Scholarships", "trophy", "Find and track funding"],
    ["Essays and writing", "pen", "Get feedback in your own voice"],
    ["Study habits", "flask", "Make a plan that sticks"],
    ["Career exploration", "brief", "See what different paths look like"],
    ["Test prep", "target", "Prepare with a realistic schedule"],
    ["Staying organized", "cal", "Keep deadlines in view"],
  ];
  const SV_AFTER = ["Four-year college", "Community college", "Trade or technical school", "Work or gap year", "Not sure yet"];
  const SV_CLARITY = ["Just exploring", "A few ideas", "Fairly set"];
  const SV_STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming", "Outside the U.S."];
  const SV_RAIL = ["About you", "Interests", "Direction", "Involvement", "Support", "Goals"];
  const SV = { open: false, step: 0, root: null, d: null };

  const svSkipKey = () => `peerpilot-survey-skip-${currentUser ? currentUser.id : "x"}`;
  const svFresh = (p) =>
    ![p.firstName, p.lastName, p.school, p.major, p.career, p.goals].some((v) => String(v || "").trim()) &&
    !arr(p.interests).length && !arr(p.activities).length && !arr(p.courses).length;

  function svOpen(force) {
    if (SV.open) return;
    const p = state.profile;
    SV.d = {
      first: p.firstName || "", last: p.lastName || "", grade: String(p.grade || "9"), school: p.school || "", state: p.state || "",
      interests: [...arr(p.interests)], major: p.major || "", career: p.career || "", after: "", clarity: "",
      activities: [...arr(p.activities)], gpa: p.gpa || "", help: [], goal: "", worry: "",
    };
    SV.step = 0;
    SV.open = true;
    SV.root = document.createElement("div");
    SV.root.className = "sv";
    SV.root.setAttribute("role", "dialog");
    SV.root.setAttribute("aria-modal", "true");
    SV.root.setAttribute("aria-labelledby", "svTitle");
    document.body.appendChild(SV.root);
    document.body.classList.add("sv-lock");
    SV.root.addEventListener("click", svClick);
    SV.root.addEventListener("input", svInput);
    SV.root.addEventListener("keydown", svKey);
    svDraw(true);
  }
  function svClose() {
    if (!SV.open) return;
    SV.root.remove();
    SV.root = null;
    SV.open = false;
    document.body.classList.remove("sv-lock");
  }
  function maybeSurvey() {
    if (SV.open || !currentUser || currentUser.is_admin) return;
    const shell = document.querySelector(".app-shell");
    if (!shell || shell.hidden || !svFresh(state.profile)) return;
    try {
      if (localStorage.getItem(svSkipKey()) === "1") return;
    } catch (e) {}
    svOpen();
  }
  const baseRender = render;
  render = function () {
    baseRender();
    maybeSurvey();
  };
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-pp-survey]")) svOpen(true);
  });

  const svChips = (list, picked, key) => {
    const all = [...list, ...picked.filter((v) => !list.includes(v))];
    return `<div class="sv-chips">${all.map((v) => `<button type="button" class="sv-chip" data-sv-toggle="${key}" data-v="${esc(v)}" aria-pressed="${picked.includes(v)}">${esc(v)}</button>`).join("")}</div>
      <div class="sv-add"><input data-sv-add="${key}" placeholder="Add your own and press Enter" maxlength="60" aria-label="Add your own"><button type="button" class="sv-addbtn" data-sv-addbtn="${key}">Add</button></div>`;
  };
  const svField = (label, input, hint) => `<label class="sv-field"><span>${label}</span>${input}${hint ? `<em>${hint}</em>` : ""}</label>`;
  const svSeg = (list, cur, attr) => `<div class="sv-seg" role="group">${list.map((v) => `<button type="button" class="sv-opt" data-${attr}="${esc(v)}" aria-pressed="${cur === v}">${esc(v)}</button>`).join("")}</div>`;

  function svBody() {
    const d = SV.d;
    switch (SV.step) {
      case 0:
        return `<span class="sv-kicker">Welcome to PeerPilot AI</span><h1 id="svTitle">Let’s build a plan that fits you.</h1>
          <p class="sv-lead">A few short questions about your interests, goals and where you are today. PeerPilot uses your answers to shape your roadmap, your advisor and your recommendations. It takes about two minutes.</p>
          <ul class="sv-points"><li>${I.check}<span>Skip anything you’d rather not answer</span></li><li>${I.check}<span>Change every answer later in My profile</span></li><li>${I.check}<span>Your answers stay in your account</span></li></ul>
          <div class="sv-field"><span>How would you like PeerPilot to look?</span><div class="sv-themes">${[["light", "Light mode", "Bright and airy", ""], ["dark", "Dark mode", "Easy on the eyes", " dark"]].map(([v, n, s, c]) => `<button type="button" class="theme-choice" data-sv-theme="${v}" aria-pressed="${document.documentElement.dataset.theme === v}"><span class="theme-preview${c}"></span><span><strong>${n}</strong><br><small>${s}</small></span></button>`).join("")}</div><em>You can change this anytime with the sun/moon button.</em></div>
          <div class="sv-actions"><button class="sv-go" data-sv-next>Get started ${I.arrow}</button><button class="sv-skip" data-sv-skip>Skip for now</button></div>`;
      case 1:
        return `<span class="sv-kicker">Step 1 of 6</span><h1 id="svTitle">First, tell us about you</h1><p class="sv-lead">This sets the starting point for your timeline.</p>
          <div class="sv-grid">${svField("First name", `<input id="svFocus" data-sv-input="first" value="${esc(d.first)}" maxlength="60" autocomplete="given-name" placeholder="Alex">`)}${svField("Last name <small>optional</small>", `<input data-sv-input="last" value="${esc(d.last)}" maxlength="60" autocomplete="family-name" placeholder="Rivera">`)}</div>
          <div class="sv-field"><span>Current grade</span><div class="sv-grades">${[["9", "Freshman"], ["10", "Sophomore"], ["11", "Junior"], ["12", "Senior"]].map(([g, n]) => `<button type="button" class="sv-grade" data-sv-grade="${g}" aria-pressed="${d.grade === g}"><b>${g}</b><small>${n}</small></button>`).join("")}</div></div>
          <div class="sv-grid">${svField("School <small>optional</small>", `<input data-sv-input="school" value="${esc(d.school)}" maxlength="120" placeholder="Your high school">`)}${svField("State <small>optional</small>", `<input data-sv-input="state" value="${esc(d.state)}" list="svStates" maxlength="60" placeholder="Start typing">`)}</div>
          <datalist id="svStates">${SV_STATES.map((s) => `<option value="${s}">`).join("")}</datalist><p class="sv-err" id="svErr" hidden>Please add your first name to continue.</p>`;
      case 2:
        return `<span class="sv-kicker">Step 2 of 6</span><h1 id="svTitle">What are you curious about?</h1><p class="sv-lead">Pick as many as you like. These help us suggest activities, opportunities and colleges.</p>${svChips(SV_INTERESTS, d.interests, "interests")}`;
      case 3:
        return `<span class="sv-kicker">Step 3 of 6</span><h1 id="svTitle">Where are you headed?</h1><p class="sv-lead">It’s completely fine if you’re not sure yet.</p>
          <div class="sv-grid">${svField("Field of study you’re considering", `<input id="svFocus" data-sv-input="major" value="${esc(d.major)}" maxlength="80" placeholder="e.g. Computer Science, Biology, Undecided">`)}${svField("A career you’re curious about", `<input data-sv-input="career" value="${esc(d.career)}" maxlength="80" placeholder="e.g. Engineer, Teacher, Designer">`)}</div>
          <div class="sv-field"><span>After high school, you’re thinking</span>${svSeg(SV_AFTER, d.after, "sv-after")}</div>
          <div class="sv-field"><span>How clear does your direction feel?</span>${svSeg(SV_CLARITY, d.clarity, "sv-clarity")}</div>`;
      case 4:
        return `<span class="sv-kicker">Step 4 of 6</span><h1 id="svTitle">What fills your time outside class?</h1><p class="sv-lead">Clubs, sports, jobs, projects — anything that matters to you.</p>${svChips(SV_ACTIVITIES, d.activities, "activities")}
          <div class="sv-grid" style="margin-top:22px">${svField("Current GPA <small>optional</small>", `<input data-sv-input="gpa" value="${esc(d.gpa)}" maxlength="10" inputmode="decimal" placeholder="e.g. 3.6">`, "Use whichever scale your school reports.")}</div>`;
      case 5:
        return `<span class="sv-kicker">Step 5 of 6</span><h1 id="svTitle">How can PeerPilot help most?</h1><p class="sv-lead">Choose what you want support with right now.</p>
          <div class="sv-cards">${SV_HELP.map(([t, ic, s]) => `<button type="button" class="sv-card-opt" data-sv-toggle="help" data-v="${esc(t)}" aria-pressed="${d.help.includes(t)}"><span class="sv-ico">${I[ic]}</span><span><b>${t}</b><small>${s}</small></span></button>`).join("")}</div>`;
      case 6:
        return `<span class="sv-kicker">Step 6 of 6</span><h1 id="svTitle">What would make this year a win?</h1><p class="sv-lead">A sentence or two is plenty. Please don’t share sensitive personal details such as health, finances or ID numbers.</p>
          ${svField("One goal for this year <small>optional</small>", `<textarea id="svFocus" data-sv-input="goal" maxlength="400" rows="3" placeholder="e.g. Raise my math grade and start a robotics project">${esc(d.goal)}</textarea>`)}
          ${svField("Anything that feels uncertain? <small>optional</small>", `<textarea data-sv-input="worry" maxlength="400" rows="3" placeholder="e.g. I’m not sure which classes to take next year">${esc(d.worry)}</textarea>`)}`;
      default: {
        const bits = [...d.interests.slice(0, 4), ...d.help.slice(0, 2)];
        return `<div class="sv-done"><div class="sv-check">${I.check}</div><span class="sv-kicker">All set</span><h1 id="svTitle">Welcome aboard, ${esc(d.first.trim() || "there")}.</h1>
          <p class="sv-lead">Your roadmap is ready, starting from grade ${esc(d.grade)}. You can edit anything in My profile whenever your plans change.</p>
          ${bits.length ? `<div class="sv-chips sv-static">${bits.map((v) => `<span class="sv-chip on">${esc(v)}</span>`).join("")}</div>` : ""}
          <div class="sv-actions"><button class="sv-go" data-sv-finish>Open my dashboard ${I.arrow}</button></div></div>`;
      }
    }
  }
  function svDraw(animate) {
    const step = SV.step;
    const showNav = step > 0 && step < 7;
    const pct = Math.round((Math.min(step, 7) / 7) * 100);
    const rail = SV_RAIL.map((t, i) => {
      const n = i + 1;
      const st = step > n ? "done" : step === n ? "now" : "";
      return `<li class="${st}"><span>${st === "done" ? I.check : n}</span>${t}</li>`;
    }).join("");
    SV.root.innerHTML = `<div class="sv-glow"></div><div class="sv-wrap">
      <aside class="sv-rail"><div class="sv-brand"><img src="/assets/logo.png" alt=""><b>PeerPilot AI</b></div><ol>${rail}</ol><p class="sv-fine">Your answers help personalize your plan. You can change them anytime in My profile.</p></aside>
      <main class="sv-main"><div class="sv-progress" aria-hidden="true"><i style="width:${pct}%"></i></div>
        <div class="sv-card-wrap"><div class="sv-panel${animate ? " sv-anim" : ""}">${svBody()}</div>
        ${showNav ? `<div class="sv-nav"><button class="sv-back" data-sv-back>Back</button><span class="sv-nav-right"><button class="sv-skip" data-sv-skip-step>Skip this</button><button class="sv-go" data-sv-next>${step === 6 ? "Finish" : "Continue"} ${I.arrow}</button></span></div>` : ""}</div></main></div>`;
    const f = SV.root.querySelector("#svFocus") || SV.root.querySelector("#svTitle");
    if (f) {
      if (f.id === "svTitle") f.setAttribute("tabindex", "-1");
      f.focus({ preventScroll: true });
    }
  }
  function svApply() {
    const d = SV.d;
    const p = state.profile;
    p.firstName = d.first.trim();
    p.lastName = d.last.trim();
    p.grade = d.grade;
    p.school = d.school.trim();
    p.state = d.state.trim();
    p.interests = [...d.interests];
    p.activities = [...d.activities];
    p.major = d.major.trim();
    p.career = d.career.trim();
    if (d.gpa.trim()) p.gpa = d.gpa.trim();
    const bits = [];
    if (d.after) bits.push(`After high school: ${d.after}.`);
    if (d.clarity) bits.push(`Direction: ${d.clarity}.`);
    if (d.help.length) bits.push(`Wants help with: ${d.help.join(", ")}.`);
    if (d.goal.trim()) bits.push(`Main goal this year: ${d.goal.trim()}`);
    if (d.worry.trim()) bits.push(`Main uncertainty: ${d.worry.trim()}`);
    if (bits.length) p.goals = bits.join(" ").slice(0, 3800);
    persist();
    if (typeof flushStateSave === "function") flushStateSave();
  }
  function svNext() {
    if (SV.step === 1 && !SV.d.first.trim()) {
      const err = SV.root.querySelector("#svErr");
      if (err) err.hidden = false;
      const f = SV.root.querySelector("#svFocus");
      if (f) f.focus();
      return;
    }
    if (SV.step === 6) svApply();
    SV.step = Math.min(7, SV.step + 1);
    svDraw(true);
  }
  function svSkipAll() {
    try {
      localStorage.setItem(svSkipKey(), "1");
    } catch (e) {}
    svClose();
    toast("No problem. You can finish your profile anytime in My profile.");
  }
  function svFinish() {
    svClose();
    nav("dashboard");
    toast(`Welcome, ${state.profile.firstName || "there"}!`);
  }
  function svAddCustom(key) {
    const input = SV.root.querySelector(`[data-sv-add="${key}"]`);
    const v = (input.value || "").trim().slice(0, 60);
    if (!v) return;
    const list = SV.d[key];
    if (!list.some((x) => x.toLowerCase() === v.toLowerCase()) && list.length < 20) list.push(v);
    svDraw();
    const again = SV.root.querySelector(`[data-sv-add="${key}"]`);
    if (again) again.focus();
  }
  function svClick(e) {
    const t = e.target.closest("button");
    if (!t) return;
    const d = SV.d;
    if (t.dataset.svTheme) {
      applyTheme(t.dataset.svTheme, false);
      return svDraw();
    }
    if (t.hasAttribute("data-sv-next")) return svNext();
    if (t.hasAttribute("data-sv-back")) {
      SV.step = Math.max(0, SV.step - 1);
      return svDraw(true);
    }
    if (t.hasAttribute("data-sv-skip")) return svSkipAll();
    if (t.hasAttribute("data-sv-skip-step")) {
      if (SV.step === 1 && !d.first.trim()) return svNext();
      return svNext();
    }
    if (t.hasAttribute("data-sv-finish")) return svFinish();
    if (t.dataset.svGrade) {
      d.grade = t.dataset.svGrade;
      return svDraw();
    }
    if (t.dataset.svAfter !== undefined) {
      d.after = d.after === t.dataset.svAfter ? "" : t.dataset.svAfter;
      return svDraw();
    }
    if (t.dataset.svClarity !== undefined) {
      d.clarity = d.clarity === t.dataset.svClarity ? "" : t.dataset.svClarity;
      return svDraw();
    }
    if (t.dataset.svToggle) {
      const list = d[t.dataset.svToggle];
      const v = t.dataset.v;
      const i = list.indexOf(v);
      if (i >= 0) list.splice(i, 1);
      else list.push(v);
      t.setAttribute("aria-pressed", String(i < 0));
      return;
    }
    if (t.dataset.svAddbtn) return svAddCustom(t.dataset.svAddbtn);
  }
  function svInput(e) {
    const k = e.target.dataset.svInput;
    if (!k) return;
    SV.d[k] = e.target.value;
    if (k === "first") {
      const err = SV.root.querySelector("#svErr");
      if (err && e.target.value.trim()) err.hidden = true;
    }
  }
  function svKey(e) {
    if (e.key === "Enter" && e.target.dataset.svAdd) {
      e.preventDefault();
      return svAddCustom(e.target.dataset.svAdd);
    }
    if (e.key === "Enter" && e.target.tagName === "INPUT") {
      e.preventDefault();
      if (SV.step > 0 && SV.step < 7) svNext();
    }
  }

  /* ---------------- nicer pop-up forms: short drop-downs become tap-to-pick buttons ---------------- */
  function segSelects(root) {
    root.querySelectorAll("select.select-input:not([data-seg])").forEach((sel) => {
      if (sel.multiple || sel.options.length > 6 || sel.options.length < 2) return;
      sel.dataset.seg = "1";
      const seg = document.createElement("div");
      seg.className = "seg";
      seg.setAttribute("role", "group");
      [...sel.options].forEach((o) => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = o.textContent;
        b.setAttribute("aria-pressed", String(o.selected));
        b.addEventListener("click", () => {
          sel.value = o.value;
          sel.dispatchEvent(new Event("change", { bubbles: true }));
          seg.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        });
        seg.appendChild(b);
      });
      sel.hidden = true;
      sel.after(seg);
    });
  }
  const modalBox = document.getElementById("modal");
  if (modalBox && window.MutationObserver) new MutationObserver(() => segSelects(modalBox)).observe(modalBox, { childList: true });

  /* ================================================================
     MOCKUP PAGES: Goals, Applications, Calendar, Resources, planning banner
     ================================================================ */
  const cols5 = ["c-blue", "c-teal", "c-purple", "c-orange", "c-pink"];
  const bar = (pct, cls) => `<div class="pw-bar"><i class="${cls || "c-blue"}" style="width:${Math.max(0, Math.min(100, pct))}%"></i></div>`;
  const ringHtml = (label, pct, big, small, cls) =>
    `<div class="pw-ringbox"><div class="pw-ring ${cls}" style="--pct:${Math.max(0, Math.min(100, pct))}"><b>${big}</b></div><strong>${label}</strong><small>${small}</small></div>`;
  const pctOf = (n, max) => Math.min(100, Math.round((n / max) * 100));

  /* Goals (progress comes from what the student has entered) */
  function goalsPage() {
    const p = state.profile;
    const pr = pathProgress();
    const gpa = parseFloat(p.gpa);
    const nInt = arr(p.internships).length;
    const nApp = arr(state.applications).length;
    const nCol = arr(state.savedColleges).length;
    const goals = [
      ["target", "c-blue", "Raise my GPA to a 3.8+", "Academic", isNaN(gpa) ? 0 : pctOf(gpa, 3.8), isNaN(gpa) ? "Add your GPA in your profile" : `Currently ${p.gpa}`],
      ["cap", "c-teal", "Save 5 colleges I like", "College", pctOf(nCol, 5), `${nCol} of 5 saved`],
      ["brief", "c-orange", "Complete 2 internships", "Career", pctOf(nInt, 2), `${nInt} of 2 listed`],
      ["doc", "c-pink", "Apply to 5 colleges", "College / Application", pctOf(nApp, 5), `${nApp} of 5 tracked`],
    ];
    return `${pageHeader("TRACK YOUR PROGRESS", "My goals", "Track your progress and stay motivated.", `<button class="btn btn-primary" data-page="advisor">${I.sparkles} Plan with your coach</button>`)}
    <section class="pw-panel"><div class="pw-rings">${ringHtml("Roadmap", pr.pct, `${pr.finished}/${pr.total}`, "Academic", "r-blue")}${ringHtml("Colleges", pctOf(nCol, 5), `${nCol}/5`, "College", "r-teal")}${ringHtml("Internships", pctOf(nInt, 2), `${nInt}/2`, "Career", "r-orange")}${ringHtml("Applications", pctOf(nApp, 5), `${nApp}/5`, "Personal", "r-purple")}</div></section>
    <section class="pw-panel" style="margin-top:18px"><div class="pw-head"><h2>Goal progress</h2></div>${goals
      .map(([ic, c, t, s, pct, note]) => `<div class="goal-row"><span class="pw-ico ${c}">${I[ic]}</span><div class="goal-main"><strong>${t}</strong><span>${s} · ${note}</span></div>${bar(pct, c)}<b class="app-pct">${pct}%</b></div>`)
      .join("")}</section>`;
  }

  /* Applications */
  let appFilter = "All";
  const APP_PCT = { "Not Started": 0, "In Progress": 50, Submitted: 85, Complete: 100 };
  applicationsPage = function () {
    const all = arr(state.applications);
    const items = all.filter((a) => appFilter === "All" || a.status === appFilter);
    const tabs = ["All", "In Progress", "Submitted", "Not Started", "Complete"]
      .map((f) => `<button class="filter-tab ${appFilter === f ? "active" : ""}" data-app-filter="${f}">${f}</button>`)
      .join("");
    const rows = items
      .map((a, i) => {
        const pct = APP_PCT[a.status] ?? 0;
        return `<div class="app-row"><span class="pw-ico ${cols5[i % 5]}">${esc((a.college_name || "?").trim().slice(0, 2).toUpperCase())}</span><div class="app-main"><strong>${esc(a.college_name)}</strong><span>${a.due ? `Due ${esc(a.due)} · ` : ""}${esc(a.notes || "Essays, recommendations, transcript and financial aid")}</span></div><div class="app-prog">${bar(pct, "c-blue")}</div><b class="app-pct">${pct}%</b><select class="select-input" data-app-status="${esc(a.id)}" aria-label="Status">${["Not Started", "In Progress", "Submitted", "Complete"].map((s) => `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select><button class="course-remove" data-action="delete-application" data-id="${esc(a.id)}" aria-label="Delete">×</button></div>`;
      })
      .join("");
    return `${pageHeader("KEEP EACH APPLICATION ORGANIZED", "My applications", "Track your college and scholarship applications.", `<button class="btn btn-primary" data-action="new-application">＋ Add application</button>`)}<div class="filter-tabs" style="margin-bottom:16px">${tabs}</div><div class="panel">${rows || `<div class="empty-state"><strong>${all.length ? "Nothing in this filter." : "No applications tracked yet."}</strong>${all.length ? "Try another tab." : "Add a college to record deadlines and what is left to prepare."}</div>`}</div>`;
  };

  /* Courses (uses the existing add-course / remove-course actions and profile data) */
  let courseTab = "All";
  const norm = (c, planned) => ({ ...(typeof c === "string" ? { name: c } : c), planned });
  function coursesPage() {
    const p = state.profile;
    const all = [...arr(p.courses).map((c) => norm(c, false)), ...arr(p.planned).map((c) => norm(c, true))];
    const tabs = ["All", "9", "10", "11", "12", "Planned"];
    const list = all.filter((c) => courseTab === "All" || (courseTab === "Planned" ? c.planned : String(c.year) === courseTab && !c.planned));
    const cur = all.filter((c) => !c.planned && String(c.year) === String(p.grade)).length;
    const rows = list
      .map((c, i) => `<div class="app-row"><span class="pw-ico ${cols5[i % 5]}">${esc((c.name || "?").trim().slice(0, 2).toUpperCase())}</span><div class="app-main"><strong>${esc(c.name)}</strong><span>${esc(c.level || "Standard")}${c.year ? ` · Grade ${esc(c.year)}` : ""}${c.credits ? ` · ${esc(c.credits)} credits` : ""}${c.prereq ? ` · Prereq: ${esc(c.prereq)}` : ""}</span></div><span class="tag ${c.planned ? "amber" : "green"}">${c.planned ? "Planned" : "Current"}</span><button class="course-remove" data-action="remove-course" data-name="${esc(c.name)}" data-year="${esc(c.year || "")}" data-planned="${c.planned}" aria-label="Remove ${esc(c.name)}">×</button></div>`)
      .join("");
    return `${pageHeader("BUILD YOUR ACADEMIC PLAN", "Courses", "Track your current classes and plan what comes next. Confirm choices with your counselor.", `<button class="btn btn-primary" data-action="add-course">＋ Add course</button>`)}
    <div class="stat-row"><div class="stat-card"><div class="stat-kicker">Total courses</div><div class="stat-value">${all.length}</div><div class="stat-help">current and planned</div></div><div class="stat-card"><div class="stat-kicker">This year</div><div class="stat-value">${cur}</div><div class="stat-help">grade ${esc(p.grade || "—")}</div></div><div class="stat-card"><div class="stat-kicker">Planned</div><div class="stat-value">${all.filter((c) => c.planned).length}</div><div class="stat-help">to discuss with a counselor</div></div></div>
    <div class="filter-tabs" style="margin-bottom:16px">${tabs.map((t) => `<button class="filter-tab ${courseTab === t ? "active" : ""}" data-course-tab="${t}">${/^\d+$/.test(t) ? t + "th grade" : t}</button>`).join("")}</div>
    <div class="panel">${rows || `<div class="empty-state"><strong>No courses here yet.</strong>Use “Add course” to record a class or one you are considering.</div>`}</div>`;
  }

  /* Calendar: month / week / day, selectable days, upcoming events */
  const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const parseD = (s) => new Date(`${s}T12:00:00`);
  let calView = "month";
  let calSel = ymd(new Date());
  function calEvents() {
    const ev = [];
    arr(state.tasks).filter((t) => t.due && !t.done).forEach((t) => ev.push({ d: t.due, title: t.title, sub: t.category || "Task" }));
    arr(state.applications).forEach((a) => /^\d{4}-\d{2}-\d{2}$/.test(a.due || "") && ev.push({ d: a.due, title: `${a.college_name} application`, sub: a.status || "Application" }));
    return ev.sort((a, b) => a.d.localeCompare(b.d));
  }
  const evRowHtml = (e) => { const d = parseD(e.d); return `<div class="pw-row"><div class="pw-date"><small>${d.toLocaleString("en-US", { month: "short" }).toUpperCase()}</small><b>${d.getDate()}</b></div><div class="grow"><strong>${esc(e.title)}</strong><span>${esc(e.sub)}</span></div></div>`; };
  function calendarPage() {
    const sel = parseD(calSel);
    const y = sel.getFullYear();
    const m = sel.getMonth();
    const ev = calEvents();
    const todayKey = ymd(new Date());
    let body = "";
    let title = sel.toLocaleString("en-US", { month: "long", year: "numeric" });
    if (calView === "month") {
      const lead = new Date(y, m, 1).getDay();
      const days = new Date(y, m + 1, 0).getDate();
      const cells = [...Array(lead).fill('<div class="cal-d empty"></div>')];
      for (let d = 1; d <= days; d++) {
        const k = ymd(new Date(y, m, d));
        cells.push(`<button class="cal-d${k === todayKey ? " today" : ""}${k === calSel ? " sel" : ""}" data-cal-day="${k}" aria-label="${k}${ev.some((e) => e.d === k) ? ", has events" : ""}">${d}${ev.some((e) => e.d === k) ? "<i></i>" : ""}</button>`);
      }
      body = `<div class="cal-grid">${["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => `<div class="cal-h">${d}</div>`).join("")}${cells.join("")}</div>`;
    } else if (calView === "week") {
      const start = new Date(sel); start.setDate(sel.getDate() - sel.getDay());
      const cols = [...Array(7)].map((_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); const k = ymd(d); const es = ev.filter((e) => e.d === k); return `<div class="cal-wk${k === todayKey ? " today" : ""}"><button data-cal-day="${k}" class="cal-wk-h${k === calSel ? " sel" : ""}"><small>${d.toLocaleString("en-US", { weekday: "short" })}</small><b>${d.getDate()}</b></button>${es.map((e) => `<div class="cal-chip">${esc(e.title)}</div>`).join("") || '<span class="cal-none">—</span>'}</div>`; });
      body = `<div class="cal-week">${cols.join("")}</div>`;
      title = `Week of ${start.toLocaleString("en-US", { month: "short", day: "numeric" })}`;
    } else {
      const es = ev.filter((e) => e.d === calSel);
      body = es.length ? es.map(evRowHtml).join("") : '<div class="empty-state"><strong>Nothing scheduled.</strong>Add a task with this date to see it here.</div>';
      title = sel.toLocaleString("en-US", { weekday: "long", month: "long", day: "numeric" });
    }
    const dayEv = ev.filter((e) => e.d === calSel);
    const side = dayEv.length ? dayEv : ev.filter((e) => e.d >= todayKey).slice(0, 6);
    const sideTitle = dayEv.length ? `Events · ${sel.toLocaleString("en-US", { month: "short", day: "numeric" })}` : "Upcoming events";
    return `${pageHeader("SEE WHAT IS COMING", "Calendar", "Your tasks and deadlines in one place.", `<button class="btn btn-primary" data-action="add-task">＋ Add a task</button>`)}
    <div class="grid two-col"><section class="pw-panel"><div class="cal-top"><div class="filter-tabs">${["month", "week", "day"].map((v) => `<button class="filter-tab ${calView === v ? "active" : ""}" data-cal-view="${v}">${v[0].toUpperCase() + v.slice(1)}</button>`).join("")}</div><div class="cal-head"><button class="icon-btn" data-cal="-1" aria-label="Previous">‹</button><h2>${title}</h2><button class="icon-btn" data-cal="1" aria-label="Next">›</button></div><button class="btn btn-quiet btn-sm" data-cal-today>Today</button></div>${body}</section>
    <section class="pw-panel"><div class="pw-head"><h2>${sideTitle}</h2></div>${side.length ? side.map(evRowHtml).join("") : '<div class="empty-state"><strong>Nothing coming up.</strong>Tasks and application deadlines with dates show here.</div>'}</section></div>`;
  }
  document.addEventListener("click", (e) => {
    const t = e.target;
    const c = t.closest("[data-cal]");
    if (c) {
      const n = Number(c.dataset.cal);
      const d = parseD(calSel);
      if (calView === "month") d.setMonth(d.getMonth() + n, 1);
      else d.setDate(d.getDate() + n * (calView === "week" ? 7 : 1));
      calSel = ymd(d);
      return render();
    }
    let x;
    if ((x = t.closest("[data-cal-day]"))) { calSel = x.dataset.calDay; return render(); }
    if ((x = t.closest("[data-cal-view]"))) { calView = x.dataset.calView; return render(); }
    if (t.closest("[data-cal-today]")) { calSel = ymd(new Date()); return render(); }
    if ((x = t.closest("[data-app-filter]"))) { appFilter = x.dataset.appFilter; return render(); }
    if ((x = t.closest("[data-course-tab]"))) { courseTab = x.dataset.courseTab; return render(); }
  });

  /* Resources */
  function resourcesPage() {
    const tiles = [
      ["cap", "c-blue", "College search", "Find the right fit", "page", "colleges"],
      ["trophy", "c-teal", "Scholarships", "Get financial help", "page", "deadlines"],
      ["book", "c-purple", "Test prep", "Practice and improve", "page", "tutor"],
      ["pen", "c-orange", "Essay guides", "Write a standout essay", "page", "essays"],
      ["compass", "c-pink", "Career exploration", "Discover your path", "page", "careers"],
      ["route", "c-blue", "Useful links", "StudentAid.gov, official aid info", "link", "https://studentaid.gov"],
    ];
    return `${pageHeader("TOOLS FOR YOUR JOURNEY", "Resources", "Helpful links, guides and tools for your journey.")}<div class="res-grid">${tiles
      .map(([ic, c, t, s, kind, to]) => {
        const inner = `<span class="pw-ico ${c}">${I[ic]}</span><span class="res-copy"><b>${t}</b><small>${s}</small></span>`;
        return kind === "page" ? `<button class="res-tile" data-page="${to}">${inner}</button>` : `<a class="res-tile" href="${to}" target="_blank" rel="noopener">${inner}</a>`;
      })
      .join("")}</div>`;
  }

  const prevOpps = opportunitiesPage;
  let oppQ = "";
  opportunitiesPage = function () {
    return prevOpps()
      .replace(/>Opportunities<\/h1>/, ">Find Internships</h1>")
      .replace("A starter collection to help you find programs, competitions, and ways to contribute.", "Discover opportunities that match your interests and goals.")
      .replace('<div class="panel"><div class="panel-head"><div><h2 class="panel-title">Explore opportunities', `<div class="search-row"><div class="search-wrap"><input class="search-input" data-opp-search type="search" placeholder="Search internships, programs, competitions…" aria-label="Search internships" value="${esc(oppQ)}"></div></div><div class="panel"><div class="panel-head"><div><h2 class="panel-title">Explore opportunities`);
  };
  function applyOppFilter() {
    const q = oppQ.trim().toLowerCase();
    document.querySelectorAll(".resource-card").forEach((c) => { c.hidden = !!q && !c.textContent.toLowerCase().includes(q); });
  }
  document.addEventListener("input", (e) => {
    if (e.target.matches("[data-opp-search]")) { oppQ = e.target.value; applyOppFilter(); }
  });

  /* Activities: show an "Active" chip like the mockup */
  const prevActivities = activitiesPage;
  activitiesPage = function () {
    return prevActivities()
      .split("<span>Part of your story</span>").join('<span class="tag green">Active</span>')
      .replace(/<span class="tag[^"]*">Edit in profile<\/span>/g, "");
  };

  /* Roadmap: night-sky planning banner */
  const prevRoadmap = roadmapPage;
  roadmapPage = function () {
    const banner = `<section class="plan-banner"><div><h1>College Planning</h1><p>Your journey to college, one step at a time!</p></div><svg viewBox="0 0 600 200" preserveAspectRatio="xMaxYMax slice" aria-hidden="true"><circle class="st" cx="60" cy="40" r="2"/><circle class="st" cx="180" cy="24" r="1.6"/><circle class="st" cx="320" cy="50" r="2"/><circle class="st" cx="470" cy="28" r="1.8"/><circle class="moon" cx="520" cy="56" r="22"/><path class="h1" d="M0 200V120l90-50 80 60 100-80 110 90 90-50 130 70v40z"/><path class="h2" d="M0 200v-50l120-40 100 50 120-60 130 70 130-40v70z"/></svg></section>`;
    return prevRoadmap().replace(/<div class="cm-head">[\s\S]*?<\/button><\/div>(?=\s*<section class="pw-panel cm-stepper">)/, banner);
  };

  const MY_PAGES = { courses: coursesPage, goals: goalsPage, calendar: calendarPage, resources: resourcesPage };

  /* ================================================================
     8. SMALL PAGE TWEAKS
     (course planning is gone from the app; saved course data in a profile is left untouched)
     ================================================================ */
  const prevProfile = profilePage;
  profilePage = function () {
    return prevProfile()
      .replace("Easy on the eyes</small></span></button></div>", `Easy on the eyes</small></span></button><button type="button" class="theme-choice" data-theme-choice="system" aria-pressed="false"><span class="theme-preview sys"></span><span><strong>System</strong><br><small class="context-hint">Match my device</small></span></button></div><div class="accent-wrap"><strong>Accent color</strong><div class="accent-row">${Object.keys(ACCENTS).map((k) => `<button type="button" class="accent-dot" data-accent="${k}" style="background:${ACCENTS[k]}" aria-label="${k} accent" aria-pressed="${readAccent() === k}"></button>`).join("")}</div></div>`)
      .replace('<form id="profileExtrasForm"', `<section class="panel"><div class="pp-toggle"><div><h2 class="panel-title">Account</h2><div class="panel-sub">Sign out of PeerPilot on this device.</div></div><button type="button" class="btn btn-danger" data-signout>Sign out</button></div></section><form id="profileExtrasForm"`)
      .replace('<form id="profileExtrasForm"', `<section class="panel"><div class="panel-head"><div><h2 class="panel-title">Preferences</h2><div class="panel-sub">Choose what you see on Home.</div></div></div>${[["recs", "Show the AI assistant on Dashboard"], ["tips", "Show the progress chart on Dashboard"]].map(([k, l]) => `<div class="pp-toggle pref-row"><span>${l}</span><button type="button" class="pp-switch${pref(k) ? " on" : ""}" role="switch" aria-checked="${pref(k)}" aria-label="${l}" data-pref="${k}"></button></div>`).join("")}</section><form id="profileExtrasForm"`)
      .replace(
      /<div class="field full"><label for="(?:courses|planned)Profile">[^<]*<\/label><textarea[^>]*name="(courses|planned)"[^>]*>([\s\S]*?)<\/textarea><\/div>/g,
      '<textarea name="$1" hidden>$2</textarea>',
    );
  };
  const prevTutor = tutorPage;
  tutorPage = function () {
    return prevTutor().split("Choose a course and learning mode").join("Choose a subject and learning mode");
  };
  const prevAdvisor = advisorPage;
  advisorPage = function () {
    const tiles = [["book", "Explain a topic", "Break down a hard idea", "Explain this topic to me simply: "], ["cal", "Make a study plan", "Plan around your deadlines", "Help me make a study plan for this week."], ["pen", "Review my college essay", "Get feedback and ideas", "Give me feedback on my college essay: "], ["brief", "Find internships", "Discover opportunities", "What internships or programs fit my interests?"]]
      .map(([ic, t, s, pr]) => `<button type="button" class="buddy-tile" data-prompt="${pr}"><span class="pw-ico c-blue">${I[ic]}</span><span class="res-copy"><b>${t}</b><small>${s}</small></span></button>`)
      .join("");
    return prevAdvisor()
      .replace('<div class="chat-input-area">', `<div class="buddy-tiles">${tiles}</div><div class="chat-input-area">`)
      .split("Plan next year’s courses").join("Plan my next steps")
      .split("What should I think about for next year's courses?").join("What should I focus on next to stay on track?")
      .split("Ask about courses, colleges, or what to do next…").join("Ask about colleges, activities, or what to do next…")
      .split("explore courses, colleges").join("explore colleges")
      .split("Always confirm course choices with your counselor").join("Always confirm school-specific choices with your counselor");
  };

  /* ================================================================
     9. WIRING: decorate every render, scroll on navigation
     ================================================================ */
  const prevRender = render;
  render = function () {
    if (MY_PAGES[activePage]) {
      updateChrome();
      document.getElementById("pageContainer").innerHTML = MY_PAGES[activePage]();
      bindPageEvents();
      bindExtraForms();
      decorate();
      return;
    }
    prevRender();
    decorate();
  };
  const prevNav = nav;
  nav = function (page) {
    if (page === "courses") {
      /* app.js still redirects "courses" to the roadmap, so open it directly */
      activePage = "courses";
      render();
    } else prevNav(page);
    closeDrawer();
    window.scrollTo(0, 0);
    if (page === "roadmap")
      setTimeout(() => {
        const here = document.querySelector(".cm-n.now");
        if (here && here.scrollIntoView) here.scrollIntoView({ block: "center", behavior: "smooth" });
      }, 80);
  };

  /* peerpilot.js injects a light-only stylesheet; styles.css now styles those
     components for both themes, so remove the injected copy. */
  document.querySelectorAll("head style").forEach((s) => {
    if (/\.pp-safe\s*\{/.test(s.textContent)) s.remove();
  });

  /* ================================================================
     10. BOOT
     app.js starts loading the account before this file has run, so re-draw
     whatever it already put on screen using the new pages.
     ================================================================ */
  buildNav();
  bindChrome();
  applyTheme(readMode() === "system" ? "system" : readTheme() || systemTheme());
  if (typeof currentUser !== "undefined" && currentUser) {
    setupNav();
    updateChrome();
    render();
  } else {
    const authRoot = document.getElementById("authRoot");
    if (authRoot && authRoot.firstElementChild) {
      authRoot.innerHTML = authPage();
      bindAuth();
    }
  }
})();
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

  applyTheme = function (theme, announce) {
    const t = theme === "light" ? "light" : "dark";
    const root = document.documentElement;
    root.dataset.theme = t;
    root.style.colorScheme = t;
    root.classList.toggle("pp-dark", t === "dark");
    if (document.body) document.body.dataset.theme = t;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", t === "dark" ? "#070d22" : "#f4f7ff");
    try {
      localStorage.setItem(THEME_KEY, t);
    } catch (e) {}
    document.querySelectorAll("[data-theme-choice]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.themeChoice === t));
    });
    const toggle = document.getElementById("themeToggle");
    if (toggle) toggle.setAttribute("aria-label", t === "dark" ? "Switch to light mode" : "Switch to dark mode");
    if (announce) toast(`${t === "light" ? "Light" : "Dark"} mode on`);
  };
  applyTheme(readTheme() || systemTheme());

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-theme-toggle]")) {
      applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", true);
    }
  });

  /* ================================================================
     3. SIDEBAR: 10 tabs max. Related pages share a tab and show sub-tabs.
     ================================================================ */
  const TABS = [
    { id: "dashboard", label: "Overview", icon: "home", pages: ["dashboard"] },
    { id: "roadmap", label: "Roadmap", icon: "route", pages: ["roadmap"] },
    { id: "coach", label: "AI Coach", icon: "sparkles", pages: ["advisor", "tutor", "studyPlan", "essays"] },
    { id: "colleges", label: "Colleges", icon: "cap", pages: ["colleges", "applications"] },
    { id: "careers", label: "Careers", icon: "compass", pages: ["careers"] },
    { id: "opps", label: "Opportunities", icon: "trophy", pages: ["opportunities", "deadlines"], extra: '<span class="count warn" id="ppDeadlineCount" style="display:none">0</span>' },
    { id: "activities", label: "Activities", icon: "star", pages: ["activities"] },
    { id: "mentors", label: "Mentors", icon: "users", pages: ["mentors"] },
    { id: "tasks", label: "Tasks", icon: "tasks", pages: ["tasks"], extra: '<span class="count" id="taskCount">0</span>' },
    { id: "me", label: "Profile", icon: "user", pages: ["profile", "memory", "feedback", "admin"] },
  ];
  const LABELS = {
    dashboard: "Overview",
    roadmap: "My roadmap",
    advisor: "AI advisor",
    tutor: "Study tutor",
    studyPlan: "Study planner",
    essays: "Essay feedback",
    colleges: "College list",
    applications: "Applications",
    careers: "Career explorer",
    opportunities: "Opportunities",
    deadlines: "Dates & scholarships",
    activities: "Activities",
    mentors: "Peer mentors",
    tasks: "Tasks & deadlines",
    profile: "My profile",
    memory: "What AI remembers",
    feedback: "Report a problem",
    admin: "Admin",
  };

  function buildNav() {
    const navEl = document.getElementById("mainNav");
    if (!navEl) return;
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
    if (out && !out.dataset.bound) {
      out.dataset.bound = "1";
      out.addEventListener("click", () => logout());
    }
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
    const bar = hubBar();
    if (root && bar) root.insertAdjacentHTML("afterbegin", bar);
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
  dashboardPage = function () {
    const p = state.profile;
    const pr = pathProgress();
    const cap = (n, max) => Math.min(100, Math.round((n / max) * 100));
    const gpaNum = parseFloat(p.gpa);
    const savedColleges = arr(state.savedColleges).length;

    const ring = (label, pct, big, small, cls) =>
      `<div class="pw-ringbox"><div class="pw-ring ${cls}" style="--pct:${Math.max(0, Math.min(100, pct))}"><b>${big}</b></div><strong>${label}</strong><small>${small}</small></div>`;
    const nAct = arr(p.activities).length;
    const nApp = arr(state.applications).length;
    const statHtml = [
      ring("Roadmap", pr.pct, `${pr.finished}/${pr.total}`, "steps done", "r-teal"),
      ring("Activities", cap(nAct, 4), nAct, "listed", "r-orange"),
      ring("Colleges", cap(savedColleges, 6), savedColleges, "saved", "r-blue"),
      ring("Applications", cap(nApp, 5), nApp, "tracked", "r-purple"),
    ].join("");

    const quick = [
      ["route", "c-blue", "My Roadmap", "Your step-by-step path", "roadmap"],
      ["trophy", "c-green", "Opportunities", "Programs and competitions", "opportunities"],
      ["star", "c-violet", "Activities", "Get involved and build up", "activities"],
      ["brief", "c-orange", "Careers", "Explore what fits you", "careers"],
      ["doc", "c-pink", "Applications", "Manage your applications", "applications"],
      ["cap", "c-purple", "College Planning", "Plan your future step by step", "colleges"],
    ]
      .map(
        (q) =>
          `<button class="pw-quick ${q[1]}" data-page="${q[4]}"><span class="pw-quick-ico">${I[q[0]]}</span><span class="pw-quick-copy"><b>${q[2]}</b><small>${q[3]}</small></span></button>`,
      )
      .join("");

    /* the next few steps, shown as a small path */
    const flat = [];
    pr.years.forEach((y) => y.items.forEach((title, i) => flat.push({ id: `${y.grade}-${i}`, title, year: y.name, grade: y.grade })));
    const startAt = Math.max(0, flat.findIndex((s) => pr.current && s.id === pr.current.id));
    const upcoming = flat.slice(startAt).filter((s) => !pr.done.includes(s.id)).slice(0, 4);
    const pathRows = upcoming.length
      ? upcoming
          .map((s, i) => {
            const now = i === 0;
            return `<button class="pw-step${now ? " now" : ""}" data-page="roadmap"><span class="pw-step-dot">${now ? I.star : i + 1}</span><span class="pw-step-copy"><b>${esc(s.title)}</b><small>${s.year} year</small></span>${now ? '<span class="pw-pill now">Start</span>' : ""}</button>`;
          })
          .join("")
      : `<div class="empty-state"><strong>Every step is done.</strong>Nice work. Your roadmap is complete.</div>`;

    const tasks = arr(state.tasks)
      .filter((t) => !t.done)
      .sort((a, b) => (a.due || "9999").localeCompare(b.due || "9999"))
      .slice(0, 4);
    const taskRows = tasks.length
      ? tasks
          .map((t) => {
            const d = t.due ? new Date(`${t.due}T12:00:00`) : null;
            const mon = d ? d.toLocaleString("en-US", { month: "short" }).toUpperCase() : "OPEN";
            return `<div class="pw-row"><div class="pw-date"><small>${mon}</small><b>${d ? d.getDate() : "—"}</b></div><div class="grow"><strong>${esc(t.title)}</strong><span>${t.due ? dateLabel(t.due) : "No deadline set"}</span></div>${t.category ? `<span class="pw-pill">${esc(t.category)}</span>` : ""}</div>`;
          })
          .join("")
      : `<div class="empty-state"><strong>A clear calendar.</strong>Add a task or deadline when you're ready.</div>`;

    const timeline = [...pr.years.map((y) => [y.grade, `${y.name} year`, y.hint]), [13, "College", "Your next chapter"]]
      .map(([g, t, s]) => {
        const cls = g < pr.grade ? "done" : g === pr.grade ? "now" : "";
        return `<div class="pw-t ${cls}"><div class="pw-dot"></div><div><strong>${t}</strong><span>${s}</span></div>${cls === "done" ? `<div class="ok">${I.check}</div>` : ""}</div>`;
      })
      .join("");

    const recoIcons = ["cap", "trophy", "star", "doc"];
    const recoColors = ["c-blue", "c-orange", "c-purple", "c-teal"];
    const reco = arr(opportunities)
      .slice(0, 4)
      .map(
        (o, i) =>
          `<button class="pw-card" data-page="opportunities"><span class="pw-ico ${recoColors[i % 4]}">${I[recoIcons[i % 4]]}</span><strong>${esc(o.name)}</strong><span class="meta">${esc(o.category || "")}${o.deadline ? " · " + esc(o.deadline) : ""}</span><span class="more">Learn more ${I.arrow}</span></button>`,
      )
      .join("");

    const cur = pr.current;
    return `<div class="pw-grid">
      <div class="pw-main">
        <div class="pw-greet"><h1>Good ${greeting()}, ${esc(p.firstName || "there")}!</h1><p>Keep going — you're closer to your goals than you think.${svFresh(p) ? ' <button class="text-link" data-pp-survey>Take the 2-minute welcome survey</button>' : ""}</p></div>
        <div class="pw-quicks">${quick}</div>
        <section class="pw-panel"><div class="pw-head"><h2>Your progress</h2></div><div class="pw-rings">${statHtml}</div></section>
        <div class="pw-two">
          <section class="pw-panel"><div class="pw-head"><h2>${I.route} Your path</h2><a href="#roadmap" data-page="roadmap">Open map</a></div><div class="pw-steps">${pathRows}</div></section>
          <section class="pw-panel"><div class="pw-head"><h2>${I.cal} Next up</h2><button data-action="add-task">+ Add</button></div>${taskRows}</section>
        </div>
        <section class="pw-panel pw-tip"><div class="pw-head"><h2>${I.sparkles} Quick tip</h2></div><p>${cur ? "Small steps add up. Finish just one roadmap step today and keep your streak going." : "Great work! Ask your AI coach what to explore next."}</p></section>
        <section class="pw-panel"><div class="pw-head"><h2>${I.sparkles} Recommended for you</h2><a href="#opportunities" data-page="opportunities">View all</a></div>${reco ? `<div class="pw-reco">${reco}</div>` : `<div class="empty-state"><strong>Nothing to show yet.</strong>Add interests in your profile to get ideas.</div>`}</section>
      </div>
      <aside class="pw-side">
        <section class="pw-panel"><div class="pw-head"><h2>Your college roadmap</h2><a href="#roadmap" data-page="roadmap">Full plan ›</a></div><div class="pw-time">${timeline}</div></section>
        <section class="pw-panel pw-ai"><div class="pw-head"><h2>${I.sparkles} AI assistant</h2></div>
          <div class="bubble">What would you like to do next?</div>
          <div class="chipcol"><button data-page="deadlines">Help me find scholarships</button><button data-page="roadmap">Review my roadmap</button><button data-page="essays">Improve my essay draft</button></div>
          <button class="pw-ask" data-page="advisor"><span>Ask me anything…</span>${I.send}</button>
        </section>
      </aside>
    </div>`;
  };

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
     8. SMALL PAGE TWEAKS
     (course planning is gone from the app; saved course data in a profile is left untouched)
     ================================================================ */
  const prevProfile = profilePage;
  profilePage = function () {
    return prevProfile().replace(
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
    return prevAdvisor()
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
    prevRender();
    decorate();
  };
  const prevNav = nav;
  nav = function (page) {
    if (page === "courses") page = "roadmap";
    prevNav(page);
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
  applyTheme(readTheme() || systemTheme());
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
/* PeerPilot AI extras: Deadlines & scholarships, Peer mentors, dashboard heads-up, extra advisor chips.
   Loaded after app.js and plugs into its render / nav / handleAction / setupNav functions. */
(function () {
  const PP_LABELS = { deadlines: "Deadlines & scholarships", mentors: "Peer mentors", memory: "What PeerPilot remembers" };
  const TOPIC_IDEAS = [
    "Computer Science", "Engineering", "Pre-med", "Business", "Arts", "Athletics",
    "Essays", "Scholarships", "Interviews", "Course choices", "Test prep", "Choosing a college",
  ];
  const STATUS_KIND = { Interested: "", "Working on it": "blue", Submitted: "green", Won: "green", "Not selected": "" };

  if (typeof aiStatus === "object" && aiStatus.model === "gpt-6-luna") aiStatus.model = "gemini-3.5-flash";

  const PP = fresh();
  function fresh() {
    return {
      userId: null,
      dl: { data: null, loading: false },
      sch: { list: null, loading: false, statuses: ["Interested", "Working on it", "Submitted", "Won", "Not selected"] },
      mentors: { data: null, loading: false },
      mem: { data: null, loading: false },
      tab: "find",
      filter: "",
      chat: null,
      poll: null,
      ai: { loading: false, answer: "", sources: [], error: "" },
    };
  }
  function reset() {
    stopPolling();
    Object.assign(PP, fresh());
  }
  function ensureUser() {
    const id = currentUser ? currentUser.id : null;
    if (PP.userId !== id) {
      reset();
      PP.userId = id;
    }
  }

  // ---------------------------------------------------------------- styles
  const style = document.createElement("style");
  style.textContent = `
  .pp-safe{display:flex;gap:10px;align-items:flex-start;background:#f2f7ff;border-left:3px solid #3f88f4;border-radius:0 10px 10px 0;padding:12px 14px;margin-bottom:17px;font-size:11px;line-height:1.55;color:#4b5a75}
  .pp-safe b{color:#273758}
  .tag.red{background:#fdecee;color:#b4424f}
  .pp-row{display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid #f0f2f6}
  .pp-row:last-child{border-bottom:0;padding-bottom:0}
  .pp-row .grow{flex:1;min-width:0}
  .pp-row strong{display:block;font-size:11px}
  .pp-row small{display:block;font-size:9px;color:#929aaa;margin-top:3px}
  .pp-row .go{cursor:pointer;border:0;background:none;text-align:left;font:inherit;color:inherit;padding:0}
  .pp-date{width:38px;height:40px;border-radius:9px;background:#f5f6fb;display:grid;place-content:center;text-align:center;line-height:1.15;flex:none}
  .pp-date b{font-size:13px;color:#33405b}.pp-date span{font-size:8px;text-transform:uppercase;color:#949cac}
  .pp-date.overdue{background:#fdecee}.pp-date.overdue b{color:#b4424f}
  .pp-date.soon{background:#fff5e4}.pp-date.soon b{color:#a87726}
  .pp-card{padding:16px;display:flex;flex-direction:column;gap:9px}
  .pp-card h3{font:700 12px Manrope,sans-serif;margin:0}
  .pp-card p{font-size:10px;line-height:1.5;color:#788397;margin:0}
  .pp-card .actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:auto;padding-top:4px}
  .pp-card .actions .btn{padding:8px 10px;font-size:9px}
  .pp-check{display:flex;gap:8px;align-items:center;font-size:10px;color:#5d6880;background:none;border:0;padding:3px 0;cursor:pointer;text-align:left;font-family:inherit}
  .pp-check i{width:14px;height:14px;border:1.5px solid #cbd2df;border-radius:4px;flex:none;display:grid;place-items:center;font-style:normal;font-size:10px;color:#fff}
  .pp-check.done i{background:#55ae86;border-color:#55ae86}.pp-check.done span{text-decoration:line-through;color:#99a1ae}
  .pp-avatar{width:36px;height:36px;border-radius:50%;background:#eaf3ff;color:#4f61da;display:grid;place-items:center;font:700 13px Manrope,sans-serif;flex:none}
  .pp-head{display:flex;gap:10px;align-items:center}
  .pp-head small{display:block;font-size:9px;color:#929aaa;margin-top:3px}
  .pp-status{font-size:10px;padding:4px 8px;border:1px solid #e5e9f0;border-radius:7px;background:#fff;color:#47536b;font-family:inherit}
  .pp-chat{height:520px;display:flex;flex-direction:column;padding:0;overflow:hidden}
  .pp-chat .msgs{flex:1;overflow:auto;padding:16px 18px;background:#fcfcfe}
  .pp-msg{max-width:78%;margin-bottom:12px}
  .pp-msg.mine{margin-left:auto}
  .pp-msg .bubble{background:#f4f6fa;border-radius:0 10px 10px 10px;padding:10px 12px;font-size:11px;line-height:1.55;color:#4f5c73;white-space:pre-wrap;overflow-wrap:anywhere}
  .pp-msg.mine .bubble{background:#3f88f4;color:#fff;border-radius:10px 0 10px 10px}
  .pp-msg small{display:block;font-size:8px;color:#a4aab7;margin:4px 2px}
  .pp-msg.mine small{text-align:right}
  .pp-chat form{display:flex;gap:8px;padding:12px 16px;border-top:1px solid #e9edf3}
  .pp-chat form input{flex:1}
  .pp-topic-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
  .pp-answer{white-space:pre-wrap;line-height:1.65;font-size:11px;color:#4f5c73;overflow-wrap:anywhere}
  .pp-heads-up{border-left:3px solid #f5c66b}
  .pp-safe.warn{border-left-color:#f5c66b;background:#fff9ec}
  .pp-chat-note{padding:12px 16px;border-top:1px solid #e9edf3;font-size:10px;color:#929aaa}
  .pp-toggle{display:flex;align-items:center;gap:12px;justify-content:space-between}
  .pp-switch{width:44px;height:25px;border-radius:99px;border:0;background:#cbd2df;position:relative;cursor:pointer;flex:none;transition:background .15s}
  .pp-switch:after{content:"";position:absolute;top:3px;left:3px;width:19px;height:19px;border-radius:50%;background:#fff;transition:left .15s}
  .pp-switch.on{background:#3f88f4}.pp-switch.on:after{left:22px}
  .pp-mem-add{display:flex;gap:8px;margin-bottom:6px}.pp-mem-add input{flex:1}
  .pp-mem-note{font-size:10px;color:#788397;line-height:1.6;margin:10px 0 0}
  .pp-dark .pp-safe{background:rgba(45,107,255,.1);border-left-color:#5b8cff;color:#b8c4e4}
  .pp-dark .pp-safe b{color:#eaf0ff}
  .pp-dark .pp-safe.warn{background:rgba(245,198,107,.1);border-left-color:#f5c66b}
  .pp-dark .tag.red{background:rgba(239,79,123,.14);color:#ff8fab}
  .pp-dark .pp-row{border-bottom-color:#16264f}
  .pp-dark .pp-row small,.pp-dark .pp-head small,.pp-dark .pp-card p,.pp-dark .pp-check,.pp-dark .pp-mem-note{color:#8d9cc0}
  .pp-dark .pp-row strong{color:#eaf0ff}
  .pp-dark .pp-date{background:#0e1c42}.pp-dark .pp-date b{color:#eaf0ff}.pp-dark .pp-date span{color:#8d9cc0}
  .pp-dark .pp-date.overdue{background:rgba(239,79,123,.15)}.pp-dark .pp-date.overdue b{color:#ff8fab}
  .pp-dark .pp-date.soon{background:rgba(245,158,11,.15)}.pp-dark .pp-date.soon b{color:#f6c05b}
  .pp-dark .pp-card h3,.pp-dark .pp-head strong{color:#eaf0ff}
  .pp-dark .pp-check i{border-color:#2a3a68}.pp-dark .pp-check.done span{color:#6b7ba3}
  .pp-dark .pp-avatar{background:rgba(45,107,255,.18);color:#8fb2ff}
  .pp-dark .pp-status{background:#08122c;border-color:#16264f;color:#cdd7f2}
  .pp-dark .pp-chat .msgs{background:transparent}
  .pp-dark .pp-msg .bubble{background:#0e1c42;color:#cfd9f5}
  .pp-dark .pp-msg.mine .bubble{background:#2d6bff;color:#fff}
  .pp-dark .pp-msg small{color:#6b7ba3}
  .pp-dark .pp-chat form,.pp-dark .pp-chat-note{border-top-color:#16264f}
  .pp-dark .pp-answer{color:#cfd9f5}
  .pp-dark .pp-heads-up{border-left-color:#f5c518}
  .pp-dark .pp-switch{background:#2a3a68}.pp-dark .pp-switch.on{background:#2d6bff}
  @media(max-width:700px){.pp-msg{max-width:92%}.pp-chat{height:460px}}
  `;
  document.head.appendChild(style);
  // The Pathway-style dark theme defines --pw-* colors; switch our extras to match it.
  if (getComputedStyle(document.documentElement).getPropertyValue("--pw-bg").trim()) {
    document.documentElement.classList.add("pp-dark");
  }

  // --------------------------------------------------------------- helpers
  const e = (v) => esc(v);
  function dayText(n) {
    if (n < 0) return `${-n} day${n === -1 ? "" : "s"} overdue`;
    if (n === 0) return "Due today";
    if (n === 1) return "Due tomorrow";
    return `Due in ${n} days`;
  }
  function dateBox(iso, urgency) {
    const d = new Date(iso + "T00:00:00");
    const mon = d.toLocaleDateString("en-US", { month: "short" });
    return `<div class="pp-date ${urgency}"><b>${d.getDate()}</b><span>${mon}</span></div>`;
  }
  function urgencyBadge(x) {
    const kind = x.urgency === "overdue" ? "red" : x.urgency === "soon" ? "amber" : "";
    return badge(dayText(x.days_left), kind);
  }
  function timeText(at) {
    const d = new Date(String(at).replace(" ", "T") + (String(at).includes("Z") ? "" : "Z"));
    return isNaN(d) ? "" : d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }
  function initial(name) {
    return e((name || "?").trim()[0] || "?").toUpperCase();
  }
  async function call(path, method = "GET", body) {
    return api(path, body === undefined ? { method } : { method, body: JSON.stringify(body) });
  }
  function fail(err) {
    toast(err && err.message ? err.message : "Something went wrong. Try again.");
  }

  // ------------------------------------------------------------ data loads
  async function loadDeadlines() {
    if (PP.dl.loading) return;
    PP.dl.loading = true;
    try {
      PP.dl.data = await call("/api/deadlines");
    } catch {
      PP.dl.data = { deadlines: [], counts: { overdue: 0, soon: 0, month: 0 }, failed: true };
    }
    PP.dl.loading = false;
    updateBadge();
    if (activePage === "deadlines" || activePage === "dashboard") render();
  }
  async function loadScholarships() {
    if (PP.sch.loading) return;
    PP.sch.loading = true;
    try {
      const d = await call("/api/scholarships");
      PP.sch.list = d.scholarships;
      if (d.statuses) PP.sch.statuses = d.statuses;
    } catch {
      PP.sch.list = [];
    }
    PP.sch.loading = false;
    if (activePage === "deadlines") render();
  }
  async function loadMentors() {
    if (PP.mentors.loading) return;
    PP.mentors.loading = true;
    try {
      PP.mentors.data = await call("/api/mentors");
    } catch (err) {
      PP.mentors.data = { mentors: [], requests: [], stages: [], me: null, name_ready: true, failed: true };
    }
    PP.mentors.loading = false;
    if (activePage === "mentors") render();
  }
  function refreshScholarshipData() {
    loadDeadlines();
    loadScholarships();
  }
  function updateBadge() {
    const el = document.getElementById("ppDeadlineCount");
    if (!el) return;
    const c = PP.dl.data && PP.dl.data.counts;
    const n = c ? c.overdue + c.soon : 0;
    el.textContent = n;
    el.style.display = n ? "" : "none";
  }

  // ------------------------------------------- deadlines & scholarships page
  function deadlinesPage() {
    if (!PP.dl.data) loadDeadlines();
    if (!PP.sch.list) loadScholarships();
    const header = pageHeader(
      "NEVER MISS A DATE",
      "Deadlines & scholarships",
      "Every task, application, and scholarship date in one place, plus a tracker for money you’re going after.",
      `<button class="btn btn-primary" data-action="pp-add-scholarship">＋ Add scholarship</button>`,
    );
    if (!PP.dl.data || !PP.sch.list) return `${header}<div class="panel"><div class="empty-state"><strong>Loading your dates…</strong></div></div>`;
    const dl = PP.dl.data.deadlines;
    const c = PP.dl.data.counts;
    const stats = `<div class="stat-row">
      <div class="stat-card"><div class="stat-kicker">Overdue</div><div class="stat-value">${c.overdue}</div><div class="stat-help">${c.overdue ? "Let’s tackle these first" : "Nothing late. Nice!"}</div></div>
      <div class="stat-card"><div class="stat-kicker">Next 7 days</div><div class="stat-value">${c.soon}</div><div class="stat-help">Coming up fast</div></div>
      <div class="stat-card"><div class="stat-kicker">Next 30 days</div><div class="stat-value">${c.month}</div><div class="stat-help">Plan ahead</div></div></div>`;
    const target = { task: "tasks", application: "applications", scholarship: "deadlines" };
    const rows = dl.length
      ? dl.slice(0, 25).map((x) => `<div class="pp-row">${dateBox(x.due, x.urgency)}<div class="grow"><button class="go" data-page="${target[x.kind]}"><strong>${e(x.title)}</strong><small>${e(x.kind[0].toUpperCase() + x.kind.slice(1))}${x.detail ? " · " + e(x.detail) : ""}</small></button></div>${urgencyBadge(x)}</div>`).join("")
      : `<div class="empty-state"><strong>No dates yet</strong>Add a due date to a task, an application, or a scholarship and it will show up here.</div>`;
    const timeline = `<div class="panel"><div class="panel-head"><div><h2 class="panel-title">What’s coming up</h2><div class="panel-sub">Tasks, applications, and scholarships that aren’t finished</div></div></div>${rows}</div>`;

    const cards = PP.sch.list.length
      ? `<div class="grid three-col">${PP.sch.list.map(scholarshipCard).join("")}</div>`
      : `<div class="empty-state"><strong>No scholarships saved yet</strong>Use “Find scholarships for me” below, or add one you already know about.</div>`;
    const tracker = `<div class="panel"><div class="panel-head"><div><h2 class="panel-title">Scholarship tracker</h2><div class="panel-sub">${PP.sch.list.length} saved</div></div></div>${cards}</div>`;
    return `${header}${stats}${timeline}${tracker}${finderPanel()}`;
  }
  function scholarshipCard(s) {
    const days = s.due ? Math.round((new Date(s.due + "T00:00:00") - new Date(new Date().toDateString())) / 86400000) : null;
    const finished = ["Submitted", "Won", "Not selected"].includes(s.status);
    const dueTag = s.due ? badge(finished ? s.due : dayText(days), !finished && days < 0 ? "red" : !finished && days <= 7 ? "amber" : "") : "";
    const reqs = (s.requirements || [])
      .map((r, i) => `<button class="pp-check ${r.done ? "done" : ""}" data-action="pp-req-toggle" data-id="${e(s.id)}" data-index="${i}"><i>${r.done ? "✓" : ""}</i><span>${e(r.text)}</span></button>`)
      .join("");
    const opts = PP.sch.statuses.map((x) => `<option ${x === s.status ? "selected" : ""}>${e(x)}</option>`).join("");
    return `<article class="card pp-card"><h3>${e(s.name)}</h3>
      <div class="tag-row">${s.provider ? badge(s.provider) : ""}${s.amount ? badge(s.amount, "green") : ""}${dueTag}</div>
      <select class="pp-status" data-pp-status="${e(s.id)}" aria-label="Status">${opts}</select>
      ${reqs ? `<div>${reqs}</div>` : ""}${s.notes ? `<p>${e(s.notes)}</p>` : ""}
      <div class="actions">${s.url ? `<a class="btn btn-soft" href="${e(s.url)}" target="_blank" rel="noopener noreferrer">Open page ↗</a>` : ""}<button class="btn btn-quiet" data-action="pp-edit-scholarship" data-id="${e(s.id)}">Edit</button><button class="btn btn-danger" data-action="pp-delete-scholarship" data-id="${e(s.id)}">Remove</button></div></article>`;
  }
  function finderPanel() {
    const a = PP.ai;
    const body = a.loading
      ? `<div class="empty-state"><strong>Searching official sources…</strong>This can take up to a minute.</div>`
      : a.error
        ? `<div class="empty-state"><strong>Couldn’t search right now</strong>${e(a.error)}</div>`
        : a.answer
          ? `<div class="pp-answer">${e(a.answer)}</div>${citationsHTML(a.sources)}<p class="small-note">Always confirm amounts, deadlines, and rules on the official page. Never pay a fee to apply for a scholarship.</p>`
          : `<p class="panel-sub" style="margin:0">PeerPilot searches the web using your grade, state, major, and interests, then lists real scholarships with links. Add the good ones to your tracker above.</p>`;
    return `<div class="panel"><div class="panel-head"><div><h2 class="panel-title">Find scholarships for me</h2><div class="panel-sub">AI search with sources</div></div><button class="btn btn-soft" data-action="pp-find-scholarships" ${a.loading ? "disabled" : ""}>✧ Find scholarships</button></div>${body}</div>`;
  }
  function scholarshipModal(s) {
    const v = s || { name: "", provider: "", amount: "", due: "", url: "", status: "Interested", requirements: [], notes: "" };
    const opts = PP.sch.statuses.map((x) => `<option ${x === v.status ? "selected" : ""}>${e(x)}</option>`).join("");
    openModal(`<div class="modal-head"><div><h2>${s ? "Edit scholarship" : "Add a scholarship"}</h2><p>Only add real scholarships from official pages.</p></div><button class="modal-close" data-action="close-modal">×</button></div>
      <form class="modal-form" id="ppScholarForm">
        <div class="field"><label>Name</label><input class="text-input" name="name" required maxlength="200" value="${e(v.name)}"></div>
        <div class="field"><label>Who gives it (optional)</label><input class="text-input" name="provider" maxlength="150" value="${e(v.provider)}"></div>
        <div class="field"><label>Amount (optional)</label><input class="text-input" name="amount" maxlength="60" placeholder="$1,000" value="${e(v.amount)}"></div>
        <div class="field"><label>Due date</label><input class="text-input" name="due" type="date" value="${e(v.due)}"></div>
        <div class="field"><label>Link (optional)</label><input class="text-input" name="url" type="url" maxlength="500" placeholder="https://…" value="${e(v.url)}"></div>
        <div class="field"><label>Status</label><select class="select-input" name="status">${opts}</select></div>
        <div class="field"><label>Checklist (one item per line)</label><textarea class="textarea-input" name="requirements" placeholder="Essay&#10;Transcript&#10;Recommendation letter">${e((v.requirements || []).map((r) => r.text).join("\n"))}</textarea></div>
        <div class="field"><label>Notes (optional)</label><textarea class="textarea-input" name="notes" maxlength="1000">${e(v.notes)}</textarea></div>
        <button class="btn btn-primary">${s ? "Save changes" : "Add to tracker"}</button></form>`);
    document.getElementById("ppScholarForm").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const f = new FormData(ev.currentTarget);
      const old = s ? s.requirements || [] : [];
      const lines = String(f.get("requirements") || "").split("\n").map((x) => x.trim()).filter(Boolean);
      const body = {
        name: f.get("name"), provider: f.get("provider"), amount: f.get("amount"), due: f.get("due"),
        url: f.get("url"), status: f.get("status"), notes: f.get("notes"),
        requirements: lines.map((text) => ({ text, done: old.some((r) => r.text === text && r.done) })),
      };
      try {
        if (s) await call("/api/scholarships", "PUT", { ...body, id: s.id });
        else await call("/api/scholarships", "POST", body);
        closeModal();
        refreshScholarshipData();
        toast(s ? "Saved" : "Added to your tracker");
      } catch (err) {
        fail(err);
      }
    });
  }
  async function findScholarships() {
    const p = state.profile || {};
    const list = (v) => (Array.isArray(v) ? v.map((x) => (typeof x === "string" ? x : x.name || "")).filter(Boolean).slice(0, 8).join(", ") : "");
    const message =
      `Find real scholarships I could apply for. I'm in grade ${p.grade || "?"}${p.state ? " in " + p.state : ""}. ` +
      `Intended major: ${p.major || "undecided"}. Career interest: ${p.career || "still exploring"}. ` +
      `Interests: ${list(p.interests) || "not listed"}. Activities: ${list(p.activities) || "not listed"}. ` +
      `Include award amount, deadline, who is eligible, and the official link for each. Only include scholarships you can verify.`;
    PP.ai = { loading: true, answer: "", sources: [], error: "" };
    render();
    try {
      const r = await call("/api/assistant/scholarships", "POST", { message });
      PP.ai = { loading: false, answer: r.answer, sources: r.sources || [], error: "" };
    } catch (err) {
      PP.ai = { loading: false, answer: "", sources: [], error: err.message || "Try again in a moment." };
    }
    if (activePage === "deadlines") render();
  }

  // -------------------------------------------------------- AI memory page
  async function loadMemory() {
    if (PP.mem.loading) return;
    PP.mem.loading = true;
    try {
      PP.mem.data = await call("/api/memory");
    } catch {
      PP.mem.data = { enabled: true, items: [], limit: 60, max_chars: 200, failed: true };
    }
    PP.mem.loading = false;
    if (activePage === "memory") render();
  }
  function memoryPage() {
    if (!PP.mem.data) loadMemory();
    const header = pageHeader(
      "YOU’RE IN CONTROL",
      "What PeerPilot remembers",
      "Short notes that help your AI coach give better advice. Only you can see them, and you can change or delete anything, any time.",
    );
    if (!PP.mem.data) return `${header}<div class="panel"><div class="empty-state"><strong>Loading…</strong></div></div>`;
    const d = PP.mem.data;
    const rows = d.items.length
      ? d.items
          .map((m) => `<div class="pp-row"><div class="grow"><strong style="font-weight:500">${e(m.text)}</strong><small>Saved ${e(m.created)}</small></div><div class="tag-row"><button class="btn btn-quiet" data-action="pp-mem-edit" data-id="${m.id}">Edit</button><button class="btn btn-danger" data-action="pp-mem-delete" data-id="${m.id}">Forget</button></div></div>`)
          .join("")
      : `<div class="empty-state"><strong>Nothing saved yet</strong>${d.enabled ? "As you chat, your AI coach may save things like your goals or how you like answers. You can also add notes yourself." : "Memory is off, so nothing is being saved."}</div>`;
    return `${header}
      <div class="panel"><div class="pp-toggle"><div><h2 class="panel-title">Let PeerPilot remember things</h2><div class="panel-sub">${d.enabled ? "On: your AI advisor and tutor can use and save these notes." : "Off: the AI won’t read or save any notes. Your notes stay here until you delete them."}</div></div><button class="pp-switch ${d.enabled ? "on" : ""}" role="switch" aria-checked="${d.enabled}" aria-label="Let PeerPilot remember things" data-action="pp-mem-toggle"></button></div></div>
      <div class="panel"><div class="panel-head"><div><h2 class="panel-title">Your notes</h2><div class="panel-sub">${d.items.length} of ${d.limit} saved</div></div>${d.items.length ? `<button class="btn btn-danger" data-action="pp-mem-clear">Forget everything</button>` : ""}</div>
        <form id="ppMemForm" class="pp-mem-add"><input class="text-input" name="text" maxlength="${d.max_chars}" placeholder="Add a note, like “I like short answers”" aria-label="New note" required><button class="btn btn-primary">Add</button></form>
        <p class="pp-mem-note">PeerPilot never saves passwords, phone numbers, emails, links, or private details like health. Please don’t type them here either.</p>
        ${rows}</div>`;
  }
  function memoryEditModal(item) {
    openModal(`<div class="modal-head"><div><h2>Edit note</h2><p>Keep it short and kind.</p></div><button class="modal-close" data-action="close-modal">×</button></div>
      <form class="modal-form" id="ppMemEditForm"><div class="field"><textarea class="textarea-input" name="text" maxlength="${PP.mem.data.max_chars}" required>${e(item.text)}</textarea></div><button class="btn btn-primary">Save</button></form>`);
    document.getElementById("ppMemEditForm").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        PP.mem.data = await call("/api/memory", "PUT", { id: item.id, text: new FormData(ev.currentTarget).get("text") });
        closeModal();
        render();
        toast("Saved");
      } catch (err) {
        fail(err);
      }
    });
  }

  // ------------------------------------------------------------ mentors page
  function mentorsPage() {
    if (!PP.mentors.data) loadMentors();
    const header = pageHeader(
      "LEARN FROM SOMEONE WHO’S BEEN THERE",
      "Peer mentors",
      "Ask a student a little further along about essays, majors, courses, and campus life.",
    );
    if (!PP.mentors.data) return `${header}<div class="panel"><div class="empty-state"><strong>Loading mentors…</strong></div></div>`;
    const d = PP.mentors.data;
    const open = d.requests.filter((r) => r.status === "pending" || r.status === "accepted").length;
    const incoming = d.requests.filter((r) => r.role === "mentor" && r.status === "pending").length;
    const tabs = [["find", "Find a mentor"], ["chats", `My chats${open ? ` (${open})` : ""}${incoming ? " •" : ""}`], ["mentor", d.me ? "My mentor profile" : "Become a mentor"]]
      .map(([k, label]) => `<button class="filter-tab ${PP.tab === k ? "active" : ""}" data-action="pp-mentor-tab" data-tab="${k}">${e(label)}</button>`)
      .join("");
    const safety = `<div class="pp-safe"><span>🛡️</span><span><b>Keep it safe.</b> Chats stay inside PeerPilot AI. Never share your phone number, email, social media names, address, or links. Mentors are students sharing their experience, not counselors. If anything feels off, tap <b>Report</b> and tell a trusted adult.</span></div>`;
    const nameWarn = d.name_ready ? "" : `<div class="pp-safe warn"><span>✏️</span><span>Add your first name in <a href="#profile" data-page="profile">My profile</a> to ask for or offer mentoring. Only your first name and last initial are shown.</span></div>`;
    let body = "";
    if (PP.chat) body = chatView();
    else if (PP.tab === "find") body = findView(d);
    else if (PP.tab === "chats") body = chatsView(d);
    else body = mentorFormView(d);
    return `${header}${safety}${nameWarn}<div class="filter-tabs" style="display:inline-flex;margin-bottom:17px">${tabs}</div>${body}`;
  }
  function findView(d) {
    const q = PP.filter.trim().toLowerCase();
    const list = d.mentors.filter((m) => !q || [m.name, m.stage, m.school, m.bio, ...m.topics].join(" ").toLowerCase().includes(q));
    const cards = list.length
      ? `<div class="grid three-col">${list.map(mentorCard).join("")}</div>`
      : `<div class="empty-state"><strong>${d.mentors.length ? "No mentors match that search" : "No mentors yet"}</strong>${d.mentors.length ? "Try a different topic." : "Be the first: open “Become a mentor” and share what you know."}</div>`;
    return `<div class="search-row"><div class="search-wrap"><input id="ppMentorSearch" class="search-input" placeholder="Search by topic, like Computer Science or essays…" value="${e(PP.filter)}"></div></div>${cards}`;
  }
  function mentorCard(m) {
    const shared = m.shared.length ? `<div class="tag-row">${m.shared.map((t) => badge("Like you: " + t, "green")).join("")}</div>` : "";
    const rest = m.topics.filter((t) => !m.shared.includes(t));
    const action = m.request
      ? m.request.status === "accepted"
        ? `<button class="btn btn-primary" data-action="pp-open-chat" data-id="${e(m.request.id)}">Open chat</button>`
        : `<button class="btn btn-quiet" disabled>Request sent</button>`
      : `<button class="btn btn-primary" data-action="pp-ask" data-id="${e(m.id)}">Ask for help</button>`;
    return `<article class="card pp-card"><div class="pp-head"><div class="pp-avatar">${initial(m.name)}</div><div><h3>${e(m.name)}</h3><small>${e(m.stage)}${m.school ? " · " + e(m.school) : ""}</small></div></div>${shared}${rest.length ? `<div class="tag-row">${rest.map((t) => badge(t)).join("")}</div>` : ""}<p>${e(m.bio)}</p><div class="actions">${action}</div></article>`;
  }
  function askModal(handle) {
    const m = PP.mentors.data.mentors.find((x) => x.id === handle);
    if (!m) return;
    const topics = [...new Set([...m.topics, "Essays", "Course choices", "Something else"])];
    openModal(`<div class="modal-head"><div><h2>Ask ${e(m.name)} for help</h2><p>Be specific and kind. Your mentor can say yes or no.</p></div><button class="modal-close" data-action="close-modal">×</button></div>
      <form class="modal-form" id="ppAskForm">
        <div class="field"><label>What do you want help with?</label><select class="select-input" name="topic" style="width:100%">${topics.map((t) => `<option>${e(t)}</option>`).join("")}</select></div>
        <div class="field"><label>Your message</label><textarea class="textarea-input" name="message" required minlength="10" maxlength="500" placeholder="Hi! I’m working on… and I’m stuck on…"></textarea><span class="field-hint">10 to 500 characters. No phone numbers, emails, or social media names.</span></div>
        <button class="btn btn-primary">Send request</button></form>`);
    document.getElementById("ppAskForm").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const f = new FormData(ev.currentTarget);
      try {
        PP.mentors.data = await call("/api/mentors/requests", "POST", { mentor: handle, topic: f.get("topic"), message: f.get("message") });
        closeModal();
        PP.tab = "chats";
        render();
        toast("Request sent!");
      } catch (err) {
        fail(err);
      }
    });
  }
  function chatsView(d) {
    if (!d.requests.length) return `<div class="empty-state"><strong>No chats yet</strong>Find a mentor and send your first request.</div>`;
    const rows = d.requests.map((r) => {
      const who = r.role === "mentee" ? `You asked ${e(r.other_name)}` : `${e(r.other_name)} asked you`;
      const kind = r.status === "accepted" ? "green" : r.status === "pending" ? "amber" : "";
      let actions = "";
      if (r.role === "mentor" && r.status === "pending")
        actions = `<button class="btn btn-primary" data-action="pp-accept" data-id="${e(r.id)}">Accept</button><button class="btn btn-quiet" data-action="pp-decline" data-id="${e(r.id)}">Decline</button>`;
      else if (r.status === "pending") actions = `<button class="btn btn-quiet" data-action="pp-end-chat" data-id="${e(r.id)}">Cancel</button>`;
      else actions = `<button class="btn ${r.status === "accepted" ? "btn-primary" : "btn-quiet"}" data-action="pp-open-chat" data-id="${e(r.id)}">${r.status === "accepted" ? "Open chat" : "View"}</button>`;
      return `<div class="pp-row"><div class="pp-avatar">${initial(r.other_name)}</div><div class="grow"><strong>${who}</strong><small>${e(r.topic)} · “${e(r.message.slice(0, 90))}${r.message.length > 90 ? "…" : ""}”</small></div>${badge(r.status[0].toUpperCase() + r.status.slice(1), kind)}<div class="tag-row">${actions}</div></div>`;
    });
    return `<div class="panel">${rows.join("")}</div>`;
  }
  function chatView() {
    const c = PP.chat;
    const r = c.request;
    const open = r.status === "accepted";
    const msgs = c.messages.length ? c.messages.map(msgHTML).join("") : `<div class="empty-state"><strong>${open ? "Say hello!" : "No messages"}</strong>${open ? "Tell your mentor what you’re working on." : ""}</div>`;
    return `<div class="pp-head" style="margin-bottom:12px"><button class="btn btn-quiet" data-action="pp-close-chat">← Back</button><div><strong>${e(r.other_name)}</strong><small>${e(r.topic)} · ${e(r.status)}</small></div><span style="flex:1"></span>${open || r.status === "pending" ? `<button class="btn btn-quiet" data-action="pp-end-chat" data-id="${e(r.id)}">End chat</button>` : ""}<button class="btn btn-danger" data-action="pp-report" data-id="${e(r.id)}">Report</button></div>
      <div class="panel pp-chat"><div class="msgs" id="ppChatMessages">${msgs}</div>${open ? `<form id="ppChatForm"><input class="text-input" id="ppChatInput" name="body" maxlength="1000" autocomplete="off" placeholder="Write a message…" required><button class="btn btn-primary">Send</button></form>` : `<div class="pp-chat-note">This chat is ${e(r.status)}.</div>`}</div>`;
  }
  function msgHTML(m) {
    return `<div class="pp-msg ${m.mine ? "mine" : ""}"><div class="bubble">${e(m.body)}</div><small>${m.mine ? "You" : e(m.sender)} · ${e(timeText(m.at))}</small></div>`;
  }
  function mentorFormView(d) {
    const me = d.me;
    const stages = d.stages.map((s) => `<option ${me && me.stage === s ? "selected" : ""}>${e(s)}</option>`).join("");
    const chips = TOPIC_IDEAS.map((t) => `<button type="button" class="chip" data-action="pp-topic-chip" data-topic="${e(t)}">${e(t)}</button>`).join("");
    return `<div class="grid two-col"><div class="panel"><div class="panel-head"><div><h2 class="panel-title">${me ? `You’re listed as ${e(me.name)}` : "Share what you know"}</h2><div class="panel-sub">${me ? (me.active ? "Students can find you." : "Paused: new students can’t find you.") : "Only your first name and last initial are shown."}</div></div></div>
      <form id="ppMentorForm" class="modal-form">
        <div class="field"><label>Where are you now?</label><select class="select-input" name="stage" style="width:100%">${stages}</select></div>
        <div class="field"><label>College or program (optional)</label><input class="text-input" name="school" maxlength="80" value="${e(me ? me.school : "")}"><span class="field-hint">Skip this if you’d rather not share.</span></div>
        <div class="field"><label>Topics you can help with (comma separated)</label><input class="text-input" id="ppTopics" name="topics" required value="${e(me ? me.topics.join(", ") : "")}"><div class="pp-topic-chips">${chips}</div></div>
        <div class="field"><label>How can you help?</label><textarea class="textarea-input" name="bio" required minlength="20" maxlength="400" placeholder="I applied to… and learned…">${e(me ? me.bio : "")}</textarea><span class="field-hint">20 to 400 characters.</span></div>
        <label class="consent-row" style="display:flex;gap:8px;font-size:11px"><input type="checkbox" name="active" ${!me || me.active ? "checked" : ""}> <span>Show me to students who are looking for a mentor</span></label>
        <label class="consent-row" style="display:flex;gap:8px;font-size:11px"><input type="checkbox" name="agree_rules" required> <span>I agree to the mentor rules.</span></label>
        <div style="display:flex;gap:8px"><button class="btn btn-primary">${me ? "Save changes" : "Become a mentor"}</button>${me ? `<button type="button" class="btn btn-danger" data-action="pp-remove-mentor">Remove my profile</button>` : ""}</div></form></div>
      <div class="panel"><h2 class="panel-title">Mentor rules</h2><ul style="font-size:11px;line-height:1.7;color:#5d6880;padding-left:18px">
        <li>Be kind and patient. Everyone is learning.</li><li>Share your own experience. You are not a counselor or an admissions officer.</li>
        <li>Never share phone numbers, emails, social media names, addresses, or links. PeerPilot blocks them.</li>
        <li>Never ask for or share private or sensitive information.</li><li>Tap <b>Report</b> if anything feels wrong. A trusted adult should hear about it too.</li>
        <li>You can pause or remove your profile any time.</li></ul></div></div>`;
  }

  async function openChat(id) {
    try {
      const d = await call(`/api/mentors/requests/${encodeURIComponent(id)}/messages`);
      PP.chat = { request: d.request, messages: d.messages };
      render();
      scrollChat(true);
      startPolling();
    } catch (err) {
      fail(err);
    }
  }
  function scrollChat(force) {
    const box = document.getElementById("ppChatMessages");
    if (box && (force || box.scrollHeight - box.scrollTop - box.clientHeight < 80)) box.scrollTop = box.scrollHeight;
  }
  function startPolling() {
    stopPolling();
    PP.poll = setInterval(async () => {
      if (activePage !== "mentors" || !PP.chat || document.hidden) return;
      try {
        const d = await call(`/api/mentors/requests/${encodeURIComponent(PP.chat.request.id)}/messages`);
        const changed = d.messages.length !== PP.chat.messages.length;
        const statusChanged = d.request.status !== PP.chat.request.status;
        PP.chat = { request: d.request, messages: d.messages };
        if (statusChanged) return render();
        const box = document.getElementById("ppChatMessages");
        if (changed && box) {
          const stick = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
          box.innerHTML = d.messages.map(msgHTML).join("");
          if (stick) box.scrollTop = box.scrollHeight;
        }
      } catch {}
    }, 8000);
  }
  function stopPolling() {
    if (PP.poll) clearInterval(PP.poll);
    PP.poll = null;
  }
  async function answerRequest(id, action) {
    try {
      PP.mentors.data = await call("/api/mentors/requests", "PUT", { id, action });
      if (PP.chat && PP.chat.request.id === id) {
        PP.chat = null;
        stopPolling();
      }
      render();
      toast(action === "accept" ? "Accepted. You can chat now." : action === "decline" ? "Declined" : "Chat ended");
    } catch (err) {
      fail(err);
    }
  }
  function reportModal(id) {
    openModal(`<div class="modal-head"><div><h2>Report this chat</h2><p>We’ll close the chat and send your note to the team. Please also tell a trusted adult.</p></div><button class="modal-close" data-action="close-modal">×</button></div>
      <form class="modal-form" id="ppReportForm"><div class="field"><label>What happened?</label><textarea class="textarea-input" name="reason" required minlength="5" maxlength="500"></textarea></div><button class="btn btn-danger">Send report and close chat</button></form>`);
    document.getElementById("ppReportForm").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        await call("/api/mentors/report", "POST", { request_id: id, reason: new FormData(ev.currentTarget).get("reason") });
        closeModal();
        PP.chat = null;
        stopPolling();
        PP.mentors.data = await call("/api/mentors");
        PP.tab = "chats";
        render();
        toast("Report sent. Thank you.");
      } catch (err) {
        fail(err);
      }
    });
  }

  // ------------------------------------------------------ binding per render
  function bind() {
    document.querySelectorAll("[data-pp-status]").forEach((sel) =>
      sel.addEventListener("change", async () => {
        try {
          await call("/api/scholarships", "PUT", { id: sel.dataset.ppStatus, status: sel.value });
          refreshScholarshipData();
          toast("Status updated");
        } catch (err) {
          fail(err);
          loadScholarships();
        }
      }),
    );
    const search = document.getElementById("ppMentorSearch");
    if (search)
      search.addEventListener("input", () => {
        const pos = search.selectionStart;
        PP.filter = search.value;
        render();
        const next = document.getElementById("ppMentorSearch");
        if (next) {
          next.focus();
          next.setSelectionRange(pos, pos);
        }
      });
    const memForm = document.getElementById("ppMemForm");
    if (memForm)
      memForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        try {
          PP.mem.data = await call("/api/memory", "POST", { text: new FormData(memForm).get("text") });
          render();
          toast("Saved");
        } catch (err) {
          fail(err);
        }
      });
    const form = document.getElementById("ppMentorForm");
    if (form)
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const f = new FormData(form);
        try {
          PP.mentors.data = await call("/api/mentors/me", "PUT", {
            stage: f.get("stage"), school: f.get("school"), topics: f.get("topics"), bio: f.get("bio"),
            active: f.get("active") === "on", agree_rules: f.get("agree_rules") === "on",
          });
          render();
          toast("Mentor profile saved");
        } catch (err) {
          fail(err);
        }
      });
    const chat = document.getElementById("ppChatForm");
    if (chat)
      chat.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const input = document.getElementById("ppChatInput");
        const body = input.value.trim();
        if (!body) return;
        try {
          const r = await call(`/api/mentors/requests/${encodeURIComponent(PP.chat.request.id)}/messages`, "POST", { body });
          PP.chat.messages.push({ ...r.message, sender: "You" });
          input.value = "";
          const box = document.getElementById("ppChatMessages");
          if (box) {
            box.innerHTML = PP.chat.messages.map(msgHTML).join("");
            box.scrollTop = box.scrollHeight;
          }
        } catch (err) {
          fail(err);
        }
      });
  }

  // ------------------------------------------------------------ click actions
  function act(el) {
    const a = el.dataset.action;
    const id = el.dataset.id;
    if (a === "pp-add-scholarship") return scholarshipModal(null);
    if (a === "pp-edit-scholarship") return scholarshipModal((PP.sch.list || []).find((s) => s.id === id));
    if (a === "pp-delete-scholarship") {
      if (!window.confirm("Remove this scholarship from your tracker?")) return;
      return call(`/api/scholarships/${encodeURIComponent(id)}`, "DELETE").then(() => { refreshScholarshipData(); toast("Removed"); }).catch(fail);
    }
    if (a === "pp-req-toggle") {
      const s = (PP.sch.list || []).find((x) => x.id === id);
      if (!s) return;
      const reqs = s.requirements.map((r, i) => (i === Number(el.dataset.index) ? { ...r, done: !r.done } : r));
      s.requirements = reqs;
      render();
      return call("/api/scholarships", "PUT", { id, requirements: reqs }).catch((err) => { fail(err); loadScholarships(); });
    }
    if (a === "pp-find-scholarships") return findScholarships();
    if (a === "pp-mem-toggle")
      return call("/api/memory/settings", "PUT", { enabled: !(PP.mem.data && PP.mem.data.enabled) })
        .then((d) => { PP.mem.data = d; render(); toast(d.enabled ? "Memory is on" : "Memory is off"); }).catch(fail);
    if (a === "pp-mem-edit") {
      const item = ((PP.mem.data || {}).items || []).find((m) => String(m.id) === String(id));
      return item && memoryEditModal(item);
    }
    if (a === "pp-mem-delete")
      return call(`/api/memory/${encodeURIComponent(id)}`, "DELETE").then((d) => { PP.mem.data = d; render(); toast("Forgotten"); }).catch(fail);
    if (a === "pp-mem-clear") {
      if (!window.confirm("Forget everything PeerPilot has saved about you?")) return;
      return call("/api/memory", "DELETE").then((d) => { PP.mem.data = d; render(); toast("All notes deleted"); }).catch(fail);
    }
    if (a === "pp-mentor-tab") {
      PP.tab = el.dataset.tab;
      PP.chat = null;
      stopPolling();
      return render();
    }
    if (a === "pp-ask") return askModal(id);
    if (a === "pp-accept") return answerRequest(id, "accept");
    if (a === "pp-decline") return answerRequest(id, "decline");
    if (a === "pp-end-chat") {
      if (!window.confirm("End this chat? You can’t restart it, but you can send a new request later.")) return;
      return answerRequest(id, "close");
    }
    if (a === "pp-open-chat") return openChat(id);
    if (a === "pp-close-chat") {
      PP.chat = null;
      stopPolling();
      loadMentorsQuiet();
      return render();
    }
    if (a === "pp-report") return reportModal(id);
    if (a === "pp-remove-mentor") {
      if (!window.confirm("Remove your mentor profile? Open chats with you will be closed.")) return;
      return call("/api/mentors/me", "DELETE").then((d) => { PP.mentors.data = d; render(); toast("Profile removed"); }).catch(fail);
    }
    if (a === "pp-topic-chip") {
      const input = document.getElementById("ppTopics");
      if (!input) return;
      const have = input.value.split(",").map((x) => x.trim()).filter(Boolean);
      if (!have.some((x) => x.toLowerCase() === el.dataset.topic.toLowerCase()) && have.length < 8) have.push(el.dataset.topic);
      input.value = have.join(", ");
    }
  }
  async function loadMentorsQuiet() {
    try {
      PP.mentors.data = await call("/api/mentors");
      if (activePage === "mentors" && !PP.chat) render();
    } catch {}
  }

  // ------------------------------------------------- dashboard + advisor extras
  function dashboardCard() {
    if (!PP.dl.data) return loadDeadlines();
    const hot = PP.dl.data.deadlines.filter((x) => x.days_left <= 14).slice(0, 3);
    const root = document.getElementById("pageContainer");
    if (!hot.length || !root) return;
    const rows = hot.map((x) => `<div class="pp-row">${dateBox(x.due, x.urgency)}<div class="grow"><strong>${e(x.title)}</strong><small>${e(x.kind)}</small></div>${urgencyBadge(x)}</div>`).join("");
    const card = document.createElement("div");
    card.className = "panel pp-heads-up";
    card.innerHTML = `<div class="panel-head"><div><h2 class="panel-title">Heads up</h2><div class="panel-sub">Due soon</div></div><button class="text-link" data-page="deadlines">See all dates →</button></div>${rows}`;
    root.prepend(card);
  }
  function advisorChips() {
    const row = document.querySelector(".suggestion-chips");
    if (!row || row.dataset.pp) return;
    row.dataset.pp = "1";
    [["What’s due soon?", "What deadlines do I have coming up, and what should I do first?"], ["Find scholarships", "Which scholarships should I look into based on my profile?"], ["I feel stressed", "I’m feeling overwhelmed with school and college stuff. Can you help me break it down?"]].forEach(([label, prompt]) => {
      const b = document.createElement("button");
      b.className = "chip";
      b.textContent = label;
      b.addEventListener("click", () => {
        document.getElementById("chatInput").value = prompt;
        sendChat();
      });
      row.append(b);
    });
  }

  // --------------------------------------------------- plug into app.js hooks
  const PP_PAGES = { deadlines: deadlinesPage, mentors: mentorsPage, memory: memoryPage };

  const baseRender = render;
  render = function () {
    ensureUser();
    if (activePage !== "mentors") stopPolling();
    if (PP_PAGES[activePage]) {
      updateChrome();
      document.getElementById("pageContainer").innerHTML = PP_PAGES[activePage]();
      bind();
      return;
    }
    baseRender();
    if (activePage === "advisor") advisorChips();
    if (activePage === "dashboard") dashboardCard();
  };

  const baseNav = nav;
  nav = function (page) {
    baseNav(page);
    if (PP_LABELS[page]) document.getElementById("crumbCurrent").textContent = PP_LABELS[page];
  };

  const baseHandle = handleAction;
  handleAction = function (el) {
    if (el.dataset.action && el.dataset.action.startsWith("pp-")) return act(el);
    return baseHandle(el);
  };

  const baseSetupNav = setupNav;
  setupNav = function () {
    baseSetupNav();
    ensureUser();
    const after = document.querySelector('.main-nav [data-page="opportunities"]');
    if (after && !document.querySelector('[data-page="deadlines"]')) {
      const d = document.createElement("button");
      d.className = "nav-item";
      d.dataset.page = "deadlines";
      d.innerHTML = '<span class="nav-icon">◷</span>Dates &amp; scholarships <span class="task-count" id="ppDeadlineCount" style="display:none">0</span>';
      const m = document.createElement("button");
      m.className = "nav-item";
      m.dataset.page = "mentors";
      m.innerHTML = '<span class="nav-icon">☺</span>Peer mentors <span class="nav-new">NEW</span>';
      after.after(d, m);
    }
    const profileBtn = document.querySelector('.main-nav [data-page="profile"]');
    if (profileBtn && !document.querySelector('[data-page="memory"]')) {
      const mem = document.createElement("button");
      mem.className = "nav-item";
      mem.dataset.page = "memory";
      mem.innerHTML = '<span class="nav-icon">✎</span>What AI remembers';
      profileBtn.after(mem);
    }
    loadDeadlines();
  };
})();
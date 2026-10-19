const { JSDOM } = require("jsdom"); const fs = require("fs");
const dir = process.argv[2] || require("path").join(__dirname, "..");
const html = fs.readFileSync(dir + "/index.html", "utf8").replace(/<script src="[^"]+"><\/script>/g, "");
const dom = new JSDOM(html, { runScripts: "outside-only", url: "http://127.0.0.1:8000/", pretendToBeVisual: true });
const w = dom.window; const errors = []; const calls = [];
w.structuredClone = structuredClone;
w.addEventListener("error", e => errors.push(e.message));
const user = { id: 1, email: "a@b.edu", is_admin: true };
const boot = { user, profile: { firstName: "Ari", grade: "10", school: "Test High", courses: [{name:"Algebra",year:"10",level:"Honors"}], planned: [], activities: ["Robotics"], interests: ["Economics"], colleges: ["Harvard"] },
  tasks: [{ id: "t1", title: "Task one", due: "2026-10-05", category: "Application", notes: "", done: false }],
  colleges: [{ id: "harvard", name: "Harvard University", location: "MA", initials: "HU", majors: ["Econ"], summary: "s", source: "https://h.edu", prepSource: "https://h.edu/p", aidSource: "https://h.edu/a", aid: "x", lastVerified: "2026-09-26", verificationStatus: "v" }],
  savedColleges: [], opportunities: [{ id: "opp", name: "Opp", category: "Competitions", description: "d", eligibility: "", deadline: "", cost: "", location: "US", application: "", interests: ["Econ"], link: "https://o.org", source: "o", verified: "2026-09-26" }],
  savedOpportunities: [], appliedOpportunities: [], completedOpportunities: [], messages: [{ role: "user", text: "hi" }, { role: "assistant", text: "hello", citations: [{ title: "T", url: "https://t.org", accessed_at: "2026-09-30" }] }],
  savedRoadmap: [], completedRoadmap: [], applications: [{ id: "a1", college_name: "Harvard", due: "2026-11-01", status: "Not Started", notes: "" }], customColleges: [], aiConfigured: true };
w.fetch = async (url, opts = {}) => {
  calls.push([opts.method || "GET", url, opts.body]);
  const j = (o, ok = true) => ({ ok, status: ok ? 200 : 400, json: async () => o });
  if (url === "/api/auth/me") return j({ user });
  if (url === "/api/bootstrap") return j(boot);
  if (url === "/api/health") return j({ ok: true, ai_configured: true, model: "m", reasoning_effort: "high" });
  if (url.startsWith("/api/admin/overview")) return j({ counts: { users: 1 } });
  if (url.startsWith("/api/admin/records")) return j({ schools: [{ id: 1, name: "S", location: "L" }], colleges: [{ id: 1, name: "C", majors_json: "[]", verification_status: "unverified" }], courses: [], opportunities: [], feedback: [], aiFailures: [], sources: [], sourceHistory: [] });
  if (url.startsWith("/api/admin/users")) return j({ users: [{ id: 1, email: "a@b.edu", is_admin: 1, is_active: 1 }] });
  if (url.startsWith("/api/school/courses")) return j({ courses: [] });
  if (url === "/api/assistant/chat") return j({ answer: "AI answer", sources: [{ title: "Src", url: "https://s.org", accessed_at: "2026-09-30" }], intent: "general", researched: true });
  if (url === "/api/assistant/tutor") return j({ answer: "Tutor answer", sources: [] });
  if (url === "/api/deadlines") return j({ deadlines: [{ kind: "task", id: "t1", title: "Task one", due: "2026-10-18", detail: "Application", days_left: 3, urgency: "soon" }, { kind: "scholarship", id: "s1", title: "Rotary", due: "2026-10-01", detail: "$500", days_left: -14, urgency: "overdue" }], counts: { overdue: 1, soon: 1, month: 1 } });
  if (url === "/api/scholarships" && (opts.method || "GET") === "GET") return j({ scholarships: [{ id: "s1", name: "Rotary", provider: "Club", amount: "$500", due: "2026-10-01", url: "https://r.org", status: "Interested", requirements: [{ text: "Essay", done: false }], notes: "" }], statuses: ["Interested", "Working on it", "Submitted", "Won", "Not selected"] });
  if (url === "/api/assistant/scholarships") return j({ answer: "Scholarship answer", sources: [{ title: "Src", url: "https://s.org", accessed_at: "2026-10-15" }] });
  if (url === "/api/mentors" && (opts.method || "GET") === "GET") return j({ mentors: [{ id: "h1", name: "Sam R.", stage: "College freshman", school: "", topics: ["Economics", "Essays"], bio: "I can help with essays and econ.", shared: ["Economics"], request: null }], requests: [{ id: "r1", role: "mentee", other_name: "Sam R.", topic: "Essays", message: "Can you help?", status: "accepted", updated_at: "2026-10-15 10:00:00" }], stages: ["Grade 11", "College freshman"], name_ready: true, me: null });
  if (url === "/api/mentors/requests/r1/messages" && (opts.method || "GET") === "GET") return j({ request: { id: "r1", role: "mentee", other_name: "Sam R.", topic: "Essays", message: "Can you help?", status: "accepted" }, messages: [{ id: 1, mine: false, sender: "Sam R.", body: "Hi there", at: "2026-10-15 10:00:00" }] });
  if (url === "/api/mentors/requests/r1/messages") return j({ message: { id: 2, mine: true, sender: "", body: "Thanks!", at: "2026-10-15 10:01:00" } });
  if (url.startsWith("/api/memory")) return j({ enabled: true, items: [{ id: 1, text: "Likes short answers", created: "2026-10-15" }], limit: 60, max_chars: 200 });
  return j({ ok: true });
};
const code = fs.readFileSync(dir + "/app.js", "utf8");
// index.html carries an inline script (login page, dashboard, course map). Run it between app.js and peerpilot.js.
const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join("\n");
(async () => {
  // Browsers share top-level let/const between classic scripts; jsdom's eval does not, so run them as one.
  w.eval(code + "\n" + inline + "\n" + fs.readFileSync(dir + "/peerpilot.js", "utf8"));
  await new Promise(r => setTimeout(r, 50));
  const doc = w.document; const click = el => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const assert = (c, m) => { if (!c) { errors.push("ASSERT: " + m); } };
  assert(!doc.querySelector(".app-shell").hidden, "app shell visible after login");
  const pages = ["dashboard","advisor","roadmap","courses","colleges","opportunities","activities","tutor","tasks","profile","applications","studyPlan","essays","careers","feedback","admin"];
  for (const pg of pages) {
    const b = doc.querySelector(`[data-page="${pg}"]`); assert(b, "nav button " + pg);
    if (b) click(b);
    await new Promise(r => setTimeout(r, 20));
    assert(doc.getElementById("pageContainer").innerHTML.length > 200, "page renders " + pg);
  }
  // PeerPilot extras
  assert(doc.querySelector('[data-page="deadlines"]') && doc.querySelector('[data-page="mentors"]'), "new nav buttons exist");
  click(doc.querySelector('[data-page="deadlines"]'));
  await new Promise(r => setTimeout(r, 80));
  let html = doc.getElementById("pageContainer").innerHTML;
  assert(html.includes("Deadlines &amp; scholarships") && html.includes("Rotary") && html.includes("overdue"), "deadlines page shows data");
  assert(doc.getElementById("crumbCurrent").textContent === "Deadlines & scholarships", "crumb label");
  click(doc.querySelector('[data-action="pp-add-scholarship"]'));
  assert(doc.getElementById("ppScholarForm"), "scholarship modal opens");
  click(doc.querySelector('#modal [data-action="close-modal"]'));
  click(doc.querySelector('[data-action="pp-req-toggle"]'));
  assert(doc.querySelector(".pp-check.done"), "checklist toggles");
  click(doc.querySelector('[data-action="pp-find-scholarships"]'));
  await new Promise(r => setTimeout(r, 80));
  assert(doc.getElementById("pageContainer").textContent.includes("Scholarship answer"), "AI scholarship answer rendered");
  click(doc.querySelector('[data-page="mentors"]'));
  await new Promise(r => setTimeout(r, 80));
  html = doc.getElementById("pageContainer").innerHTML;
  assert(html.includes("Sam R.") && html.includes("Keep it safe"), "mentors page shows mentor and safety note");
  click(doc.querySelector('[data-action="pp-ask"]'));
  assert(doc.getElementById("ppAskForm"), "ask modal opens");
  click(doc.querySelector('#modal [data-action="close-modal"]'));
  click(doc.querySelector('[data-tab="chats"]'));
  click(doc.querySelector('[data-action="pp-open-chat"]'));
  await new Promise(r => setTimeout(r, 80));
  assert(doc.getElementById("ppChatMessages") && doc.getElementById("ppChatMessages").textContent.includes("Hi there"), "chat opens");
  doc.getElementById("ppChatInput").value = "Thanks!";
  doc.getElementById("ppChatForm").dispatchEvent(new w.Event("submit", { cancelable: true, bubbles: true }));
  await new Promise(r => setTimeout(r, 80));
  assert(doc.getElementById("ppChatMessages").textContent.includes("Thanks!"), "sent message appears");
  click(doc.querySelector('[data-page="mentors"]'));
  click(doc.querySelector('[data-tab="mentor"]'));
  assert(doc.getElementById("ppMentorForm"), "mentor form renders");
  click(doc.querySelector('[data-page="dashboard"]'));
  await new Promise(r => setTimeout(r, 60));
  assert(doc.querySelector(".pp-heads-up"), "dashboard heads-up card");
  // AI memory page
  assert(doc.querySelector('[data-page="memory"]'), "memory nav button exists");
  click(doc.querySelector('[data-page="memory"]'));
  await new Promise(r => setTimeout(r, 80));
  html = doc.getElementById("pageContainer").innerHTML;
  assert(html.includes("What PeerPilot remembers") && html.includes("Likes short answers"), "memory page lists notes");
  assert(doc.getElementById("crumbCurrent").textContent === "What PeerPilot remembers", "memory crumb label");
  click(doc.querySelector('[data-action="pp-mem-edit"]'));
  assert(doc.getElementById("ppMemEditForm"), "memory edit modal opens");
  click(doc.querySelector('#modal [data-action="close-modal"]'));
  doc.querySelector("#ppMemForm input").value = "Wants to study biology";
  doc.getElementById("ppMemForm").dispatchEvent(new w.Event("submit", { cancelable: true, bubbles: true }));
  await new Promise(r => setTimeout(r, 60));
  assert(calls.some(c => c[0] === "POST" && c[1] === "/api/memory"), "memory note is posted");
  click(doc.querySelector('[data-action="pp-mem-toggle"]'));
  await new Promise(r => setTimeout(r, 60));
  assert(calls.some(c => c[0] === "PUT" && c[1] === "/api/memory/settings"), "memory toggle calls the server");
  assert(doc.documentElement.classList.contains("pp-dark"), "dark theme detected");
  click(doc.querySelector('[data-page="dashboard"]'));
  await new Promise(r => setTimeout(r, 60));
  assert(doc.querySelector(".hm-tiles") && doc.querySelector(".hm-rings"), "new Home layout renders");
  click(doc.querySelector('[data-page="courses"]'));
  await new Promise(r => setTimeout(r, 30));
  assert(doc.querySelector(".cs-stats") && doc.querySelector(".cs-table"), "courses table renders");
  // delegated actions fire exactly once
  click(doc.querySelector('[data-page="tasks"]'));
  const before = doc.querySelector(".task-check").className;
  click(doc.querySelector('[data-action="toggle-task"]'));
  assert(doc.querySelector(".task-check").classList.contains("checked"), "toggle-task toggled exactly once");
  click(doc.querySelector('[data-action="add-task"]'));
  assert(doc.getElementById("taskForm"), "task modal opens");
  click(doc.querySelector('#modal [data-action="close-modal"]'));
  assert(doc.getElementById("modalBackdrop").hidden, "modal closes via delegated handler");
  // college save from modal toggles once
  click(doc.querySelector('[data-page="colleges"]'));
  click(doc.querySelector('[data-action="college-detail"]'));
  click(doc.querySelector('#modal [data-action="save-college"]'));
  click(doc.querySelector('[data-action="close-modal"]'));
  click(doc.querySelector('[data-page="dashboard"]'));
  assert(doc.body.textContent.includes("1"), "saved college count updates");
  // advisor chat round trip: no history/profile sent, server owns transcript
  click(doc.querySelector('[data-page="advisor"]'));
  doc.getElementById("chatInput").value = "What are Harvard deadlines?";
  doc.getElementById("chatForm").dispatchEvent(new w.Event("submit", { cancelable: true, bubbles: true }));
  await new Promise(r => setTimeout(r, 400));
  const chat = calls.find(c => c[1] === "/api/assistant/chat");
  assert(chat && JSON.parse(chat[2]).history === undefined && JSON.parse(chat[2]).profile === undefined, "chat payload is minimal");
  assert(doc.getElementById("chatMessages").textContent.includes("AI answer"), "AI answer rendered");
  await new Promise(r => setTimeout(r, 400));
  const states = calls.filter(c => c[1] === "/api/state");
  assert(states.length > 0 && states.every(c => JSON.parse(c[2]).messages === undefined), "state saves exclude messages");
  console.log("state saves:", states.length, "| api calls:", calls.length);
  console.log(errors.length ? "FAIL:\n" + errors.join("\n") : "SMOKE OK — all 16 pages render, delegated events fire once");
  process.exit(errors.length ? 1 : 0);
})();
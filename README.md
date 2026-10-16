# PeerPilot AI

A local Python web application for high-school students planning courses, exploring colleges and careers, organizing applications, and getting AI-supported academic guidance. The product is called PeerPilot AI.

## Run locally

1. Install Python 3.10 or newer.
2. Install the two helper packages (use the SAME Python you run the app with):
   `python -m pip install -r requirements.txt`
   Optional but recommended for better web search: `python -m pip install ddgs`
3. Copy `.env.example` to a new file named `.env` and paste your free Gemini key after `GEMINI_API_KEY=` (get one at https://aistudio.google.com/apikey). The key stays on the Python server. **Never put a real key in `.env.example`, and never share `.env`.**
4. Start the app with `python app.py`.
5. Open `http://127.0.0.1:8000`.

## Use on iPhone or iPad

The interface adapts to iOS Safari, including narrow screens, iPhone safe areas, and the on-screen keyboard. To open it from an iPhone or iPad on the same Wi-Fi network, change `APP_HOST` to `0.0.0.0` in `.env` before starting the app, then visit `http://<computer-local-IP>:8000` in Safari. Find the computer’s local IP in its network settings. Keep the computer and app running while you use it. For access outside your home network, deploy behind HTTPS rather than exposing the development server directly.

The web server itself uses the Python standard library; the AI helper uses `requests` and `beautifulsoup4`. SQLite data is stored in `student_guidance.sqlite3`; keep that file private and back it up securely. Set `APP_DATABASE` to use another local path.

## AI configuration

The AI is an agent built from the ai-starter project: Gemini plus tools it can call, in a loop, until it has an answer.

| Piece | File | What it does |
|---|---|---|
| Model client | `core/llm.py` | Talks to Gemini. Tries each model in `GEMINI_MODELS` in order; a model that hits a limit or is retired rests for a minute while the next one answers. Handles Gemini 3 "thought signatures" and the `reasoning_effort` setting. |
| Agent loop | `core/agent.py` | Builds the prompt (instructions + date + the student's memory), runs tool calls side by side, and logs every tool call. |
| Tool list | `core/tools.py` | Finds every file in `tools/` and runs them. Each mode (advisor, tutor, essay, study plan, scholarships) is only allowed some tools: see `MODE_TOOLS` in `assistant.py`. |
| Student memory | `core/memory.py` | A private notes list per student in the database. The student can see, edit, delete, or switch it off on the "What AI remembers" page. |
| Internet | `tools/web.py` | `web_search` (DuckDuckGo) and `read_page`. `read_page` refuses non-web addresses and anything on your own network. |
| Everyday tools | `tools/calculator.py`, `tools/get_time.py` | Exact maths, and today's date. |
| Memory tools | `tools/memory_tools.py` | `remember`, `update_memory`, `forget`, `search_memory`, for the signed-in student only. The AI never saves passwords, contact info, or private details. |
| PeerPilot tools | `tools/peerpilot_tools.py` | `get_deadlines` and `get_scholarship_tracker` (read-only). |

To add a tool, copy `tools/_template.py`, rename it, fill it in, restart the app, and list its name in the right modes in `MODE_TOOLS` (`assistant.py`). A tool that needs to know which student is asking takes a second argument, `ctx` (`ctx["user_id"]`).

Sources shown under an answer are only pages the tools really opened (or search results if no page was opened), never links the model typed. If a question needs current facts and no source could be found, the app says so instead of guessing.

**Models.** The default list is `gemini-3.5-flash-lite` then `gemini-3.8-flash`. Google renames and retires models often. If you see "could not find the model", look up the names your key can use at https://aistudio.google.com or by calling `https://generativelanguage.googleapis.com/v1beta/openai/models` with your key, then set `GEMINI_MODELS` in `.env`.

**Free tier.** Free Gemini limits are per day and per Google project and change without notice. One research question can use several requests. Google may use free-tier prompts to improve its products, so use a paid (billing-enabled) key before real students use the app.

Without a key, profiles and planners remain usable. AI features return a clear setup message instead of inventing research.

## Accounts and privacy

The app supports account registration, sign-in, sign-out, profile updates, account deletion, and a local development password-reset flow. Profiles, planner state, and recent advisor conversations are saved to the local SQLite database and tied to the signed-in account. Passwords are PBKDF2-SHA256 hashed; session cookies are HttpOnly and SameSite strict. Set `APP_SECURE_COOKIES=true` behind HTTPS. The development reset code is returned by the local API; configure a real email delivery provider before enabling public password recovery.

For a local administrator account, set `ADMIN_EMAIL` and `ADMIN_INITIAL_PASSWORD` before the first server start. Use a unique, strong password. The admin area supports college and school records, user access, and user reports.

Students should avoid storing sensitive information. Review applicable student and child privacy rules with qualified counsel before public deployment. This local build is an MVP/RC and is not a compliance certification.

New accounts must affirm they are at least 13, confirm guardian permission if under 18, and accept the current Terms of Service and Privacy Notice. Each acceptance records the document versions and UTC timestamp. The legal documents are starting drafts for this application, not a legal-compliance certification. Before public use, identify the legal operator and privacy contact in the notices, review the deployment's hosting and data flows, establish retention and incident-response practices, and have qualified counsel assess applicable federal and state requirements. Set `APP_ENV=production` behind HTTPS; this makes session cookies Secure by default. The app does not currently provide a COPPA parental-consent workflow for children under 13 and blocks their account creation.

## Included workflows

- Private student profiles and account-scoped SQLite persistence
- Dashboard, four-year course planner, school catalog view, roadmap, tasks, activities, colleges, and opportunities
- AI advisor, tutor, career exploration, study planner, and essay coaching
- Current web research with citations when the request requires it
- Application organizer and user feedback reports
- Admin overview, college/school entry, account controls, and data-quality reports
- Rate limits, input bounds, CSRF origin checks, output safety checks, and graceful API errors

Run the backend checks with `python -m unittest discover -s tests`. The frontend smoke test (`npm install && npm run smoke`) loads the app in jsdom, renders all 16 pages and verifies event handling.

## Changelog: optimization pass

**Bugs fixed**
- Saved/applied opportunities never showed after a reload (server returned numeric ids, the UI uses slugs).
- Tutor, study-plan and essay calls overwrote the advisor chat history. Only advisor calls are stored now, and they are appended instead of rewriting the transcript.
- Course planner re-fetched `/api/school/courses` in an endless loop when a school had no verified catalog.
- Course rows lost their remove button in an earlier override; restored.
- `DELETE` routes had no error handling; malformed `Content-Length`, invalid JSON and non-list admin fields now return 400 instead of dropping the connection.
- A reset code is returned only when `APP_ENV=development` is set explicitly (it used to be the default when unset).

**Performance**
- `/api/state` upserts instead of delete-and-reinsert, uses `executemany`, and no longer carries chat messages.
- College/opportunity catalogs are cached in memory and invalidated on admin edits.
- Static files get ETag + gzip (`app.js` 111 KB -> about 26 KB on the wire).
- Expired sessions are purged periodically; the rate limiter evicts idle keys; extra indexes added.
- `app.js`: 14 dead duplicate/overridden functions removed, one delegated click handler instead of rebinding on every render, and the chat request now sends only the message (history comes from the database, never the client).
- AI: research is triggered by fewer generic words (e.g. "college" alone no longer forces a web search); reasoning effort defaults to `medium` unless the request is research or essay feedback (set `GEMINI_REASONING_EFFORT` to override).

**Security**
- Client-supplied chat history and profile are no longer trusted by the AI endpoint.
- Login spends equal hashing time for unknown emails to avoid account enumeration by timing.
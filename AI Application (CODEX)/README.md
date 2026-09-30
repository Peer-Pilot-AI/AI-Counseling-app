# Student guidance application

A local Python web application for high-school students planning courses, exploring colleges and careers, organizing applications, and getting AI-supported academic guidance. The product intentionally has no specific application name.

## Run locally

1. Install Python 3.10 or newer.
2. Copy `.env.example` to `.env`. Add a provider API key to enable AI guidance and live web research. The key stays on the Python server. OpenAI is the default; OpenRouter can be used by setting `OPENAI_BASE_URL=https://openrouter.ai/api/v1` and a compatible model such as `openai/gpt-6-luna`.
3. Start the app with `python app.py`.
4. Open `http://127.0.0.1:8000`.

## Use on iPhone or iPad

The interface adapts to iOS Safari, including narrow screens, iPhone safe areas, and the on-screen keyboard. To open it from an iPhone or iPad on the same Wi-Fi network, change `APP_HOST` to `0.0.0.0` in `.env` before starting the app, then visit `http://<computer-local-IP>:8000` in Safari. Find the computer’s local IP in its network settings. Keep the computer and app running while you use it. For access outside your home network, deploy behind HTTPS rather than exposing the development server directly.

The server uses only the Python standard library. SQLite data is stored in `student_guidance.sqlite3`; keep that file private and back it up securely. Set `APP_DATABASE` to use another local path.

## AI configuration

Defaults use `gpt-6-luna`, `high` reasoning effort, and a 180-second timeout to give complex advising questions more time. Set `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_REASONING_EFFORT`, and `OPENAI_TIMEOUT_SECONDS` in `.env` to change provider and model settings. Research-triggering requests use the configured provider's web-search tool with bounded calls; source links and retrieval dates appear with answers. Requests use `store: false`.

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

Run the requested unit checks with `python -m unittest discover -s tests`.

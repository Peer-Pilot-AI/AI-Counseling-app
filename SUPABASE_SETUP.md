# Supabase setup

PeerPilot keeps its Python server. Supabase provides **Auth** (sign-up/sign-in/password reset) and **Postgres + RLS**
for each user's profile, courses, activities, goals, roadmap progress and AI chat history. AI calls stay on the server
(`/api/assistant/*`), use the server's `GEMINI_API_KEY`, and work for any signed-in user.

1. **Create a project** at supabase.com.
2. **Run the migration:** SQL Editor, paste `supabase/migrations/001_init.sql`, Run.
3. **Auth settings:** Authentication > Providers > Email. For quick testing turn off "Confirm email"
   (if it stays on, new users get "Check your email to confirm", then sign in). Set a minimum password length of 10.
4. **Keys:** copy `.env.example` to `.env` and fill `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GEMINI_API_KEY`.
   `SUPABASE_SERVICE_ROLE_KEY` is optional (only to delete the Auth user on account deletion). Never put it in frontend files.
5. **Run:** `pip install -r requirements.txt` then `python app.py`. Without `SUPABASE_URL` the app uses the old local accounts.
6. **Admin:** create the admin user in Supabase first, then set `ADMIN_EMAIL`.

## How it works
- Sign-in goes through Supabase Auth. The browser only gets PeerPilot's own HttpOnly session cookie. Supabase tokens
  live in the server's `sessions` table and are refreshed server-side.
- On sign-in, Supabase is the source of truth: its data is loaded into the local SQLite cache (or uploaded if Supabase is empty).
  Saves and AI chat messages are then pushed to Supabase with the *user's JWT*, so RLS applies. The service key is never used for data.
- If Supabase is unreachable, the app keeps working from SQLite and logs "Supabase sync skipped".

## Verify
- `python tests/test_supabase.py` runs 22 end-to-end checks against a **simulated** Supabase and Gemini (no network needed).
- **Check RLS on your real project** (the simulation can't prove the SQL): create two users, add data as user A, then in the SQL editor run
  `set role authenticated; set request.jwt.claims = '{"sub":"<USER_B_UUID>"}'; select count(*) from public.courses;` and expect `0` for A's rows.

## Known limits
- Tasks, saved colleges/opportunities, applications and essays are still stored in local SQLite only (not in Supabase).
- Password reset: Supabase emails a link, but the app has no page to receive it, so set the new password from Supabase's hosted flow or add a reset page.
- Without the service-role key, deleting an account removes the user's Supabase *data* but not the Auth login.
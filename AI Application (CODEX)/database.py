"""SQLite persistence and seed data for the student guidance application."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("APP_DATABASE", ROOT / "student_guidance.sqlite3")).resolve()


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS legal_acceptances (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  terms_version TEXT NOT NULL, privacy_version TEXT NOT NULL,
  accepted_at TEXT NOT NULL, guardian_permission_confirmed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS legal_acceptances_user_idx ON legal_acceptances(user_id, accepted_at);
CREATE TABLE IF NOT EXISTS profiles (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  data_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_state (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  state_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS schools (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
  website TEXT NOT NULL DEFAULT '', catalog_url TEXT NOT NULL DEFAULT '',
  source_id INTEGER, verification_status TEXT NOT NULL DEFAULT 'unverified',
  last_verified TEXT, UNIQUE(name, location)
);
CREATE TABLE IF NOT EXISTS colleges (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
  majors_json TEXT NOT NULL DEFAULT '[]', summary TEXT NOT NULL DEFAULT '',
  admissions_url TEXT NOT NULL DEFAULT '', preparation_url TEXT NOT NULL DEFAULT '',
  financial_aid_url TEXT NOT NULL DEFAULT '', verification_status TEXT NOT NULL DEFAULT 'unverified',
  last_verified TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY, school_id INTEGER REFERENCES schools(id) ON DELETE CASCADE,
  name TEXT NOT NULL, level TEXT NOT NULL DEFAULT 'Standard', grade TEXT NOT NULL DEFAULT '',
  prerequisites TEXT NOT NULL DEFAULT '', credits REAL, description TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '', verification_status TEXT NOT NULL DEFAULT 'unverified',
  last_verified TEXT
);
CREATE INDEX IF NOT EXISTS courses_school_idx ON courses(school_id, grade);
CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL, category TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '', eligibility TEXT NOT NULL DEFAULT '', deadline TEXT NOT NULL DEFAULT '',
  cost TEXT NOT NULL DEFAULT 'Check official source', location TEXT NOT NULL DEFAULT '',
  application_info TEXT NOT NULL DEFAULT '', interests_json TEXT NOT NULL DEFAULT '[]',
  official_url TEXT NOT NULL DEFAULT '', source_id INTEGER,
  verification_status TEXT NOT NULL DEFAULT 'unverified', last_verified TEXT
);
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, organization TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL, accessed_at TEXT NOT NULL, source_type TEXT NOT NULL DEFAULT 'web',
  UNIQUE(url)
);
CREATE TABLE IF NOT EXISTS source_history (
  id INTEGER PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  title TEXT NOT NULL, url TEXT NOT NULL, verification_status TEXT NOT NULL DEFAULT 'unverified',
  retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  verified_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS source_history_entity_idx ON source_history(entity_type,entity_id,retrieved_at);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, due TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'Personal task',
  notes TEXT NOT NULL DEFAULT '', done INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS tasks_user_due_idx ON tasks(user_id, done, due);
CREATE TABLE IF NOT EXISTS saved_colleges (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  college_id INTEGER NOT NULL REFERENCES colleges(id) ON DELETE CASCADE,
  saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, college_id)
);
CREATE TABLE IF NOT EXISTS custom_colleges (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL, location TEXT NOT NULL DEFAULT '', majors_json TEXT NOT NULL DEFAULT '[]',
  official_url TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS saved_opportunities (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'saved', saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(user_id, opportunity_id)
);
CREATE TABLE IF NOT EXISTS applications (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  college_name TEXT NOT NULL, due TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Not Started',
  requirements_json TEXT NOT NULL DEFAULT '[]', notes TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'Student advisor', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
  citations_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS messages_conversation_idx ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS research_records (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
  intent TEXT NOT NULL, query TEXT NOT NULL, sources_json TEXT NOT NULL DEFAULT '[]',
  researched INTEGER NOT NULL DEFAULT 0, latency_ms INTEGER NOT NULL DEFAULT 0,
  error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS essays (
  id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, prompt TEXT NOT NULL DEFAULT '', body TEXT NOT NULL,
  feedback TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_feedback (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS password_resets (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0
);
"""

COLLEGE_SEEDS = [
    ("harvard", "Harvard University", "Cambridge, Massachusetts", ["Economics", "Applied Mathematics", "Government"], "Explore undergraduate fields and current first-year application information.", "https://college.harvard.edu/admissions/apply/first-year-applicants", "https://college.harvard.edu/admissions/apply/application-requirements", "https://college.harvard.edu/financial-aid", "2026-09-26"),
    ("stanford", "Stanford University", "Stanford, California", ["Economics", "Management Science & Engineering", "Mathematics"], "Explore undergraduate programs, first-year application details, and curriculum guidance.", "https://admission.stanford.edu/apply/first-year/index.html", "https://admission.stanford.edu/apply/first-year/prepare.html", "https://financialaid.stanford.edu/", "2026-09-26"),
]

OPPORTUNITY_SEEDS = [
    ("hs-fed-challenge", "National High School Fed Challenge", "Competitions", "Student teams research an economic theme and develop skills in research, data literacy, writing, and analysis.", "For grades 9–12. Review current participation instructions and regional details on the official site.", "Check official site", "Check official source", "United States · regional", "Check official site for application steps.", ["Economics", "Finance", "Public speaking"], "https://www.federalreserve.gov/aboutthefed/educational-tools/national-high-school-fed-challenge.htm", "2026-09-26"),
    ("national-economics-challenge", "National Economics Challenge", "Competitions", "A team competition where high-school students apply economic analysis and knowledge of the world economy.", "Divisions and state qualification details are on the official site.", "Check official site", "Check official source", "United States", "See the official site for registration and state contacts.", ["Economics", "Finance"], "https://www.councilforeconed.org/programs/for-students/national-economic-challenge/", "2026-09-26"),
    ("stock-market-game", "SIFMA Foundation Stock Market Game", "Programs", "A classroom simulation that introduces investing and financial markets.", "Grades 4–12 are listed by the official program; participation requirements can vary by route.", "Season dates vary", "No cost / low cost; verify current terms", "Online / classroom", "An educator, parent, or other adult may need to enroll minors; check the official site.", ["Finance", "Economics"], "https://www.stockmarketgame.org/", "2026-09-26"),
    ("careerone-stop-scholarship-finder", "CareerOneStop Scholarship Finder", "Scholarships", "Search scholarship, grant, and other education-award listings, then confirm details with each sponsor.", "Varies by award. Confirm current eligibility with the sponsor.", "Varies", "Varies", "United States", "Use the official finder and review each sponsor's application page.", ["College planning"], "https://www.careeronestop.org/Toolkit/Training/find-scholarships.aspx", "2026-09-26"),
    ("harvard-summer-high-school", "Harvard Summer School high-school programs", "Summer programs", "Compare high-school summer programs and consider whether one fits your interests, schedule, and budget.", "Program-specific. Review current grade, age, and application details on the official page.", "Seasonal · check official site", "Program fees vary; check official page", "Online / campus", "Review program-specific application information on the official page.", ["Economics", "Research"], "https://summer.harvard.edu/high-school-programs/", "2026-09-26"),
]


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 20000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        for slug, name, location, majors, summary, admissions, prep, aid, verified in COLLEGE_SEEDS:
            conn.execute("""INSERT OR IGNORE INTO colleges
                (slug,name,location,majors_json,summary,admissions_url,preparation_url,financial_aid_url,verification_status,last_verified)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (slug,name,location,json.dumps(majors),summary,admissions,prep,aid,"verified_link_only",verified))
        for row in OPPORTUNITY_SEEDS:
            slug,name,category,description,eligibility,deadline,cost,location,application,interests,url,verified = row
            source = conn.execute("SELECT id FROM sources WHERE url=?",(url,)).fetchone()
            if not source:
                cur = conn.execute("INSERT INTO sources(title,organization,url,accessed_at) VALUES(?,?,?,?)",(name,name,url,verified))
                source_id = cur.lastrowid
            else:
                source_id = source["id"]
            conn.execute("""INSERT OR IGNORE INTO opportunities
                (slug,name,category,description,eligibility,deadline,cost,location,application_info,interests_json,official_url,source_id,verification_status,last_verified)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (slug,name,category,description,eligibility,deadline,cost,location,application,json.dumps(interests),url,source_id,"verified_link_only",verified))
        # Sessions are short-lived; old entries can be removed at startup.
        conn.execute("DELETE FROM sessions WHERE expires_at < strftime('%s','now')")


def json_load(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback

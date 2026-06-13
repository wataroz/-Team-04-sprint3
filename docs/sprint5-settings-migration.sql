-- Sprint 5: Settings page schema extensions
-- =========================================
-- Run on Render Postgres shell BEFORE pushing the code that depends on these
-- columns. SQLAlchemy's create_all() does NOT alter existing tables, so the
-- new columns must be added manually on the live database.
--
-- How to run on Render:
--   1) Open Render Dashboard → Database "moneymind-test-db" → Connect → PSQL
--   2) Paste this whole file and hit Enter
--   3) Confirm "ALTER TABLE" output for each statement
--
-- Local SQLite note:
--   For a fresh local DB, Base.metadata.create_all() will pick up the new
--   columns automatically — no action needed.
--   For an EXISTING local data/moneymind.db, either:
--     (a) Delete data/moneymind.db and re-login to start fresh (easiest), OR
--     (b) Run the equivalent ALTER TABLE in sqlite3 CLI:
--           sqlite3 data/moneymind.db
--           ALTER TABLE preferences ADD COLUMN budget_alert_enabled BOOLEAN DEFAULT 1;
--           ALTER TABLE preferences ADD COLUMN line_notify_enabled BOOLEAN DEFAULT 1;
--           ALTER TABLE users ADD COLUMN display_name VARCHAR(100);
--           ALTER TABLE users ADD COLUMN delete_scheduled_at DATETIME;
--           CREATE INDEX idx_users_delete_scheduled ON users(delete_scheduled_at);

-- ─── Preference: notification toggles ──────────────────────────────────────
ALTER TABLE preferences ADD COLUMN IF NOT EXISTS budget_alert_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE preferences ADD COLUMN IF NOT EXISTS line_notify_enabled BOOLEAN DEFAULT TRUE;

-- ─── User: display name + grace period delete ─────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS delete_scheduled_at TIMESTAMP NULL;

-- ─── Partial index for grace cleanup cron ─────────────────────────────────
-- Only indexes rows whose delete is actually scheduled — small index, fast
-- scan for the daily cleanup job which queries WHERE delete_scheduled_at < now().
CREATE INDEX IF NOT EXISTS idx_users_delete_scheduled
  ON users(delete_scheduled_at)
  WHERE delete_scheduled_at IS NOT NULL;

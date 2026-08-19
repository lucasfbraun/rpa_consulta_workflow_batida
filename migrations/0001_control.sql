CREATE TABLE IF NOT EXISTS schedules (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  time TEXT NOT NULL,
  weekdays TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  last_enqueued_on TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL CHECK (source IN ('manual', 'schedule')),
  schedule_id TEXT REFERENCES schedules(id) ON DELETE SET NULL,
  requested_at TEXT NOT NULL,
  scheduled_for TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  claimed_at TEXT,
  finished_at TEXT,
  result TEXT
);

CREATE INDEX IF NOT EXISTS commands_status_requested ON commands(status, requested_at);
CREATE INDEX IF NOT EXISTS commands_requested_at ON commands(requested_at DESC);

CREATE TABLE IF NOT EXISTS control_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

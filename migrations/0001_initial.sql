PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','operator','viewer')));
CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS auth_limits (id TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS equipment (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), name TEXT NOT NULL, category TEXT NOT NULL CHECK(category IN ('camera','lens','light','audio','accessory')), serial TEXT NOT NULL DEFAULT '', day_rate INTEGER NOT NULL CHECK(day_rate>=0), state TEXT NOT NULL DEFAULT 'available' CHECK(state IN ('available','maintenance','retired')), UNIQUE(id,workspace_id));
CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', UNIQUE(id,workspace_id));
CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id), equipment_id TEXT NOT NULL, customer_id TEXT NOT NULL, starts_on TEXT NOT NULL, ends_on TEXT NOT NULL, day_rate INTEGER NOT NULL CHECK(day_rate>=0), status TEXT NOT NULL DEFAULT 'reserved' CHECK(status IN ('reserved','out','returned','cancelled')), notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, CHECK(ends_on>starts_on), FOREIGN KEY(equipment_id,workspace_id) REFERENCES equipment(id,workspace_id), FOREIGN KEY(customer_id,workspace_id) REFERENCES customers(id,workspace_id));
CREATE INDEX IF NOT EXISTS reservation_lookup ON reservations(workspace_id,equipment_id,starts_on,ends_on,status);
CREATE INDEX IF NOT EXISTS session_expiry ON sessions(expires_at);
CREATE TRIGGER IF NOT EXISTS booking_insert_guard BEFORE INSERT ON reservations WHEN NEW.status IN ('reserved','out') BEGIN
  SELECT RAISE(ABORT,'equipment_unavailable') WHERE NOT EXISTS(SELECT 1 FROM equipment WHERE id=NEW.equipment_id AND workspace_id=NEW.workspace_id AND state='available');
  SELECT RAISE(ABORT,'reservation_conflict') WHERE EXISTS(SELECT 1 FROM reservations WHERE workspace_id=NEW.workspace_id AND equipment_id=NEW.equipment_id AND status IN ('reserved','out') AND starts_on<NEW.ends_on AND ends_on>NEW.starts_on);
END;
CREATE TRIGGER IF NOT EXISTS booking_update_guard BEFORE UPDATE OF equipment_id,starts_on,ends_on,status ON reservations WHEN NEW.status IN ('reserved','out') BEGIN
  SELECT RAISE(ABORT,'equipment_unavailable') WHERE NEW.status='out' AND OLD.status!='out' AND NOT EXISTS(SELECT 1 FROM equipment WHERE id=NEW.equipment_id AND workspace_id=NEW.workspace_id AND state='available');
  SELECT RAISE(ABORT,'reservation_conflict') WHERE EXISTS(SELECT 1 FROM reservations WHERE id!=NEW.id AND workspace_id=NEW.workspace_id AND equipment_id=NEW.equipment_id AND status IN ('reserved','out') AND starts_on<NEW.ends_on AND ends_on>NEW.starts_on);
END;
CREATE TRIGGER IF NOT EXISTS equipment_limit BEFORE INSERT ON equipment BEGIN
  SELECT RAISE(ABORT,'equipment_limit') WHERE (SELECT COUNT(*) FROM equipment WHERE workspace_id=NEW.workspace_id)>=50;
END;

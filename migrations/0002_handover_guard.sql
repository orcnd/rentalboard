CREATE UNIQUE INDEX IF NOT EXISTS one_active_handover ON reservations(equipment_id) WHERE status='out';
DROP TRIGGER IF EXISTS booking_update_guard;
CREATE TRIGGER booking_update_guard BEFORE UPDATE OF equipment_id,starts_on,ends_on,status ON reservations WHEN NEW.status IN ('reserved','out') BEGIN
  SELECT RAISE(ABORT,'equipment_unavailable') WHERE NEW.status='out' AND OLD.status!='out' AND NOT EXISTS(SELECT 1 FROM equipment WHERE id=NEW.equipment_id AND workspace_id=NEW.workspace_id AND state='available');
  SELECT RAISE(ABORT,'equipment_already_out') WHERE NEW.status='out' AND EXISTS(SELECT 1 FROM reservations WHERE id!=NEW.id AND equipment_id=NEW.equipment_id AND status='out');
  SELECT RAISE(ABORT,'reservation_conflict') WHERE EXISTS(SELECT 1 FROM reservations WHERE id!=NEW.id AND workspace_id=NEW.workspace_id AND equipment_id=NEW.equipment_id AND status IN ('reserved','out') AND starts_on<NEW.ends_on AND ends_on>NEW.starts_on);
END;

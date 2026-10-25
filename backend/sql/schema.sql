CREATE DATABASE IF NOT EXISTS eye_care
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE eye_care;

CREATE TABLE IF NOT EXISTS devices (
  device_id VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS device_configs (
  device_id VARCHAR(64) NOT NULL,
  lux_min INT NOT NULL DEFAULT 150,
  lux_max INT NOT NULL DEFAULT 1000,
  sit_warn_min INT NOT NULL DEFAULT 45,
  sit_strong_min INT NOT NULL DEFAULT 60,
  buzzer_enabled TINYINT(1) NOT NULL DEFAULT 1,
  report_interval INT NOT NULL DEFAULT 15,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (device_id),
  CONSTRAINT fk_config_device
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS telemetry (
  id INT NOT NULL AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  ts DATETIME NOT NULL,
  lux INT NULL,
  temperature DECIMAL(5,2) NULL,
  humidity DECIMAL(5,2) NULL,
  light_state VARCHAR(32) NULL,
  occupied TINYINT(1) NULL,
  sit_cont_min INT NULL,
  sit_total_min INT NULL,
  last_motion_min INT NULL,
  risk DECIMAL(4,2) NULL,
  risk_level VARCHAR(16) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_telemetry_device_ts (device_id, ts),
  CONSTRAINT fk_telemetry_device
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS events (
  id INT NOT NULL AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  ts DATETIME NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  level VARCHAR(16) NULL,
  payload JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_events_device_ts (device_id, ts),
  KEY idx_events_type (event_type),
  CONSTRAINT fk_events_device
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS commands (
  id INT NOT NULL AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  command_name VARCHAR(64) NOT NULL,
  params JSON NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'pending',
  request_id VARCHAR(64) NOT NULL,
  requested_by VARCHAR(64) NOT NULL DEFAULT 'app',
  result JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  confirmed_at DATETIME NULL,
  sent_at DATETIME NULL,
  acked_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_commands_request_id (request_id),
  KEY idx_commands_device_created (device_id, created_at),
  KEY idx_commands_status (status),
  CONSTRAINT fk_commands_device
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reports (
  id INT NOT NULL AUTO_INCREMENT,
  device_id VARCHAR(64) NOT NULL,
  report_date DATE NOT NULL,
  summary TEXT NULL,
  risk_level VARCHAR(16) NULL,
  data JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_report_device_date (device_id, report_date),
  KEY idx_reports_device_date (device_id, report_date),
  CONSTRAINT fk_reports_device
    FOREIGN KEY (device_id) REFERENCES devices (device_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO devices (device_id, name)
VALUES ('hi3861_001', '工位1')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO device_configs (device_id)
VALUES ('hi3861_001')
ON DUPLICATE KEY UPDATE device_id = VALUES(device_id);

export interface Telemetry {
  id: number;
  device_id: string;
  ts: string;
  lux?: number;
  temperature?: number;
  humidity?: number;
  light_state?: string;
  occupied?: boolean;
  sit_cont_min?: number;
  sit_total_min?: number;
  last_motion_min?: number;
  risk?: number;
  risk_level?: string;
  created_at: string;
}

export interface ThresholdConfig {
  device_id: string;
  lux_min: number;
  lux_max: number;
  sit_warn_min: number;
  sit_strong_min: number;
  buzzer_enabled: boolean;
  report_interval: number;
  updated_at: string;
}

export interface ThresholdUpdate {
  lux_min?: number;
  lux_max?: number;
  sit_warn_min?: number;
  sit_strong_min?: number;
  buzzer_enabled?: boolean;
  report_interval?: number;
}

export interface LatestData {
  device_id: string;
  telemetry?: Telemetry;
  config?: ThresholdConfig;
}

export interface HistoryData {
  device_id: string;
  items: Telemetry[];
}

export interface CommandInfo {
  id: number;
  device_id: string;
  command_name: string;
  params: Object;
  status: string;
  request_id: string;
  requested_by: string;
  result?: Object;
  created_at: string;
  confirmed_at?: string;
  sent_at?: string;
  acked_at?: string;
}

export interface ReportData {
  source?: string;
  model?: string;
  engine?: string;
  generated_at?: string;
  sample_count?: number;
  avg_lux?: number;
  min_lux?: number;
  max_lux?: number;
  avg_temperature?: number;
  avg_humidity?: number;
  max_sit_cont_min?: number;
  max_risk?: number;
  poor_light_ratio?: number;
  risk_level?: string;
  insights?: AiInsight[];
  recommendations?: string[];
}

export interface AiInsight {
  title: string;
  detail: string;
  level: string;
}

export interface ChartSegment {
  label: string;
  value: number;
  color: string;
}

export interface DailyReport {
  id: number;
  device_id: string;
  report_date: string;
  summary?: string;
  risk_level?: string;
  data: ReportData;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

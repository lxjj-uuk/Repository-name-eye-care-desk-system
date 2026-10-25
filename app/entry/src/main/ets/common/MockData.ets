import { AppConfig } from './AppConfig';
import {
  AiInsight,
  DailyReport,
  HistoryData,
  LatestData,
  Telemetry,
  ThresholdConfig,
  ThresholdUpdate
} from './Models';

export class MockData {
  private static thresholds: ThresholdConfig = {
    device_id: AppConfig.deviceId,
    lux_min: 150,
    lux_max: 1000,
    sit_warn_min: 45,
    sit_strong_min: 60,
    buzzer_enabled: true,
    report_interval: 15,
    updated_at: new Date().toISOString()
  };

  static getLatest(): LatestData {
    const history = MockData.getHistory().items;
    return {
      device_id: AppConfig.deviceId,
      telemetry: history[history.length - 1],
      config: MockData.thresholds
    };
  }

  static getHistory(): HistoryData {
    const items: Telemetry[] = [];
    const now = Date.now();
    for (let i = 47; i >= 0; i--) {
      const moment = new Date(now - i * 30 * 60 * 1000);
      const hour = moment.getHours();
      const daylight = Math.max(0, Math.sin((hour - 6) / 12 * Math.PI));
      const lux = Math.round(90 + daylight * 620 + Math.sin(i / 3) * 55);
      const occupied = hour >= 8 && hour <= 21 && i % 13 !== 0;
      const sit = occupied ? Math.min(92, 12 + (47 - i) * 2) : 0;
      let risk = 0.08;
      if (occupied) {
        risk = Math.min(0.94, 0.18 + (lux < 150 ? 0.32 : 0) + sit / 260);
      }
      let level = 'low';
      if (risk >= 0.7) {
        level = 'high';
      } else if (risk >= 0.4) {
        level = 'medium';
      }
      let lightState = 'idle';
      if (occupied) {
        lightState = lux < 150 ? 'dark' : lux > 1000 ? 'too_bright' : 'ok';
      }
      const item: Telemetry = {
        id: 1000 + (47 - i),
        device_id: AppConfig.deviceId,
        ts: moment.toISOString(),
        lux: lux,
        temperature: Math.round((23.6 + Math.sin(i / 5) * 1.4) * 10) / 10,
        humidity: Math.round(50 + Math.sin(i / 7) * 6),
        light_state: lightState,
        occupied: occupied,
        sit_cont_min: sit,
        sit_total_min: occupied ? 180 : 150,
        last_motion_min: occupied ? (i % 7) + 1 : 18,
        risk: Math.round(risk * 100) / 100,
        risk_level: level,
        created_at: moment.toISOString()
      };
      items.push(item);
    }
    return {
      device_id: AppConfig.deviceId,
      items: items
    };
  }

  static getThresholds(): ThresholdConfig {
    return MockData.thresholds;
  }

  static updateThresholds(update: ThresholdUpdate): ThresholdConfig {
    if (update.lux_min !== undefined) {
      MockData.thresholds.lux_min = update.lux_min;
    }
    if (update.lux_max !== undefined) {
      MockData.thresholds.lux_max = update.lux_max;
    }
    if (update.sit_warn_min !== undefined) {
      MockData.thresholds.sit_warn_min = update.sit_warn_min;
    }
    if (update.sit_strong_min !== undefined) {
      MockData.thresholds.sit_strong_min = update.sit_strong_min;
    }
    if (update.report_interval !== undefined) {
      MockData.thresholds.report_interval = update.report_interval;
    }
    MockData.thresholds.updated_at = new Date().toISOString();
    return MockData.thresholds;
  }

  static getDailyReport(): DailyReport {
    const history = MockData.getHistory().items;
    let luxSum = 0;
    let luxCount = 0;
    let minLux = 200000;
    let maxLux = 0;
    let tempSum = 0;
    let tempCount = 0;
    let maxSit = 0;
    let maxRisk = 0;
    let poorLight = 0;
    for (let i = 0; i < history.length; i++) {
      const item = history[i];
      if (item.lux !== undefined) {
        luxSum += item.lux;
        luxCount++;
        minLux = Math.min(minLux, item.lux);
        maxLux = Math.max(maxLux, item.lux);
        if (item.lux < MockData.thresholds.lux_min) {
          poorLight++;
        }
      }
      if (item.temperature !== undefined) {
        tempSum += item.temperature;
        tempCount++;
      }
      if (item.sit_cont_min !== undefined) {
        maxSit = Math.max(maxSit, item.sit_cont_min);
      }
      if (item.risk !== undefined) {
        maxRisk = Math.max(maxRisk, item.risk);
      }
    }
    const avgLux = luxCount > 0 ? Math.round(luxSum / luxCount) : 0;
    const avgTemp = tempCount > 0 ? Math.round(tempSum / tempCount * 10) / 10 : 0;
    const poorRatio = luxCount > 0 ? Math.round(poorLight / luxCount * 100) / 100 : 0;
    const insights: AiInsight[] = [
      {
        title: '午后光照偏低',
        detail: '14:00-16:00 平均照度约 210 lux，低于建议的 300 lux。',
        level: 'warn'
      },
      {
        title: '连续久坐偏长',
        detail: '最长连续久坐 72 分钟，建议每小时起身活动 5 分钟。',
        level: 'high'
      },
      {
        title: '温湿度较舒适',
        detail: '温度 23-25°C、湿度 45%-55%，处于舒适区间。',
        level: 'good'
      }
    ];
    const recommendations: string[] = [
      '把台灯调亮一档',
      '设置 45 分钟久坐提醒',
      '下午安排一次 5 分钟远眺'
    ];
    return {
      id: 1,
      device_id: AppConfig.deviceId,
      report_date: new Date().toISOString().substring(0, 10),
      summary: `今日共记录 ${history.length} 条数据；平均照度 ${avgLux} lux，偏低光照占比 ${Math.round(poorRatio * 100)}%，最长连续久坐 ${maxSit} 分钟。整体用眼负担处于中等水平，建议优先改善午后光照和久坐节奏。`,
      risk_level: 'medium',
      data: {
        sample_count: history.length,
        avg_lux: avgLux,
        min_lux: minLux,
        max_lux: maxLux,
        avg_temperature: avgTemp,
        avg_humidity: 51,
        max_sit_cont_min: maxSit,
        max_risk: Math.round(maxRisk * 100) / 100,
        poor_light_ratio: poorRatio,
        risk_level: 'medium',
        insights: insights,
        recommendations: recommendations
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
  }
}

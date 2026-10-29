import { http } from '@kit.NetworkKit';
import { AppConfig } from './AppConfig';
import { MockData } from './MockData';
import {
  CommandInfo,
  DailyReport,
  HistoryData,
  LatestData,
  LoginResponse,
  ThresholdConfig,
  ThresholdUpdate
} from './Models';

interface LoginBody {
  username: string;
  password: string;
}

export class ApiClient {
  private static token: string = '';

  static getBaseUrl(): string {
    return AppConfig.baseUrl;
  }

  static setBaseUrl(url: string): void {
    let value = url.trim();
    while (value.endsWith('/')) {
      value = value.substring(0, value.length - 1);
    }
    AppConfig.baseUrl = value;
  }

  static setUseMockData(value: boolean): void {
    AppConfig.useMockData = value;
  }

  private static async request(
    method: http.RequestMethod,
    path: string,
    body?: Object
  ): Promise<string> {
    const client = http.createHttp();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Authorization': ApiClient.token.length > 0 ? `Bearer ${ApiClient.token}` : '',
      'Cache-Control': 'no-cache',
      'Pragma': 'no-cache'
    };
    const options: http.HttpRequestOptions = {
      method: method,
      header: headers,
      connectTimeout: 15000,
      readTimeout: 180000
    };
    if (body !== undefined) {
      options.extraData = JSON.stringify(body);
    }
    try {
      let requestUrl = `${AppConfig.baseUrl}${path}`;
      if (method === http.RequestMethod.GET) {
        requestUrl += `${path.indexOf('?') >= 0 ? '&' : '?'}_t=${Date.now()}`;
      }
      const response = await client.request(requestUrl, options);
      const text = response.result as string;
      if (response.responseCode >= 400) {
        throw new Error(`HTTP ${response.responseCode}: ${text}`);
      }
      return text;
    } catch (err) {
      const error = err as Error;
      if (error && error.message && error.message.length > 0) {
        throw new Error(error.message);
      }
      throw new Error('网络请求失败，请检查后端地址和网络连接');
    } finally {
      client.destroy();
    }
  }

  static async login(username: string, password: string): Promise<void> {
    const body: LoginBody = {
      username: username,
      password: password
    };
    const text = await ApiClient.request(
      http.RequestMethod.POST,
      '/auth/login',
      body
    );
    const data = JSON.parse(text) as LoginResponse;
    ApiClient.token = data.access_token;
  }

  static async ensureLogin(): Promise<void> {
    if (ApiClient.token.length === 0) {
      await ApiClient.login(AppConfig.demoUser, AppConfig.demoPassword);
    }
  }

  static async getLatest(): Promise<LatestData> {
    if (AppConfig.useMockData) {
      return MockData.getLatest();
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.GET,
      `/devices/${AppConfig.deviceId}/latest`
    );
    return JSON.parse(text) as LatestData;
  }

  static async getHistory(): Promise<HistoryData> {
    if (AppConfig.useMockData) {
      return MockData.getHistory();
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.GET,
      `/devices/${AppConfig.deviceId}/history?limit=200`
    );
    return JSON.parse(text) as HistoryData;
  }

  static async getThresholds(): Promise<ThresholdConfig> {
    if (AppConfig.useMockData) {
      return MockData.getThresholds();
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.GET,
      `/devices/${AppConfig.deviceId}/thresholds`
    );
    return JSON.parse(text) as ThresholdConfig;
  }

  static async updateThresholds(update: ThresholdUpdate): Promise<ThresholdConfig> {
    if (AppConfig.useMockData) {
      return MockData.updateThresholds(update);
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.PUT,
      `/devices/${AppConfig.deviceId}/thresholds`,
      update
    );
    return JSON.parse(text) as ThresholdConfig;
  }

  static async confirmLatestPending(): Promise<CommandInfo | null> {
    if (AppConfig.useMockData) {
      return null;
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.GET,
      `/devices/${AppConfig.deviceId}/commands?limit=20`
    );
    const list = JSON.parse(text) as CommandInfo[];
    for (let i = 0; i < list.length; i++) {
      if (list[i].status === 'pending') {
        return await ApiClient.confirmCommand(list[i].id);
      }
    }
    return null;
  }

  static async confirmCommand(id: number): Promise<CommandInfo> {
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.POST,
      `/commands/${id}/confirm`
    );
    return JSON.parse(text) as CommandInfo;
  }

  static async getPendingCommands(): Promise<CommandInfo[]> {
    if (AppConfig.useMockData) {
      return [];
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.GET,
      `/devices/${AppConfig.deviceId}/commands?limit=20`
    );
    const list = JSON.parse(text) as CommandInfo[];
    const pending: CommandInfo[] = [];
    for (let i = 0; i < list.length; i++) {
      if (list[i].status === 'pending') {
        pending.push(list[i]);
      }
    }
    return pending;
  }

  static async getDailyReport(date: string): Promise<DailyReport> {
    if (AppConfig.useMockData) {
      return MockData.getDailyReport();
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.GET,
      `/devices/${AppConfig.deviceId}/reports/daily?date=${date}`
    );
    return JSON.parse(text) as DailyReport;
  }

  static async refreshDailyReport(date: string): Promise<DailyReport> {
    if (AppConfig.useMockData) {
      return MockData.getDailyReport();
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.POST,
      `/devices/${AppConfig.deviceId}/reports/daily/generate?date=${date}`
    );
    return JSON.parse(text) as DailyReport;
  }

  static async generateAiReport(date: string): Promise<DailyReport> {
    if (AppConfig.useMockData) {
      return MockData.getDailyReport();
    }
    await ApiClient.ensureLogin();
    const text = await ApiClient.request(
      http.RequestMethod.POST,
      `/devices/${AppConfig.deviceId}/reports/ai?date=${date}`
    );
    return JSON.parse(text) as DailyReport;
  }
}

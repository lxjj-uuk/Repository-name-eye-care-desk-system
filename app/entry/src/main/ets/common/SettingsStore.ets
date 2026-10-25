import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';
import { AppConfig } from './AppConfig';

export class SettingsStore {
  private static context: common.UIAbilityContext | null = null;
  private static readonly STORE_NAME: string = 'eye_care_settings';

  static init(context: common.UIAbilityContext): void {
    SettingsStore.context = context;
  }

  static async load(): Promise<void> {
    if (SettingsStore.context === null) {
      return;
    }
    const prefs = await preferences.getPreferences(
      SettingsStore.context,
      SettingsStore.STORE_NAME
    );
    AppConfig.useMockData = prefs.getSync('useMockData', false) as boolean;
    AppConfig.baseUrl = prefs.getSync('baseUrl', AppConfig.baseUrl) as string;
  }

  static async save(): Promise<void> {
    if (SettingsStore.context === null) {
      return;
    }
    const prefs = await preferences.getPreferences(
      SettingsStore.context,
      SettingsStore.STORE_NAME
    );
    prefs.putSync('useMockData', AppConfig.useMockData);
    prefs.putSync('baseUrl', AppConfig.baseUrl);
    await prefs.flush();
  }
}

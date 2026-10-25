import { ApiClient } from '../common/ApiClient';
import { AppConfig } from '../common/AppConfig';
import { SettingsStore } from '../common/SettingsStore';

@Component
export struct SettingsPage {
  @State baseUrl: string = ApiClient.getBaseUrl();
  @State mockMode: boolean = AppConfig.useMockData;
  @State luxMin: string = '150';
  @State luxMax: string = '1000';
  @State sitWarn: string = '45';
  @State sitStrong: string = '60';
  @State message: string = '';
  @State loading: boolean = false;

  aboutToAppear(): void {
    this.initSettings();
  }

  async initSettings(): Promise<void> {
    await SettingsStore.load();
    this.mockMode = AppConfig.useMockData;
    this.baseUrl = ApiClient.getBaseUrl();
    await this.load();
  }

  async load(): Promise<void> {
    try {
      const config = await ApiClient.getThresholds();
      this.luxMin = config.lux_min.toString();
      this.luxMax = config.lux_max.toString();
      this.sitWarn = config.sit_warn_min.toString();
      this.sitStrong = config.sit_strong_min.toString();
      this.message = '';
    } catch (err) {
      this.message = `${err}`;
    }
  }

  async save(): Promise<void> {
    this.loading = true;
    try {
      await ApiClient.updateThresholds({
        lux_min: Number(this.luxMin),
        lux_max: Number(this.luxMax),
        sit_warn_min: Number(this.sitWarn),
        sit_strong_min: Number(this.sitStrong)
      });
      const command = await ApiClient.confirmLatestPending();
      if (AppConfig.useMockData) {
        this.message = '演示模式：阈值已保存，未真实下发';
      } else {
        this.message = command ? '阈值已保存并下发' : '阈值已保存，等待确认';
      }
    } catch (err) {
      this.message = `${err}`;
    } finally {
      this.loading = false;
    }
  }

  @Builder
  field(label: string, value: string, onChange: (value: string) => void) {
    Column({ space: 5 }) {
      Text(label)
        .fontSize(11)
        .fontColor('#8A94A6')
      TextInput({ text: value })
        .type(InputType.Number)
        .height(42)
        .backgroundColor('#F5F7FA')
        .borderRadius(10)
        .onChange((next: string) => {
          onChange(next);
        })
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  build() {
    Scroll() {
      Column({ space: 14 }) {
        Text('设备与阈值')
          .fontSize(20)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
          .width('100%')

        Row() {
          Column({ space: 4 }) {
            Text('演示数据模式')
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor('#1B2430')
            Text('开启后使用模拟数据，关闭后连接真实后端')
              .fontSize(11)
              .fontColor('#8A94A6')
          }
          .layoutWeight(1)
          .alignItems(HorizontalAlign.Start)
          Toggle({ type: ToggleType.Switch, isOn: this.mockMode })
            .selectedColor('#1EC8A5')
            .onChange((isOn: boolean) => {
              this.mockMode = isOn;
              ApiClient.setUseMockData(isOn);
              SettingsStore.save();
              this.message = isOn ? '已切换到演示数据' : '已切换到真实后端';
              this.load();
            })
        }
        .padding(16)
        .backgroundColor('#FFFFFF')
        .borderRadius(18)
        .width('100%')

        Column({ space: 8 }) {
          Text('后端地址')
            .fontSize(11)
            .fontColor('#8A94A6')
          TextInput({ text: this.baseUrl })
            .height(42)
            .backgroundColor('#F5F7FA')
            .borderRadius(10)
            .onChange((value: string) => {
              this.baseUrl = value;
            })
          Button('保存地址')
            .fontSize(12)
            .height(34)
            .backgroundColor('#E8EEF5')
            .fontColor('#35506A')
            .onClick(() => {
              ApiClient.setBaseUrl(this.baseUrl);
              SettingsStore.save();
              this.message = '后端地址已更新';
            })
        }
        .padding(16)
        .backgroundColor('#FFFFFF')
        .borderRadius(18)
        .width('100%')
        .alignItems(HorizontalAlign.Start)

        Column({ space: 10 }) {
          Text('提醒阈值')
            .fontSize(15)
            .fontWeight(FontWeight.Medium)
            .fontColor('#1B2430')
            .width('100%')
          this.field('偏低光照阈值 (lux)', this.luxMin, (value: string) => {
            this.luxMin = value;
          })
          this.field('偏高光照阈值 (lux)', this.luxMax, (value: string) => {
            this.luxMax = value;
          })
          this.field('久坐轻提醒 (min)', this.sitWarn, (value: string) => {
            this.sitWarn = value;
          })
          this.field('久坐强提醒 (min)', this.sitStrong, (value: string) => {
            this.sitStrong = value;
          })

          Button(this.loading ? '保存中...' : '保存并下发')
            .width('100%')
            .height(42)
            .backgroundColor('#0F2D45')
            .fontColor('#FFFFFF')
            .enabled(!this.loading)
            .onClick(() => {
              this.save();
            })

          if (this.message.length > 0) {
            Text(this.message)
              .fontSize(11)
              .fontColor('#5F6B7A')
          }
        }
        .padding(16)
        .backgroundColor('#FFFFFF')
        .borderRadius(18)
        .width('100%')
        .alignItems(HorizontalAlign.Start)

        Column({ space: 7 }) {
          Row() {
            Text('AI 分析准备')
              .fontSize(15)
              .fontWeight(FontWeight.Bold)
              .fontColor('#0B4F43')
            Blank()
            Text('READY')
              .fontSize(9)
              .fontColor('#0B6E5A')
              .backgroundColor('#C9F0E5')
              .borderRadius(8)
              .padding({ left: 7, right: 7, top: 3, bottom: 3 })
          }
          .width('100%')
          Text('日报数据已预留 insights 和 recommendations 字段，后续接入大模型后可以直接显示原因分析、建议和闭环命令。')
            .fontSize(12)
            .fontColor('#24594F')
            .lineHeight(20)
        }
        .padding(16)
        .backgroundColor('#E8F8F2')
        .borderRadius(18)
        .width('100%')
        .alignItems(HorizontalAlign.Start)
      }
      .padding(16)
      .width('100%')
    }
    .width('100%')
    .height('100%')
  }
}

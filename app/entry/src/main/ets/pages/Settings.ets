import { abilityAccessCtrl, common, Permissions } from '@kit.AbilityKit';
import { ApiClient } from '../common/ApiClient';
import { AppConfig } from '../common/AppConfig';
import { BleDeviceInfo, BleProvisioner } from '../common/BleProvisioner';
import { SettingsStore } from '../common/SettingsStore';

interface BleStatusMessage {
  state: string;
  detail?: string;
  ip?: string;
  device_id?: string;
}

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
  @State bleDevices: BleDeviceInfo[] = [];
  @State bleScanning: boolean = false;
  @State bleConnecting: boolean = false;
  @State connectedBleId: string = '';
  @State connectedBleName: string = '';
  @State wifiSsid: string = '';
  @State wifiPassword: string = '';
  @State bleStatusText: string = '尚未连接配网设备';

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

  private async ensureBluetoothPermission(): Promise<boolean> {
    const manager = abilityAccessCtrl.createAtManager();
    const permissions: Array<Permissions> = ['ohos.permission.ACCESS_BLUETOOTH'];
    const context = getContext(this) as common.UIAbilityContext;
    const result = await manager.requestPermissionsFromUser(context, permissions);
    return result.authResults.length > 0 && result.authResults[0] === 0;
  }

  private updateBleStatus(text: string): void {
    try {
      const status = JSON.parse(text) as BleStatusMessage;
      if (status.state === 'connected' || status.state === 'ble_ready') {
        this.bleStatusText = '蓝牙已连接，等待 WiFi 凭证';
      } else if (status.state === 'credentials_saved') {
        this.bleStatusText = 'WiFi 凭证已保存，正在连接';
      } else if (status.state === 'wifi_connecting') {
        this.bleStatusText = `正在连接 WiFi：${status.detail ?? ''}`;
      } else if (status.state === 'wifi_failed') {
        this.bleStatusText = 'WiFi 连接失败，请检查 2.4GHz 名称和密码';
      } else if (status.state === 'online') {
        this.bleStatusText = `设备已联网，IP：${status.ip ?? status.detail ?? ''}`;
      } else if (status.state === 'provisioning_error') {
        this.bleStatusText = `配网失败：${status.detail ?? '参数错误'}`;
      } else {
        this.bleStatusText = text;
      }
    } catch (err) {
      this.bleStatusText = text;
    }
  }

  async scanBleDevices(): Promise<void> {
    this.message = '';
    try {
      const granted = await this.ensureBluetoothPermission();
      if (!granted) {
        this.bleStatusText = '没有蓝牙权限，无法扫描设备';
        return;
      }
      BleProvisioner.close();
      this.bleDevices = [];
      this.connectedBleId = '';
      this.connectedBleName = '';
      this.bleScanning = true;
      this.bleStatusText = '正在扫描 EyeCare 设备...';
      BleProvisioner.startScan((device: BleDeviceInfo) => {
        let exists = false;
        for (let i = 0; i < this.bleDevices.length; i++) {
          if (this.bleDevices[i].deviceId === device.deviceId) {
            exists = true;
            break;
          }
        }
        if (!exists) {
          const next = this.bleDevices.slice();
          next.push(device);
          this.bleDevices = next;
        }
      });
      setTimeout(() => {
        BleProvisioner.stopScan();
        this.bleScanning = false;
        if (this.bleDevices.length === 0) {
          this.bleStatusText = '未发现设备，请确认 ESP32 已通电';
        } else {
          this.bleStatusText = '请选择要配置的设备';
        }
      }, 8000);
    } catch (err) {
      BleProvisioner.stopScan();
      this.bleScanning = false;
      this.bleStatusText = `${err}`;
    }
  }

  async connectBle(device: BleDeviceInfo): Promise<void> {
    BleProvisioner.stopScan();
    this.bleScanning = false;
    this.bleConnecting = true;
    this.connectedBleId = '';
    this.connectedBleName = device.name;
    this.bleStatusText = `正在连接 ${device.name}...`;
    try {
      await BleProvisioner.connect(device.deviceId, (status: string) => {
        this.updateBleStatus(status);
      });
      this.connectedBleId = device.deviceId;
      this.bleStatusText = '蓝牙已连接，请填写 WiFi 信息';
    } catch (err) {
      this.bleStatusText = `${err}`;
    } finally {
      this.bleConnecting = false;
    }
  }

  async provisionWifi(): Promise<void> {
    this.bleConnecting = true;
    try {
      await BleProvisioner.provision(this.wifiSsid, this.wifiPassword);
      this.bleStatusText = '凭证已发送，正在等待 ESP32 联网...';
    } catch (err) {
      this.bleStatusText = `${err}`;
    } finally {
      this.bleConnecting = false;
    }
  }

  async testBuzzer(): Promise<void> {
    this.bleConnecting = true;
    try {
      await BleProvisioner.sendBuzzer('short', 250);
      this.bleStatusText = '蜂鸣器测试指令已发送';
    } catch (err) {
      this.bleStatusText = `${err}`;
    } finally {
      this.bleConnecting = false;
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
          Row() {
            Text('设备联网')
              .fontSize(15)
              .fontWeight(FontWeight.Medium)
              .fontColor('#1B2430')
            Blank()
            Text(this.bleScanning ? '扫描中' : '蓝牙配网')
              .fontSize(10)
              .fontColor('#0B6E5A')
              .backgroundColor('#C9F0E5')
              .borderRadius(8)
              .padding({ left: 7, right: 7, top: 3, bottom: 3 })
          }
          .width('100%')

          Text(this.bleStatusText)
            .fontSize(11)
            .fontColor('#5F6B7A')
            .width('100%')

          Button(this.bleScanning ? '扫描中...' : '扫描附近设备')
            .width('100%')
            .height(38)
            .backgroundColor('#E8EEF5')
            .fontColor('#35506A')
            .fontSize(12)
            .enabled(!this.bleScanning && !this.bleConnecting)
            .onClick(() => {
              this.scanBleDevices();
            })

          if (this.bleDevices.length > 0) {
            Column({ space: 6 }) {
              ForEach(this.bleDevices, (device: BleDeviceInfo) => {
                Row({ space: 8 }) {
                  Column({ space: 2 }) {
                    Text(device.name)
                      .fontSize(13)
                      .fontWeight(FontWeight.Medium)
                      .fontColor('#1B2430')
                    Text(`${device.deviceId}  ${device.rssi} dBm`)
                      .fontSize(10)
                      .fontColor('#8A94A6')
                  }
                  .layoutWeight(1)
                  .alignItems(HorizontalAlign.Start)

                  Button(this.connectedBleId === device.deviceId ? '已连接' : '连接')
                    .height(30)
                    .fontSize(11)
                    .backgroundColor(
                      this.connectedBleId === device.deviceId ? '#C9F0E5' : '#0F2D45'
                    )
                    .fontColor(
                      this.connectedBleId === device.deviceId ? '#0B6E5A' : '#FFFFFF'
                    )
                    .enabled(!this.bleConnecting &&
                      this.connectedBleId !== device.deviceId)
                    .onClick(() => {
                      this.connectBle(device);
                    })
                }
                .padding(10)
                .backgroundColor('#F5F7FA')
                .borderRadius(10)
                .width('100%')
              }, (device: BleDeviceInfo) => device.deviceId)
            }
            .width('100%')
          }

          if (this.connectedBleId.length > 0) {
            Button(this.bleConnecting ? '正在发送...' : '测试蜂鸣器')
              .width('100%')
              .height(36)
              .backgroundColor('#E8F8F2')
              .fontColor('#0B6E5A')
              .fontSize(12)
              .enabled(!this.bleConnecting)
              .onClick(() => {
                this.testBuzzer();
              })
            TextInput({ text: this.wifiSsid, placeholder: 'WiFi 名称（仅支持 2.4GHz）' })
              .height(40)
              .backgroundColor('#F5F7FA')
              .borderRadius(10)
              .onChange((value: string) => {
                this.wifiSsid = value;
              })
            TextInput({ text: this.wifiPassword, placeholder: 'WiFi 密码' })
              .type(InputType.Password)
              .height(40)
              .backgroundColor('#F5F7FA')
              .borderRadius(10)
              .onChange((value: string) => {
                this.wifiPassword = value;
              })
            Button(this.bleConnecting ? '正在下发...' : '连接 WiFi')
              .width('100%')
              .height(40)
              .backgroundColor('#0F2D45')
              .fontColor('#FFFFFF')
              .fontSize(13)
              .enabled(!this.bleConnecting && this.wifiSsid.trim().length > 0)
              .onClick(() => {
                this.provisionWifi();
              })
          }
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

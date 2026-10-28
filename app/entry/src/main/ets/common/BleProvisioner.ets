import { ble, constant } from '@kit.ConnectivityKit';
import { util } from '@kit.ArkTS';
import { AppConfig } from './AppConfig';

export interface BleDeviceInfo {
  deviceId: string;
  name: string;
  rssi: number;
}

interface WifiProvisionRequest {
  ssid: string;
  password: string;
  device_id: string;
  upload_token: string;
}

interface BuzzerRequest {
  command: string;
  pattern: string;
  duration_ms: number;
}

export class BleProvisioner {
  private static readonly SERVICE_UUID: string = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
  private static readonly RX_UUID: string = '6e400002-b5a3-f393-e0a9-e50e24dcca9e';
  private static readonly STATUS_UUID: string = '6e400003-b5a3-f393-e0a9-e50e24dcca9e';

  private static client: ble.GattClientDevice | null = null;
  private static rxCharacteristic: ble.BLECharacteristic | null = null;
  private static statusCharacteristic: ble.BLECharacteristic | null = null;
  private static scanning: boolean = false;

  static startScan(onFound: (device: BleDeviceInfo) => void): void {
    BleProvisioner.stopScan();
    BleProvisioner.scanning = true;
    ble.on('BLEDeviceFind', (results: Array<ble.ScanResult>) => {
      for (let i = 0; i < results.length; i++) {
        const result = results[i];
        if (result.deviceName.startsWith('EyeCare-')) {
          const device: BleDeviceInfo = {
            deviceId: result.deviceId,
            name: result.deviceName,
            rssi: result.rssi
          };
          onFound(device);
        }
      }
    });
    const filters: Array<ble.ScanFilter> = [{
      serviceUuid: BleProvisioner.SERVICE_UUID
    }];
    try {
      ble.startBLEScan(filters);
    } catch (err) {
      ble.off('BLEDeviceFind');
      BleProvisioner.scanning = false;
      throw err as Error;
    }
  }

  static stopScan(): void {
    if (!BleProvisioner.scanning) {
      return;
    }
    try {
      ble.stopBLEScan();
    } catch (err) {
    }
    ble.off('BLEDeviceFind');
    BleProvisioner.scanning = false;
  }

  static async connect(deviceId: string, onStatus: (status: string) => void): Promise<void> {
    BleProvisioner.close();
    const client = ble.createGattClientDevice(deviceId);
    BleProvisioner.client = client;

    client.on('BLECharacteristicChange', (characteristic: ble.BLECharacteristic) => {
      if (characteristic.characteristicUuid.toLowerCase() !== BleProvisioner.STATUS_UUID) {
        return;
      }
      const decoder = util.TextDecoder.create('utf-8');
      const text = decoder.decodeToString(new Uint8Array(characteristic.characteristicValue));
      if (text.length > 0) {
        onStatus(text);
      }
    });

    await new Promise<void>((resolve: () => void, reject: (reason: Error) => void) => {
      let settled: boolean = false;
      const timer = setTimeout(() => {
        if (!settled) {
          settled = true;
          reject(new Error('连接超时，请确认 ESP32 已通电并在附近'));
        }
      }, 15000);

      client.on('BLEConnectionStateChange', (state: ble.BLEConnectionChangeState) => {
        if (state.state === constant.ProfileConnectionState.STATE_CONNECTED && !settled) {
          try {
            client.setBLEMtuSize(512);
          } catch (err) {
          }
          BleProvisioner.discover(client, onStatus)
            .then(() => {
              if (!settled) {
                settled = true;
                clearTimeout(timer);
                resolve();
              }
            })
            .catch((err: Error) => {
              if (!settled) {
                settled = true;
                clearTimeout(timer);
                reject(err);
              }
            });
        } else if (state.state === constant.ProfileConnectionState.STATE_DISCONNECTED && !settled) {
          settled = true;
          clearTimeout(timer);
          reject(new Error('蓝牙连接已断开'));
        }
      });

      client.connect();
    });
  }

  static async provision(ssid: string, password: string): Promise<void> {
    if (BleProvisioner.client === null || BleProvisioner.rxCharacteristic === null) {
      throw new Error('请先连接 EyeCare 设备');
    }
    if (ssid.trim().length === 0) {
      throw new Error('请输入 WiFi 名称');
    }

    const request: WifiProvisionRequest = {
      ssid: ssid.trim(),
      password: password,
      device_id: AppConfig.deviceId,
      upload_token: AppConfig.uploadToken
    };
    const encoder = util.TextEncoder.create('utf-8');
    const payload = encoder.encodeInto(JSON.stringify(request));
    const value = new ArrayBuffer(payload.byteLength);
    new Uint8Array(value).set(payload);
    BleProvisioner.rxCharacteristic.characteristicValue = value;
    await BleProvisioner.client.writeCharacteristicValue(
      BleProvisioner.rxCharacteristic,
      ble.GattWriteType.WRITE
    );
  }

  static async sendBuzzer(pattern: string, durationMs: number): Promise<void> {
    if (BleProvisioner.client === null || BleProvisioner.rxCharacteristic === null) {
      throw new Error('请先连接 EyeCare 设备');
    }
    const request: BuzzerRequest = {
      command: 'buzz',
      pattern: pattern,
      duration_ms: durationMs
    };
    const payload = util.TextEncoder.create('utf-8').encodeInto(JSON.stringify(request));
    const value = new ArrayBuffer(payload.byteLength);
    new Uint8Array(value).set(payload);
    BleProvisioner.rxCharacteristic.characteristicValue = value;
    await BleProvisioner.client.writeCharacteristicValue(
      BleProvisioner.rxCharacteristic,
      ble.GattWriteType.WRITE
    );
  }

  static close(): void {
    const client = BleProvisioner.client;
    BleProvisioner.client = null;
    BleProvisioner.rxCharacteristic = null;
    BleProvisioner.statusCharacteristic = null;
    if (client !== null) {
      try {
        client.disconnect();
        client.close();
      } catch (err) {
      }
    }
  }

  private static async discover(
    client: ble.GattClientDevice,
    onStatus: (status: string) => void
  ): Promise<void> {
    const services = await client.getServices();
    for (let i = 0; i < services.length; i++) {
      const service = services[i];
      if (service.serviceUuid.toLowerCase() !== BleProvisioner.SERVICE_UUID) {
        continue;
      }
      for (let j = 0; j < service.characteristics.length; j++) {
        const characteristic = service.characteristics[j];
        const uuid = characteristic.characteristicUuid.toLowerCase();
        if (uuid === BleProvisioner.RX_UUID) {
          BleProvisioner.rxCharacteristic = characteristic;
        } else if (uuid === BleProvisioner.STATUS_UUID) {
          BleProvisioner.statusCharacteristic = characteristic;
        }
      }
    }

    if (BleProvisioner.rxCharacteristic === null ||
      BleProvisioner.statusCharacteristic === null) {
      throw new Error('未找到 EyeCare 配网服务');
    }
    await client.setCharacteristicChangeNotification(
      BleProvisioner.statusCharacteristic,
      true
    );
    onStatus('{"state":"connected","detail":"ble_ready"}');
  }
}

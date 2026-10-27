import { ApiClient } from '../common/ApiClient';
import { AppConfig } from '../common/AppConfig';
import { Telemetry } from '../common/Models';

@Component
struct SummaryStatCard {
  @Prop label: string = '';
  @Prop value: string = '0';
  @Prop unit: string = '';
  @Prop color: string = '#1EC8A5';

  build() {
    Column({ space: 4 }) {
      Row({ space: 5 }) {
        Text('●')
          .fontSize(8)
          .fontColor(this.color)
        Text(this.label)
          .fontSize(11)
          .fontColor('#8A94A6')
      }
      Row({ space: 3 }) {
        Text(this.value)
          .fontSize(21)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
        Text(this.unit)
          .fontSize(10)
          .fontColor('#A7B0BE')
          .margin({ top: 6 })
      }
    }
    .layoutWeight(1)
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(16)
    .alignItems(HorizontalAlign.Start)
  }
}

@Component
export struct HistoryPage {
  @State items: Telemetry[] = [];
  @State error: string = '';
  @State loading: boolean = false;
  @State avgLuxValue: number = 0;
  @State maxLuxValue: number = 0;
  @State lowRatioValue: number = 0;
  private timer: number = -1;

  aboutToAppear(): void {
    this.load();
    if (this.timer !== -1) {
      clearInterval(this.timer);
    }
    this.timer = setInterval(() => {
      this.load();
    }, AppConfig.refreshMs * 2);
  }

  aboutToDisappear(): void {
    if (this.timer !== -1) {
      clearInterval(this.timer);
      this.timer = -1;
    }
  }

  async load(): Promise<void> {
    if (this.loading) {
      return;
    }
    this.loading = true;
    try {
      const data = await ApiClient.getHistory();
      const historyItems = data.items;
      this.items = historyItems;
      this.updateSummary(historyItems);
      this.error = '';
    } catch (err) {
      this.items = [];
      this.avgLuxValue = 0;
      this.maxLuxValue = 0;
      this.lowRatioValue = 0;
      this.error = `后端连接失败：${err}`;
    } finally {
      this.loading = false;
    }
  }

  private updateSummary(items: Telemetry[]): void {
    let sum = 0;
    let count = 0;
    let max = 0;
    let low = 0;
    for (let i = 0; i < items.length; i++) {
      const lux = items[i].lux;
      if (lux !== undefined && lux !== null) {
        sum += lux;
        count++;
        max = Math.max(max, lux);
        if (lux < 150) {
          low++;
        }
      }
    }
    this.avgLuxValue = count > 0 ? Math.round(sum / count) : 0;
    this.maxLuxValue = max;
    this.lowRatioValue = count > 0 ? Math.round(low / count * 100) : 0;
  }

  private barHeight(lux?: number): number {
    return Math.max(5, Math.min(96, (lux ?? 0) / 10));
  }

  private barColor(lux?: number): string {
    if (lux === undefined) {
      return '#D9DDE3';
    }
    if (lux < 150) {
      return '#F5B942';
    }
    if (lux > 1000) {
      return '#E85D5D';
    }
    return '#1EC8A5';
  }

  private formatLocalTime(value: string): string {
    let normalized = value;
    if (
      normalized.length > 0 &&
      !normalized.endsWith('Z') &&
      normalized.indexOf('+') < 0
    ) {
      normalized += 'Z';
    }
    const date = new Date(normalized);
    const hours = date.getHours();
    const minutes = date.getMinutes();
    const hh = hours < 10 ? `0${hours}` : `${hours}`;
    const mm = minutes < 10 ? `0${minutes}` : `${minutes}`;
    return `${hh}:${mm}`;
  }

  @Builder
  statBlock(label: string, value: string, unit: string, color: string) {
    Column({ space: 4 }) {
      Row({ space: 5 }) {
        Text('●')
          .fontSize(8)
          .fontColor(color)
        Text(label)
          .fontSize(11)
          .fontColor('#8A94A6')
      }
      Row({ space: 3 }) {
        Text(value)
          .fontSize(21)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
        Text(unit)
          .fontSize(10)
          .fontColor('#A7B0BE')
          .margin({ top: 6 })
      }
    }
    .layoutWeight(1)
    .padding(14)
    .backgroundColor('#FFFFFF')
    .borderRadius(16)
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  legendDot(color: string, label: string) {
    Row({ space: 4 }) {
      Text('●')
        .fontSize(8)
        .fontColor(color)
      Text(label)
        .fontSize(10)
        .fontColor('#8A94A6')
    }
  }

  build() {
    Scroll() {
      Column({ space: 14 }) {
        Row({ space: 8 }) {
          Text('光照历史')
            .fontSize(20)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1B2430')
          Blank()
          Button(this.loading ? '读取中' : '刷新')
            .fontSize(12)
            .height(32)
            .backgroundColor('#E8EEF5')
            .fontColor('#35506A')
            .onClick(() => {
              this.load();
            })
        }
        .width('100%')

        if (this.error.length > 0) {
          Text(this.error)
            .fontSize(11)
            .fontColor('#E85D5D')
            .width('100%')
        }

        Row({ space: 10 }) {
          SummaryStatCard({
            label: '平均照度',
            value: `${this.avgLuxValue}`,
            unit: 'lux',
            color: '#1EC8A5'
          })
          SummaryStatCard({
            label: '峰值照度',
            value: `${this.maxLuxValue}`,
            unit: 'lux',
            color: '#5A8DEE'
          })
          SummaryStatCard({
            label: '偏低占比',
            value: `${this.lowRatioValue}`,
            unit: '%',
            color: '#F5B942'
          })
        }
        .width('100%')

        Column({ space: 12 }) {
          Row() {
            Column({ space: 3 }) {
              Text('最近 24 小时光照曲线')
                .fontSize(16)
                .fontWeight(FontWeight.Bold)
                .fontColor('#1B2430')
              Text('颜色越暖，代表当前采样点越需要关注')
                .fontSize(10)
                .fontColor('#8A94A6')
            }
            .alignItems(HorizontalAlign.Start)
            Blank()
            Row({ space: 8 }) {
              this.legendDot('#1EC8A5', '舒适')
              this.legendDot('#F5B942', '偏暗')
              this.legendDot('#E85D5D', '过亮')
            }
          }
          .width('100%')

          Row({ space: 2 }) {
            ForEach(this.items.slice(-30), (item: Telemetry) => {
              Column() {
              }
              .width(8)
              .height(this.barHeight(item.lux))
              .backgroundColor(this.barColor(item.lux))
              .borderRadius(3)
            }, (item: Telemetry) => item.id.toString())
          }
          .height(108)
          .width('100%')
          .alignItems(VerticalAlign.Bottom)
          .padding({ left: 4, right: 4 })
        }
        .padding(16)
        .backgroundColor('#FFFFFF')
        .borderRadius(20)
        .width('100%')

        Column({ space: 7 }) {
          Row() {
            Text('AI 趋势提示')
              .fontSize(15)
              .fontWeight(FontWeight.Bold)
              .fontColor('#0B4F43')
            Blank()
            Text('PREVIEW')
              .fontSize(9)
              .fontColor('#0B6E5A')
              .backgroundColor('#C9F0E5')
              .borderRadius(8)
              .padding({ left: 7, right: 7, top: 3, bottom: 3 })
          }
          .width('100%')
          Text('午后照度下降明显，建议在 14:00 前调亮台灯；下午久坐峰值较长，可以把提醒提前到 45 分钟。')
            .fontSize(12)
            .fontColor('#24594F')
            .lineHeight(20)
        }
        .padding(16)
        .backgroundColor('#E8F8F2')
        .borderRadius(18)
        .width('100%')
        .alignItems(HorizontalAlign.Start)

        List({ space: 7 }) {
          ForEach(this.items.slice().reverse(), (item: Telemetry) => {
            ListItem() {
              Row() {
                Column({ space: 3 }) {
                  Text(this.formatLocalTime(item.ts))
                    .fontSize(13)
                    .fontWeight(FontWeight.Medium)
                    .fontColor('#1B2430')
                  Text(item.light_state ?? '--')
                    .fontSize(10)
                    .fontColor(item.light_state === 'dark' ? '#B77900' : '#8A94A6')
                }
                .width(58)
                .alignItems(HorizontalAlign.Start)

                Text(`${item.lux ?? '--'} lux`)
                  .fontSize(13)
                  .fontWeight(FontWeight.Medium)
                  .fontColor('#1B2430')
                  .layoutWeight(1)

                Text(`${item.temperature ?? '--'}°C / ${item.humidity ?? '--'}%`)
                  .fontSize(11)
                  .fontColor('#8A94A6')
              }
              .width('100%')
              .padding({ left: 12, right: 12, top: 10, bottom: 10 })
              .backgroundColor('#FFFFFF')
              .borderRadius(12)
            }
          }, (item: Telemetry) => item.id.toString())
        }
        .width('100%')
      }
      .padding(16)
      .width('100%')
    }
    .width('100%')
    .height('100%')
  }
}

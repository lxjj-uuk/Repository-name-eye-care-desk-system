import { ApiClient } from '../common/ApiClient';
import { AppConfig } from '../common/AppConfig';
import { DonutChart } from '../common/DonutChart';
import { ChartSegment, Telemetry } from '../common/Models';

@Component
struct MetricCard {
  @Prop label: string = '';
  @Prop value: string = '';
  @Prop unit: string = '';
  @Prop color: string = '#5A8DEE';

  build() {
    Column({ space: 5 }) {
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
          .fontSize(22)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
        Text(this.unit)
          .fontSize(10)
          .fontColor('#A7B0BE')
          .margin({ top: 7 })
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
export struct DashboardPage {
  @State hasTelemetry: boolean = false;
  @State hasLux: boolean = false;
  @State lux: number = 0;
  @State hasTemperature: boolean = false;
  @State temperature: number = 0;
  @State hasHumidity: boolean = false;
  @State humidity: number = 0;
  @State occupied: boolean = false;
  @State sitCont: number = 0;
  @State sitTotal: number = 0;
  @State risk: number = 0;
  @State riskLevel: string = 'low';
  @State lightState: string = '--';
  @State hasLastMotion: boolean = false;
  @State lastMotion: number = 0;
  @State segments: ChartSegment[] = [];
  @State error: string = '';
  @State loading: boolean = false;
  @State lastUpdated: string = '';
  @State refreshCount: number = 0;
  @State dataTimestamp: string = '';
  private timer: number = -1;
  private requestSeq: number = 0;

  aboutToAppear(): void {
    this.refresh();
    if (this.timer !== -1) {
      clearInterval(this.timer);
    }
    this.timer = setInterval(() => {
      this.refresh();
    }, AppConfig.refreshMs);
  }

  aboutToDisappear(): void {
    if (this.timer !== -1) {
      clearInterval(this.timer);
      this.timer = -1;
    }
  }

  async refresh(): Promise<void> {
    const seq = ++this.requestSeq;
    this.refreshCount += 1;
    this.loading = true;
    try {
      const latest = await ApiClient.getLatest();
      const history = await ApiClient.getHistory();
      if (seq !== this.requestSeq) {
        return;
      }

      if (latest.telemetry) {
        this.hasTelemetry = true;
        this.hasLux = latest.telemetry.lux !== undefined;
        this.lux = latest.telemetry.lux ?? 0;
        this.hasTemperature = latest.telemetry.temperature !== undefined;
        this.temperature = latest.telemetry.temperature ?? 0;
        this.hasHumidity = latest.telemetry.humidity !== undefined;
        this.humidity = latest.telemetry.humidity ?? 0;
        this.occupied = latest.telemetry.occupied ?? false;
        this.sitCont = latest.telemetry.sit_cont_min ?? 0;
        this.sitTotal = latest.telemetry.sit_total_min ?? 0;
        this.risk = latest.telemetry.risk ?? 0;
        this.riskLevel = latest.telemetry.risk_level ?? 'low';
        this.lightState = latest.telemetry.light_state ?? '--';
        this.hasLastMotion = latest.telemetry.last_motion_min !== undefined;
        this.lastMotion = latest.telemetry.last_motion_min ?? 0;
        this.dataTimestamp = latest.telemetry.ts;
      } else {
        this.hasTelemetry = false;
        this.dataTimestamp = '';
      }

      this.segments = this.buildSegments(history.items);
      this.lastUpdated = new Date().toTimeString().substring(0, 8);
      this.error = '';
    } catch (err) {
      if (seq !== this.requestSeq) {
        return;
      }
      this.hasTelemetry = false;
      this.segments = this.buildSegments([]);
      this.dataTimestamp = '';
      this.error = `后端连接失败（${ApiClient.getBaseUrl()}）：请确认 FastAPI 已启动`;
    } finally {
      if (seq === this.requestSeq) {
        this.loading = false;
      }
    }
  }

  private buildSegments(items: Telemetry[]): ChartSegment[] {
    let comfortable = 0;
    let low = 0;
    let high = 0;
    let away = 0;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      const itemLux = item.lux ?? 0;
      if (!item.occupied) {
        away++;
      } else if (itemLux < 150) {
        low++;
      } else if (itemLux > 1000) {
        high++;
      } else {
        comfortable++;
      }
    }
    if (comfortable + low + high + away === 0) {
      return [{ label: '暂无', value: 1, color: '#D9DDE3' }];
    }
    return [
      { label: '舒适', value: comfortable, color: '#1EC8A5' },
      { label: '偏暗', value: low, color: '#F5B942' },
      { label: '过亮', value: high, color: '#E85D5D' },
      { label: '离开', value: away, color: '#A7B4C4' }
    ];
  }

  private riskColor(level: string): string {
    if (level === 'high') {
      return '#E85D5D';
    }
    if (level === 'medium') {
      return '#F5B942';
    }
    return '#1EC8A5';
  }

  private riskLabel(level: string): string {
    if (level === 'high') {
      return '偏高';
    }
    if (level === 'medium') {
      return '中等';
    }
    return '良好';
  }

  private percent(segment: ChartSegment): string {
    let total = 0;
    for (let i = 0; i < this.segments.length; i++) {
      total += this.segments[i].value;
    }
    if (total === 0) {
      return '0%';
    }
    return `${Math.round(segment.value / total * 100)}%`;
  }

  @Builder
  legendRow(segment: ChartSegment) {
    Row({ space: 7 }) {
      Text('●')
        .fontSize(9)
        .fontColor(segment.color)
      Text(segment.label)
        .fontSize(12)
        .fontColor('#5F6B7A')
        .width(34)
      Text(this.percent(segment))
        .fontSize(12)
        .fontWeight(FontWeight.Medium)
        .fontColor('#1B2430')
    }
    .width('100%')
  }

  @Builder
  heroCard() {
    Column({ space: 14 }) {
      Row() {
        Stack() {
          Progress({
            value: this.risk * 100,
            total: 100,
            type: ProgressType.Ring
          })
            .width(104)
            .height(104)
            .color(this.riskColor(this.riskLevel))
            .backgroundColor('#29455B')
            .style({ strokeWidth: 9 })
          Column({ space: 1 }) {
            Text(`${(this.risk * 100).toFixed(0)}`)
              .fontSize(28)
              .fontWeight(FontWeight.Bold)
              .fontColor('#FFFFFF')
            Text('风险分')
              .fontSize(10)
              .fontColor('#AEBECD')
          }
        }
        .width(104)
        .height(104)

        Column({ space: 7 }) {
          Row({ space: 6 }) {
            Text('用眼负担')
              .fontSize(13)
              .fontColor('#AEBECD')
            Text(this.riskLabel(this.riskLevel))
              .fontSize(11)
              .fontColor(this.riskColor(this.riskLevel))
              .backgroundColor('#1D3A50')
              .borderRadius(8)
              .padding({ left: 8, right: 8, top: 3, bottom: 3 })
          }
          Text('今天的光照与久坐组合处于可控区间')
            .fontSize(15)
            .fontWeight(FontWeight.Medium)
            .fontColor('#FFFFFF')
            .lineHeight(22)
          Text(`当前照度 ${this.hasLux ? this.lux : '--'} lux · 连续久坐 ${this.sitCont} 分钟`)
            .fontSize(11)
            .fontColor('#9FB2C4')
        }
        .layoutWeight(1)
        .margin({ left: 16 })
        .alignItems(HorizontalAlign.Start)
      }
      .width('100%')

      Row({ space: 18 }) {
        Column({ space: 2 }) {
          Text('AI 建议')
            .fontSize(10)
            .fontColor('#7FD9C8')
          Text('先调亮台灯，再安排一次远眺')
            .fontSize(13)
            .fontColor('#FFFFFF')
        }
        .alignItems(HorizontalAlign.Start)
        Blank()
        Text('查看报告 →')
          .fontSize(11)
          .fontColor('#7FD9C8')
      }
      .width('100%')
      .padding({ top: 10 })
      .border({ width: { top: 1 }, color: '#24445B' })
    }
    .padding(18)
    .backgroundColor('#102B40')
    .borderRadius(22)
    .width('100%')
    .linearGradient({
      angle: 135,
      colors: [['#102B40', 0.0], ['#173F55', 1.0]]
    })
  }

  @Builder
  distributionCard() {
    Column({ space: 12 }) {
      Row() {
        Column({ space: 3 }) {
          Text('今日光照分布')
            .fontSize(17)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1B2430')
          Text('按采样点统计，帮助识别用眼环境风险')
            .fontSize(11)
            .fontColor('#8A94A6')
        }
        .alignItems(HorizontalAlign.Start)
        Blank()
        Text('AI')
          .fontSize(9)
          .fontColor('#0B6E5A')
          .backgroundColor('#DDF6EF')
          .borderRadius(8)
          .padding({ left: 7, right: 7, top: 3, bottom: 3 })
      }
      .width('100%')

      Row({ space: 14 }) {
        DonutChart({ segments: this.segments, chartSize: 142 })
        Column({ space: 9 }) {
          ForEach(this.segments, (segment: ChartSegment) => {
            this.legendRow(segment)
          }, (segment: ChartSegment) => segment.label)
        }
        .layoutWeight(1)
      }
      .width('100%')
    }
    .padding(16)
    .backgroundColor('#FFFFFF')
    .borderRadius(20)
    .width('100%')
  }

  @Builder
  aiCard() {
    Column({ space: 9 }) {
      Row() {
        Text('AI 洞察')
          .fontSize(16)
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
      Text('午后光照偏低，建议提前开灯；连续久坐 72 分钟，建议起身活动 5 分钟。')
        .fontSize(13)
        .fontColor('#24594F')
        .lineHeight(21)
      Text('接入大模型后，这里会显示基于当日数据的个性化分析。')
        .fontSize(11)
        .fontColor('#5E8A80')
    }
    .padding(16)
    .backgroundColor('#E8F8F2')
    .borderRadius(20)
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  build() {
    Scroll() {
      Column({ space: 14 }) {
        Row({ space: 8 }) {
          Text('实时状态')
            .fontSize(20)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1B2430')
          Text(AppConfig.useMockData ? '演示数据' : '实时数据')
            .fontSize(10)
            .fontColor(AppConfig.useMockData ? '#8A5A00' : '#0B6E5A')
            .backgroundColor(AppConfig.useMockData ? '#FFF1D6' : '#DDF6EF')
            .borderRadius(8)
            .padding({ left: 7, right: 7, top: 3, bottom: 3 })
          Blank()
          Button(this.loading ? '同步中' : '刷新')
            .fontSize(12)
            .height(32)
            .backgroundColor('#E8EEF5')
            .fontColor('#35506A')
            .onClick(() => {
              this.refresh();
            })
        }
        .width('100%')

        Text(this.lastUpdated.length > 0
          ? `上次更新 ${this.lastUpdated}`
          : '尚未更新')
          .fontSize(10)
          .fontColor('#8A94A6')
          .width('100%')

        Text(`刷新 #${this.refreshCount} · 数据时间 ${this.dataTimestamp.length > 0 ? this.dataTimestamp : '--'}`)
          .fontSize(10)
          .fontColor('#8A94A6')
          .width('100%')

        if (this.error.length > 0) {
          Text(this.error)
            .fontSize(11)
            .fontColor('#E85D5D')
            .width('100%')
        }

        if (this.hasTelemetry) {
          this.heroCard()
        } else {
          Text('正在读取设备数据...')
            .fontSize(13)
            .fontColor('#8A94A6')
            .padding(24)
        }

        this.distributionCard()

        if (this.hasTelemetry) {
          Row({ space: 10 }) {
            MetricCard({
              label: '照度',
              value: `${this.hasLux ? this.lux : '--'}`,
              unit: 'lux',
              color: '#F5B942'
            })
            MetricCard({
              label: '温度',
              value: `${this.hasTemperature ? this.temperature.toFixed(1) : '--'}`,
              unit: '°C',
              color: '#E85D5D'
            })
            MetricCard({
              label: '湿度',
              value: `${this.hasHumidity ? this.humidity.toFixed(1) : '--'}`,
              unit: '%',
              color: '#5A8DEE'
            })
          }
          .width('100%')

          Row({ space: 10 }) {
            MetricCard({
              label: '连续久坐',
              value: `${this.sitCont}`,
              unit: 'min',
              color: '#9B6BDF'
            })
            MetricCard({
              label: '今日累计',
              value: `${this.sitTotal}`,
              unit: 'min',
              color: '#1EC8A5'
            })
            MetricCard({
              label: '工位状态',
              value: this.occupied ? '有人' : '无人',
              unit: '',
              color: '#5A8DEE'
            })
          }
          .width('100%')

          Row() {
            Text(`光照状态：${this.lightState}`)
              .fontSize(12)
              .fontColor('#5F6B7A')
            Blank()
            Text(this.hasLastMotion
              ? `上次活动：${this.lastMotion} 分钟前`
              : '上次活动：--')
              .fontSize(11)
              .fontColor('#8A94A6')
          }
          .width('100%')
          .padding(14)
          .backgroundColor('#FFFFFF')
          .borderRadius(14)
        }

        this.aiCard()
      }
      .padding(16)
      .width('100%')
    }
    .width('100%')
    .height('100%')
  }
}

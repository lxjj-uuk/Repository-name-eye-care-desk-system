import { ChartSegment } from './Models';

@Component
export struct DonutChart {
  @Prop @Watch('onSegmentsChanged') segments: ChartSegment[] = [];
  @Prop chartSize: number = 150;
  private settings: RenderingContextSettings = new RenderingContextSettings(true);
  private context: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);

  onSegmentsChanged(): void {
    setTimeout(() => {
      this.draw();
    }, 0);
  }

  private draw(): void {
    const center = this.chartSize / 2;
    const radius = center - 14;
    this.context.clearRect(0, 0, this.chartSize, this.chartSize);
    this.context.lineWidth = 18;
    let total = 0;
    for (let i = 0; i < this.segments.length; i++) {
      total += this.segments[i].value;
    }
    if (total <= 0) {
      this.context.beginPath();
      this.context.arc(center, center, radius, 0, Math.PI * 2);
      this.context.strokeStyle = '#E3E8EF';
      this.context.stroke();
      return;
    }
    let start = -Math.PI / 2;
    for (let i = 0; i < this.segments.length; i++) {
      const segment = this.segments[i];
      const angle = segment.value / total * Math.PI * 2;
      if (angle < 0.04) {
        continue;
      }
      this.context.beginPath();
      this.context.arc(center, center, radius, start, start + angle - 0.03);
      this.context.strokeStyle = segment.color;
      this.context.stroke();
      start += angle;
    }
  }

  build() {
    Stack() {
      Canvas(this.context)
        .width(this.chartSize)
        .height(this.chartSize)
        .onReady(() => {
          this.draw();
        })
      Column({ space: 2 }) {
        Text('光照')
          .fontSize(11)
          .fontColor('#8A8F98')
        Text('分布')
          .fontSize(18)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
      }
    }
    .width(this.chartSize)
    .height(this.chartSize)
  }
}

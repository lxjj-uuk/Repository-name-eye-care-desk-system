import { ApiClient } from '../common/ApiClient';
import { AppConfig } from '../common/AppConfig';
import {
  AiEvidence,
  AiInsight,
  CommandInfo,
  DailyReport,
  KnowledgeSource,
  ProposedAction,
  ReportData
} from '../common/Models';

@Component
export struct ReportPage {
  @Prop @Watch('onRefreshTokenChange') refreshToken: number = 0;
  @State reportDate: string = '';
  @State report: DailyReport | null = null;
  @State error: string = '';
  @State loading: boolean = false;
  @State message: string = '';
  @State pending: CommandInfo[] = [];
  @State reportRevision: number = 0;
  @State feedbackSent: string = '';
  @State feedbackMessage: string = '';

  aboutToAppear(): void {
    this.reportDate = this.today();
    this.load();
  }

  private onRefreshTokenChange(): void {
    this.load(false);
  }

  private today(): string {
    const now = new Date();
    const month = `${now.getMonth() + 1}`.padStart(2, '0');
    const day = `${now.getDate()}`.padStart(2, '0');
    return `${now.getFullYear()}-${month}-${day}`;
  }

  async load(generateIfMissing: boolean = true): Promise<void> {
    if (this.loading) {
      return;
    }
    this.loading = true;
    this.message = '正在读取今日数据...';
    try {
      let loadedReport = await ApiClient.getDailyReport(this.reportDate);
      if (
        generateIfMissing &&
        (
          !loadedReport.data.insights ||
          loadedReport.data.insights.length === 0
        )
      ) {
        this.message = '首次分析需要加载本地模型，请稍候...';
        loadedReport = await ApiClient.generateAiReport(this.reportDate);
      }
      this.report = loadedReport;
      this.reportRevision += 1;
      this.feedbackSent = '';
      this.feedbackMessage = '';
      this.error = '';
      this.message = loadedReport.data.source === 'llm'
        ? `分析已更新：${this.sourceLabel(loadedReport.data.source, loadedReport.data.model, loadedReport.data.engine)}`
        : '今日数据已载入；点击“AI 深度分析”生成新报告';
    } catch (err) {
      this.report = null;
      this.error = this.errorText(err);
    } finally {
      this.loading = false;
      await this.loadPending();
    }
  }

  async analyze(): Promise<void> {
    if (this.loading) {
      return;
    }
    this.loading = true;
    this.error = '';
    this.message = '正在连接本地大模型并分析今日数据，首次加载可能需要约 1 分钟...';
    try {
      const analyzedReport = await ApiClient.generateAiReport(this.reportDate);
      this.report = analyzedReport;
      this.reportRevision += 1;
      this.feedbackSent = '';
      this.feedbackMessage = '';
      this.error = '';
      if (AppConfig.useMockData) {
        this.message = '演示模式：AI 报告已生成';
      } else if (analyzedReport.data.source === 'llm') {
        this.message = `深度分析完成：${this.sourceLabel(analyzedReport.data.source, analyzedReport.data.model, analyzedReport.data.engine)}`;
      } else {
        this.message = '已使用规则+风险模型完成分析';
      }
      await this.loadPending();
    } catch (err) {
      this.error = this.errorText(err);
    } finally {
      this.loading = false;
    }
  }

  async refreshReport(): Promise<void> {
    if (this.loading) {
      return;
    }
    this.loading = true;
    this.error = '';
    this.message = '正在重新聚合今日传感器数据...';
    try {
      const refreshedReport = await ApiClient.refreshDailyReport(this.reportDate);
      this.report = refreshedReport;
      this.reportRevision += 1;
      this.error = '';
      this.message = '统计数据已刷新；点击“AI 深度分析”生成最新结论';
    } catch (err) {
      this.error = this.errorText(err);
    } finally {
      this.loading = false;
      await this.loadPending();
    }
  }

  async loadPending(): Promise<void> {
    try {
      this.pending = await ApiClient.getPendingCommands();
    } catch (err) {
      this.pending = [];
    }
  }

  async confirmPending(id: number): Promise<void> {
    try {
      await ApiClient.confirmCommand(id);
      this.message = '指令已确认执行';
      await this.loadPending();
    } catch (err) {
      this.error = this.errorText(err);
    }
  }

  async sendFeedback(type: string): Promise<void> {
    if (!this.report || this.feedbackSent.length > 0) {
      return;
    }
    let commandId = 0;
    const actions = this.report.data.proposed_actions ?? [];
    if (actions.length > 0 && actions[0].command_id) {
      commandId = actions[0].command_id;
    }
    try {
      await ApiClient.sendFeedback(this.report.id, commandId, type);
      this.feedbackSent = type;
      this.feedbackMessage = '反馈已记录，下次分析会参考你的偏好';
    } catch (err) {
      this.feedbackMessage = this.errorText(err);
    }
  }

  private errorText(err: Object): string {
    const error = err as Error;
    if (error && error.message && error.message.length > 0) {
      return error.message;
    }
    return '操作失败，请稍后重试';
  }

  private riskColor(level?: string): string {
    if (level === 'high') {
      return '#E85D5D';
    }
    if (level === 'medium') {
      return '#F5B942';
    }
    return '#1EC8A5';
  }

  private riskLabel(level?: string): string {
    if (level === 'high') {
      return '偏高';
    }
    if (level === 'medium') {
      return '中等';
    }
    return '良好';
  }

  private sourceLabel(source?: string, model?: string, engine?: string): string {
    if (source === 'llm') {
      const prefix = engine === 'local'
        ? '本地大模型'
        : engine === 'api'
          ? '云端大模型'
          : '大模型';
      return model && model.length > 0 ? `${prefix} ${model}` : prefix;
    }
    return '规则+风险模型';
  }

  private generatedAt(value?: string): string {
    if (!value || value.length < 16) {
      return '--';
    }
    const parsed = new Date(value.endsWith('Z') ? value : `${value}Z`);
    if (Number.isNaN(parsed.getTime())) {
      return value.substring(0, 16).replace('T', ' ');
    }
    const month = `${parsed.getMonth() + 1}`.padStart(2, '0');
    const day = `${parsed.getDate()}`.padStart(2, '0');
    const hour = `${parsed.getHours()}`.padStart(2, '0');
    const minute = `${parsed.getMinutes()}`.padStart(2, '0');
    return `${parsed.getFullYear()}-${month}-${day} ${hour}:${minute}`;
  }

  @Builder
  insightCard(insight: AiInsight) {
    Row({ space: 10 }) {
      Text('●')
        .fontSize(10)
        .fontColor(insight.level === 'high'
          ? '#E85D5D'
          : insight.level === 'warn'
            ? '#F5B942'
            : '#1EC8A5')
        .margin({ top: 4 })
      Column({ space: 4 }) {
        Text(insight.title)
          .fontSize(13)
          .fontWeight(FontWeight.Medium)
          .fontColor('#1B2430')
        Text(insight.detail)
          .fontSize(11)
          .fontColor('#6C7787')
          .lineHeight(18)
      }
      .layoutWeight(1)
      .alignItems(HorizontalAlign.Start)
    }
    .width('100%')
    .padding({ top: 8, bottom: 8 })
  }

  @Builder
  recommendationChip(text: string) {
    Text(text)
      .fontSize(11)
      .fontColor('#0B6E5A')
      .backgroundColor('#DDF6EF')
      .borderRadius(14)
      .padding({ left: 10, right: 10, top: 6, bottom: 6 })
  }

  @Builder
  evidenceCard(item: AiEvidence) {
    Row({ space: 9 }) {
      Text('✓')
        .fontSize(11)
        .fontColor('#2749E8')
      Column({ space: 3 }) {
        Text(item.fact)
          .fontSize(11)
          .fontColor('#53625C')
          .lineHeight(18)
        if (item.knowledge_ids && item.knowledge_ids.length > 0) {
          Text(item.knowledge_ids.map((id: string) => `[${id}]`).join(' '))
            .fontSize(9)
            .fontColor('#2749E8')
        }
      }
      .layoutWeight(1)
      .alignItems(HorizontalAlign.Start)
    }
    .width('100%')
    .padding(12)
    .backgroundColor('#EEF1EB')
    .borderRadius(14)
  }

  @Builder
  knowledgeCard(item: KnowledgeSource) {
    Column({ space: 4 }) {
      Text(`[${item.id}] ${item.title}`)
        .fontSize(12)
        .fontWeight(FontWeight.Bold)
        .fontColor('#1B2430')
      Text(item.source)
        .fontSize(9)
        .fontColor('#7B8982')
      Text(item.excerpt)
        .fontSize(10)
        .fontColor('#53625C')
        .lineHeight(16)
    }
    .width('100%')
    .padding(13)
    .backgroundColor('#FFF4E1')
    .borderRadius(14)
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  proposedActionCard(action: ProposedAction) {
    Column({ space: 8 }) {
      Text('需要你确认')
        .fontSize(9)
        .fontColor('#D9FF57')
      Text(action.label)
        .fontSize(20)
        .fontWeight(FontWeight.Bold)
        .fontColor('#FFFFFF')
      Text(action.reason)
        .fontSize(10)
        .fontColor('#B9C9C1')
        .lineHeight(16)
      if (action.command_id && action.command_id > 0) {
        Button('确认执行')
          .width('100%')
          .height(42)
          .fontSize(11)
          .fontWeight(FontWeight.Bold)
          .fontColor('#142820')
          .backgroundColor('#D9FF57')
          .borderRadius(12)
          .onClick(() => {
            this.confirmPending(action.command_id as number);
          })
      }
    }
    .width('100%')
    .padding(16)
    .backgroundColor('#142820')
    .borderRadius(18)
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  statBlock(label: string, value: string) {
    Column({ space: 4 }) {
      Text(label)
        .fontSize(10)
        .fontColor('#8A94A6')
      Text(value)
        .fontSize(17)
        .fontWeight(FontWeight.Bold)
        .fontColor('#1B2430')
    }
    .layoutWeight(1)
    .padding(12)
    .backgroundColor('#FFFFFF')
    .borderRadius(14)
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  reportBody(report: DailyReport, data: ReportData) {
    Column({ space: 10 }) {
      Row() {
        Column({ space: 4 }) {
          Text('今日用眼负担')
            .fontSize(12)
            .fontColor('#AEBECD')
          Text(this.riskLabel(report.risk_level ?? data.risk_level))
            .fontSize(26)
            .fontWeight(FontWeight.Bold)
            .fontColor(this.riskColor(report.risk_level ?? data.risk_level))
        }
        .alignItems(HorizontalAlign.Start)
        Blank()
        Column({ space: 2 }) {
          Text(`${data.sample_count ?? '--'}`)
            .fontSize(22)
            .fontWeight(FontWeight.Bold)
            .fontColor('#FFFFFF')
          Text('采样点')
            .fontSize(10)
            .fontColor('#AEBECD')
        }
        .alignItems(HorizontalAlign.End)
      }
      .width('100%')

      Text(report.summary ?? '暂无摘要')
        .fontSize(12)
        .fontColor('#D4E0EA')
        .lineHeight(20)
    }
    .padding(18)
    .backgroundColor('#102B40')
    .borderRadius(22)
    .width('100%')
    .linearGradient({
      angle: 135,
      colors: [['#102B40', 0.0], ['#173F55', 1.0]]
    })

    Row({ space: 10 }) {
      this.statBlock('平均照度', `${data.avg_lux ?? '--'} lux`)
      this.statBlock('最长久坐', `${data.max_sit_cont_min ?? '--'} min`)
      this.statBlock('偏低占比', data.poor_light_ratio === undefined
        ? '--'
        : `${Math.round(data.poor_light_ratio * 100)}%`)
    }
    .width('100%')

    if (data.evidence && data.evidence.length > 0) {
      Column({ space: 8 }) {
        Text('判断依据')
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
          .width('100%')
        ForEach(data.evidence, (item: AiEvidence) => {
          this.evidenceCard(item)
        }, (item: AiEvidence) => item.fact)
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

    if (data.knowledge_sources && data.knowledge_sources.length > 0) {
      Column({ space: 8 }) {
        Text('知识来源')
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
          .width('100%')
        ForEach(data.knowledge_sources, (item: KnowledgeSource) => {
          this.knowledgeCard(item)
        }, (item: KnowledgeSource) => item.id)
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

    Column({ space: 6 }) {
      Row() {
        Text('AI 原因分析')
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
        Blank()
        Text(this.sourceLabel(data.source, data.model, data.engine))
          .fontSize(9)
          .fontColor('#0B6E5A')
          .backgroundColor('#DDF6EF')
          .borderRadius(8)
          .padding({ left: 7, right: 7, top: 3, bottom: 3 })
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
      }
      .width('100%')

      Text(`生成时间：${this.generatedAt(data.generated_at)}`)
        .fontSize(9)
        .fontColor('#8A94A6')

      if (data.insights && data.insights.length > 0) {
        ForEach(data.insights, (insight: AiInsight) => {
          this.insightCard(insight)
        }, (insight: AiInsight) => insight.title)
      } else {
        Text('暂无 AI 分析结果')
          .fontSize(12)
          .fontColor('#8A94A6')
      }
    }
    .padding(16)
    .backgroundColor('#FFFFFF')
    .borderRadius(18)
    .width('100%')
    .alignItems(HorizontalAlign.Start)

    if (data.recommendations && data.recommendations.length > 0) {
      Column({ space: 8 }) {
        Text('行动建议')
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
          .width('100%')
        Column({ space: 8 }) {
          ForEach(data.recommendations, (item: string) => {
            this.recommendationChip(item)
          }, (item: string) => item)
        }
        .width('100%')
      }
      .padding(16)
      .backgroundColor('#F8FBFD')
      .borderRadius(18)
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

    if (data.proposed_actions && data.proposed_actions.length > 0) {
      Column({ space: 8 }) {
        Text('AI 提议')
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor('#1B2430')
          .width('100%')
        ForEach(data.proposed_actions, (action: ProposedAction) => {
          this.proposedActionCard(action)
        }, (action: ProposedAction) => action.tool)
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
    }

    Column({ space: 8 }) {
      Text('这次建议有帮助吗？')
        .fontSize(14)
        .fontWeight(FontWeight.Bold)
        .fontColor('#1B2430')
        .width('100%')
      Row({ space: 8 }) {
        Button(this.feedbackSent === 'handled' ? '已记录' : '已处理')
          .layoutWeight(1)
          .height(36)
          .fontSize(10)
          .fontColor(this.feedbackSent === 'handled' ? '#2749E8' : '#53625C')
          .backgroundColor(this.feedbackSent === 'handled' ? '#E9EBFF' : '#EEF1EB')
          .borderRadius(18)
          .enabled(this.feedbackSent.length === 0)
          .onClick(() => {
            this.sendFeedback('handled');
          })
        Button(this.feedbackSent === 'later' ? '已记录' : '稍后提醒')
          .layoutWeight(1)
          .height(36)
          .fontSize(10)
          .fontColor(this.feedbackSent === 'later' ? '#2749E8' : '#53625C')
          .backgroundColor(this.feedbackSent === 'later' ? '#E9EBFF' : '#EEF1EB')
          .borderRadius(18)
          .enabled(this.feedbackSent.length === 0)
          .onClick(() => {
            this.sendFeedback('later');
          })
        Button(this.feedbackSent === 'not_helpful' ? '已记录' : '没帮助')
          .layoutWeight(1)
          .height(36)
          .fontSize(10)
          .fontColor(this.feedbackSent === 'not_helpful' ? '#2749E8' : '#53625C')
          .backgroundColor(this.feedbackSent === 'not_helpful' ? '#E9EBFF' : '#EEF1EB')
          .borderRadius(18)
          .enabled(this.feedbackSent.length === 0)
          .onClick(() => {
            this.sendFeedback('not_helpful');
          })
      }
      .width('100%')
      if (this.feedbackMessage.length > 0) {
        Text(this.feedbackMessage)
          .fontSize(9)
          .fontColor('#7B8982')
      }
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  @Builder
  pendingCard() {
    Column({ space: 8 }) {
      Row() {
        Text('待确认指令')
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor('#7A4B00')
        Blank()
        Button('刷新')
          .fontSize(10)
          .height(28)
          .backgroundColor('#F4D79A')
          .fontColor('#6B4200')
          .onClick(() => {
            this.loadPending();
          })
      }
      .width('100%')

      if (this.pending.length > 0) {
        ForEach(this.pending, (command: CommandInfo) => {
          Row({ space: 8 }) {
            Column({ space: 3 }) {
              Text(command.command_name)
                .fontSize(13)
                .fontWeight(FontWeight.Medium)
                .fontColor('#4A3300')
              Text(`状态：${command.status}`)
                .fontSize(10)
                .fontColor('#8A6A2A')
            }
            .layoutWeight(1)
            .alignItems(HorizontalAlign.Start)

            Button('确认执行')
              .fontSize(11)
              .height(30)
              .backgroundColor('#7A4B00')
              .fontColor('#FFFFFF')
              .onClick(() => {
                this.confirmPending(command.id);
              })
          }
          .width('100%')
          .padding(10)
          .backgroundColor('#FFFDF7')
          .borderRadius(12)
        }, (command: CommandInfo) => command.id.toString())
      } else {
        Text('暂无待确认指令。MCP 生成蜂鸣或阈值命令后会出现在这里。')
          .fontSize(10)
          .fontColor('#8A6A2A')
          .lineHeight(16)
      }
    }
    .padding(16)
    .backgroundColor('#FFF4D8')
    .borderRadius(18)
    .width('100%')
    .alignItems(HorizontalAlign.Start)
  }

  build() {
    Scroll() {
      Column({ space: 14 }) {
        Row({ space: 8 }) {
          Text('每日用眼报告')
            .fontSize(20)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1B2430')
          Blank()
          Text('AI')
            .fontSize(9)
            .fontColor('#0B6E5A')
            .backgroundColor('#DDF6EF')
            .borderRadius(8)
            .padding({ left: 7, right: 7, top: 3, bottom: 3 })
        }
        .width('100%')

        Row({ space: 8 }) {
          TextInput({ text: this.reportDate, placeholder: 'YYYY-MM-DD' })
            .layoutWeight(1)
            .height(40)
            .backgroundColor('#FFFFFF')
            .borderRadius(10)
            .onChange((value: string) => {
              this.reportDate = value;
            })
          Button(this.loading ? '分析中' : 'AI 深度分析')
            .fontSize(12)
            .height(40)
            .backgroundColor('#0F2D45')
            .fontColor('#FFFFFF')
            .enabled(!this.loading)
            .onClick(() => {
              this.analyze();
            })
        }
        .width('100%')

        Row({ space: 8 }) {
          Button(this.loading ? '刷新中' : '刷新报告')
            .fontSize(12)
            .height(34)
            .backgroundColor('#E8EEF5')
            .fontColor('#35506A')
            .enabled(!this.loading)
            .onClick(() => {
              this.refreshReport();
            })
          Blank()
          if (this.message.length > 0) {
            Text(this.message)
              .fontSize(10)
              .fontColor('#8A94A6')
          }
        }
        .width('100%')

        if (this.error.length > 0) {
          Text(this.error)
            .fontSize(11)
            .fontColor('#E85D5D')
            .width('100%')
        }

        if (this.loading) {
          Row({ space: 10 }) {
            LoadingProgress()
              .width(16)
              .height(16)
              .color('#1EC8A5')
            Text(this.message)
              .fontSize(11)
              .fontColor('#35506A')
              .lineHeight(18)
              .layoutWeight(1)
          }
          .width('100%')
          .padding(12)
          .backgroundColor('#EAF7F4')
          .borderRadius(12)
        }

        if (this.report && this.report.data) {
          ForEach([this.reportRevision], (revision: number) => {
            if (this.report && this.report.data) {
              this.reportBody(this.report, this.report.data)
            }
          }, (revision: number) => revision.toString())
        } else if (!this.loading) {
          Text('当天没有数据，或后端未启动')
            .fontSize(13)
            .fontColor('#8A94A6')
            .padding(24)
        }

        this.pendingCard()

      }
      .padding(16)
      .width('100%')
    }
    .width('100%')
    .height('100%')
  }
}

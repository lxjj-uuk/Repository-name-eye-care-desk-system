import { DashboardPage } from './Dashboard';
import { HistoryPage } from './History';
import { SettingsPage } from './Settings';
import { ReportPage } from './Report';
import common from '@ohos.app.ability.common';
import { SettingsStore } from '../common/SettingsStore';

@Entry
@Component
struct Home {
  @State currentTab: number = 0;

  aboutToAppear(): void {
    const context = getContext(this) as common.UIAbilityContext;
    SettingsStore.init(context);
    SettingsStore.load();
  }

  build() {
    Column() {
      Column({ space: 6 }) {
        Row() {
          Text('EYE CARE DESK')
            .fontSize(10)
            .fontColor('#7FD9C8')
            .letterSpacing(2)
          Blank()
          Text('AI READY')
            .fontSize(9)
            .fontColor('#0B1F3A')
            .backgroundColor('#7FD9C8')
            .borderRadius(8)
            .padding({ left: 8, right: 8, top: 3, bottom: 3 })
        }
        .width('100%')

        Text('工位用眼健康')
          .fontSize(26)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')

        Row({ space: 6 }) {
          Text('●')
            .fontSize(9)
            .fontColor('#1EC8A5')
          Text('设备在线 · 数据每 5 秒刷新')
            .fontSize(11)
            .fontColor('#B7C6D6')
        }
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 18, bottom: 20 })
      .linearGradient({
        angle: 135,
        colors: [['#081B2E', 0.0], ['#164A63', 1.0]]
      })
      .borderRadius({ bottomLeft: 26, bottomRight: 26 })

      Tabs({ barPosition: BarPosition.End, index: this.currentTab }) {
        TabContent() {
          DashboardPage()
        }.tabBar('实时')

        TabContent() {
          HistoryPage()
        }.tabBar('历史')

        TabContent() {
          SettingsPage()
        }.tabBar('设置')

        TabContent() {
          ReportPage()
        }.tabBar('报告')
      }
      .onChange((index: number) => {
        this.currentTab = index;
      })
      .barHeight(58)
      .layoutWeight(1)
    }
    .width('100%')
    .height('100%')
    .backgroundColor('#F3F6F9')
  }
}

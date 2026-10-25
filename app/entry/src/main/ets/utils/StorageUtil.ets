import preferences from '@ohos.data.preferences';
import common from '@ohos.app.ability.common';

// 单条历史记录结构
export interface GameRecord {
  id: number
  difficulty: string  // 难度
  score: number       // 得分
  time: string        // 游玩时间
}

// 模块级变量（替代 static 成员，消除 this）
const STORE_NAME: string = "GuessNumberRecord"
let uiContext: common.UIAbilityContext | null = null

// 本地存储工具类
export class StorageUtil {
  // 初始化上下文
  static initContext(ctx: common.UIAbilityContext): void {
    uiContext = ctx
  }

  // 保存历史记录列表
  static async saveRecordList(list: GameRecord[]): Promise<void> {
    if (!uiContext) return
    try {
      const prefs = await preferences.getPreferences(uiContext, STORE_NAME)
      await prefs.putSync("recordList", JSON.stringify(list))
      await prefs.flush()
    } catch (err) {
      console.error("保存记录失败：", JSON.stringify(err))
    }
  }

  // 读取历史记录列表
  static async getRecordList(): Promise<GameRecord[]> {
    if (!uiContext) return []
    try {
      const prefs = await preferences.getPreferences(uiContext, STORE_NAME)
      const str = prefs.getSync("recordList", "[]") as string
      return JSON.parse(str) as GameRecord[]
    } catch (err) {
      console.error("读取记录失败：", JSON.stringify(err))
      return []
    }
  }

  // 清空所有历史记录
  static async clearRecord(): Promise<void> {
    if (!uiContext) return
    try {
      const prefs = await preferences.getPreferences(uiContext, STORE_NAME)
      await prefs.deleteSync("recordList")
      await prefs.flush()
    } catch (err) {
      console.error("清空记录失败：", JSON.stringify(err))
    }
  }
}
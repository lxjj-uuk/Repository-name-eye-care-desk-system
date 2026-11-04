---
id: sensor-confidence
title: 工位传感器数据可信度说明
source: Eye Care Desk 项目 BH1750、DHT20、LD2410B 联调与验收记录
url: https://github.com/lxjj-uuk/Repository-name-eye-care-desk-system
tags: 传感器,可信度,覆盖,采样,LD2410B,PIR,BH1750,DHT20,离线
excerpt: 低照光占比、久坐分钟和人体存在结论只有在传感器有效覆盖足够、设备在线且时间连续时才具有较高可信度。
---

BH1750 反映模块附近照度，不代表整个房间的均匀照明；DHT20 的温湿度是局部读数；LD2410B 的 `OUT` 信号提供有人/无人状态，但安装方向、遮挡和静止状态仍会影响结果。

报告生成前应检查采样数量、各字段覆盖率、最后上传时间和是否存在长时间离线。数据不足时应降低结论强度，并明确告诉用户先检查设备，而不是编造完整趋势。

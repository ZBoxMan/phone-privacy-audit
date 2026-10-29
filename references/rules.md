# 评分口径

回答用户"凭什么这么判"时查这张表。规则 ID 与 `scripts/analyze.py` 一一对应。

## 三条前提

**单一信号不构成结论。** 不是商店装的、最近刚装的、要了敏感权限——这三件事每天都在正常软件上发生。

**分数是"值不值得看一眼"，不是"有多危险"。** 报告里不显示分数，只显示三档结论。

**每个结论都要能追到证据。** 追不到就不写。

## 计分方式

```
得分 = 最强信号 + 0.6 × 其余信号之和，再乘以来源系数
```

来源系数：Android/HarmonyOS 系统应用 0.75；商店来源且有桌面图标 0.62；有图标但来源不明 0.85；其余 1.0。iOS 从 App Store 装的 0.55，其余 1.0。

这样做的原因：线性累加会让"无图标 + 侧载 + 悬浮窗 + 开机自启 + 要了几个权限"的普通软件轻易破表，"什么都高危"的报告等于没有报告。

## 规则表

### Android / HarmonyOS

| ID | 名称 | 权重 | 触发条件 |
|---|---|---|---|
| R_ADMIN | 能拦住卸载 | 40 | 在已启用的设备管理员列表中 |
| R_BLACKLIST | 命中监控软件名 | 35 | 包名含公开报道过的监控软件标识 |
| R_A11Y | 能看到屏幕内容 | 34 | 在无障碍服务列表中 |
| R_CAMO | 隐藏 + 系统化命名 | 25 | 非系统应用、无桌面图标、包名末段含 system/service 等 |
| R_NOTIF | 能读所有通知 | 22 | 在通知使用权列表中 |
| R_BG_LOC | 后台定位 + 无图标 | 22 | 后台定位已授权且桌面无入口 |
| R_HIDDEN | 桌面无入口 | 16 | 非系统应用且无启动图标 |
| R_OVERLAY | 能弹悬浮窗 | 16 | appops SYSTEM_ALERT_WINDOW 为 allow |
| R_PERM_COMBO | 高敏感权限 ≥3 项 | 14 | 同时持有 3 项以上高危权限 |
| R_OLDSDK | 很久没更新 | 12 | targetSdk < 23 |
| R_OUTBOUND | 连非常规端口 | 12 | 远端端口不在 80/443/8080/8443/53 |
| R_SIDELOAD | 非商店来源 | 8 | 安装来源为空或不在可信商店列表 |
| R_BOOT | 开机自启 | 8 | 注册 BOOT_COMPLETED |

### iOS

数据来源是 `InstallationProxy` 返回的 Info.plist 与 Entitlements，全部只读。

| ID | 名称 | 权重 | 触发条件 |
|---|---|---|---|
| I_ENTERPRISE | 非 App Store 安装 | 40 | 无 `ITSDRMScheme`（和旧系统的 `ApplicationSINF`） |
| I_BLACKLIST | 命中监控软件名 | 38 | bundle id 含公开报道过的监控软件标识 |
| I_PERM_FLOOD | 声明 ≥12 项私密权限 | 22 | 数 `NS*UsageDescription`，只算私密类 |
| I_BG_TRACK | 后台定位 + 后台放音 | 20 | `UIBackgroundModes` 同时含 location 与 audio |
| I_PERM_WIDE | 声明 9–11 项私密权限 | 14 | 同上 |
| I_LOCAL_NET | 能扫同 WiFi 设备 | 14 | 有 `NSLocalNetworkUsageDescription` |
| I_QUERY_MANY | 探测 >60 个 App | 12 | `LSApplicationQueriesSchemes` 条目数 ≥60 |
| I_BETA | TestFlight 测试版 | 6 | `SignerIdentity` 含 TestFlight 或 `beta-reports-active` |

**iOS 判定来源的方法**（iOS 17 之后 `ApplicationSINF` 已从清单里移除，不能再靠它）：

1. `ApplicationType == System` → 系统自带
2. `SignerIdentity` 含 `TestFlight` 或 `beta-reports-active` → 测试版
3. 有 `ITSDRMScheme` → **App Store**（商店下载的包带 DRM 加密，其他渠道没有）
4. `get-task-allow` → 开发者证书
5. 其余 → 来源不明

**iOS 上不参与加分的信号**：持有 VPN / 网络扩展权限。原因是装 VPN 配置时系统必然弹窗要求授权，不是隐蔽行为。它只进"能看见你全部上网内容的软件"这个控制点，让用户自己判断要不要留。代理工具（Shadowrocket、Clash 一类）拿这个权限更是本职。

## 分档

| 分值 | 等级 | 报告里的说法 |
|---|---|---|
| ≥ 65 | high | 建议现在就看 |
| 32–64 | check | 有空看一眼 |
| 15–31 | watch | 知道一下就行 |
| < 15 | low | 不进报告 |

## 硬性过滤

来源清晰（可信商店）+ 桌面可见 + 没有驻留或隐藏特征（R_ADMIN / R_A11Y / R_CAMO / R_BG_LOC）→ **直接不进报告**。

微信有一条"不是从商店装的"或者"要了四个权限"，那不是给用户看的东西，是噪音。

iOS 上同理：App Store 来源本身已经把大部分风险挡掉了。所以那边不设硬过滤，而是用 0.55 的来源系数压住——商店软件要权限、能后台，分数也上不到"看一眼"。真正能把它推上去的只有来源不明这一条。

## 必须主动排除的高分误报

| 情况 | 为什么不算问题 |
|---|---|
| `com.google.android.gms` 有设备管理员 | 查找我的设备，关掉会失去定位找手机的能力 |
| 小米/华为/OPPO/vivo/三星的云服务同理 | 同上 |
| 输入法有无障碍 | 语音输入需要，已单独打 0.4 折 |
| 微信/QQ 有悬浮窗 | 消息气泡 |
| 智能手表 App 有通知使用权 | 同步通知用的 |
| 输入法/主题/小组件无桌面图标 | 本来就没有 |
| 企业内网应用、车机配套为非商店来源 | 官方直装渠道 |

**遇到这些要在报告里主动说明**，否则用户会去关掉，然后发现手机找不到、手表收不到消息。

## 报告里不允许出现的表述

| 不许说 | 原因 |
|---|---|
| 安全指数 100 分 / 手机已彻底安全 | 无法测量 |
| 已清除 X 个病毒 | 没有引擎比对，不存在"病毒"判定 |
| 释放了 X GB / 省电 X% / 广告减少 X% | 未测量 |
| 你的手机正在被监控 | 单一信号推不出这个结论 |
| 建议全部卸载 | 用户会丢掉自己要用的东西 |
| 关注度 66 分 | 普通人不理解分数，只理解"要不要管" |

## 数据来源标注

每个结论都要能追到具体来源：`dumpsys package` 的哪个字段、`settings get secure` 的哪一项、`/proc/net/tcp` 的哪条连接、iOS 的哪一页设置。做不到就不写这条结论。

"""词表：包名 → 人话、可信来源、敏感权限、伪装词等。

所有平台共用的静态表都放这里，规则代码里不再内嵌表格。
"""


SYSTEM_PATH_MARKERS = (
    "/system/", "/system_ext/", "/product/", "/vendor/", "/odm/",
    "/apex/", "/vendor_dlkm/", "/my_product/", "/my_heytap/",
    "/my_stock/", "/preinstall/", "/preinstalled/", "/cust/",
)


TRUSTED_INSTALLERS = {
    "com.android.vending": "Google Play",
    "com.google.android.packageinstaller": "Google 安装器",
    "com.android.packageinstaller": "系统安装器",
    "com.miui.packageinstaller": "小米安装器",
    "com.huawei.appmarket": "华为应用市场",
    "com.hihonor.appmarket": "荣耀应用市场",
    "com.heytap.market": "OPPO 软件商店",
    "com.oppo.market": "OPPO 软件商店",
    "com.bbk.appstore": "vivo 应用商店",
    "com.sec.android.app.samsungapps": "三星应用商店",
    "com.oneplus.market": "一加软件商店",
    "com.coloros.packageinstaller": "OPPO 安装器",
    "com.vivo.packageinstaller": "vivo 安装器",
    "com.samsung.android.packageinstaller": "三星安装器",
    "com.huawei.android.packageinstaller": "华为安装器",
    "com.hihonor.android.packageinstaller": "荣耀安装器",
    "com.coolapk.market": "酷安",
    "com.xiaomi.market": "小米应用商店",
}


# 认得出中文名，报告才说得出人话。认不出就用"一个天气软件"这类推断。
KNOWN_APPS = {
    "com.tencent.mm": "微信", "com.tencent.mobileqq": "QQ",
    "com.tencent.tim": "TIM", "com.tencent.wework": "企业微信",
    "com.taobao.taobao": "淘宝", "com.tmall.wireless": "天猫",
    "com.eg.android.AlipayGphone": "支付宝", "com.jingdong.app.mall": "京东",
    "com.xunmeng.pinduoduo": "拼多多", "com.achievo.vipshop": "唯品会",
    "com.ss.android.ugc.aweme": "抖音", "com.ss.android.ugc.aweme.lite": "抖音极速版",
    "com.smile.gifmaker": "快手", "com.xingin.xhs": "小红书",
    "com.sina.weibo": "微博", "com.ss.android.article.news": "今日头条",
    "com.netease.cloudmusic": "网易云音乐", "com.tencent.qqmusic": "QQ音乐",
    "com.kugou.android": "酷狗音乐", "com.baidu.searchbox": "百度",
    "com.UCMobile": "UC浏览器", "com.tencent.mtt": "QQ浏览器",
    "com.android.chrome": "Chrome", "com.unionpay": "云闪付",
    "com.icbc": "工商银行", "com.chinamworld.main": "建设银行",
    "com.android.bankabc": "农业银行", "com.cmbchina.ccd.pluto.cmbActivity": "招商银行",
    "com.autonavi.minimap": "高德地图", "com.baidu.BaiduMap": "百度地图",
    "com.dianping.v1": "大众点评", "me.ele": "饿了么",
    "com.sankuai.meituan": "美团", "com.taobao.idlefish": "闲鱼",
    "com.zhihu.android": "知乎", "com.douban.frodo": "豆瓣",
    "tv.danmaku.bili": "哔哩哔哩", "com.youku.phone": "优酷",
    "com.qiyi.video": "爱奇艺", "com.tencent.qqlive": "腾讯视频",
    "com.alibaba.android.rimet": "钉钉",
    "com.ximalaya.ting.android": "喜马拉雅",
    "com.whatsapp": "WhatsApp", "com.facebook.katana": "Facebook",
    "com.instagram.android": "Instagram", "com.twitter.android": "X",
    "com.google.android.youtube": "YouTube", "com.google.android.gm": "Gmail",
    "com.google.android.apps.maps": "Google 地图",
    "com.microsoft.office.outlook": "Outlook",
    "com.spotify.music": "Spotify", "org.telegram.messenger": "Telegram",
    "com.tencent.ig": "和平精英", "com.tencent.tmgp.sgame": "王者荣耀",
    "com.miHoYo.Yuanshen": "原神",
    "com.miui.securitycenter": "手机管家", "com.miui.home": "小米桌面",
    "com.android.settings": "设置", "com.android.vending": "应用商店",
    "com.google.android.gms": "Google 服务",
    "com.huawei.android.launcher": "华为桌面",
    "com.huawei.systemmanager": "华为手机管家",
    "com.coloros.safecenter": "OPPO 手机管家",
    "com.vivo.abe": "vivo 手机管家",
    # iOS
    "com.apple.mobilesafari": "Safari", "com.apple.mobileslideshow": "照片",
    "com.apple.MobileSMS": "信息", "com.apple.mobilephone": "电话",
    "com.apple.Preferences": "设置", "com.apple.Maps": "地图",
    "com.apple.Health": "健康", "com.apple.findmy": "查找",
    "com.apple.shortcuts": "快捷指令", "com.apple.mobilemail": "邮件",
    "com.apple.reminders": "提醒事项", "com.apple.notes": "备忘录",
    "com.apple.calculator": "计算器", "com.apple.camera": "相机",
    "com.apple.DocumentsApp": "文件", "com.apple.AppStore": "App Store",
    "com.apple.Passbook": "钱包", "com.apple.Music": "音乐",
    "com.apple.Podcasts": "播客", "com.apple.Bridge": "Watch",
    "com.apple.weather": "天气", "com.apple.stocks": "股市",
    "com.tencent.xin": "微信",
    "com.tencent.mqq": "QQ",
    "com.taobao.taobao4iphone": "淘宝",
    "com.alipay.iphoneclient": "支付宝",
    "com.xingin.discover": "小红书",
    "com.ss.iphone.ugc.aweme": "抖音",
    "com.ss.iphone.ugc.aweme.lite": "抖音极速版",
    "com.zhihu.ios": "知乎",
    "com.autonavi.amap": "高德地图",
    "com.meituan.imeituan": "美团",
    "com.dianping.dpscope": "大众点评",
    "com.taobao.fleamarket": "闲鱼",
    "com.taobao.tmall": "天猫",
    "com.tencent.QQMusic": "QQ音乐",
    "tv.danmaku.bilianime": "哔哩哔哩",
    "com.youku.YouKu": "优酷",
    "com.qiyi.iphone": "爱奇艺",
    "ph.telegra.Telegraph": "Telegram",
    "net.whatsapp.WhatsApp": "WhatsApp",
    "com.burbn.instagram": "Instagram",
    "com.atebits.Tweetie2": "X",
    "com.openai.chat": "ChatGPT",
    "com.bot.doubao": "豆包",
    "com.bytedance.flow": "豆包",
    "com.luffa.messenger": "Luffa",
    "com.liguangming.Shadowrocket": "Shadowrocket",
    "com.huania.earthquakewarning": "地震预警",
    "com.cmbchina.MPBBank": "招商银行",
}


PURPOSE_HINTS = (
    ("weather", "天气"), ("clean", "清理加速"), ("boost", "清理加速"),
    ("speed", "清理加速"), ("lock", "锁屏"), ("browser", "浏览器"),
    ("input", "输入法"), ("ime", "输入法"), ("keyboard", "输入法"),
    ("camera", "相机"), ("photo", "相册"), ("video", "视频"),
    ("music", "音乐"), ("news", "新闻资讯"), ("shop", "购物"),
    ("mall", "购物"), ("pay", "支付"), ("wallet", "钱包"),
    ("game", "游戏"), ("map", "地图"), ("health", "健康"),
    ("theme", "主题壁纸"), ("wallpaper", "主题壁纸"), ("launcher", "桌面"),
    ("file", "文件管理"), ("calendar", "日历"), ("clock", "时钟"),
    ("alarm", "闹钟"), ("radio", "收音机"), ("flashlight", "手电筒"),
    ("live", "直播"), ("reading", "阅读"), ("book", "阅读"),
    ("widget", "小组件"),
)


VENDOR_COMPONENTS = {
    "com.miui.msa.global": "小米系统广告服务",
    "com.miui.systemadolution": "小米系统广告组件",
    "com.miui.systemadsolution": "小米系统广告组件",
    "com.miui.analytics": "小米统计服务",
    "com.miui.miuibbs": "小米社区",
    "com.miui.hybrid": "小米快应用引擎",
    "com.miui.hybrid.accessory": "小米快应用支撑",
    "com.miui.mipicks": "小米应用推荐",
    "com.xiaomi.market": "小米应用商店",
    "com.huawei.hwid": "华为账号服务",
    "com.huawei.android.hwouc": "华为系统更新",
    "com.huawei.intelligent": "华为负一屏",
    "com.hihonor.intelligent": "荣耀负一屏",
    "com.coloros.assistantscreen": "OPPO 负一屏",
    "com.heytap.browser": "OPPO 浏览器",
    "com.vivo.assistant": "vivo 负一屏",
    "com.bbk.launcher2": "vivo 桌面",
    "com.huawei.hms.core": "华为移动服务",
}


SENSITIVE_PERMS = {
    "android.permission.ACCESS_FINE_LOCATION": ("位置", "high"),
    "android.permission.ACCESS_COARSE_LOCATION": ("大致位置", "mid"),
    "android.permission.ACCESS_BACKGROUND_LOCATION": ("后台位置", "high"),
    "android.permission.RECORD_AUDIO": ("麦克风", "high"),
    "android.permission.CAMERA": ("相机", "high"),
    "android.permission.READ_SMS": ("短信", "high"),
    "android.permission.RECEIVE_SMS": ("短信", "high"),
    "android.permission.READ_CONTACTS": ("通讯录", "high"),
    "android.permission.READ_CALL_LOG": ("通话记录", "high"),
    "android.permission.CALL_PHONE": ("打电话", "mid"),
    "android.permission.READ_PHONE_STATE": ("手机信息", "mid"),
    "android.permission.READ_PHONE_NUMBERS": ("本机号码", "mid"),
    "android.permission.PROCESS_OUTGOING_CALLS": ("监听拨出电话", "high"),
    "android.permission.SEND_SMS": ("发短信", "high"),
    "android.permission.WRITE_SMS": ("改短信", "high"),
}


WATCHED_OPS = {
    "SYSTEM_ALERT_WINDOW": ("弹窗", "high"),
    "ACCESS_FINE_LOCATION": ("位置", "high"),
    "RECORD_AUDIO": ("麦克风", "high"),
    "CAMERA": ("相机", "high"),
    "READ_SMS": ("短信", "high"),
    "READ_CONTACTS": ("通讯录", "high"),
    "READ_CALL_LOG": ("通话记录", "high"),
    "POST_NOTIFICATION": ("通知", "mid"),
    "RUN_IN_BACKGROUND": ("后台运行", "mid"),
    "START_FOREGROUND": ("常驻后台", "mid"),
    "BOOT_COMPLETED": ("开机自启", "mid"),
    "ACTIVATE_VPN": ("VPN", "high"),
    "GET_USAGE_STATS": ("使用记录", "mid"),
}


CAMOUFLAGE_WORDS = (
    "system", "service", "services", "update", "updater", "security",
    "protect", "protection", "settings", "framework", "core",
    "provider", "manager", "guard", "safe", "engine",
)


STALKERWARE_HINTS = (
    "mspy", "flexispy", "hellospy", "spyhuman", "spyzie", "cerberus",
    "thetruthspy", "hoverwatch", "kidguard", "xnspy", "minspy", "cocospy",
    "spyic", "mobiletrack", "phonesheriff", "snoopza", "trackmyfone",
)


FIND_MY_DEVICE = (
    "com.google.android.gms", "com.miui.cloudservice", "com.huawei.hwid",
    "com.coloros.findmyphone", "com.vivo.findphone", "com.samsung.android.fmm",
    "com.hihonor.findmydevice", "com.huawei.findmydevice",
)


IME_HINTS = ("inputmethod", ".ime", "keyboard", "sogou.input", "baidu.input",
             "iflytek", "ime.")


SRC_LABEL = {
    "prop_brand": "设备品牌", "prop_model": "设备型号", "prop_manufacturer": "厂商",
    "prop_release": "系统版本", "prop_sdk": "系统 API", "prop_security_patch": "安全补丁",
    "prop_fingerprint": "系统指纹", "prop_serial": "设备序列号", "users": "用户列表",
    "packages_all": "应用清单", "packages_third": "第三方应用清单",
    "packages_system": "系统应用清单", "packages_disabled": "已停用应用",
    "launcher_entries": "桌面入口", "boot_receivers": "开机自启",
    "default_home": "默认桌面", "default_input": "默认输入法", "admins_apps": "管理员组件",
    "package_dump": "应用详情", "device_policy": "设备管理员",
    "accessibility": "无障碍服务", "notif_listeners": "通知使用权",
    "appops_dump": "权限操作记录", "deviceidle": "电池优化白名单",
    "power_whitelist": "省电白名单", "net_tcp": "TCP 连接", "net_tcp6": "IPv6 TCP 连接",
    "net_udp": "UDP 连接", "net_udp6": "IPv6 UDP 连接", "proxy": "代理设置",
    "bundles": "应用清单", "running": "运行中的应用",
}


LEVEL_LABEL = {
    "high": "先处理这个",
    "check": "有空看一眼",
    "watch": "知道就行",
    "low": "没发现异常",
}


IOS_SYSTEM_PREFIX = "com.apple."


# 代理 / 加速工具，拿 VPN 权限是本职，不算信号
PROXY_HINTS = ("shadowrocket", "clash", "surge", "quantumult", "loon",
               "stash", "sing-box", "v2ray", "surfboard", "kitsunebi",
               "outline", "wireguard", "tailscale", "expressvpn", "nordvpn")


def nice_app_name(pkg: str) -> str:
    """把包名翻译成人能看懂的名字。识别不出就返回包名本身。

    名字里带系统词汇的软件不做用途推断：猜出来的"系统服务"
    正好就是它伪装的身份，那等于替它洗白。这种时候直接给包名——
    包名本身就是证据，用户拿着它才能在设置里搜到这个东西。
    """
    if pkg in KNOWN_APPS:
        return KNOWN_APPS[pkg]
    low = pkg.lower()
    tail = low.rsplit(".", 1)[-1]
    if any(w in tail for w in CAMOUFLAGE_WORDS):
        return pkg
    for word, label in PURPOSE_HINTS:
        if word in low:
            return f"一个{label}软件"
    return pkg


def is_proxy_tool(bid: str) -> bool:
    low = bid.lower()
    return any(h in low for h in PROXY_HINTS)


# ---------------------------------------------------------------- iOS

MODEL_NAMES = {
    "iPhone14,2": "iPhone 13 Pro", "iPhone14,3": "iPhone 13 Pro Max",
    "iPhone14,4": "iPhone 13 mini", "iPhone14,5": "iPhone 13",
    "iPhone14,6": "iPhone SE (第 3 代)", "iPhone14,7": "iPhone 14",
    "iPhone14,8": "iPhone 14 Plus", "iPhone15,2": "iPhone 14 Pro",
    "iPhone15,3": "iPhone 14 Pro Max", "iPhone15,4": "iPhone 15",
    "iPhone15,5": "iPhone 15 Plus", "iPhone16,1": "iPhone 15 Pro",
    "iPhone16,2": "iPhone 15 Pro Max", "iPhone17,1": "iPhone 16 Pro",
    "iPhone17,2": "iPhone 16 Pro Max", "iPhone17,3": "iPhone 16",
    "iPhone17,4": "iPhone 16 Plus", "iPhone17,5": "iPhone 16e",
    "iPhone18,1": "iPhone 17 Pro", "iPhone18,2": "iPhone 17 Pro Max",
    "iPhone18,3": "iPhone 17", "iPhone18,4": "iPhone 17 Air",
    "iPhone12,1": "iPhone 11", "iPhone12,3": "iPhone 11 Pro",
    "iPhone12,5": "iPhone 11 Pro Max", "iPhone12,8": "iPhone SE (第 2 代)",
    "iPhone13,1": "iPhone 12 mini", "iPhone13,2": "iPhone 12",
    "iPhone13,3": "iPhone 12 Pro", "iPhone13,4": "iPhone 12 Pro Max",
}

# 隐私权限声明 → 大白话。键是 Info.plist 里的字段名。
PERM_MAP = {
    "NSCameraUsageDescription": "相机",
    "NSMicrophoneUsageDescription": "麦克风",
    "NSContactsUsageDescription": "通讯录",
    "NSLocationWhenInUseUsageDescription": "位置",
    "NSLocationAlwaysAndWhenInUseUsageDescription": "一直知道位置",
    "NSLocationAlwaysUsageDescription": "一直知道位置",
    "NSPhotoLibraryUsageDescription": "相册",
    "NSPhotoLibraryAddUsageDescription": "存照片",
    "NSAppleMusicUsageDescription": "音乐库",
    "NSBluetoothAlwaysUsageDescription": "蓝牙",
    "NSBluetoothPeripheralUsageDescription": "蓝牙",
    "NSHealthShareUsageDescription": "健康数据",
    "NSHealthUpdateUsageDescription": "改健康数据",
    "NSFaceIDUsageDescription": "面容 ID",
    "NSUserTrackingUsageDescription": "跨软件追踪你",
    "NSSpeechRecognitionUsageDescription": "语音识别",
    "NSCalendarsUsageDescription": "日历",
    "NSCalendarsFullAccessUsageDescription": "日历",
    "NSRemindersUsageDescription": "提醒事项",
    "NSRemindersFullAccessUsageDescription": "提醒事项",
    "NSMotionUsageDescription": "运动与健身",
    "NSLocalNetworkUsageDescription": "同 WiFi 下的其他设备",
    "NSNearbyInteractionUsageDescription": "附近的设备",
    "NSHomeKitUsageDescription": "家里的智能设备",
    "NSFocusStatusUsageDescription": "专注状态",
    "NSFamilyControlsUsageDescription": "家长控制",
    "NSVideoSubscriberAccountUsageDescription": "电视服务商账号",
    "NSGKFriendListUsageDescription": "游戏好友",
    "NSSystemAdministrationUsageDescription": "系统设置",
    "NSAppleEventsUsageDescription": "控制其他软件",
    "NSCriticalMessagingUsageDescription": "紧急消息",
}

# 后台运行能力 → 大白话
BG_MAP = {
    "audio": "后台放声音",
    "location": "后台知道位置",
    "voip": "后台接网络电话",
    "fetch": "后台自己刷新",
    "remote-notification": "收推送后台醒来",
    "processing": "后台干重活",
    "bluetooth-central": "后台连蓝牙设备",
    "bluetooth-peripheral": "自己当蓝牙设备",
    "external-accessory": "后台连外接设备",
    "network-authentication": "网络认证",
    "nearby-interaction": "附近感应",
    "push-to-talk": "对讲机",
}

# 声明了这些，才是"能打听到你私事"的权限
PRIVATE_PERMS = {
    "相机", "麦克风", "通讯录", "位置", "一直知道位置", "相册", "音乐库",
    "健康数据", "改健康数据", "跨软件追踪你", "语音识别", "日历", "提醒事项",
    "运动与健身", "同 WiFi 下的其他设备", "控制其他软件",
}

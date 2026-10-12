# -*- coding: utf-8 -*-
"""theme.py —— 小猪记账主题常量集中定义。

本模块只包含纯常量，不依赖任何其他模块，可被任意模块安全导入（避免循环依赖）。
视觉风格：可爱小猪拟物风（light 主题，浅色底 + 深色文字）。
"""

# ---------------------------------------------------------------------------
# 颜色常量（Color Palette）
# ---------------------------------------------------------------------------
BG_CREAM = "#FFF0F3"        # 奶油粉背景
PRIMARY = "#FF8FA3"         # 主色珊瑚粉
SECONDARY = "#FFD6A5"       # 辅色暖黄
ACCENT = "#FFB07C"          # 强调色蜜桃橙
TEXT = "#5C4448"            # 文字深棕灰

CARD_WHITE = "#FFFFFF"      # 卡片白
CARD_BORDER = "#FFD9E0"     # 卡片描边浅粉
CARD_SHADOW = "#F0B8C4"     # 卡片底部投影深粉

INCOME_GREEN = "#5BAE7C"    # 收入绿
EXPENSE_PINK = "#E8748C"    # 支出粉红
WARN_YELLOW = "#F0B040"     # 警示黄
DANGER_RED = "#E4572E"      # 危险红

# 辅助色（用于 hover、次级文字、分隔线等）
TEXT_MUTED = "#9B8288"      # 次级文字（灰粉）
HOVER_LIGHT = "#FFE0E7"     # 按钮 hover 浅粉
TRACK_BG = "#FFE7EC"        # 进度条 / 输入框轨道浅粉
WHITE = "#FFFFFF"
DISABLED_GRAY = "#C9B8BC"   # 禁用态

# 分类色板（长度 >= 9，用于饼图/图例）
CATEGORY_COLORS = [
    "#FF8FA3",  # 餐饮 - 珊瑚粉
    "#FFD6A5",  # 交通 - 暖黄
    "#FFB07C",  # 购物 - 蜜桃橙
    "#5BAE7C",  # 娱乐 - 绿
    "#8FB8E8",  # 居住 - 蓝
    "#C7A8E0",  # 医疗 - 紫
    "#F0B040",  # 工资 - 警示黄（收入）
    "#E8748C",  # 理财 - 粉红
    "#B0C4A8",  # 其他 - 灰绿
]

# ---------------------------------------------------------------------------
# 尺寸常量（Sizes）
# ---------------------------------------------------------------------------
RADIUS = 12                 # 圆角半径
PAD = 16                    # 卡片内边距
GAP = 12                    # 元素间距
SHADOW_OFFSET = 2           # 卡片底部投影线高度
PRESS_OFFSET = 3            # 按钮按下下移像素

# ---------------------------------------------------------------------------
# 字体常量（Fonts）—— Windows 中文使用「微软雅黑」
# ---------------------------------------------------------------------------
FONT_FAMILY = "Microsoft YaHei"


def font(size=11, bold=False):
    """返回一个 tkinter 字体元组。

    Args:
        size: 字号（像素/点，tkinter 语义）。
        bold: 是否加粗。

    Returns:
        tuple: ("Microsoft YaHei", size, "bold") 或 ("Microsoft YaHei", size)。
    """
    return (FONT_FAMILY, size, "bold") if bold else (FONT_FAMILY, size)


# 常用字号快捷字体
FONT_TITLE = font(18, True)     # 页面标题
FONT_SUBTITLE = font(13, True)  # 卡片标题
FONT_BODY = font(11, False)     # 正文
FONT_BODY_BOLD = font(11, True)
FONT_SMALL = font(9, False)     # 小字/图例
FONT_MONEY = font(20, True)     # 金额数字（放大加粗）
FONT_MONEY_MID = font(14, True)

# ---------------------------------------------------------------------------
# 业务常量（Business）
# ---------------------------------------------------------------------------
APP_TITLE = "小猪记账"

# 分类清单（与 emoji 映射）
CATEGORIES = ["餐饮", "交通", "购物", "娱乐", "居住", "医疗", "工资", "理财", "其他"]

CATEGORY_EMOJI = {
    "餐饮": "🍚",
    "交通": "🚌",
    "购物": "🛍",
    "娱乐": "🎮",
    "居住": "🏠",
    "医疗": "💊",
    "工资": "💰",
    "理财": "📈",
    "其他": "📦",
}

# 账户类型清单
ACCOUNT_TYPES = ["现金", "银行卡", "支付宝", "微信", "其他"]

# 预算总预算的占位分类名
BUDGET_TOTAL = "TOTAL"

# 收入类型关键字（用于判断哪些是收入分类的兜底，主要仍以 type 字段为准）
INCOME_CATEGORIES = {"工资", "理财"}

# 弹窗默认尺寸
DIALOG_WIDTH = 360
DIALOG_HEIGHT = 200

# 金额显示精度
MONEY_DECIMALS = 2


def fmt_money(value):
    """将数字格式化为带 ¥ 符号、两位小数的字符串。

    Args:
        value: 可为 int/float/str/None。

    Returns:
        str: 形如 "¥123.45"。非法输入返回 "¥0.00"。
    """
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = 0.0
    return "¥{:.2f}".format(num)


def fmt_money_signed(value, is_income=False):
    """带正负号的金额显示（收入 +，支出 -）。"""
    try:
        num = abs(float(value))
    except (TypeError, ValueError):
        num = 0.0
    sign = "+" if is_income else "-"
    return "{}¥{:.2f}".format(sign, num)

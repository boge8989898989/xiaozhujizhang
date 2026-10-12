# 🐷 小猪记账（Piggy Ledger）

一款可爱的 Windows 桌面记账软件，采用「小猪拟物风」温暖配色，纯 Python 标准库实现，
零第三方依赖，可一键打包为单文件 exe。

![风格](https://img.shields.io/badge/style-小猪拟物风-FF8FA3)

## ✨ 功能特性

- **记账收支**：金额 / 类型 / 分类 / 备注 / 日期 / 账户录入，数字与日期校验，明细列表增删；
  月份筛选支持 ◀ ▶ 箭头自由前后翻页（不受「有没有数据」限制）。
- **统计图表**：**可按账户筛选**（全部账户 / 单个账户）、月份切换、收入/支出/结余数字卡、
  分类占比饼图（**可点击扇形高亮**）、近 6 个月收支趋势双线折线图 —— 全部基于 tkinter Canvas 手绘。
- **预算管理**：**按账户独立设置**月度总预算 + 分类预算；横向圆角进度条内嵌**会走动的小猪头**；
  三档状态（<70% 绿 / 70~100% 黄 / >100% 红）与中文剩余或超支提示；分类预算列表可上下滚动。
- **多账户与导出**：账户 CRUD、余额自动联动（记账增删双向回滚）、
  删除账户时**级联清理其名下全部记账记录**（并提前告知条数）、
  按当前筛选范围一键导出 **UTF-8-sig** CSV（Excel 可直接打开）。

## 🎨 视觉风格

- 圆角「白瓷卡片」布局（1px 浅粉描边 + 2px 底部投影），圆角半径 12px，内边距 16px，间距 12px。
- 按钮支持**按下凹陷**效果（下移 3px、深色底边消失）与 hover 变色。
- 自绘圆角输入框、胶囊切换、可爱确认弹窗、自动消失 Toast。
- 右上角简笔小猪吉祥物，表情可切换（开心 / 平脸 / 哭）。
- 中文字体「微软雅黑」，金额数字加粗放大。

## 🗂 项目结构

```
tjbapp/
├── main.py              # 入口：创建窗口、初始化 DB、导航与页面切换
├── db.py                # 数据库层（sqlite3）：建表/CRUD/统计/余额联动/导出查询
├── ui_components.py     # 通用自绘组件：卡片/按钮/输入框/胶囊/小猪/进度条/滚动容器/弹窗/Toast/数字卡
├── theme.py             # 颜色/尺寸/字体常量集中定义
├── pages/
│   ├── __init__.py
│   ├── record.py        # 记账收支
│   ├── stats.py         # 统计图表
│   ├── budget.py        # 预算管理
│   └── accounts.py      # 多账户与导出
├── requirements.txt     # 说明：无需第三方依赖
├── .gitignore           # 忽略数据库/打包产物/缓存
└── README.md
```

数据库文件 `piggy.db` 的存放规则：

- **打包后（PyInstaller）**：与 exe 同目录，保证数据持久化；
- **源码运行**：与 `db.py` 同目录。

## 🚀 运行

需要 **Python 3.10+**（使用到 `str.removeprefix` 等标准库能力，本仓库在 3.13 验证）。

```bash
# 进入项目目录
cd tjbapp

# 直接运行（无需安装任何依赖）
python main.py
```

首次运行会自动建表并插入默认账户「现金」。

## 📦 打包为单文件 exe

```bash
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed --name 小猪记账 ^
    --hidden-import sqlite3 main.py
```

> Windows 下如使用 PowerShell，把 `^` 换成 `` ` ``；或直接写成一行。
>
> 打包产物位于 `dist/小猪记账.exe`，双击运行，`piggy.db` 会生成在 exe 同目录，
> 便于拷贝分发且数据随程序走。

## 🧩 数据库表结构

| 表 | 字段 | 说明 |
| --- | --- | --- |
| `transactions` | `id, type, amount, category, note, date, account_id` | 交易记录，`type` 为 收入/支出 |
| `accounts` | `id, name, type, balance` | 账户，`type` 为 现金/银行卡/支付宝/微信/其他 |
| `budgets` | `id, month, category, amount, account_id` | 预算，`month` 为 `YYYY-MM`，`category` 为 `TOTAL` 或分类名，`account_id = 0` 表示「全部账户」 |

索引：`transactions(date)`、`transactions(account_id)`、`budgets(month, category, account_id)`（唯一）。

> 说明：`budgets.account_id` 用 `0` 而非 `NULL` 表示全局预算 —— 因为 SQLite 的 UNIQUE 索引不约束 `NULL`，用 `NULL` 会导致同一 (月份, 分类) 重复插入。

## 🛡 异常处理

- 数据库读写失败、金额/日期格式错误、CSV 导出失败、用户取消保存 —— 均给出中文 Toast / 弹窗提示，程序不会崩溃。

## 📝 说明

- 金额以 `REAL` 存储，显示统一经 `theme.fmt_money()` 格式化为两位小数并加 `¥`。
- 全程去除 tkinter/ttk 默认灰色系统外观，控件均自绘。

## 📄 License

[MIT](LICENSE) © 2026 boge

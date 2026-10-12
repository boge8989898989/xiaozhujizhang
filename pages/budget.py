# -*- coding: utf-8 -*-
"""pages/budget.py —— 预算管理页面（支持按账户区分）。

包含：账户筛选下拉、月度总预算（横向进度条 + 内嵌走动小猪头 + 大字剩余可用）、
分类预算（逐分类进度条 + 剩余金额）、三档状态（<70% 绿 / 70~100% 黄 / >100% 红）、
页面顶部中文总结提示。全部基于 tkinter Canvas 手绘。

预算数据按 (month, category, account_id) 存储：
- 账户下拉选「全部账户」→ account_id 用 0（= 全局预算）；
- 选具体账户 → 该账户维度独立的预算，已用金额也按该账户过滤。
"""

import datetime
import tkinter as tk
from tkinter import ttk

import db
import theme
from ui_components import (
    RoundCard,
    RoundButton,
    RoundEntry,
    ProgressBar,
    PigCanvas,
    ScrollFrame,
    show_toast,
)

#: 账户下拉中「全部账户」选项的显示文案。
ALL_ACCOUNTS_LABEL = "全部账户"

#: 分类预算列表滚动视口的首选高度（px）。窗口可用空间更小时会相应收缩，
#: 保证总预算卡与分类预算卡都能放下、底部不被裁切。
CAT_SCROLL_HEIGHT = 260

#: 分类预算滚动视口的最小高度（px）。低于此值会触发按可用空间的动态收缩下限。
CAT_SCROLL_MIN_HEIGHT = 150


class BudgetPage(tk.Frame):
    """预算管理页面（按账户区分）。"""

    def __init__(self, master, app):
        """初始化页面。

        Args:
            master: 父容器。
            app: 主应用实例。
        """
        super().__init__(master, bg=theme.BG_CREAM)
        self.app = app
        today = datetime.date.today()
        self.month = "{:04d}-{:02d}".format(today.year, today.month)
        self._cat_rows = []      # [(category, row_frame, status_label)]
        self.accounts = []       # 账户列表缓存
        self._account_options = []
        self._cat_scroll_height = CAT_SCROLL_HEIGHT  # 当前滚动视口高度
        self._build()
        self.refresh()

    @property
    def _tkmaster(self):
        """返回用于弹窗/提示条的真实 tkinter 顶层窗口。"""
        root = getattr(self.app, "root", None)
        return root if root is not None else self

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build(self):
        """构建页面布局。"""
        header = tk.Frame(self, bg=theme.BG_CREAM)
        header.pack(fill="x", padx=theme.PAD, pady=(theme.GAP, 0))
        tk.Label(header, text="🎯 预算管理", bg=theme.BG_CREAM, fg=theme.TEXT,
                 font=theme.FONT_TITLE).pack(side="left")
        self.month_label = tk.Label(header, text=self.month, bg=theme.BG_CREAM,
                                    fg=theme.TEXT_MUTED, font=theme.FONT_SUBTITLE)
        self.month_label.pack(side="right")

        # 账户筛选下拉（切换后整页预算数据随之切换）
        acc_frame = tk.Frame(header, bg=theme.BG_CREAM)
        acc_frame.pack(side="right", padx=(0, 16))
        tk.Label(acc_frame, text="账户", bg=theme.BG_CREAM, fg=theme.TEXT_MUTED,
                 font=theme.FONT_BODY).pack(side="left", padx=(0, 4))
        self.account_var = tk.StringVar(value=ALL_ACCOUNTS_LABEL)
        self.account_combo = ttk.Combobox(
            acc_frame, textvariable=self.account_var,
            values=[ALL_ACCOUNTS_LABEL], width=16, state="readonly",
            font=theme.FONT_BODY)
        self.account_combo.pack(side="left")
        self.account_combo.bind("<<ComboboxSelected>>",
                                lambda e: self.refresh())

        # 顶部中文总结提示（重点强化「有什么用」）
        self.summary_label = tk.Label(
            self, text="", bg=theme.BG_CREAM, fg=theme.TEXT,
            font=theme.FONT_BODY_BOLD, anchor="w", justify="left",
            wraplength=900,
        )
        self.summary_label.pack(fill="x", padx=theme.PAD, pady=(6, 0))

        # 总预算卡片（宽度自适应父容器，高度自适应内容）
        total_card = RoundCard(self, bg=theme.BG_CREAM)
        total_card.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        body = total_card.body

        top_row = tk.Frame(body, bg=theme.CARD_WHITE)
        top_row.pack(fill="x")
        tk.Label(top_row, text="月度总预算", bg=theme.CARD_WHITE, fg=theme.TEXT,
                 font=theme.FONT_SUBTITLE).pack(side="left")
        # 设置控件
        self.total_entry = RoundEntry(top_row, width=140, height=36,
                                      bg=theme.CARD_WHITE, fill=theme.TRACK_BG)
        self.total_entry.pack(side="right")
        RoundButton(top_row, text="保存", command=self._save_total, width=80,
                    height=36, bg=theme.CARD_WHITE, fill=theme.PRIMARY,
                    hover=theme.HOVER_LIGHT).pack(side="right", padx=6)
        tk.Label(top_row, text="总预算 ¥", bg=theme.CARD_WHITE,
                 fg=theme.TEXT_MUTED, font=theme.FONT_BODY).pack(side="right")

        # 总预算进度条
        self.total_bar = ProgressBar(body, width=800, height=52, bg=theme.CARD_WHITE)
        self.total_bar.pack(fill="x", pady=(12, 6))

        # 总预算状态行（大字剩余可用 + 小猪 + 百分比文字）
        status_row = tk.Frame(body, bg=theme.CARD_WHITE)
        status_row.pack(fill="x")
        self.total_pig = PigCanvas(status_row, width=60, height=54,
                                   bg=theme.CARD_WHITE)
        self.total_pig.pack(side="left")
        # 大字「本月剩余可用 ¥xxx」
        self.total_remain = tk.Label(status_row, text="", bg=theme.CARD_WHITE,
                                     fg=theme.INCOME_GREEN, font=theme.FONT_MONEY)
        self.total_remain.pack(side="left", padx=8)
        # 次级说明（已用 xx% / 已用金额）
        self.total_status = tk.Label(status_row, text="", bg=theme.CARD_WHITE,
                                     fg=theme.TEXT_MUTED, font=theme.FONT_BODY)
        self.total_status.pack(side="left", padx=4)

        # 分类预算卡片。关键修复：分类预算列表放入固定高度可滚动容器
        # （ScrollFrame：Canvas + 内嵌 Frame + Scrollbar），否则 RoundCard
        # 高度被分类行数撑开（如 9 个分类 → 409px+），超出页面可见高度后
        # 底部行被窗口裁掉、看起来「挤在一起」。总预算卡不受影响，始终可见。
        cat_card = RoundCard(self, bg=theme.BG_CREAM)
        cat_card.pack(fill="x", padx=theme.PAD, pady=(0, theme.GAP))
        cbody = cat_card.body

        cat_top = tk.Frame(cbody, bg=theme.CARD_WHITE)
        cat_top.pack(fill="x")
        tk.Label(cat_top, text="分类预算", bg=theme.CARD_WHITE, fg=theme.TEXT,
                 font=theme.FONT_SUBTITLE).pack(side="left")
        # 滚动提示（仅在需要滚动时可见）
        self.cat_scroll_hint = tk.Label(
            cat_top, text="（可上下滚动查看全部）", bg=theme.CARD_WHITE,
            fg=theme.TEXT_MUTED, font=theme.FONT_SMALL)
        self.cat_scroll_hint.pack(side="left", padx=6)

        # 分类预算设置控件
        setter = tk.Frame(cat_top, bg=theme.CARD_WHITE)
        setter.pack(side="right")
        self.cat_var = tk.StringVar(value=theme.CATEGORIES[0])
        self.cat_combo = ttk.Combobox(setter, textvariable=self.cat_var,
                                      values=theme.CATEGORIES, width=8,
                                      state="readonly", font=theme.FONT_BODY)
        self.cat_combo.pack(side="left", padx=(0, 6))
        self.cat_entry = RoundEntry(setter, width=120, height=36,
                                    bg=theme.CARD_WHITE, fill=theme.TRACK_BG)
        self.cat_entry.pack(side="left")
        RoundButton(setter, text="保存", command=self._save_category, width=72,
                    height=36, bg=theme.CARD_WHITE, fill=theme.ACCENT,
                    hover=theme.HOVER_LIGHT).pack(side="left", padx=6)

        # 分类进度滚动容器：固定高度，内容超出时出现滚动条，可上下滑动。
        self.cat_scroll = ScrollFrame(
            cbody, bg=theme.CARD_WHITE, fixed_height=self._cat_scroll_height)
        self.cat_scroll.pack(fill="x", pady=(10, 0))
        # 兼容旧属性名（cat_list）——分类行渲染进 content。
        self.cat_list = self.cat_scroll.content
        # 滚动条的 yscrollcommand 挂钩：内容超出视口时才显示提示文字。
        self.cat_scroll.canvas.configure(
            yscrollcommand=self._on_cat_scroll)

        # 页面（本 Frame）尺寸变化时，按剩余空间动态调整滚动视口高度，
        # 保证总预算卡 + 分类预算卡整体都在可见范围内、底部不被裁切。
        self.bind("<Configure>", self._on_page_configure)

    # ------------------------------------------------------------------
    # 滚动视口尺寸 / 滚动提示
    # ------------------------------------------------------------------
    def _on_page_configure(self, event):
        """页面尺寸变化时，按剩余空间动态调整分类预算滚动视口高度。

        计算逻辑：可用高度 = 页面高度 − 头部/总预算卡等「滚动容器以上」控件
        所占高度（用 ``content`` 的窗口 y 位置推算）− 底部留白。将其夹在
        [CAT_SCROLL_MIN_HEIGHT, CAT_SCROLL_HEIGHT] 区间内，保证：
        - 页面够高时用首选高度（体验好）；
        - 页面矮时收缩视口，使分类预算卡底部不被窗口裁切。
        """
        try:
            # 防御：<Configure> 可能在 _build() 过程中（cat_scroll 尚未创建）
            # 就被触发，此时直接忽略。
            sf = getattr(self, "cat_scroll", None)
            if sf is None or not sf.winfo_exists():
                return
            cbody = sf.master
            # 滚动容器顶部在页面坐标系中的 y（含卡片内边距）
            top_y = (cbody.winfo_rooty() - self.winfo_rooty()
                     + sf.winfo_y())
            avail = int(event.height) - top_y - theme.PAD - 4
            target = max(CAT_SCROLL_MIN_HEIGHT,
                         min(CAT_SCROLL_HEIGHT, avail))
            if abs(target - self._cat_scroll_height) >= 2:
                self._cat_scroll_height = target
                sf.set_fixed_height(target)
        except tk.TclError:
            return

    def _on_cat_scroll(self, first, last):
        """滚动回调：同步滚动条，并在内容超出视口时显示滚动提示。"""
        try:
            self.cat_scroll.scrollbar.set(first, last)
        except tk.TclError:
            return
        try:
            overflow = not (float(first) <= 0.0 and float(last) >= 1.0)
            self.cat_scroll_hint.configure(
                text="（可上下滚动查看全部）" if overflow else "")
        except (tk.TclError, ValueError):
            pass

    # ------------------------------------------------------------------
    # 账户下拉
    # ------------------------------------------------------------------
    def _reload_accounts(self):
        """重新加载账户下拉选项（含「全部账户」），并保持原选择（若仍存在）。"""
        try:
            self.accounts = list(db.list_accounts())
        except db.DatabaseError as exc:
            self.accounts = []
            show_toast(self._tkmaster, str(exc), kind="error")
        options = [ALL_ACCOUNTS_LABEL] + [
            "{} ({})".format(a["name"], theme.fmt_money(a["balance"]))
            for a in self.accounts
        ]
        self._account_options = options
        self.account_combo.configure(values=options)
        if self.account_var.get() not in options:
            self.account_var.set(ALL_ACCOUNTS_LABEL)

    def _selected_account_id(self):
        """由下拉当前选项反查账户 id。

        Returns:
            int | None: None 表示「全部账户」（对应全局预算 account_id=0）。
        """
        label = self.account_var.get()
        if label == ALL_ACCOUNTS_LABEL:
            return None
        for a in self.accounts:
            if label == "{} ({})".format(a["name"], theme.fmt_money(a["balance"])):
                return int(a["id"])
        return None

    def _scope_text(self):
        """返回当前账户作用域的中文描述（用于提示文案）。"""
        label = self.account_var.get()
        if label == ALL_ACCOUNTS_LABEL:
            return "全部账户"
        return label.split(" (")[0]

    # ------------------------------------------------------------------
    # 刷新
    # ------------------------------------------------------------------
    def refresh(self):
        """刷新总预算与分类预算的进度展示（按当前所选账户）。"""
        self._reload_accounts()
        account_id = self._selected_account_id()
        try:
            budgets = {row["category"]: float(row["amount"])
                       for row in db.list_budgets(self.month,
                                                  account_id=account_id)}
            total_budget = budgets.get(theme.BUDGET_TOTAL, 0.0)
            summary = db.month_summary(self.month, account_id=account_id)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return

        expense = summary["expense"]
        # 总预算进度
        self.total_entry.set("{:.2f}".format(total_budget) if total_budget else "")
        self._render_total(total_budget, expense)
        self._render_summary(total_budget, expense)

        # 分类预算
        for row in self._cat_rows:
            row[1].destroy()
        self._cat_rows = []
        cat_budgets = {k: v for k, v in budgets.items()
                       if k != theme.BUDGET_TOTAL and v > 0}
        if not cat_budgets:
            tk.Label(self.cat_list,
                     text="尚未设置分类预算，在上方选择分类并输入金额即可添加～",
                     bg=theme.CARD_WHITE, fg=theme.TEXT_MUTED,
                     font=theme.FONT_BODY).pack(anchor="w", pady=8)
            return

        for category, budget in sorted(cat_budgets.items()):
            spent = db.monthly_category_spend(self.month, category,
                                              account_id=account_id)
            row = tk.Frame(self.cat_list, bg=theme.CARD_WHITE)
            row.pack(fill="x", pady=4)
            tk.Label(row, text="{}{}".format(
                theme.CATEGORY_EMOJI.get(category, ""), category),
                bg=theme.CARD_WHITE, fg=theme.TEXT, font=theme.FONT_BODY_BOLD,
                width=8, anchor="w").pack(side="left")

            bar = ProgressBar(row, width=420, height=48, bg=theme.CARD_WHITE)
            bar.pack(side="left", padx=8)
            _apply_bar(bar, spent, budget)

            status = tk.Label(row, text=_status_text(spent, budget),
                              bg=theme.CARD_WHITE, fg=theme.TEXT,
                              font=theme.FONT_SMALL)
            status.pack(side="left", padx=6)
            self._cat_rows.append((category, row, status))

    def _render_total(self, budget, spent):
        """渲染总预算进度条、表情与大字剩余/超支金额。"""
        if budget <= 0:
            self.total_bar.set_value(0.0, color=theme.DISABLED_GRAY, mood="flat")
            self.total_pig.set_mood("flat")
            self.total_remain.configure(text="", fg=theme.TEXT_MUTED)
            self.total_status.configure(
                text="还未设置本月总预算，快在上方输入一个吧～", fg=theme.TEXT_MUTED)
            return
        pct = spent / budget
        color, mood = _state(pct)
        self.total_bar.set_value(pct, color=color, mood=mood)
        self.total_pig.set_mood(mood)
        remain = budget - spent
        if remain >= 0:
            self.total_remain.configure(text="本月剩余可用 {}".format(
                theme.fmt_money(remain)), fg=color)
        else:
            self.total_remain.configure(text="已超支 {}".format(
                theme.fmt_money(-remain)), fg=theme.DANGER_RED)
        self.total_status.configure(
            text="（已用 {} / {}".format(theme.fmt_money(spent),
                                    theme.fmt_money(budget)) + "，{}）".format(
                                        _state_text(pct)),
            fg=color)

    def _render_summary(self, budget, spent):
        """渲染页面顶部的中文总结提示。"""
        scope = self._scope_text()
        if budget <= 0:
            self.summary_label.configure(
                text="还没设置本月{}预算，设置后我会帮你盯着花销哦～".format(scope),
                fg=theme.TEXT_MUTED)
            return
        pct = spent / budget
        remain = budget - spent
        if pct > 1.0:
            self.summary_label.configure(
                text="已超支 {}，下个月要控制一下啦 🐷".format(
                    theme.fmt_money(-remain)), fg=theme.DANGER_RED)
        elif pct >= 0.7:
            self.summary_label.configure(
                text="注意！本月{}预算已用 {:.0f}%，只剩 {} 了".format(
                    scope, pct * 100, theme.fmt_money(remain)),
                fg=theme.WARN_YELLOW)
        else:
            self.summary_label.configure(
                text="本月{}还可花 {}，已用 {:.0f}%".format(
                    scope, theme.fmt_money(remain), pct * 100),
                fg=theme.INCOME_GREEN)

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def _save_total(self):
        """保存当前账户维度的月度总预算。"""
        text = self.total_entry.get().strip()
        if not text:
            show_toast(self._tkmaster, "请输入总预算金额", kind="warn")
            return
        try:
            amount = round(float(text), 2)
        except ValueError:
            show_toast(self._tkmaster, "预算金额格式不正确", kind="error")
            return
        if amount < 0:
            show_toast(self._tkmaster, "预算金额不能为负", kind="warn")
            return
        account_id = self._selected_account_id()
        try:
            db.set_budget(self.month, theme.BUDGET_TOTAL, amount,
                          account_id=account_id)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return
        self.refresh()
        show_toast(self._tkmaster, "已设置【{}】本月总预算 {}".format(
            self._scope_text(), theme.fmt_money(amount)), kind="success")

    def _save_category(self):
        """保存当前账户维度的某分类预算。"""
        category = self.cat_var.get()
        text = self.cat_entry.get().strip()
        if not text:
            show_toast(self._tkmaster, "请输入分类预算金额", kind="warn")
            return
        try:
            amount = round(float(text), 2)
        except ValueError:
            show_toast(self._tkmaster, "预算金额格式不正确", kind="error")
            return
        if amount < 0:
            show_toast(self._tkmaster, "预算金额不能为负", kind="warn")
            return
        account_id = self._selected_account_id()
        try:
            db.set_budget(self.month, category, amount, account_id=account_id)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return
        self.cat_entry.set("")
        self.refresh()
        show_toast(self._tkmaster, "已设置【{}】「{}」预算 {}".format(
            self._scope_text(), category, theme.fmt_money(amount)),
            kind="success")


# ---------------------------------------------------------------------------
# 纯逻辑辅助函数（可独立测试）
# ---------------------------------------------------------------------------
def _state(pct):
    """根据使用比例返回 (颜色, 小猪表情)。

    三档：
    - pct < 0.7        → 绿 + 笑脸猪（happy）
    - 0.7 <= pct <= 1.0 → 黄 + 平脸猪（flat）
    - pct > 1.0        → 红 + 哭泣猪（cry）

    Args:
        pct: 使用比例（已用 / 预算）。

    Returns:
        tuple: (color, mood)
    """
    if pct < 0.7:
        return theme.INCOME_GREEN, "happy"
    if pct <= 1.0:
        return theme.WARN_YELLOW, "flat"
    return theme.DANGER_RED, "cry"


def _state_text(pct):
    """根据使用比例返回三档中文状态词。"""
    if pct < 0.7:
        return "宽裕"
    if pct <= 1.0:
        return "接近上限"
    return "已超支"


def _status_text(spent, budget):
    """生成中文状态提示（剩余可用 / 超支）。"""
    if budget <= 0:
        return "未设置预算"
    remain = budget - spent
    if remain >= 0:
        return "已用 {} / {}，剩余可用 {}".format(
            theme.fmt_money(spent), theme.fmt_money(budget),
            theme.fmt_money(remain))
    return "已用 {} / {}，已超支 {}".format(
        theme.fmt_money(spent), theme.fmt_money(budget),
        theme.fmt_money(-remain))


def _apply_bar(bar, spent, budget):
    """根据分类预算情况设置进度条颜色与表情。"""
    if budget <= 0:
        bar.set_value(0.0, color=theme.DISABLED_GRAY, mood="flat")
        return
    pct = spent / budget
    color, mood = _state(pct)
    bar.set_value(pct, color=color, mood=mood)

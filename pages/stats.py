# -*- coding: utf-8 -*-
"""pages/stats.py —— 统计图表页面。

包含：月份切换器、收入/支出/结余数字卡、分类占比饼图（可点击高亮）、
近 6 个月收支趋势折线图。全部基于 tkinter Canvas 手绘。
"""

import datetime
import math
import tkinter as tk
from tkinter import ttk

import db
import theme
from ui_components import RoundCard, RoundButton, NumberCard, show_toast

#: 账户下拉中「全部账户」选项的显示文案。
ALL_ACCOUNTS_LABEL = "全部账户"


class StatsPage(tk.Frame):
    """统计图表页面。"""

    def __init__(self, master, app):
        """初始化页面。

        Args:
            master: 父容器。
            app: 主应用实例。
        """
        super().__init__(master, bg=theme.BG_CREAM)
        self.app = app
        today = datetime.date.today()
        self.year = today.year
        self.month = today.month
        self._pie_slices = []   # [(start_angle, end_angle, cx, cy, r, idx)]
        self._highlight = -1
        self._breakdown = []
        self.accounts = []           # 账户列表缓存
        self._account_options = []   # 账户下拉选项文案（含「全部账户」）
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
        tk.Label(header, text="📊 统计图表", bg=theme.BG_CREAM, fg=theme.TEXT,
                 font=theme.FONT_TITLE).pack(side="left")

        # 月份切换器
        switcher = tk.Frame(header, bg=theme.BG_CREAM)
        switcher.pack(side="right")
        RoundButton(switcher, text="◀", command=self._prev_month, width=44,
                    height=36, bg=theme.BG_CREAM, fill=theme.SECONDARY,
                    text_color=theme.TEXT, hover=theme.HOVER_LIGHT).pack(side="left")
        self.month_label = tk.Label(switcher, text="", bg=theme.BG_CREAM,
                                    fg=theme.TEXT, font=theme.FONT_SUBTITLE,
                                    width=10)
        self.month_label.pack(side="left", padx=6)
        RoundButton(switcher, text="▶", command=self._next_month, width=44,
                    height=36, bg=theme.BG_CREAM, fill=theme.SECONDARY,
                    text_color=theme.TEXT, hover=theme.HOVER_LIGHT).pack(side="left")

        # 账户筛选下拉（在月份切换器左侧，切换后所有统计随之变化）
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

        # 数字卡行（各卡片宽度随内容自适应，不再写死 180）
        cards_row = tk.Frame(self, bg=theme.BG_CREAM)
        cards_row.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self.income_card = NumberCard(cards_row, title="本月收入", value=0.0,
                                      color=theme.INCOME_GREEN)
        self.income_card.pack(side="left", padx=(0, theme.GAP))
        self.expense_card = NumberCard(cards_row, title="本月支出", value=0.0,
                                       color=theme.EXPENSE_PINK)
        self.expense_card.pack(side="left", padx=(0, theme.GAP))
        self.balance_card = NumberCard(cards_row, title="本月结余", value=0.0,
                                       color=theme.TEXT)
        self.balance_card.pack(side="left")

        # 图表行：饼图 + 折线图（固定高度，宽度自适应父容器）
        charts_row = tk.Frame(self, bg=theme.BG_CREAM)
        charts_row.pack(fill="both", expand=True, padx=theme.PAD,
                        pady=(0, theme.GAP))

        pie_card = RoundCard(charts_row, height=340, bg=theme.BG_CREAM)
        pie_card.pack(side="left", fill="both", expand=True,
                      padx=(0, theme.GAP))
        tk.Label(pie_card.body, text="支出分类占比", bg=theme.CARD_WHITE,
                 fg=theme.TEXT, font=theme.FONT_SUBTITLE).pack(anchor="w")
        self.pie_canvas = tk.Canvas(pie_card.body, bg=theme.CARD_WHITE,
                                    highlightthickness=0, bd=0)
        self.pie_canvas.pack(fill="both", expand=True)
        self.pie_canvas.bind("<Button-1>", self._on_pie_click)

        line_card = RoundCard(charts_row, height=340,
                              bg=theme.BG_CREAM)
        line_card.pack(side="left", fill="both", expand=True)
        tk.Label(line_card.body, text="近 6 个月收支趋势", bg=theme.CARD_WHITE,
                 fg=theme.TEXT, font=theme.FONT_SUBTITLE).pack(anchor="w")
        self.line_canvas = tk.Canvas(line_card.body, bg=theme.CARD_WHITE,
                                     highlightthickness=0, bd=0)
        self.line_canvas.pack(fill="both", expand=True)
        self.line_canvas.bind("<Configure>", lambda e: self._draw_line())

    # ------------------------------------------------------------------
    # 月份切换
    # ------------------------------------------------------------------
    def _prev_month(self):
        self.month -= 1
        if self.month == 0:
            self.month = 12
            self.year -= 1
        self.refresh()

    def _next_month(self):
        self.month += 1
        if self.month == 13:
            self.month = 1
            self.year += 1
        self.refresh()

    def _month_str(self):
        return "{:04d}-{:02d}".format(self.year, self.month)

    # ------------------------------------------------------------------
    # 账户下拉
    # ------------------------------------------------------------------
    def _reload_accounts(self):
        """重新加载账户下拉选项（含「全部账户」），并保持原选择（若仍存在）。

        账户数据来自 db.list_accounts()；账户名后附带余额，便于识别。
        """
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
            int | None: None 表示「全部账户」。
        """
        label = self.account_var.get()
        if label == ALL_ACCOUNTS_LABEL:
            return None
        for a in self.accounts:
            if label == "{} ({})".format(a["name"], theme.fmt_money(a["balance"])):
                return int(a["id"])
        return None

    # ------------------------------------------------------------------
    # 刷新
    # ------------------------------------------------------------------
    def refresh(self):
        """重新查询并绘制全部图表（按当前所选账户过滤）。"""
        month = self._month_str()
        self.month_label.configure(text=month)
        # 每次刷新重载账户下拉，保证在账户页新增账户后回到本页能看到新账户
        self._reload_accounts()
        account_id = self._selected_account_id()
        try:
            summary = db.month_summary(month, account_id=account_id)
            self._breakdown = db.category_breakdown(month, "支出",
                                                    account_id=account_id)
            trend = db.month_trend(6, month, account_id=account_id)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return

        self.income_card.set_value(summary["income"], theme.INCOME_GREEN)
        self.expense_card.set_value(summary["expense"], theme.EXPENSE_PINK)
        balance_color = theme.DANGER_RED if summary["balance"] < 0 else theme.INCOME_GREEN
        self.balance_card.set_value(summary["balance"], balance_color)

        self._highlight = -1
        self._trend = trend
        self.after(30, self._draw_pie)
        self.after(30, self._draw_line)

    # ------------------------------------------------------------------
    # 饼图绘制
    # ------------------------------------------------------------------
    def _draw_pie(self):
        """绘制分类占比饼图与图例。"""
        cv = self.pie_canvas
        cv.delete("all")
        w = cv.winfo_width() or 340
        h = cv.winfo_height() or 260
        data = self._breakdown
        if not data:
            cv.create_text(w / 2, h / 2, text="本月暂无支出数据",
                           fill=theme.TEXT_MUTED, font=theme.FONT_BODY)
            return

        legend_w = 130
        cx = (w - legend_w) / 2 + 10
        cy = h / 2
        r = max(30, min(cx, cy) - 20)
        total = sum(d["amount"] for d in data) or 1.0

        self._pie_slices = []
        start = 90.0  # 从 12 点方向开始，顺时针
        for idx, d in enumerate(data):
            extent = 360.0 * (d["amount"] / total)
            color = theme.CATEGORY_COLORS[idx % len(theme.CATEGORY_COLORS)]
            # Canvas 的 create_arc：start 逆时针，故用负 extent 顺时针
            arc_id = cv.create_arc(cx - r, cy - r, cx + r, cy + r,
                                   start=start, extent=-extent,
                                   fill=color, outline=theme.CARD_WHITE, width=2)
            self._pie_slices.append((start, start - extent, cx, cy, r, idx))
            start -= extent

        # 高亮扇形（重绘描边）
        if 0 <= self._highlight < len(self._pie_slices):
            s = self._pie_slices[self._highlight]
            cv.create_arc(cx - r, cy - r, cx + r, cy + r,
                          start=s[0], extent=s[1] - s[0],
                          style="arc", outline=theme.TEXT, width=4)

        # 中心百分比/总额
        cv.create_text(cx, cy, text="¥{:.0f}".format(total), fill=theme.TEXT,
                       font=theme.FONT_BODY_BOLD)

        # 图例
        lx = w - legend_w + 6
        ly = 14
        for idx, d in enumerate(data):
            color = theme.CATEGORY_COLORS[idx % len(theme.CATEGORY_COLORS)]
            cv.create_oval(lx, ly, lx + 10, ly + 10, fill=color, outline="")
            pct = d["ratio"] * 100
            text = "{}({:.0f}%)".format(d["category"], pct)
            fg = theme.TEXT if idx != self._highlight else theme.PRIMARY
            cv.create_text(lx + 16, ly + 5, text=text, anchor="w", fill=fg,
                           font=theme.FONT_SMALL)
            ly += 20
            if ly > h - 16:
                break

    def _on_pie_click(self, event):
        """点击判定落在哪个扇形内（极角+半径），高亮之。"""
        for (a_start, a_end, cx, cy, r, idx) in self._pie_slices:
            dx = event.x - cx
            dy = event.y - cy
            dist = math.hypot(dx, dy)
            if dist > r:
                continue
            # 计算点击点角度（Canvas 坐标系：y 向下）
            ang = math.degrees(math.atan2(-dy, dx))
            ang = (ang + 360) % 360
            lo, hi = min(a_start, a_end), max(a_start, a_end)
            # a_start 与 a_end 均已归一化到 0~360 附近
            lo_n, hi_n = (lo % 360), (hi % 360)
            hit = False
            if lo_n <= hi_n:
                hit = lo_n <= ang <= hi_n
            else:
                hit = ang >= lo_n or ang <= hi_n
            if hit:
                self._highlight = idx
                self._draw_pie()
                d = self._breakdown[idx]
                show_toast(self._tkmaster, "{}{}：{}（{:.0f}%）".format(
                    theme.CATEGORY_EMOJI.get(d["category"], ""), d["category"],
                    theme.fmt_money(d["amount"]), d["ratio"] * 100), kind="info")
                return
        self._highlight = -1
        self._draw_pie()

    # ------------------------------------------------------------------
    # 折线图绘制
    # ------------------------------------------------------------------
    def _draw_line(self):
        """绘制近 6 个月双线趋势图。"""
        cv = self.line_canvas
        cv.delete("all")
        w = cv.winfo_width() or 400
        h = cv.winfo_height() or 260
        trend = getattr(self, "_trend", None)
        if not trend:
            cv.create_text(w / 2, h / 2, text="暂无趋势数据",
                           fill=theme.TEXT_MUTED, font=theme.FONT_BODY)
            return

        margin_l, margin_r, margin_t, margin_b = 48, 16, 24, 36
        plot_w = max(1, w - margin_l - margin_r)
        plot_h = max(1, h - margin_t - margin_b)

        max_val = max([max(d["income"], d["expense"]) for d in trend] + [1.0])
        # y 轴网格 + 刻度
        for i in range(5):
            y = margin_t + plot_h * i / 4
            val = max_val * (1 - i / 4)
            cv.create_line(margin_l, y, w - margin_r, y,
                           fill=theme.TRACK_BG, dash=(3, 3))
            cv.create_text(margin_l - 6, y, text="{:.0f}".format(val),
                           anchor="e", fill=theme.TEXT_MUTED,
                           font=theme.FONT_SMALL)
        # 轴线
        cv.create_line(margin_l, margin_t, margin_l, margin_t + plot_h,
                       fill=theme.CARD_BORDER)
        cv.create_line(margin_l, margin_t + plot_h, w - margin_r,
                       margin_t + plot_h, fill=theme.CARD_BORDER)

        n = len(trend)
        step = plot_w / max(1, n - 1) if n > 1 else 0

        def point(i, value):
            x = margin_l + step * i
            y = margin_t + plot_h * (1 - value / max_val)
            return x, y

        # 收入线（绿）
        self._draw_series(cv, trend, "income", theme.INCOME_GREEN, point, n)
        # 支出线（粉）
        self._draw_series(cv, trend, "expense", theme.EXPENSE_PINK, point, n)

        # 月份标签
        for i, d in enumerate(trend):
            x, _ = point(i, 0)
            label = d["month"][5:]  # 只显示 MM
            cv.create_text(x, margin_t + plot_h + 14, text=label,
                           fill=theme.TEXT, font=theme.FONT_SMALL)

        # 图例
        cv.create_oval(margin_l, 6, margin_l + 10, 16, fill=theme.INCOME_GREEN,
                       outline="")
        cv.create_text(margin_l + 16, 11, text="收入", anchor="w",
                       fill=theme.TEXT, font=theme.FONT_SMALL)
        cv.create_oval(margin_l + 60, 6, margin_l + 70, 16,
                       fill=theme.EXPENSE_PINK, outline="")
        cv.create_text(margin_l + 76, 11, text="支出", anchor="w",
                       fill=theme.TEXT, font=theme.FONT_SMALL)

    def _draw_series(self, cv, trend, key, color, point, n):
        """绘制单条折线（含数据点圆点）。"""
        coords = []
        for i, d in enumerate(trend):
            coords.extend(point(i, d[key]))
        if len(coords) >= 4:
            cv.create_line(*coords, fill=color, width=2, smooth=True)
        for i, d in enumerate(trend):
            x, y = point(i, d[key])
            cv.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color,
                           outline=theme.CARD_WHITE, width=1)

# -*- coding: utf-8 -*-
"""pages/record.py —— 记账收支页面。

包含：记账表单（金额/类型/分类/备注/日期/账户）、明细列表（Treeview）、
筛选、删除（自绘确认框）、保存后小猪表情动画。
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
    CapsuleToggle,
    show_toast,
    ask_confirm,
)


class RecordPage(tk.Frame):
    """记账收支页面。"""

    def __init__(self, master, app):
        """初始化页面。

        Args:
            master: 父容器。
            app: 主应用实例（用于访问 pig_canvas 等）。
        """
        super().__init__(master, bg=theme.BG_CREAM)
        self.app = app
        self.accounts = []          # 缓存账户列表
        self._build()
        self.refresh(initial=True)

    @property
    def _tkmaster(self):
        """返回用于弹窗/提示条的真实 tkinter 顶层窗口。

        绝不能把 ``self.app``（普通 PiggyApp 对象）直接当 master 传，
        否则 ``tk.Toplevel`` 会因缺少 ``.tk`` 属性而崩溃。
        """
        root = getattr(self.app, "root", None)
        return root if root is not None else self

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build(self):
        """构建整个页面布局。"""
        # 标题
        header = tk.Frame(self, bg=theme.BG_CREAM)
        header.pack(fill="x", padx=theme.PAD, pady=(theme.GAP, 0))
        tk.Label(header, text="✏️ 记一笔", bg=theme.BG_CREAM, fg=theme.TEXT,
                 font=theme.FONT_TITLE).pack(side="left")

        # 上部：表单卡片（宽度自适应父容器，高度自适应内容）
        form_card = RoundCard(self, bg=theme.BG_CREAM)
        form_card.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._build_form(form_card.body)

        # 下部：明细卡片（宽度自适应，高度按内容自适应）
        list_card = RoundCard(self, bg=theme.BG_CREAM)
        list_card.pack(fill="both", expand=True, padx=theme.PAD,
                       pady=(0, theme.GAP))
        self._build_list(list_card.body)

    def _build_form(self, body):
        """构建记账表单（两列网格）。"""
        bg = theme.CARD_WHITE
        # 第一行：类型切换 + 金额
        tk.Label(body, text="类型", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).grid(row=0, column=0, sticky="w",
                                                  pady=6, padx=(0, 8))
        self.type_toggle = CapsuleToggle(
            body, options=["支出", "收入"], value="支出",
            command=lambda v: None, width=200, height=38, bg=bg,
        )
        self.type_toggle.grid(row=0, column=1, sticky="w", pady=6)

        tk.Label(body, text="金额", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).grid(row=0, column=2, sticky="w",
                                                  pady=6, padx=(24, 8))
        self.amount_entry = RoundEntry(body, width=200, height=38, bg=bg,
                                       fill=theme.TRACK_BG)
        self.amount_entry.grid(row=0, column=3, sticky="w", pady=6)

        # 第二行：分类 + 日期
        tk.Label(body, text="分类", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).grid(row=1, column=0, sticky="w",
                                                  pady=6, padx=(0, 8))
        cat_frame = tk.Frame(body, bg=bg)
        cat_frame.grid(row=1, column=1, sticky="w", pady=6)
        self.cat_var = tk.StringVar(value=theme.CATEGORIES[0])
        self.cat_combo = ttk.Combobox(cat_frame, textvariable=self.cat_var,
                                      values=theme.CATEGORIES, width=12,
                                      state="readonly", font=theme.FONT_BODY)
        self.cat_combo.pack(side="left")
        self.cat_combo.bind("<<ComboboxSelected>>", self._on_category_change)
        self.cat_emoji = tk.Label(cat_frame, text=theme.CATEGORY_EMOJI.get(
            theme.CATEGORIES[0], ""), bg=bg, font=theme.font(14), width=3)
        self.cat_emoji.pack(side="left", padx=(6, 0))

        tk.Label(body, text="日期", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).grid(row=1, column=2, sticky="w",
                                                  pady=6, padx=(24, 8))
        date_frame = tk.Frame(body, bg=bg)
        date_frame.grid(row=1, column=3, sticky="w", pady=6)
        today = datetime.date.today().strftime("%Y-%m-%d")
        self.date_var = tk.StringVar(value=today)
        self.date_entry = RoundEntry(date_frame, width=140, height=38, bg=bg,
                                     fill=theme.TRACK_BG,
                                     textvariable=self.date_var)
        self.date_entry.pack(side="left")
        tk.Label(date_frame, text="(YYYY-MM-DD)", bg=bg, fg=theme.TEXT_MUTED,
                 font=theme.FONT_SMALL).pack(side="left", padx=(6, 0))

        # 第三行：账户 + 备注
        tk.Label(body, text="账户", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).grid(row=2, column=0, sticky="w",
                                                  pady=6, padx=(0, 8))
        self.acc_var = tk.StringVar()
        self.acc_combo = ttk.Combobox(body, textvariable=self.acc_var,
                                      values=[], width=16, state="readonly",
                                      font=theme.FONT_BODY)
        self.acc_combo.grid(row=2, column=1, sticky="w", pady=6)

        tk.Label(body, text="备注", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).grid(row=2, column=2, sticky="w",
                                                  pady=6, padx=(24, 8))
        self.note_entry = RoundEntry(body, width=200, height=38, bg=bg,
                                     fill=theme.TRACK_BG)
        self.note_entry.grid(row=2, column=3, sticky="w", pady=6)

        # 第四行：保存按钮 + 快速提示
        btn_row = tk.Frame(body, bg=bg)
        btn_row.grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 4))
        RoundButton(btn_row, text="💾 保存", command=self._on_save,
                    width=140, height=42, bg=bg, fill=theme.PRIMARY,
                    hover=theme.HOVER_LIGHT).pack(side="left")
        tk.Label(btn_row, text="金额必填，支持两位小数", bg=bg,
                 fg=theme.TEXT_MUTED, font=theme.FONT_SMALL).pack(
                     side="left", padx=(12, 0))

    def _build_list(self, body):
        """构建明细列表区（筛选栏 + Treeview）。"""
        bg = theme.CARD_WHITE
        # 筛选栏
        filter_row = tk.Frame(body, bg=bg)
        filter_row.pack(fill="x", pady=(0, 8))
        tk.Label(filter_row, text="明细筛选", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_SUBTITLE).pack(side="left")

        tk.Label(filter_row, text="月份", bg=bg, fg=theme.TEXT_MUTED,
                 font=theme.FONT_SMALL).pack(side="left", padx=(16, 4))
        # 月份切换：◀ 箭头 + 下拉框 + ▶ 箭头（下拉可切到任意月份，含无数据月份）
        self.filter_month_var = tk.StringVar(value="全部")
        RoundButton(filter_row, text="◀", command=self._prev_filter_month,
                    width=34, height=30, bg=bg, fill=theme.SECONDARY,
                    text_color=theme.TEXT, hover=theme.HOVER_LIGHT
                    ).pack(side="left")
        self.filter_month_combo = ttk.Combobox(
            filter_row, textvariable=self.filter_month_var, values=["全部"],
            width=9, state="readonly", font=theme.FONT_SMALL)
        self.filter_month_combo.pack(side="left", padx=4)
        RoundButton(filter_row, text="▶", command=self._next_filter_month,
                    width=34, height=30, bg=bg, fill=theme.SECONDARY,
                    text_color=theme.TEXT, hover=theme.HOVER_LIGHT
                    ).pack(side="left")
        self.filter_month_combo.bind("<<ComboboxSelected>>",
                                     lambda e: self._reload_list())

        tk.Label(filter_row, text="类型", bg=bg, fg=theme.TEXT_MUTED,
                 font=theme.FONT_SMALL).pack(side="left", padx=(12, 4))
        self.filter_type_var = tk.StringVar(value="全部")
        ttk.Combobox(filter_row, textvariable=self.filter_type_var,
                     values=["全部", "收入", "支出"], width=6, state="readonly",
                     font=theme.FONT_SMALL).pack(side="left")
        self.filter_type_var.trace_add("write", lambda *a: self._reload_list())

        tk.Label(filter_row, text="账户", bg=bg, fg=theme.TEXT_MUTED,
                 font=theme.FONT_SMALL).pack(side="left", padx=(12, 4))
        self.filter_acc_var = tk.StringVar(value="全部")
        self.filter_acc_combo = ttk.Combobox(
            filter_row, textvariable=self.filter_acc_var, values=["全部"],
            width=10, state="readonly", font=theme.FONT_SMALL)
        self.filter_acc_combo.pack(side="left")
        self.filter_acc_combo.bind("<<ComboboxSelected>>",
                                   lambda e: self._reload_list())

        # 删除按钮
        RoundButton(filter_row, text="🗑 删除选中", command=self._on_delete,
                    width=110, height=34, bg=bg, fill=theme.EXPENSE_PINK,
                    hover=theme.HOVER_LIGHT).pack(side="right")

        # Treeview
        tree_frame = tk.Frame(body, bg=bg)
        tree_frame.pack(fill="both", expand=True)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Piggy.Treeview", background=theme.CARD_WHITE,
                        fieldbackground=theme.CARD_WHITE, foreground=theme.TEXT,
                        rowheight=30, font=theme.FONT_BODY, borderwidth=0)
        style.configure("Piggy.Treeview.Heading", background=theme.SECONDARY,
                        foreground=theme.TEXT, font=theme.FONT_BODY_BOLD,
                        borderwidth=0)
        style.map("Piggy.Treeview", background=[("selected", theme.HOVER_LIGHT)])

        columns = ("date", "category", "note", "amount")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 style="Piggy.Treeview", selectmode="browse",
                                 height=8)
        self.tree.heading("date", text="日期")
        self.tree.heading("category", text="分类")
        self.tree.heading("note", text="备注")
        self.tree.heading("amount", text="金额")
        self.tree.column("date", width=130, anchor="center")
        self.tree.column("category", width=120, anchor="center")
        self.tree.column("note", width=260, anchor="w")
        self.tree.column("amount", width=140, anchor="e")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        # Tag 颜色：收入绿、支出粉红
        self.tree.tag_configure("income", foreground=theme.INCOME_GREEN)
        self.tree.tag_configure("expense", foreground=theme.EXPENSE_PINK)

    # ------------------------------------------------------------------
    # 数据刷新
    # ------------------------------------------------------------------
    def refresh(self, initial=False):
        """刷新账户下拉、筛选月份选项与明细列表。

        Args:
            initial: 是否首次加载。
        """
        self._reload_accounts()
        self._reload_filter_months()
        self._reload_list()
        # 首次加载时，等控件真正映射后再刷一次，避免因窗口尚未布局导致
        # Treeview 高度/数据未生效（历史上出现过「明明有数据却显示 0 行」）。
        try:
            self.after_idle(self._reload_list)
        except tk.TclError:
            pass

    def _reload_accounts(self):
        """重新加载账户下拉（表单 + 筛选）。"""
        try:
            self.accounts = list(db.list_accounts())
        except db.DatabaseError as exc:
            self.accounts = []
            show_toast(self._tkmaster, str(exc), kind="error")
        names = ["{} ({})".format(a["name"], theme.fmt_money(a["balance"]))
                 for a in self.accounts]
        self.acc_combo.configure(values=names)
        if names and not self.acc_var.get():
            self.acc_var.set(names[0])
        elif names:
            # 保持原选择（若仍存在）
            current = self.acc_var.get()
            self.acc_combo.configure(values=names)
            if current not in names:
                self.acc_var.set(names[0])

        filter_names = ["全部"] + [a["name"] for a in self.accounts]
        self.filter_acc_combo.configure(values=filter_names)
        if self.filter_acc_var.get() not in filter_names:
            self.filter_acc_var.set("全部")

    def _reload_filter_months(self):
        """生成月份筛选选项：'全部' + 最近 24 个月（无论是否有数据）。

        与统计页交互一致——用户可切到任意月份（含尚无记账记录的月份），
        不再局限于「只在 transactions 里出现过的月份」。
        """
        values = ["全部"] + self._recent_months(24)
        self.filter_month_combo.configure(values=values)
        if self.filter_month_var.get() not in values:
            self.filter_month_var.set("全部")

    @staticmethod
    def _recent_months(count=24, end=None):
        """生成以 end（默认当前月）结尾的最近 count 个月的 'YYYY-MM' 列表（降序）。

        Args:
            count: 月份数量。
            end: 'YYYY-MM'，序列末尾月份；None 表示当前月。

        Returns:
            list[str]: 形如 ['2026-10', '2026-09', ...]，按时间倒序。
        """
        today = datetime.date.today()
        if end:
            try:
                year, mon = (int(x) for x in str(end).split("-"))
            except (ValueError, TypeError):
                year, mon = today.year, today.month
        else:
            year, mon = today.year, today.month
        months = []
        for _ in range(int(count)):
            months.append("{:04d}-{:02d}".format(year, mon))
            mon -= 1
            if mon == 0:
                mon = 12
                year -= 1
        return months

    def _shift_filter_month(self, step):
        """把月份筛选按 step 个月平移（◀/▶ 箭头）。

        - 若当前为「全部」，则以当前月为基准平移；
        - 平移结果裁剪在「最近 24 个月 + 当前月之后」范围内不生效，
          直接设置到下拉变量（下拉只读，仍可通过 set 修改）。
        """
        current = self.filter_month_var.get()
        today = datetime.date.today()
        if current == "全部":
            year, mon = today.year, today.month
        else:
            try:
                year, mon = (int(x) for x in str(current).split("-"))
            except (ValueError, TypeError):
                year, mon = today.year, today.month
        mon += int(step)
        while mon > 12:
            mon -= 12
            year += 1
        while mon < 1:
            mon += 12
            year -= 1
        self.filter_month_var.set("{:04d}-{:02d}".format(year, mon))
        self._reload_list()

    def _prev_filter_month(self):
        """月份筛选左移一个月并刷新列表。"""
        self._shift_filter_month(-1)

    def _next_filter_month(self):
        """月份筛选右移一个月并刷新列表。"""
        self._shift_filter_month(1)

    def _current_account_id(self):
        """由表单中选中的账户名反查账户 id。"""
        name = self.acc_var.get()
        for a in self.accounts:
            if name == "{} ({})".format(a["name"], theme.fmt_money(a["balance"])):
                return int(a["id"])
        return int(self.accounts[0]["id"]) if self.accounts else None

    def _filter_params(self):
        """组装当前筛选条件（供列表与导出复用）。

        Returns:
            tuple: (month, tx_type, account_id)
        """
        month = self.filter_month_var.get()
        month = None if month == "全部" else month
        tx_type = self.filter_type_var.get()
        tx_type = None if tx_type == "全部" else tx_type
        acc_name = self.filter_acc_var.get()
        account_id = None
        if acc_name != "全部":
            for a in self.accounts:
                if a["name"] == acc_name:
                    account_id = int(a["id"])
                    break
        return month, tx_type, account_id

    def _reload_list(self):
        """按当前筛选条件刷新明细列表。"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        month, tx_type, account_id = self._filter_params()
        try:
            rows = db.list_transactions(month=month, tx_type=tx_type,
                                        account_id=account_id)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return
        for row in rows:
            is_income = row["type"] == "收入"
            tag = "income" if is_income else "expense"
            amount_text = theme.fmt_money_signed(row["amount"], is_income)
            self.tree.insert(
                "", "end", iid=str(row["id"]),
                values=(row["date"], row["category"], row["note"] or "",
                        amount_text),
                tags=(tag,),
            )

    def _on_category_change(self, _event=None):
        """分类切换时更新 emoji。"""
        self.cat_emoji.configure(
            text=theme.CATEGORY_EMOJI.get(self.cat_var.get(), "📦"))

    # ------------------------------------------------------------------
    # 保存 / 删除
    # ------------------------------------------------------------------
    def _on_save(self):
        """校验并保存一笔交易。"""
        amount_text = self.amount_entry.get().strip()
        if not amount_text:
            show_toast(self._tkmaster, "请输入金额", kind="warn")
            return
        try:
            amount = round(float(amount_text), 2)
        except ValueError:
            show_toast(self._tkmaster, "金额格式不正确，请输入数字", kind="error")
            return
        if amount <= 0:
            show_toast(self._tkmaster, "金额必须大于 0", kind="warn")
            return

        date_text = self.date_var.get().strip()
        try:
            datetime.datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            show_toast(self._tkmaster, "日期格式应为 YYYY-MM-DD", kind="error")
            return

        if not self.accounts:
            show_toast(self._tkmaster, "请先在「账户」页添加账户", kind="warn")
            return

        tx_type = self.type_toggle.get()
        category = self.cat_var.get()
        note = self.note_entry.get().strip()
        account_id = self._current_account_id()

        try:
            db.add_transaction(tx_type, amount, category, note, date_text,
                               account_id)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return

        # 成功反馈
        self.amount_entry.set("")
        self.note_entry.set("")
        self._reload_accounts()
        self._reload_filter_months()
        self._reload_list()
        show_toast(self._tkmaster, "已记录一笔{}：{}".format(
            tx_type, theme.fmt_money(amount)), kind="success")
        self._flash_pig_happy()

    def _flash_pig_happy(self):
        """右上角小猪切换开心表情 1.5 秒后恢复。"""
        pig = getattr(self.app, "pig_canvas", None)
        if pig is None:
            return
        pig.set_mood("happy")
        self.after(1500, lambda: pig.set_mood("happy"))

    def _on_delete(self):
        """删除选中的交易（先弹自绘确认框）。"""
        sel = self.tree.selection()
        if not sel:
            show_toast(self._tkmaster, "请先选中要删除的明细", kind="warn")
            return
        tx_id = int(sel[0])

        def do_delete():
            try:
                db.delete_transaction(tx_id)
            except db.DatabaseError as exc:
                show_toast(self._tkmaster, str(exc), kind="error")
                return
            self._reload_accounts()
            self._reload_filter_months()
            self._reload_list()
            show_toast(self._tkmaster, "已删除该笔记录，余额已回滚", kind="success")

        ask_confirm(self._tkmaster, "删除确认",
                    "确定要删除这笔记录吗？删除后账户余额会自动回滚哦～",
                    on_ok=do_delete, ok_text="删除", cancel_text="再想想")

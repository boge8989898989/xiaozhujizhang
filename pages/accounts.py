# -*- coding: utf-8 -*-
"""pages/accounts.py —— 多账户与导出页面。

包含：账户卡片列表（增/改/删）、账户余额展示、按当前筛选范围一键导出 CSV
（UTF-8-sig，Excel 可直接打开），导出失败友好提示。
"""

import csv
import tkinter as tk
from tkinter import filedialog, ttk

import db
import theme
from ui_components import (
    RoundCard,
    RoundButton,
    RoundEntry,
    CapsuleToggle,
    ScrollFrame,
    show_toast,
    ask_confirm,
)


class AccountsPage(tk.Frame):
    """多账户与导出页面。"""

    def __init__(self, master, app):
        """初始化页面。

        Args:
            master: 父容器。
            app: 主应用实例（用于读取当前筛选条件）。
        """
        super().__init__(master, bg=theme.BG_CREAM)
        self.app = app
        self.accounts = []
        self._editing_id = None   # 正在编辑的账户 id（None 表示新增模式）
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
        tk.Label(header, text="💳 多账户与导出", bg=theme.BG_CREAM,
                 fg=theme.TEXT, font=theme.FONT_TITLE).pack(side="left")
        RoundButton(header, text="📤 导出 CSV", command=self._on_export,
                    width=140, height=40, bg=theme.BG_CREAM, fill=theme.ACCENT,
                    hover=theme.HOVER_LIGHT).pack(side="right")

        # 账户编辑卡片（宽度自适应父容器，高度自适应内容）
        edit_card = RoundCard(self, bg=theme.BG_CREAM)
        edit_card.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._build_editor(edit_card.body)

        # 账户列表卡片（宽度自适应，高度按内容自适应）
        # 关键修复：账户列表放入可滚动容器（Canvas + 内嵌 Frame + Scrollbar），
        # 否则 RoundCard 高度自适应 + list_frame expand 会让列表区域被压扁，
        # 账户一多就看不到新增的卡片。
        list_card = RoundCard(self, bg=theme.BG_CREAM)
        list_card.pack(fill="both", expand=True, padx=theme.PAD,
                       pady=(0, theme.GAP))
        tk.Label(list_card.body, text="我的账户", bg=theme.CARD_WHITE,
                 fg=theme.TEXT, font=theme.FONT_SUBTITLE).pack(anchor="w")

        # 可滚动区：复用通用 ScrollFrame（Canvas + 内嵌 Frame + 垂直滚动条），
        # 避免与预算页各写一套、两处 bind_all 冲突。pady=(8, 0) 保持原间距。
        self.scroll = ScrollFrame(list_card.body, scroller=self, bg=theme.CARD_WHITE)
        self.scroll.pack(fill="both", expand=True, pady=(8, 0))
        # 兼容旧属性名（list_canvas / list_frame 供外部或测试引用）。
        self.list_canvas = self.scroll.canvas
        self.list_frame = self.scroll.content

    def _build_editor(self, body):
        """构建账户新增/编辑表单。"""
        bg = theme.CARD_WHITE
        row1 = tk.Frame(body, bg=bg)
        row1.pack(fill="x")
        tk.Label(row1, text="账户名称", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).pack(side="left")
        self.name_entry = RoundEntry(row1, width=180, height=38, bg=bg,
                                     fill=theme.TRACK_BG)
        self.name_entry.pack(side="left", padx=(8, 20))

        tk.Label(row1, text="类型", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).pack(side="left")
        self.type_var = tk.StringVar(value=theme.ACCOUNT_TYPES[0])
        self.type_combo = ttk.Combobox(row1, textvariable=self.type_var,
                                       values=theme.ACCOUNT_TYPES, width=10,
                                       state="readonly", font=theme.FONT_BODY)
        self.type_combo.pack(side="left", padx=(8, 20))

        tk.Label(row1, text="初始余额", bg=bg, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD).pack(side="left")
        self.balance_entry = RoundEntry(row1, width=140, height=38, bg=bg,
                                        fill=theme.TRACK_BG)
        self.balance_entry.pack(side="left", padx=(8, 6))
        # 余额说明（编辑模式下置灰并提示不可修改）
        self.balance_hint = tk.Label(
            row1, text="", bg=bg, fg=theme.TEXT_MUTED, font=theme.FONT_SMALL)
        self.balance_hint.pack(side="left", padx=(0, 20))

        # 按钮行
        row2 = tk.Frame(body, bg=bg)
        row2.pack(fill="x", pady=(12, 0))
        self.save_btn = RoundButton(row2, text="➕ 新增账户",
                                    command=self._on_save_account, width=140,
                                    height=40, bg=bg, fill=theme.PRIMARY,
                                    hover=theme.HOVER_LIGHT)
        self.save_btn.pack(side="left")
        RoundButton(row2, text="清空输入", command=self._on_clear_clicked,
                    width=110, height=40, bg=bg, fill=theme.TRACK_BG,
                    text_color=theme.TEXT, hover=theme.HOVER_LIGHT
                    ).pack(side="left", padx=8)
        self.hint_label = tk.Label(
            row2, text="提示：新增账户可填写初始余额",
            bg=bg, fg=theme.TEXT_MUTED, font=theme.FONT_SMALL)
        self.hint_label.pack(side="left", padx=8)

    # ------------------------------------------------------------------
    # 刷新
    # ------------------------------------------------------------------
    def refresh(self):
        """重新加载账户列表并绘制卡片。"""
        try:
            self.accounts = list(db.list_accounts())
        except db.DatabaseError as exc:
            self.accounts = []
            show_toast(self._tkmaster, str(exc), kind="error")
        for child in self.list_frame.winfo_children():
            child.destroy()

        if not self.accounts:
            tk.Label(self.list_frame, text="暂无账户，请在上方新增账户。",
                     bg=theme.CARD_WHITE, fg=theme.TEXT_MUTED,
                     font=theme.FONT_BODY).pack(anchor="w", pady=8)
            return

        for acc in self.accounts:
            self._render_account_card(acc)

    def _render_account_card(self, acc):
        """渲染单个账户卡片（名称、类型、余额、编辑/删除）。"""
        card = tk.Frame(self.list_frame, bg=theme.HOVER_LIGHT,
                        highlightthickness=1, highlightbackground=theme.CARD_BORDER)
        card.pack(fill="x", pady=4)
        inner = tk.Frame(card, bg=theme.HOVER_LIGHT)
        inner.pack(fill="x", padx=12, pady=8)

        icon = theme.CATEGORY_EMOJI.get("理财", "💳")
        tk.Label(inner, text=icon, bg=theme.HOVER_LIGHT, font=theme.font(16)
                 ).pack(side="left")
        tk.Label(inner, text=acc["name"], bg=theme.HOVER_LIGHT, fg=theme.TEXT,
                 font=theme.FONT_BODY_BOLD, width=14, anchor="w"
                 ).pack(side="left", padx=6)
        tk.Label(inner, text="[{}]".format(acc["type"]), bg=theme.HOVER_LIGHT,
                 fg=theme.TEXT_MUTED, font=theme.FONT_SMALL, width=8, anchor="w"
                 ).pack(side="left")
        balance = float(acc["balance"])
        color = theme.INCOME_GREEN if balance >= 0 else theme.DANGER_RED
        tk.Label(inner, text=theme.fmt_money(balance), bg=theme.HOVER_LIGHT,
                 fg=color, font=theme.FONT_MONEY_MID).pack(side="left", padx=12)

        RoundButton(inner, text="编辑", width=70, height=32, bg=theme.HOVER_LIGHT,
                    fill=theme.SECONDARY, text_color=theme.TEXT,
                    hover=theme.WARN_YELLOW,
                    command=lambda a=acc: self._start_edit(a)).pack(side="right",
                                                                     padx=4)
        RoundButton(inner, text="删除", width=70, height=32, bg=theme.HOVER_LIGHT,
                    fill=theme.EXPENSE_PINK, hover=theme.DANGER_RED,
                    command=lambda a=acc: self._confirm_delete(a)).pack(
                        side="right", padx=4)

    # ------------------------------------------------------------------
    # 编辑 / 保存 / 删除
    # ------------------------------------------------------------------
    def _start_edit(self, acc):
        """进入编辑模式，把账户信息填入表单。

        编辑模式下「初始余额」置为只读：余额由收支流水自动计算，
        不允许手动改写（避免误操作把余额清零）。
        """
        self._editing_id = int(acc["id"])
        self.name_entry.set(acc["name"])
        self.type_var.set(acc["type"] if acc["type"] in theme.ACCOUNT_TYPES
                          else theme.ACCOUNT_TYPES[0])
        self.balance_entry.set("{:.2f}".format(float(acc["balance"])))
        # 禁用余额输入框（浅灰 + 只读）
        self.balance_entry.set_enabled(False)
        self.balance_hint.configure(
            text="余额由收支自动计算，不可手动修改", fg=theme.TEXT_MUTED)
        self.save_btn.set_text("💾 保存修改")
        self.hint_label.configure(text="正在编辑「{}」".format(acc["name"]),
                                  fg=theme.PRIMARY)
        show_toast(self._tkmaster, "正在编辑「{}」".format(acc["name"]),
                   kind="info")

    def _on_clear_clicked(self):
        """「清空输入」按钮回调：清空表单并给出可见反馈。"""
        self._clear_editor()
        show_toast(self._tkmaster, "已清空表单", kind="info")

    def _clear_editor(self):
        """清空表单并回到新增模式（余额输入框恢复可编辑）。"""
        self._editing_id = None
        self.name_entry.set("")
        self.type_var.set(theme.ACCOUNT_TYPES[0])
        self.balance_entry.set("")
        self.balance_entry.set_enabled(True)
        self.balance_hint.configure(text="")
        self.save_btn.set_text("➕ 新增账户")
        self.hint_label.configure(text="提示：新增账户可填写初始余额",
                                  fg=theme.TEXT_MUTED)

    def _on_save_account(self):
        """保存账户（新增或更新）。

        编辑模式下余额字段被禁用，禁止用表单值覆盖账户余额；
        此时传当前账户的实际余额给 ``db.update_account``，确保余额不被清零。
        """
        name = self.name_entry.get().strip()
        if not name:
            show_toast(self._tkmaster, "请输入账户名称", kind="warn")
            return
        acc_type = self.type_var.get() or theme.ACCOUNT_TYPES[0]

        if self._editing_id is None:
            # 新增模式：余额来自表单
            balance_text = self.balance_entry.get().strip() or "0"
            try:
                balance = round(float(balance_text), 2)
            except ValueError:
                show_toast(self._tkmaster, "余额格式不正确", kind="error")
                return
            action_done = "新增"
        else:
            # 编辑模式：余额锁定为账户当前实际余额，绝不使用（可能为空的）表单值
            current = db.get_account(self._editing_id)
            if current is None:
                show_toast(self._tkmaster, "账户不存在，可能已被删除", kind="error")
                self._clear_editor()
                self.refresh()
                return
            balance = float(current["balance"])
            action_done = "更新"

        try:
            if self._editing_id is None:
                db.add_account(name, acc_type, balance)
                msg = "已新增账户「{}」".format(name)
            else:
                db.update_account(self._editing_id, name, acc_type, balance)
                msg = "已更新账户「{}」".format(name)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return

        self._clear_editor()
        self.refresh()
        self._notify_others()
        show_toast(self._tkmaster, msg, kind="success")

    def _confirm_delete(self, acc):
        """删除账户（自绘确认框 + 级联删除该账户名下所有记账记录）。

        行为：
        - 确认框明确告知将连带删除的记账记录条数；
        - 确认后调用 ``db.delete_account_cascade`` 在一个事务内
          先删该账户所有 transactions，再删账户本身；
        - 账户已被删除，故不做余额回滚（不存在可更新的账户）；
        - 删除后刷新账户列表，并通知记账/统计/预算页刷新（被删账户名
          应从各页账户下拉中消失）。
        """
        acc_id = int(acc["id"])
        if len(self.accounts) <= 1:
            show_toast(self._tkmaster, "至少保留一个账户哦", kind="warn")
            return

        # 统计该账户名下的记账记录条数，用于确认框提示
        try:
            tx_count = db.count_transactions_by_account(acc_id)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return

        def do_delete():
            try:
                db.delete_account_cascade(acc_id)
            except db.DatabaseError as exc:
                show_toast(self._tkmaster, str(exc), kind="error")
                return
            self.refresh()
            self._notify_others()
            show_toast(
                self._tkmaster,
                "已删除账户「{}」及其 {} 条记账记录".format(acc["name"], tx_count),
                kind="success",
            )

        message = (
            "确定删除账户「{}」吗？该账户下的 {} 条记账记录也会一并删除，"
            "此操作不可撤销。".format(acc["name"], tx_count)
        )
        ask_confirm(self._tkmaster, "删除账户", message,
                    on_ok=do_delete, ok_text="删除", cancel_text="取消")

    def _notify_others(self):
        """账户变化后通知记账/统计/预算页刷新（账户下拉、筛选、列表）。

        被删账户的名字不应再出现在任何页面的账户下拉中。
        """
        for key in ("record", "stats", "budget"):
            try:
                page = self.app.pages.get(key)
                if page is not None and hasattr(page, "refresh"):
                    page.refresh()
            except (AttributeError, tk.TclError):
                continue

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------
    def _on_export(self):
        """按当前筛选范围导出 CSV（UTF-8-sig）。"""
        month, tx_type, account_id = self._current_filter()
        try:
            rows = db.query_for_export(month=month, tx_type=tx_type,
                                       account_id=account_id)
        except db.DatabaseError as exc:
            show_toast(self._tkmaster, str(exc), kind="error")
            return

        if not rows:
            show_toast(self._tkmaster, "当前筛选范围没有可导出的记录", kind="warn")
            return

        path = filedialog.asksaveasfilename(
            title="导出账单",
            defaultextension=".csv",
            initialfile="小猪记账_导出.csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
        )
        if not path:
            # 用户取消
            return

        try:
            # utf-8-sig 让 Excel 正确识别中文
            with open(path, "w", newline="", encoding="utf-8-sig") as fp:
                writer = csv.writer(fp)
                writer.writerow(["日期", "类型", "分类", "备注", "金额", "账户"])
                total_income = 0.0
                total_expense = 0.0
                for r in rows:
                    amount = float(r["amount"])
                    if r["type"] == "收入":
                        total_income += amount
                    else:
                        total_expense += amount
                    writer.writerow([
                        r["date"], r["type"], r["category"], r["note"] or "",
                        "{:.2f}".format(amount),
                        r["account_name"] or "未指定账户",
                    ])
                # 汇总行
                writer.writerow([])
                writer.writerow(["合计收入", "", "", "", "{:.2f}".format(total_income), ""])
                writer.writerow(["合计支出", "", "", "", "{:.2f}".format(total_expense), ""])
                writer.writerow(["结余", "", "", "",
                                 "{:.2f}".format(total_income - total_expense), ""])
        except OSError as exc:
            show_toast(self._tkmaster, "导出失败：{}".format(exc), kind="error")
            return
        except Exception as exc:  # noqa: BLE001 - 兜底保证不崩溃
            show_toast(self._tkmaster, "导出失败：{}".format(exc), kind="error")
            return

        show_toast(self._tkmaster, "已导出 {} 条记录到：{}".format(len(rows), path),
                   kind="success")

    def _current_filter(self):
        """从记账页读取当前筛选条件（保持两页筛选一致）。

        Returns:
            tuple: (month, tx_type, account_id)
        """
        record_page = self.app.pages.get("record")
        if record_page is not None and hasattr(record_page, "_filter_params"):
            try:
                return record_page._filter_params()
            except Exception:  # noqa: BLE001
                pass
        return None, None, None

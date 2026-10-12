# -*- coding: utf-8 -*-
"""main.py —— 小猪记账入口。

职责：
- 创建 Tk root、应用主题背景；
- 初始化数据库（建表 + 默认账户）；
- 构建左侧导航栏 + 右侧内容区（四个页面切换）；
- 右上角小猪吉祥物。

运行：python main.py
打包：pyinstaller --noconfirm --onefile --windowed --name 小猪记账 main.py
"""

import tkinter as tk

import db
import theme
from ui_components import RoundButton, PigCanvas, show_toast
from pages import record, stats, budget, accounts


class PiggyApp:
    """小猪记账主应用。"""

    NAV_ITEMS = [
        ("record", "📝 记账收支"),
        ("stats", "📊 统计图表"),
        ("budget", "🎯 预算管理"),
        ("accounts", "💳 账户导出"),
    ]

    def __init__(self, root):
        """初始化应用。

        Args:
            root: tkinter.Tk 实例。
        """
        self.root = root
        self.pages = {}
        self.nav_buttons = {}
        self._current = None

        self.root.title(theme.APP_TITLE)
        self.root.geometry("1080x720")
        self.root.minsize(960, 640)
        self.root.configure(bg=theme.BG_CREAM)

        # 初始化数据库
        try:
            db.init_db()
        except db.DatabaseError as exc:
            show_toast(self.root, str(exc), kind="error")

        self._build_layout()
        self._build_pages()
        self._build_nav()
        self.show_page("record")

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------
    def _build_layout(self):
        """构建左右分栏骨架。"""
        # 左侧导航栏
        self.nav = tk.Frame(self.root, bg=theme.CARD_WHITE, width=200)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)

        # 导航栏顶部 Logo
        logo = tk.Frame(self.nav, bg=theme.CARD_WHITE)
        logo.pack(fill="x", pady=(20, 10))
        tk.Label(logo, text="🐷", bg=theme.CARD_WHITE, font=theme.font(26)
                 ).pack()
        self.pig_canvas = PigCanvas(logo, width=80, height=72,
                                    bg=theme.CARD_WHITE)
        self.pig_canvas.pack()

        # 右侧内容区
        self.content = tk.Frame(self.root, bg=theme.BG_CREAM)
        self.content.pack(side="left", fill="both", expand=True)

    def _build_pages(self):
        """实例化四个页面（全部创建，切换时 pack/pack_forget）。"""
        self.pages["record"] = record.RecordPage(self.content, self)
        self.pages["stats"] = stats.StatsPage(self.content, self)
        self.pages["budget"] = budget.BudgetPage(self.content, self)
        self.pages["accounts"] = accounts.AccountsPage(self.content, self)

    def _build_nav(self):
        """构建左侧胶囊导航按钮列表。"""
        for key, label in self.NAV_ITEMS:
            btn = RoundButton(
                self.nav, text=label, width=170, height=48,
                bg=theme.CARD_WHITE, fill=theme.CARD_WHITE,
                text_color=theme.TEXT, hover=theme.HOVER_LIGHT,
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(pady=6, padx=14)
            self.nav_buttons[key] = btn

    # ------------------------------------------------------------------
    # 页面切换
    # ------------------------------------------------------------------
    def show_page(self, key):
        """显示指定页面并高亮对应导航按钮。

        Args:
            key: 'record' | 'stats' | 'budget' | 'accounts'。
        """
        if key not in self.pages:
            return
        # 隐藏所有页面
        for page in self.pages.values():
            page.pack_forget()
        page = self.pages[key]
        page.pack(fill="both", expand=True)
        self._current = key

        # 高亮导航
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.set_fill(theme.PRIMARY)
                btn._text_color = theme.WHITE
                btn.set_text(dict(self.NAV_ITEMS)[k])
            else:
                btn.set_fill(theme.CARD_WHITE)
                btn._text_color = theme.TEXT
                btn.set_text(dict(self.NAV_ITEMS)[k])

        # 刷新页面数据
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception:  # noqa: BLE001 - 保证切页不崩
                pass

        # 表情随页面变化（趣味）
        if key == "budget":
            self.pig_canvas.set_mood("happy")
        else:
            self.pig_canvas.set_mood("happy")


def main():
    """程序主入口。"""
    root = tk.Tk()
    PiggyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

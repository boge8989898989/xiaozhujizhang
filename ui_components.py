# -*- coding: utf-8 -*-
"""ui_components.py —— 小猪记账通用自绘 UI 组件。

包含：RoundCard、RoundButton、RoundEntry、CapsuleToggle、PigCanvas、
ProgressBar、ConfirmDialog、Toast、NumberCard。

全部基于 tkinter.Canvas 手绘圆角与投影，去除系统默认灰色外观。
"""

import tkinter as tk
from tkinter import ttk

import theme


# ===========================================================================
# 顶层窗口解析工具（防御性，保证弹窗/Toast 绝不因 master 传错而崩溃）
# ===========================================================================
def resolve_toplevel(master):
    """把任意对象解析为可用的 tkinter 顶层窗口。

    背景：调用方可能误传一个「普通 Python 对象」（如 PiggyApp，它自己没有
    ``.tk`` 属性），也可能传一个 tkinter 控件。直接 ``tk.Toplevel(master)`` 会因
    ``master.tk`` 缺失而抛 ``AttributeError``，导致按钮点击崩溃。

    解析顺序：
    1. ``master`` 本身是 tkinter 控件（有 ``.tk``）→ 取其 ``winfo_toplevel()``；
    2. ``master`` 有 ``root`` 属性且该属性是 tkinter 控件 → 取该 root 的 toplevel；
    3. 退回 ``tkinter._default_root``（若存在且是有效控件）。

    Args:
        master: 任意对象（tkinter 控件 / 应用对象 / None）。

    Returns:
        tkinter.Misc | None: 可用的顶层窗口；无法解析时返回 None。
    """
    # 1) master 本身是 tkinter 控件
    if hasattr(master, "tk"):
        try:
            top = master.winfo_toplevel()
            if top is not None:
                return top
        except tk.TclError:
            return master
        except Exception:  # noqa: BLE001 - 兜底
            return master
    # 2) master 携带 root 属性（如 PiggyApp.root）
    root = getattr(master, "root", None)
    if root is not None and hasattr(root, "tk"):
        try:
            top = root.winfo_toplevel()
            return top if top is not None else root
        except tk.TclError:
            return root
        except Exception:  # noqa: BLE001
            return root
    # 3) 退回默认 root
    try:
        default_root = tk._default_root  # noqa: SLF001 - 官方隐式全局
        if default_root is not None and hasattr(default_root, "tk"):
            return default_root
    except Exception:  # noqa: BLE001
        pass
    return None


# ===========================================================================
# 圆角矩形绘制工具
# ===========================================================================
def draw_round_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """在 Canvas 上绘制圆角矩形（用多边形 + smooth 平滑近似）。

    Args:
        canvas: tkinter.Canvas 实例。
        x1, y1, x2, y2: 矩形外接框坐标。
        radius: 圆角半径（会被自动限制为不超过半边长）。
        **kwargs: 透传给 create_polygon（fill/outline/width/tags 等）。

    Returns:
        int: 多边形 item id。
    """
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


# ===========================================================================
# RoundCard —— 圆角白瓷卡片（带底部投影）
# ===========================================================================
class RoundCard(tk.Frame):
    """圆角卡片容器（自适应内容尺寸）。

    结构：外层 Canvas 负责绘制圆角背景 + 底部投影线，
    内部嵌套一个 tk.Frame（self.body）供调用方放置子控件。

    尺寸策略（关键修复点）：
    - **宽度自适应父容器**：Canvas 以 pack(fill="both", expand=True) 跟随父容器，
      通过 `<Configure>` 事件动态把 body 窗口宽度同步为 ``event.width - 2*pad``，
      因此不再有「写死 860 被 pack 成 848 后右侧被裁 12px」的问题。
    - **高度自适应内容**：默认高度由 ``body.winfo_reqheight() + 2*pad`` 决定，
      内容变化时（子控件新增 / 文本换行）会自动推动卡片变高，底部不再被裁。
    - 兼容旧用法：``height`` 参数仍可显式传入以固定高度（如统计页图表卡），
      ``width`` 参数保留但**仅作为初始宽度提示**，运行时始终以父容器宽度为准。

    注意：尺寸字段命名使用 ``_cw/_ch``，**严禁**改回 ``_w/_h``——那是
    ``tkinter.Misc`` 的保留属性（存放控件 Tcl 窗口路径名，字符串类型），
    覆盖后会导致控件创建失败。
    """

    def __init__(self, master, width=200, height=None, bg=None,
                 fill=None, border=None, shadow=None, radius=None, pad=None, **kw):
        """初始化卡片。

        Args:
            master: 父容器。
            width: 初始宽度（仅作提示，实际宽度随父容器自适应）。
            height: 固定高度；为 None（默认）时高度自适应 body 内容。
            bg: 卡片外部（父）背景色。
            fill: 卡片填充色。
            border: 描边色。
            shadow: 底部投影色。
            radius: 圆角半径。
            pad: 内边距。
        """
        self._outer_bg = bg or theme.BG_CREAM
        self._fill = fill or theme.CARD_WHITE
        self._border = border or theme.CARD_BORDER
        self._shadow = shadow or theme.CARD_SHADOW
        self._radius = radius if radius is not None else theme.RADIUS
        pad = pad if pad is not None else theme.PAD
        super().__init__(master, bg=self._outer_bg, highlightthickness=0, bd=0, **kw)

        # 固定高度（None 表示自适应）；宽度始终自适应父容器。
        self._fixed_height = height
        # 初始尺寸：未被布局前先给一个合理默认，避免闪烁与 1x1。
        self._cw = max(1, int(width))
        self._ch = max(1, int(height)) if height is not None else 1
        self._pad = pad

        self.canvas = tk.Canvas(
            self, width=self._cw, height=self._ch, bg=self._outer_bg,
            highlightthickness=0, bd=0,
        )
        # 让 Canvas 跟随父容器宽度/高度，从而卡片宽度自适应。
        self.canvas.pack(fill="both", expand=True)

        # 主体 Frame 叠放在 Canvas 之上
        self.body = tk.Frame(self.canvas, bg=self._fill, bd=0, highlightthickness=0)
        self._body_window = self.canvas.create_window(
            pad, pad, anchor="nw", window=self.body,
            width=max(1, self._cw - 2 * pad),
            height=max(1, self._ch - 2 * pad) if height is not None else 1,
        )

        # 内容尺寸变化 → 重新计算卡片高度（防抖在回调内比较新旧值）。
        self.body.bind("<Configure>", self._on_body_configure)
        # 卡片自身尺寸变化 → 同步 body 宽度与重绘投影/描边。
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._render()

    # ------------------------------------------------------------------
    # 尺寸同步与重绘
    # ------------------------------------------------------------------
    def _on_canvas_configure(self, event):
        """Canvas（父容器）尺寸变化时同步 body 宽度并重绘背景。

        宽度自适应：body 宽度 = 事件宽度 - 2*pad。
        高度：固定高度时用配置值，否则由 ``_sync_height`` 依内容决定。
        """
        new_w = max(1, int(event.width))
        new_h = max(1, int(event.height))
        changed = (new_w != self._cw or new_h != self._ch)
        self._cw = new_w
        self._ch = new_h
        # 同步 body 宽度（防抖：仅宽度真的变化时才 itemconfigure）
        body_w = max(1, new_w - 2 * self._pad)
        cur = self.canvas.itemcget(self._body_window, "width")
        try:
            cur_w = int(float(cur)) if cur else -1
        except (TypeError, ValueError):
            cur_w = -1
        if cur_w != body_w:
            self.canvas.itemconfigure(self._body_window, width=body_w)
        if self._fixed_height is None:
            # 高度自适应：按内容重新计算（内部同样防抖）
            self._sync_height()
        if changed:
            self._render()

    def _on_body_configure(self, _event=None):
        """body 内容尺寸变化时，按内容更新卡片高度（自适应模式）。"""
        if self._fixed_height is None:
            self._sync_height()

    def _sync_height(self):
        """根据 body 的内容需求高度调整 body 窗口高度（防抖，避免无限重绘）。

        说明：不能以 ``winfo_ismapped()`` 作为前置条件——当 Canvas 高度为 1 时
        body 窗口尚未映射，但其 ``winfo_reqheight()`` 仍能正确反映内容高度。
        循环风险通过「新旧值相等则不设置」的防抖逻辑规避。
        """
        if self._fixed_height is not None:
            return
        try:
            req_h = self.body.winfo_reqheight()
        except tk.TclError:
            return
        if req_h <= 1:
            return
        cur = self.canvas.itemcget(self._body_window, "height")
        try:
            cur_h = int(float(cur)) if cur else -1
        except (TypeError, ValueError):
            cur_h = -1
        if cur_h != req_h:
            self.canvas.itemconfigure(self._body_window, height=req_h)
        # Canvas 高度 = 内容高度 + 上下内边距，卡片随之自然撑高。
        want_ch = req_h + 2 * self._pad
        if want_ch != self._ch:
            self._ch = want_ch
            self.canvas.configure(height=want_ch)
            self._render()

    def _render(self):
        """绘制卡片背景、投影与描边（按当前动态尺寸重绘）。"""
        self.canvas.delete("card_bg")
        if self._cw <= 2 or self._ch <= 2:
            return
        # 底部投影线（先画，位于卡片下方）
        draw_round_rect(
            self.canvas, 1, theme.SHADOW_OFFSET, self._cw - 1, self._ch,
            self._radius, fill=self._shadow, outline=self._shadow, tags="card_bg",
        )
        # 卡片主体
        draw_round_rect(
            self.canvas, 1, 1, self._cw - 1, self._ch - theme.SHADOW_OFFSET,
            self._radius, fill=self._fill, outline=self._border, width=1, tags="card_bg",
        )
        self.canvas.tag_lower("card_bg")

    def resize(self, width, height):
        """手动调整卡片尺寸（固定高度模式）。

        Args:
            width: 目标宽度（仅提示，运行时仍以父容器为准）。
            height: 目标高度；传入后本卡片进入固定高度模式。
        """
        self._fixed_height = height
        self._cw = max(1, int(width))
        self._ch = max(1, int(height))
        self.canvas.configure(width=self._cw, height=self._ch)
        self.canvas.itemconfigure(
            self._body_window,
            width=max(1, self._cw - 2 * self._pad),
            height=max(1, self._ch - 2 * self._pad),
        )
        self._render()


# ===========================================================================
# RoundButton —— 圆角按钮（按下凹陷效果）
# ===========================================================================
class RoundButton(tk.Canvas):
    """自绘圆角按钮，按下时整体下移 3px 且深色边消失。"""

    def __init__(self, master, text="按钮", command=None, width=120, height=40,
                 bg=None, fill=None, text_color=None, hover=None,
                 radius=None, font=None, **kw):
        """初始化按钮。

        Args:
            master: 父容器。
            text: 按钮文字。
            command: 点击回调（无参）。
            width, height: 尺寸。
            bg: 外部背景色。
            fill: 按钮主色。
            text_color: 文字色。
            hover: hover 变色（可空）。
            radius: 圆角。
            font: 字体。
        """
        self._bg = bg or theme.BG_CREAM
        self._fill = fill or theme.PRIMARY
        self._orig_fill = self._fill          # 记录原始色，用于 hover 复位
        self._text_color = text_color or theme.WHITE
        self._hover = hover
        self._radius = radius if radius is not None else theme.RADIUS
        self._text = text
        self._command = command
        # 尺寸字段使用 _cw/_ch，避免覆盖 tkinter.Misc 保留属性 _w/_h。
        self._cw = width
        self._ch = height
        self._font = font or theme.FONT_BODY_BOLD
        self._pressed = False
        super().__init__(master, width=width, height=height + theme.PRESS_OFFSET,
                         bg=self._bg, highlightthickness=0, bd=0, **kw)

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._draw()

    def _draw(self):
        """重绘按钮（正常态有 3px 深色底边，按下态下移并去掉底边）。"""
        self.delete("all")
        offset = theme.PRESS_OFFSET if self._pressed else 0
        top = offset + 1
        # 深色底边（仅非按下态绘制）
        if not self._pressed:
            draw_round_rect(
                self, 1, theme.PRESS_OFFSET, self._cw - 1, self._ch + theme.PRESS_OFFSET,
                self._radius, fill=self._darken(self._fill), outline="",
            )
        # 按钮主体
        draw_round_rect(
            self, 1, top, self._cw - 1, self._ch - theme.PRESS_OFFSET + top,
            self._radius, fill=self._fill, outline="",
        )
        self.create_text(
            self._cw / 2, (top + self._ch - theme.PRESS_OFFSET + top) / 2,
            text=self._text, fill=self._text_color, font=self._font,
        )

    @staticmethod
    def _darken(color):
        """将颜色按比例调暗，用于生成按钮底边阴影色。"""
        try:
            c = color.lstrip("#")
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            r, g, b = int(r * 0.72), int(g * 0.72), int(b * 0.72)
            return "#{:02X}{:02X}{:02X}".format(r, g, b)
        except (ValueError, IndexError):
            return theme.CARD_SHADOW

    def _on_press(self, _event=None):
        self._pressed = True
        self._draw()

    def _on_release(self, event=None):
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        # 仅在指针仍在按钮范围内时触发回调
        if was_pressed and event is not None:
            inside = (0 <= event.x <= self._cw and
                      0 <= event.y <= self._ch + theme.PRESS_OFFSET)
            if inside and callable(self._command):
                self._command()
        elif was_pressed and callable(self._command):
            self._command()

    def _on_enter(self, _event=None):
        if self._hover:
            self._fill = self._hover
            self._draw()

    def _on_leave(self, event=None):
        if self._hover:
            self._fill = self._orig_fill
            self._pressed = False
            self._draw()

    def set_text(self, text):
        """更新按钮文字。"""
        self._text = text
        self._draw()

    def set_fill(self, fill):
        """更新按钮主色（同步更新原始色，保证 hover 复位正确）。"""
        self._fill = fill
        self._orig_fill = fill
        self._draw()


# ===========================================================================
# RoundEntry —— 圆角输入框
# ===========================================================================
class RoundEntry(tk.Frame):
    """自绘圆角背景 + 无边框 Entry 叠加的输入框。"""

    def __init__(self, master, width=220, height=40, bg=None, fill=None,
                 textvariable=None, radius=None, show=None, **kw):
        """初始化输入框。

        Args:
            master: 父容器。
            width, height: 尺寸。
            bg: 外部背景色。
            fill: 输入框背景色。
            textvariable: 绑定变量。
            radius: 圆角。
            show: 密码掩码字符（可空）。
        """
        self._bg = bg or theme.CARD_WHITE
        self._fill = fill or theme.TRACK_BG
        self._radius = radius if radius is not None else theme.RADIUS
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0, **kw)

        self.canvas = tk.Canvas(self, width=width, height=height, bg=self._bg,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        draw_round_rect(self.canvas, 1, 1, width - 1, height - 1,
                        self._radius, fill=self._fill, outline=theme.CARD_BORDER, width=1)

        self.var = textvariable if textvariable is not None else tk.StringVar()
        self.entry = tk.Entry(
            self.canvas, textvariable=self.var, bd=0, relief="flat",
            highlightthickness=0, bg=self._fill, fg=theme.TEXT,
            insertbackground=theme.TEXT, font=theme.FONT_BODY, show=show,
        )
        self.canvas.create_window(width / 2, height / 2, window=self.entry,
                                  width=width - 2 * theme.GAP,
                                  height=height - 8)
        self._entry_window = self.canvas.find_all()[-1]
        # 记录画布与几何尺寸，供禁用态重绘（浅灰视觉区分）使用。
        self._cw = width
        self._ch = height
        self._disabled = False
        self._rect_id = self.canvas.find_all()[0]

    def get(self):
        """获取文本。"""
        try:
            return self.var.get()
        except tk.TclError:
            return ""

    def set(self, value):
        """设置文本。"""
        self.var.set(value)

    def focus_entry(self):
        """聚焦到内部 Entry。"""
        self.entry.focus_set()

    def set_enabled(self, enabled):
        """启用/禁用输入框。

        禁用态：内部 Entry 置为 ``state="disabled"``、文字变浅、背景变浅灰、
        光标形状改为 ``arrow``，让用户一眼看出「不可编辑」。

        Args:
            enabled: True 启用、False 禁用。
        """
        self.set_state("normal" if enabled else "disabled")

    def set_state(self, state):
        """设置输入框状态。

        Args:
            state: ``"normal"``（可编辑）或 ``"disabled"``（只读）。
        """
        is_disabled = (state == "disabled")
        self._disabled = is_disabled
        try:
            self.entry.configure(state="disabled" if is_disabled else "normal",
                                 cursor="arrow" if is_disabled else "xterm")
        except tk.TclError:
            return
        bg = theme.DISABLED_GRAY if is_disabled else self._fill
        fg = theme.TEXT_MUTED if is_disabled else theme.TEXT
        try:
            self.entry.configure(bg=bg, fg=fg)
            self.canvas.itemconfigure(self._rect_id, fill=bg)
        except tk.TclError:
            pass

    def is_enabled(self):
        """返回当前是否可编辑。"""
        return not self._disabled


# ===========================================================================
# ScrollFrame —— 可滚动容器（Canvas + 内嵌 Frame + 垂直滚动条）
# ===========================================================================
class ScrollFrame(tk.Frame):
    """可滚动容器，供账户列表 / 分类预算列表等长列表复用。

    结构：``self``（外层 Frame）内放一个 ``Canvas``（滚动视口）与一个垂直
    ``ttk.Scrollbar``；``Canvas`` 里通过 ``create_window`` 内嵌一个 ``tk.Frame``
    （``self.content``）承载真正的列表内容。内容高度超出视口时出现滚动条，
    可上下滑动；``content`` 宽度始终跟随视口宽度，保证列表项横向填满、不出现
    横向溢出。

    关键实现点：
    - **固定高度模式**（``fixed_height`` 非空）：Canvas 高度被显式设定为该值，
      因此容器高度稳定、不会被内部内容撑开；内容超出时由滚动条解决。
      （预算页/账户页列表区使用此模式。）
    - **自适应模式**（``fixed_height`` 为 None）：Canvas 高度 = 内容高度，
      且上限为 ``max_height``；未超限时无滚动条。为兼容旧账户页行为，
      保留 ``parent_propagate`` 开关（默认 False——为避免递归重绘，仅显式传入
      ``parent_propagate=True`` 时才让外层高度随内容增长）。
    - **滚轮**：绑定在 Canvas 与 content 子控件上（进入区域时才触发），
      不依赖 ``bind_all``，从根本上避免「账户页/预算页两处 ``bind_all``
      互相冲突、后台页面也响应滚轮」的问题。为兼容账户页旧行为（进入页面
      后无需悬停即可滚轮），额外置 ``self.scroller`` 后可调用
      :meth:`attach_wheel_bind_all` 显式使用 ``bind_all``（带解绑跟踪）。

    Args:
        master: 父容器。
        scroller: 宿主页面对象（如 AccountsPage）。提供时会把本实例登记为
            ``scroller.scroll``，并（若宿主提供了旧的 ``_on_mousewheel``）
            保持向后兼容的滚轮回调。
        bg: 背景色（Canvas 与 content 底色）。
        fixed_height: 固定视口高度（px）；None 表示自适应内容高度。
        max_height: 自适应模式下的视口最大高度（px）。
        parent_propagate: 是否让外层 Frame 高度随内容自适应（旧账户页行为）。
        scrollbar_style: 风格名标记。``"default"`` 用系统 ttk 滚动条；
            其它值会尝试套用自定义样式（缺失时静默退回系统风格）。
        **kw: 透传给外层 Frame。
    """

    #: 是否已启用 ``bind_all`` 滚轮（类级，仅用于诊断/测试）。
    _WHEEL_UNIT = 120  # Windows 滚轮一格 delta 值

    def __init__(self, master, scroller=None, bg=None, fixed_height=None,
                 max_height=None, parent_propagate=False,
                 scrollbar_style="default", **kw):
        self._bg = bg or theme.CARD_WHITE
        self._scroller = scroller
        self._fixed_height = fixed_height
        self._max_height = max_height
        self._parent_propagate = bool(parent_propagate)
        # 不使用类级状态，避免多实例互相干扰；登记本实例自身的 bind_all id。
        self._wheel_bind_all_cb = None
        super().__init__(master, bg=self._bg, bd=0, highlightthickness=0, **kw)

        # --- 视口 Canvas ---
        canvas_kw = {
            "bg": self._bg, "highlightthickness": 0, "bd": 0,
        }
        self.canvas = tk.Canvas(self, **canvas_kw)
        if self._fixed_height is not None:
            self.canvas.configure(height=int(self._fixed_height))

        # --- 垂直滚动条（隐藏横向）---
        self.scrollbar = ttk.Scrollbar(self, orient="vertical",
                                       command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # --- 内嵌可滚内容 Frame ---
        self.content = tk.Frame(self.canvas, bg=self._bg)
        self._window_id = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw")

        # 内容尺寸变化 → 同步 scrollregion（并触发自适应高度刷新）。
        self.content.bind("<Configure>", self._on_content_configure)
        # 视口尺寸变化 → 内嵌 Frame 宽度跟随视口；固定高度时保持不变。
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # 滚轮：绑定到 Canvas 与 content（仅进入区域时生效）。
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.content.bind("<MouseWheel>", self._on_mousewheel)

        # 兼容旧账户页：宿主若有 _on_mousewheel，则沿用其 bind_all 行为。
        if self._scroller is not None:
            try:
                setattr(self._scroller, "scroll", self)
            except Exception:  # noqa: BLE001 - 宿主可能是只读对象
                pass
            old_cb = getattr(self._scroller, "_on_mousewheel", None)
            if callable(old_cb):
                self.attach_wheel_bind_all()

    # ------------------------------------------------------------------
    # 尺寸同步
    # ------------------------------------------------------------------
    def _on_content_configure(self, _event=None):
        """内容尺寸变化时同步滚动范围（必要时刷新自适应高度）。"""
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            return
        if self._fixed_height is None:
            self._sync_adaptive_height()

    def _on_canvas_configure(self, event):
        """视口宽度变化时，让内嵌内容宽度跟随视口（防止横向溢出）。"""
        try:
            self.canvas.itemconfigure(self._window_id, width=event.width)
        except tk.TclError:
            return

    def set_fixed_height(self, height):
        """运行时设置固定视口高度（px）。

        用于页面可用空间变化时动态收缩/放大滚动区域，保证容器高度稳定，
        内容超出时由滚动条解决。

        Args:
            height: 目标视口高度（px），会被夹到 >= 1。
        """
        self._fixed_height = max(1, int(height))
        try:
            self.canvas.configure(height=self._fixed_height)
        except tk.TclError:
            pass
        # 高度变化后重新计算滚动范围
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

    def _sync_adaptive_height(self):
        """自适应模式：视口高度 = min(内容高度, max_height)。

        仅在高度确实变化时重设，避免 ``<Configure>`` 递归。
        """
        try:
            req_h = self.content.winfo_reqheight()
        except tk.TclError:
            return
        target = req_h
        if self._max_height is not None:
            target = min(req_h, int(self._max_height))
        target = max(1, int(target))
        try:
            cur = int(self.canvas.cget("height"))
        except (tk.TclError, ValueError):
            cur = -1
        if cur != target:
            self.canvas.configure(height=target)

    # ------------------------------------------------------------------
    # 滚动
    # ------------------------------------------------------------------
    def _on_mousewheel(self, event):
        """鼠标滚轮滚动（Windows 下 ``event.delta`` 为 120 的倍数）。

        优先转交给宿主页面的 ``_on_mousewheel``（保持账户页旧语义），
        否则自行滚动。
        """
        if self._scroller is not None:
            old_cb = getattr(self._scroller, "_on_mousewheel", None)
            if callable(old_cb):
                try:
                    old_cb(event)
                    return
                except tk.TclError:
                    return
        self.scroll_units(-int(event.delta / self._WHEEL_UNIT))

    def scroll_units(self, units):
        """按「行」滚动指定单位数（正数向上，负数向下）。"""
        try:
            self.canvas.yview_scroll(int(units), "units")
        except tk.TclError:
            pass

    def scroll_moveto(self, fraction):
        """滚动到内容指定比例位置（0.0 顶部，1.0 底部）。"""
        try:
            self.canvas.yview_moveto(float(fraction))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # bind_all 兼容（仅账户页旧行为显式启用；销毁时自动解绑）
    # ------------------------------------------------------------------
    def attach_wheel_bind_all(self):
        """使用 ``bind_all`` 绑定滚轮（进入页面即可滚动，无需悬停）。

        会记录绑定的 funcid，``destroy`` 时精确解绑，避免影响其它页面。
        """
        if self._wheel_bind_all_cb is not None:
            return
        self._wheel_bind_all_cb = self._on_mousewheel
        try:
            self.canvas.bind_all("<MouseWheel>", self._wheel_bind_all_cb)
        except tk.TclError:
            self._wheel_bind_all_cb = None

    def destroy(self):
        """销毁时解绑 ``bind_all`` 滚轮，防止其它页面误响应。"""
        if self._wheel_bind_all_cb is not None:
            try:
                self.canvas.unbind_all("<MouseWheel>")
            except tk.TclError:
                pass
            self._wheel_bind_all_cb = None
        super().destroy()


# ===========================================================================
# CapsuleToggle —— 胶囊切换（收入/支出）
# ===========================================================================
class CapsuleToggle(tk.Canvas):
    """胶囊状单选切换控件（如 收入 / 支出）。"""

    def __init__(self, master, options=None, value=None, command=None,
                 width=200, height=40, bg=None, font=None, **kw):
        """初始化切换控件。

        Args:
            master: 父容器。
            options: 选项列表，如 ["支出", "收入"]。
            value: 初始值。
            command: 切换回调（接收新值）。
            width, height: 尺寸。
            bg: 外部背景色。
        """
        # 注意：_options 是 tkinter.Misc 的方法名，_w/_h 是保留属性，均不可覆盖。
        self._opt_list = list(options) if options else ["支出", "收入"]
        self._value = value or self._opt_list[0]
        self._command = command
        self._bg = bg or theme.CARD_WHITE
        self._font = font or theme.FONT_BODY_BOLD
        self._cw = width
        self._ch = height
        self._segments = []
        super().__init__(master, width=width, height=height, bg=self._bg,
                         highlightthickness=0, bd=0, **kw)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _draw(self):
        """绘制胶囊背景与选中高亮。"""
        self.delete("all")
        n = len(self._opt_list)
        seg_w = self._cw / n
        self._segments = []
        # 背景轨道
        draw_round_rect(self, 1, 1, self._cw - 1, self._ch - 1,
                        theme.RADIUS, fill=theme.TRACK_BG, outline="")
        for i, opt in enumerate(self._opt_list):
            x1 = i * seg_w
            x2 = x1 + seg_w
            self._segments.append((x1, x2))
            selected = (opt == self._value)
            if selected:
                draw_round_rect(self, x1 + 3, 3, x2 - 3, self._ch - 3,
                                theme.RADIUS - 3, fill=theme.PRIMARY, outline="")
            color = theme.WHITE if selected else theme.TEXT_MUTED
            self.create_text((x1 + x2) / 2, self._ch / 2, text=opt,
                             fill=color, font=self._font)

    def _on_click(self, event):
        """根据点击 x 坐标确定选中项。"""
        for i, (x1, x2) in enumerate(self._segments):
            if x1 <= event.x <= x2:
                self.set(self._opt_list[i])
                break

    def set(self, value, notify=True):
        """设置当前选中项。"""
        if value in self._opt_list:
            self._value = value
            self._draw()
            if notify and callable(self._command):
                self._command(value)

    def get(self):
        """获取当前选中项。"""
        return self._value


# ===========================================================================
# PigCanvas —— 简笔小猪吉祥物
# ===========================================================================
class PigCanvas(tk.Canvas):
    """Canvas 手绘简笔小猪，支持 开心/平脸/哭 三种表情。"""

    def __init__(self, master, width=90, height=80, bg=None, **kw):
        """初始化小猪。

        Args:
            master: 父容器。
            width, height: 尺寸。
            bg: 背景色。
        """
        self._bg = bg or theme.CARD_WHITE
        # 尺寸字段使用 _cw/_ch：tkinter.Misc 已占用 _w（控件 Tcl 路径名）。
        self._cw = width
        self._ch = height
        self._mood = "happy"
        super().__init__(master, width=width, height=height, bg=self._bg,
                         highlightthickness=0, bd=0, **kw)
        self._draw()

    def set_mood(self, mood):
        """切换表情：'happy' | 'flat' | 'cry'。"""
        if mood in ("happy", "flat", "cry"):
            self._mood = mood
            self._draw()

    def get_mood(self):
        """返回当前表情。"""
        return self._mood

    def _draw(self):
        """绘制小猪身体、耳朵、眼睛、鼻孔与嘴巴。"""
        self.delete("all")
        w, h = self._cw, self._ch
        cx, cy = w / 2, h / 2 + 4
        rx, ry = w * 0.40, h * 0.38

        # 耳朵（两个三角）
        self.create_polygon(cx - rx * 0.7, cy - ry * 0.75,
                            cx - rx * 0.35, cy - ry * 1.35,
                            cx - rx * 0.05, cy - ry * 0.85,
                            fill=theme.PRIMARY, outline=theme.PRIMARY)
        self.create_polygon(cx + rx * 0.7, cy - ry * 0.75,
                            cx + rx * 0.35, cy - ry * 1.35,
                            cx + rx * 0.05, cy - ry * 0.85,
                            fill=theme.PRIMARY, outline=theme.PRIMARY)

        # 身体（粉色椭圆）
        self.create_oval(cx - rx, cy - ry, cx + rx, cy + ry,
                         fill=theme.PRIMARY, outline=theme.PRIMARY)

        # 眼睛（两个黑点）
        self.create_oval(cx - rx * 0.45 - 3, cy - ry * 0.25 - 3,
                         cx - rx * 0.45 + 3, cy - ry * 0.25 + 3,
                         fill=theme.TEXT, outline=theme.TEXT)
        self.create_oval(cx + rx * 0.45 - 3, cy - ry * 0.25 - 3,
                         cx + rx * 0.45 + 3, cy - ry * 0.25 + 3,
                         fill=theme.TEXT, outline=theme.TEXT)

        # 鼻子（椭圆 + 两个鼻孔）
        nose_rx, nose_ry = rx * 0.42, ry * 0.32
        self.create_oval(cx - nose_rx, cy + ry * 0.28 - nose_ry,
                         cx + nose_rx, cy + ry * 0.28 + nose_ry,
                         fill=theme.EXPENSE_PINK, outline=theme.EXPENSE_PINK)
        self.create_oval(cx - nose_rx * 0.45 - 2, cy + ry * 0.28 - 2,
                         cx - nose_rx * 0.45 + 2, cy + ry * 0.28 + 2,
                         fill=theme.TEXT, outline=theme.TEXT)
        self.create_oval(cx + nose_rx * 0.45 - 2, cy + ry * 0.28 - 2,
                         cx + nose_rx * 0.45 + 2, cy + ry * 0.28 + 2,
                         fill=theme.TEXT, outline=theme.TEXT)

        # 腮红
        self.create_oval(cx - rx * 0.85, cy + ry * 0.05,
                         cx - rx * 0.55, cy + ry * 0.35,
                         fill=theme.SECONDARY, outline="")
        self.create_oval(cx + rx * 0.55, cy + ry * 0.05,
                         cx + rx * 0.85, cy + ry * 0.35,
                         fill=theme.SECONDARY, outline="")

        # 嘴巴（随表情变化）
        mx = cx
        my = cy + ry * 0.95
        if self._mood == "happy":
            self.create_arc(mx - rx * 0.35, my - ry * 0.28,
                            mx + rx * 0.35, my + ry * 0.28,
                            start=200, extent=140, style="arc",
                            outline=theme.TEXT, width=2)
        elif self._mood == "flat":
            self.create_line(mx - rx * 0.30, my, mx + rx * 0.30, my,
                             fill=theme.TEXT, width=2)
        else:  # cry
            self.create_arc(mx - rx * 0.35, my - ry * 0.05,
                            mx + rx * 0.35, my + ry * 0.50,
                            start=20, extent=140, style="arc",
                            outline=theme.TEXT, width=2)
            # 眼泪
            self.create_oval(cx - rx * 0.45 - 2, cy + ry * 0.05,
                             cx - rx * 0.45 + 2, cy + ry * 0.30,
                             fill="#8FB8E8", outline="")


# ===========================================================================
# ProgressBar —— 圆角进度条（内嵌会走动的小猪头）
# ===========================================================================
class ProgressBar(tk.Canvas):
    """横向圆角进度条，进度越大内部小猪头越靠右。"""

    def __init__(self, master, width=420, height=48, bg=None, **kw):
        """初始化进度条。

        Args:
            master: 父容器。
            width, height: 尺寸。
            bg: 背景色。
        """
        self._bg = bg or theme.CARD_WHITE
        # 尺寸字段使用 _cw/_ch，避免覆盖 tkinter.Misc 保留属性 _w/_h。
        self._cw = width
        self._ch = height
        self._pct = 0.0
        self._bar_color = theme.INCOME_GREEN
        self._mood = "happy"
        super().__init__(master, width=width, height=height, bg=self._bg,
                         highlightthickness=0, bd=0, **kw)

    def set_value(self, pct, color=None, mood=None):
        """设置进度（0~1 以上均可，内部会 clamp 显示）与状态。

        Args:
            pct: 进度比例（>1 表示超支）。
            color: 填充色（可空）。
            mood: 小猪表情（可空）。
        """
        self._pct = float(pct) if pct else 0.0
        if color:
            self._bar_color = color
        if mood:
            self._mood = mood
        self._draw()

    def _draw(self):
        """绘制轨道、填充、小猪头与百分比文字。"""
        self.delete("all")
        pad = 6
        bar_h = self._ch - 2 * pad
        # 轨道
        draw_round_rect(self, pad, pad, self._cw - pad, pad + bar_h,
                        bar_h / 2, fill=theme.TRACK_BG, outline="")
        # 填充（clamp 到 1.0）
        frac = max(0.0, min(self._pct, 1.0))
        fill_w = (self._cw - 2 * pad) * frac
        if fill_w > 2:
            draw_round_rect(self, pad, pad, pad + fill_w, pad + bar_h,
                            bar_h / 2, fill=self._bar_color, outline="")
        # 小猪头位置
        head_x = pad + max(bar_h / 2, min(fill_w, self._cw - 2 * pad - bar_h / 2))
        head_y = pad + bar_h / 2
        self._draw_pig_head(head_x, head_y, bar_h / 2)

        # 百分比文字（居中）
        pct_text = "{:.0f}%".format(self._pct * 100)
        self.create_text(self._cw / 2, pad + bar_h / 2, text=pct_text,
                         fill=theme.WHITE, font=theme.FONT_BODY_BOLD)

    def _draw_pig_head(self, cx, cy, r):
        """在 (cx, cy) 处画一个小猪头。"""
        # 头
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         fill=theme.PRIMARY, outline=theme.WHITE, width=2)
        # 耳朵
        self.create_polygon(cx - r * 0.55, cy - r * 0.55,
                            cx - r * 0.25, cy - r * 1.05,
                            cx + r * 0.05, cy - r * 0.65,
                            fill=theme.PRIMARY, outline=theme.WHITE, width=1)
        # 眼睛
        eye = max(1.5, r * 0.14)
        self.create_oval(cx - r * 0.35 - eye, cy - eye,
                         cx - r * 0.35 + eye, cy + eye,
                         fill=theme.TEXT, outline=theme.TEXT)
        self.create_oval(cx + r * 0.05 - eye, cy - eye,
                         cx + r * 0.05 + eye, cy + eye,
                         fill=theme.TEXT, outline=theme.TEXT)
        # 鼻子
        self.create_oval(cx + r * 0.05, cy + r * 0.15,
                         cx + r * 0.55, cy + r * 0.55,
                         fill=theme.EXPENSE_PINK, outline=theme.WHITE, width=1)


# ===========================================================================
# NumberCard —— 数字卡片（收入/支出/结余）
# ===========================================================================
class NumberCard(tk.Frame):
    """展示一个金额数字的卡片（标题 + 大号金额）。"""

    def __init__(self, master, title="标题", value=0.0, color=None,
                 width=180, height=110, bg=None, **kw):
        """初始化数字卡片。

        Args:
            master: 父容器。
            title: 卡标题。
            value: 金额。
            color: 金额颜色。
            width: 宽度提示（实际随父容器/内容自适应）。
            height: 高度提示（实际随内容自适应）。
        """
        self._bg = bg or theme.BG_CREAM
        super().__init__(master, bg=self._bg, highlightthickness=0, bd=0, **kw)
        # 尺寸字段统一使用 _cw/_ch（避免 tkinter.Misc 保留属性 _w/_h）。
        self._cw = width
        self._ch = height
        # 卡片宽度自适应父容器；高度按内容自适应，避免金额被裁。
        self._card = RoundCard(self, width=width, bg=self._bg)
        self._card.pack(fill="both", expand=True)
        self._title_label = tk.Label(
            self._card.body, text=title, bg=theme.CARD_WHITE,
            fg=theme.TEXT_MUTED, font=theme.FONT_BODY,
        )
        self._title_label.pack(anchor="w", pady=(6, 2))
        self._value_label = tk.Label(
            self._card.body, text=theme.fmt_money(value), bg=theme.CARD_WHITE,
            fg=color or theme.TEXT, font=theme.FONT_MONEY,
        )
        self._value_label.pack(anchor="w")

    def set_value(self, value, color=None):
        """更新金额显示。"""
        self._value_label.configure(text=theme.fmt_money(value))
        if color:
            self._value_label.configure(fg=color)


# ===========================================================================
# ConfirmDialog —— 可爱风格自绘确认框
# ===========================================================================
class ConfirmDialog(tk.Toplevel):
    """自绘圆角确认弹窗，支持 Esc/Enter 快捷响应。

    关键健壮性：``master`` 可能被误传为普通应用对象（无 ``.tk``）。构造时用
    :func:`resolve_toplevel` 解析出真正的 tkinter 顶层窗口，解析失败则优雅降级
    （不抛异常），保证「按钮点击因弹窗失败而崩溃」的情况不再发生。
    """

    def __init__(self, master, title="确认", message="确定要操作吗？",
                 ok_text="确定", cancel_text="取消", on_ok=None):
        """初始化确认框。

        Args:
            master: 父窗口（tkinter 控件或携带 root 的应用对象）。
            title: 标题。
            message: 提示正文。
            ok_text: 确认按钮文字。
            cancel_text: 取消按钮文字。
            on_ok: 确认回调。
        """
        parent = resolve_toplevel(master)
        if parent is None:
            # 无法解析出可用窗口：直接构造一个独立 Toplevel（用默认 root）；
            # 若连默认 root 都没有（极少见），则放弃弹窗，静默返回。
            parent = tk._default_root  # noqa: SLF001
        if parent is None:
            self._failed = True
            self._on_ok = on_ok
            return
        self._failed = False
        super().__init__(parent)
        self._on_ok = on_ok
        self._parent = parent
        self.configure(bg=theme.BG_CREAM)
        self.title(title)
        self.resizable(False, False)
        try:
            self.transient(parent)
        except tk.TclError:
            pass
        self._build(title, message, ok_text, cancel_text)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.bind("<Return>", lambda e: self._on_ok_clicked())
        self._center(parent)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()

    def _build(self, title, message, ok_text, cancel_text):
        """构建弹窗内容（卡片高度自适应文本长度）。"""
        card = RoundCard(self, width=theme.DIALOG_WIDTH, bg=theme.BG_CREAM)
        card.pack(padx=theme.GAP, pady=theme.GAP, fill="both", expand=True)
        body = card.body

        tk.Label(body, text=title, bg=theme.CARD_WHITE, fg=theme.PRIMARY,
                 font=theme.FONT_SUBTITLE).pack(anchor="w", pady=(6, 6))
        tk.Label(body, text=message, bg=theme.CARD_WHITE, fg=theme.TEXT,
                 font=theme.FONT_BODY, wraplength=theme.DIALOG_WIDTH - 2 * theme.PAD - 20,
                 justify="left").pack(anchor="w")

        btn_row = tk.Frame(body, bg=theme.CARD_WHITE)
        btn_row.pack(side="bottom", fill="x", pady=(12, 4))
        RoundButton(btn_row, text=cancel_text, command=self._on_cancel,
                    width=100, height=36, bg=theme.CARD_WHITE,
                    fill=theme.TRACK_BG, text_color=theme.TEXT,
                    hover=theme.HOVER_LIGHT).pack(side="left", expand=True)
        RoundButton(btn_row, text=ok_text, command=self._on_ok_clicked,
                    width=100, height=36, bg=theme.CARD_WHITE,
                    fill=theme.PRIMARY, hover=theme.HOVER_LIGHT
                    ).pack(side="right", expand=True)

    def _on_ok_clicked(self):
        """确认：先关闭再回调（弹窗构造失败时直接回调）。"""
        if getattr(self, "_failed", False):
            cb = self._on_ok
            if callable(cb):
                cb()
            return
        cb = self._on_ok
        try:
            self.destroy()
        except tk.TclError:
            pass
        if callable(cb):
            cb()

    def _on_cancel(self):
        """取消：直接关闭。"""
        if getattr(self, "_failed", False):
            return
        try:
            self.destroy()
        except tk.TclError:
            pass

    def _center(self, master):
        """相对父窗口居中。"""
        self.update_idletasks()
        try:
            mw, mh = master.winfo_width(), master.winfo_height()
            mx, my = master.winfo_rootx(), master.winfo_rooty()
            w, h = self.winfo_width(), self.winfo_height()
            x = mx + max(0, (mw - w) // 2)
            y = my + max(0, (mh - h) // 2)
            self.geometry("+{}+{}".format(x, y))
        except tk.TclError:
            pass


# ===========================================================================
# Toast —— 轻量提示（自动消失）
# ===========================================================================
class Toast:
    """在父窗口顶部中央弹出的轻量提示条，2 秒后自动消失。

    关键健壮性：``master`` 可能被误传为普通应用对象（无 ``.tk``）。构造时用
    :func:`resolve_toplevel` 解析出真正的顶层窗口；解析失败则直接放弃显示、
    静默返回（绝不抛异常，保证任何按钮点击都不会因提示条而崩溃）。
    """

    def __init__(self, master, message, kind="info", duration=2200):
        """显示提示。

        Args:
            master: 父窗口（tkinter 控件或携带 root 的应用对象）。
            message: 提示文字。
            kind: 'info' | 'success' | 'error' | 'warn'。
            duration: 停留毫秒数。
        """
        self.master = master
        self.shown = False
        parent = resolve_toplevel(master)
        if parent is None:
            return  # 无法解析窗口：放弃显示，绝不崩溃
        color_map = {
            "info": theme.ACCENT,
            "success": theme.INCOME_GREEN,
            "error": theme.DANGER_RED,
            "warn": theme.WARN_YELLOW,
        }
        fill = color_map.get(kind, theme.ACCENT)
        try:
            top = tk.Toplevel(parent)
        except tk.TclError:
            return
        top.overrideredirect(True)
        top.configure(bg=theme.BG_CREAM)
        text = str(message)
        width = max(220, min(560, 14 * len(text) + 60))
        canvas = tk.Canvas(top, width=width, height=52, bg=theme.BG_CREAM,
                           highlightthickness=0, bd=0)
        canvas.pack()
        draw_round_rect(canvas, 1, 1, width - 1, 51, theme.RADIUS,
                        fill=fill, outline="")
        canvas.create_text(width / 2, 26, text=text, fill=theme.WHITE,
                           font=theme.FONT_BODY_BOLD)
        self._position(parent, top, width, 52)
        top.after(int(duration), self._safe_destroy, top)
        self.shown = True

    @staticmethod
    def _position(master, top, width, height):
        """把提示条放到父窗口顶部居中。"""
        try:
            master.update_idletasks()
            mx = master.winfo_rootx()
            my = master.winfo_rooty()
            mw = master.winfo_width()
            x = mx + max(0, (mw - width) // 2)
            y = my + 16
            top.geometry("+{}+{}".format(x, y))
        except tk.TclError:
            pass

    @staticmethod
    def _safe_destroy(top):
        """安全销毁提示窗口。"""
        try:
            top.destroy()
        except tk.TclError:
            pass


def show_toast(master, message, kind="info"):
    """便捷函数：显示一条 Toast（绝不抛异常）。

    Args:
        master: 父窗口（tkinter 控件或携带 root 的应用对象）。
        message: 提示文字。
        kind: 'info' | 'success' | 'error' | 'warn'。

    Returns:
        Toast | None: Toast 实例；构造失败返回 None。
    """
    try:
        return Toast(master, message, kind=kind)
    except Exception:  # noqa: BLE001 - 提示条失败绝不影响主流程
        return None


def ask_confirm(master, title, message, on_ok, ok_text="确定", cancel_text="取消"):
    """便捷函数：弹出自绘确认框（绝不抛异常）。

    Args:
        master: 父窗口（tkinter 控件或携带 root 的应用对象）。
        title: 标题。
        message: 提示正文。
        on_ok: 确认回调。
        ok_text: 确认按钮文字。
        cancel_text: 取消按钮文字。

    Returns:
        ConfirmDialog | None: 弹窗实例；构造失败返回 None。
    """
    try:
        return ConfirmDialog(master, title=title, message=message,
                             ok_text=ok_text, cancel_text=cancel_text, on_ok=on_ok)
    except Exception:  # noqa: BLE001 - 弹窗失败绝不影响主流程
        return None

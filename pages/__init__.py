# -*- coding: utf-8 -*-
"""pages 包：小猪记账的四个功能页面。

- record  记账收支
- stats   统计图表
- budget  预算管理
- accounts 多账户与导出
"""

from . import record  # noqa: F401
from . import stats  # noqa: F401
from . import budget  # noqa: F401
from . import accounts  # noqa: F401

__all__ = ["record", "stats", "budget", "accounts"]

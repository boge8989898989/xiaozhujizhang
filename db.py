# -*- coding: utf-8 -*-
"""db.py —— 小猪记账数据库层。

职责：
- 连接管理（单文件 exe 场景下把 piggy.db 放在 exe 同目录）。
- 建表 + 索引 + 默认数据。
- transactions / accounts / budgets 的 CRUD。
- 统计查询（按月汇总、分类占比、近 N 月趋势）。
- 账户余额联动（保存交易时增删余额、删除交易时反向回滚），全部使用事务。

所有对外函数在捕获 sqlite3.Error 后抛出统一的 DatabaseError，供上层 UI 友好提示。
"""

import os
import sys
import sqlite3

# ---------------------------------------------------------------------------
# 数据库文件路径
# ---------------------------------------------------------------------------
DB_PATH = ""  # 由 _resolve_db_path() 在导入时初始化


def _resolve_db_path():
    """确定数据库文件路径。

    规则：
    - PyInstaller 打包后（sys.frozen 为真）：取 exe 所在目录，保证数据持久化；
    - 否则：取本文件（db.py）所在目录。

    Returns:
        str: piggy.db 的绝对路径。
    """
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "piggy.db")


DB_PATH = _resolve_db_path()


class DatabaseError(Exception):
    """数据库操作异常（上层可捕获并弹出友好中文提示）。"""


# ---------------------------------------------------------------------------
# 连接管理
# ---------------------------------------------------------------------------
def get_connection():
    """创建并返回一个新的 sqlite3 连接。

    - 使用 check_same_thread=False 以便从 tkinter 主线程安全使用；
    - row_factory 设为 sqlite3.Row，便于按列名取值。

    Returns:
        sqlite3.Connection
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as exc:  # pragma: no cover - 连接失败极少见
        raise DatabaseError("连接数据库失败：{}".format(exc)) from exc


# ---------------------------------------------------------------------------
# 建表
# ---------------------------------------------------------------------------
def init_db():
    """初始化数据库：建表、建索引、无账户时插入默认账户「现金」。

    Returns:
        None
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # 账户表
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL,
                type    TEXT    NOT NULL DEFAULT '现金',
                balance REAL    NOT NULL DEFAULT 0
            )
            """
        )

        # 交易表（account_id 关联 accounts.id，删除账户时置空）
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                type       TEXT    NOT NULL,              -- '收入' 或 '支出'
                amount     REAL    NOT NULL,
                category   TEXT    NOT NULL,
                note       TEXT    NOT NULL DEFAULT '',
                date       TEXT    NOT NULL,              -- 'YYYY-MM-DD'
                account_id INTEGER,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL
            )
            """
        )

        # 预算表（month 'YYYY-MM'，category 为 'TOTAL' 或具体分类名）
        # account_id：0 表示「全局/全部账户」预算；> 0 表示具体账户预算。
        # 采用 0 而非 NULL 作为全局标记——SQLite 的 UNIQUE 索引不会对 NULL 去重，
        # 用 NULL 会导致 (month, category, NULL) 可重复插入，故统一用 0。
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                month      TEXT    NOT NULL,
                category   TEXT    NOT NULL,
                amount     REAL    NOT NULL DEFAULT 0,
                account_id INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        # 索引与唯一约束
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account_id)")

        # ------------------------------------------------------------------
        # 迁移：老库的 budgets 表没有 account_id 列，需 ALTER TABLE 补列。
        # 迁移后老数据的 account_id 默认 0（即视为「全局预算」），数据不丢失。
        # ------------------------------------------------------------------
        _migrate_budgets_account_column(conn, cur)

        # 唯一索引改为 (month, category, account_id)：同一预算维度只允许一行，
        # set_budget 使用 ON CONFLICT 依赖此索引实现 upsert。
        # 注意：需先删旧索引再建新索引（老索引列数不同，IF NOT EXISTS 不会替换）。
        cur.execute("DROP INDEX IF EXISTS idx_budget_month_cat")
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_budget_month_cat_acc "
            "ON budgets(month, category, account_id)"
        )

        conn.commit()

        # 若无账户，插入默认账户「现金」
        cur.execute("SELECT COUNT(*) AS c FROM accounts")
        row = cur.fetchone()
        if row is not None and int(row["c"]) == 0:
            cur.execute(
                "INSERT INTO accounts(name, type, balance) VALUES (?, ?, ?)",
                ("现金", "现金", 0.0),
            )
            conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError("初始化数据库失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def _migrate_budgets_account_column(conn, cur):
    """迁移 budgets 表：确保存在 account_id 列（老库平滑升级）。

    逻辑：
    - 读取 ``PRAGMA table_info(budgets)`` 判断列是否存在；
    - 不存在则 ``ALTER TABLE budgets ADD COLUMN account_id INTEGER NOT NULL DEFAULT 0``；
    - 老数据的 account_id 自动填 0，即视为「全局预算」，数据完整保留。

    Args:
        conn: 已打开的 sqlite3.Connection。
        cur: 该连接上的 cursor。

    Returns:
        bool: True 表示本次执行了加列，False 表示列已存在（无需迁移）。
    """
    cur.execute("PRAGMA table_info(budgets)")
    columns = {row[1] for row in cur.fetchall()}
    if "account_id" in columns:
        return False
    cur.execute(
        "ALTER TABLE budgets ADD COLUMN account_id INTEGER NOT NULL DEFAULT 0"
    )
    return True
def list_accounts():
    """列出所有账户（按 id 升序）。

    Returns:
        list[sqlite3.Row]: 每行含 id/name/type/balance。
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.execute("SELECT id, name, type, balance FROM accounts ORDER BY id")
        return cur.fetchall()
    except sqlite3.Error as exc:
        raise DatabaseError("读取账户失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def get_account(account_id):
    """按 id 读取单个账户。

    Returns:
        sqlite3.Row | None
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.execute(
            "SELECT id, name, type, balance FROM accounts WHERE id = ?", (account_id,)
        )
        return cur.fetchone()
    except sqlite3.Error as exc:
        raise DatabaseError("读取账户失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def add_account(name, acc_type, balance=0.0):
    """新增账户。

    Returns:
        int: 新账户 id。
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO accounts(name, type, balance) VALUES (?, ?, ?)",
            (str(name), str(acc_type), float(balance)),
        )
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.Error as exc:
        raise DatabaseError("新增账户失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def update_account(account_id, name, acc_type, balance):
    """更新账户信息（含余额）。

    Returns:
        None
    """
    conn = None
    try:
        conn = get_connection()
        conn.execute(
            "UPDATE accounts SET name = ?, type = ?, balance = ? WHERE id = ?",
            (str(name), str(acc_type), float(balance), int(account_id)),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError("更新账户失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def count_transactions_by_account(account_id):
    """统计某账户名下的记账记录条数（用于删除账户前的确认提示）。

    Args:
        account_id: 账户 id。

    Returns:
        int: 该账户名下的交易条数；account_id 非法或 None 时返回 0。
    """
    conn = None
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE account_id = ?",
            (int(account_id),),
        ).fetchone()
        return int(row["c"]) if row is not None else 0
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise DatabaseError("统计账户记录失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def delete_account_cascade(account_id):
    """级联删除账户：在同一事务内先删该账户的所有交易，再删账户本身。

    说明：
    - transactions.account_id 外键为 ``ON DELETE SET NULL``，若先删账户会把
      交易的 account_id 置为 NULL（变成「未指定账户」）而不是删除记录；
      因此这里**必须先删 transactions 再删 accounts**，才能真正级联清除。
    - 账户本身被删除，故**不需要**回滚余额（不存在已删除的账户可更新）。
    - 全过程使用单一连接/事务，任一步失败则 ``rollback()``，保证数据一致。

    Args:
        account_id: 账户 id。

    Returns:
        int: 被级联删除的交易条数。
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        # 1) 先统计并删除该账户名下的所有交易（避免外键 SET NULL 干扰）
        cur.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE account_id = ?",
            (int(account_id),),
        )
        row = cur.fetchone()
        removed = int(row["c"]) if row is not None else 0
        cur.execute(
            "DELETE FROM transactions WHERE account_id = ?", (int(account_id),)
        )
        # 2) 再删除账户本身
        cur.execute("DELETE FROM accounts WHERE id = ?", (int(account_id),))
        conn.commit()
        return removed
    except sqlite3.Error as exc:
        if conn is not None:
            conn.rollback()
        raise DatabaseError("删除账户失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def delete_account(account_id):
    """删除账户（兼容旧调用：转发到级联删除，连同名下记账记录一并删除）。

    历史上此函数仅删除账户、把交易 account_id 置空；现按产品需求改为级联删除，
    保留本函数名以避免破坏既有调用点。

    Args:
        account_id: 账户 id。

    Returns:
        int: 被级联删除的交易条数。
    """
    return delete_account_cascade(account_id)


def adjust_account_balance(conn, account_id, delta):
    """在已有事务连接内调整账户余额（内部使用，不单独提交）。

    Args:
        conn: 已打开的 sqlite3.Connection。
        account_id: 账户 id（可为 None，则忽略）。
        delta: 余额变化量（收入为正、支出为负）。
    """
    if account_id is None:
        return
    conn.execute(
        "UPDATE accounts SET balance = balance + ? WHERE id = ?",
        (float(delta), int(account_id)),
    )


# ---------------------------------------------------------------------------
# 交易 CRUD（含账户余额联动）
# ---------------------------------------------------------------------------
def add_transaction(tx_type, amount, category, note, date, account_id):
    """新增交易并联动更新账户余额。

    支出：balance 减少；收入：balance 增加。使用事务保证一致性。

    Returns:
        int: 新交易 id。
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO transactions(type, amount, category, note, date, account_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(tx_type),
                float(amount),
                str(category),
                str(note),
                str(date),
                None if account_id is None else int(account_id),
            ),
        )
        new_id = int(cur.lastrowid)
        # 余额联动：支出为负、收入为正
        delta = float(amount) if tx_type == "收入" else -float(amount)
        adjust_account_balance(conn, account_id, delta)
        conn.commit()
        return new_id
    except sqlite3.Error as exc:
        if conn is not None:
            conn.rollback()
        raise DatabaseError("保存交易失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def delete_transaction(tx_id):
    """删除交易并反向回滚账户余额。

    Returns:
        None
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        # 先查出被删交易，用于余额回滚
        cur.execute(
            "SELECT type, amount, account_id FROM transactions WHERE id = ?",
            (int(tx_id),),
        )
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            return
        # 反向回滚：原支出则加回，原收入则扣回
        delta = -float(row["amount"]) if row["type"] == "收入" else float(row["amount"])
        adjust_account_balance(conn, row["account_id"], delta)
        cur.execute("DELETE FROM transactions WHERE id = ?", (int(tx_id),))
        conn.commit()
    except sqlite3.Error as exc:
        if conn is not None:
            conn.rollback()
        raise DatabaseError("删除交易失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def list_transactions(month=None, tx_type=None, account_id=None, limit=None):
    """按条件查询交易列表（默认按日期倒序、id 倒序）。

    Args:
        month: 'YYYY-MM'，按月份筛选（可空）。
        tx_type: '收入' / '支出'（可空）。
        account_id: 账户 id（可空）。
        limit: 最多返回条数（可空）。

    Returns:
        list[sqlite3.Row]: 含 id/type/amount/category/note/date/account_id/account_name。
    """
    conn = None
    try:
        conn = get_connection()
        sql = (
            "SELECT t.id, t.type, t.amount, t.category, t.note, t.date, t.account_id, "
            "a.name AS account_name "
            "FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id WHERE 1=1"
        )
        params = []
        if month:
            sql += " AND substr(t.date, 1, 7) = ?"
            params.append(str(month))
        if tx_type:
            sql += " AND t.type = ?"
            params.append(str(tx_type))
        if account_id is not None:
            sql += " AND t.account_id = ?"
            params.append(int(account_id))
        sql += " ORDER BY t.date DESC, t.id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        cur = conn.execute(sql, params)
        return cur.fetchall()
    except sqlite3.Error as exc:
        raise DatabaseError("查询交易失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# 统计查询
# ---------------------------------------------------------------------------
def month_summary(month, account_id=None):
    """统计某月的收入、支出、结余（可按账户过滤）。

    Args:
        month: 'YYYY-MM'。
        account_id: 账户 id；None 表示统计全部账户（含 account_id 为 NULL 的
            未指定账户交易）。

    Returns:
        dict: {'income': float, 'expense': float, 'balance': float}
    """
    conn = None
    try:
        conn = get_connection()
        sql = (
            """
            SELECT
                COALESCE(SUM(CASE WHEN type='收入' THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN type='支出' THEN amount ELSE 0 END), 0) AS expense
            FROM transactions WHERE substr(date, 1, 7) = ?
            """
        )
        params = [str(month)]
        if account_id is not None:
            # 仅统计指定账户（不含 NULL）
            sql += " AND account_id = ?"
            params.append(int(account_id))
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        income = float(row["income"]) if row else 0.0
        expense = float(row["expense"]) if row else 0.0
        return {"income": income, "expense": expense, "balance": income - expense}
    except sqlite3.Error as exc:
        raise DatabaseError("统计本月数据失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def category_breakdown(month, tx_type="支出", account_id=None):
    """统计某月某类型（默认支出）下各分类的金额与占比（可按账户过滤）。

    Args:
        month: 'YYYY-MM'。
        tx_type: '收入' / '支出'。
        account_id: 账户 id；None 表示全部账户。

    Returns:
        list[dict]: [{'category': str, 'amount': float, 'ratio': float}]，按金额降序。
    """
    conn = None
    try:
        conn = get_connection()
        sql = (
            """
            SELECT category, COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE substr(date, 1, 7) = ? AND type = ?
            """
        )
        params = [str(month), str(tx_type)]
        if account_id is not None:
            sql += " AND account_id = ?"
            params.append(int(account_id))
        sql += " GROUP BY category ORDER BY total DESC"
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        grand = sum(float(r["total"]) for r in rows)
        result = []
        for r in rows:
            amt = float(r["total"])
            result.append(
                {
                    "category": r["category"],
                    "amount": amt,
                    "ratio": (amt / grand) if grand > 0 else 0.0,
                }
            )
        return result
    except sqlite3.Error as exc:
        raise DatabaseError("统计分类占比失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def month_trend(num_months, end_month, account_id=None):
    """统计以 end_month 结尾的最近 num_months 个月收支趋势（可按账户过滤）。

    Args:
        num_months: 月份数量（如 6）。
        end_month: 'YYYY-MM'，序列末尾月份。
        account_id: 账户 id；None 表示全部账户。

    Returns:
        list[dict]: [{'month': 'YYYY-MM', 'income': float, 'expense': float}]，按时间升序。
    """
    months = _recent_months(end_month, num_months)
    conn = None
    try:
        conn = get_connection()
        sql = (
            """
            SELECT
                COALESCE(SUM(CASE WHEN type='收入' THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN type='支出' THEN amount ELSE 0 END), 0) AS expense
            FROM transactions WHERE substr(date, 1, 7) = ?
            """
        )
        result = []
        for m in months:
            params = [m]
            sql_m = sql
            if account_id is not None:
                sql_m += " AND account_id = ?"
                params.append(int(account_id))
            row = conn.execute(sql_m, params).fetchone()
            result.append(
                {
                    "month": m,
                    "income": float(row["income"]) if row else 0.0,
                    "expense": float(row["expense"]) if row else 0.0,
                }
            )
        return result
    except sqlite3.Error as exc:
        raise DatabaseError("统计趋势失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def monthly_category_spend(month, category, account_id=None):
    """统计某月某分类的支出总额（用于分类预算进度，可按账户过滤）。

    Args:
        month: 'YYYY-MM'。
        category: 分类名。
        account_id: 账户 id；None 表示全部账户。

    Returns:
        float
    """
    conn = None
    try:
        conn = get_connection()
        sql = (
            """
            SELECT COALESCE(SUM(amount), 0) AS total FROM transactions
            WHERE substr(date, 1, 7) = ? AND type = '支出' AND category = ?
            """
        )
        params = [str(month), str(category)]
        if account_id is not None:
            sql += " AND account_id = ?"
            params.append(int(account_id))
        row = conn.execute(sql, params).fetchone()
        return float(row["total"]) if row else 0.0
    except sqlite3.Error as exc:
        raise DatabaseError("统计分类支出失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def _recent_months(end_month, count):
    """生成最近 count 个月的 'YYYY-MM' 列表（含 end_month，升序）。

    Args:
        end_month: 'YYYY-MM'。
        count: 数量。

    Returns:
        list[str]
    """
    try:
        year, mon = str(end_month).split("-")
        year = int(year)
        mon = int(mon)
    except (ValueError, AttributeError):
        import datetime

        today = datetime.date.today()
        year, mon = today.year, today.month

    months = []
    for _ in range(int(count)):
        months.append("{:04d}-{:02d}".format(year, mon))
        mon -= 1
        if mon == 0:
            mon = 12
            year -= 1
    months.reverse()
    return months


# ---------------------------------------------------------------------------
# 预算 CRUD
# ---------------------------------------------------------------------------
#: 账户维度的「全局」预算标记值（0 表示「全部账户」预算）。
#: 用 0 而非 NULL 是为了让 UNIQUE(month, category, account_id) 索引生效。
BUDGET_GLOBAL_ACCOUNT = 0


def _normalize_budget_account(account_id):
    """把预算的 account_id 归一化为整数：None → 0（全局）。

    Args:
        account_id: int | None。

    Returns:
        int: 归一化后的账户 id（0 表示全局）。
    """
    if account_id is None:
        return BUDGET_GLOBAL_ACCOUNT
    try:
        return int(account_id)
    except (TypeError, ValueError):
        return BUDGET_GLOBAL_ACCOUNT


def set_budget(month, category, amount, account_id=None):
    """设置/更新预算（同 month+category+account_id 存在则更新，否则插入）。

    依赖 UNIQUE(month, category, account_id) 唯一索引实现 upsert，
    同维度二次调用为「更新」而非重复插入。

    Args:
        month: 'YYYY-MM'。
        category: 'TOTAL' 或分类名。
        amount: 预算金额。
        account_id: 账户 id；None/0 表示「全局/全部账户」预算。

    Returns:
        None
    """
    conn = None
    try:
        conn = get_connection()
        acc = _normalize_budget_account(account_id)
        conn.execute(
            """
            INSERT INTO budgets(month, category, amount, account_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(month, category, account_id)
            DO UPDATE SET amount = excluded.amount
            """,
            (str(month), str(category), float(amount), acc),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError("保存预算失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def get_budget(month, category, account_id=None):
    """读取某月某分类某账户的预算金额，不存在返回 0.0。

    Args:
        month: 'YYYY-MM'。
        category: 'TOTAL' 或分类名。
        account_id: 账户 id；None/0 表示「全局」预算。

    Returns:
        float
    """
    conn = None
    try:
        conn = get_connection()
        acc = _normalize_budget_account(account_id)
        row = conn.execute(
            "SELECT amount FROM budgets WHERE month = ? AND category = ? "
            "AND account_id = ?",
            (str(month), str(category), acc),
        ).fetchone()
        return float(row["amount"]) if row else 0.0
    except sqlite3.Error as exc:
        raise DatabaseError("读取预算失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def list_budgets(month, account_id=None):
    """列出某月某账户的所有预算设置。

    Args:
        month: 'YYYY-MM'。
        account_id: 账户 id；None/0 表示「全局」预算。

    Returns:
        list[sqlite3.Row]: 含 category/amount/account_id。
    """
    conn = None
    try:
        conn = get_connection()
        acc = _normalize_budget_account(account_id)
        cur = conn.execute(
            "SELECT category, amount, account_id FROM budgets "
            "WHERE month = ? AND account_id = ? ORDER BY category",
            (str(month), acc),
        )
        return cur.fetchall()
    except sqlite3.Error as exc:
        raise DatabaseError("读取预算列表失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def delete_budget(month, category, account_id=None):
    """删除某月某分类某账户的预算。

    Args:
        month: 'YYYY-MM'。
        category: 'TOTAL' 或分类名。
        account_id: 账户 id；None/0 表示「全局」预算。

    Returns:
        None
    """
    conn = None
    try:
        conn = get_connection()
        acc = _normalize_budget_account(account_id)
        conn.execute(
            "DELETE FROM budgets WHERE month = ? AND category = ? AND account_id = ?",
            (str(month), str(category), acc),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError("删除预算失败：{}".format(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


# ---------------------------------------------------------------------------
# 导出查询
# ---------------------------------------------------------------------------
def query_for_export(month=None, tx_type=None, account_id=None):
    """查询用于导出的交易数据（含账户名）。

    Args:
        month: 'YYYY-MM'（可空）。
        tx_type: '收入' / '支出'（可空）。
        account_id: 账户 id（可空）。

    Returns:
        list[sqlite3.Row]
    """
    return list_transactions(month=month, tx_type=tx_type, account_id=account_id)

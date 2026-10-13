import sqlite3
import time
from contextlib import closing

DB_FILE = "bot.db"


def _run(sql, args=(), fetch=None, commit=False):
    with closing(sqlite3.connect(DB_FILE, timeout=10)) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute(sql, args)
        if commit:
            con.commit()
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return cur.lastrowid


def now():
    return time.strftime("%Y-%m-%d %H:%M")


def init():
    _run("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, joined TEXT)""", commit=True)
    _run("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        first_name TEXT, kind TEXT, item TEXT, price INTEGER, target TEXT,
        status TEXT, file_id TEXT, file_type TEXT, created TEXT)""", commit=True)


def add_user(uid, username, first_name):
    _run("INSERT OR IGNORE INTO users(user_id, username, first_name, joined) VALUES(?,?,?,?)",
         (uid, username, first_name, now()), commit=True)
    _run("UPDATE users SET username=?, first_name=? WHERE user_id=?",
         (username, first_name, uid), commit=True)


def get_user(uid):
    return _run("SELECT * FROM users WHERE user_id=?", (uid,), fetch="one")


def all_user_ids():
    return [r["user_id"] for r in _run("SELECT user_id FROM users", fetch="all")]


def create_order(uid, username, first_name, kind, item, price, target):
    return _run(
        "INSERT INTO orders(user_id, username, first_name, kind, item, price, target, status, created) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (uid, username, first_name, kind, item, price, target, "waiting", now()), commit=True)


def get_order(oid):
    return _run("SELECT * FROM orders WHERE id=?", (oid,), fetch="one")


def set_status(oid, status):
    _run("UPDATE orders SET status=? WHERE id=?", (status, oid), commit=True)


def set_receipt(oid, file_id, file_type):
    _run("UPDATE orders SET file_id=?, file_type=?, status='pending' WHERE id=?",
         (file_id, file_type, oid), commit=True)


def waiting_order(uid):
    return _run("SELECT * FROM orders WHERE user_id=? AND status='waiting' ORDER BY id DESC LIMIT 1",
                (uid,), fetch="one")


def user_orders(uid, limit=10):
    return _run("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (uid, limit), fetch="all")


def pending_orders():
    return _run("SELECT * FROM orders WHERE status='pending' ORDER BY id", fetch="all")


def stats():
    users = _run("SELECT COUNT(*) AS n FROM users", fetch="one")["n"]
    rows = _run("SELECT status, COUNT(*) AS n FROM orders GROUP BY status", fetch="all")
    by_status = {r["status"]: r["n"] for r in rows}
    total = _run("SELECT COALESCE(SUM(price),0) AS s FROM orders WHERE status='done'", fetch="one")["s"]
    return users, by_status, total

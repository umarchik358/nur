"""
TELEGRAM STARS BOT  (bitta fayl: sozlamalar + baza + bot)

ISHGA TUSHIRISH:
    pip install pyTelegramBotAPI        (yoki: python -m pip install pyTelegramBotAPI)
    python bot.py

Faqat pastdagi "1) SOZLAMALAR" qismini o'zgartirasiz.
"""
import html
import logging
import re
import sqlite3
import sys
import time
from contextlib import closing

import telebot
from telebot import types

# =====================================================================
# 1) SOZLAMALAR  --  FAQAT SHU QISMNI O'ZGARTIRASIZ
# =====================================================================
# @BotFather bergan token
BOT_TOKEN = "7752065190:AAGsN_jCteqpbWebP_1t8MrW6ywhxn2Muzw"

# Admin Telegram ID lari (@userinfobot dan olinadi). Bir nechta bo'lsa vergul bilan: [111, 222]
ADMIN_IDS = [7253190744]

# To'lov uchun karta
CARD_NUMBER = "6262910201065257"
CARD_OWNER = "N.S"

# Aloqa uchun (admin username yoki telefon)
SUPPORT = "@nrvsh17"

# Yetkazib berish muddati (mijozga ko'rsatiladi)
DELIVERY_TEXT = "1 soat ichida"

# Stars paketlari: (miqdor, narx so'mda)
STARS_PACKAGES = [
    (50, 12000),
    (100, 23000),
    (250, 57000),
    (500, 112000),
    (1000, 222000),
    (2500, 550000),
]

# "Boshqa miqdor" uchun: 1 ta Stars narxi va chegaralar
PRICE_PER_STAR = 240
MIN_CUSTOM = 50
MAX_CUSTOM = 10000

# Gifts: (nomi, narx so'mda)  -- NAMUNAVIY NARXLAR, o'zingiznikiga almashtiring
GIFTS = [
    # --- 15 ⭐ ---
    ("🧸 Ayiqcha (15⭐)", 4000),
    ("❤️ Yurak (15⭐)", 4000),
    # --- 25 ⭐ ---
    ("🎁 Sovg'a qutisi (25⭐)", 6500),
    ("🌹 Atirgul (25⭐)", 6500),
    # --- 50 ⭐ ---
    ("🎂 Tort (50⭐)", 13000),
    ("💐 Gullar (50⭐)", 13000),
    ("🚀 Raketa (50⭐)", 13000),
    ("🍾 Shampan (50⭐)", 13000),
    # --- 100 ⭐ ---
    ("🏆 Kubok (100⭐)", 26000),
    ("💍 Uzuk (100⭐)", 26000),
    ("💎 Olmos (100⭐)", 26000),
]

# Telegram Premium: (nomi, narx so'mda)  -- NARXNI O'ZINGIZ YOZASIZ
PREMIUM = [
    ("💎 Premium — 3 oy", 170000),
    ("💎 Premium — 6 oy", 230000),
    ("💎 Premium — 12 oy", 400000),
]

# =====================================================================
# 2) KODNING QOLGAN QISMI  --  TEGMANG
# =====================================================================

class db:
    """SQLite baza (bot.db). Tegmang."""
    DB_FILE = "bot.db"

    @staticmethod
    def _run(sql, args=(), fetch=None, commit=False):
        with closing(sqlite3.connect(db.DB_FILE, timeout=10)) as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(sql, args)
            if commit:
                con.commit()
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return cur.lastrowid

    @staticmethod
    def now():
        return time.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def init():
        db._run("""CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, joined TEXT)""", commit=True)
        db._run("""CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
            first_name TEXT, kind TEXT, item TEXT, price INTEGER, target TEXT,
            status TEXT, file_id TEXT, file_type TEXT, created TEXT)""", commit=True)

    @staticmethod
    def add_user(uid, username, first_name):
        db._run("INSERT OR IGNORE INTO users(user_id, username, first_name, joined) VALUES(?,?,?,?)",
                (uid, username, first_name, db.now()), commit=True)
        db._run("UPDATE users SET username=?, first_name=? WHERE user_id=?",
                (username, first_name, uid), commit=True)

    @staticmethod
    def get_user(uid):
        return db._run("SELECT * FROM users WHERE user_id=?", (uid,), fetch="one")

    @staticmethod
    def all_user_ids():
        return [r["user_id"] for r in db._run("SELECT user_id FROM users", fetch="all")]

    @staticmethod
    def create_order(uid, username, first_name, kind, item, price, target):
        return db._run(
            "INSERT INTO orders(user_id, username, first_name, kind, item, price, target, status, created) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (uid, username, first_name, kind, item, price, target, "waiting", db.now()), commit=True)

    @staticmethod
    def get_order(oid):
        return db._run("SELECT * FROM orders WHERE id=?", (oid,), fetch="one")

    @staticmethod
    def set_status(oid, status):
        db._run("UPDATE orders SET status=? WHERE id=?", (status, oid), commit=True)

    @staticmethod
    def set_receipt(oid, file_id, file_type):
        db._run("UPDATE orders SET file_id=?, file_type=?, status='pending' WHERE id=?",
                (file_id, file_type, oid), commit=True)

    @staticmethod
    def waiting_order(uid):
        return db._run("SELECT * FROM orders WHERE user_id=? AND status='waiting' ORDER BY id DESC LIMIT 1",
                       (uid,), fetch="one")

    @staticmethod
    def user_orders(uid, limit=10):
        return db._run("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?",
                       (uid, limit), fetch="all")

    @staticmethod
    def pending_orders():
        return db._run("SELECT * FROM orders WHERE status='pending' ORDER BY id", fetch="all")

    @staticmethod
    def stats():
        users = db._run("SELECT COUNT(*) AS n FROM users", fetch="one")["n"]
        rows = db._run("SELECT status, COUNT(*) AS n FROM orders GROUP BY status", fetch="all")
        by_status = {r["status"]: r["n"] for r in rows}
        total = db._run("SELECT COALESCE(SUM(price),0) AS s FROM orders WHERE status='done'", fetch="one")["s"]
        return users, by_status, total


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stars_bot")

if BOT_TOKEN.startswith("PASTE"):
    print("XATO: bot.py ning yuqorisidagi BOT_TOKEN ga tokenni yozing!")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
states = {}  # user_id -> {"step": ..., ...}


BTN_STARS = "⭐ Stars sotib olish"
BTN_GIFT = "🎁 Gift sotib olish"
BTN_PREMIUM = "💎 Telegram Premium"
BTN_PRICES = "💰 Narxlar"
BTN_ORDERS = "📋 Buyurtmalarim"
BTN_HELP = "☎️ Aloqa"

STATUS_TEXT = {
    "waiting": "⏳ Chek kutilmoqda",
    "pending": "🕓 Tekshirilmoqda",
    "done": "✅ Bajarildi",
    "rejected": "❌ Rad etildi",
    "cancelled": "🚫 Bekor qilindi",
}

# ---------- RANGLI TUGMALAR ----------
# style: "primary" (ko'k), "success" (yashil), "danger" (qizil), None (oddiy)
# Rang yangi Telegram versiyalarida ko'rinadi; eskisida tugma oddiy bo'lib qoladi.


class IBtn(types.InlineKeyboardButton):
    def __init__(self, text, callback_data=None, style=None, **kw):
        super().__init__(text, callback_data=callback_data, **kw)
        self.btn_style = style

    def to_dict(self):
        d = super().to_dict()
        if self.btn_style:
            d["style"] = self.btn_style
        return d


class KBtn(types.KeyboardButton):
    def __init__(self, text, style=None, **kw):
        super().__init__(text, **kw)
        self.btn_style = style

    def to_dict(self):
        d = super().to_dict()
        if self.btn_style:
            d["style"] = self.btn_style
        return d


# ---------- yordamchi funksiyalar ----------
def money(n):
    return f"{int(n):,}".replace(",", " ") + " so'm"


def is_admin(uid):
    return uid in ADMIN_IDS


def e(text):
    return html.escape(str(text or ""))


def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KBtn(BTN_STARS, style="primary"), KBtn(BTN_GIFT, style="success"))
    kb.row(KBtn(BTN_PREMIUM, style="primary"), KBtn(BTN_PRICES, style="success"))
    kb.row(KBtn(BTN_ORDERS, style="primary"), KBtn(BTN_HELP, style="success"))
    return kb


def order_text(o):
    uname = f" (@{e(o['username'])})" if o["username"] else ""
    return (
        f"🧾 <b>Buyurtma #{o['id']}</b>\n"
        f"👤 <a href=\"tg://user?id={o['user_id']}\">{e(o['first_name'] or 'Foydalanuvchi')}</a>{uname}\n"
        f"📦 {e(o['item'])}\n"
        f"💰 {money(o['price'])}\n"
        f"🎯 Qabul qiluvchi: {e(o['target'])}"
    )


def write_kb(uid, text="💬 Mijozga yozish"):
    kb = types.InlineKeyboardMarkup()
    kb.add(IBtn(text, f"reply:{uid}", "primary"))
    return kb


def admin_kb(oid, uid):
    kb = types.InlineKeyboardMarkup()
    kb.row(IBtn("✅ Tasdiqlash", f"ok:{oid}", "success"),
           IBtn("❌ Rad etish", f"no:{oid}", "danger"))
    kb.add(IBtn("💬 Mijozga yozish", f"reply:{uid}", "primary"))
    return kb


def relay_to_admins(m):
    """Mijozning xabarini adminlarga uzatadi (admin 'Javob yozish' tugmasi bilan javob beradi)."""
    u = m.from_user
    uname = f" (@{e(u.username)})" if u.username else ""
    head = (f"📩 <b>Mijozdan xabar</b>\n"
            f"👤 <a href=\"tg://user?id={u.id}\">{e(u.first_name or 'Foydalanuvchi')}</a>{uname}\n"
            f"🆔 <code>{u.id}</code>")
    kb = write_kb(u.id, "💬 Javob yozish")
    sent = 0
    for aid in ADMIN_IDS:
        try:
            if m.content_type == "text":
                bot.send_message(aid, head + "\n\n" + e(m.text), reply_markup=kb)
            else:
                bot.send_message(aid, head)
                bot.copy_message(aid, m.chat.id, m.message_id, reply_markup=kb)
            sent += 1
        except Exception as ex:
            log.warning("Adminga xabar ketmadi (%s): %s", aid, ex)
    if sent:
        bot.send_message(m.chat.id, "✅ Xabaringiz adminga yuborildi. Javobni shu yerda olasiz.",
                         reply_markup=main_menu())
    else:
        bot.send_message(m.chat.id, f"Xabar yuborilmadi. Iltimos, {e(SUPPORT)} ga yozing.",
                         reply_markup=main_menu())


def send_to_customer(uid, m):
    """Admin xabarini (matn/rasm/ovoz/fayl) bot nomidan mijozga yuboradi."""
    if m.content_type == "text":
        bot.send_message(uid, f"💬 <b>Admin:</b>\n{e(m.text)}")
    else:
        bot.send_message(uid, "💬 <b>Admin xabari:</b>")
        bot.copy_message(uid, m.chat.id, m.message_id)


# ---------- admin: mijozga bot nomidan yozish ----------
def _admin_replying(m):
    st = states.get(m.from_user.id)
    if not st or st.get("step") != "reply" or not is_admin(m.from_user.id):
        return False
    return not (m.content_type == "text" and (m.text or "").startswith("/"))


@bot.message_handler(func=_admin_replying,
                     content_types=["text", "photo", "document", "video", "voice", "audio",
                                    "sticker", "video_note", "animation"])
def admin_reply(m):
    st = states.pop(m.from_user.id)
    uid = st["uid"]
    try:
        send_to_customer(uid, m)
        bot.send_message(m.chat.id, "✅ Mijozga yuborildi.", reply_markup=write_kb(uid, "💬 Yana yozish"))
    except Exception as ex:
        bot.send_message(m.chat.id, f"❌ Yuborib bo'lmadi (mijoz botni bloklagan bo'lishi mumkin): {e(ex)}")


@bot.callback_query_handler(func=lambda c: c.data.startswith("reply:"))
def cb_reply(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "Ruxsat yo'q")
        return
    uid = int(c.data.split(":")[1])
    u = db.get_user(uid)
    name = e(u["first_name"]) if u and u["first_name"] else str(uid)
    states[c.from_user.id] = {"step": "reply", "uid": uid}
    bot.answer_callback_query(c.id)
    kb = types.InlineKeyboardMarkup()
    kb.add(IBtn("❌ Bekor qilish", "rcancel", "danger"))
    bot.send_message(
        c.message.chat.id,
        f"✍️ <b>{name}</b> (<code>{uid}</code>) ga yuboriladigan xabarni yozing.\n"
        "Matn, rasm, ovozli xabar, fayl — hammasi bo'ladi.",
        reply_markup=kb,
    )


@bot.callback_query_handler(func=lambda c: c.data == "rcancel")
def cb_rcancel(c):
    if states.get(c.from_user.id, {}).get("step") == "reply":
        states.pop(c.from_user.id, None)
    bot.answer_callback_query(c.id, "Bekor qilindi")


# ---------- /start va menyu ----------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    states.pop(m.from_user.id, None)
    db.add_user(m.from_user.id, m.from_user.username, m.from_user.first_name)
    bot.send_message(
        m.chat.id,
        f"Assalomu alaykum, <b>{e(m.from_user.first_name)}</b>! 👋\n\n"
        "Bu bot orqali <b>Telegram Stars</b>, <b>Gift</b> va <b>Premium</b> sotib olishingiz mumkin.\n"
        f"⏱ Buyurtma <b>{e(DELIVERY_TEXT)}</b> hisobingizga tushadi.\n\n"
        "Quyidagi menyudan tanlang 👇\n"
        "Yoki kerakli Stars sonini yozing (masalan: 120)",
        reply_markup=main_menu(),
    )


@bot.message_handler(func=lambda m: m.text == BTN_STARS)
def menu_stars(m):
    states.pop(m.from_user.id, None)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(*[
        IBtn(f"⭐ {a} — {money(p)}", f"buy:stars:{i}", "primary")
        for i, (a, p) in enumerate(STARS_PACKAGES)
    ])
    kb.add(IBtn("✏️ Boshqa miqdor", "custom", "success"))
    bot.send_message(m.chat.id, "⭐ <b>Stars paketini tanlang:</b>", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == BTN_GIFT)
def menu_gift(m):
    states.pop(m.from_user.id, None)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(*[
        IBtn(f"{name} — {money(p)}", f"buy:gift:{i}", "success")
        for i, (name, p) in enumerate(GIFTS)
    ])
    bot.send_message(m.chat.id, "🎁 <b>Giftni tanlang:</b>", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == BTN_PREMIUM)
def menu_premium(m):
    states.pop(m.from_user.id, None)
    if not PREMIUM:
        bot.send_message(m.chat.id, "Hozircha Premium mavjud emas.")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(*[
        IBtn(f"{name} — {money(p)}", f"buy:prem:{i}", "primary")
        for i, (name, p) in enumerate(PREMIUM)
    ])
    bot.send_message(m.chat.id, "💎 <b>Telegram Premium muddatini tanlang:</b>", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == BTN_PRICES)
def menu_prices(m):
    states.pop(m.from_user.id, None)
    lines = ["💰 <b>Narxlar ro'yxati</b>\n", "⭐ <b>Stars</b>"]
    for a, p in STARS_PACKAGES:
        lines.append(f"• {a} ⭐ — {money(p)}")
    lines.append(f"• Boshqa miqdor: 1 ⭐ = {money(PRICE_PER_STAR)}")
    lines.append("\n🎁 <b>Giftlar</b>")
    for name, p in GIFTS:
        lines.append(f"• {e(name)} — {money(p)}")
    if PREMIUM:
        lines.append("\n💎 <b>Premium</b>")
        for name, p in PREMIUM:
            lines.append(f"• {e(name)} — {money(p)}")
    lines.append(f"\n⏱ Buyurtma {e(DELIVERY_TEXT)} hisobingizga tushadi.")
    bot.send_message(m.chat.id, "\n".join(lines))


@bot.message_handler(func=lambda m: m.text == BTN_ORDERS)
def menu_orders(m):
    states.pop(m.from_user.id, None)
    rows = db.user_orders(m.from_user.id, 10)
    if not rows:
        bot.send_message(m.chat.id, "Sizda hali buyurtmalar yo'q.")
        return
    lines = ["📋 <b>Oxirgi buyurtmalaringiz:</b>\n"]
    for o in rows:
        lines.append(
            f"#{o['id']} • {e(o['item'])} • {money(o['price'])}\n"
            f"   {STATUS_TEXT.get(o['status'], o['status'])} • {o['created']}"
        )
    bot.send_message(m.chat.id, "\n".join(lines))


@bot.message_handler(func=lambda m: m.text == BTN_HELP)
def menu_help(m):
    states.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, f"☎️ Savollar uchun: {e(SUPPORT)}")


# ---------- tanlash va buyurtma ----------
def ask_target(chat_id, user, kind, item, price):
    states[user.id] = {"step": "target", "kind": kind, "item": item, "price": price}
    kb = types.InlineKeyboardMarkup()
    if user.username:
        kb.add(IBtn(f"👤 O'zimga (@{user.username})", "self", "success"))
    kb.add(IBtn("❌ Bekor qilish", "abort", "danger"))
    bot.send_message(
        chat_id,
        f"Tanlandi: <b>{e(item)}</b>\nNarxi: <b>{money(price)}</b>\n\n"
        "Kimga yuborilsin? Qabul qiluvchining <b>@username</b> ini yozing:",
        reply_markup=kb,
    )


def create_order(chat_id, user, target):
    st = states.pop(user.id, None)
    if not st:
        return
    oid = db.create_order(user.id, user.username, user.first_name,
                          st["kind"], st["item"], st["price"], target)
    kb = types.InlineKeyboardMarkup()
    kb.add(IBtn("❌ Buyurtmani bekor qilish", f"cancel:{oid}", "danger"))
    bot.send_message(
        chat_id,
        f"🧾 <b>Buyurtma #{oid}</b>\n"
        f"📦 {e(st['item'])}\n"
        f"🎯 Qabul qiluvchi: {e(target)}\n"
        f"💰 To'lov summasi: <b>{money(st['price'])}</b>\n\n"
        f"💳 Karta: <code>{e(CARD_NUMBER)}</code>\n"
        f"👤 Egasi: <b>{e(CARD_OWNER)}</b>\n\n"
        f"⏱ To'lov tasdiqlangach, <b>{e(DELIVERY_TEXT)}</b> hisobingizga tushadi.\n\n"
        "To'lovni qilgach, <b>chek rasmini (skrinshot)</b> shu yerga yuboring 📸",
        reply_markup=kb,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("buy:"))
def cb_buy(c):
    bot.answer_callback_query(c.id)
    try:
        _, kind, idx = c.data.split(":")
        idx = int(idx)
        if kind == "stars":
            amount, price = STARS_PACKAGES[idx]
            item = f"⭐ {amount} Stars"
        elif kind == "gift":
            name, price = GIFTS[idx]
            item = f"Gift: {name}"
        elif kind == "prem":
            name, price = PREMIUM[idx]
            item = name
        else:
            return
    except Exception:
        return
    ask_target(c.message.chat.id, c.from_user, kind, item, price)


@bot.callback_query_handler(func=lambda c: c.data == "custom")
def cb_custom(c):
    bot.answer_callback_query(c.id)
    states[c.from_user.id] = {"step": "custom"}
    bot.send_message(
        c.message.chat.id,
        f"Nechta Stars kerak? Son yozing ({MIN_CUSTOM} dan {MAX_CUSTOM} gacha).\n"
        f"1 ⭐ = {money(PRICE_PER_STAR)}",
    )


@bot.callback_query_handler(func=lambda c: c.data == "self")
def cb_self(c):
    bot.answer_callback_query(c.id)
    if states.get(c.from_user.id, {}).get("step") != "target":
        return
    if not c.from_user.username:
        bot.send_message(c.message.chat.id, "Sizda username yo'q. Qabul qiluvchi @username ni yozing.")
        return
    create_order(c.message.chat.id, c.from_user, "@" + c.from_user.username)


@bot.callback_query_handler(func=lambda c: c.data == "abort")
def cb_abort(c):
    states.pop(c.from_user.id, None)
    bot.answer_callback_query(c.id, "Bekor qilindi")
    bot.send_message(c.message.chat.id, "Bekor qilindi.", reply_markup=main_menu())


@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel:"))
def cb_cancel(c):
    oid = int(c.data.split(":")[1])
    o = db.get_order(oid)
    if not o or o["user_id"] != c.from_user.id or o["status"] != "waiting":
        bot.answer_callback_query(c.id, "Buni bekor qilib bo'lmaydi")
        return
    db.set_status(oid, "cancelled")
    bot.answer_callback_query(c.id, "Bekor qilindi")
    bot.send_message(c.message.chat.id, f"🚫 Buyurtma #{oid} bekor qilindi.", reply_markup=main_menu())


# ---------- chek qabul qilish ----------
@bot.message_handler(content_types=["photo", "document"])
def on_receipt(m):
    o = db.waiting_order(m.from_user.id)
    if not o:
        if is_admin(m.from_user.id):
            bot.send_message(m.chat.id, "Menyudan tanlang 👇", reply_markup=main_menu())
        else:
            relay_to_admins(m)
        return
    if m.content_type == "photo":
        file_id, ftype = m.photo[-1].file_id, "photo"
    else:
        file_id, ftype = m.document.file_id, "document"
    db.set_receipt(o["id"], file_id, ftype)
    o = db.get_order(o["id"])

    sent = 0
    for aid in ADMIN_IDS:
        try:
            if ftype == "photo":
                bot.send_photo(aid, file_id, caption=order_text(o), reply_markup=admin_kb(o["id"], o["user_id"]))
            else:
                bot.send_document(aid, file_id, caption=order_text(o), reply_markup=admin_kb(o["id"], o["user_id"]))
            sent += 1
        except Exception as ex:
            log.warning("Adminga yuborib bo'lmadi (%s): %s", aid, ex)
    if sent == 0:
        log.error("Hech bir adminga chek yetib bormadi! ADMIN_IDS ni va adminning /start bosganini tekshiring.")
    bot.send_message(
        m.chat.id,
        f"✅ Chek qabul qilindi. Buyurtma #{o['id']} tekshirilmoqda.\n"
        f"Buyurtma <b>{e(DELIVERY_TEXT)}</b> hisobingizga tushadi va sizga xabar beramiz.",
        reply_markup=main_menu(),
    )


# ---------- admin tugmalari ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith(("ok:", "no:")))
def cb_admin(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "Ruxsat yo'q")
        return
    action, oid = c.data.split(":")
    oid = int(oid)
    o = db.get_order(oid)
    if not o or o["status"] != "pending":
        bot.answer_callback_query(c.id, "Bu buyurtma allaqachon ko'rib chiqilgan")
        return
    who = c.from_user.first_name or "admin"
    if action == "ok":
        db.set_status(oid, "done")
        mark, user_msg = f"\n\n✅ Bajarildi ({e(who)})", (
            f"✅ <b>Buyurtma #{oid} bajarildi!</b>\n{e(o['item'])} → {e(o['target'])}\n"
            "Xaridingiz uchun rahmat! 🙌")
    else:
        db.set_status(oid, "rejected")
        mark, user_msg = f"\n\n❌ Rad etildi ({e(who)})", (
            f"❌ <b>Buyurtma #{oid} rad etildi.</b>\n"
            f"Chek tasdiqlanmadi. Savol bo'lsa: {e(SUPPORT)}")
    bot.answer_callback_query(c.id, "Bajarildi")
    try:
        bot.edit_message_caption(order_text(o) + mark, c.message.chat.id, c.message.message_id,
                                reply_markup=write_kb(o["user_id"]))
    except Exception as ex:
        log.warning("caption tahrirlanmadi: %s", ex)
    try:
        bot.send_message(o["user_id"], user_msg)
    except Exception as ex:
        log.warning("Foydalanuvchiga xabar ketmadi: %s", ex)


# ---------- admin buyruqlari ----------
@bot.message_handler(commands=["stats"])
def cmd_stats(m):
    if not is_admin(m.from_user.id):
        return
    users, by_status, total = db.stats()
    lines = ["📊 <b>Statistika</b>", f"👥 Foydalanuvchilar: {users}"]
    for k, v in by_status.items():
        lines.append(f"{STATUS_TEXT.get(k, k)}: {v}")
    lines.append(f"💰 Bajarilgan summa: {money(total)}")
    bot.send_message(m.chat.id, "\n".join(lines))


@bot.message_handler(commands=["pending"])
def cmd_pending(m):
    if not is_admin(m.from_user.id):
        return
    rows = db.pending_orders()
    if not rows:
        bot.send_message(m.chat.id, "Kutilayotgan buyurtma yo'q ✅")
        return
    for o in rows:
        try:
            if o["file_type"] == "document":
                bot.send_document(m.chat.id, o["file_id"], caption=order_text(o), reply_markup=admin_kb(o["id"], o["user_id"]))
            else:
                bot.send_photo(m.chat.id, o["file_id"], caption=order_text(o), reply_markup=admin_kb(o["id"], o["user_id"]))
        except Exception:
            bot.send_message(m.chat.id, order_text(o), reply_markup=admin_kb(o["id"], o["user_id"]))


@bot.message_handler(commands=["order"])
def cmd_order(m):
    if not is_admin(m.from_user.id):
        return
    parts = m.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        bot.send_message(m.chat.id, "Foydalanish: /order 12")
        return
    o = db.get_order(int(parts[1]))
    if not o:
        bot.send_message(m.chat.id, "Buyurtma topilmadi.")
        return
    bot.send_message(
        m.chat.id,
        order_text(o) + f"\n📌 {STATUS_TEXT.get(o['status'], o['status'])}\n🕒 {o['created']}")


@bot.message_handler(commands=["msg"])
def cmd_msg(m):
    if not is_admin(m.from_user.id):
        return
    parts = m.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        bot.send_message(m.chat.id, "Foydalanish: /msg 123456789 xabar matni", parse_mode=None)
        return
    try:
        bot.send_message(int(parts[1]), f"💬 <b>Admin:</b>\n{e(parts[2])}")
        bot.send_message(m.chat.id, "✅ Yuborildi.")
    except Exception as ex:
        bot.send_message(m.chat.id, f"❌ Yuborib bo'lmadi: {e(ex)}")


@bot.message_handler(commands=["admin"])
def cmd_admin(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(
        m.chat.id,
        "🛠 <b>Admin buyruqlari</b>\n\n"
        "/stats — statistika\n"
        "/pending — kutilayotgan buyurtmalar\n"
        "/order 12 — buyurtmani ko'rish\n"
        "/msg ID matn — mijozga bot nomidan yozish\n"
        "/broadcast matn — hammaga xabar\n\n"
        "💬 Mijoz yozganda yoki chek kelganda <b>Javob yozish / Mijozga yozish</b> tugmasini bosing.")


@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(m):
    if not is_admin(m.from_user.id):
        return
    text = m.text.partition(" ")[2].strip()
    if not text:
        bot.send_message(m.chat.id, "Foydalanish: /broadcast xabar matni")
        return
    ok = fail = 0
    for uid in db.all_user_ids():
        try:
            bot.send_message(uid, text, parse_mode=None)
            ok += 1
        except Exception:
            fail += 1
        time.sleep(0.05)
    bot.send_message(m.chat.id, f"Yuborildi: {ok}, xato: {fail}")


# ---------- matnli javoblar (state) ----------
@bot.message_handler(content_types=["text"])
def on_text(m):
    st = states.get(m.from_user.id)
    if not st:
        txt = (m.text or "").strip()
        if txt.isdigit() and MIN_CUSTOM <= int(txt) <= MAX_CUSTOM:
            amount = int(txt)
            ask_target(m.chat.id, m.from_user, "stars", f"⭐ {amount} Stars", amount * PRICE_PER_STAR)
            return
        if txt.isdigit():
            bot.send_message(m.chat.id, f"Stars soni {MIN_CUSTOM} dan {MAX_CUSTOM} gacha bo'lishi kerak.",
                             reply_markup=main_menu())
            return
        if is_admin(m.from_user.id):
            bot.send_message(m.chat.id, "Menyudan tanlang 👇  (/admin — admin buyruqlari)", reply_markup=main_menu())
            return
        relay_to_admins(m)
        return

    if st["step"] == "custom":
        txt = m.text.strip()
        if not txt.isdigit() or not (MIN_CUSTOM <= int(txt) <= MAX_CUSTOM):
            bot.send_message(m.chat.id, f"Iltimos, {MIN_CUSTOM} dan {MAX_CUSTOM} gacha son yozing.")
            return
        amount = int(txt)
        ask_target(m.chat.id, m.from_user, "stars", f"⭐ {amount} Stars", amount * PRICE_PER_STAR)

    elif st["step"] == "target":
        uname = m.text.strip()
        if not re.fullmatch(r"@?[A-Za-z0-9_]{5,32}", uname):
            bot.send_message(m.chat.id, "Username noto'g'ri. Masalan: @username")
            return
        create_order(m.chat.id, m.from_user, "@" + uname.lstrip("@"))


@bot.message_handler(content_types=["voice", "video", "audio", "video_note", "animation"])
def on_other(m):
    if is_admin(m.from_user.id):
        return
    relay_to_admins(m)


if __name__ == "__main__":
    db.init()
    log.info("Bot ishga tushdi. To'xtatish: Ctrl+C")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
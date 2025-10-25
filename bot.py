# bot.py
"""
Purple Digital Store - ငွေဖြည့် Bot
python-telegram-bot==21.6
"""

import os
import sqlite3
import random
import datetime
import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ===== CONFIG =====
TOKEN = os.getenv("7664363867:AAHaVrLGHUx_GfWtHDjNSuZtQohGk5LwNAY")  # <-- Set BOT_TOKEN in Render environment
ADMIN_ID = 5583558824
DB_PATH = "orders.db"
# ==================


# ---------- DATABASE ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE,
            user_id INTEGER,
            username TEXT,
            website_name TEXT,
            amount TEXT,
            status TEXT,
            created_at TEXT,
            photo_file_id TEXT
        )
    """
    )
    conn.commit()
    conn.close()


# ---------- HELPERS ----------
def gen_order_id():
    return f"{random.randint(0, 999999):06d}"


def save_order(user_id, username, website_name, amount=None, status="pending", photo=None, order_id=None):
    # Allow passing an order_id so displayed order_id and DB order_id can match
    order_id = order_id or gen_order_id()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO orders (order_id, user_id, username, website_name, amount, status, created_at, photo_file_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (order_id, user_id, username, website_name, amount or "N/A", status, datetime.datetime.utcnow().isoformat(), photo),
    )
    conn.commit()
    conn.close()
    return order_id


# ---------- MEMORY ----------
user_states = {}
user_names = {}
user_orders = {}


# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_states[user.id] = "awaiting_name"

    text = (
        "<b>Purple Digital Store\n"
        "ငွေဖြည့် Bot မှ ကြိုဆိုပါတယ်</b> 🎉\n\n"
        "စတင်ရန်၊ သင့် Website\n"
        "အသုံးပြုသူအမည်ကို ပေးပို့ပါ။\n\n"
        "🔁 Bot ကို အစမှ ပြန်စချင်ပါက\n"
        "/start ဟု ပို့ပါ။\n"
    )
    # message may be None if using callback query — but start is via /start command
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML")


# ---------- NAME ----------
async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user_states.get(user.id) != "awaiting_name":
        return

    name = update.message.text.strip()
    user_names[user.id] = name
    user_states[user.id] = "registered"

    text = (
        f"✅ <b>အဆင်ပြေပါပြီ!</b>\n\n"
        f"သင့်အသုံးပြုသူအမည် <b>“{name}”</b> သည် သင့် Telegram အကောင့်နှင့် ချိတ်ဆက်ပြီးပါပြီ။\n\n"
        "ဆောင်ရွက်လိုသောအရာကို ရွေးချယ်ပါ 👇\n\n"
        "🔁 Bot ကို အစမှ ပြန်စချင်ပါက /start ဟု ပို့ပါ။"
    )

    keyboard = [[InlineKeyboardButton("💰 ငွေဖြည့်မည်", callback_data="topup")]]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


# ---------- PAYMENT METHOD ----------
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    name = user_names.get(user.id, "မသိရသေးပါ")

    if query.data == "topup":
        keyboard = [
            [InlineKeyboardButton("🟢 KBZ Pay", callback_data="kbz")],
            [InlineKeyboardButton("🟡 Wave Pay", callback_data="wave")],
        ]
        await query.edit_message_text(
            f"💵 <b>ငွေပေးချေမှုနည်းလမ်း ရွေးချယ်ပါ</b>\n\n"
            f"👤 အသုံးပြုသူအမည်: <b>{name}</b>\n\n"
            "🔁 Bot ကို အစမှ ပြန်စချင်ပါက\n"
            "/start ဟု ပို့ပါ။\n",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data in ["kbz", "wave"]:
        method = "KBZ Pay" if query.data == "kbz" else "Wave Pay"
        user_states[user.id] = "waiting_payment"
        order_id = gen_order_id()
        user_orders[user.id] = order_id

        await query.edit_message_text(
            f"💳 <b>{method}</b> ဖြင့် ငွေပေးချေမည်။\n\n"
            "1$ = 4000Ks\n\n"
            "💰 ငွေချေရမည့်အချက်အလက်များ\n"
            "📱 09451266782\n"
            "👤 Mya Sandar\n\n"
            "💡 ငွေချေပြီးပါက Screenshot ပေးပို့ပါ။\n",
            parse_mode="HTML",
        )


# ---------- PAYMENT HANDLER ----------
async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user_states.get(user.id) != "waiting_payment":
        return

    name = user_names.get(user.id, "Unknown")
    order_id = user_orders.get(user.id, gen_order_id())
    username = user.username or user.full_name

    # PHOTO Handler
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        caption = (
            f"📩 Screenshot from @{username}\n"
            f"📋 ငွေဖြည့်အမှတ်: {order_id}\n"
            f"👤 Name: {name}"
        )
        # forward photo to admin (or send)
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=file_id, caption=caption)

        # Save order with photo and status
        save_order(user.id, username, name, amount=None, status="screenshot_received", photo=file_id, order_id=order_id)

        await update.message.reply_text(
            f"🔄 သင့်ငွေဖြည့်တောင်းဆိုမှုကို\n"
            f"စစ်ဆေးနေပါပြီ။ စစ်ပြီး ငွေထည့်ပြီးပါက \n"
            f"စာပြန်ပို့ပေးပါမည်။\n\n"
            f"📋 ငွေဖြည့်အမှတ်: {order_id}\n"
            f"👤 အသုံးပြုသူအမည်: {name}\n\n"
            "purpledigitalstore.com ကို\n"
            "အသုံးပြုသည့်အတွက် ကျေးဇူးတင်ပါသည် 🎉\n\n"
            "📸 ဓာတ်ပုံ (screenshot) လက်ခံပြီး\n"
            Admin သို့ auto-forward ပြုလုပ်ပြီးပါပြီ။\n",
            parse_mode="HTML",
        )

        return

    # AMOUNT Handler
    if update.message.text:
        text = update.message.text.strip()
    else:
        text = ""

    if re.fullmatch(r"\d+", text):
        amount = f"{int(text):,}"
        # save order with the same order_id shown to user
        save_order(user.id, username, name, amount, "waiting_screenshot", order_id=order_id)

        reply_text = (
            f"🔄 သင့်ငွေဖြည့်တောင်းဆိုမှုကို စစ်ဆေးနေပါပြီ။\n"
            f"စစ်ပြီး ငွေထည့်ပြီးပါက စာပြန်ပိုပေးပါမည်။\n\n"
            f"📋 ငွေထိုးအမှတ်: {order_id}\n"
            f"👤 အသုံးပြုသူအမည်: {name}\n"
            f"💰 ငွေပမာဏ: {amount} ကျပ်\n\n"
            "purpledigitalstore.com ကို အသုံးပြုသည့်အတွက် ကျေးဇူးတင်ပါသည် 🎉\n\n"
            "📸 ဓာတ်ပုံ (Screenshot) ပေးပါ — Admin သို့ auto-forward လုပ်ပါမည်။"
        )

        await update.message.reply_text(reply_text, parse_mode="HTML")
    else:
        await update.message.reply_text("🧾 ငွေပမာဏ သို့မဟုတ် Screenshot ပေးပါ။")


# ---------- MAIN ----------
async def main():
    # ensure DB exists
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    # name registration - only when awaiting name
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), register_name))
    # payments (photo or amount)
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), payment_handler))

    print("🤖 Purple Digital Store Bot Running (Dual Input)...")

    # run polling (async)
    await app.run_polling()


if __name__ == "__main__":
    # run the async main safely
    asyncio.run(main())

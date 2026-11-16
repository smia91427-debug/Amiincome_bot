import logging
import sqlite3
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

API_TOKEN = '9256749123:AAFe4PIUr_LR0esudKZUL4Ro5_MHAEJQJ7o' 
ADMIN_ID = 6935814571
WEB_APP_URL = 'https://smia91427-debug.github.io/Amiincome_bot/'
CHANNEL_USERNAME = '@amiofficialchannel'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- ইউজার ব্যালেন্স আপডেট করার জন্য স্টেট (FSM) ---
class AdminStates(StatesGroup):
    waiting_for_new_balance = State()

# --- রেন্ডার পোর্ট ওপেন রাখার জন্য ডাইনামিক ওয়েব সার্ভার ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Ami Income Bot is Alive and Running!")

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, SimpleHandler)
    httpd.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# --- ডেটাবেজ এবং টেবিল ইনিশিয়ালাইজেশন ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            reward REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_bonus', '5.0')")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_devices (
            user_id INTEGER,
            device_id TEXT,
            UNIQUE(user_id, device_id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# --- চ্যানেল সাবস্ক্রিপশন চেক করার ফাংশন ---
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logging.error(f"Subscription check error: {e}")
    return False

# --- স্টার্ট কমান্ড ও চ্যানেল জয়েন চেক ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user and user[0] == 1:
        conn.close()
        await message.answer("⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে!")
        return

    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

    if not await is_subscribed(user_id):
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("📢 চ্যানেলে জয়েন করুন", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
            InlineKeyboardButton("✅ ভেরিফাই করুন", callback_data="verify_join")
        )
        await message.answer(
            "⚠️ বটটি ব্যবহার করতে হলে প্রথমে আমাদের অফিসিয়াল চ্যানেলে জয়েন করতে হবে!\n\nদয়া করে নিচের বাটনে ক্লিক করে চ্যানেলে জয়েন করুন এবং তারপর **'ভেরিফাই করুন'** বাটনে ক্লিক করুন:",
            reply_markup=keyboard
        )
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=WEB_APP_URL))
    )

    await message.answer(
        f"হ্যালো {message.from_user.first_name}! আমাদের প্রফেশনাল আর্নিং বটে স্বাগতম।",
        reply_markup=keyboard
    )

@dp.callback_query_handler(text="verify_join")
async def verify_join(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if await is_subscribed(user_id):
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=WEB_APP_URL))
        )
        await callback.message.edit_text(
            "✅ ভেরিফিকেশন সফল হয়েছে! কাজ শুরু করতে নিচের বাটনে ক্লিক করুন:",
            reply_markup=keyboard
        )
    else:
        await callback.answer("❌ আপনি এখনো আমাদের চ্যানেলে জয়েন করেননি! দয়া করে আগে চ্যানেলে জয়েন করুন।", show_alert=True)

# ==========================================
# --- অ্যাডমিন প্যানেল (Admin Panel) ---
# ==========================================

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⚠️ আপনার এই প্যানেল ব্যবহার করার অনুমতি নেই!")
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 User List", callback_data="admin_users_list"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("📝 Manage Tasks", callback_data="admin_tasks"),
        InlineKeyboardButton("💰 Referral Rate", callback_data="admin_ref_rate"),
        InlineKeyboardButton("🚨 Multi-Account Check", callback_data="admin_fraud_check")
    )
    
    await message.reply("🛠 **প্রফেশনাল অ্যাডমিন প্যানেলে স্বাগতম বস!**\nনিচের অপশনগুলো থেকে সিলেক্ট করুন:", reply_markup=keyboard)

# ১. ইউজার লিস্ট দেখানো (নামসহ)
@dp.callback_query_handler(text="admin_users_list")
async def admin_users_list(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, balance, is_banned FROM users')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await callback.answer("⚠️ কোনো ইউজার পাওয়া যায়নি!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for u in users:
        uname = f"@{u[1]}" if u[1] else f"ID: {u[0]}"
        status_icon = "🔴" if u[3] == 1 else "🟢"
        keyboard.add(
            InlineKeyboardButton(f"{status_icon} {uname} (Bal: {u[2]} BDT)", callback_data=f"manage_user_{u[0]}")
        )
    
    keyboard.add(InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin"))
    await callback.message.edit_text("👥 **রেজিস্টার্ড ইউজারদের তালিকা:**\nইউজারের উপর ক্লিক করে কন্ট্রোল করুন:", reply_markup=keyboard)

# ২. নির্দিষ্ট ইউজারের কন্ট্রোল প্যানেল (ব্যালেন্স, ব্লক, আনব্লক)
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('manage_user_'))
async def manage_user_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split('_')[2])
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, balance, is_banned FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await callback.answer("⚠️ ইউজারটি পাওয়া যায়নি!", show_alert=True)
        return
    
    u_id, username, balance, is_banned = user
    uname_str = f"@{username}" if username else "N/A"
    status_str = "🔴 Blocked" if is_banned == 1 else "🟢 Active"
    
    text = (
        f"👤 **ইউজার ডিটেইলস:**\n\n"
        f"🆔 ID: `{u_id}`\n"
        f"👤 Username: {uname_str}\n"
        f"💰 বর্তমান ব্যালেন্স: {balance} BDT\n"
        f"📌 স্ট্যাটাস: {status_str}"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✏️ Change Balance (অ্যামাউন্ট পরিবর্তন)", callback_data=f"set_bal_{u_id}")
    )
    
    if is_banned == 1:
        keyboard.add(InlineKeyboardButton("✅ Unblock User (আনব্লক করুন)", callback_data=f"toggle_ban_{u_id}"))
    else:
        keyboard.add(InlineKeyboardButton("🚫 Block User (ব্লক করুন)", callback_data=f"toggle_ban_{u_id}"))
        
    keyboard.add(InlineKeyboardButton("🔙 Back to User List", callback_data="admin_users_list"))
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ৩. ব্যালেন্স পরিবর্তন করার জন্য প্রম্পট (FSM Trigger)
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('set_bal_'))
async def ask_new_balance(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split('_')[2])
    await state.update_data(target_user_id=user_id)
    await AdminStates.waiting_for_new_balance.set()
    
    await callback.message.answer("✍️ এই ইউজারের জন্য নতুন কত অ্যামাউন্ট সেট করতে চান? শুধু সংখ্যাটি লিখে পাঠান (যেমন: 50 বা 100):")
    await callback.answer()

# ৪. ব্যালেন্স সেভ করা
@dp.message_handler(state=AdminStates.waiting_for_new_balance)
async def save_new_balance(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        new_balance = float(message.text)
    except ValueError:
        await message.reply("❌ দয়া করে সঠিক সংখ্যা লিখুন (যেমন: 50)!")
        return
    
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, target_user_id))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply(f"✅ সফলভাবে ইউজারের ব্যালেন্স আপডেট করে **{new_balance} BDT** করা হয়েছে!")

# ৫. ব্লক / আনব্লক টগল করা
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('toggle_ban_'))
async def toggle_ban_user(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split('_')[2])
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    
    if res:
        new_status = 0 if res[0] == 1 else 1
        cursor.execute('UPDATE users SET is_banned = ? WHERE user_id = ?', (new_status, user_id))
        conn.commit()
    conn.close()
    
    action_name = "আনব্লক" if new_status == 0 else "ব্লক"
    await callback.answer(f"✅ ইউজারকে সফলভাবে {action_name} করা হয়েছে!", show_alert=True)
    
    fake_callback = callback
    fake_callback.data = f"manage_user_{user_id}"
    await manage_user_panel(fake_callback)

@dp.callback_query_handler(text="admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.answer("📢 ব্রডকাস্ট ফিচার প্রস্তুত করা হচ্ছে!", show_alert=True)

@dp.callback_query_handler(text="admin_tasks")
async def admin_tasks(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Add New Task", callback_data="add_task_info"),
        InlineKeyboardButton("📋 View/Delete Tasks", callback_data="view_tasks"),
        InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin")
    )
    await callback.message.edit_text("📝 **টাস্ক ম্যানেজমেন্ট প্যানেল:**", reply_markup=keyboard)

@dp.callback_query_handler(text="add_task_info")
async def add_task_info(callback: types.CallbackQuery):
    await callback.answer("নতুন টাস্ক যোগ করার অপশন চালু হচ্ছে।", show_alert=True)

@dp.callback_query_handler(text="view_tasks")
async def view_tasks(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, reward FROM tasks')
    tasks = cursor.fetchall()
    conn.close()
    
    if not tasks:
        await callback.answer("

import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler

# --- আপনার সঠিক এপিআই টোকেন ---
API_TOKEN = '9256749123:AAE1Tc5c9GExqHivojmtFjb4TBATv3PrgNE' 
ADMIN_ID = 6935814571
WEB_APP_URL = 'https://smia91427-debug.github.io/Amiincome_bot/'
CHANNEL_USERNAME = '@amiofficialchannel'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- ব্লক করা ইউজারদের আটকানোর জন্য মিডলওয়্যার (Middleware) ---
class CheckBanMiddleware(BaseMiddleware):
    async def on_process_message(self, message: types.Message, data: dict):
        if message.from_user.id == ADMIN_ID:
            return
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
        res = cursor.fetchone()
        conn.close()
        
        if res and res[0] == 1:
            await message.answer(
                "⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে। আপনি হয়তো মাল্টি-একাউন্ট করেছেন অথবা নিয়ম ভঙ্গ করেছেন।",
                reply_markup=ReplyKeyboardRemove()
            )
            raise CancelHandler()

    async def on_process_callback_query(self, call: types.CallbackQuery, data: dict):
        if call.from_user.id == ADMIN_ID:
            return
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (call.from_user.id,))
        res = cursor.fetchone()
        conn.close()
        
        if res and res[0] == 1:
            await call.answer("⚠️ আপনাকে এই বট থেকে ব্লক করা হয়েছে!", show_alert=True)
            raise CancelHandler()

dp.middleware.setup(CheckBanMiddleware())

# --- অ্যাডমিন স্টেট ম্যানেজমেন্ট (FSM) ---
class AdminStates(StatesGroup):
    waiting_for_new_balance = State()
    waiting_for_ref_bonus = State()
    waiting_for_broadcast = State()
    waiting_for_task_title = State()
    waiting_for_task_url = State()
    waiting_for_task_reward = State()

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

# --- মূল কিবোর্ড: শুধু Open App এবং Restart বাটন ---
def get_clean_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True, row_width=2)
    keyboard.add(
        KeyboardButton("🚀 Open App", web_app=WebAppInfo(url=WEB_APP_URL)),
        KeyboardButton("🔄 Restart")
    )
    return keyboard

# --- স্টার্ট ও রিস্টার্ট হ্যান্ডেল করার মেইন ফাংশন ---
async def send_welcome_or_subscribe(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user and user[0] == 1:
        conn.close()
        await message.answer(
            "⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে। আপনি হয়তো মাল্টি-একাউন্ট করেছেন অথবা নিয়ম ভঙ্গ করেছেন।", 
            reply_markup=ReplyKeyboardRemove()
        )
        return

    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

    if not await is_subscribed(user_id):
        inline_kb = InlineKeyboardMarkup(row_width=1)
        inline_kb.add(
            InlineKeyboardButton("📢 চ্যানেলে জয়েন করুন", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
            InlineKeyboardButton("✅ ভেরিফাই করুন", callback_data="verify_join")
        )
        await message.answer("⚠️ বটটি ব্যবহার করতে হলে প্রথমে আমাদের অফিসিয়াল চ্যানেলে জয়েন করতে হবে!\n\nদয়া করে নিচের বাটনে ক্লিক করে চ্যানেলে জয়েন করুন এবং তারপর **'ভেরিফাই করুন'** বাটনে ক্লিক করুন:", reply_markup=inline_kb)
        return

    await message.answer(f"হ্যালো {message.from_user.first_name}! আমাদের প্রফেশনাল আর্নিং বটে স্বাগতম। নিচে থেকে অ্যাপ ওপেন করুন বা রিস্টার্ট দিন 👇", reply_markup=get_clean_keyboard())

# --- স্টার্ট কমান্ড ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await send_welcome_or_subscribe(message)

# --- রিস্টার্ট বাটন হ্যান্ডলার ---
@dp.message_handler(lambda message: message.text == "🔄 Restart")
async def handle_restart(message: types.Message):
    await send_welcome_or_subscribe(message)

# --- ভেরিফাই বাটন হ্যান্ডলার ---
@dp.callback_query_handler(text="verify_join")
async def verify_join(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if await is_subscribed(user_id):
        await callback.message.edit_text("✅ ভেরিফিকেশন সফল হয়েছে!")
        await callback.message.answer("কাজ শুরু করতে নিচের বাটনগুলো ব্যবহার করুন 👇", reply_markup=get_clean_keyboard())
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
    await callback.message.edit_text("👥 **রেজিস্টার্ড ইউজারদের তালিকা:** ইউজারের উপর ক্লিক করে কন্ট্রোল করুন:", reply_markup=keyboard)

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
    
    text = f"👤 **ইউজার ডিটেইলস:**\n\n🆔 ID: `{u_id}`\n👤 Username: {uname_str}\n💰 বর্তমান ব্যালেন্স: {balance} BDT\n📌 স্ট্যাটাস: {status_str}"
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✏️ Change Balance", callback_data=f"set_bal_{u_id}")
    )
    
    if is_banned == 1:
        keyboard.add(InlineKeyboardButton("✅ Unblock User", callback_data=f"toggle_ban_{u_id}"))
    else:
        keyboard.add(InlineKeyboardButton("🚫 Block User", callback_data=f"toggle_ban_{u_id}"))
        
    keyboard.add(InlineKeyboardButton("🔙 Back to User List", callback_data="admin_users_list"))
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('set_bal_'))
async def ask_new_balance(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split('_')[2])
    await state.update_data(target_user_id=user_id)
    await AdminStates.waiting_for_new_balance.set()
    
    await callback.message.answer("✍️ এই ইউজারের জন্য নতুন ব্যালেন্স কত করতে চান? (যেমন: 50 বা 100 লিখে পাঠান):")
    await callback.answer()

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
    
    if not target_user_id:
        await message.reply("❌ কোনো ইউজার আইডি পাওয়া যায়নি। দয়া করে আবার চেষ্টা করুন।")
        await state.finish()
        return

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, target_user_id))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply(f"✅ সফলভাবে ইউজারের ব্যালেন্স আপডেট করে **{new_balance} BDT** করা হয়েছে!")

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
    
    if new_status == 1:
        try:
            await bot.send_message(
                user_id, 
                "⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে। আপনি হয়তো মাল্টি-একাউন্ট করেছেন অথবা নিয়ম ভঙ্গ করেছেন।", 
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            logging.error(f"Could not remove keyboard: {e}")
    else:
        try:
            await bot.send_message(
                user_id, 
                "✅ আপনাকে আনব্লক করা হয়েছে! বট ব্যবহার করতে নিচের বাটন ব্যবহার করুন:", 
                reply_markup=get_clean_keyboard()
            )
        except Exception as e:
            logging.error(f"Could not restore keyboard: {e}")

    await callback.answer(f"✅ ইউজারকে সফলভাবে {action_name} করা হয়েছে!", show_alert=True)
    
    fake_callback = callback
    fake_callback.data = f"manage_user_{user_id}"
    await manage_user_panel(fake_callback)

# --- ব্রডকাস্ট ফিচার (Broadcast Feature) ---
@dp.callback_query_handler(text="admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_broadcast.set()
    await callback.message.answer("📢 সব ইউজারের কাছে পাঠানোর জন্য আপনার মেসেজটি (টেক্সট, ছবি বা পোস্ট) এখানে ফরোয়ার্ড বা লিখে পাঠান:")
    await callback.answer()

@dp.message_handler(state=AdminStates.waiting_for_broadcast, content_types=types.ContentTypes.ANY)
async def execute_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    all_users = cursor.fetchall()
    conn.close()
    
    await state.finish()
    sent_count = 0
    blocked_count = 0
    
    status_msg = await message.reply("⏳ ব্রডকাস্ট পাঠানো শুরু হয়েছে, দয়া করে অপেক্ষা করুন...")

    for u in all_users:
        uid = u[0]
        try:
            await message.send_copy(chat_id=uid)
            sent_count += 1
        except Exception:
            blocked_count += 1

    await status_msg.edit_text(f"✅ ব্রডকাস্ট সম্পন্ন!\n\n📤 সফলভাবে পাঠানো হয়েছে: `{sent_count}` জনের কাছে\n❌ ناکام (বট ব্লক করা): `{blocked_count}` জন")

# ==========================================
# --- টাস্ক ম্যানেজমেন্ট (Add & Delete Tasks) ---
# ==========================================

@dp.callback_query_handler(text="admin_tasks")
async def admin_tasks(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Add New Task", callback_data="add_task_start"),
        InlineKeyboardButton("📋 View/Delete Tasks", callback_data="view_tasks"),
        InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin")
    )
    await callback.message.edit_text("📝 **টাস্ক ম্যানেজমেন্ট প্যানেল:**", reply_markup=keyboard)

# ১. নতুন টাস্ক যোগ করার প্রসেস (FSM)
@dp.callback_query_handler(text="add_task_start")
async def add_task_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_task_title.set()
    await callback.message.answer("✍️ নতুন টাস্কের নাম বা টাইটেল (Title) লিখে পাঠান (যেমন: Join YouTube Channel):")
    await callback.answer()

@dp.message_handler(state=AdminStates.waiting_for_task_title)
async def process_task_title(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(task_title=message.text)
    await AdminStates.waiting_for_task_url.set()
    await message.reply("🔗 এখন টাস্কের লিংক বা URL লিখে পাঠান (যেমন: https://t.me/...):")

@dp.message_handler(state=AdminStates.waiting_for_task_url)
async def process_task_url(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(task_url=message.text)
    await AdminStates.waiting_for_task_reward.set()
    await message.reply("💰 টাস্কটি সম্পন্ন করলে ইউজার কত টাকা (Reward) পাবে? শুধু সংখ্যাটি লিখে পাঠান (যেমন: 2 বা 5):")

@dp.message_handler(state=AdminStates.waiting_for_task_reward)
async def process_task_reward(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        reward = float(message.text)
    except ValueError:
        await message.reply("❌ দয়া করে সঠিক সংখ্যা লিখুন (যেমন: 5)! আবার চেষ্টা করুন:")
        return
    
    data = await state.get_data()
    title = data.get('task_title')
    url = data.get('task_url')
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tasks (title, url, reward) VALUES (?, ?, ?)', (title, url, reward))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply(f"✅ সফলভাবে নতুন টাস্ক যোগ করা হয়েছে!\n\n📌 Title: {title}\n🔗 URL: {url}\n💰 Reward: {reward} BDT")

# ২. টাস্ক দেখা এবং ডিলিট করার প্রসেস
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
        await callback.answer("⚠️ কোনো টাস্ক পাওয়া যায়নি!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for t in tasks:
        keyboard.add(
            InlineKeyboardButton(f"❌ ডিলিট: {t[1]} ({t[2]} BDT)", callback_data=f"del_task_{t[0]}")
        )
    keyboard.add(InlineKeyboardButton("🔙 Back to Task Menu", callback_data="admin_tasks"))
    
    await callback.message.edit_text("📋 **বর্তমান টাস্কগুলোর তালিকা:**\n(যেটি ডিলিট করতে চান তার উপর ক্লিক করুন)", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('del_task_'))
async def delete_task_action(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    task_id = int(callback.data.split('_')[2])
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    
    await callback.answer("✅ টাস্কটি সফলভাবে ডিলিট করা হয়েছে!", show_alert=True)
    
    await view_tasks(callback)

# ==========================================
# --- রেফারেল রেট ও অন্যান্য ম্যানেজমেন্ট ---
# ==========================================

@dp.callback_query_handler(text="admin_ref_rate")
async def admin_ref_rate(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'ref_bonus'")
    row = cursor.fetchone()
    current_bonus = row[0] if row else "5.0"
    conn.close()
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✏️ Change Referral Bonus", callback_data="change_ref_bonus"),
        InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin")
    )
    
    await callback.message.edit_text(f"💰 **বর্তমান রেফার বোনাস:** `{current_bonus}` টাকা\n\nপরিবর্তন করতে নিচের বাটনে ক্লিক করুন:", reply_markup=keyboard)

@dp.callback_query_handler(text="change_ref_bonus")
async def ask_new_ref_bonus(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_ref_bonus.set()
    await callback.message.answer("✍️ নতুন রেফার বোনাস কত টাকা করতে চান? শুধু সংখ্যাটি লিখে পাঠান যেমন: 10:")
    await callback.answer()

@dp.message_handler(state=AdminStates.waiting_for_ref_bonus)
async def save_new_ref_bonus(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    new_bonus = message.text.strip()
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ref_bonus', ?)", (new_bonus,))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply(f"✅ সফলভাবে রেফার বোনাস আপডেট করে **{new_bonus} টাকা** করা হয়েছে!")

@dp.callback_query_handler(text="admin_fraud_check")
async def admin_fraud_check(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT device_id, COUNT(DISTINCT user_id) as total_accounts, GROUP_CONCAT(user_id) 
        FROM user_devices 
        GROUP BY device_id 
        HAVING total_accounts > 1
    ''')
    fraud_users = cursor.fetchall()
    conn.close()
    
    if not fraud_users:
        await callback.answer("✅ কোনো মাল্টি-অ্যাকাউন্ট চিটিং পাওয়া যায়নি!", show_alert=True)
        return
    
    text = "🚨 **মাল্টি-অ্যাকাউন্ট ধরা পড়েছে:**\n\n"
    for f in fraud_users:
        text += f"📱 Device: {f[0]}...\n👥 Accounts: {f[1]}টি\n🆔 IDs: {f[2]}\n\n"
    
    await callback.message.edit_text(text)

@dp.callback_query_handler(text="back_admin")
async def back_admin(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 User List", callback_data="admin_users_list"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("📝 Manage Tasks", callback_data="admin_tasks"),
        InlineKeyboardButton("💰 Referral Rate", callback_data="admin_ref_rate"),
        InlineKeyboardButton("🚨 Multi-Account Check", callback_data="admin_fraud_check")
    )
    await callback.message.edit_text("🛠 **অ্যাডমিন প্যানেলে স্বাগতম বস!**", reply_markup=keyboard)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler

# --- আপনার সঠিক এপিআই টোকেন ---
API_TOKEN = '9256749123:AAE1Tc5c9GExqHivojmtFjb4TBATv3PrgNE' 
ADMIN_ID = 6935814571
WEB_APP_URL = 'https://smia91427-debug.github.io/Amiincome_bot/'
CHANNEL_USERNAME = '@amiofficialchannel'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- ব্লক করা ইউজারদের আটকানোর জন্য মিডলওয়্যার (Middleware) ---
class CheckBanMiddleware(BaseMiddleware):
    async def on_process_message(self, message: types.Message, data: dict):
        if message.from_user.id == ADMIN_ID:
            return
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
        res = cursor.fetchone()
        conn.close()
        
        if res and res[0] == 1:
            await message.answer(
                "⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে। আপনি হয়তো মাল্টি-একাউন্ট করেছেন অথবা নিয়ম ভঙ্গ করেছেন।",
                reply_markup=ReplyKeyboardRemove()
            )
            raise CancelHandler()

    async def on_process_callback_query(self, call: types.CallbackQuery, data: dict):
        if call.from_user.id == ADMIN_ID:
            return
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (call.from_user.id,))
        res = cursor.fetchone()
        conn.close()
        
        if res and res[0] == 1:
            await call.answer("⚠️ আপনাকে এই বট থেকে ব্লক করা হয়েছে!", show_alert=True)
            raise CancelHandler()

dp.middleware.setup(CheckBanMiddleware())

# --- অ্যাডমিন স্টেট ম্যানেজমেন্ট (FSM) ---
class AdminStates(StatesGroup):
    waiting_for_new_balance = State()
    waiting_for_ref_bonus = State()
    waiting_for_broadcast = State()
    waiting_for_task_title = State()
    waiting_for_task_url = State()
    waiting_for_task_reward = State()

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

# --- মূল কিবোর্ড: শুধু Open App এবং Restart বাটন ---
def get_clean_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True, row_width=2)
    keyboard.add(
        KeyboardButton("🚀 Open App", web_app=WebAppInfo(url=WEB_APP_URL)),
        KeyboardButton("🔄 Restart")
    )
    return keyboard

# --- স্টার্ট ও রিস্টার্ট হ্যান্ডেল করার মেইন ফাংশন ---
async def send_welcome_or_subscribe(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user and user[0] == 1:
        conn.close()
        await message.answer(
            "⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে। আপনি হয়তো মাল্টি-একাউন্ট করেছেন অথবা নিয়ম ভঙ্গ করেছেন।", 
            reply_markup=ReplyKeyboardRemove()
        )
        return

    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

    if not await is_subscribed(user_id):
        inline_kb = InlineKeyboardMarkup(row_width=1)
        inline_kb.add(
            InlineKeyboardButton("📢 চ্যানেলে জয়েন করুন", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
            InlineKeyboardButton("✅ ভেরিফাই করুন", callback_data="verify_join")
        )
        await message.answer("⚠️ বটটি ব্যবহার করতে হলে প্রথমে আমাদের অফিসিয়াল চ্যানেলে জয়েন করতে হবে!\n\nদয়া করে নিচের বাটনে ক্লিক করে চ্যানেলে জয়েন করুন এবং তারপর **'ভেরিফাই করুন'** বাটনে ক্লিক করুন:", reply_markup=inline_kb)
        return

    await message.answer(f"হ্যালো {message.from_user.first_name}! আমাদের প্রফেশনাল আর্নিং বটে স্বাগতম। নিচে থেকে অ্যাপ ওপেন করুন বা রিস্টার্ট দিন 👇", reply_markup=get_clean_keyboard())

# --- স্টার্ট কমান্ড ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await send_welcome_or_subscribe(message)

# --- রিস্টার্ট বাটন হ্যান্ডলার ---
@dp.message_handler(lambda message: message.text == "🔄 Restart")
async def handle_restart(message: types.Message):
    await send_welcome_or_subscribe(message)

# --- ভেরিফাই বাটন হ্যান্ডলার ---
@dp.callback_query_handler(text="verify_join")
async def verify_join(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if await is_subscribed(user_id):
        await callback.message.edit_text("✅ ভেরিফিকেশন সফল হয়েছে!")
        await callback.message.answer("কাজ শুরু করতে নিচের বাটনগুলো ব্যবহার করুন 👇", reply_markup=get_clean_keyboard())
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
    await callback.message.edit_text("👥 **রেজিস্টার্ড ইউজারদের তালিকা:** ইউজারের উপর ক্লিক করে কন্ট্রোল করুন:", reply_markup=keyboard)

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
    
    text = f"👤 **ইউজার ডিটেইলস:**\n\n🆔 ID: `{u_id}`\n👤 Username: {uname_str}\n💰 বর্তমান ব্যালেন্স: {balance} BDT\n📌 স্ট্যাটাস: {status_str}"
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✏️ Change Balance", callback_data=f"set_bal_{u_id}")
    )
    
    if is_banned == 1:
        keyboard.add(InlineKeyboardButton("✅ Unblock User", callback_data=f"toggle_ban_{u_id}"))
    else:
        keyboard.add(InlineKeyboardButton("🚫 Block User", callback_data=f"toggle_ban_{u_id}"))
        
    keyboard.add(InlineKeyboardButton("🔙 Back to User List", callback_data="admin_users_list"))
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('set_bal_'))
async def ask_new_balance(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split('_')[2])
    await state.update_data(target_user_id=user_id)
    await AdminStates.waiting_for_new_balance.set()
    
    await callback.message.answer("✍️ এই ইউজারের জন্য নতুন ব্যালেন্স কত করতে চান? (যেমন: 50 বা 100 লিখে পাঠান):")
    await callback.answer()

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
    
    if not target_user_id:
        await message.reply("❌ কোনো ইউজার আইডি পাওয়া যায়নি। দয়া করে আবার চেষ্টা করুন।")
        await state.finish()
        return

    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, target_user_id))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply(f"✅ সফলভাবে ইউজারের ব্যালেন্স আপডেট করে **{new_balance} BDT** করা হয়েছে!")

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
    
    if new_status == 1:
        try:
            await bot.send_message(
                user_id, 
                "⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে। আপনি হয়তো মাল্টি-একাউন্ট করেছেন অথবা নিয়ম ভঙ্গ করেছেন।", 
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            logging.error(f"Could not remove keyboard: {e}")
    else:
        try:
            await bot.send_message(
                user_id, 
                "✅ আপনাকে আনব্লক করা হয়েছে! বট ব্যবহার করতে নিচের বাটন ব্যবহার করুন:", 
                reply_markup=get_clean_keyboard()
            )
        except Exception as e:
            logging.error(f"Could not restore keyboard: {e}")

    await callback.answer(f"✅ ইউজারকে সফলভাবে {action_name} করা হয়েছে!", show_alert=True)
    
    fake_callback = callback
    fake_callback.data = f"manage_user_{user_id}"
    await manage_user_panel(fake_callback)

# --- ব্রডকাস্ট ফিচার (Broadcast Feature) ---
@dp.callback_query_handler(text="admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_broadcast.set()
    await callback.message.answer("📢 সব ইউজারের কাছে পাঠানোর জন্য আপনার মেসেজটি (টেক্সট, ছবি বা পোস্ট) এখানে ফরোয়ার্ড বা লিখে পাঠান:")
    await callback.answer()

@dp.message_handler(state=AdminStates.waiting_for_broadcast, content_types=types.ContentTypes.ANY)
async def execute_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    all_users = cursor.fetchall()
    conn.close()
    
    await state.finish()
    sent_count = 0
    blocked_count = 0
    
    status_msg = await message.reply("⏳ ব্রডকাস্ট পাঠানো শুরু হয়েছে, দয়া করে অপেক্ষা করুন...")

    for u in all_users:
        uid = u[0]
        try:
            await message.send_copy(chat_id=uid)
            sent_count += 1
        except Exception:
            blocked_count += 1

    await status_msg.edit_text(f"✅ ব্রডকাস্ট সম্পন্ন!\n\n📤 সফলভাবে পাঠানো হয়েছে: `{sent_count}` জনের কাছে\n❌ ناکام (বট ব্লক করা): `{blocked_count}` জন")

# ==========================================
# --- টাস্ক ম্যানেজমেন্ট (Add & Delete Tasks) ---
# ==========================================

@dp.callback_query_handler(text="admin_tasks")
async def admin_tasks(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Add New Task", callback_data="add_task_start"),
        InlineKeyboardButton("📋 View/Delete Tasks", callback_data="view_tasks"),
        InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin")
    )
    await callback.message.edit_text("📝 **টাস্ক ম্যানেজমেন্ট প্যানেল:**", reply_markup=keyboard)

# ১. নতুন টাস্ক যোগ করার প্রসেস (FSM)
@dp.callback_query_handler(text="add_task_start")
async def add_task_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_task_title.set()
    await callback.message.answer("✍️ নতুন টাস্কের নাম বা টাইটেল (Title) লিখে পাঠান (যেমন: Join YouTube Channel):")
    await callback.answer()

@dp.message_handler(state=AdminStates.waiting_for_task_title)
async def process_task_title(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(task_title=message.text)
    await AdminStates.waiting_for_task_url.set()
    await message.reply("🔗 এখন টাস্কের লিংক বা URL লিখে পাঠান (যেমন: https://t.me/...):")

@dp.message_handler(state=AdminStates.waiting_for_task_url)
async def process_task_url(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(task_url=message.text)
    await AdminStates.waiting_for_task_reward.set()
    await message.reply("💰 টাস্কটি সম্পন্ন করলে ইউজার কত টাকা (Reward) পাবে? শুধু সংখ্যাটি লিখে পাঠান (যেমন: 2 বা 5):")

@dp.message_handler(state=AdminStates.waiting_for_task_reward)
async def process_task_reward(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        reward = float(message.text)
    except ValueError:
        await message.reply("❌ দয়া করে সঠিক সংখ্যা লিখুন (যেমন: 5)! আবার চেষ্টা করুন:")
        return
    
    data = await state.get_data()
    title = data.get('task_title')
    url = data.get('task_url')
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tasks (title, url, reward) VALUES (?, ?, ?)', (title, url, reward))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply(f"✅ সফলভাবে নতুন টাস্ক যোগ করা হয়েছে!\n\n📌 Title: {title}\n🔗 URL: {url}\n💰 Reward: {reward} BDT")

# ২. টাস্ক দেখা এবং ডিলিট করার প্রসেস
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
        await callback.answer("⚠️ কোনো টাস্ক পাওয়া যায়নি!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for t in tasks:
        keyboard.add(
            InlineKeyboardButton(f"❌ ডিলিট: {t[1]} ({t[2]} BDT)", callback_data=f"del_task_{t[0]}")
        )
    keyboard.add(InlineKeyboardButton("🔙 Back to Task Menu", callback_data="admin_tasks"))
    
    await callback.message.edit_text("📋 **বর্তমান টাস্কগুলোর তালিকা:**\n(যেটি ডিলিট করতে চান তার উপর ক্লিক করুন)", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('del_task_'))
async def delete_task_action(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    task_id = int(callback.data.split('_')[2])
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    
    await callback.answer("✅ টাস্কটি সফলভাবে ডিলিট করা হয়েছে!", show_alert=True)
    
    await view_tasks(callback)

# ==========================================
# --- রেফারেল রেট ও অন্যান্য ম্যানেজমেন্ট ---
# ==========================================

@dp.callback_query_handler(text="admin_ref_rate")
async def admin_ref_rate(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'ref_bonus'")
    row = cursor.fetchone()
    current_bonus = row[0] if row else "5.0"
    conn.close()
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✏️ Change Referral Bonus", callback_data="change_ref_bonus"),
        InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin")
    )
    
    await callback.message.edit_text(f"💰 **বর্তমান রেফার বোনাস:** `{current_bonus}` টাকা\n\nপরিবর্তন করতে নিচের বাটনে ক্লিক করুন:", reply_markup=keyboard)

@dp.callback_query_handler(text="change_ref_bonus")
async def ask_new_ref_bonus(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_ref_bonus.set()
    await callback.message.answer("✍️ নতুন রেফার বোনাস কত টাকা করতে চান? শুধু সংখ্যাটি লিখে পাঠান যেমন: 10:")
    await callback.answer()

@dp.message_handler(state=AdminStates.waiting_for_ref_bonus)
async def save_new_ref_bonus(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    new_bonus = message.text.strip()
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ref_bonus', ?)", (new_bonus,))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply(f"✅ সফলভাবে রেফার বোনাস আপডেট করে **{new_bonus} টাকা** করা হয়েছে!")

@dp.callback_query_handler(text="admin_fraud_check")
async def admin_fraud_check(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT device_id, COUNT(DISTINCT user_id) as total_accounts, GROUP_CONCAT(user_id) 
        FROM user_devices 
        GROUP BY device_id 
        HAVING total_accounts > 1
    ''')
    fraud_users = cursor.fetchall()
    conn.close()
    
    if not fraud_users:
        await callback.answer("✅ কোনো মাল্টি-অ্যাকাউন্ট চিটিং পাওয়া যায়নি!", show_alert=True)
        return
    
    text = "🚨 **মাল্টি-অ্যাকাউন্ট ধরা পড়েছে:**\n\n"
    for f in fraud_users:
        text += f"📱 Device: {f[0]}...\n👥 Accounts: {f[1]}টি\n🆔 IDs: {f[2]}\n\n"
    
    await callback.message.edit_text(text)

@dp.callback_query_handler(text="back_admin")
async def back_admin(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 User List", callback_data="admin_users_list"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("📝 Manage Tasks", callback_data="admin_tasks"),
        InlineKeyboardButton("💰 Referral Rate", callback_data="admin_ref_rate"),
        InlineKeyboardButton("🚨 Multi-Account Check", callback_data="admin_fraud_check")
    )
    await callback.message.edit_text("🛠 **অ্যাডমিন প্যানেলে স্বাগতম বস!**", reply_markup=keyboard)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

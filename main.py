import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler

API_TOKEN = '9256749123:AAE1Tc5c9GExqHivojmtFjb4TBATv3PrgNE' 
ADMIN_ID = 6935814571
WEB_APP_URL = 'https://smia91427-debug.github.io/Amiincome_bot/'
CHANNEL_USERNAME = '@amiofficialchannel'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

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
            await message.answer("⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে।", reply_markup=ReplyKeyboardRemove())
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

class AdminStates(StatesGroup):
    waiting_for_new_balance = State()
    waiting_for_ref_bonus = State()
    waiting_for_broadcast = State()
    waiting_for_task_url = State()
    waiting_for_notice = State()

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
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_bonus', '5.0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('notice', '📢 স্বাগতম AMI Income এ! প্রতিদিন নিয়মিত অ্যাড দেখে আয় করুন।')")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            method TEXT,
            number TEXT,
            amount REAL,
            status TEXT DEFAULT 'Pending',
            time TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logging.error(f"Subscription check error: {e}")
    return False

def get_clean_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True, row_width=2)
    keyboard.add(
        KeyboardButton("🚀 Open App", web_app=WebAppInfo(url=WEB_APP_URL)),
        KeyboardButton("🔄 Restart")
    )
    return keyboard

async def send_welcome_or_subscribe(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

    if not await is_subscribed(user_id):
        inline_kb = InlineKeyboardMarkup(row_width=1)
        inline_kb.add(
            InlineKeyboardButton("📢 চ্যানেলে জয়েন করুন", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
            InlineKeyboardButton("✅ ভেরিফাই করুন", callback_data="verify_join")
        )
        await message.answer("⚠️ বটটি ব্যবহার করতে হলে প্রথমে আমাদের অফিসিয়াল চ্যানেলে জয়েন করতে হবে!", reply_markup=inline_kb)
        return

    await message.answer(f"হ্যালো {message.from_user.first_name}! আমাদের প্রফেশনাল আর্নিং বটে স্বাগতম 👇", reply_markup=get_clean_keyboard())

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await send_welcome_or_subscribe(message)

@dp.message_handler(lambda message: message.text == "🔄 Restart")
async def handle_restart(message: types.Message):
    await send_welcome_or_subscribe(message)

@dp.callback_query_handler(text="verify_join")
async def verify_join(callback: types.CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.edit_text("✅ ভেরিফিকেশন সফল হয়েছে!")
        await callback.message.answer("কাজ শুরু করতে নিচের বাটনগুলো ব্যবহার করুন 👇", reply_markup=get_clean_keyboard())
    else:
        await callback.answer("❌ আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)

# ==========================================
# --- অ্যাডমিন প্যানেল (Admin Panel) ---
# ==========================================

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 User List", callback_data="admin_users_list"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("💰 Withdraw Review", callback_data="admin_withdraws"),
        InlineKeyboardButton("🔔 Change Notice", callback_data="admin_change_notice"),
        InlineKeyboardButton("📝 Manage Tasks", callback_data="admin_tasks"),
        InlineKeyboardButton("💳 Referral Rate", callback_data="admin_ref_rate")
    )
    await message.reply("🛠 **প্রফেশনাল অ্যাডমিন প্যানেল:**", reply_markup=keyboard)

# 1. Withdraw Review System
@dp.callback_query_handler(text="admin_withdraws")
async def admin_withdraws(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, method, number, amount, status, time FROM withdrawals WHERE status = "Pending"')
    withdraws = cursor.fetchall()
    conn.close()
    
    if not withdraws:
        await callback.answer("⚠️ কোনো পেন্ডিং উইথড্র নেই!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for w in withdraws:
        w_id, u_id, method, num, amt, status, t = w
        keyboard.add(
            InlineKeyboardButton(f"💳 {method.upper()} | ৳{amt} | {num}", callback_data=f"review_w_{w_id}")
        )
    keyboard.add(InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin"))
    await callback.message.edit_text("💳 **পেন্ডিং উইথড্র রিকোয়েস্টসমূহ:**", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('review_w_'))
async def review_withdraw_item(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    w_id = int(callback.data.split('_')[2])
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, method, number, amount, time FROM withdrawals WHERE id = ?', (w_id,))
    w = cursor.fetchone()
    conn.close()
    
    if not w:
        await callback.answer("⚠️ রিকোয়েস্টটি পাওয়া যায়নি!", show_alert=True)
        return
    
    text = f"💳 **উইথড্র রিকোয়েস্ট ডিটেইলস:**\n\n🆔 User ID: `{w[1]}`\n📱 Method: {w[2].upper()}\n📞 Number: `{w[3]}`\n💰 Amount: ৳{w[4]}\n🕒 Time: {w[5]}"
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"app_w_{w[0]}_{w[1]}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"rej_w_{w[0]}_{w[1]}")
    )
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="admin_withdraws"))
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data and (c.data.startswith('app_w_') or c.data.startswith('rej_w_')))
async def action_withdraw(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    parts = callback.data.split('_')
    action = parts[0]
    w_id = int(parts[2])
    target_user_id = int(parts[3])
    
    new_status = 'Approved' if action == 'app' else 'Rejected'
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE withdrawals SET status = ? WHERE id = ?', (new_status, w_id))
    conn.commit()
    conn.close()
    
    try:
        if new_status == 'Approved':
            await bot.send_message(target_user_id, "✅ অভিনন্দন! আপনার উইথড্র রিকোয়েস্টটি **Approved** করা হয়েছে এবং পেমেন্ট পাঠিয়ে দেওয়া হয়েছে।")
        else:
            await bot.send_message(target_user_id, "❌ দুঃখিত, আপনার উইথড্র রিকোয়েস্টটি রিজেক্ট করা হয়েছে।")
    except Exception:
        pass

    await callback.answer(f"✅ সফলভাবে উইথড্র {new_status} করা হয়েছে!", show_alert=True)
    await admin_withdraws(callback)

# 2. Change Notice System
@dp.callback_query_handler(text="admin_change_notice")
async def admin_change_notice(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_notice.set()
    await callback.message.answer("✍️ মিনি অ্যাপে দেখানোর জন্য নতুন নোটিশটি লিখে পাঠান:")
    await callback.answer()

@dp.message_handler(state=AdminStates.waiting_for_notice)
async def save_new_notice(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    new_notice = message.text.strip()
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('notice', ?)", (new_notice,))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply("✅ সফলভাবে নতুন নোটিশ আপডেট করা হয়েছে!")

# 3. Manage Tasks (Ad Tasks 1 to 4)
@dp.callback_query_handler(text="admin_tasks")
async def admin_tasks(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📺 Ad Task 1 লিংক পরিবর্তন", callback_data="edit_task_1"),
        InlineKeyboardButton("📺 Ad Task 2 লিংক পরিবর্তন", callback_data="edit_task_2"),
        InlineKeyboardButton("📺 Ad Task 3 লিংক পরিবর্তন", callback_data="edit_task_3"),
        InlineKeyboardButton("📺 Ad Task 4 লিংক পরিবর্তন", callback_data="edit_task_4"),
        InlineKeyboardButton("🔙 Back to Admin", callback_data="back_admin")
    )
    await callback.message.edit_text("📝 **অ্যাড টাস্ক ম্যানেজমেন্ট প্যানেল:**\nকোন টাস্কটির লিংক পরিবর্তন করতে চান তা সিলেক্ট করুন:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('edit_task_'))
async def edit_task_link_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    task_num = callback.data.split('_')[2]
    await state.update_data(current_task_num=task_num)
    await AdminStates.waiting_for_task_url.set()
    
    await callback.message.answer(f"✍️ **Ad Task {task_num}** এর জন্য নতুন অ্যাড নেটওয়ার্কের লিংক (URL) লিখে পাঠান:")
    await callback.answer()

@dp.message_handler(state=AdminStates.waiting_for_task_url)
async def save_ad_task_url(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    new_url = message.text.strip()
    data = await state.get_data()
    task_num = data.get('current_task_num', '1')
    
    task_key = f"ad_task_{task_num}_url"
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (task_key, new_url))
    conn.commit()
    conn.close()
    
    await state.finish()
    await message.reply(f"✅ সফলভাবে সাবমিট হয়ে গেছে! Ad Task {task_num}-এর নতুন লিংক আপডেট করা হয়েছে:\n`{new_url}`", parse_mode="Markdown")

# User List & Broadcast
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
        await callback.answer("⚠️ কোনো ইউজার নেই!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for u in users:
        uname = f"@{u[1]}" if u[1] else f"ID: {u[0]}"
        keyboard.add(InlineKeyboardButton(f"{uname} (Bal: {u[2]} BDT)", callback_data=f"manage_user_{u[0]}"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="back_admin"))
    await callback.message.edit_text("👥 ইউজার তালিকা:", reply_markup=keyboard)

@dp.callback_query_handler(text="admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await AdminStates.waiting_for_broadcast.set()
    await callback.message.answer("📢 ব্রডকাস্ট করার মেসেজটি পাঠান:")
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
    
    sent = 0
    for u in all_users:
        try:
            await message.send_copy(chat_id=u[0])
            sent += 1
        except Exception:
            pass
    await message.reply(f"✅ সফলভাবে {sent} জনের কাছে পাঠানো হয়েছে!")

@dp.callback_query_handler(text="back_admin")
async def back_admin(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👥 User List", callback_data="admin_users_list"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("💰 Withdraw Review", callback_data="admin_withdraws"),
        InlineKeyboardButton("🔔 Change Notice", callback_data="admin_change_notice"),
        InlineKeyboardButton("📝 Manage Tasks", callback_data="admin_tasks"),
        InlineKeyboardButton("💳 Referral Rate", callback_data="admin_ref_rate")
    )
    await callback.message.edit_text("🛠 **অ্যাডমিন প্যানেল:**", reply_markup=keyboard)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

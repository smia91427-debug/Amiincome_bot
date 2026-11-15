import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

API_TOKEN = '9256749123:AAFe4PIUr_LR0esudKZUL4Ro5_MHAEJQJ7o' 
ADMIN_ID = 6935814571
WEB_APP_URL = 'https://smia91427-debug.github.io/Amiincome_bot/'
CHANNEL_USERNAME = '@amiofficialchannel'  # আপনার অফিশিয়াল চ্যানেলের ইউজারনেম এখানে বসাবেন

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- ডেটাবেজ এবং টেবিল ইনিশিয়ালাইজেশন ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # ইউজার টেবিল (ব্লক স্ট্যাটাসসহ)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0
        )
    ''')
    
    # টাস্ক টেবিল
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            reward REAL
        )
    ''')
    
    # সেটিংস টেবিল (রেফার কমিশন)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ref_bonus', '5.0')")
    
    # মাল্টি-অ্যাকাউন্ট ট্র্যাক করার ডিভাইস টেবিল
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
    
    # ইউজার ব্লক করা আছে কি না চেক
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user and user[0] == 1:
        conn.close()
        await message.answer("⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে!")
        return

    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

    # চ্যানেল জয়েন করেছে কি না চেক করা
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

    # চ্যানেলে জয়েন করা থাকলে শুধু ক্লিন "Open" বাটন দেখাবে
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🚀 Open", web_app=WebAppInfo(url=WEB_APP_URL))
    )

    await message.answer(
        f"হ্যালো {message.from_user.first_name}! আমাদের প্রফেশনাল আর্নিং বটে স্বাগতম।",
        reply_markup=keyboard
    )

# --- ভেরিফাই বাটন হ্যান্ডলার ---
@dp.callback_query_handler(text="verify_join")
async def verify_join(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if await is_subscribed(user_id):
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("🚀 Open", web_app=WebAppInfo(url=WEB_APP_URL))
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
        InlineKeyboardButton("📊 Total Users", callback_data="admin_stats"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("📝 Manage Tasks", callback_data="admin_tasks"),
        InlineKeyboardButton("💰 Referral Rate", callback_data="admin_ref_rate"),
        InlineKeyboardButton("🚨 Multi-Account Check", callback_data="admin_fraud_check")
    )
    
    await message.reply("🛠 **প্রফেশনাল অ্যাডমিন প্যানেলে স্বাগতম বস!**\nনিচের অপশনগুলো থেকে সিলেক্ট করুন:", reply_markup=keyboard)

# ১. মোট ইউজার দেখা
@dp.callback_query_handler(text="admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    conn.close()
    
    await callback.answer(f"📊 বটের মোট রেজিস্টার্ড ইউজার: {total_users} জন", show_alert=True)

# ২. ব্রডকাস্ট
@dp.callback_query_handler(text="admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.answer("📢 ব্রডকাস্ট ফিচার প্রস্তুত করা হচ্ছে!", show_alert=True)

# ৩. টাস্ক ম্যানেজমেন্ট মেনু
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
        await callback.answer("⚠️ কোনো টাস্ক পাওয়া যায়নি!", show_alert=True)
        return
    
    text = "📋 **বর্তমান টাস্কগুলোর তালিকা:**\n\n"
    for t in tasks:
        text += f"ID: {t[0]} | Title: {t[1]} | Reward: {t[2]} BDT\n"
    
    await callback.message.edit_text(text)

# ৪. রেফারেল রেট চেক
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
    
    await callback.answer(f"💰 বর্তমান রেফার বোনাস: {current_bonus} টাকা", show_alert=True)

# ৫. মাল্টি-অ্যাকাউন্ট চেক
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

# ব্যাক বাটন
@dp.callback_query_handler(text="back_admin")
async def back_admin(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Total Users", callback_data="admin_stats"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("📝 Manage Tasks", callback_data="admin_tasks"),
        InlineKeyboardButton("💰 Referral Rate", callback_data="admin_ref_rate"),
        InlineKeyboardButton("🚨 Multi-Account Check", callback_data="admin_fraud_check")
    )
    await callback.message.edit_text("🛠 **অ্যাডমিন প্যানেলে স্বাগতম বস!**", reply_markup=keyboard)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

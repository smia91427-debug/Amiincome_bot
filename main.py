import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# আপনার বটের টোকেন এবং অ্যাডমিন আইডি এখানে বসাবেন
API_TOKEN = 'YOUR_BOT_TOKEN_HERE'
ADMIN_ID = 123456789  # আপনার টেলিগ্রাম আইডি এখানে দেবেন

# মিনি-অ্যাপের গিটহ্যাব বা হোস্টিং লিংক এখানে বসাবেন
WEB_APP_URL = 'https://your-github-page-url.com'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- ডেটাবেজ ইনিশিয়ালাইজেশন ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- স্টার্ট কমান্ড ও মিনি-অ্যাপ বাটন ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

    keyboard = InlineKeyboardMarkup(row_width=1)
    # মিনি অ্যাপ ওপেন করার বাটন
    keyboard.add(
        InlineKeyboardButton("🚀 Open Earn App", web_app=WebAppInfo(url=WEB_APP_URL)),
        InlineKeyboardButton("📢 Official Channel", url="https://t.me/YourChannel")
    )

    await message.answer(
        f"হ্যালো {message.from_user.first_name}! আমাদের প্রফেশনাল আর্নিং বটে স্বাগতম।\nনিচের বাটনে ক্লিক করে কাজ শুরু করুন:",
        reply_markup=keyboard
    )

# ==========================================
# --- সিক্রেট অ্যাডমিন প্যানেল (Admin Panel) ---
# ==========================================

@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⚠️ আপনার এই প্যানেল ব্যবহার করার অনুমতি নেই!")
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Total Users", callback_data="admin_stats"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
    )
    
    await message.reply("🛠 **অ্যাডমিন প্যানেলে স্বাগতম বস!**", reply_markup=keyboard)

@dp.callback_query_handler(text="admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    conn.close()
    
    await callback.answer(f"বটের মোট রেজিস্টার্ড ইউজার: {total_users} জন", show_alert=True)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

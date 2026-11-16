import logging
import sqlite3
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
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
        await message.answer("⚠️ দুঃখিত, আপনাকে এই বট থেকে ব্লক করা হয়েছে!")
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
        await message.answer(
            "⚠️ বটটি ব্যবহার করতে হলে প্রথমে আমাদের অফিসিয়াল চ্যানেলে জয়েন করতে হবে!\n\nদয়া করে নিচের বাটনে ক্লিক করে চ্যানেলে জয়েন করুন এবং তারপর **'ভেরিফাই করুন'** বাটনে ক্লিক করুন:",
            reply_markup=inline_kb
        )
        return

    await message.answer(
        f"হ্যালো {message.from_user.first_name}! আমাদের প্রফেশনাল আর্নিং বটে স্বাগতম। নিচে থেকে অ্যাপ ওপেন করুন বা রিস্টার্ট দিন 👇",
        reply_markup=get_clean_keyboard()
    )

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
        await callback.message.answer(
            "কাজ শুরু করতে নিচের বাটনগুলো ব্যবহার করুন 👇",
            reply_markup=get_clean_keyboard()
        )
    else:
        await callback.answer("❌ আপনি এখনো আমাদের চ্যানেলে জয়েন করেননি! দয়া করে আগে চ্যানেলে জয়েন

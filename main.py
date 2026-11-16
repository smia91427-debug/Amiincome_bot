import logging
import sqlite3
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler

API_TOKEN = '9256749123:AAFe4PIUr_LR0esudKZUL4Ro5_MHAEJQJ7o' 
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
    
    cursor.execute('SELECT is

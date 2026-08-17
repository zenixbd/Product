import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Token
TOKEN = "8852119659:AAGVte4r5e3T5iCA6-4bJNfsWp-Wp1L1ykM"  # আপনার বট টোকেন দিন

# Admin Password
ADMIN_PASSWORD = "01328724002"

# Conversation States
ADMIN_PASSWORD_CHECK = 1
ADD_PRODUCT_NAME = 2
ADD_PRODUCT_DESCRIPTION = 3
ADD_PRODUCT_PRICE = 4
ADD_PRODUCT_STOCK = 5
ADD_PRODUCT_CATEGORY = 6
PAYMENT_CONFIRM = 7
UPDATE_BIKASH_NUMBER = 8

# Database setup
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.setup()
    
    def setup(self):
        # Users table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_date TEXT,
                balance INTEGER DEFAULT 0
            )
        ''')
        
        # Products table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                stock INTEGER DEFAULT 0,
                category TEXT DEFAULT 'general',
                created_at TEXT
            )
        ''')
        
        # Admin sessions table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_sessions (
                user_id INTEGER PRIMARY KEY,
                is_logged_in INTEGER DEFAULT 0,
                login_time TEXT
            )
        ''')
        
        # Settings table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Orders table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                product_name TEXT,
                price REAL,
                payment_method TEXT,
                payment_number TEXT,
                transaction_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        ''')
        
        # Default Bikash number
        self.cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) VALUES ('bikash_number', '01700000000')
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
    
    def check_admin_login(self, user_id):
        self.cursor.execute('SELECT is_logged_in FROM admin_sessions WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    def set_admin_login(self, user_id, status):
        self.cursor.execute('''
            INSERT OR REPLACE INTO admin_sessions (user_id, is_logged_in, login_time)
            VALUES (?, ?, ?)
        ''', (user_id, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
    
    def add_product(self, name, description, price, stock, category):
        self.cursor.execute('''
            INSERT INTO products (name, description, price, stock, category, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, price, stock, category, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_all_products(self):
        self.cursor.execute('SELECT * FROM products ORDER BY id DESC')
        return self.cursor.fetchall()
    
    def get_products_by_category(self, category):
        self.cursor.execute('SELECT * FROM products WHERE category = ? ORDER BY id DESC', (category,))
        return self.cursor.fetchall()
    
    def get_categories(self):
        self.cursor.execute('SELECT DISTINCT category FROM products')
        return [row[0] for row in self.cursor.fetchall()]
    
    def get_product(self, product_id):
        self.cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        return self.cursor.fetchone()
    
    def delete_product(self, product_id):
        self.cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        self.conn.commit()
    
    def get_bikash_number(self):
        self.cursor.execute("SELECT value FROM settings WHERE key = 'bikash_number'")
        result = self.cursor.fetchone()
        return result[0] if result else "01700000000"
    
    def update_bikash_number(self, number):
        self.cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value) VALUES ('bikash_number', ?)
        ''', (number,))
        self.conn.commit()
    
    def add_order(self, user_id, product_id, product_name, price, payment_method, payment_number, transaction_id):
        self.cursor.execute('''
            INSERT INTO orders (user_id, product_id, product_name, price, payment_method, payment_number, transaction_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, product_id, product_name, price, payment_method, payment_number, transaction_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_orders(self, user_id=None):
        if user_id:
            self.cursor.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id,))
        else:
            self.cursor.execute('SELECT * FROM orders ORDER BY id DESC')
        return self.cursor.fetchall()

db = Database()

# ==================== KEYBOARDS ====================

def main_keyboard():
    """ইউজার মেইন কিবোর্ড"""
    keyboard = [
        [
            InlineKeyboardButton("👤 প্রোফাইল", callback_data='profile'),
            InlineKeyboardButton("🛍 আইটেম মেনু", callback_data='item_menu')
        ],
        [
            InlineKeyboardButton("💰 ওয়ালেট", callback_data='wallet'),
            InlineKeyboardButton("📦 আমার অর্ডার", callback_data='my_orders')
        ],
        [
            InlineKeyboardButton("🔐 অ্যাডমিন", callback_data='admin_login')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def item_menu_keyboard():
    """আইটেম মেনু কিবোর্ড - ক্যাটাগরি অনুযায়ী"""
    keyboard = [
        [
            InlineKeyboardButton("🎮 গেম আইটেম", callback_data='category_game'),
            InlineKeyboardButton("📱 মোবাইল", callback_data='category_mobile')
        ],
        [
            InlineKeyboardButton("💻 কম্পিউটার", callback_data='category_computer'),
            InlineKeyboardButton("👕 কাপড়", callback_data='category_clothing')
        ],
        [
            InlineKeyboardButton("🍔 খাবার", callback_data='category_food'),
            InlineKeyboardButton("📦 অন্যান্য", callback_data='category_general')
        ],
        [
            InlineKeyboardButton("🔙 মেইন মেনু", callback_data='main_menu')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def products_by_category_keyboard(category):
    """ক্যাটাগরি অনুযায়ী প্রোডাক্ট কিবোর্ড"""
    products = db.get_products_by_category(category)
    keyboard = []
    for product in products:
        keyboard.append([
            InlineKeyboardButton(f"📦 {product[1]} - {product[3]}৳", callback_data=f'view_{product[0]}')
        ])
    keyboard.append([InlineKeyboardButton("🔙 আইটেম মেনু", callback_data='item_menu')])
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard():
    """অ্যাডমিন কিবোর্ড"""
    keyboard = [
        [
            InlineKeyboardButton("➕ প্রোডাক্ট যোগ", callback_data='add_product'),
            InlineKeyboardButton("📋 প্রোডাক্ট লিস্ট", callback_data='admin_products')
        ],
        [
            InlineKeyboardButton("📱 বিকাশ নাম্বার", callback_data='bikash_number'),
            InlineKeyboardButton("📊 অর্ডার লিস্ট", callback_data='orders_list')
        ],
        [
            InlineKeyboardButton("🔙 মেইন মেনু", callback_data='main_menu')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def category_select_keyboard():
    """প্রোডাক্ট যোগের সময় ক্যাটাগরি সিলেক্ট"""
    keyboard = [
        [
            InlineKeyboardButton("🎮 গেম", callback_data='cat_game'),
            InlineKeyboardButton("📱 মোবাইল", callback_data='cat_mobile')
        ],
        [
            InlineKeyboardButton("💻 কম্পিউটার", callback_data='cat_computer'),
            InlineKeyboardButton("👕 কাপড়", callback_data='cat_clothing')
        ],
        [
            InlineKeyboardButton("🍔 খাবার", callback_data='cat_food'),
            InlineKeyboardButton("📦 অন্যান্য", callback_data='cat_general')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টার্ট কমান্ড"""
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""
╔══════════════════════╗
   🤖 স্বাগতম {user.first_name}!
╚══════════════════════╝

আমি আপনার শপিং বট।
আইটেম কিনতে নিচের বাটন চাপুন 👇
    """
    
    await update.message.reply_text(welcome_text, reply_markup=main_keyboard())

async def item_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """আইটেম মেনু দেখান"""
    categories = db.get_categories()
    
    menu_text = "🛍 **আইটেম মেনু**\n\n"
    menu_text += "ক্যাটাগরি নির্বাচন করুন:\n"
    
    await update.message.reply_text(
        menu_text,
        reply_markup=item_menu_keyboard(),
        parse_mode='Markdown'
    )

async def show_category_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ক্যাটাগরি অনুযায়ী প্রোডাক্ট দেখান"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.split('_')[1]
    products = db.get_products_by_category(category)
    
    if products:
        category_names = {
            'game': '🎮 গেম আইটেম',
            'mobile': '📱 মোবাইল',
            'computer': '💻 কম্পিউটার',
            'clothing': '👕 কাপড়',
            'food': '🍔 খাবার',
            'general': '📦 অন্যান্য'
        }
        
        await query.message.reply_text(
            f"{category_names.get(category, '📦 প্রোডাক্ট')}\n\n"
            f"প্রোডাক্ট দেখতে বাটনে চাপুন:",
            reply_markup=products_by_category_keyboard(category)
        )
    else:
        await query.message.reply_text(
            "❌ এই ক্যাটাগরিতে কোনো প্রোডাক্ট নেই!",
            reply_markup=item_menu_keyboard()
        )

async def view_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """প্রোডাক্ট বিস্তারিত দেখান"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split('_')[1])
    product = db.get_product(product_id)
    
    if product:
        category_names = {
            'game': '🎮 গেম',
            'mobile': '📱 মোবাইল',
            'computer': '💻 কম্পিউটার',
            'clothing': '👕 কাপড়',
            'food': '🍔 খাবার',
            'general': '📦 অন্যান্য'
        }
        
        buy_keyboard = [
            [InlineKeyboardButton("🛒 কিনুন", callback_data=f'buy_{product_id}')],
            [InlineKeyboardButton("🔙 আইটেম মেনু", callback_data='item_menu')]
        ]
        
        product_details = f"""
📦 **{product[1]}**

📂 ক্যাটাগরি: {category_names.get(product[5], '📦 অন্যান্য')}
📝 বিবরণ: {product[2]}
💰 দাম: {product[3]}৳
📊 স্টক: {product[4]} টি
🆔 ID: {product[0]}
        """
        
        await query.message.reply_text(
            product_details,
            reply_markup=InlineKeyboardMarkup(buy_keyboard),
            parse_mode='Markdown'
        )

async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """প্রোডাক্ট কেনা"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split('_')[1])
    product = db.get_product(product_id)
    
    if product:
        context.user_data['buying_product_id'] = product_id
        context.user_data['buying_product_name'] = product[1]
        context.user_data['buying_product_price'] = product[3]
        
        payment_keyboard = [
            [InlineKeyboardButton("📱 বিকাশ", callback_data='pay_bikash')],
            [InlineKeyboardButton("💵 নগদ", callback_data='pay_nagad')],
            [InlineKeyboardButton("🔙 ব্যাক", callback_data=f'view_{product_id}')]
        ]
        
        await query.message.reply_text(
            f"🛒 **প্রোডাক্ট কিনুন**\n\n"
            f"📦 প্রোডাক্ট: {product[1]}\n"
            f"💰 দাম: {product[3]}৳\n\n"
            f"পেমেন্ট মেথড নির্বাচন করুন:",
            reply_markup=InlineKeyboardMarkup(payment_keyboard),
            parse_mode='Markdown'
        )

async def payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """পেমেন্ট মেথড"""
    query = update.callback_query
    await query.answer()
    
    method = query.data.split('_')[1]
    context.user_data['payment_method'] = method
    
    if method == 'bikash':
        number = db.get_bikash_number()
        await query.message.reply_text(
            f"📱 **বিকাশ পেমেন্ট**\n\n"
            f"💰 টাকা পাঠান: {context.user_data['buying_product_price']}৳\n"
            f"📱 বিকাশ নাম্বার: {number}\n\n"
            f"পেমেন্ট করে Transaction ID লিখুন:",
            parse_mode='Markdown'
        )
        return PAYMENT_CONFIRM
    elif method == 'nagad':
        await query.message.reply_text(
            f"💵 **নগদ পেমেন্ট**\n\n"
            f"💰 টাকা পাঠান: {context.user_data['buying_product_price']}৳\n"
            f"📱 নগদ নাম্বার: 01700000000\n\n"
            f"পেমেন্ট করে Transaction ID লিখুন:",
            parse_mode='Markdown'
        )
        return PAYMENT_CONFIRM

async def payment_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """পেমেন্ট কনফার্ম"""
    transaction_id = update.message.text
    
    user_id = update.effective_user.id
    product_id = context.user_data.get('buying_product_id')
    product_name = context.user_data.get('buying_product_name')
    price = context.user_data.get('buying_product_price')
    payment_method = context.user_data.get('payment_method', 'bikash')
    
    order_id = db.add_order(
        user_id, product_id, product_name, price, payment_method,
        db.get_bikash_number(), transaction_id
    )
    
    await update.message.reply_text(
        f"✅ **অর্ডার সফল!**\n\n"
        f"🆔 অর্ডার ID: {order_id}\n"
        f"📦 প্রোডাক্ট: {product_name}\n"
        f"💰 দাম: {price}৳\n"
        f"📱 পেমেন্ট: {payment_method}\n"
        f"🔢 Transaction ID: {transaction_id}\n\n"
        f"⏳ অ্যাডমিন কনফার্ম করলে প্রোডাক্ট পাঠানো হবে।",
        parse_mode='Markdown',
        reply_markup=main_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ADMIN FUNCTIONS ====================

async def admin_login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """অ্যাডমিন লগইন"""
    user_id = update.effective_user.id
    
    if db.check_admin_login(user_id):
        await update.message.reply_text(
            "✅ আপনি লগইন আছেন!",
            reply_markup=admin_keyboard()
        )
        return ConversationHandler.END
    
    await update.message.reply_text("🔐 পাসওয়ার্ড লিখুন:")
    return ADMIN_PASSWORD_CHECK

async def admin_login_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """পাসওয়ার্ড চেক"""
    password = update.message.text
    
    if password == ADMIN_PASSWORD:
        user_id = update.effective_user.id
        db.set_admin_login(user_id, 1)
        
        await update.message.reply_text(
            "✅ লগইন সফল!",
            reply_markup=admin_keyboard()
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ ভুল পাসওয়ার্ড! আবার চেষ্টা করুন:")
        return ADMIN_PASSWORD_CHECK

async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """প্রোডাক্ট যোগ শুরু"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if db.check_admin_login(user_id):
        await query.message.reply_text("📦 প্রোডাক্টের নাম লিখুন:")
        return ADD_PRODUCT_NAME
    else:
        await query.message.reply_text("❌ আগে লগইন করুন!")
        return ConversationHandler.END

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_name'] = update.message.text
    await update.message.reply_text("📝 প্রোডাক্টের বিবরণ লিখুন:")
    return ADD_PRODUCT_DESCRIPTION

async def add_product_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_description'] = update.message.text
    await update.message.reply_text("💰 প্রোডাক্টের দাম লিখুন:")
    return ADD_PRODUCT_PRICE

async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['product_price'] = price
        await update.message.reply_text("📊 স্টক সংখ্যা লিখুন:")
        return ADD_PRODUCT_STOCK
    except ValueError:
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন!")
        return ADD_PRODUCT_PRICE

async def add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text)
        context.user_data['product_stock'] = stock
        await update.message.reply_text(
            "📂 ক্যাটাগরি নির্বাচন করুন:",
            reply_markup=category_select_keyboard()
        )
        return ADD_PRODUCT_CATEGORY
    except ValueError:
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন!")
        return ADD_PRODUCT_STOCK

async def add_product_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ক্যাটাগরি সিলেক্ট"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.split('_')[1]
    context.user_data['product_category'] = category
    
    product_id = db.add_product(
        context.user_data['product_name'],
        context.user_data['product_description'],
        context.user_data['product_price'],
        context.user_data['product_stock'],
        context.user_data['product_category']
    )
    
    await query.message.reply_text(
        f"✅ **প্রোডাক্ট যোগ হয়েছে!**\n\n"
        f"🆔 ID: {product_id}\n"
        f"📦 নাম: {context.user_data['product_name']}\n"
        f"📂 ক্যাটাগরি: {category}\n"
        f"💰 দাম: {context.user_data['product_price']}৳\n"
        f"📊 স্টক: {context.user_data['product_stock']}",
        parse_mode='Markdown',
        reply_markup=admin_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# ==================== CALLBACK HANDLER ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == 'profile':
        user = query.from_user
        await query.message.reply_text(
            f"👤 **প্রোফাইল:**\n\n"
            f"🆔 ID: {user.id}\n"
            f"👤 নাম: {user.first_name}\n"
            f"📝 Username: @{user.username}",
            p            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_date TEXT,
                balance INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        
        # Products table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                stock INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')
        
        # Admin sessions table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_sessions (
                user_id INTEGER PRIMARY KEY,
                is_logged_in INTEGER DEFAULT 0,
                login_time TEXT
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
    
    def check_admin_login(self, user_id):
        self.cursor.execute('SELECT is_logged_in FROM admin_sessions WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    def set_admin_login(self, user_id, status):
        self.cursor.execute('''
            INSERT OR REPLACE INTO admin_sessions (user_id, is_logged_in, login_time)
            VALUES (?, ?, ?)
        ''', (user_id, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
    
    def add_product(self, name, description, price, stock):
        self.cursor.execute('''
            INSERT INTO products (name, description, price, stock, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, price, stock, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_all_products(self):
        self.cursor.execute('SELECT * FROM products ORDER BY id DESC')
        return self.cursor.fetchall()
    
    def get_product(self, product_id):
        self.cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        return self.cursor.fetchone()
    
    def delete_product(self, product_id):
        self.cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        self.conn.commit()
    
    def get_all_users(self):
        self.cursor.execute('SELECT * FROM users ORDER BY joined_date DESC')
        return self.cursor.fetchall()
    
    def get_user_count(self):
        self.cursor.execute('SELECT COUNT(*) FROM users')
        return self.cursor.fetchone()[0]

db = Database()

# ==================== KEYBOARDS ====================

def main_keyboard():
    """ইউজার মেইন কিবোর্ড"""
    keyboard = [
        [
            InlineKeyboardButton("👤 প্রোফাইল", callback_data='profile'),
            InlineKeyboardButton("🛍 প্রোডাক্টস", callback_data='products')
        ],
        [
            InlineKeyboardButton("💰 ব্যালেন্স", callback_data='balance'),
            InlineKeyboardButton("ℹ️ হেল্প", callback_data='help')
        ],
        [
            InlineKeyboardButton("🔐 অ্যাডমিন", callback_data='admin_login')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard():
    """অ্যাডমিন কিবোর্ড"""
    keyboard = [
        [
            InlineKeyboardButton("➕ প্রোডাক্ট যোগ", callback_data='add_product'),
            InlineKeyboardButton("📋 প্রোডাক্ট লিস্ট", callback_data='admin_products')
        ],
        [
            InlineKeyboardButton("❌ প্রোডাক্ট ডিলিট", callback_data='delete_product'),
            InlineKeyboardButton("👥 ইউজার লিস্ট", callback_data='users_list')
        ],
        [
            InlineKeyboardButton("📊 স্ট্যাটস", callback_data='admin_stats'),
            InlineKeyboardButton("🔙 মেইন মেনু", callback_data='main_menu')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টার্ট কমান্ড"""
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""
╔══════════════════════╗
   🤖 স্বাগতম {user.first_name}!
╚══════════════════════╝

আমি আপনার শপিং বট।
নিচের বাটন থেকে পছন্দ করুন 👇
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """হেল্প কমান্ড"""
    help_text = """
📚 **কমান্ড লিস্ট:**

👤 **ইউজার কমান্ড:**
/start - বট শুরু করুন
/products - প্রোডাক্ট দেখুন
/help - হেল্প দেখুন

🔐 **অ্যাডমিন কমান্ড:**
/admin - অ্যাডমিন লগইন
/logout - অ্যাডমিন লগআউট
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """প্রোডাক্ট লিস্ট দেখান"""
    products = db.get_all_products()
    
    if products:
        products_text = "🛍 **আমাদের প্রোডাক্টস:**\n\n"
        for product in products:
            products_text += f"📦 **{product[1]}**\n"
            products_text += f"📝 {product[2]}\n"
            products_text += f"💰 দাম: {product[3]}৳\n"
            products_text += f"📊 স্টক: {product[4]}\n"
            products_text += f"🆔 ID: {product[0]}\n\n"
    else:
        products_text = "❌ এখনো কোনো প্রোডাক্ট নেই।"
    
    await update.message.reply_text(products_text, parse_mode='Markdown')

# ==================== ADMIN AUTH ====================

async def admin_login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """অ্যাডমিন লগইন শুরু"""
    user_id = update.effective_user.id
    
    if db.check_admin_login(user_id):
        await update.message.reply_text(
            "✅ আপনি ইতিমধ্যে লগইন আছেন!",
            reply_markup=admin_keyboard()
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🔐 **অ্যাডমিন প্যানেল**\n\n"
        "পাসওয়ার্ড লিখুন:",
        parse_mode='Markdown'
    )
    return ADMIN_PASSWORD_CHECK

async def admin_login_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """পাসওয়ার্ড চেক করুন"""
    password = update.message.text
    
    if password == ADMIN_PASSWORD:
        user_id = update.effective_user.id
        db.set_admin_login(user_id, 1)
        
        await update.message.reply_text(
            "✅ **লগইন সফল!**\n\n"
            "অ্যাডমিন প্যানেলে স্বাগতম!",
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ **ভুল পাসওয়ার্ড!**\n\n"
            "আবার চেষ্টা করুন অথবা /cancel চাপুন।",
            parse_mode='Markdown'
        )
        return ADMIN_PASSWORD_CHECK

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """অ্যাডমিন কমান্ড"""
    user_id = update.effective_user.id
    
    if db.check_admin_login(user_id):
        await update.message.reply_text(
            "👑 **অ্যাডমিন প্যানেল**",
            reply_markup=admin_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "🔐 অ্যাডমিন প্যানেলে লগইন করতে পাসওয়ার্ড লিখুন:"
        )
        return ADMIN_PASSWORD_CHECK

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """লগআউট করুন"""
    user_id = update.effective_user.id
    db.set_admin_login(user_id, 0)
    
    await update.message.reply_text(
        "✅ আপনি লগআউট হয়েছেন।",
        reply_markup=main_keyboard()
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ক্যানসেল করুন"""
    await update.message.reply_text(
        "❌ অপারেশন বাতিল হয়েছে।",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

# ==================== PRODUCT MANAGEMENT ====================

async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """প্রোডাক্ট যোগ শুরু"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not db.check_admin_login(user_id):
        await query.message.reply_text("❌ আগে লগইন করুন! /admin")
        return ConversationHandler.END
    
    await query.message.reply_text("📦 প্রোডাক্টের নাম লিখুন:")
    return ADD_PRODUCT_NAME

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_name'] = update.message.text
    await update.message.reply_text("📝 প্রোডাক্টের বিবরণ লিখুন:")
    return ADD_PRODUCT_DESCRIPTION

async def add_product_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['product_description'] = update.message.text
    await update.message.reply_text("💰 প্রোডাক্টের দাম লিখুন (সংখ্যা):")
    return ADD_PRODUCT_PRICE

async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['product_price'] = price
        await update.message.reply_text("📊 স্টক সংখ্যা লিখুন:")
        return ADD_PRODUCT_STOCK
    except ValueError:
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন!")
        return ADD_PRODUCT_PRICE

async def add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text)
        context.user_data['product_stock'] = stock
        
        product_id = db.add_product(
            context.user_data['product_name'],
            context.user_data['product_description'],
            context.user_data['product_price'],
            context.user_data['product_stock']
        )
        
        await update.message.reply_text(
            f"✅ **প্রোডাক্ট যোগ হয়েছে!**\n\n"
            f"🆔 ID: {product_id}\n"
            f"📦 নাম: {context.user_data['product_name']}\n"
            f"💰 দাম: {context.user_data['product_price']}৳\n"
            f"📊 স্টক: {context.user_data['product_stock']}",
            parse_mode='Markdown',
            reply_markup=admin_keyboard()
        )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন!")
        return ADD_PRODUCT_STOCK

# ==================== CALLBACK HANDLER ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == 'profile':
        user = query.from_user
        await query.message.reply_text(
            f"👤 **প্রোফাইল:**\n\n"
            f"🆔 ID: {user.id}\n"
            f"👤 নাম: {user.first_name}\n"
            f"📝 Username: @{user.username}",
            parse_mode='Markdown'
        )
    
    elif query.data == 'products':
        products = db.get_all_products()
        if products:
            products_text = "🛍 **প্রোডাক্টস:**\n\n"
            for product in products:
                products_text += f"📦 {product[1]} - {product[3]}৳\n"
            await query.message.reply_text(products_text, parse_mode='Markdown')
        else:
            await query.message.reply_text("❌ কোনো প্রোডাক্ট নেই।")
    
    elif query.data == 'balance':
        await query.message.reply_text("💰 আপনার ব্যালেন্স: 0 ৳")
    
    elif query.data == 'help':
        await help_command(update, context)
    
    elif query.data == 'admin_login':
        if db.check_admin_login(user_id):
            await query.message.reply_text(
                "✅ আপনি ইতিমধ্যে লগইন আছেন!",
                reply_markup=admin_keyboard()
            )
        else:
            await query.message.reply_text("🔐 পাসওয়ার্ড লিখুন:")
            return ADMIN_PASSWORD_CHECK
    
    elif query.data == 'main_menu':
        await query.message.reply_text(
            "🔙 মেইন মেনু",
            reply_markup=main_keyboard()
        )
    
    elif query.data == 'add_product':
        if db.check_admin_login(user_id):
            await query.message.reply_text("📦 প্রোডাক্টের নাম লিখুন:")
            return ADD_PRODUCT_NAME
        else:
            await query.message.reply_text("❌ আগে লগইন করুন!")
    
    elif query.data == 'admin_products':
        if db.check_admin_login(user_id):
            await products_command(update, context)
        else:
            await query.message.reply_text("❌ আগে লগইন করুন!")
    
    elif query.data == 'users_list':
        if db.check_admin_login(user_id):
            users = db.get_all_users()
            total = db.get_user_count()
            users_text = f"👥 **মোট ইউজার: {total}**\n\n"
            for user in users[:10]:
                users_text += f"🆔 {user[0]} | {user[2]}\n"
            await query.message.reply_text(users_text, parse_mode='Markdown')
        else:
            await query.message.reply_text("❌ আগে লগইন করুন!")
    
    elif query.data == 'admin_stats':
        if db.check_admin_login(user_id):
            total_users = db.get_user_count()
            total_products = len(db.get_all_products())
            await query.message.reply_text(
                f"📊 **স্ট্যাটস:**\n\n"
                f"👥 ইউজার: {total_users}\n"
                f"📦 প্রোডাক্ট: {total_products}",
                parse_mode='Markdown'
            )
        else:
            await query.message.reply_text("❌ আগে লগইন করুন!")
    
    elif query.data == 'delete_product':
        if db.check_admin_login(user_id):
            products = db.get_all_products()
            if products:
                keyboard = []
                for product in products:
                    keyboard.append([InlineKeyboardButton(f"❌ {product[1]}", callback_data=f'del_{product[0]}')])
                await query.message.reply_text(
                    "কোন প্রোডাক্ট ডিলিট করবেন?",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.message.reply_text("❌ কোনো প্রোডাক্ট নেই!")
        else:
            await query.message.reply_text("❌ আগে লগইন করুন!")
    
    elif query.data.startswith('del_'):
        if db.check_admin_login(user_id):
            product_id = int(query.data.split('_')[1])
            db.delete_product(product_id)
            await query.message.reply_text(f"✅ প্রোডাক্ট ID {product_id} ডিলিট হয়েছে!")
        else:
            await query.message.reply_text("❌ আগে লগইন করুন!")

# ==================== MAIN ====================

def main():
    # Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('admin', admin_command),
            CallbackQueryHandler(admin_login_start, pattern='^admin_login$'),
            CallbackQueryHandler(add_product_start, pattern='^add_product$')
        ],
        states={
            ADMIN_PASSWORD_CHECK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_login_check)
            ],
            ADD_PRODUCT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)
            ],
            ADD_PRODUCT_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_description)
            ],
            ADD_PRODUCT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)
            ],
            ADD_PRODUCT_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_stock)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app = Application.builder().token(TOKEN).build()
    
    # Command Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("products", products_command))
    app.add_handler(CommandHandler("logout", logout_command))
    
    # Conversation Handler
    app.add_handler(conv_handler)
    
    # Callback Handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()

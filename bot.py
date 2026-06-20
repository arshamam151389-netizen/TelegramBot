import os
import telebot
import sqlite3
import threading
import time
import logging
from datetime import datetime
import re

# ============== نصب خودکار jdatetime ==============
try:
    import jdatetime
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'jdatetime'])
    import jdatetime

# ============== تنظیمات ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== توکن از متغیر محیطی ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ توکن پیدا نشد! متغیر BOT_TOKEN را تنظیم کنید.")

bot = telebot.TeleBot(BOT_TOKEN)

# ============== مسیر دیتابیس ==============
DB_PATH = "reminders.db"
logger.info(f"📁 مسیر دیتابیس: {DB_PATH}")

# ============== دیتابیس ==============
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                remind_time TEXT,
                is_done INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("✅ دیتابیس ساخته شد")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در ساخت دیتابیس: {e}")
        return False

def add_reminder(user_id, text, remind_time):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO reminders (user_id, text, remind_time, created_at) VALUES (?, ?, ?, ?)",
            (user_id, text, remind_time, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ خطا در افزودن یادآوری: {e}")
        return False

def get_reminders(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id, text, remind_time FROM reminders WHERE user_id = ? AND is_done = 0 ORDER BY remind_time",
            (user_id,)
        )
        reminders = c.fetchall()
        conn.close()
        return reminders
    except Exception as e:
        logger.error(f"❌ خطا در دریافت یادآوری‌ها: {e}")
        return []

def delete_reminder(user_id, reminder_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE reminders SET is_done = 1 WHERE id = ? AND user_id = ?",
            (reminder_id, user_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ خطا در حذف یادآوری: {e}")
        return False

def get_done_reminders(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id, text, remind_time FROM reminders WHERE user_id = ? AND is_done = 1 ORDER BY remind_time DESC LIMIT 10",
            (user_id,)
        )
        reminders = c.fetchall()
        conn.close()
        return reminders
    except Exception as e:
        logger.error(f"❌ خطا در دریافت تاریخچه: {e}")
        return []

def get_pending_reminders():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute(
            "SELECT id, user_id, text, remind_time FROM reminders WHERE is_done = 0 AND remind_time <= ?",
            (now,)
        )
        reminders = c.fetchall()
        conn.close()
        return reminders
    except Exception as e:
        logger.error(f"❌ خطا در دریافت یادآوری‌های معوق: {e}")
        return []

def mark_as_done(reminder_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE reminders SET is_done = 1 WHERE id = ?", (reminder_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ خطا در بروزرسانی: {e}")
        return False

# ============== توابع کمکی ==============
def parse_datetime(text):
    try:
        text = text.strip()
        pattern = r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?'
        match = re.search(pattern, text)
        
        if not match:
            return None
        
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4)) if match.group(4) else 0
        minute = int(match.group(5)) if match.group(5) else 0
        
        jalali_date = jdatetime.date(year, month, day)
        gregorian_date = jalali_date.togregorian()
        
        result = datetime(
            gregorian_date.year,
            gregorian_date.month,
            gregorian_date.day,
            hour,
            minute
        )
        return result
    except Exception as e:
        logger.error(f"❌ خطا در تبدیل تاریخ: {e}")
        return None

def format_reminder_list(reminders):
    if not reminders:
        return "📭 هیچ یادآوری فعالی ندارید."
    
    lines = ["📋 لیست یادآوری‌های شما:"]
    lines.append("─" * 30)
    
    for i, (id, text, remind_time) in enumerate(reminders, 1):
        try:
            dt = datetime.fromisoformat(remind_time)
            jalali = jdatetime.datetime.fromgregorian(datetime=dt)
            time_str = jalali.strftime("%Y/%m/%d %H:%M")
        except:
            time_str = remind_time
        
        lines.append(f"{i}. {text}")
        lines.append(f"   🕐 {time_str}")
        lines.append(f"   🆔 {id}")
        lines.append("")
    
    return "\n".join(lines)

# ============== بررسی خودکار یادآوری‌ها ==============
def check_reminders():
    while True:
        try:
            reminders = get_pending_reminders()
            for reminder_id, user_id, text, remind_time in reminders:
                try:
                    bot.send_message(
                        user_id,
                        f"⏰ یادآوری!\n\n📝 {text}\n\n🕐 زمان: {remind_time}"
                    )
                    mark_as_done(reminder_id)
                    logger.info(f"✅ یادآوری ارسال شد: {reminder_id}")
                except Exception as e:
                    logger.error(f"❌ خطا در ارسال: {e}")
        except Exception as e:
            logger.error(f"❌ خطا در بررسی: {e}")
        
        time.sleep(30)

# ============== دستورات بات ==============

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        logger.info(f"📩 start از کاربر {message.from_user.id}")
        bot.reply_to(
            message,
            "👋 سلام! من ربات برنامه‌ریزی و یادآوری هستم.\n\n"
            "📌 دستورات من:\n"
            "/add - اضافه کردن یادآوری جدید\n"
            "/list - مشاهده لیست یادآوری‌ها\n"
            "/done - حذف یک یادآوری (با ID)\n"
            "/history - تاریخچه یادآوری‌های انجام شده\n"
            "/help - راهنما\n\n"
            "📝 مثال:\n"
            "/add جلسه کاری 1404/1/15 14:30"
        )
    except Exception as e:
        logger.error(f"❌ خطا در start: {e}")

@bot.message_handler(commands=['help'])
def send_help(message):
    try:
        bot.reply_to(
            message,
            "📚 راهنمای کامل:\n\n"
            "1️⃣ اضافه کردن یادآوری:\n"
            "/add متن یادآوری تاریخ ساعت\n"
            "مثال: /add جلسه کاری 1404/1/15 14:30\n\n"
            "2️⃣ مشاهده یادآوری‌ها:\n"
            "/list\n\n"
            "3️⃣ حذف یادآوری:\n"
            "/done ID\n"
            "مثال: /done 5\n\n"
            "4️⃣ تاریخچه:\n"
            "/history\n\n"
            "📅 فرمت تاریخ: YYYY/MM/DD\n"
            "🕐 فرمت زمان: HH:MM (اختیاری)"
        )
    except Exception as e:
        logger.error(f"❌ خطا در help: {e}")

@bot.message_handler(commands=['add'])
def add_reminder_command(message):
    try:
        logger.info(f"📩 add از کاربر {message.from_user.id}")
        text = message.text.replace('/add', '').strip()
        
        if not text:
            bot.reply_to(
                message,
                "❌ لطفاً متن و زمان یادآوری را وارد کنید.\n"
                "مثال: /add جلسه کاری 1404/1/15 14:30"
            )
            return
        
        remind_time = parse_datetime(text)
        if not remind_time:
            bot.reply_to(
                message,
                "❌ فرمت تاریخ صحیح نیست!\n"
                "از فرمت‌های زیر استفاده کنید:\n"
                "1404/1/15 14:30\n"
                "1404-1-15 14:30\n"
                "1404/1/15\n\n"
                "مثال: /add جلسه کاری 1404/1/15 14:30"
            )
            return
        
        clean_text = re.sub(r'\d{4}[/-]\d{1,2}[/-]\d{1,2}(?:\s+\d{1,2}:\d{2})?', '', text).strip()
        if not clean_text:
            clean_text = "بدون عنوان"
        
        if add_reminder(message.from_user.id, clean_text, remind_time.isoformat()):
            jalali = jdatetime.datetime.fromgregorian(datetime=remind_time)
            time_str = jalali.strftime("%Y/%m/%d %H:%M")
            
            bot.reply_to(
                message,
                f"✅ یادآوری با موفقیت ثبت شد!\n\n"
                f"📝 متن: {clean_text}\n"
                f"🕐 زمان: {time_str}"
            )
        else:
            bot.reply_to(message, "❌ خطا در ثبت یادآوری! لطفاً دوباره تلاش کنید.")
    except Exception as e:
        logger.error(f"❌ خطا در add: {e}")
        bot.reply_to(message, "❌ خطایی رخ داد! لطفاً دوباره تلاش کنید.")

@bot.message_handler(commands=['list'])
def list_reminders(message):
    try:
        logger.info(f"📩 list از کاربر {message.from_user.id}")
        reminders = get_reminders(message.from_user.id)
        bot.reply_to(message, format_reminder_list(reminders))
    except Exception as e:
        logger.error(f"❌ خطا در list: {e}")
        bot.reply_to(message, "❌ خطا در دریافت لیست!")

@bot.message_handler(commands=['done'])
def done_reminder(message):
    try:
        logger.info(f"📩 done از کاربر {message.from_user.id}")
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(
                message,
                "❌ لطفاً ID یادآوری را وارد کنید.\n"
                "مثال: /done 5\n\n"
                "برای دیدن IDها از /list استفاده کنید."
            )
            return
        
        reminder_id = int(parts[1])
        if delete_reminder(message.from_user.id, reminder_id):
            bot.reply_to(
                message,
                f"✅ یادآوری با ID {reminder_id} به عنوان انجام شده ثبت شد!"
            )
        else:
            bot.reply_to(message, "❌ خطا در حذف یادآوری!")
    except ValueError:
        bot.reply_to(message, "❌ ID باید عدد باشد!")
    except Exception as e:
        logger.error(f"❌ خطا در done: {e}")
        bot.reply_to(message, "❌ خطایی رخ داد!")

@bot.message_handler(commands=['history'])
def show_history(message):
    try:
        logger.info(f"📩 history از کاربر {message.from_user.id}")
        reminders = get_done_reminders(message.from_user.id)
        if not reminders:
            bot.reply_to(message, "📭 هنوز هیچ یادآوری انجام نداده‌اید.")
            return
        
        lines = ["📜 تاریخچه یادآوری‌های انجام شده:"]
        lines.append("─" * 30)
        
        for id, text, remind_time in reminders:
            try:
                dt = datetime.fromisoformat(remind_time)
                jalali = jdatetime.datetime.fromgregorian(datetime=dt)
                time_str = jalali.strftime("%Y/%m/%d %H:%M")
            except:
                time_str = remind_time
            
            lines.append(f"✅ {text}")
            lines.append(f"   🕐 {time_str}")
            lines.append("")
        
        bot.reply_to(message, "\n".join(lines))
    except Exception as e:
        logger.error(f"❌ خطا در history: {e}")
        bot.reply_to(message, "❌ خطا در دریافت تاریخچه!")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(
        message,
        "❓ دستور نامعتبر!\n"
        "برای دیدن راهنما /help را بزنید."
    )

# ============== اجرا ==============
if __name__ == '__main__':
    # راه‌اندازی دیتابیس
    if not init_db():
        logger.error("❌ خطا در راه‌اندازی دیتابیس! برنامه متوقف شد.")
        exit(1)
    
    logger.info("📊 دیتابیس راه‌اندازی شد")
    
    # راه‌اندازی ترد بررسی یادآوری‌ها
    reminder_thread = threading.Thread(target=check_reminders, daemon=True)
    reminder_thread.start()
    logger.info("⏰ سیستم بررسی یادآوری‌ها فعال شد")
    
    logger.info("🤖 بات در حال اجراست...")
    
    # اجرای بات با مدیریت خطا
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"❌ خطا در اجرای بات: {e}")
            logger.info("🔄 تلاش مجدد در 5 ثانیه...")
            time.sleep(5)
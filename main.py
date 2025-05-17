import logging
import flask
import os
import threading
import traceback
import sys
from datetime import datetime

# استيراد نظام السجلات
from logger_setup import init_all_loggers, setup_exception_handler, log_error

# استيراد الإعدادات
from config import Config

# Create a Flask app
app = flask.Flask(__name__)

# تكوين قاعدة البيانات
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# تهيئة قاعدة البيانات
from models import db, User, UserTemplate, UserLog, SmartRule
db.init_app(app)

# Flag to track if the bot is already running
bot_is_running = False
bot_thread = None

@app.route('/')
def index():
    return """
    <html dir="rtl">
    <head><title>بوت تعديل الوسوم الصوتية</title></head>
    <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
        <h1>تم تشغيل البوت بنجاح ✅</h1>
        <p>البوت يعمل الآن ويمكنك استخدامه عبر تطبيق تيليجرام.</p>
        <p><a href="/status">عرض حالة البوت</a></p>
        <p><a href="/logs">عرض السجلات</a></p>
    </body>
    </html>
    """

@app.route('/status')
def status():
    global bot_is_running
    status_text = "يعمل" if bot_is_running else "متوقف"
    status_color = "green" if bot_is_running else "red"
    
    return f"""
    <html dir="rtl">
    <head><title>حالة البوت</title></head>
    <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
        <h1>حالة البوت</h1>
        <p>البوت حالياً: <span style="color: {status_color}; font-weight: bold;">{status_text}</span></p>
        <p>وقت التحقق: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><a href="/">العودة للصفحة الرئيسية</a></p>
    </body>
    </html>
    """

@app.route('/logs')
def view_logs():
    # نص السجلات الرئيسية
    log_content = "السجلات غير متوفرة"
    try:
        if os.path.exists("logs/bot.log"):
            with open("logs/bot.log", "r", encoding="utf-8") as log_file:
                # عرض آخر 100 سطر من السجلات
                log_content = "".join(log_file.readlines()[-100:])
    except Exception as e:
        log_content = f"خطأ في قراءة السجلات: {str(e)}"
    
    return f"""
    <html dir="rtl">
    <head><title>سجلات البوت</title></head>
    <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 30px;">
        <h1>سجلات البوت</h1>
        <p>آخر 100 سطر من السجلات:</p>
        <div style="text-align: left; direction: ltr; background-color: #f5f5f5; padding: 15px; margin: 20px; border-radius: 5px; overflow: auto; max-height: 500px; font-family: monospace;">
            <pre>{log_content}</pre>
        </div>
        <p><a href="/">العودة للصفحة الرئيسية</a></p>
    </body>
    </html>
    """

def run_bot():
    try:
        from bot import start_bot
        # تسجيل بدء تشغيل البوت
        logger = logging.getLogger('main')
        logger.info("بدء تشغيل البوت في خيط منفصل")
        start_bot()
    except Exception as e:
        # تسجيل أي خطأ يحدث أثناء تشغيل البوت
        log_error(e, "تشغيل البوت في خيط منفصل")

# إعداد نظام السجلات
logger = init_all_loggers()
setup_exception_handler()

# إنشاء جداول قاعدة البيانات إذا لم تكن موجودة
with app.app_context():
    try:
        db.create_all()
        logger.info("تم إنشاء/التحقق من جداول قاعدة البيانات بنجاح")
    except Exception as e:
        log_error(e, "إنشاء جداول قاعدة البيانات")

# تهيئة لوحة الإدارة
try:
    import admin_panel
    logger.info("Admin panel module initialized successfully")
except Exception as e:
    log_error(e, "تهيئة لوحة الإدارة")

if __name__ == '__main__':
    # Only start the bot directly when running as a script
    # Not when imported by gunicorn
    try:
        from bot import start_bot
        start_bot()
    except Exception as e:
        log_error(e, "تشغيل البوت المباشر")

import os
import logging
import telebot
import tempfile
import shutil
import base64
from types import SimpleNamespace
from telebot import types
from telebot.handler_backends import State, StatesGroup
from tag_handler import (
    get_audio_tags, set_audio_tags, get_valid_tag_fields, extract_album_art,
    extract_lyrics
)
from template_handler import (
    save_template, get_template, list_templates, delete_template,
    extract_artist_from_tags, get_artists_with_templates
)

from utils import sanitize_filename, ensure_temp_dir
import auto_processor  # استيراد وحدة المعالجة التلقائية

# استيراد النماذج من ملف models.py
from models import db, User, UserTemplate, UserLog, SmartRule
from config import Config  # استيراد الإعدادات
from logger_setup import log_user_action, log_error, log_admin_action  # استيراد وظائف السجلات

# Arabic names for tag fields
def get_tag_field_names_arabic():
    """Return a dictionary mapping tag fields to their Arabic names."""
    return {
        'title': 'العنوان',
        'artist': 'الفنان',
        'album': 'الألبوم',
        'album_artist': 'فنان الألبوم',
        'year': 'السنة',
        'genre': 'النوع',
        'composer': 'الملحن',
        'comment': 'تعليق',
        'track': 'رقم المسار',
        'length': 'المدة',
        'lyrics': 'كلمات الأغنية',
        'picture': 'صورة الغلاف'
    }

# Global user data storage
user_data = {}
TEMP_DIR = "temp_audio_files"

# Helper function to access user data
def get_user_data(user_id):
    """Get user data by user_id, or None if not found."""
    if user_id in user_data:
        return user_data[user_id]
    return None

# Status tracking
bot_status = {
    "started_time": None,
    "processed_files": 0,
    "successful_edits": 0,
    "failed_operations": 0,
    "active_users": set(),
    "errors": []
}

# Interactive response messages
response_messages = {
    "welcome": "✨ *مرحباً بك في بوت تعديل الوسوم الصوتية المتطور* ✨\n\n🎵 البوت الأول والأكثر تطوراً لإدارة ملفاتك الصوتية باللغة العربية",
    "file_received": "🎧 *تم استلام الملف الصوتي بنجاح!* ✅\n\n⏳ جارٍ معالجة الملف واستخراج الوسوم... برجاء الانتظار قليلاً",
    "file_processing_error": "⛔️ *حدث خطأ أثناء معالجة الملف* ⛔️\n\n🔍 التفاصيل:\n• تأكد من أن الملف بتنسيق صوتي صحيح\n• حجم الملف يجب أن يكون أقل من 50 ميجابايت\n• جرب إرسال الملف مرة أخرى أو استخدم ملفاً آخر",
    "edit_started": "📝 *ابدأ تعديل الوسوم!* 📝\n\n• اضغط على الوسم الذي تريد تعديله\n• بعد الانتهاء، اضغط على 'حفظ التغييرات'\n• يمكنك إضافة/تعديل صورة الغلاف من خلال الزر المخصص",
    "edit_completed": "✅ *تم حفظ التعديلات بنجاح!* ✅\n\n💾 جارٍ معالجة الملف وتطبيق التغييرات...\n📤 سيتم إرسال الملف المعدل إليك فور الانتهاء",
    "operation_canceled": "❌ *تم إلغاء العملية* ❌\n\n• لم يتم إجراء أي تغييرات على الملف\n• يمكنك إرسال ملف آخر في أي وقت\n• أو استخدام قائمة 'إدارة القوالب' لإنشاء قوالب جديدة",
    "invalid_input": "⚠️ *المدخلات غير صحيحة* ⚠️\n\nالرجاء التأكد من اتباع التعليمات واستخدام القيم المناسبة لكل وسم",
    "tag_saved": "✅ *تم حفظ الوسم بنجاح!* ✅\n\nيمكنك الاستمرار في تعديل الوسوم الأخرى أو حفظ جميع التغييرات",
    "upload_image": "🖼️ *إضافة صورة غلاف* 🖼️\n\n• أرسل صورة لاستخدامها كغلاف للملف الصوتي\n• يفضل استخدام صورة مربعة الشكل\n• يدعم البوت صور عالية الدقة حتى 3000×3000 بكسل",
    "image_saved": "✅ *تم حفظ صورة الغلاف بنجاح!* ✅\n\n• تم تحسين الصورة تلقائياً للاستخدام في الملف الصوتي\n• ستظهر الصورة في برامج تشغيل الموسيقى وعند إرسال الملف"
}

# Setup advanced logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]',
    handlers=[
        logging.FileHandler("bot_logs.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('bot')

# المجلدات المؤقتة
TEMP_DIR = Config.TEMP_DIR
TEMPLATES_DIR = Config.TEMPLATES_DIR

# قاموس لتخزين حالات المستخدمين
user_states = {}

# دالة لتعيين حالة المستخدم (يستخدمها ملف admin_handlers.py)
def set_user_state(user_id, state_name, data=None):
    """تعيين حالة المستخدم وبياناته"""
    user_states[user_id] = {
        'state': state_name,
        'data': data or {}
    }
    logger.info(f"تم تعيين حالة المستخدم {user_id} إلى {state_name}")
    return True

# دالة للحصول على حالة المستخدم
def get_user_state(user_id):
    """الحصول على حالة المستخدم"""
    if user_id in user_states:
        return user_states[user_id]
    return None

# تسجيل عمليات المستخدم وأخطاء البوت أصبحت مستوردة من logger_setup

# Define state class for conversation management
class BotStates(StatesGroup):
    waiting_for_audio = State()
    editing_tags = State()
    waiting_for_tag_values = State()
    waiting_for_specific_tag = State()  # New state for editing a specific tag
    template_menu = State()  # حالة قائمة القوالب
    waiting_for_template_name = State()  # حالة انتظار اسم القالب للحفظ
    waiting_for_template_selection = State()  # حالة انتظار اختيار القالب للتطبيق
    waiting_for_manual_template = State()  # حالة انتظار إدخال بيانات القالب اليدوي
    waiting_for_manual_template_name = State()  # حالة انتظار اسم القالب اليدوي
    
    # حالات إدارة البوت
    admin_panel = State()  # حالة لوحة الإدارة
    admin_waiting_for_admin_id = State()  # حالة انتظار معرف المشرف
    admin_waiting_for_user_id = State()  # حالة انتظار معرف المستخدم
    admin_waiting_for_broadcast = State()  # حالة انتظار نص الرسالة الجماعية
    admin_waiting_for_welcome_msg = State()  # حالة انتظار رسالة الترحيب
    admin_waiting_for_file_size = State()  # حالة انتظار حجم الملف المخصص
    admin_waiting_for_delay = State()  # حالة انتظار وقت التأخير المخصص
    admin_waiting_for_limit = State()  # حالة انتظار الحد اليومي المخصص
    admin_waiting_for_channel_id = State()  # حالة انتظار معرف القناة
    admin_waiting_for_channel_title = State()  # حالة انتظار عنوان القناة
    admin_waiting_for_log_channel = State()  # حالة انتظار قناة السجل
    
    # حالات التعديل التلقائي للقنوات
    admin_waiting_for_replacement = State()  # حالة انتظار استبدال نصي جديد
    admin_waiting_for_smart_template = State()  # حالة انتظار إضافة قالب ذكي جديد
    admin_waiting_old_text = State()  # حالة انتظار النص الأصلي للاستبدال
    admin_waiting_new_text = State()  # حالة انتظار النص البديل للاستبدال
    admin_waiting_source_channel = State()  # حالة انتظار معرف قناة المصدر
    admin_waiting_target_channel = State()  # حالة انتظار معرف قناة الهدف للنشر التلقائي
    admin_waiting_artist_name = State()  # حالة انتظار اسم الفنان للقالب الذكي
    admin_waiting_template_id = State()  # حالة انتظار معرف القالب الذكي
    admin_waiting_replacement_number = State()  # حالة انتظار رقم الاستبدال للحذف
    admin_waiting_template_number = State()  # حالة انتظار رقم القالب الذكي للحذف
    
    # حالات إعدادات العلامة المائية
    admin_waiting_for_watermark_size = State()  # حالة انتظار حجم العلامة المائية
    admin_waiting_for_watermark_opacity = State()  # حالة انتظار شفافية العلامة المائية
    admin_waiting_for_watermark_padding = State()  # حالة انتظار تباعد العلامة المائية
    admin_waiting_for_watermark_image = State()  # حالة انتظار صورة العلامة المائية

def start_bot():
    """Start the bot."""
    # Get the telegram token from environment variable or config
    token = Config.BOT_TOKEN
    if not token:
        logger.error("No Telegram token found in environment variables or config!")
        return
    
    # Ensure temp directory exists
    ensure_temp_dir(Config.TEMP_DIR)
    
    # Create bot instance
    bot = telebot.TeleBot(token)
    
    logger.info(f"Starting the Telegram bot '{Config.BOT_NAME}'...")
    
    # تسجيل حدث بدء التشغيل
    logger.info(f"Bot started in {Config.ENVIRONMENT} environment")
    
    # إعداد معالجات القنوات للمعالجة التلقائية
    auto_processor.setup_channel_handlers(bot)
    
    # Define handlers
    # Command for getting bot status
    @bot.message_handler(commands=['status'])
    def status_command(message):
        """Get bot status."""
        user_id = message.from_user.id
        logger.info(f"Received /status command from user {user_id}")
        
        # Generate status report
        import datetime
        if bot_status["started_time"]:
            uptime = datetime.datetime.now() - bot_status["started_time"]
            uptime_str = f"{uptime.days} يوم, {uptime.seconds // 3600} ساعة, {(uptime.seconds // 60) % 60} دقيقة"
        else:
            uptime_str = "غير متوفر"
            
        # Get list of supported formats
        supported_formats = ["MP3", "FLAC", "OGG", "WAV", "M4A", "AAC"]
        formats_str = ", ".join(supported_formats)
        
        # Get memory usage
        import psutil, os
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # in MB
        
        report = (
            f"📊 *بوت تعديل الوسوم الصوتية - تقرير الحالة*\n\n"
            f"🤖 *معلومات البوت:*\n"
            f"⏱️ وقت التشغيل: {uptime_str}\n"
            f"💾 استهلاك الذاكرة: {memory_usage:.1f} ميجابايت\n"
            f"🎵 التنسيقات المدعومة: {formats_str}\n\n"
            
            f"📈 *إحصائيات:*\n"
            f"📁 الملفات المعالجة: {bot_status['processed_files']}\n"
            f"✅ التعديلات الناجحة: {bot_status['successful_edits']}\n"
            f"❌ العمليات الفاشلة: {bot_status['failed_operations']}\n"
            f"👥 المستخدمين النشطين: {len(bot_status['active_users'])}\n"
            f"🛑 الأخطاء المسجلة: {len(bot_status['errors'])}\n\n"
        )
        
        # Add recent errors if any
        if bot_status["errors"]:
            report += "*آخر 3 أخطاء:*\n"
            for error in bot_status["errors"][-3:]:
                error_time = error.get("timestamp", "وقت غير معروف")
                error_type = error.get("error_type", "نوع غير معروف")
                error_msg = error.get("message", "رسالة غير معروفة")
                report += f"- {error_time[-8:]}: {error_type}: {error_msg[:40]}...\n"
        else:
            report += "*الأخطاء:* لا توجد أخطاء مسجلة 👍\n"
        
        # Create action buttons
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("مسح سجل الأخطاء 🗑️", callback_data="clear_errors"),
            types.InlineKeyboardButton("إعادة التشغيل 🔄", callback_data="restart_bot")
        )
        
        bot.send_message(message.chat.id, report, reply_markup=markup, parse_mode="Markdown")
        
    # Command for getting help
    @bot.message_handler(commands=['help'])
    def help_command(message):
        """Send help information."""
        user_id = message.from_user.id
        logger.info(f"Received /help command from user {user_id}")
        
        help_text = (
            "📚 **دليل استخدام بوت تعديل الوسوم الصوتية** 📚\n\n"
            "الأوامر المتاحة:\n"
            "/start - بدء استخدام البوت\n"
            "/help - عرض هذه المساعدة\n"
            "/status - عرض حالة البوت\n"
            "/templates - إدارة القوالب\n"
            "/cancel - إلغاء العملية الحالية\n\n"
            
            "**كيفية استخدام البوت:**\n"
            "1️⃣ أرسل ملف صوتي (MP3, FLAC, WAV, إلخ)\n"
            "2️⃣ سيعرض البوت الوسوم الحالية وصورة الغلاف (إن وجدت)\n"
            "3️⃣ اضغط على 'تعديل الوسوم' للبدء في التعديل\n"
            "4️⃣ اختر الوسم الذي تريد تعديله من القائمة\n"
            "5️⃣ أدخل القيمة الجديدة للوسم\n"
            "6️⃣ يمكنك تعديل وسوم متعددة بتكرار الخطوات 4 و 5\n"
            "7️⃣ اضغط على 'تم الانتهاء' عندما تنتهي من التعديل\n"
            "8️⃣ سيقوم البوت بحفظ التغييرات وإرسال الملف المعدل\n\n"
            
            "**ميزة القوالب:**\n"
            "🔸 يمكنك حفظ مجموعة من الوسوم كقالب واستخدامها لاحقاً\n"
            "🔸 استخدم زر 'حفظ قالب جديد' في رسالة البداية لحفظ وسوم الملف الحالي\n"
            "🔸 استخدم زر 'القوالب المحفوظة' لعرض وتطبيق القوالب المحفوظة\n"
            "🔸 يتم تنظيم القوالب حسب اسم الفنان لسهولة الوصول إليها\n\n"
            
            "**الوسوم المدعومة:**\n"
            "🔹 العنوان (Title)\n"
            "🔹 الفنان (Artist)\n"
            "🔹 فنان الألبوم (Album Artist)\n"
            "🔹 الألبوم (Album)\n"
            "🔹 السنة (Year)\n"
            "🔹 النوع (Genre)\n"
            "🔹 الملحن (Composer)\n"
            "🔹 تعليق (Comment)\n"
            "🔹 رقم المسار (Track)\n"
            "🔹 المدة (Length)\n"
            "🔹 كلمات الأغنية (Lyrics)\n"
            "🔹 صورة الغلاف (Album Art)\n\n"
            
            "لإضافة صورة غلاف، اضغط على 'إضافة/تغيير صورة الغلاف' وأرسل الصورة."
        )
        
        bot.send_message(message.chat.id, help_text)
        
    @bot.message_handler(commands=['admin'])
    def admin_command(message):
        """فتح لوحة الإدارة للمشرف"""
        user_id = message.from_user.id
        logger.info(f"Received /admin command from user {user_id}")
        
        # التحقق من أن المستخدم مشرف
        if admin_panel.is_admin(user_id):
            admin_handlers.open_admin_panel(bot, message)
        else:
            bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            logger.warning(f"Unauthorized access attempt to admin panel by user {user_id}")
            admin_panel.log_action(user_id, "admin_access_attempt", "failed", "غير مصرح له")
    
    @bot.message_handler(commands=['start'])
    def start_command(message):
        """Start the conversation."""
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        logger.info(f"Received /start command from user {user_id}")
        
        # إضافة أو تحديث بيانات المستخدم - نستخدم admin_panel بدلاً من الوصول المباشر لقاعدة البيانات
        try:
            # استخدام admin_panel لتحديث بيانات المستخدم
            from admin_panel import update_user_data
            update_user_data(
                user_id=user_id,
                username=username,
                first_name=first_name
            )
            logger.info(f"تم تحديث بيانات المستخدم: {user_id}")
        except Exception as e:
            logger.error(f"خطأ في تحديث بيانات المستخدم: {e}")
        
        # Add user to active users
        bot_status["active_users"].add(user_id)
        
        # Send welcome message with improved, attractive buttons
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📚 دليل الاستخدام", callback_data="help"),
            types.InlineKeyboardButton("📊 إحصائيات البوت", callback_data="status")
        )
        
        # إضافة زر إدارة القوالب مع تصميم محسن
        markup.add(
            types.InlineKeyboardButton("🎵 إدارة قوالب الصوت", callback_data="manage_templates")
        )
        
        # إضافة زر حول البوت مع تصميم محسن
        markup.add(
            types.InlineKeyboardButton("ℹ️ معلومات عن البوت", callback_data="about_bot")
        )
        
        # إضافة زر لوحة الإدارة للمشرفين والمطورين
        developer_ids = [1174919068, 6556918772, 6602517122]
        is_dev = user_id in developer_ids
        if admin_panel.is_admin(user_id) or is_dev:
            markup.add(
                types.InlineKeyboardButton("⚙️ لوحة التحكم الإدارية", callback_data="open_admin_panel")
            )
        
        bot.send_message(
            message.chat.id,
            response_messages["welcome"] + "\n\n"
            "يدعم البوت تعديل الوسوم التالية: العنوان، الفنان، الألبوم، فنان الألبوم، السنة، النوع، الملحن، التعليق، رقم المسار، المدة، كلمات الأغنية، وصورة الغلاف.\n\n"
            "يمكنك استخدام زر 'إدارة القوالب' لإنشاء وعرض وتعديل القوالب، أو استخدم أمر /templates.\n\n"
            "استخدم /help للحصول على مزيد من المعلومات.",
            reply_markup=markup
        )
        
    @bot.message_handler(commands=['templates'])
    def templates_command(message):
        """عرض قائمة للوصول إلى القوالب وإدارتها."""
        user_id = message.from_user.id
        logger.info(f"Received /templates command from user {user_id}")
        
        # إنشاء قائمة أزرار لإدارة القوالب
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 إنشاء قالب يدوي", callback_data="create_manual_template"),
            types.InlineKeyboardButton("📋 عرض القوالب", callback_data="show_templates")
        )
        markup.add(
            types.InlineKeyboardButton("❌ حذف قالب", callback_data="delete_template"),
            types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="edit_template")
        )
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
        
        bot.send_message(
            message.chat.id,
            "🗂️ *إدارة القوالب*\n\n"
            "• استخدم *إنشاء قالب يدوي* لإضافة قالب جديد عن طريق إدخال الوسوم يدوياً\n"
            "• استخدم *عرض القوالب* لاستعراض القوالب المحفوظة وتطبيقها\n"
            "• استخدم *حذف قالب* لإزالة قالب موجود\n"
            "• استخدم *تعديل قالب* لتغيير محتوى قالب موجود",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    # This is a duplicate help command handler, removed to avoid conflicts
    
    # Handler for receiving audio files
    @bot.message_handler(content_types=['audio', 'document'])
    def receive_audio(message):
        """Handle receiving an audio file and display the current tags."""
        logger.info(f"Received potential audio file from user {message.from_user.id}")
        logger.info(f"Message type: {message.content_type}")
        
        if message.content_type == 'audio':
            logger.info(f"Audio file details: {message.audio.file_name}, ID: {message.audio.file_id}")
        elif message.content_type == 'document':
            logger.info(f"Document details: {message.document.file_name}, ID: {message.document.file_id}")
            if hasattr(message.document, 'mime_type'):
                logger.info(f"Document mime_type: {message.document.mime_type}")
        
        user_id = message.from_user.id
        
        # Ensure user has a data entry
        if user_id not in user_data:
            user_data[user_id] = {}
        
        # Check if an audio file was sent
        audio_file = None
        file_name = None
        file_id = None
        
        if message.audio:
            audio_file = message.audio
            file_id = audio_file.file_id
            file_name = audio_file.file_name or f"audio_{file_id}.mp3"
        elif message.document:
            document = message.document
            mime_type = document.mime_type
            
            if mime_type and mime_type.startswith('audio/'):
                audio_file = document
                file_id = document.file_id
                file_name = document.file_name or f"audio_{file_id}"
            else:
                bot.send_message(message.chat.id, "هذا لا يبدو ملفًا صوتيًا. الرجاء إرسال ملف صوتي.")
                return
        
        if not audio_file or not file_id:
            bot.send_message(message.chat.id, "لم أتمكن من اكتشاف ملف صوتي. الرجاء إرسال ملف صوتي.")
            return
        
        # Download the file
        bot.send_message(message.chat.id, "جاري تنزيل الملف الصوتي...")
        
        try:
            logger.info(f"Attempting to download file with ID: {file_id}")
            file_info = bot.get_file(file_id)
            logger.info(f"Got file info: {file_info}")
            
            if not file_info.file_path:
                logger.error("file_info.file_path is None or empty")
                bot.send_message(message.chat.id, "تعذر الحصول على مسار الملف. الرجاء المحاولة مرة أخرى.")
                return
                
            logger.info(f"Downloading file from path: {file_info.file_path}")
            downloaded_file = bot.download_file(file_info.file_path)
            logger.info(f"Downloaded file of size: {len(downloaded_file)} bytes")
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            bot.send_message(message.chat.id, f"حدث خطأ في تنزيل الملف: {e}. الرجاء المحاولة مرة أخرى.")
            return
        
        safe_file_name = sanitize_filename(file_name)
        file_path = os.path.join(TEMP_DIR, f"{user_id}_{safe_file_name}")
        
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # Store the file path
        user_data[user_id]['file_path'] = file_path
        user_data[user_id]['original_file_name'] = file_name
        
        # Get the current tags
        try:
            logger.info(f"Reading tags from file: {file_path}")
            tags = get_audio_tags(file_path)
            logger.info(f"Retrieved tags: {tags}")
            
            # Store the complete tags from the file for future reference
            user_data[user_id]['complete_tags'] = tags
            tag_text = "الوسوم الحالية:\n\n"
            
            if tags:
                # Define the order of tags we want to display (prioritize the requested tags)
                priority_tags = ['title', 'artist', 'album', 'album_artist', 'year', 'genre', 
                               'composer', 'comment', 'track', 'length']
                
                # Get Arabic names for tags
                arabic_names = get_tag_field_names_arabic()
                
                # حد أقصى للطول لتجنب خطأ "message caption is too long"
                max_caption_length = 900  # أقل من الحد الأقصى 1024 بهامش أمان
                current_length = len(tag_text)
                
                # First add priority tags - مع التحقق من طول النص
                for tag in priority_tags:
                    # تخطي كلمات الأغنية لتجنب مشكلة الوصف الطويل
                    if tag != 'lyrics' and tag in tags and tag != 'has_album_art' and tag != 'file_type':
                        arabic_name = arabic_names.get(tag, tag)
                        
                        # تقصير القيم الطويلة
                        value = str(tags[tag])
                        if len(value) > 50:
                            value = value[:47] + "..."
                            
                        # إضافة السطر إذا كان الطول الإجمالي ضمن الحدود
                        new_line = f"{arabic_name}: {value}\n"
                        if current_length + len(new_line) < max_caption_length:
                            tag_text += new_line
                            current_length += len(new_line)
                        else:
                            tag_text += "...\n"
                            break
                    elif tag in ['genre', 'comment', 'track', 'length']:
                        # For the specifically requested tags, show them even if empty
                        arabic_name = arabic_names.get(tag, tag)
                        new_line = f"{arabic_name}: غير محدد\n"
                        
                        if current_length + len(new_line) < max_caption_length:
                            tag_text += new_line
                            current_length += len(new_line)
                        else:
                            tag_text += "...\n"
                            break
                
                # إضافة العلامات الأخرى إذا كان هناك مساحة كافية
                if current_length < max_caption_length - 50:  # ترك مساحة للمزيد
                    for key, value in tags.items():
                        if key != 'lyrics' and key not in priority_tags and key != 'has_album_art' and key != 'file_type':
                            arabic_name = arabic_names.get(key, key)
                            
                            # تقصير القيم الطويلة
                            value_str = str(value)
                            if len(value_str) > 50:
                                value_str = value_str[:47] + "..."
                                
                            new_line = f"{arabic_name}: {value_str}\n"
                            if current_length + len(new_line) < max_caption_length:
                                tag_text += new_line
                                current_length += len(new_line)
                            else:
                                tag_text += "...\n"
                                break
                
                # إضافة ملاحظة عن كلمات الأغنية إذا كانت موجودة
                if 'lyrics' in tags and tags.get('lyrics') and current_length + 60 < max_caption_length:
                    tag_text += "\n(كلمات الأغنية متاحة عند النقر على زر 'تعديل الوسوم')\n"
                
                logger.info(f"Formatted tag text: {tag_text}")
            else:
                tag_text += "لم يتم العثور على وسوم ID3 أو الملف لا يدعم وسوم ID3."
                logger.info("No tags found in the file")
            
            # استخدام دالة display_current_tags لعرض الوسوم مع زر تطبيق القالب
            try:
                logger.info("Using display_current_tags function with enhanced UI")
                display_current_tags(message, user_id, file_path, show_edited=False)
                return  # إيقاف الدالة هنا لأننا استخدمنا الدالة المطورة
            except Exception as e:
                logger.error(f"Error using display_current_tags: {str(e)}")
                
                # في حالة حدوث خطأ، نستمر باستخدام الطريقة القديمة
            
            # Using inline keyboard buttons if enhanced display failed
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton(text='تعديل الوسوم', callback_data='edit_tags'))
            markup.add(types.InlineKeyboardButton(text='🗂️ تطبيق قالب جاهز', callback_data='apply_template_menu'))
            markup.add(types.InlineKeyboardButton(text='إلغاء', callback_data='cancel'))
            logger.info("Created inline keyboard with edit/template/cancel options")
            
            # Check if the file has album art
            logger.info(f"Checking for album art, has_album_art = {tags.get('has_album_art', False)}")
            if tags.get('has_album_art', False):
                # Extract album art
                logger.info(f"Extracting album art from file: {file_path}")
                image_data, mime_type = extract_album_art(file_path)
                logger.info(f"Album art extraction result - mime_type: {mime_type}, data size: {len(image_data) if image_data else 0} bytes")
                
                if image_data:
                    # Save album art to a temporary file
                    art_file_path = os.path.join(TEMP_DIR, f"{user_id}_albumart.jpg")
                    logger.info(f"Saving album art to: {art_file_path}")
                    with open(art_file_path, 'wb') as art_file:
                        art_file.write(image_data)
                    
                    # Send album art with tags as caption and inline keyboard
                    logger.info("Sending album art with caption and inline keyboard")
                    with open(art_file_path, 'rb') as art_file:
                        bot.send_photo(
                            message.chat.id,
                            art_file,
                            caption=tag_text,
                            reply_markup=markup
                        )
                    
                    # Clean up the temporary album art file
                    try:
                        logger.info(f"Cleaning up temporary album art file: {art_file_path}")
                        os.remove(art_file_path)
                    except Exception as e:
                        logger.error(f"Error removing temporary album art file: {e}")
                else:
                    # If extraction failed, just send the message with tags
                    logger.info("Album art extraction failed, sending text-only message with inline keyboard")
                    bot.send_message(message.chat.id, tag_text, reply_markup=markup)
            else:
                # If no album art, just send the message with tags
                logger.info("No album art found, sending text-only message with inline keyboard")
                bot.send_message(message.chat.id, tag_text, reply_markup=markup)
            
            # Set state to editing tags
            bot.set_state(message.from_user.id, BotStates.editing_tags, message.chat.id)
        
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            bot.send_message(
                message.chat.id,
                f"خطأ في معالجة الملف الصوتي: {str(e)}.\n"
                "الرجاء تجربة ملف آخر."
            )
    
    # Callback query handler for inline buttons
    @bot.callback_query_handler(func=lambda call: not call.data.startswith("admin_"))
    def handle_callback_query(call):
        """Handle callback queries from inline keyboard buttons."""
        logger.info(f"Received callback query: {call.data} from user {call.from_user.id}")
        user_id = call.from_user.id
        
        try:
            # Always answer callback query first to prevent timeout errors
            bot.answer_callback_query(call.id)
            
            if call.data == 'open_admin_panel':
                # فتح لوحة الإدارة للمشرف أو المطور
                # التحقق من أن المستخدم مطور أو مشرف
                developer_ids = [1174919068, 6556918772, 6602517122]
                is_dev = user_id in developer_ids
                
                if admin_panel.is_admin(user_id) or is_dev:
                    # إذا كان مطوراً ولكن ليس مشرفاً، أضفه كمشرف
                    if is_dev and not admin_panel.is_admin(user_id):
                        admin_panel.add_admin(user_id)
                        logger.info(f"تمت إضافة مطور البوت {user_id} كمشرف تلقائياً")
                    
                    # فتح لوحة الإدارة للمشرف أو المطور
                    admin_handlers.open_admin_panel(bot, call.message)
                else:
                    bot.send_message(call.message.chat.id, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            
            elif call.data == "confirm_template":
                # تأكيد حفظ القالب
                logger.info(f"User {user_id} confirmed template saving")
                
                # التحقق من وجود حالة المستخدم وبياناته
                user_state = get_user_state(user_id)
                
                if user_state and user_state.get("state") == "admin_waiting_for_template_confirmation":
                    # التحقق من وجود بيانات القالب
                    if user_id in user_data and 'manual_template_tags' in user_data[user_id]:
                        template_tags = user_data[user_id]['manual_template_tags']
                        
                        # تحديث رسالة العرض
                        bot.edit_message_text(
                            "✅ *جاري حفظ القالب...*",
                            call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown"
                        )
                        
                        # طلب اسم القالب
                        msg = bot.edit_message_text(
                            "✏️ *إدخال اسم القالب*\n\n"
                            "أدخل اسمًا للقالب العام (يفضل أن يتضمن اسم الفنان). هذا الاسم سيظهر في قائمة القوالب العامة.\n\n"
                            "❔ *مثال:* قالب أغاني عيسى الليث\n\n"
                            "🔄 أرسل `الغاء` للإلغاء.",
                            call.message.chat.id, call.message.message_id,
                            parse_mode="Markdown"
                        )
                        
                        # تحديث حالة المستخدم
                        set_user_state(user_id, "admin_waiting_for_template_name", {
                            "message_id": msg.message_id,
                            "template_tags": template_tags
                        })
                    else:
                        # عدم وجود بيانات للقالب
                        bot.answer_callback_query(
                            call.id,
                            "❌ لم يتم العثور على بيانات القالب.",
                            show_alert=True
                        )
                        # العودة للوحة التحكم
                        admin_handlers.open_admin_panel(bot, call.message)
                else:
                    # حالة المستخدم غير صحيحة
                    bot.answer_callback_query(
                        call.id,
                        "❌ حدث خطأ في حالة المستخدم أثناء حفظ القالب.",
                        show_alert=True
                    )
                    # العودة للوحة التحكم
                    admin_handlers.open_admin_panel(bot, call.message)
                    
            elif call.data == "cancel_template":
                # إلغاء حفظ القالب
                logger.info(f"User {user_id} cancelled template saving")
                
                # تنظيف حالة المستخدم
                bot.delete_state(user_id, call.message.chat.id)
                
                # إظهار رسالة
                bot.answer_callback_query(
                    call.id,
                    "تم إلغاء حفظ القالب.",
                    show_alert=True
                )
                
                # العودة للوحة التحكم
                admin_handlers.open_admin_panel(bot, call.message)
            
            elif call.data == 'about_bot':
                # عرض معلومات حول البوت
                about_text = (
                    "ℹ️ *حول البوت*\n\n"
                    "*بوت تعديل الوسوم الصوتية 🎵*\n\n"
                    "هذا البوت متخصص في إدارة وتعديل وسوم الملفات الصوتية بطريقة سهلة ومتكاملة باللغة العربية.\n\n"
                    "*🔹 المميزات الرئيسية:*\n"
                    "• دعم جميع أنواع الملفات الصوتية: MP3، FLAC، OGG، WAV، M4A، AAC\n"
                    "• تعديل كامل لوسوم ID3v2 مع واجهة تفاعلية سهلة الاستخدام\n"
                    "• حفظ قوالب مخصصة لكل فنان لتطبيقها بسهولة على الملفات\n"
                    "• إمكانية إضافة وتعديل صور الألبوم عالية الدقة\n"
                    "• استخراج وتعديل كلمات الأغاني\n"
                    "• إنشاء قوالب يدوية بدون الحاجة لملف صوتي\n"
                    "• معالجة متقدمة للوسوم مع دعم كامل للغة العربية\n\n"
                    
                    "*🔹 ميزات متقدمة:*\n"
                    "• نظام معالجة تلقائية للملفات الصوتية من القنوات\n"
                    "• استبدال نصوص تلقائي في الوسوم\n"
                    "• تطبيق قوالب ذكية حسب اسم الفنان\n"
                    "• حفظ الملفات مع الحفاظ على جودة الصوت الأصلية\n"
                    "• تحسين تلقائي لصور الألبوم في تيليجرام\n"
                    "• دعم الضغط بضغطة واحدة على وسم معين لتعديله\n"
                    "• حماية من حالات الخطأ مع تقارير تشخيصية متقدمة\n\n"
                    
                    "*🔹 للاستخدام:*\n"
                    "• أرسل ملفًا صوتيًا للبوت ليعرض لك الوسوم الحالية وخيارات التعديل\n"
                    "• استخدم قائمة 'إدارة القوالب' لإنشاء وتطبيق القوالب\n"
                    "• اضغط على وسم معين لتعديل قيمته\n"
                    "• احفظ التغييرات بعد الانتهاء من التعديل\n\n"
                    
                    "*🔹 قناة البوت:*\n"
                    "• [@zawamlAnsarAlllah](https://t.me/zawamlAnsarAlllah)\n\n"
                    
                    "*🔹 تطوير:*\n"
                    "• المطور: [عدي الغولي](https://t.me/odaygholy)\n\n"
                    
                    "*📚 للمساعدة:* استخدم الأمر /help"
                )
                
                # إنشاء لوحة مفاتيح مع زر العودة
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
                
                try:
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=about_text,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error editing message for about_bot: {e}")
                    bot.send_message(
                        call.message.chat.id,
                        about_text,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    
            elif call.data == 'edit_tags':
                # Handle edit tags button
                handle_edit_tags(call.message, user_id)
                
            # تم حذف وظيفة تنزيل بدون تعديل بناءً على طلب المستخدم
                
            elif call.data == 'show_templates':
                # Show templates menu
                handle_show_templates(call.message, user_id)
                
            elif call.data == 'save_template':
                # Save current tags as template
                handle_save_template(call.message, user_id)
                
            elif call.data.startswith('artist_templates_'):
                # Show templates for specific artist
                artist_name = call.data.replace('artist_templates_', '')
                handle_show_artist_templates(call.message, user_id, artist_name)
                
            elif call.data == 'apply_template_menu':
                # عرض قائمة القوالب المتاحة للتطبيق على الملف الصوتي الحالي
                logger.info(f"User {user_id} wants to apply a template from the audio view")
                
                # التأكد من وجود ملف صوتي
                if user_id not in user_data or 'file_path' not in user_data[user_id]:
                    bot.send_message(
                        call.message.chat.id,
                        "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً."
                    )
                    return
                
                # جلب قائمة الفنانين الذين لديهم قوالب
                artists = get_artists_with_templates()
                
                if not artists:
                    bot.send_message(
                        call.message.chat.id,
                        "لا توجد قوالب محفوظة بعد. قم بإنشاء قالب أولاً من خلال قائمة إدارة القوالب."
                    )
                    return
                
                # إنشاء لوحة مفاتيح مع أسماء الفنانين
                markup = types.InlineKeyboardMarkup(row_width=1)
                for artist in artists:
                    markup.add(types.InlineKeyboardButton(
                        text=f"🎵 {artist}",
                        callback_data=f"apply_artist_templates_{artist}"
                    ))
                markup.add(types.InlineKeyboardButton("🔙 رجوع للوسوم", callback_data="back_to_tags"))
                
                # حفظ رسالة القائمة في بيانات المستخدم لتنظيفها لاحقاً
                message = bot.send_message(
                    call.message.chat.id,
                    "🗂️ اختر الفنان الذي تريد تطبيق أحد قوالبه:",
                    reply_markup=markup
                )
                
                # حفظ معرف الرسالة للتنظيف
                user_data[user_id] = user_data.get(user_id, {})
                user_data[user_id]['ui_messages'] = user_data[user_id].get('ui_messages', [])
                user_data[user_id]['ui_messages'].append(message.message_id)
            
            elif call.data.startswith('apply_artist_templates_'):
                # عرض قوالب فنان محدد للتطبيق
                artist_name = call.data.replace('apply_artist_templates_', '')
                logger.info(f"User {user_id} wants to apply template from artist: {artist_name}")
                
                # التأكد من وجود ملف صوتي
                if user_id not in user_data or 'file_path' not in user_data[user_id]:
                    bot.send_message(
                        call.message.chat.id,
                        "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً."
                    )
                    return
                
                # جلب قوالب الفنان
                templates = list_templates(artist_name)
                
                if not templates:
                    bot.send_message(
                        call.message.chat.id,
                        f"لا توجد قوالب محفوظة للفنان '{artist_name}'."
                    )
                    return
                
                # إنشاء لوحة مفاتيح مع أسماء القوالب
                markup = types.InlineKeyboardMarkup(row_width=1)
                for template in templates:
                    # إضافة أيقونة للقوالب التي لديها صورة
                    icon = "🖼️" if template.get("has_image") else "📋"
                    markup.add(types.InlineKeyboardButton(
                        text=f"{icon} {template['name']}",
                        callback_data=f"direct_apply_template_{template['id']}"
                    ))
                markup.add(types.InlineKeyboardButton("🔙 رجوع لاختيار الفنان", callback_data="apply_template_menu"))
                
                # حفظ رسالة القائمة في بيانات المستخدم لتنظيفها لاحقاً
                message = bot.send_message(
                    call.message.chat.id,
                    f"اختر القالب الذي تريد تطبيقه من قوالب الفنان '{artist_name}':",
                    reply_markup=markup
                )
                
                # حفظ معرف الرسالة للتنظيف
                user_data[user_id] = user_data.get(user_id, {})
                user_data[user_id]['ui_messages'] = user_data[user_id].get('ui_messages', [])
                user_data[user_id]['ui_messages'].append(message.message_id)
            
            elif call.data.startswith('direct_apply_template_'):
                # تطبيق قالب على الملف الصوتي مباشرة من قائمة الوسوم
                template_id = call.data.replace('direct_apply_template_', '')
                logger.info(f"User {user_id} wants to directly apply template: {template_id} to current audio file")
                
                # التأكد من وجود ملف صوتي
                if user_id not in user_data or 'file_path' not in user_data[user_id]:
                    bot.send_message(
                        call.message.chat.id,
                        "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً."
                    )
                    return
                
                # تنظيف رسائل واجهة المستخدم المؤقتة
                cleanup_ui_messages(user_id, call.message.chat.id, bot)
                
                # جلب القالب
                template = get_template(template_id)
                if not template:
                    bot.send_message(
                        call.message.chat.id,
                        f"لم يتم العثور على القالب المحدد."
                    )
                    return
                
                # الحصول على مسار الملف الصوتي
                file_path = user_data[user_id]['file_path']
                
                # حفظ الوسوم الأصلية قبل التطبيق
                original_tags = get_audio_tags(file_path)
                user_data[user_id]['original_tags'] = original_tags
                
                # دمج وسوم القالب مع الوسوم الحالية (مع الحفاظ على الوسوم غير الموجودة في القالب)
                merged_tags = original_tags.copy()  # بدء من الوسوم الأصلية
                
                # التحقق من بنية القالب
                template_tags = {}
                
                # القوالب القديمة تخزن الوسوم في مفتاح 'tags'
                if 'tags' in template:
                    template_tags = template['tags']
                # القوالب الجديدة تخزن الوسوم مباشرة في القالب
                else:
                    # استنساخ القالب ولكن استبعاد 'album_art' إذا كان موجودًا
                    template_tags = {k: v for k, v in template.items() if k != 'album_art'}
                
                # تسجيل بنية القالب للتصحيح
                logger.debug(f"هيكل القالب: {template.keys()}")
                logger.debug(f"الوسوم المستخرجة: {template_tags.keys()}")
                
                # تحديث الوسوم من القالب فقط إذا كان الوسم موجود في القالب وله قيمة
                for tag_name, tag_value in template_tags.items():
                    if tag_value:  # فقط إذا كانت قيمة الوسم في القالب غير فارغة
                        # إذا كان الوسم هو صورة الألبوم وكانت الصورة موجودة في القالب
                        if tag_name == 'picture' and 'album_art' in template and template['album_art']:
                            # استخدام صورة الألبوم من القالب
                            merged_tags[tag_name] = base64.b64decode(template['album_art'])
                        # معالجة خاصة لكلمات الأغنية للتأكد من الحفاظ على تنسيق الأسطر المتعددة
                        elif tag_name == 'lyrics':
                            # الحفاظ على تنسيق الأسطر المتعددة ومعالجتها بشكل صحيح
                            lyrics_text = tag_value
                            
                            # التحقق مما إذا كانت القيمة تبدأ بعلامة $ (متغير)
                            if isinstance(lyrics_text, str) and lyrics_text.startswith('$'):
                                # استخراج اسم الوسم والنص الإضافي (إن وجد)
                                
                                # البحث عن الكلمات الشائعة التي قد تكون وسوما
                                common_tags = ['title', 'artist', 'album', 'album_artist', 'year', 'genre', 'composer', 'comment', 'track', 'length', 'lyrics']
                                
                                # البحث عن أول تطابق مع أسماء الوسوم المعروفة
                                var_name = None
                                additional_text = ''
                                
                                # التحقق من حالة خاصة: الوسم بدون مسافة والنص ملتصق به
                                # مثل: $lyricst.me/ZawamlAnsarallah
                                for tag in common_tags:
                                    if lyrics_text[1:].startswith(tag):
                                        var_name = tag
                                        additional_text = lyrics_text[len(tag) + 1:]  # +1 للعلامة $
                                        break
                                
                                # إذا لم نجد تطابقا مع الحالة الخاصة، نستخدم التقسيم العادي
                                if var_name is None:
                                    parts = lyrics_text.split(' ', 1)
                                    var_name = parts[0][1:]  # استخراج اسم الوسم بدون علامة $
                                    additional_text = parts[1] if len(parts) > 1 else ''
                                
                                # تحويل \n إلى أسطر جديدة حقيقية
                                if additional_text:
                                    additional_text = additional_text.replace('\\n', '\n')
                                
                                # التحقق مما إذا كان الوسم المطلوب موجودًا في الوسوم الأصلية
                                if var_name in original_tags and original_tags[var_name]:
                                    # دمج القيمة الأصلية مع النص الإضافي
                                    merged_value = original_tags[var_name]
                                    if additional_text:
                                        # إضافة النص الإضافي مع الأخذ بعين الاعتبار أن المتغير قد يكون كلمات الأغنية
                                        if isinstance(merged_value, str):
                                            # نحتاج للتأكد من إضافة سطر جديد إذا لم يكن هناك
                                            if additional_text.startswith('\n'):
                                                merged_value = f"{merged_value}{additional_text}"
                                            else:
                                                merged_value = f"{merged_value}\n{additional_text}"
                                    
                                    # تعيين القيمة المدمجة للوسم
                                    lyrics_text = merged_value
                                    logger.info(f"استخدام متغير ${var_name} وإضافة النص الإضافي '{additional_text}' للوسم {tag_name}")
                                else:
                                    # إذا لم يكن الوسم المطلوب موجودًا، استخدم النص الإضافي فقط (إن وجد)
                                    if additional_text:
                                        lyrics_text = additional_text
                                    # وإلا نضع النص كما هو بدون المتغير
                                    else:
                                        lyrics_text = lyrics_text.replace('$' + var_name, '')
                            else:
                                # تحويل \n إلى أسطر جديدة حقيقية إذا كان النص عاديًا
                                lyrics_text = lyrics_text.replace('\\n', '\n')
                            
                            # تنظيف أي تنسيق خاص قد يتسبب في مشاكل
                            lyrics_text = lyrics_text.replace('\r\n', '\n').replace('\r', '\n')
                            
                            # تأكد أن الأسطر المتعددة في كلمات الأغنية تظل محفوظة
                            merged_tags[tag_name] = lyrics_text
                            first_line = lyrics_text.split("\n")[0] if "\n" in lyrics_text else lyrics_text
                            logger.info(f"Applied lyrics from template, length: {len(lyrics_text)}, first line: {first_line}")
                        else:
                            # التحقق مما إذا كانت القيمة تبدأ بعلامة $ متبوعة باسم وسم (وربما نص إضافي)
                            if isinstance(tag_value, str) and tag_value.startswith('$'):
                                # استخراج اسم الوسم والنص الإضافي (إن وجد)
                                
                                # البحث عن الكلمات الشائعة التي قد تكون وسوما
                                common_tags = ['title', 'artist', 'album', 'album_artist', 'year', 'genre', 'composer', 'comment', 'track', 'length', 'lyrics']
                                
                                # البحث عن أول تطابق مع أسماء الوسوم المعروفة
                                var_name = None
                                additional_text = ''
                                
                                # التحقق من حالة خاصة: الوسم بدون مسافة والنص ملتصق به
                                # مثل: $composert.me/ZawamlAnsarallah
                                for tag in common_tags:
                                    if tag_value[1:].startswith(tag):
                                        var_name = tag
                                        additional_text = tag_value[len(tag) + 1:]  # +1 للعلامة $
                                        break
                                
                                # إذا لم نجد تطابقا مع الحالة الخاصة، نستخدم التقسيم العادي
                                if var_name is None:
                                    parts = tag_value.split(' ', 1)
                                    var_name = parts[0][1:]  # استخراج اسم الوسم بدون علامة $
                                    additional_text = parts[1] if len(parts) > 1 else ''
                                
                                # تحويل \n إلى أسطر جديدة حقيقية في النص الإضافي
                                if additional_text:
                                    additional_text = additional_text.replace('\\n', '\n')
                                
                                # التحقق مما إذا كان الوسم المطلوب موجودًا في الوسوم الأصلية
                                if var_name in original_tags and original_tags[var_name]:
                                    # دمج القيمة الأصلية مع النص الإضافي
                                    merged_value = original_tags[var_name]
                                    if additional_text:
                                        # إضافة مسافة بين القيمة الأصلية والنص الإضافي إذا كانت القيمة الأصلية نصية
                                        if isinstance(merged_value, str):
                                            merged_value = f"{merged_value} {additional_text}"
                                        else:
                                            # إذا لم تكن القيمة الأصلية نصية (مثل الصورة)، نستخدمها كما هي
                                            pass
                                    
                                    # تعيين القيمة المدمجة للوسم
                                    merged_tags[tag_name] = merged_value
                                    logger.info(f"استخدام متغير ${var_name} وإضافة النص الإضافي '{additional_text}' للوسم {tag_name}")
                                else:
                                    # إذا لم يكن الوسم المطلوب موجودًا، استخدم النص الإضافي فقط (إن وجد)
                                    if additional_text:
                                        merged_tags[tag_name] = additional_text
                                    # وإلا نضع قيمة الوسم كما هي (ربما لدينا قيمة تبدأ بـ $ عن طريق الخطأ)
                                    else:
                                        merged_tags[tag_name] = tag_value
                            else:
                                # استخدام قيمة الوسم من القالب
                                merged_tags[tag_name] = tag_value
                    
                # إذا كان القالب لا يحتوي على صورة ألبوم ولكن الملف الأصلي يحتوي عليها، نحتفظ بها
                if 'picture' in original_tags and ('picture' not in template_tags or not template_tags['picture']):
                    merged_tags['picture'] = original_tags['picture']
                
                # حفظ الوسوم المدمجة كوسوم مؤقتة
                user_data[user_id]['temp_tags'] = merged_tags
                
                # استخراج اسم القالب من معرف الاستدعاء
                template_name = call.data.replace('direct_apply_template_', '')
                
                # رسالة تأكيد
                bot.send_message(
                    call.message.chat.id,
                    f"✅ تم تطبيق القالب '{template_name}' بنجاح. اضغط على زر 'حفظ التغييرات' لحفظ التعديلات."
                )
                
                # عرض الوسوم المحدثة للمستخدم
                display_current_tags(call.message, user_id, file_path, show_edited=True)
                
            elif call.data.startswith('apply_template_'):
                # Apply selected template (للاستخدام في واجهة إدارة القوالب)
                template_id = call.data.replace('apply_template_', '')
                handle_apply_template(call.message, user_id, template_id)
                
            elif call.data == 'back_from_edit':
                # Return to the main file view without saving changes
                logger.info(f"User {user_id} wants to go back from edit tags without saving")
                
                # Check if we have the file
                if user_id not in user_data or 'file_path' not in user_data[user_id]:
                    bot.send_message(call.message.chat.id, "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً.")
                    return
                
                # تنظيف رسائل واجهة المستخدم الحالية
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                    logger.debug(f"Deleted edit panel message: {call.message.message_id}")
                except Exception as e:
                    logger.error(f"Error deleting message: {e}")
                
                # عرض الوسوم الأصلية من جديد (بدون الوسوم المعدلة)
                file_path = user_data[user_id]['file_path']
                # تأكد من استخدام الوسوم الأصلية وليس المعدلة
                if 'temp_tags' in user_data[user_id]:
                    del user_data[user_id]['temp_tags']
                
                display_current_tags(call.message, user_id, file_path, show_edited=False)
                
            elif call.data == 'back_to_template_menu':
                # Return to templates menu
                handle_show_templates(call.message, user_id)
                
            elif call.data == 'cancel':
                # Handle cancel button
                handle_cancel_operation(call.message, user_id)
                
            elif call.data == 'save_tags':
                # حفظ التغييرات بعد تطبيق القالب أو تعديل الوسوم
                logger.info(f"User {user_id} wants to save tags after template application")
                
                # التحقق من وجود ملف صوتي
                if user_id not in user_data or 'file_path' not in user_data[user_id]:
                    bot.send_message(call.message.chat.id, "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً.")
                    return
                
                # التحقق من وجود تغييرات على الوسوم (إما من القالب أو من التعديلات اليدوية)
                has_changes = False
                if 'temp_tags' in user_data[user_id] and user_data[user_id]['temp_tags']:
                    logger.info(f"Found temp_tags for user {user_id}, proceeding with save.")
                    has_changes = True
                elif 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
                    logger.info(f"Found new_tags for user {user_id}, proceeding with save.")
                    has_changes = True
                    
                if not has_changes:
                    bot.send_message(call.message.chat.id, "لم يتم العثور على تغييرات للحفظ. الرجاء تعديل الوسوم أو تطبيق قالب أولاً.")
                    return
                
                # إنشاء كائن رسالة افتراضي للاستخدام في وظيفة save_tags
                message_wrapper = SimpleNamespace()
                message_wrapper.chat = SimpleNamespace()
                message_wrapper.chat.id = call.message.chat.id
                message_wrapper._direct_user_id = user_id  # إضافة معرف المستخدم مباشرة في الكائن
                
                # استدعاء وظيفة save_tags لحفظ التعديلات
                bot.send_message(call.message.chat.id, "جاري حفظ التغييرات، يرجى الانتظار...")
                
                # استدعاء وظيفة save_tags لحفظ التعديلات
                save_tags(message_wrapper, bot)
                
            elif call.data == 'done_editing':
                # Handle done editing button
                logger.info(f"Done editing button pressed by user {user_id}")
                
                if user_id in user_data and 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
                    logger.info(f"User {user_id} finished editing with tags: {user_data[user_id]['new_tags']}")
                    
                    # Create a wrapper message object that has the chat.id
                    # We know user_id is the chat.id in this case
                    # Create a direct reference to call.message for better reliability
                    message_wrapper = call.message
                    # Add a custom property to message for identifying user ID in save_tags
                    message_wrapper._direct_user_id = user_id
                    
                    # Pass the message wrapper to save_tags
                    save_tags(message_wrapper, bot)
                else:
                    bot.send_message(call.message.chat.id, "لم تقم بتعديل أي وسوم. الرجاء تعديل وسم واحد على الأقل أو إلغاء العملية.")
                    
            elif call.data == 'upload_picture':
                # Handle picture upload request
                logger.info(f"User {user_id} wants to upload album art")
                
                # Add a waiting_for_album_art flag to user data
                if user_id not in user_data:
                    user_data[user_id] = {}
                user_data[user_id]['waiting_for_album_art'] = True
                
                # Send message to user
                bot.send_message(
                    call.message.chat.id,
                    "الرجاء إرسال صورة لاستخدامها كصورة غلاف للملف الصوتي. 🖼️"
                )
                
            elif call.data.startswith('edit_tag_'):
                # Handle edit specific tag button
                tag_name = call.data.replace('edit_tag_', '')
                logger.info(f"User {user_id} wants to edit tag: {tag_name}")
                
                # Special handling for lyrics
                if tag_name == 'lyrics':
                    try:
                        bot.answer_callback_query(
                            call.id,
                            "جاري تحضير واجهة تعديل الكلمات..."
                        )
                        
                        # Store the tag being edited
                        if user_id not in user_data:
                            user_data[user_id] = {'new_tags': {}}
                        if 'new_tags' not in user_data[user_id]:
                            user_data[user_id]['new_tags'] = {}
                            
                        # Check if file path exists in user data
                        if 'file_path' not in user_data[user_id]:
                            # No file path means user hasn't sent a file yet
                            bot.send_message(
                                call.message.chat.id,
                                "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً."
                            )
                            return
                            
                        # Store the tag we're editing
                        user_data[user_id]['editing_tag'] = tag_name
                        
                        # Get file path
                        file_path = user_data[user_id]['file_path']
                        
                        # Get current lyrics value
                        try:
                            current_tags = get_audio_tags(file_path)
                            current_value = current_tags.get('lyrics', '')
                            
                            # Try extended lyrics extraction if not found in normal tags
                            if not current_value:
                                current_value = extract_lyrics(file_path)
                                logger.info(f"Used extended lyrics extraction: {bool(current_value)}")
                        except Exception as e:
                            logger.error(f"Error re-extracting lyrics: {e}")
                            current_value = ""
                        
                        # Check if we have new tags already
                        if 'lyrics' in user_data[user_id]['new_tags']:
                            current_value = user_data[user_id]['new_tags']['lyrics']
                        
                        # Create back button
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton(text="رجوع", callback_data="back_to_tags"))
                        
                        # عرض كلمات الأغنية فقط - بدون أي عناوين أو نصوص إضافية
                        message_text = ""
                        
                        if current_value:
                            # عرض النص كاملاً بناءً على طلب المستخدم
                            # لكن مع مراعاة حد تيليجرام الأقصى (4096 حرف)
                            
                            max_chars = 4000  # حد قريب من الحد الأقصى لتيليجرام مع ترك هامش
                            if len(current_value) > max_chars:
                                # تقصير النص فقط إذا تجاوز حد تيليجرام 
                                message_text = current_value[:max_chars] + "...\n\n(النص طويل جدًا وتم اقتصاصه لأن تيليجرام لا يسمح بأكثر من 4096 حرف في الرسالة)"
                            else:
                                # عرض النص كاملاً إذا كان ضمن الحدود المسموح بها
                                message_text = current_value
                        else:
                            message_text = "لا توجد كلمات أغنية مخزنة في الملف"
                        
                        # Send a new message instead of editing to avoid Markdown issues
                        try:
                            # Delete previous message
                            bot.delete_message(call.message.chat.id, call.message.message_id)
                            
                            # Send completely new message
                            sent_msg = bot.send_message(
                                call.message.chat.id,
                                message_text,
                                reply_markup=markup
                            )
                            
                            # Keep track of message ID
                            user_data[user_id]['current_edit_message_id'] = sent_msg.message_id
                            
                            # Set state
                            bot.set_state(user_id, BotStates.waiting_for_specific_tag, call.message.chat.id)
                            logger.info(f"Special lyrics handler: Set state to {BotStates.waiting_for_specific_tag.name}")
                            
                            # Exit early, we've handled lyrics specially
                            return
                            
                        except Exception as e:
                            logger.error(f"Error in special lyrics handler: {e}")
                            error_data = log_error(
                                "LYRICS_HANDLER_ERROR",
                                str(e),
                                user_id,
                                "edit_tag_lyrics_special",
                                {'callback_data': call.data}
                            )
                            bot_status["errors"].append(error_data)
                            
                            # If we fail, let the regular handler take over
                            pass
                    except Exception as outer_e:
                        logger.error(f"Outer error in lyrics special handler: {outer_e}")
                        # Continue with normal flow if special handling fails
                
                # Regular handling for other tags
                # Store the tag being edited
                if user_id not in user_data:
                    user_data[user_id] = {'new_tags': {}}
                
                # Make sure all required keys exist
                if 'new_tags' not in user_data[user_id]:
                    user_data[user_id]['new_tags'] = {}
                if 'current_tags' not in user_data[user_id]:
                    user_data[user_id]['current_tags'] = {}
                    
                # Store the tag being edited
                user_data[user_id]['editing_tag'] = tag_name
                
                # Get current value from the complete tags (always use original file data)
                current_value = ''
                
                # قراءة الوسوم من الملف
                file_path = user_data[user_id]['file_path']
                file_tags = get_audio_tags(file_path)
                
                # دمج الوسوم من الملف مع التعديلات
                if 'new_tags' in user_data[user_id]:
                    # نسخ الوسوم من الملف
                    merged_tags = {**file_tags}
                    # تطبيق التعديلات
                    for tag, value in user_data[user_id]['new_tags'].items():
                        merged_tags[tag] = value
                else:
                    merged_tags = file_tags
                
                # الحصول على القيمة الحالية من الوسوم المدمجة
                if tag_name in merged_tags:
                    current_value = merged_tags[tag_name]
                # استخدام القيم المخزنة كبديل إذا لزم الأمر
                elif 'complete_tags' in user_data[user_id] and tag_name in user_data[user_id]['complete_tags']:
                    current_value = user_data[user_id]['complete_tags'][tag_name]
                # استخدام القيم الحالية كبديل آخر
                elif 'current_tags' in user_data[user_id] and tag_name in user_data[user_id]['current_tags']:
                    current_value = user_data[user_id]['current_tags'][tag_name]
                
                # If we still don't have a value and it's lyrics, try to extract it directly from the file
                if (not current_value or current_value == 'غير محدد') and tag_name == 'lyrics':
                    try:
                        # Re-read the file to get the most up-to-date tags
                        file_path = user_data[user_id]['file_path']
                        logger.info(f"Trying to extract lyrics directly from file: {file_path}")
                        
                        # For MP3 files, try to extract USLT frame specifically
                        if file_path.lower().endswith('.mp3'):
                            try:
                                from mutagen.id3 import ID3
                                audio = ID3(file_path)
                                
                                # Look for any USLT frame
                                for key in audio.keys():
                                    if key.startswith('USLT'):
                                        uslt_frame = audio[key]
                                        if hasattr(uslt_frame, 'text'):
                                            current_value = uslt_frame.text
                                            logger.info(f"Found USLT lyrics: {current_value[:50]}...")
                                            break
                            except Exception as e:
                                logger.error(f"Error extracting USLT frame: {e}")
                        
                        # If we still don't have lyrics, try the general approach
                        if not current_value:
                            fresh_tags = get_audio_tags(file_path)
                            if 'lyrics' in fresh_tags:
                                current_value = fresh_tags['lyrics']
                                # Update stored tags
                                user_data[user_id]['complete_tags'] = fresh_tags
                                logger.info(f"Re-extracted lyrics for user {user_id}: {current_value[:50]}...")
                    except Exception as e:
                        logger.error(f"Error re-extracting lyrics: {e}")
                        
                # For lyrics specifically, if still no value found, set appropriate message
                if (not current_value or current_value == 'غير محدد') and tag_name == 'lyrics':
                    current_value = ""
                    logger.info(f"No lyrics found for file")
                
                # Get Arabic name
                arabic_names = get_tag_field_names_arabic()
                arabic_name = arabic_names.get(tag_name, tag_name)
                
                # Format the current value for display
                display_value = current_value
                
                # For lyrics, show all of the text (as telegram allows up to 4096 characters per message)
                if tag_name == 'lyrics' and current_value:
                    # Show as much of the lyrics as possible
                    # Telegram message limit is 4096 chars, we'll leave some space for other text
                    # and formatting in the message
                    max_chars = 3800
                    if len(current_value) > max_chars:
                        display_value = current_value[:max_chars] + "...\n\n(الكلمات طويلة جدًا وتم اقتصاصها. ستتمكن من تعديل النص الكامل)"
                    else:
                        display_value = current_value
                    
                # Create back button
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(text="رجوع", callback_data="back_to_tags"))
                
                # Prepare message text
                message_text = f"📝 تعديل وسم: *{arabic_name}*\n\n"
                
                if display_value:
                    # For lyrics (usually longer text), maintain original formatting, but NO special characters to avoid API errors
                    if tag_name == 'lyrics':
                        message_text += "القيمة الحالية:\n"
                        # Don't use any markdown or special formatting
                        if len(display_value) > 0:
                            message_text += display_value + "\n\n"
                        message_text += "يمكنك نسخ النص عن طريق الضغط أدناه\n\n"
                    # For other tags, wrap in code ticks for easy copying
                    else:
                        message_text += f"*القيمة الحالية:*\n`{display_value}`\n\n"
                else:
                    # Special handling for lyrics
                    if tag_name == 'lyrics':
                        message_text += "*القيمة الحالية:* لا توجد كلمات أغنية مخزنة في الملف\n\n"
                    else:
                        message_text += "*القيمة الحالية:* غير موجودة\n\n"
                
                message_text += "الرجاء إدخال القيمة الجديدة:"
                
                # Edit the current message instead of sending a new one
                try:
                    # Store the original message ID if we haven't already (for going back later)
                    if 'edit_panel_message_id' not in user_data[user_id]:
                        user_data[user_id]['edit_panel_message_id'] = call.message.message_id
                    
                    # Special handling for lyrics to avoid Markdown parsing issues
                    parse_mode = "Markdown"
                    if tag_name == 'lyrics':
                        # For lyrics, completely disable Markdown which can cause parsing issues with special characters
                        parse_mode = None
                        # Create a completely clean message without any Markdown or special characters
                        arabic_name_clean = arabic_names.get(tag_name, tag_name)
                        message_text = f"📝 تعديل وسم: {arabic_name_clean}\n\n"
                        message_text += "القيمة الحالية:\n"
                        
                        if display_value and len(display_value) > 0:
                            message_text += display_value + "\n\n"
                        else:
                            message_text += "لا توجد كلمات أغنية مخزنة في الملف\n\n"
                            
                        message_text += "الرجاء إدخال القيمة الجديدة:"
                    
                    # Check if message has text content before trying to edit
                    if hasattr(call.message, 'text') and call.message.text is not None:
                        # Edit the current message
                        bot.edit_message_text(
                            text=message_text,
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            reply_markup=markup,
                            parse_mode=parse_mode
                        )
                        
                        # Keep track of this message being the currently active one
                        user_data[user_id]['current_edit_message_id'] = call.message.message_id
                    else:
                        # Message doesn't have text content (e.g., it's a photo), send new message
                        raise Exception("Message doesn't have text content to edit")
                    
                except Exception as e:
                    logger.error(f"Error editing message: {e}")
                    # Fall back to sending a new message if editing fails
                    sent_msg = bot.send_message(
                        call.message.chat.id,
                        message_text,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    
                    # Store the new message ID for future reference
                    user_data[user_id]['current_edit_message_id'] = sent_msg.message_id
                    
                    # Store the message ID for deletion later
                    if 'messages_to_delete' not in user_data[user_id]:
                        user_data[user_id]['messages_to_delete'] = []
                    user_data[user_id]['messages_to_delete'].append(sent_msg.message_id)
                
                # Set state to waiting for specific tag value
                try:
                    logger.info(f"Setting state to waiting_for_specific_tag for user {user_id}")
                    # Make sure we have all necessary user data
                    if 'editing_tag' not in user_data[user_id]:
                        logger.error(f"editing_tag not in user_data for user {user_id}")
                        bot.send_message(call.message.chat.id, "حدث خطأ في تحديد الوسم المراد تعديله. يرجى المحاولة مرة أخرى.")
                        return
                    
                    # Set state to waiting for specific tag
                    bot.set_state(user_id, BotStates.waiting_for_specific_tag, call.message.chat.id)
                    
                    # Add a helpful message
                    bot.send_message(
                        call.message.chat.id, 
                        f"أنا أنتظر قيمة جديدة للوسم '{arabic_name}'. الرجاء إدخال القيمة الآن.",
                        reply_to_message_id=call.message.message_id
                    )
                except Exception as e:
                    logger.error(f"Failed to set state: {e}")
                    bot.send_message(call.message.chat.id, "حدث خطأ في تعيين الحالة. يرجى المحاولة مرة أخرى.")
                
            elif call.data == 'manage_templates':
                # Handle manage templates button
                logger.info(f"User {user_id} wants to manage templates")
                
                # إنشاء لوحة مفاتيح للإدارة
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("📝 إنشاء قالب يدوي", callback_data="create_manual_template"),
                    types.InlineKeyboardButton("📋 عرض القوالب", callback_data="show_templates")
                )
                markup.add(
                    types.InlineKeyboardButton("❌ حذف قالب", callback_data="delete_template"),
                    types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="edit_template")
                )
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
                
                bot.send_message(
                    call.message.chat.id,
                    "🗂️ *إدارة القوالب*\n\n"
                    "• استخدم *إنشاء قالب يدوي* لإضافة قالب جديد عن طريق إدخال الوسوم يدوياً\n"
                    "• استخدم *عرض القوالب* لاستعراض القوالب المحفوظة وتطبيقها\n"
                    "• استخدم *حذف قالب* لإزالة قالب موجود\n"
                    "• استخدم *تعديل قالب* لتغيير محتوى قالب موجود",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            elif call.data == 'create_manual_template':
                # Handle create manual template button
                logger.info(f"User {user_id} wants to create a manual template")
                
                # تعيين الحالة لانتظار إدخال البيانات اليدوية
                bot.set_state(user_id, BotStates.waiting_for_manual_template, call.message.chat.id)
                
                # إعداد نموذج للمستخدم
                template_format = """لإنشاء قالب يدوي، قم بملء الوسوم التالية:

title: 
artist: 
album: 
album_artist: 
year: 
genre: 
composer: 
comment: 
track: 
length: 
lyrics: 

أرسل هذه البيانات مع قيمك الخاصة.
يمكنك ترك بعض الحقول فارغة إذا لم ترغب بتضمينها.
"""
                
                # إنشاء لوحة مفاتيح مع زر إلغاء
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("إلغاء ❌", callback_data="cancel_template_creation"))
                
                # إرسال النموذج للمستخدم
                bot.send_message(
                    call.message.chat.id,
                    template_format,
                    reply_markup=markup
                )
                
            elif call.data == 'cancel_template_creation':
                # إلغاء عملية إنشاء القالب
                logger.info(f"User {user_id} canceled template creation")
                bot.delete_state(user_id, call.message.chat.id)
                bot.send_message(call.message.chat.id, "تم إلغاء إنشاء القالب.")
                
                # العودة إلى قائمة إدارة القوالب عن طريق معالج manage_templates
                # سنستخدم الحل البديل حيث أن الدالة return_to_template_management لم يتم تعريفها بعد
                # في هذا السياق، نحاكي السلوك عن طريق استدعاء معالج زر إدارة القوالب
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("📝 إنشاء قالب يدوي", callback_data="create_manual_template"),
                    types.InlineKeyboardButton("📋 عرض القوالب", callback_data="show_templates")
                )
                markup.add(
                    types.InlineKeyboardButton("❌ حذف قالب", callback_data="delete_template"),
                    types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="edit_template")
                )
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
                
                bot.send_message(
                    call.message.chat.id,
                    "🗂️ *إدارة القوالب*\n\n"
                    "• استخدم *إنشاء قالب يدوي* لإضافة قالب جديد عن طريق إدخال الوسوم يدوياً\n"
                    "• استخدم *عرض القوالب* لاستعراض القوالب المحفوظة وتطبيقها\n"
                    "• استخدم *حذف قالب* لإزالة قالب موجود\n"
                    "• استخدم *تعديل قالب* لتغيير محتوى قالب موجود",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )

            elif call.data == 'delete_template':
                # Handle delete template button
                logger.info(f"User {user_id} wants to delete a template")
                
                # جلب قائمة الفنانين الذين لديهم قوالب
                artists = get_artists_with_templates()
                
                if not artists:
                    bot.send_message(
                        call.message.chat.id,
                        "لا توجد قوالب محفوظة للحذف."
                    )
                    return
                
                # إنشاء لوحة مفاتيح مع أسماء الفنانين
                markup = types.InlineKeyboardMarkup(row_width=1)
                for artist in artists:
                    markup.add(types.InlineKeyboardButton(
                        text=f"🎵 {artist}",
                        callback_data=f"delete_artist_templates_{artist}"
                    ))
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="manage_templates"))
                
                bot.send_message(
                    call.message.chat.id,
                    "اختر الفنان الذي تريد حذف قوالبه:",
                    reply_markup=markup
                )
            
            elif call.data.startswith('delete_artist_templates_'):
                # Handle selecting artist for template deletion
                artist_name = call.data.replace('delete_artist_templates_', '')
                logger.info(f"User {user_id} is viewing templates to delete for artist: {artist_name}")
                
                # جلب قوالب الفنان
                templates = list_templates(artist_name)
                
                if not templates:
                    bot.send_message(
                        call.message.chat.id,
                        f"لا توجد قوالب محفوظة للفنان '{artist_name}'."
                    )
                    return
                
                # إنشاء لوحة مفاتيح مع أسماء القوالب
                markup = types.InlineKeyboardMarkup(row_width=1)
                for template in templates:
                    # إضافة أيقونة للقوالب التي لديها صورة
                    icon = "🖼️" if template.get("has_image") else "📋"
                    markup.add(types.InlineKeyboardButton(
                        text=f"{icon} {template['name']}",
                        callback_data=f"confirm_delete_template_{template['id']}"
                    ))
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="delete_template"))
                
                bot.send_message(
                    call.message.chat.id,
                    f"اختر القالب الذي تريد حذفه من قوالب الفنان '{artist_name}':",
                    reply_markup=markup
                )
            
            elif call.data.startswith('confirm_delete_template_'):
                # Handle confirming template deletion
                template_id = call.data.replace('confirm_delete_template_', '')
                logger.info(f"User {user_id} wants to delete template: {template_id}")
                
                # الحصول على بيانات القالب
                template_data = get_template(template_id)
                
                if not template_data:
                    bot.send_message(
                        call.message.chat.id,
                        "هذا القالب غير موجود أو تم حذفه بالفعل."
                    )
                    return
                
                # إنشاء لوحة مفاتيح للتأكيد
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("نعم، احذف القالب ❌", callback_data=f"do_delete_template_{template_id}"),
                    types.InlineKeyboardButton("لا، إلغاء ↩️", callback_data="delete_template")
                )
                
                bot.send_message(
                    call.message.chat.id,
                    f"هل أنت متأكد من أنك تريد حذف القالب '{template_data.get('name')}'؟\n"
                    "لا يمكن التراجع عن هذا الإجراء.",
                    reply_markup=markup
                )
            
            elif call.data.startswith('do_delete_template_'):
                # Handle actual template deletion
                template_id = call.data.replace('do_delete_template_', '')
                logger.info(f"User {user_id} is deleting template: {template_id}")
                
                # حذف القالب
                success = delete_template(template_id)
                
                if success:
                    bot.send_message(
                        call.message.chat.id,
                        "✅ تم حذف القالب بنجاح."
                    )
                else:
                    bot.send_message(
                        call.message.chat.id,
                        "❌ حدث خطأ أثناء حذف القالب. الرجاء المحاولة مرة أخرى."
                    )
                
                # العودة إلى قائمة إدارة القوالب
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("📝 إنشاء قالب يدوي", callback_data="create_manual_template"),
                    types.InlineKeyboardButton("📋 عرض القوالب", callback_data="show_templates")
                )
                markup.add(
                    types.InlineKeyboardButton("❌ حذف قالب", callback_data="delete_template"),
                    types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="edit_template")
                )
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
                
                bot.send_message(
                    call.message.chat.id,
                    "🗂️ *إدارة القوالب*\n\n"
                    "• استخدم *إنشاء قالب يدوي* لإضافة قالب جديد عن طريق إدخال الوسوم يدوياً\n"
                    "• استخدم *عرض القوالب* لاستعراض القوالب المحفوظة وتطبيقها\n"
                    "• استخدم *حذف قالب* لإزالة قالب موجود\n"
                    "• استخدم *تعديل قالب* لتغيير محتوى قالب موجود",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            
            elif call.data == 'show_templates':
                # Handle show templates button
                logger.info(f"User {user_id} wants to view templates")
                
                # جلب قائمة الفنانين الذين لديهم قوالب
                artists = get_artists_with_templates()
                
                if not artists:
                    bot.send_message(
                        call.message.chat.id,
                        "لا توجد قوالب محفوظة بعد. قم بإنشاء قالب جديد أولاً."
                    )
                    return
                
                # إنشاء لوحة مفاتيح مع أسماء الفنانين
                markup = types.InlineKeyboardMarkup(row_width=1)
                for artist in artists:
                    markup.add(types.InlineKeyboardButton(
                        text=f"🎵 {artist}",
                        callback_data=f"show_artist_templates_{artist}"
                    ))
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="manage_templates"))
                
                # حفظ رسالة القائمة في بيانات المستخدم لتنظيفها لاحقاً
                sent_msg = bot.send_message(
                    call.message.chat.id,
                    "اختر الفنان لعرض قوالبه:",
                    reply_markup=markup
                )
                
                # حفظ معرف الرسالة للتنظيف
                user_data[user_id] = user_data.get(user_id, {})
                user_data[user_id]['ui_messages'] = user_data[user_id].get('ui_messages', [])
                user_data[user_id]['ui_messages'].append(sent_msg.message_id)
            
            elif call.data.startswith('show_artist_templates_'):
                # Handle selecting artist for template view
                artist_name = call.data.replace('show_artist_templates_', '')
                logger.info(f"User {user_id} is viewing templates for artist: {artist_name}")
                
                # جلب قوالب الفنان
                templates = list_templates(artist_name)
                
                if not templates:
                    bot.send_message(
                        call.message.chat.id,
                        f"لا توجد قوالب محفوظة للفنان '{artist_name}'."
                    )
                    return
                
                # إنشاء لوحة مفاتيح مع أسماء القوالب
                markup = types.InlineKeyboardMarkup(row_width=1)
                for template in templates:
                    # إضافة أيقونة للقوالب التي لديها صورة
                    icon = "🖼️" if template.get("has_image") else "📋"
                    markup.add(types.InlineKeyboardButton(
                        text=f"{icon} {template['name']}",
                        callback_data=f"view_template_{template['id']}"
                    ))
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="show_templates"))
                
                # حفظ رسالة القائمة في بيانات المستخدم لتنظيفها لاحقاً
                sent_msg = bot.send_message(
                    call.message.chat.id,
                    f"قوالب الفنان '{artist_name}':",
                    reply_markup=markup
                )
                
                # حفظ معرف الرسالة للتنظيف
                user_data[user_id] = user_data.get(user_id, {})
                user_data[user_id]['ui_messages'] = user_data[user_id].get('ui_messages', [])
                user_data[user_id]['ui_messages'].append(sent_msg.message_id)
            
            elif call.data.startswith('view_template_'):
                # Handle viewing template details
                template_id = call.data.replace('view_template_', '')
                logger.info(f"User {user_id} is viewing template: {template_id}")
                
                # الحصول على بيانات القالب
                template_data = get_template(template_id)
                
                if not template_data:
                    bot.send_message(
                        call.message.chat.id,
                        "هذا القالب غير موجود."
                    )
                    return
                
                # إعداد نص عرض القالب
                template_details = f"🗂️ *{template_data.get('name', 'قالب')}*\n\n"
                
                if 'artist' in template_data.get('tags', {}):
                    template_details += f"الفنان: {template_data['tags']['artist']}\n\n"
                
                # إضافة تفاصيل الوسوم
                arabic_names = get_tag_field_names_arabic()
                for tag, value in template_data.get('tags', {}).items():
                    if value and tag != 'lyrics':  # عدم عرض كلمات الأغنية لتجنب رسائل طويلة
                        arabic_name = arabic_names.get(tag, tag)
                        template_details += f"• {arabic_name}: {value}\n"
                
                # إنشاء أزرار التحكم
                markup = types.InlineKeyboardMarkup(row_width=2)
                
                # إضافة زر تطبيق القالب إذا كان هناك ملف صوتي مفتوح حالياً
                if user_id in user_data and 'file_path' in user_data[user_id]:
                    markup.add(types.InlineKeyboardButton(
                        "✅ تطبيق القالب",
                        callback_data=f"apply_template_{template_id}"
                    ))
                
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"show_artist_templates_{template_data.get('artist_name', 'عام')}"))
                
                # إرسال تفاصيل القالب
                bot.send_message(
                    call.message.chat.id,
                    template_details,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
                # إرسال صورة الغلاف إذا كانت موجودة
                if template_data.get('album_art'):
                    try:
                        # إرسال صورة الغلاف كصورة منفصلة
                        bot.send_photo(
                            call.message.chat.id,
                            photo=template_data['album_art'],
                            caption="صورة الغلاف المرفقة مع القالب"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send album art: {e}")
                        bot.send_message(
                            call.message.chat.id,
                            "فشل في عرض صورة الغلاف."
                        )
            
            elif call.data.startswith('apply_template_'):
                # Handle applying template to current audio file
                template_id = call.data.replace('apply_template_', '')
                logger.info(f"User {user_id} is applying template: {template_id}")
                
                # التحقق من وجود ملف صوتي
                if user_id not in user_data or 'file_path' not in user_data[user_id]:
                    bot.send_message(
                        call.message.chat.id,
                        "لا يوجد ملف صوتي مفتوح حالياً. قم بإرسال ملف صوتي أولاً."
                    )
                    return
                
                # الحصول على مسار الملف
                file_path = user_data[user_id]['file_path']
                
                # الحصول على بيانات القالب
                template_data = get_template(template_id)
                
                if not template_data:
                    bot.send_message(
                        call.message.chat.id,
                        "هذا القالب غير موجود."
                    )
                    return
                
                # تحديث الوسوم المؤقتة باستخدام وسوم القالب
                if 'temp_tags' not in user_data[user_id]:
                    # إذا لم تكن هناك وسوم مؤقتة، نبدأ بالوسوم الأصلية
                    original_tags = get_audio_tags(file_path)
                    user_data[user_id]['temp_tags'] = original_tags.copy()
                    
                    # حفظ الوسوم الأصلية للمقارنة
                    if 'original_tags' not in user_data[user_id]:
                        user_data[user_id]['original_tags'] = original_tags.copy()
                
                # دمج وسوم القالب مع الوسوم المؤقتة
                template_tags = template_data.get('tags', {})
                for tag, value in template_tags.items():
                    user_data[user_id]['temp_tags'][tag] = value
                
                # إذا كان القالب يحتوي على صورة، حفظها مؤقتاً
                if template_data.get('album_art'):
                    user_data[user_id]['temp_album_art'] = template_data['album_art']
                    user_data[user_id]['temp_album_art_mime'] = template_data.get('album_art_mime', 'image/jpeg')
                
                bot.send_message(
                    call.message.chat.id,
                    f"✅ تم تطبيق القالب '{template_data.get('name')}' على الملف.\n"
                    "لم يتم حفظ التغييرات بعد. استخدم زر 'حفظ التغييرات' لتأكيد حفظ الوسوم."
                )
                
                # عرض الوسوم المحدثة بإعادة عرض قائمة الوسوم
                handle_edit_tags(call.message, user_id)
                
            elif call.data == 'edit_template':
                # Handle edit template button
                logger.info(f"User {user_id} wants to edit a template")
                
                bot.send_message(
                    call.message.chat.id,
                    "⚠️ لتعديل قالب، يرجى إنشاء قالب جديد ثم حذف القالب القديم."
                )
                
                # العودة إلى قائمة إدارة القوالب
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("📝 إنشاء قالب يدوي", callback_data="create_manual_template"),
                    types.InlineKeyboardButton("📋 عرض القوالب", callback_data="show_templates")
                )
                markup.add(
                    types.InlineKeyboardButton("❌ حذف قالب", callback_data="delete_template"),
                    types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="edit_template")
                )
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
                
                bot.send_message(
                    call.message.chat.id,
                    "🗂️ *إدارة القوالب*\n\n"
                    "• استخدم *إنشاء قالب يدوي* لإضافة قالب جديد عن طريق إدخال الوسوم يدوياً\n"
                    "• استخدم *عرض القوالب* لاستعراض القوالب المحفوظة وتطبيقها\n"
                    "• استخدم *حذف قالب* لإزالة قالب موجود\n"
                    "• استخدم *تعديل قالب* لتغيير محتوى قالب موجود",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            elif call.data == 'back_to_start':
                # العودة إلى رسالة الترحيب
                start_command(call.message)
                
            elif call.data == 'manage_templates':
                # عرض قائمة إدارة القوالب
                logger.info(f"User {user_id} is accessing template management menu")
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("📝 إنشاء قالب يدوي", callback_data="create_manual_template"),
                    types.InlineKeyboardButton("📋 عرض القوالب", callback_data="show_templates")
                )
                markup.add(
                    types.InlineKeyboardButton("❌ حذف قالب", callback_data="delete_template"),
                    types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="edit_template")
                )
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
                
                bot.send_message(
                    call.message.chat.id,
                    "🗂️ *إدارة القوالب*\n\n"
                    "• استخدم *إنشاء قالب يدوي* لإضافة قالب جديد عن طريق إدخال الوسوم يدوياً\n"
                    "• استخدم *عرض القوالب* لاستعراض القوالب المحفوظة وتطبيقها\n"
                    "• استخدم *حذف قالب* لإزالة قالب موجود\n"
                    "• استخدم *تعديل قالب* لتغيير محتوى قالب موجود",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            elif call.data == 'back_to_tags':
                # Handle back to tags list button
                logger.info(f"User {user_id} wants to go back to tag list")
                
                # تنظيف رسائل القوالب المؤقتة
                cleanup_ui_messages(user_id, call.message.chat.id, bot)
                
                # Check if we have the file
                if user_id not in user_data or 'file_path' not in user_data[user_id]:
                    bot.send_message(call.message.chat.id, "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً.")
                    return
                
                file_path = user_data[user_id]['file_path']
                
                # Get updated tags, applying any temporary changes
                if 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
                    # Combine current file tags with any new edits
                    current_tags = get_audio_tags(file_path)
                    
                    # Apply any new tag edits to the current tags for display
                    for tag, value in user_data[user_id]['new_tags'].items():
                        if tag != 'picture':  # Skip picture tag as it's handled differently
                            current_tags[tag] = value
                    
                    if 'picture' in user_data[user_id]['new_tags']:
                        # Mark that we have updated album art
                        current_tags['has_album_art'] = True
                        current_tags['updated_album_art'] = True
                else:
                    # No changes, just use current file tags
                    current_tags = get_audio_tags(file_path)
                    
                    # Initialize empty tag values dictionary if not exists
                    if 'new_tags' not in user_data[user_id]:
                        user_data[user_id]['new_tags'] = {}
                
                # Mark user as editing
                user_data[user_id]['is_editing'] = True
                logger.info(f"User {user_id} marked as editing. Current data: {user_data[user_id]}")
                
                # Store current tags for reference
                user_data[user_id]['current_tags'] = current_tags
                
                # Create keyboard with tag buttons
                markup = types.InlineKeyboardMarkup(row_width=2)
                tag_fields = get_valid_tag_fields()
                arabic_names = get_tag_field_names_arabic()
                
                # Add a button for each tag
                tag_buttons = []
                for tag in tag_fields:
                    # Skip picture tag as it's handled differently
                    if tag != 'picture':
                        button_text = f"{arabic_names.get(tag, tag)}"
                        tag_buttons.append(types.InlineKeyboardButton(
                            text=button_text,
                            callback_data=f"edit_tag_{tag}"
                        ))
                
                # Add buttons in pairs
                for i in range(0, len(tag_buttons), 2):
                    if i + 1 < len(tag_buttons):
                        markup.row(tag_buttons[i], tag_buttons[i+1])
                    else:
                        markup.row(tag_buttons[i])
                
                # Add picture upload button
                markup.row(types.InlineKeyboardButton(
                    text="إضافة/تغيير صورة الغلاف",
                    callback_data="upload_picture"
                ))
                
                # Add Done, Back and Cancel buttons
                markup.row(
                    types.InlineKeyboardButton(text="تم الانتهاء", callback_data="done_editing"),
                    types.InlineKeyboardButton(text="🔙 رجوع", callback_data="back_from_edit"),
                    types.InlineKeyboardButton(text="إلغاء", callback_data="cancel")
                )
                
                # Format tags for display
                tags_text = "**الوسوم الحالية:**\n"
                
                # Define the order of tags we want to display
                priority_tags = ['title', 'artist', 'album', 'album_artist', 'year', 'genre', 
                                 'composer', 'comment', 'track', 'length']
                
                # Add priority tags
                for tag in priority_tags:
                    if tag != 'picture':
                        arabic_name = arabic_names.get(tag, tag)
                        current_value = current_tags.get(tag, '')
                        if current_value:  # Only add non-empty tags to the text
                            # Truncate long values (like lyrics)
                            if tag == 'lyrics' and len(current_value) > 50:
                                current_value = current_value[:50] + "..."
                            tags_text += f"• {arabic_name}: {current_value}\n"
                        else:
                            # For the specifically requested tags, show them even if empty
                            if tag in ['genre', 'comment', 'track', 'length']:
                                tags_text += f"• {arabic_name}: غير محدد\n"
                                
                # Then add any remaining tags
                for tag in tag_fields:
                    if tag not in priority_tags and tag != 'picture':
                        arabic_name = arabic_names.get(tag, tag)
                        current_value = current_tags.get(tag, '')
                        if current_value:  # Only add non-empty tags to the text
                            # Truncate long values (like lyrics)
                            if tag == 'lyrics' and len(current_value) > 50:
                                current_value = current_value[:50] + "..."
                            tags_text += f"• {arabic_name}: {current_value}\n"
                
                # Check if we have updated album art that needs to be displayed
                has_updated_album_art = current_tags.get('updated_album_art', False)
                has_album_art = current_tags.get('has_album_art', False)
                
                # Set state to waiting for tag selection
                bot.set_state(user_id, BotStates.editing_tags, call.message.chat.id)
                logger.info(f"Set state for user {user_id} to {BotStates.editing_tags.name}")
                
                if has_updated_album_art and 'picture' in user_data[user_id]['new_tags']:
                    # We have a new album art image to display
                    logger.info(f"Displaying updated album art for user {user_id}")
                    
                    # Create temp file for the updated album art
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_img:
                        temp_img.write(user_data[user_id]['new_tags']['picture'])
                        temp_img_path = temp_img.name
                    
                    # Try to delete the existing message
                    try:
                        bot.delete_message(call.message.chat.id, call.message.message_id)
                    except Exception as e:
                        logger.error(f"Error deleting old message: {e}")
                    
                    # Send updated album art with tags
                    with open(temp_img_path, 'rb') as img_file:
                        sent_msg = bot.send_photo(
                            call.message.chat.id,
                            img_file,
                            caption=f"📝 *تعديل الوسوم*\n\n{tags_text}\n\nاختر الوسم الذي تريد تعديله:",
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )
                    
                    # Clean up temporary file
                    try:
                        os.remove(temp_img_path)
                    except Exception as e:
                        logger.error(f"Error removing temporary image: {e}")
                        
                    # Keep track of message ID
                    if 'messages_to_delete' not in user_data[user_id]:
                        user_data[user_id]['messages_to_delete'] = []
                    user_data[user_id]['messages_to_delete'].append(sent_msg.message_id)
                    
                elif has_album_art:
                    # Existing album art from the file
                    try:
                        # Extract album art from the file
                        file_path = user_data[user_id]['file_path']
                        image_data, mime_type = extract_album_art(file_path)
                        
                        if image_data:
                            # Save album art to temporary file
                            art_file_path = os.path.join(TEMP_DIR, f"{user_id}_albumart.jpg")
                            logger.info(f"Saving album art to: {art_file_path}")
                            with open(art_file_path, 'wb') as art_file:
                                art_file.write(image_data)
                            
                            # Try to delete the existing message
                            try:
                                bot.delete_message(call.message.chat.id, call.message.message_id)
                            except Exception as e:
                                logger.error(f"Error deleting old message: {e}")
                            
                            # Send with album art
                            with open(art_file_path, 'rb') as img_file:
                                sent_msg = bot.send_photo(
                                    call.message.chat.id,
                                    img_file,
                                    caption=f"📝 *تعديل الوسوم*\n\n{tags_text}\n\nاختر الوسم الذي تريد تعديله:",
                                    reply_markup=markup,
                                    parse_mode="Markdown"
                                )
                            
                            # Cleanup
                            try:
                                os.remove(art_file_path)
                                logger.info(f"Cleaning up temporary album art file: {art_file_path}")
                            except Exception as e:
                                logger.error(f"Error cleaning up album art: {e}")
                            
                            # Keep track of message ID
                            if 'messages_to_delete' not in user_data[user_id]:
                                user_data[user_id]['messages_to_delete'] = []
                            user_data[user_id]['messages_to_delete'].append(sent_msg.message_id)
                        else:
                            # Can't extract album art, fall back to text mode
                            raise Exception("Failed to extract album art")
                    except Exception as e:
                        # Fall back to text mode
                        logger.error(f"Error displaying album art: {e}, falling back to text mode")
                        
                        # Try to edit the current message instead of creating a new one
                        try:
                            # Check if message has text content before trying to edit
                            if hasattr(call.message, 'text') and call.message.text is not None:
                                bot.edit_message_text(
                                    text=f"📝 *تعديل الوسوم*\n\n{tags_text}\n\nاختر الوسم الذي تريد تعديله:",
                                    chat_id=call.message.chat.id,
                                    message_id=call.message.message_id,
                                    reply_markup=markup,
                                    parse_mode="Markdown"
                                )
                            else:
                                # Message doesn't have text content, send new message
                                raise Exception("Message doesn't have text content to edit")
                        except Exception as inner_e:
                            logger.error(f"Error editing message in fallback: {inner_e}")
                            # Send new message as last resort
                            sent_msg = bot.send_message(
                                call.message.chat.id,
                                f"📝 *تعديل الوسوم*\n\n{tags_text}\n\nاختر الوسم الذي تريد تعديله:",
                                reply_markup=markup,
                                parse_mode="Markdown"
                            )
                            
                            # Keep track of the message ID for deletion later
                            if 'messages_to_delete' not in user_data[user_id]:
                                user_data[user_id]['messages_to_delete'] = []
                            user_data[user_id]['messages_to_delete'].append(sent_msg.message_id)
                else:
                    # No album art, just use text mode
                    try:
                        # Check if message has text content before trying to edit
                        if hasattr(call.message, 'text') and call.message.text is not None:
                            bot.edit_message_text(
                                text=f"📝 *تعديل الوسوم*\n\n{tags_text}\n\nاختر الوسم الذي تريد تعديله:",
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                reply_markup=markup,
                                parse_mode="Markdown"
                            )
                        else:
                            # Message doesn't have text content, send new message
                            raise Exception("Message doesn't have text content to edit")
                    except Exception as e:
                        logger.error(f"Error editing message for back_to_tags: {e}")
                        # If editing fails, send a new message
                        sent_msg = bot.send_message(
                            call.message.chat.id,
                            f"📝 *تعديل الوسوم*\n\n{tags_text}\n\nاختر الوسم الذي تريد تعديله:",
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )
                        
                        # Keep track of the message ID for deletion later
                        if 'messages_to_delete' not in user_data[user_id]:
                            user_data[user_id]['messages_to_delete'] = []
                        user_data[user_id]['messages_to_delete'].append(sent_msg.message_id)
                
            elif call.data == 'clear_errors':
                # Handle clear errors button
                bot_status["errors"] = []
                bot.send_message(
                    call.message.chat.id,
                    "✅ تم مسح سجل الأخطاء بنجاح!"
                )
                # Update status report
                status_command(call.message)
                
            elif call.data == 'restart_bot':
                # Handle restart bot button
                bot.send_message(
                    call.message.chat.id,
                    "⏳ جاري إعادة تشغيل البوت... سيكون متاحاً خلال لحظات."
                )
                # Clear all user data and states
                for u_id in list(user_data.keys()):
                    bot.delete_state(u_id, call.message.chat.id)
                    if u_id in user_data and 'file_path' in user_data[u_id]:
                        try:
                            os.remove(user_data[u_id]['file_path'])
                        except:
                            pass
                user_data.clear()
                
                # Reset statistics
                import datetime
                bot_status["started_time"] = datetime.datetime.now()
                bot_status["processed_files"] = 0
                bot_status["successful_edits"] = 0
                bot_status["failed_operations"] = 0
                bot_status["active_users"] = set()
                bot_status["errors"] = []
                
                # Send confirmation
                bot.send_message(
                    call.message.chat.id,
                    "✅ تم إعادة تشغيل البوت بنجاح!\n"
                    "يمكنك الآن استخدام البوت بشكل طبيعي."
                )
                
        except Exception as e:
            # Log detailed error information
            error_data = log_error(
                "CALLBACK_QUERY_ERROR", 
                str(e), 
                user_id=user_id, 
                function_name="handle_callback_query",
                extra_details={"callback_data": call.data}
            )
            
            # Add error to bot status
            if len(bot_status["errors"]) >= 10:  # Keep only the last 10 errors
                bot_status["errors"].pop(0)
            bot_status["errors"].append(error_data)
            bot_status["failed_operations"] += 1
            
            # Send user friendly error message
            bot.send_message(
                call.message.chat.id, 
                response_messages["invalid_input"] + f"\nنوع الخطأ: {type(e).__name__}"
            )
    
    # Function to handle edit tags request
    def handle_edit_tags(message, user_id):
        """Handle edit tags request."""
        logger.info(f"Processing edit tags request for user {user_id}")
        
        # معالجة مشكلة عدم وجود بيانات المستخدم
        if user_id not in user_data:
            user_data[user_id] = {}
            bot.send_message(message.chat.id, "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً.")
            return
            
        # معالجة مشكلة عدم وجود ملف صوتي
        if 'file_path' not in user_data[user_id]:
            bot.send_message(message.chat.id, "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً.")
            return
        
        file_path = user_data[user_id]['file_path']
        current_tags = get_audio_tags(file_path)
        
        # Initialize empty tag values dictionary if not exists
        if 'new_tags' not in user_data[user_id]:
            user_data[user_id]['new_tags'] = {}
        
        # Mark user as editing
        user_data[user_id]['is_editing'] = True
        logger.info(f"User {user_id} marked as editing. Current data: {user_data[user_id]}")
        
        # Store current tags for reference
        user_data[user_id]['current_tags'] = current_tags
        
        # Create keyboard with tag buttons
        markup = types.InlineKeyboardMarkup(row_width=2)
        tag_fields = get_valid_tag_fields()
        arabic_names = get_tag_field_names_arabic()
        
        # Add a button for each tag
        tag_buttons = []
        for tag in tag_fields:
            # Skip picture tag as it's handled differently
            if tag != 'picture':
                current_value = current_tags.get(tag, '-')
                button_text = f"{arabic_names.get(tag, tag)}"
                tag_buttons.append(types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"edit_tag_{tag}"
                ))
        
        # Add buttons in pairs
        for i in range(0, len(tag_buttons), 2):
            if i + 1 < len(tag_buttons):
                markup.row(tag_buttons[i], tag_buttons[i+1])
            else:
                markup.row(tag_buttons[i])
        
        # Add picture upload button
        markup.row(types.InlineKeyboardButton(
            text="إضافة/تغيير صورة الغلاف",
            callback_data="upload_picture"
        ))

        # Add Done, Back and Cancel buttons
        markup.row(
            types.InlineKeyboardButton(text="تم الانتهاء", callback_data="done_editing"),
            types.InlineKeyboardButton(text="🔙 رجوع", callback_data="back_from_edit"),
            types.InlineKeyboardButton(text="إلغاء", callback_data="cancel")
        )
        
        # Format tags for display - Prioritize showing all important tags
        tags_text = "**الوسوم الحالية:**\n"
        
        # Define the order of tags we want to display (prioritize the requested tags)
        priority_tags = ['title', 'artist', 'album', 'album_artist', 'year', 'genre', 
                         'composer', 'comment', 'track', 'length']
        
        # First add priority tags
        for tag in priority_tags:
            if tag != 'picture':
                arabic_name = arabic_names.get(tag, tag)
                current_value = current_tags.get(tag, '')
                if current_value:  # Only add non-empty tags to the text
                    # Truncate long values (like lyrics)
                    if tag == 'lyrics' and len(current_value) > 50:
                        current_value = current_value[:50] + "..."
                    tags_text += f"• {arabic_name}: {current_value}\n"
                else:
                    # For the specifically requested tags, show them even if empty
                    if tag in ['genre', 'comment', 'track', 'length']:
                        tags_text += f"• {arabic_name}: غير محدد\n"
                        
        # Then add any remaining tags
        for tag in tag_fields:
            if tag not in priority_tags and tag != 'picture':
                arabic_name = arabic_names.get(tag, tag)
                current_value = current_tags.get(tag, '')
                if current_value:  # Only add non-empty tags to the text
                    # Truncate long values (like lyrics)
                    if tag == 'lyrics' and len(current_value) > 50:
                        current_value = current_value[:50] + "..."
                    tags_text += f"• {arabic_name}: {current_value}\n"
        
        # Check if file has album art and send it with tags
        file_path = user_data[user_id]['file_path']
        has_album_art = current_tags.get('has_album_art', False)
        
        if has_album_art:
            # Extract and save album art
            image_data, mime_type = extract_album_art(file_path)
            if image_data:
                # Save album art to temporary file
                album_art_path = f"{TEMP_DIR}/{user_id}_albumart.jpg"
                with open(album_art_path, 'wb') as img_file:
                    img_file.write(image_data)
                logger.info(f"Saving album art to: {album_art_path}")
                
                # Send album art with tag information as caption
                with open(album_art_path, 'rb') as img_file:
                    sent_msg = bot.send_photo(
                        message.chat.id,
                        img_file,
                        caption=f"📝 **تعديل الوسوم**\n\n{tags_text}\n\nاختر الوسم الذي تريد تعديله:",
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    
                    # Store the message ID for later deletion
                    user_data[user_id]['edit_panel_message_id'] = sent_msg.message_id
                
                # Clean up temporary album art file
                try:
                    os.remove(album_art_path)
                    logger.info(f"Cleaning up temporary album art file: {album_art_path}")
                except Exception as e:
                    logger.error(f"Error removing temporary album art file: {e}")
                return
        
        # If no album art, just send the message with tags
        sent_msg = bot.send_message(
            message.chat.id,
            f"📝 **تعديل الوسوم**\n\n{tags_text}\n\nاختر الوسم الذي تريد تعديله:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        # Store the message ID for later deletion
        user_data[user_id]['edit_panel_message_id'] = sent_msg.message_id
        
        # Set state to waiting for tag selection
        bot.set_state(user_id, BotStates.editing_tags, message.chat.id)
        logger.info(f"Set state for user {user_id} to {BotStates.editing_tags.name}")
    
    # تم حذف وظيفة "تنزيل بدون تعديل" بناءً على طلب المستخدم
    
    # Function to handle cancel operation request
    def handle_cancel_operation(message, user_id):
        """Handle cancel operation request."""
        logger.info(f"Processing cancel operation request for user {user_id}")
        
        # Clean up the user data
        if user_id in user_data:
            # Delete any UI messages and control panels
            # Delete messages tracked in messages_to_delete list
            if 'messages_to_delete' in user_data[user_id]:
                try:
                    for msg_id in user_data[user_id]['messages_to_delete']:
                        try:
                            bot.delete_message(message.chat.id, msg_id)
                            logger.debug(f"Deleted UI message ID: {msg_id}")
                        except Exception as e:
                            logger.error(f"Failed to delete message {msg_id}: {e}")
                except Exception as e:
                    logger.error(f"Error during cleanup of UI messages: {e}")
            
            # Also try to delete the main tag editing panel message if we have its ID
            if 'edit_panel_message_id' in user_data[user_id]:
                try:
                    bot.delete_message(message.chat.id, user_data[user_id]['edit_panel_message_id'])
                    logger.debug(f"Deleted main edit panel message")
                except Exception as e:
                    logger.error(f"Failed to delete edit panel message: {e}")
            
            # Remove the temporary file if it exists
            if 'file_path' in user_data[user_id]:
                try:
                    os.remove(user_data[user_id]['file_path'])
                    logger.info(f"Removed temporary file: {user_data[user_id]['file_path']}")
                except Exception as e:
                    logger.error(f"Error removing temporary file: {e}")
            
            # Delete the user data
            user_data.pop(user_id, None)
        
        # Reset the state
        bot.send_message(message.chat.id, "تم إلغاء العملية. يمكنك إرسال ملف صوتي آخر في أي وقت.")
        bot.delete_state(user_id, message.chat.id)
    
    # Handler for receiving photos - can handle photos in any state
    @bot.message_handler(content_types=['photo'])
    def receive_photo_for_tag(message):
        """Handle receiving a photo for album art."""
        user_id = message.from_user.id
        logger.info(f"Received photo from user {user_id}")
        
        # Check if we have the file
        if user_id not in user_data or 'file_path' not in user_data[user_id]:
            bot.send_message(message.chat.id, "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً.")
            bot.delete_state(user_id, message.chat.id)
            return
            
        logger.info(f"Received photo for album art from user {user_id}")
        
        # First send acknowledgment so user knows we're processing
        processing_msg = bot.send_message(
            message.chat.id,
            "جاري معالجة صورة الألبوم... ⏳"
        )
        
        try:
            # Get the largest photo (best quality)
            file_id = message.photo[-1].file_id
            
            # Download the photo
            file_info = bot.get_file(file_id)
            if not file_info.file_path:  
                raise Exception("تعذر الحصول على مسار الملف من تليجرام")
                
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Save the photo to user data for later use
            if 'new_tags' not in user_data[user_id]:
                user_data[user_id]['new_tags'] = {}
            
            # Save the image data
            user_data[user_id]['new_tags']['picture'] = downloaded_file
            
            logger.info(f"Successfully downloaded album art for user {user_id}, size: {len(downloaded_file)} bytes")
            
            # Create a keyboard with back button
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text="العودة لقائمة الوسوم", callback_data="back_to_tags"))
            
            # Try to delete the processing message
            try:
                bot.delete_message(message.chat.id, processing_msg.message_id)
            except Exception as e:
                logger.error(f"Error deleting processing message: {e}")
            
            # Send confirmation with the image preview
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_img:
                temp_img.write(downloaded_file)
                temp_img_path = temp_img.name
            
            with open(temp_img_path, 'rb') as img_file:
                success_msg = bot.send_photo(
                    message.chat.id,
                    img_file,
                    caption="✅ تم تحميل صورة الألبوم بنجاح! سيتم إضافتها للملف الصوتي عند الحفظ.",
                    reply_markup=markup
                )
            
            # Clean up the temp file
            try:
                os.remove(temp_img_path)
            except Exception as e:
                logger.error(f"Error removing temporary image preview: {e}")
                
            # Store message ID for cleanup later
            if 'messages_to_delete' not in user_data[user_id]:
                user_data[user_id]['messages_to_delete'] = []
            user_data[user_id]['messages_to_delete'].append(success_msg.message_id)
            
        except Exception as e:
            logger.error(f"Error downloading photo: {e}")
            bot.send_message(
                message.chat.id,
                f"حدث خطأ في تنزيل الصورة: {str(e)}. الرجاء المحاولة مرة أخرى."
            )
    
    # Handler for done command in tag editing state
    @bot.message_handler(commands=['done'], state=BotStates.waiting_for_tag_values)
    def handle_done_command(message):
        """Handle the done command to finalize tag editing."""
        user_id = message.from_user.id
        logger.info(f"Received explicit /done command from user {user_id}")
        
        if user_id not in user_data or 'file_path' not in user_data[user_id]:
            logger.error(f"User {user_id} data not found when processing /done command")
            bot.send_message(message.chat.id, "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً.")
            bot.delete_state(user_id, message.chat.id)
            return
            
        if not user_data[user_id].get('new_tags'):
            logger.info(f"No tags added by user {user_id}, sending message to add tags")
            bot.send_message(message.chat.id, "لم تقم بإضافة أي وسوم للتعديل. الرجاء إضافة وسوم أو إلغاء العملية باستخدام /cancel.")
            return
        
        logger.info(f"User {user_id} has added tags via /done command. Calling save_tags function.")
        save_tags(message, bot)
        
    # Handler for tag value input
    @bot.message_handler(state=BotStates.waiting_for_tag_values)
    def receive_tag_values(message):
        """Receive and process tag values from the user."""
        user_id = message.from_user.id
        
        # Check if we have the file
        if user_id not in user_data or 'file_path' not in user_data[user_id]:
            bot.send_message(message.chat.id, "لم يتم العثور على ملف صوتي. الرجاء إرسال ملف صوتي أولاً.")
            bot.delete_state(user_id, message.chat.id)
            return
        
        # Check for done command - this section will likely be handled by @bot.message_handler(commands=['done'])
        # But we'll keep it as a fallback
        if message.text == '/done':
            logger.info(f"Received /done text command from user {user_id} in receive_tag_values function")
            # Make sure to mark user as editing
            user_data[user_id]['is_editing'] = True
            
            if not user_data[user_id].get('new_tags'):
                logger.info(f"No tags added by user {user_id}, sending message to add tags")
                bot.send_message(message.chat.id, "لم تقم بإضافة أي وسوم للتعديل. الرجاء إضافة وسوم أو إلغاء العملية باستخدام /cancel.")
                return
            
            logger.info(f"User {user_id} has added tags: {user_data[user_id].get('new_tags')}. Calling save_tags function.")
            save_tags(message, bot)
            return
        
        # Check for cancel command
        if message.text == '/cancel':
            bot.send_message(message.chat.id, "تم إلغاء تعديل الوسوم.")
            bot.delete_state(user_id, message.chat.id)
            handle_cancel_operation(message, user_id)
            return
        
        # Process tag input
        try:
            tag_line = message.text.strip()
            if ':' not in tag_line:
                bot.send_message(
                    message.chat.id,
                    "الصيغة غير صحيحة. الرجاء استخدام الصيغة 'اسم_الوسم: القيمة'."
                )
                return
            
            tag_name, tag_value = tag_line.split(':', 1)
            tag_name = tag_name.strip()
            tag_value = tag_value.strip()
            
            valid_fields = get_valid_tag_fields()
            if tag_name not in valid_fields:
                bot.send_message(
                    message.chat.id,
                    f"اسم الوسم '{tag_name}' غير صالح. الوسوم الصالحة هي: {', '.join(valid_fields)}."
                )
                return
            
            user_data[user_id]['new_tags'][tag_name] = tag_value
            bot.send_message(
                message.chat.id,
                f"تم إضافة الوسم '{tag_name}: {tag_value}'. أرسل وسومًا أخرى أو /done للانتهاء أو /cancel للإلغاء."
            )
            
        except Exception as e:
            logger.error(f"Error processing tag input: {e}")
            bot.send_message(
                message.chat.id,
                f"حدث خطأ في معالجة المدخلات: {str(e)}.\n"
                "الرجاء المحاولة مرة أخرى أو إلغاء العملية باستخدام /cancel."
            )
    
    # Helper function to delete messages
    def delete_messages(chat_id, message_ids, bot):
        """Delete multiple messages by ID."""
        for msg_id in message_ids:
            try:
                bot.delete_message(chat_id, msg_id)
                logger.debug(f"Deleted message {msg_id} in chat {chat_id}")
            except Exception as e:
                logger.error(f"Error deleting message {msg_id}: {e}")
    
    # Helper function to clean up temporary UI messages
    def cleanup_ui_messages(user_id, chat_id, bot):
        """تنظيف الرسائل المؤقتة للواجهة مثل رسائل قوائم القوالب"""
        if user_id in user_data and 'ui_message_ids' in user_data[user_id]:
            message_ids = user_data[user_id]['ui_message_ids']
            # حذف الرسائل المؤقتة
            for msg_id in message_ids:
                try:
                    bot.delete_message(chat_id, msg_id)
                    logger.debug(f"Cleaned up temporary UI message {msg_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up message {msg_id}: {e}")
            # إعادة تعيين قائمة الرسائل المؤقتة
            user_data[user_id]['ui_message_ids'] = []
            logger.info(f"Cleaned up all UI messages for user {user_id}")
    
    # Function to save tags and send the modified file back
    def save_tags(message, bot, override_user_id=None):
        """Save the tags to the audio file.
        
        Args:
            message: Message object containing chat info
            bot: Telebot instance
            override_user_id: Optional user ID to use instead of extracting from message
        """
        # Get user ID from message object
        # We handle different scenarios:
        # 1. If override_user_id is provided, use it directly
        # 2. If _direct_user_id custom property exists, use it
        # 3. Try message.from_user.id if it exists
        # 4. Fallback to chat_id if nothing else works
        
        chat_id = message.chat.id  # This should always exist
        
        # First priority: use override_user_id if provided
        if override_user_id is not None:
            user_id = override_user_id
            logger.info(f"Using explicit override user_id={user_id}")
        # Second: check for our custom property
        elif hasattr(message, '_direct_user_id'):
            user_id = message._direct_user_id
            logger.info(f"Using direct user_id={user_id} from custom property")
        # Third: try regular message from_user
        elif hasattr(message, 'from_user') and message.from_user is not None:
            user_id = message.from_user.id
            logger.info(f"Using from_user.id={user_id} from direct message")
        # Last resort: use chat_id
        else:
            user_id = chat_id
            logger.info(f"Falling back to chat_id={user_id}")
        
        logger.info(f"In save_tags: chat_id = {chat_id}, resolved user_id = {user_id}")
            
        logger.info(f"Starting save_tags function for user {user_id}")
        
        try:
            if user_id not in user_data:
                logger.error(f"User {user_id} not found in user_data")
                bot.send_message(message.chat.id, "حدث خطأ: البيانات غير متوفرة. الرجاء إعادة إرسال الملف الصوتي.")
                bot.delete_state(user_id, message.chat.id)
                return
                
            if 'file_path' not in user_data[user_id]:
                logger.error(f"file_path not found in user_data for user {user_id}")
                bot.send_message(message.chat.id, "حدث خطأ: مسار الملف غير متوفر. الرجاء إعادة إرسال الملف الصوتي.")
                bot.delete_state(user_id, message.chat.id)
                return
                
            file_path = user_data[user_id]['file_path']
            
            # تحديد الوسوم المُحدَّثة، بناءً على نوع التعديل (مباشر أو تطبيق قالب)
            if 'temp_tags' in user_data[user_id] and user_data[user_id]['temp_tags']:
                # إذا كان قد تم تطبيق قالب، استخدم الوسوم المؤقتة
                new_tags = user_data[user_id]['temp_tags']
                logger.info(f"Using temp_tags (from template) for saving: {new_tags}")
            elif 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
                # إذا كان المستخدم قد قام بتعديل وسوم محددة، استخدم هذه الوسوم
                new_tags = user_data[user_id]['new_tags']
                logger.info(f"Using new_tags (from direct edits) for saving: {new_tags}")
            else:
                logger.error(f"No tags found to save for user {user_id}")
                bot.send_message(message.chat.id, "لم يتم العثور على وسوم للحفظ. الرجاء تعديل الوسوم أولاً.")
                return
                
            logger.info(f"File path: {file_path}, Tags to save: {new_tags}")
            original_file_name = user_data[user_id]['original_file_name']
            
            bot.send_message(message.chat.id, "جاري حفظ الوسوم الجديدة...")
            
            # Create a copy of the file for modification
            original_file_path = file_path
            file_ext = os.path.splitext(file_path)[1]
            modified_file_path = os.path.join(os.path.dirname(file_path), f"modified_{user_id}{file_ext}")
            
            # Make a copy of the original file
            try:
                shutil.copy2(original_file_path, modified_file_path)
                logger.info(f"Created a copy of the original file at: {modified_file_path}")
            except Exception as e:
                logger.error(f"Error creating copy of original file: {e}")
                bot.send_message(message.chat.id, f"حدث خطأ أثناء إنشاء نسخة من الملف: {str(e)}")
                bot.delete_state(user_id, message.chat.id)
                return
            
            # Save tags to the modified file
            logger.info(f"Attempting to save tags to file: {modified_file_path}")
            try:
                # تسجيل الوسوم الجديدة لفحصها
                logger.info(f"New tags for saving: {new_tags}")
                
                # قراءة الوسوم الحالية من الملف الأصلي
                current_tags = get_audio_tags(file_path)
                logger.info(f"Current tags from file: {current_tags}")
                
                # دمج الوسوم الحالية مع الجديدة
                merged_tags = {**current_tags}
                for key, value in new_tags.items():
                    merged_tags[key] = value
                    
                # تطبيق القواعد الذكية على الوسوم المدمجة
                try:
                    with app.app_context():
                        modified_tags, applied_rules = smart_rules.apply_smart_rules(merged_tags)
                        if applied_rules:
                            merged_tags = modified_tags
                            logger.info(f"Applied smart rules to tags: {applied_rules}")
                            # إشعار المستخدم بالقواعد المطبقة
                            bot.send_message(
                                message.chat.id,
                                f"✨ تم تطبيق القواعد الذكية التالية تلقائياً:\n• " + "\n• ".join(applied_rules)
                            )
                except Exception as e:
                    logger.error(f"خطأ في تطبيق القواعد الذكية: {e}")
                
                # معالجة خاصة لكلمات الأغنية
                if 'lyrics' in new_tags and new_tags['lyrics']:
                    logger.info(f"Special handling for lyrics from new_tags, length: {len(new_tags['lyrics'])}")
                    # تأكد من تنسيق الكلمات بشكل صحيح
                    lyrics = new_tags['lyrics']
                    # تنظيف أي تنسيق خاص قد يتسبب في مشاكل
                    lyrics = lyrics.replace('\r\n', '\n').replace('\r', '\n')
                    # تحويل نهايات الأسطر إلى \r\n للتوافق مع معظم المشغلات
                    lyrics = lyrics.replace('\n', '\r\n')
                    merged_tags['lyrics'] = lyrics
                    
                    # سجل السطر الأول من كلمات الأغنية للتحقق
                    first_line = lyrics.split("\r\n")[0] if "\r\n" in lyrics else lyrics
                    logger.info(f"Saving lyrics, total length: {len(lyrics)}, first line: {first_line}")
                # التحقق من وجود نسخة كاملة من الكلمات مخزنة في user_data
                elif 'full_lyrics' in user_data[user_id] and user_data[user_id]['full_lyrics']:
                    logger.info(f"Found full lyrics in user_data, length: {len(user_data[user_id]['full_lyrics'])}")
                    # تنسيق الكلمات
                    lyrics = user_data[user_id]['full_lyrics']
                    # تنظيف أي تنسيق خاص قد يتسبب في مشاكل
                    lyrics = lyrics.replace('\r\n', '\n').replace('\r', '\n')
                    # تحويل نهايات الأسطر إلى \r\n للتوافق مع معظم المشغلات
                    lyrics = lyrics.replace('\n', '\r\n')
                    merged_tags['lyrics'] = lyrics
                    # إضافة الكلمات أيضًا إلى new_tags لإرشاد المكتبة
                    new_tags['lyrics'] = lyrics
                    
                    # سجل السطر الأول من كلمات الأغنية للتحقق
                    first_line = lyrics.split("\r\n")[0] if "\r\n" in lyrics else lyrics
                    logger.info(f"Saving full lyrics from user_data, total length: {len(lyrics)}, first line: {first_line}")
                
                logger.info(f"Merged tags after special handling: {merged_tags}")
                
                # حفظ الوسوم المدمجة في الملف المعدل
                set_audio_tags(modified_file_path, merged_tags)
                
                # التحقق من أن الوسوم تم حفظها بنجاح باستخراجها من الملف
                saved_tags = get_audio_tags(modified_file_path)
                logger.info(f"Verification - saved tags: {saved_tags}")
                
                # التحقق تحديدًا من الكلمات
                if 'lyrics' in saved_tags:
                    logger.info(f"Saved lyrics length: {len(saved_tags['lyrics'])}, Sample: {saved_tags['lyrics'][:100]}")
                
                logger.info(f"Tags saved successfully to file: {modified_file_path}")
                
                bot.send_message(message.chat.id, "تم حفظ الوسوم بنجاح. جاري إرسال الملف المعدل...")
                
                # Send the modified file back with optimized settings for Telegram
                logger.info(f"Attempting to send modified file back to user {user_id}")
                with open(modified_file_path, 'rb') as audio_file:
                    logger.info(f"Modified file opened successfully: {modified_file_path}")
                    # Send audio file with specific parameters to maximize Telegram thumbnail compatibility
                    # First, check if we have an album art thumbnail we can use directly
                    album_art_path = None
                    try:
                        # استخراج صورة الألبوم وتحسينها للعرض في تيليجرام
                        # هذا يساعد تيليجرام على التعرف عليها بشكل أفضل ويحسن من العرض المصغر
                        img_data = None
                        mime = None
                        
                        # محاولة استخراج الصورة من الملف المعدل
                        try:
                            img_data, mime = extract_album_art(modified_file_path)
                            if img_data:
                                logger.info(f"Extracted album art from modified file, size: {len(img_data)} bytes")
                            else:
                                logger.info("No album art found in modified file")
                                
                                # إذا لم نتمكن من استخراج الصورة، نحاول استخدام الصورة من الوسوم الجديدة
                                if 'picture' in new_tags and new_tags['picture']:
                                    img_data = new_tags['picture']
                                    logger.info(f"Using picture from new_tags, size: {len(img_data)} bytes")
                            
                            # إذا حصلنا على بيانات الصورة، نقوم بمعالجتها
                            if img_data:
                                # استخدام PIL لمعالجة الصورة
                                from PIL import Image
                                import io
                                
                                # تحويل الصورة إلى كائن Image
                                img_io = io.BytesIO(img_data)
                                img = Image.open(img_io)
                                
                                # حفظ الصورة الأصلية ذات الدقة العالية للملف النهائي
                                album_art_high_res = os.path.join('temp_audio_files', f"{user_id}_high_res_albumart.jpg")
                                img.save(album_art_high_res, format='JPEG', quality=95)
                                logger.info(f"Saved high-quality album art to: {album_art_high_res}")
                                
                                # إنشاء نسخة مصغرة (90x90) لعرضها كصورة مصغرة في تيليجرام
                                thumb_size = (90, 90)
                                thumb_img = img.copy()
                                thumb_img.thumbnail(thumb_size)
                                
                                # حفظ الصورة المصغرة
                                album_art_path = os.path.join('temp_audio_files', f"{user_id}_thumbnail.jpg")
                                thumb_img.save(album_art_path, format='JPEG', quality=95)
                                logger.info(f"Saved thumbnail version to: {album_art_path}")
                                
                                # حفظ نسخة متوسطة ذات حجم مناسب لتيليجرام (320x320)
                                medium_size = (320, 320)
                                medium_img = img.copy()
                                medium_img.thumbnail(medium_size)
                                
                                # حفظ النسخة المتوسطة كنسخة احتياطية
                                medium_path = os.path.join('temp_audio_files', f"{user_id}_medium_albumart.jpg")
                                medium_img.save(medium_path, format='JPEG', quality=95)
                                logger.info(f"Saved medium-size album art to: {medium_path}")
                        except Exception as e:
                            logger.error(f"Error processing album art: {e}")
                            
                            # في حالة فشل معالجة الصورة، نستخدم الطريقة التقليدية
                            if img_data:
                                album_art_path = os.path.join('temp_audio_files', f"{user_id}_final_albumart.jpg")
                                with open(album_art_path, 'wb') as img_file:
                                    img_file.write(img_data)
                                logger.info(f"Fallback: Saved album art directly to: {album_art_path}")
                    except Exception as e:
                        logger.error(f"Error preparing thumbnail: {e}")
                    
                    # الحد الأقصى للوصف في تيليجرام هو 1024 حرف - لذلك نختصر اسم الملف إذا كان طويلاً
                    # Create a safe caption that won't exceed Telegram's limit
                    short_filename = original_file_name
                    if len(short_filename) > 30:  # تقصير اسم الملف إذا كان طويلاً
                        short_filename = original_file_name[:27] + "..."
                    safe_caption = f"ملف صوتي معدل: {short_filename}"
                    
                    # استخراج جميع الوسوم الحالية من الملف المعدل لضمان استخدام الوسوم النهائية بعد الدمج
                    final_tags = get_audio_tags(modified_file_path)
                    logger.info(f"Retrieved final tags for sending: {final_tags}")
                    
                    # تحديث معلومات performer و title للتأكد من ظهورها بشكل صحيح في تيليجرام
                    performer = final_tags.get('artist', '')
                    title = final_tags.get('title', '')
                    album = final_tags.get('album', '')
                        
                    # إذا كانت فارغة، استخدم اسم الملف الأصلي
                    if not performer:
                        performer = "غير محدد"
                    if not title:
                        title = original_file_name
                    
                    # إضافة معلومات الألبوم للوصف إذا كانت متوفرة
                    if album and album != "غير محدد":
                        safe_caption = f"ملف صوتي معدل: {short_filename}\nالألبوم: {album}"
                    
                    logger.info(f"Sending final file with performer={performer}, title={title}")
                    
                    # استخدام الصورة المصغرة المحسنة إذا كانت متوفرة
                    if album_art_path and os.path.exists(album_art_path):
                        logger.info(f"Using optimized thumbnail for upload: {album_art_path}")
                        
                        with open(album_art_path, 'rb') as thumb_file:
                            try:
                                # إرسال الملف الصوتي مع الصورة المصغرة المحسنة
                                sent_audio = bot.send_audio(
                                    message.chat.id,
                                    audio_file,
                                    caption=safe_caption,
                                    performer=performer,
                                    title=title,
                                    thumb=thumb_file
                                )
                                logger.info(f"File sent successfully with thumbnail")
                            except Exception as e:
                                logger.error(f"Error sending audio with custom thumbnail: {e}")
                                # محاولة الإرسال بدون الصورة المصغرة المخصصة في حالة فشل الإرسال
                                bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء إرفاق الصورة المصغرة، جاري إعادة المحاولة...")
                                bot.send_audio(
                                    message.chat.id,
                                    audio_file,
                                    caption=safe_caption,
                                    performer=performer,
                                    title=title
                                )
                        
                        # تنظيف الملفات المؤقتة للصور
                        try:
                            # حذف الصورة المصغرة
                            os.remove(album_art_path)
                            logger.info(f"Removed temporary thumbnail: {album_art_path}")
                            
                            # تحقق من وجود الملفات الأخرى وحذفها
                            medium_path = os.path.join('temp_audio_files', f"{user_id}_medium_albumart.jpg")
                            high_res_path = os.path.join('temp_audio_files', f"{user_id}_high_res_albumart.jpg")
                            
                            if os.path.exists(medium_path):
                                os.remove(medium_path)
                                logger.info(f"Removed medium resolution art: {medium_path}")
                                
                            if os.path.exists(high_res_path):
                                os.remove(high_res_path)
                                logger.info(f"Removed high resolution art: {high_res_path}")
                        except Exception as e:
                            logger.error(f"Error cleaning up temporary files: {e}")
                    else:
                        # استخدام الصورة المدمجة في الملف (يستخرجها تيليجرام تلقائيًا)
                        logger.info("No custom thumbnail available, letting Telegram extract thumbnail automatically")
                        
                        try:
                            bot.send_audio(
                                message.chat.id,
                                audio_file,
                                caption=safe_caption,
                                performer=performer,
                                title=title
                            )
                        except Exception as e:
                            logger.error(f"Error sending audio: {e}")
                            # إبلاغ المستخدم بالخطأ
                            bot.send_message(
                                message.chat.id,
                                f"⚠️ حدث خطأ أثناء إرسال الملف: {str(e)}"
                            )
                    logger.info(f"Modified file sent successfully to user {user_id}")
            except Exception as e:
                logger.error(f"Error processing or sending modified file: {e}")
                bot.send_message(message.chat.id, f"حدث خطأ أثناء معالجة أو إرسال الملف المعدل: {str(e)}")
            
            # Clean up both files
            try:
                # Original temp file
                if os.path.exists(original_file_path):
                    os.remove(original_file_path)
                    logger.info(f"Removed original temporary file: {original_file_path}")
                
                # Modified temp file
                if os.path.exists(modified_file_path):
                    os.remove(modified_file_path)
                    logger.info(f"Removed modified temporary file: {modified_file_path}")
            except Exception as e:
                logger.error(f"Error removing temporary files: {e}")
            
            # Delete any previous UI messages (buttons and controls)
            # First try to find any edit panels or message IDs we've stored
            if 'messages_to_delete' in user_data[user_id]:
                try:
                    for msg_id in user_data[user_id]['messages_to_delete']:
                        try:
                            bot.delete_message(message.chat.id, msg_id)
                            logger.debug(f"Deleted UI message ID: {msg_id}")
                        except Exception as e:
                            logger.error(f"Failed to delete message {msg_id}: {e}")
                except Exception as e:
                    logger.error(f"Error during cleanup of UI messages: {e}")
            
            # Also try to delete the main tag editing panel message if we have its ID
            if 'edit_panel_message_id' in user_data[user_id]:
                try:
                    bot.delete_message(message.chat.id, user_data[user_id]['edit_panel_message_id'])
                    logger.debug(f"Deleted main edit panel message")
                except Exception as e:
                    logger.error(f"Failed to delete edit panel message: {e}")
            
            # Clean up user data
            user_data.pop(user_id, None)
            bot.delete_state(user_id, message.chat.id)
            
            # Send final message
            bot.send_message(message.chat.id, "✅ تم حفظ الوسوم وإرسال الملف بنجاح!\n\nيمكنك إرسال ملف صوتي آخر في أي وقت.")
            
        except Exception as e:
            logger.error(f"Error saving tags: {e}")
            bot.send_message(
                message.chat.id,
                f"حدث خطأ في حفظ الوسوم: {str(e)}.\n"
                "الرجاء المحاولة مرة أخرى."
            )
            bot.delete_state(user_id, message.chat.id)
    
    # Handler for specific tag input
    @bot.message_handler(state=BotStates.waiting_for_specific_tag)
    def receive_specific_tag_value(message):
        """Handle receiving a value for a specific tag."""
        user_id = message.from_user.id
        logger.info(f"Received specific tag value from user {user_id}: {message.text}")
        
        # First, send acknowledgment to show we received the message
        ack_msg = bot.send_message(
            message.chat.id,
            "📨 تم استلام القيمة الجديدة. جاري المعالجة..."
        )
        
        # Try to delete the user's message to keep the chat clean
        try:
            bot.delete_message(message.chat.id, message.message_id)
            logger.debug(f"Deleted user message with value for tag")
        except Exception as e:
            logger.error(f"Error deleting user message: {e}")
        
        try:
            # Check if we have the file and editing tag information
            if (user_id not in user_data or 
                'file_path' not in user_data[user_id] or 
                'editing_tag' not in user_data[user_id]):
                
                error_data = log_error(
                    "MISSING_USER_DATA", 
                    "User data is missing required fields", 
                    user_id=user_id, 
                    function_name="receive_specific_tag_value",
                    extra_details={"user_data": user_data.get(user_id, {})}
                )
                
                bot.send_message(message.chat.id, "حدث خطأ. الرجاء إعادة تعديل الوسوم من البداية.")
                bot.delete_state(user_id, message.chat.id)
                return
            
            tag_name = user_data[user_id]['editing_tag']
            arabic_name = get_tag_field_names_arabic().get(tag_name, tag_name)
            
            # Skip if no text is provided
            if not message.text:
                bot.send_message(message.chat.id, "الرجاء إدخال قيمة نصية للوسم.")
                return
                
            # Save the new tag value
            if 'new_tags' not in user_data[user_id]:
                user_data[user_id]['new_tags'] = {}
                
            # معالجة خاصة لحقل الكلمات للتأكد من حفظه بشكل صحيح
            if tag_name == 'lyrics':
                logger.info(f"Special handling for lyrics tag, length: {len(message.text.strip())}")
                # تأكد من حفظ كامل النص وعدم اقتطاعه
                lyrics_text = message.text.strip()
                
                # تنظيف أي تنسيق خاص قد يتسبب في مشاكل
                lyrics_text = lyrics_text.replace('\r\n', '\n').replace('\r', '\n')
                # تحويل علامات السطر الجديد إلى \r\n للتوافق مع معظم مشغلات الصوت
                lyrics_text = lyrics_text.replace('\n', '\r\n')
                
                # حفظ الكلمات الكاملة في حالتين: في new_tags للتطبيق الفوري وفي full_lyrics كنسخة احتياطية
                user_data[user_id]['new_tags'][tag_name] = lyrics_text
                user_data[user_id]['full_lyrics'] = lyrics_text
                
                # سجل السطر الأول من كلمات الأغنية للتحقق
                first_line = lyrics_text.split("\r\n")[0] if "\r\n" in lyrics_text else lyrics_text
                logger.info(f"Received lyrics from user, total length: {len(lyrics_text)}, first line: {first_line}")
            else:
                user_data[user_id]['new_tags'][tag_name] = message.text.strip()
            
            logger.info(f"Saved value '{message.text.strip()}' for tag '{tag_name}' for user {user_id}")
            
            # Update the main tag editing panel with the new values
            try:
                # احصل على الوسوم الحالية من الملف
                file_path = user_data[user_id]['file_path']
                current_tags = get_audio_tags(file_path)
                
                # إنشاء نسخة للعرض تحتوي على الوسوم المعدلة
                if 'new_tags' not in user_data[user_id]:
                    user_data[user_id]['new_tags'] = {}
                    
                # دمج الوسوم الحالية مع التعديلات التي قام بها المستخدم
                preview_tags = {**current_tags}
                
                # تطبيق التعديلات التي قام بها المستخدم
                for tag, value in user_data[user_id]['new_tags'].items():
                    preview_tags[tag] = value
                    
                logger.info(f"Preview tags for UI update: {preview_tags}")
                
                # Format the display text with special highlighting for modified tags
                tag_fields = get_valid_tag_fields()
                arabic_names = get_tag_field_names_arabic()
                # Fix: Use regular markdown syntax instead of bold in preview text
                preview_text = "📝 *تعديل الوسوم*\n\n*الوسوم الحالية:*\n"
                
                # تحديد طول النص بحد أقصى لتجنب خطأ "message caption is too long"
                max_caption_length = 900  # أقل من الحد الأقصى 1024 بهامش أمان
                current_length = len(preview_text)
                
                for tag in tag_fields:
                    # تخطي حقل picture وأيضًا حقل lyrics لتجنب الوصف الطويل
                    if tag != 'picture' and tag != 'lyrics':  
                        tag_arabic = arabic_names.get(tag, tag)
                        tag_value = preview_tags.get(tag, 'غير محدد')
                        
                        # تقصير القيم الطويلة
                        if isinstance(tag_value, str) and len(tag_value) > 50:
                            tag_value = tag_value[:47] + "..."
                            
                        # إنشاء سطر جديد وفحص الطول الإجمالي
                        new_line = ""
                        if tag in user_data[user_id]['new_tags']:
                            new_line = f"• {tag_arabic}: {tag_value} 🔄\n"
                        else:
                            new_line = f"• {tag_arabic}: {tag_value}\n"
                            
                        # التحقق من أن إضافة هذا السطر لن تجعل النص طويلًا جدًا
                        if current_length + len(new_line) < max_caption_length:
                            preview_text += new_line
                            current_length += len(new_line)
                        else:
                            preview_text += "...\n"
                            break
                
                # إضافة ملاحظة حول كلمات الأغنية إذا كانت موجودة
                if 'lyrics' in preview_tags and preview_tags['lyrics'] and current_length + 60 < max_caption_length:
                    preview_text += "\n_(كلمات الأغنية متاحة عند النقر على زر 'كلمات الأغنية')_\n"
                
                # Create the same keyboard for editing
                markup = types.InlineKeyboardMarkup(row_width=2)
                
                # Add tag buttons in pairs
                tag_buttons = []
                for tag in tag_fields:
                    if tag != 'picture':
                        tag_buttons.append(types.InlineKeyboardButton(
                            text=arabic_names.get(tag, tag),
                            callback_data=f"edit_tag_{tag}"
                        ))
                
                for i in range(0, len(tag_buttons), 2):
                    if i + 1 < len(tag_buttons):
                        markup.add(tag_buttons[i], tag_buttons[i + 1])
                    else:
                        markup.add(tag_buttons[i])
                
                # Add picture upload button
                markup.add(types.InlineKeyboardButton(
                    text="إضافة/تغيير صورة الغلاف",
                    callback_data="upload_picture"
                ))
                
                # Add done and cancel buttons
                markup.add(
                    types.InlineKeyboardButton(text="تم الانتهاء", callback_data="done_editing"),
                    types.InlineKeyboardButton(text="إلغاء", callback_data="cancel")
                )
                
                # Update the editing panel
                if 'edit_panel_message_id' in user_data[user_id]:
                    try:
                        # Try to edit the existing message
                        bot.edit_message_text(
                            preview_text,
                            chat_id=message.chat.id,
                            message_id=user_data[user_id]['edit_panel_message_id'],
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )
                        logger.info(f"Updated tag panel with new value for {tag_name}")
                    except Exception as e:
                        # If editing fails, send a new message
                        logger.error(f"Error editing message: {e}")
                        sent_msg = bot.send_message(
                            message.chat.id,
                            preview_text,
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )
                        # Update the reference to the new message
                        user_data[user_id]['edit_panel_message_id'] = sent_msg.message_id
                        logger.info(f"Created new tag panel instead of updating")
                else:
                    # No previous panel exists, create a new one
                    sent_msg = bot.send_message(
                        message.chat.id,
                        preview_text,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    user_data[user_id]['edit_panel_message_id'] = sent_msg.message_id
                    logger.info(f"Created new tag panel because no previous panel existed")
            except Exception as e:
                logger.error(f"Error updating tag panel: {e}")
            
            # التحقق من إذا كان هناك تحديث للكلمات
            if tag_name == 'lyrics':
                # يتم تحديث قيمة الكلمات في user_data مباشرة لضمان تحديثها في واجهة المستخدم
                # وأيضاً عند الحفظ النهائي
                # قم بتخزين نسخة من الكلمات الجديدة في قسم منفصل لضمان استخدامها عند الحفظ
                if 'full_lyrics' not in user_data[user_id]:
                    user_data[user_id]['full_lyrics'] = {}
                    
                user_data[user_id]['full_lyrics'] = message.text.strip()
                logger.info(f"Stored full lyrics of length {len(message.text.strip())} for future saving")
                
                # عرض رسالة خاصة للمستخدم
                bot.send_message(
                    message.chat.id,
                    "✅ تم حفظ الكلمات بنجاح في الذاكرة. سيتم تطبيقها عند حفظ التغييرات."
                )
            
            # Update status counters
            bot_status["processed_files"] += 1
            
            # Create a keyboard with buttons for the confirmation message
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("تعديل وسم آخر", callback_data="back_to_tags"),
                types.InlineKeyboardButton("حفظ وإنهاء", callback_data="done_editing")
            )
            
            # Try to delete the acknowledgment message
            try:
                bot.delete_message(message.chat.id, ack_msg.message_id)
            except Exception as e:
                logger.error(f"Error deleting acknowledgment message: {e}")
            
            # Check if we have a current edit message ID to update
            if 'current_edit_message_id' in user_data[user_id]:
                try:
                    # Try to edit the existing message
                    bot.edit_message_text(
                        text=f"✅ تم حفظ '{arabic_name}' بقيمة: `{message.text.strip()}`\n\n"
                             f"ماذا تريد أن تفعل الآن؟",
                        chat_id=message.chat.id,
                        message_id=user_data[user_id]['current_edit_message_id'],
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    # Store this message ID
                    if 'messages_to_delete' not in user_data[user_id]:
                        user_data[user_id]['messages_to_delete'] = []
                    user_data[user_id]['messages_to_delete'].append(user_data[user_id]['current_edit_message_id'])
                    return
                except Exception as e:
                    logger.error(f"Error editing message after saving tag: {e}")
                    # Fall through to sending a new message
            
            # If we don't have a current message or editing failed, send a new message
            sent_msg = bot.send_message(
                message.chat.id,
                f"✅ تم حفظ '{arabic_name}' بقيمة: `{message.text.strip()}`\n\n"
                f"ماذا تريد أن تفعل الآن؟",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            
            # Store the message ID for future updates and cleanup
            user_data[user_id]['current_edit_message_id'] = sent_msg.message_id
            if 'messages_to_delete' not in user_data[user_id]:
                user_data[user_id]['messages_to_delete'] = []
            user_data[user_id]['messages_to_delete'].append(sent_msg.message_id)
            
        except Exception as e:
            # Log detailed error information
            error_data = log_error(
                "TAG_VALUE_ERROR", 
                str(e), 
                user_id=user_id, 
                function_name="receive_specific_tag_value",
                extra_details={"message_text": message.text}
            )
            
            # Add error to bot status
            if len(bot_status["errors"]) >= 10:
                bot_status["errors"].pop(0)
            bot_status["errors"].append(error_data)
            bot_status["failed_operations"] += 1
            
            # Send user friendly error message
            bot.send_message(
                message.chat.id, 
                f"حدث خطأ أثناء حفظ الوسم. {response_messages['invalid_input']}"
            )
            
            # Return to tag selection menu
            handle_edit_tags(message, user_id)
    
    # Command handler for done command from any state
    @bot.message_handler(commands=['done'], state='*')
    def global_done_command(message):
        """Handle done command from any state."""
        user_id = message.from_user.id
        logger.info(f"Received global /done command from user {user_id}")
        
        # Check if user exists in user_data and is in editing mode
        logger.info(f"Checking if user {user_id} exists in user_data: {user_id in user_data}")
        if user_id in user_data:
            logger.info(f"User data for user {user_id}: {user_data[user_id]}")
            
        if user_id in user_data and user_data[user_id].get('is_editing', False):
            logger.info(f"User {user_id} is in editing mode, processing done command")
            if 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
                logger.info(f"User {user_id} has tags to save: {user_data[user_id]['new_tags']}")
                save_tags(message, bot)
            else:
                logger.info(f"User {user_id} has no tags to save")
                bot.send_message(message.chat.id, "لم تقم بإضافة أي وسوم للتعديل. الرجاء إضافة وسوم أو إلغاء العملية باستخدام /cancel.")
        else:
            # Also check state as a fallback
            current_state = bot.get_state(user_id, message.chat.id)
            logger.info(f"User {user_id} is not marked as editing. Current state: {current_state}")
            
            if current_state == BotStates.waiting_for_tag_values.name:
                logger.info(f"Based on state, user {user_id} is editing. Processing done command.")
                if user_id in user_data and 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
                    save_tags(message, bot)
                else:
                    bot.send_message(message.chat.id, "لم تقم بإضافة أي وسوم للتعديل. الرجاء إضافة وسوم أو إلغاء العملية باستخدام /cancel.")
            else:
                logger.info(f"User {user_id} is not in editing mode based on data or state, ignoring done command")
                bot.send_message(message.chat.id, "أنت لست في وضع تعديل الوسوم. أرسل ملفًا صوتيًا أولاً.")

    # Command handler for canceling operation from any state
    @bot.message_handler(commands=['cancel'], state='*')
    def cancel_command(message):
        """Cancel the operation from any state."""
        user_id = message.from_user.id
        logger.info(f"Received cancel command from user {user_id}")
        handle_cancel_operation(message, user_id)
        
    # General text handler as fallback - this must be the LAST handler
    @bot.message_handler(content_types=['text'], func=lambda message: True)
    def fallback_text_handler(message):
        """Fallback handler for text messages if all other handlers fail."""
        user_id = message.from_user.id
        
        # الحصول على حالة المستخدم من كلا النظامين
        bot_state = bot.get_state(user_id, message.chat.id)
        custom_state = get_user_state(user_id)
        
        current_state = bot_state
        # استخدام الحالة المخصصة إذا كانت موجودة
        if custom_state and 'state' in custom_state:
            current_state = custom_state['state']
            
        logger.info(f"Fallback text handler called for user {user_id}, bot_state: {bot_state}, custom_state: {custom_state}, text: {message.text}")
        
        # Check if the user is in a state that should be handled elsewhere
        if current_state == BotStates.waiting_for_specific_tag.name:
            logger.info(f"User {user_id} is in waiting_for_specific_tag state, manually handling tag value")
            
            # Try to get the tag being edited
            if user_id in user_data and 'editing_tag' in user_data[user_id]:
                tag_name = user_data[user_id]['editing_tag']
                arabic_name = get_tag_field_names_arabic().get(tag_name, tag_name)
                
                # Save the value
                user_data[user_id]['new_tags'][tag_name] = message.text.strip()
                logger.info(f"Saved value '{message.text.strip()}' for tag '{tag_name}' via fallback handler")
                
                # Create a keyboard with buttons
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("تعديل وسم آخر", callback_data="back_to_tags"),
                    types.InlineKeyboardButton("حفظ وإنهاء", callback_data="done_editing")
                )
                
                # Send confirmation message
                bot.send_message(
                    message.chat.id,
                    f"✅ تم حفظ '{arabic_name}' بقيمة: `{message.text.strip()}`\n\n"
                    f"ماذا تريد أن تفعل الآن؟",
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(message.chat.id, "حدث خطأ في معالجة قيمة الوسم. الرجاء المحاولة مرة أخرى.")
        elif current_state == BotStates.waiting_for_template_name.name:
            # المستخدم ينتظر إدخال اسم القالب
            logger.info(f"User {user_id} is in waiting_for_template_name state, handling template name: {message.text}")
            try:
                receive_template_name(message)
            except Exception as e:
                logger.error(f"Error processing template name: {str(e)}")
                bot.send_message(
                    message.chat.id,
                    "حدث خطأ أثناء معالجة اسم القالب. الرجاء المحاولة مرة أخرى."
                )
                # Reset state
                bot.set_state(user_id, BotStates.editing_tags, message.chat.id)
        
        elif current_state == BotStates.waiting_for_manual_template.name:
            # المستخدم ينتظر إدخال بيانات القالب اليدوي
            logger.info(f"User {user_id} is in waiting_for_manual_template state, handling template data: {message.text}")
            try:
                receive_manual_template(message)
            except Exception as e:
                logger.error(f"Error processing manual template data: {str(e)}")
                bot.send_message(
                    message.chat.id,
                    "حدث خطأ أثناء معالجة بيانات القالب. الرجاء المحاولة مرة أخرى."
                )
        
        elif current_state == BotStates.waiting_for_manual_template_name.name:
            # المستخدم ينتظر إدخال اسم القالب اليدوي
            logger.info(f"User {user_id} is in waiting_for_manual_template_name state, handling manual template name: {message.text}")
            try:
                receive_manual_template_name(message)
            except Exception as e:
                logger.error(f"Error processing manual template name: {str(e)}")
                bot.send_message(
                    message.chat.id,
                    "حدث خطأ أثناء معالجة اسم القالب. الرجاء المحاولة مرة أخرى."
                )
                
        # معالجة حالات المشرف المخصصة
        elif current_state == "admin_waiting_source_channel":
            # المشرف ينتظر إدخال معرف قناة المصدر للتعديل التلقائي
            logger.info(f"Admin {user_id} is in admin_waiting_source_channel state, processing channel ID: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية تعيين قناة المصدر."
                )
                # العودة للوحة التحكم
                from admin_handlers import open_admin_panel
                open_admin_panel(bot, message)
            else:
                # تعيين قناة المصدر
                from admin_panel import set_source_channel
                result = set_source_channel(message.text.strip())
                
                if result:
                    # نجاح
                    bot.send_message(
                        message.chat.id,
                        f"✅ تم تعيين قناة المصدر بنجاح: `{message.text.strip()}`",
                        parse_mode="Markdown"
                    )
                    # تنظيف الحالة
                    bot.delete_state(user_id, message.chat.id)
                    # العودة للوحة التحكم
                    from admin_handlers import open_admin_panel
                    open_admin_panel(bot, message)
                else:
                    # فشل
                    bot.send_message(
                        message.chat.id,
                        "❌ حدث خطأ أثناء تعيين قناة المصدر. الرجاء المحاولة مرة أخرى."
                    )
                    
        elif current_state == "admin_waiting_old_text":
            # المشرف ينتظر إدخال النص الأصلي للاستبدال
            logger.info(f"Admin {user_id} is in admin_waiting_old_text state, processing old text: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية إضافة استبدال نصي."
                )
                # العودة للوحة التحكم
                from admin_handlers import open_admin_panel
                open_admin_panel(bot, message)
            else:
                # حفظ النص الأصلي وطلب النص الجديد
                user_state = get_user_state(user_id)
                if user_state and 'data' in user_state:
                    user_state['data']['old_text'] = message.text.strip()
                    set_user_state(user_id, "admin_waiting_new_text", user_state['data'])
                    
                    msg = bot.send_message(
                        message.chat.id,
                        "📝 *إضافة استبدال نصي للوسوم*\n\n"
                        f"النص الأصلي: `{message.text.strip()}`\n\n"
                        "الآن أرسل النص الجديد الذي سيحل محل النص الأصلي.\n\n"
                        "🔄 أو أرسل `الغاء` للإلغاء.",
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ حدث خطأ أثناء معالجة النص الأصلي. الرجاء المحاولة مرة أخرى."
                    )
                    bot.delete_state(user_id, message.chat.id)
        
        elif current_state == "admin_waiting_new_text":
            # المشرف ينتظر إدخال النص الجديد للاستبدال
            logger.info(f"Admin {user_id} is in admin_waiting_new_text state, processing new text: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية إضافة استبدال نصي."
                )
                # العودة للوحة التحكم
                from admin_handlers import open_admin_panel
                open_admin_panel(bot, message)
            else:
                # إضافة استبدال نصي
                user_state = get_user_state(user_id)
                if user_state and 'data' in user_state and 'old_text' in user_state['data']:
                    old_text = user_state['data']['old_text']
                    new_text = message.text.strip()
                    
                    from admin_panel import add_tag_replacement
                    result = add_tag_replacement(old_text, new_text)
                    
                    if result:
                        # نجاح
                        bot.send_message(
                            message.chat.id,
                            f"✅ تم إضافة استبدال نصي بنجاح:\n"
                            f"النص الأصلي: `{old_text}`\n"
                            f"النص الجديد: `{new_text}`",
                            parse_mode="Markdown"
                        )
                    else:
                        # فشل
                        bot.send_message(
                            message.chat.id,
                            "❌ حدث خطأ أثناء إضافة استبدال نصي. الرجاء المحاولة مرة أخرى."
                        )
                    
                    # تنظيف الحالة
                    bot.delete_state(user_id, message.chat.id)
                    # العودة للوحة التحكم
                    from admin_handlers import open_admin_panel
                    open_admin_panel(bot, message)
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ حدث خطأ أثناء معالجة النص الجديد. الرجاء المحاولة مرة أخرى."
                    )
                    bot.delete_state(user_id, message.chat.id)
                    
        elif current_state == "admin_waiting_artist_name":
            # المشرف ينتظر إدخال اسم الفنان للقالب الذكي
            logger.info(f"Admin {user_id} is in admin_waiting_artist_name state, processing artist name: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية إضافة قالب ذكي."
                )
                # العودة للوحة التحكم
                from admin_handlers import open_admin_panel
                open_admin_panel(bot, message)
            else:
                # حفظ اسم الفنان وطلب معرف القالب
                user_state = get_user_state(user_id)
                if user_state and 'data' in user_state:
                    user_state['data']['artist_name'] = message.text.strip()
                    set_user_state(user_id, "admin_waiting_template_id", user_state['data'])
                    
                    # استيراد template_handler للحصول على قائمة القوالب
                    import template_handler
                    template_list = template_handler.get_template_list()
                    template_text = "\n".join([f"• `{t_id}`: {t_name}" for t_id, t_name in template_list.items()])
                    
                    msg = bot.send_message(
                        message.chat.id,
                        "📝 *إضافة قالب ذكي للتعديل التلقائي*\n\n"
                        f"اسم الفنان: `{message.text.strip()}`\n\n"
                        "الآن أرسل معرف القالب الذي سيتم تطبيقه تلقائيًا على أغاني هذا الفنان.\n\n"
                        f"القوالب المتاحة:\n{template_text}\n\n"
                        "🔄 أو أرسل `الغاء` للإلغاء.",
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ حدث خطأ أثناء معالجة اسم الفنان. الرجاء المحاولة مرة أخرى."
                    )
                    bot.delete_state(user_id, message.chat.id)
                    
        elif current_state == "admin_waiting_template_id":
            # المشرف ينتظر إدخال معرف القالب للقالب الذكي
            logger.info(f"Admin {user_id} is in admin_waiting_template_id state, processing template ID: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية إضافة قالب ذكي."
                )
                # العودة للوحة التحكم
                from admin_handlers import open_admin_panel
                open_admin_panel(bot, message)
            else:
                # إضافة قالب ذكي
                user_state = get_user_state(user_id)
                if user_state and 'data' in user_state and 'artist_name' in user_state['data']:
                    artist_name = user_state['data']['artist_name']
                    template_id = message.text.strip()
                    
                    from admin_panel import add_smart_template
                    result = add_smart_template(artist_name, template_id)
                    
                    if result:
                        # نجاح
                        bot.send_message(
                            message.chat.id,
                            f"✅ تم إضافة قالب ذكي بنجاح:\n"
                            f"اسم الفنان: `{artist_name}`\n"
                            f"معرف القالب: `{template_id}`",
                            parse_mode="Markdown"
                        )
                    else:
                        # فشل
                        bot.send_message(
                            message.chat.id,
                            "❌ حدث خطأ أثناء إضافة قالب ذكي. الرجاء التأكد من صحة معرف القالب والمحاولة مرة أخرى."
                        )
                    
                    # تنظيف الحالة
                    bot.delete_state(user_id, message.chat.id)
                    # العودة للوحة التحكم
                    from admin_handlers import open_admin_panel
                    open_admin_panel(bot, message)
                else:
                    bot.send_message(
                        message.chat.id,
                        "❌ حدث خطأ أثناء معالجة معرف القالب. الرجاء المحاولة مرة أخرى."
                    )
                    bot.delete_state(user_id, message.chat.id)
                    
        elif current_state == "admin_waiting_target_channel":
            # المشرف ينتظر إدخال معرف قناة الهدف للنشر التلقائي
            logger.info(f"Admin {user_id} is in admin_waiting_target_channel state, processing target channel ID: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية تعيين قناة الهدف."
                )
                # العودة للوحة التحكم
                from admin_handlers import open_admin_panel
                open_admin_panel(bot, message)
            else:
                # تعيين قناة الهدف
                from admin_panel import set_target_channel
                result = set_target_channel(message.text.strip())
                
                if result:
                    # نجاح
                    bot.send_message(
                        message.chat.id,
                        f"✅ تم تعيين قناة الهدف بنجاح: `{message.text.strip()}`",
                        parse_mode="Markdown"
                    )
                    # تنظيف الحالة
                    bot.delete_state(user_id, message.chat.id)
                    # العودة للوحة التحكم
                    from admin_handlers import open_admin_panel
                    open_admin_panel(bot, message)
                else:
                    # فشل
                    bot.send_message(
                        message.chat.id,
                        "❌ حدث خطأ أثناء تعيين قناة الهدف. الرجاء المحاولة مرة أخرى."
                    )
                    
        elif current_state == "waiting_for_footer_text":
            # المشرف ينتظر إدخال نص التذييل للوسوم
            logger.info(f"Admin {user_id} is in waiting_for_footer_text state, processing footer text: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية تعديل نص التذييل."
                )
                # إرجاع المستخدم إلى صفحة تذييل الوسوم
                from admin_handlers import handle_admin_callback
                handle_admin_callback(bot, types.CallbackQuery(
                    id="temp", from_user=message.from_user, message=message,
                    data="admin_tag_footer", chat_instance="0"
                ))
            else:
                # حفظ نص التذييل الجديد
                from admin_panel import set_tag_footer
                result = set_tag_footer(message.text)
                
                if result:
                    # نجاح
                    bot.send_message(
                        message.chat.id,
                        f"✅ تم تعيين نص التذييل بنجاح:\n\n{message.text}"
                    )
                    # تنظيف الحالة
                    bot.delete_state(user_id, message.chat.id)
                    # العودة لصفحة تذييل الوسوم
                    from admin_handlers import handle_admin_callback
                    handle_admin_callback(bot, types.CallbackQuery(
                        id="temp", from_user=message.from_user, message=message,
                        data="admin_tag_footer", chat_instance="0"
                    ))
                else:
                    # فشل
                    bot.send_message(
                        message.chat.id,
                        "❌ حدث خطأ أثناء تعيين نص التذييل. الرجاء المحاولة مرة أخرى."
                    )
                    bot.delete_state(user_id, message.chat.id)
        
        elif current_state == "admin_waiting_test_text":
            # المشرف ينتظر إدخال النص لتجربة القواعد الذكية عليه
            logger.info(f"Admin {user_id} is in admin_waiting_test_text state, processing test text: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                user_state = get_user_state(user_id)
                message_id = user_state['data']['message_id'] if user_state and 'data' in user_state and 'message_id' in user_state['data'] else None
                
                bot.delete_state(user_id, message.chat.id)
                
                if message_id:
                    # العودة إلى واجهة اختيار نوع الحقل
                    from admin_handlers import get_admin_smart_rules_markup
                    bot.edit_message_text(
                        "🧠 *القواعد الذكية*\n\n"
                        "اختر إحدى الوظائف التالية:",
                        message.chat.id, message_id,
                        reply_markup=get_admin_smart_rules_markup(),
                        parse_mode="Markdown"
                    )
                else:
                    # إذا لم نستطع العودة لنفس الرسالة، نرسل رسالة جديدة
                    bot.send_message(
                        message.chat.id,
                        "تم إلغاء عملية تجربة القواعد الذكية."
                    )
                    # العودة للوحة التحكم
                    from admin_handlers import open_admin_panel
                    open_admin_panel(bot, message)
            else:
                # استخراج نوع الحقل من حالة المستخدم
                user_state = get_user_state(user_id)
                if user_state and 'data' in user_state and 'field_id' in user_state['data']:
                    field_id = user_state['data']['field_id']
                    original_text = message.text.strip()
                    
                    # استيراد Smart Rules للتجربة
                    import smart_rules
                    
                    # الحصول على اسم الحقل
                    field_name = next((field['name'] for field in smart_rules.get_available_fields() if field['id'] == field_id), field_id)
                    
                    # تجربة القواعد الذكية
                    modified_text, applied_rules, active_rules_count = smart_rules.test_smart_rules_on_text(original_text, field_id)
                    
                    # تحضير رسالة النتيجة
                    result_message = f"🧪 *نتيجة تجربة القواعد الذكية*\n\n"
                    result_message += f"• *نوع الحقل*: {field_name} ({field_id})\n"
                    result_message += f"• *القواعد النشطة*: {active_rules_count}\n"
                    result_message += f"• *القواعد المطبقة*: {len(applied_rules)}\n\n"
                    
                    if original_text == modified_text:
                        result_message += "✅ لم يتم إجراء أي تغييرات على النص.\n\n"
                    else:
                        result_message += "✅ تم تطبيق التغييرات التالية:\n\n"
                        
                    result_message += f"*النص الأصلي*:\n`{original_text}`\n\n"
                    result_message += f"*النص بعد التطبيق*:\n`{modified_text}`\n\n"
                    
                    if applied_rules:
                        result_message += "*القواعد المطبقة*:\n"
                        for rule in applied_rules:
                            result_message += f"• {rule}\n"
                    
                    # إنشاء أزرار التحكم
                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton("🔄 تجربة نص آخر", callback_data="admin_test_smart_rules"),
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_rules")
                    )
                    
                    # إرسال النتيجة
                    bot.send_message(
                        message.chat.id,
                        result_message,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    
                    # تنظيف الحالة
                    bot.delete_state(user_id, message.chat.id)
                else:
                    # خطأ في استخراج البيانات
                    bot.send_message(
                        message.chat.id,
                        "❌ حدث خطأ أثناء معالجة النص. الرجاء المحاولة مرة أخرى."
                    )
                    bot.delete_state(user_id, message.chat.id)
                    # العودة للوحة التحكم
                    from admin_handlers import open_admin_panel
                    open_admin_panel(bot, message)
        
        elif current_state == "admin_waiting_for_template_data":
            # المشرف ينتظر إدخال بيانات القالب
            logger.info(f"Admin {user_id} is in admin_waiting_for_template_data state, processing template data: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية إنشاء القالب."
                )
                # العودة للوحة التحكم
                from admin_handlers import open_admin_panel
                open_admin_panel(bot, message)
            else:
                # معالجة بيانات القالب
                template_data = message.text.strip()
                tags = {}
                
                # استخراج الوسوم من النص المرسل
                lines = template_data.split('\n')
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # ترجمة أسماء الوسوم من العربية للإنجليزية
                        tag_mapping = {
                            'الفنان': 'artist',
                            'العنوان': 'title',
                            'الألبوم': 'album',
                            'فنان الألبوم': 'album_artist',
                            'السنة': 'year',
                            'النوع': 'genre',
                            'الملحن': 'composer',
                            'التعليق': 'comment',
                            'المسار': 'track',
                            'الكلمات': 'lyrics'  # إضافة كلمات الأغنية
                        }
                        
                        tag_name = tag_mapping.get(key)
                        if tag_name and value:
                            tags[tag_name] = value
                
                # التحقق من وجود وسوم على الأقل
                if tags:
                    # الحصول على معرف الرسالة من حالة المستخدم
                    user_state = get_user_state(user_id)
                    if user_state and 'data' in user_state and 'message_id' in user_state['data']:
                        message_id = user_state['data']['message_id']
                        
                        # إنشاء نص العرض
                        display_text = "✅ *تم استلام بيانات القالب*\n\n"
                        
                        # عرض الوسوم المستخرجة
                        tag_display_names = {
                            'artist': 'الفنان',
                            'title': 'العنوان',
                            'album': 'الألبوم',
                            'album_artist': 'فنان الألبوم',
                            'year': 'السنة',
                            'genre': 'النوع',
                            'composer': 'الملحن',
                            'comment': 'التعليق',
                            'track': 'المسار',
                            'lyrics': 'الكلمات'  # إضافة كلمات الأغنية
                        }
                        
                        for tag, value in tags.items():
                            display_name = tag_display_names.get(tag, tag)
                            # عرض النص المختصر لكلمات الأغنية إذا كانت طويلة
                            if tag == 'lyrics' and len(value) > 100:
                                display_value = value[:100] + "..."
                            else:
                                display_value = value
                                
                            display_text += f"• *{display_name}*: {display_value}\n"
                        
                        # حفظ الوسوم في حالة المستخدم
                        user_data[user_id] = user_data.get(user_id, {})
                        user_data[user_id]['manual_template_tags'] = tags
                        
                        # إنشاء أزرار التحكم
                        markup = types.InlineKeyboardMarkup()
                        markup.add(
                            types.InlineKeyboardButton("✅ حفظ القالب", callback_data="confirm_template"),
                            types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_template")
                        )
                        
                        # عرض النتيجة
                        bot.edit_message_text(
                            display_text,
                            message.chat.id, message_id,
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )
                        
                        # تغيير الحالة
                        set_user_state(user_id, "admin_waiting_for_template_confirmation", {"message_id": message_id})
                    else:
                        # إذا لم نتمكن من العثور على معرف الرسالة، نرسل رسالة جديدة
                        bot.send_message(
                            message.chat.id,
                            "⚠️ حدث خطأ أثناء معالجة بيانات القالب. الرجاء المحاولة مرة أخرى."
                        )
                        bot.delete_state(user_id, message.chat.id)
                else:
                    # لم يتم العثور على وسوم صالحة
                    bot.send_message(
                        message.chat.id,
                        "⚠️ لم يتم العثور على بيانات قالب صالحة. الرجاء التأكد من استخدام التنسيق الصحيح:\n\n"
                        "الفنان: اسم الفنان\n"
                        "العنوان: عنوان الأغنية\n"
                        "الألبوم: اسم الألبوم\n"
                        "السنة: 2024\n"
                        "النوع: نوع الموسيقى\n"
                        "الملحن: اسم الملحن\n"
                        "التعليق: أي تعليق إضافي\n"
                        "الكلمات: كلمات الأغنية"
                    )
                    
        elif current_state == "admin_waiting_for_template_name":
            # المشرف ينتظر إدخال اسم القالب
            logger.info(f"Admin {user_id} is in admin_waiting_for_template_name state, processing template name: {message.text}")
            
            if message.text.lower() == "الغاء":
                # إلغاء العملية
                bot.delete_state(user_id, message.chat.id)
                bot.send_message(
                    message.chat.id,
                    "تم إلغاء عملية إنشاء القالب."
                )
                # العودة للوحة التحكم
                from admin_handlers import open_admin_panel
                open_admin_panel(bot, message)
            else:
                # معالجة اسم القالب
                template_name = message.text.strip()
                
                # التحقق من وجود اسم
                if template_name:
                    # الحصول على معرف الرسالة وبيانات القالب من حالة المستخدم
                    user_state = get_user_state(user_id)
                    if user_state and 'data' in user_state and 'message_id' in user_state['data'] and 'template_tags' in user_state['data']:
                        message_id = user_state['data']['message_id']
                        template_tags = user_state['data']['template_tags']
                        
                        # حفظ القالب
                        import json
                        from pathlib import Path
                        
                        # تأكد من وجود مجلد القوالب
                        templates_dir = Path("templates")
                        templates_dir.mkdir(exist_ok=True)
                        
                        # تحضير ملف القالب
                        template_file = templates_dir / f"{template_name.replace('/', '_')}.json"
                        
                        # حفظ القالب في ملف
                        with open(template_file, 'w', encoding='utf-8') as f:
                            json.dump(template_tags, f, ensure_ascii=False, indent=4)
                        
                        # عرض رسالة نجاح
                        success_message = f"✅ *تم حفظ القالب بنجاح*\n\n"
                        success_message += f"📝 *اسم القالب:* {template_name}\n\n"
                        success_message += "*الوسوم المضمنة:*\n"
                        
                        # عرض الوسوم المضمنة
                        tag_display_names = {
                            'artist': 'الفنان',
                            'title': 'العنوان',
                            'album': 'الألبوم',
                            'album_artist': 'فنان الألبوم',
                            'year': 'السنة',
                            'genre': 'النوع',
                            'composer': 'الملحن',
                            'comment': 'التعليق',
                            'track': 'المسار',
                            'lyrics': 'الكلمات'  # إضافة كلمات الأغنية
                        }
                        
                        for tag, value in template_tags.items():
                            display_name = tag_display_names.get(tag, tag)
                            # عرض النص المختصر لكلمات الأغنية إذا كانت طويلة
                            if tag == 'lyrics' and len(value) > 100:
                                display_value = value[:100] + "..."
                            else:
                                display_value = value
                                
                            success_message += f"• *{display_name}*: {display_value}\n"
                        
                        # إضافة القالب إلى ملف admin_panel.py للاستخدام في المستقبل
                        import admin_panel
                        admin_panel.add_global_template(template_name, template_tags)
                        
                        # إنشاء أزرار التحكم
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔙 العودة إلى قائمة القوالب", callback_data="admin_templates"))
                        
                        # عرض النتيجة
                        bot.edit_message_text(
                            success_message,
                            message.chat.id, message_id,
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )
                        
                        # تنظيف الحالة
                        bot.delete_state(user_id, message.chat.id)
                        
                        # تسجيل
                        logger.info(f"Admin {user_id} created global template '{template_name}' with {len(template_tags)} tags")
                    else:
                        # إذا لم نتمكن من العثور على البيانات، نرسل رسالة خطأ
                        bot.send_message(
                            message.chat.id,
                            "⚠️ حدث خطأ أثناء حفظ القالب. الرجاء المحاولة مرة أخرى."
                        )
                        bot.delete_state(user_id, message.chat.id)
                else:
                    # لم يتم إدخال اسم
                    bot.send_message(
                        message.chat.id,
                        "⚠️ الرجاء إدخال اسم صالح للقالب."
                    )
        
        else:
            # Default response if we don't know what to do
            bot.send_message(
                message.chat.id,
                "مرحباً! أرسل لي ملف صوتي لعرض أو تعديل وسومه (العنوان، الفنان، الألبوم، إلخ)."
            )
    
    # ===== بداية وظائف إدارة القوالب =====
    def handle_save_template(message, user_id):
        """معالجة طلب حفظ القالب الحالي"""
        logger.info(f"User {user_id} wants to save current tags as template")
        
        # التأكد من وجود بيانات المستخدم
        if user_id not in user_data:
            bot.send_message(message.chat.id, "لا توجد وسوم لحفظها كقالب. الرجاء إرسال ملف صوتي أولاً.")
            return
            
        # استخدام current_tags لأنه يحتوي على الوسوم الحالية للملف
        if 'file_path' not in user_data[user_id]:
            bot.send_message(message.chat.id, "لا توجد وسوم لحفظها كقالب. الرجاء إرسال ملف صوتي أولاً.")
            return
            
        # استخراج الوسوم الحالية من الملف
        file_path = user_data[user_id]['file_path']
        current_tags = get_audio_tags(file_path)
        
        # إذا تم تعديل بعض الوسوم، استخدم الوسوم المعدلة
        if 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
            # دمج الوسوم الحالية مع التعديلات
            for tag, value in user_data[user_id]['new_tags'].items():
                current_tags[tag] = value
        
        # تعيين الحالة للانتظار لاسم القالب
        bot.set_state(user_id, BotStates.waiting_for_template_name, message.chat.id)
        
        # إنشاء لوحة مفاتيح مع زر العودة
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="إلغاء", callback_data="back_to_tags"))
        
        # أدخل اسم الفنان من الوسوم الحالية
        artist_name = extract_artist_from_tags(current_tags)
        
        # إرسال رسالة لطلب اسم القالب
        bot.send_message(
            message.chat.id,
            f"الرجاء إدخال اسم القالب الذي ستحفظ به هذه الوسوم.\n\n"
            f"سيتم ربط هذا القالب بالفنان: {artist_name}",
            reply_markup=markup
        )
    
    def handle_show_templates(message, user_id):
        """عرض قائمة الفنانين الذين لديهم قوالب"""
        logger.info(f"User {user_id} is viewing templates menu")
        
        # جلب قائمة الفنانين
        artists = get_artists_with_templates()
        
        # تحديد ما إذا كان المستخدم يملك ملف صوتي حاليًا
        has_audio_file = user_id in user_data and 'file_path' in user_data[user_id]
        return_callback = "back_to_tags" if has_audio_file else "back_to_start"
        
        if not artists:
            # إنشاء لوحة مفاتيح مع زر العودة
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text="رجوع", callback_data=return_callback))
            
            # إعداد الرسالة المناسبة حسب السياق
            if has_audio_file:
                msg_text = "لا توجد قوالب محفوظة بعد. يمكنك حفظ القالب الحالي باستخدام زر 'حفظ كقالب'."
            else:
                msg_text = "لا توجد قوالب محفوظة بعد. أرسل ملف صوتي أولاً ثم استخدم زر 'حفظ كقالب' لإنشاء قالب جديد، أو استخدم زر 'إنشاء قالب يدوي'."
            
            bot.send_message(
                message.chat.id,
                msg_text,
                reply_markup=markup
            )
            return
        
        # إنشاء لوحة مفاتيح مع أزرار للفنانين
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # إضافة زر لكل فنان
        for artist in artists:
            markup.add(types.InlineKeyboardButton(
                text=f"🎵 {artist}",
                callback_data=f"artist_templates_{artist}"
            ))
        
        # إضافة زر إنشاء قالب يدوي إذا كان المستخدم في القائمة الرئيسية
        if not has_audio_file:
            markup.add(types.InlineKeyboardButton(
                text="📝 إنشاء قالب يدوي",
                callback_data="create_manual_template"
            ))
        
        # إضافة زر العودة
        markup.add(types.InlineKeyboardButton(text="رجوع", callback_data=return_callback))
        
        # إرسال رسالة جديدة دائماً لعرض القوالب (لتجنب أخطاء تعديل رسائل الصور)
        try:
            # عدم استخدام edit_message_text لأن الرسالة السابقة قد تكون صورة
            template_message = bot.send_message(
                chat_id=message.chat.id,
                text="🗂️ اختر الفنان لعرض القوالب المتاحة:",
                reply_markup=markup
            )
            
            # حفظ معرف رسالة عرض القوالب لتسهيل التنظيف لاحقاً
            if user_id in user_data:
                if 'ui_message_ids' not in user_data[user_id]:
                    user_data[user_id]['ui_message_ids'] = []
                user_data[user_id]['ui_message_ids'].append(template_message.message_id)
        except Exception as e:
            logger.error(f"Error showing templates: {e}")
            bot.send_message(
                message.chat.id,
                "⚠️ حدث خطأ أثناء عرض القوالب. الرجاء المحاولة مرة أخرى."
            )
    
    # نقل دالة display_current_tags للأعلى حتى يمكن استخدامها في الدوال الأخرى
    def display_current_tags(message, user_id, file_path, show_edited=False):
        """
        عرض الوسوم الحالية للملف الصوتي
        
        Args:
            message: كائن الرسالة
            user_id: معرف المستخدم
            file_path: مسار الملف الصوتي
            show_edited: إذا كان True، سيتم استخدام الوسوم المعدلة مؤقتاً (إن وجدت)
        """
        logger.info(f"Displaying current tags for user {user_id}, showing edited: {show_edited}")
        
        try:
            # استخراج الوسوم من الملف
            current_tags = get_audio_tags(file_path)
            
            # إذا كان المطلوب هو عرض الوسوم المعدلة وكان هناك وسوم مؤقتة، استخدمها
            if show_edited and user_id in user_data and 'temp_tags' in user_data[user_id]:
                current_tags = user_data[user_id]['temp_tags']
            
            # إعداد رسالة الوسوم
            tag_names_arabic = get_tag_field_names_arabic()
            tag_message = "📋 الوسوم الحالية:\n\n"
            
            # تحديد الوسوم المعدلة لإضافة إشارة لها
            edited_tags = set()
            if user_id in user_data and 'temp_tags' in user_data[user_id] and 'original_tags' in user_data[user_id]:
                for tag, value in user_data[user_id]['temp_tags'].items():
                    if (tag in user_data[user_id]['original_tags'] and 
                            value != user_data[user_id]['original_tags'].get(tag, '')):
                        edited_tags.add(tag)
            
            # إضافة كل وسم إلى الرسالة مع مراعاة عدم عرض كلمات الأغنية في القائمة لتجنب الرسائل الطويلة
            for tag, value in current_tags.items():
                if tag != 'lyrics' and value:  # تجنب عرض كلمات الأغنية هنا
                    arabic_name = tag_names_arabic.get(tag, tag)
                    
                    # إضافة إشارة للوسوم المعدلة
                    edited_mark = "🔄 " if tag in edited_tags else ""
                    
                    # تقصير القيمة إذا كانت طويلة جداً
                    if value and isinstance(value, str) and len(value) > 30:
                        value = value[:30] + "..."
                    
                    tag_message += f"{edited_mark}{arabic_name}: {value}\n"
            
            # إضافة زر لعرض كلمات الأغنية إذا كانت موجودة
            has_lyrics = current_tags.get('lyrics', '')
            
            # إنشاء أزرار التحكم
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # الصف الأول: أزرار تحرير الوسوم والاطلاع على الكلمات
            row1 = []
            row1.append(types.InlineKeyboardButton("✏️ تحرير الوسوم", callback_data="edit_tags"))
            if has_lyrics:
                row1.append(types.InlineKeyboardButton("📝 عرض الكلمات", callback_data="show_lyrics"))
            markup.add(*row1)
            
            # الصف الثاني: إضافة زر تطبيق قالب جاهز
            markup.add(types.InlineKeyboardButton("🗂️ تطبيق قالب جاهز", callback_data="apply_template_menu"))
            
            # الصف الثالث: أزرار حفظ التغييرات - يظهر فقط عند وجود تغييرات للحفظ
            has_changes = False
            if user_id in user_data:
                if 'temp_tags' in user_data[user_id] and user_data[user_id]['temp_tags']:
                    has_changes = True
                elif 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
                    has_changes = True
            
            # إضافة زر حفظ التغييرات إذا كان هناك تغييرات
            if has_changes or show_edited:
                markup.add(types.InlineKeyboardButton("💾 حفظ التغييرات", callback_data="save_tags"))
            
            # إرسال الرسالة مع لوحة المفاتيح
            bot.send_message(message.chat.id, tag_message, reply_markup=markup)
            
        except Exception as e:
            error_data = log_error("display_tags", str(e), user_id, "display_current_tags")
            bot.send_message(
                message.chat.id, 
                f"حدث خطأ أثناء قراءة الوسوم: {e}"
            )


    
    def handle_show_artist_templates(message, user_id, artist_name):
        """عرض قوالب فنان محدد"""
        logger.info(f"User {user_id} is viewing templates for artist: {artist_name}")
        
        # جلب قائمة القوالب للفنان المحدد
        templates = list_templates(filter_artist=artist_name)
        
        if not templates:
            # إنشاء لوحة مفاتيح مع زر العودة
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text="رجوع لقائمة الفنانين", callback_data="show_templates"))
            
            bot.send_message(
                message.chat.id,
                f"لا توجد قوالب محفوظة للفنان '{artist_name}'.",
                reply_markup=markup
            )
            return
        
        # إنشاء لوحة مفاتيح مع أزرار للقوالب
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # إضافة زر لكل قالب
        for template in templates:
            # إضافة أيقونة للقوالب التي لديها صورة
            icon = "🖼️" if template.get("has_image") else "📋"
            markup.add(types.InlineKeyboardButton(
                text=f"{icon} {template['name']}",
                callback_data=f"apply_template_{template['id']}"
            ))
        
        # إضافة زر العودة
        markup.add(types.InlineKeyboardButton(
            text="رجوع لقائمة الفنانين",
            callback_data="show_templates"
        ))
        
        # إرسال رسالة جديدة دائمًا لعرض القوالب
        try:
            # استخدام إرسال رسالة جديدة بدلاً من تعديل لتجنب أخطاء تعديل الصور
            template_message = bot.send_message(
                chat_id=message.chat.id,
                text=f"🗂️ اختر القالب الذي تريد تطبيقه من قوالب الفنان '{artist_name}':",
                reply_markup=markup
            )
            
            # حفظ معرف الرسالة لتسهيل التنظيف لاحقاً
            if user_id in user_data:
                if 'ui_message_ids' not in user_data[user_id]:
                    user_data[user_id]['ui_message_ids'] = []
                user_data[user_id]['ui_message_ids'].append(template_message.message_id)
        except Exception as e:
            logger.error(f"Error showing artist templates: {e}")
            bot.send_message(
                message.chat.id,
                "⚠️ حدث خطأ أثناء عرض قوالب الفنان. الرجاء المحاولة مرة أخرى."
            )
    
    def handle_apply_template(message, user_id, template_id):
        """تطبيق قالب على الملف الحالي"""
        logger.info(f"User {user_id} is applying template: {template_id}")
        
        # جلب بيانات المستخدم والقالب
        template_data = get_template(template_id)
        
        # التأكد من وجود بيانات المستخدم
        if user_id not in user_data:
            bot.send_message(
                message.chat.id,
                "لم يتم العثور على ملف صوتي لتطبيق القالب عليه. الرجاء إرسال ملف صوتي أولاً."
            )
            return
            
        # التأكد من وجود ملف
        if 'file_path' not in user_data[user_id]:
            bot.send_message(
                message.chat.id,
                "لم يتم العثور على ملف صوتي لتطبيق القالب عليه. الرجاء إرسال ملف صوتي أولاً."
            )
            return
        
        # التأكد من وجود القالب
        if not template_data:
            bot.send_message(
                message.chat.id,
                "لم يتم العثور على القالب المطلوب. ربما تم حذفه أو تغييره."
            )
            return
        
        # إنشاء new_tags إذا لم يكن موجودًا
        if 'new_tags' not in user_data[user_id]:
            user_data[user_id]['new_tags'] = {}
            
        # إنشاء edited_tags إذا لم يكن موجودًا
        if 'edited_tags' not in user_data[user_id]:
            user_data[user_id]['edited_tags'] = set()
        
        # تطبيق وسوم القالب على الملف الحالي
        for tag, value in template_data.get('tags', {}).items():
            if tag in get_valid_tag_fields():
                # تحديث الوسوم المعدلة
                user_data[user_id]['new_tags'][tag] = value
                # تسجيل التغيير في قائمة الوسوم المعدلة
                user_data[user_id]['edited_tags'].add(tag)
        
        # تطبيق صورة الغلاف إذا كانت موجودة في القالب
        if 'album_art' in template_data and 'album_art_mime' in template_data:
            user_data[user_id]['album_art'] = template_data['album_art']
            user_data[user_id]['album_art_mime'] = template_data['album_art_mime']
            # تسجيل التغيير في قائمة الوسوم المعدلة
            user_data[user_id]['edited_tags'].add('album_art')
        
        bot.send_message(
            message.chat.id,
            f"✅ تم تطبيق القالب '{template_data.get('name', 'بدون اسم')}' بنجاح!"
        )
        
        # تنظيف رسائل القوالب المؤقتة
        cleanup_ui_messages(user_id, message.chat.id, bot)
        
        # العودة إلى قائمة تحرير الوسوم
        handle_edit_tags(message, user_id)
    
    # وظيفة للعودة إلى قائمة إدارة القوالب
    def return_to_template_management(message):
        """العودة إلى قائمة إدارة القوالب"""
        user_id = message.from_user.id
        logger.info(f"Returning user {user_id} to template management menu")
        
        # إنشاء لوحة مفاتيح للإدارة
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 إنشاء قالب يدوي", callback_data="create_manual_template"),
            types.InlineKeyboardButton("📋 عرض القوالب", callback_data="show_templates")
        )
        markup.add(
            types.InlineKeyboardButton("❌ حذف قالب", callback_data="delete_template"),
            types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="edit_template")
        )
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
        
        bot.send_message(
            message.chat.id,
            "🗂️ *إدارة القوالب*\n\n"
            "• استخدم *إنشاء قالب يدوي* لإضافة قالب جديد عن طريق إدخال الوسوم يدوياً\n"
            "• استخدم *عرض القوالب* لاستعراض القوالب المحفوظة وتطبيقها\n"
            "• استخدم *حذف قالب* لإزالة قالب موجود\n"
            "• استخدم *تعديل قالب* لتغيير محتوى قالب موجود",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    @bot.message_handler(content_types=['text'], state=BotStates.waiting_for_manual_template)
    def receive_manual_template(message):
        """استلام بيانات القالب اليدوي وتحليلها"""
        user_id = message.from_user.id
        template_data = message.text.strip()
        
        logger.info(f"Received manual template data from user {user_id}")
        
        # تحليل البيانات المدخلة
        tags = {}
        lines = template_data.split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                tag_name, value = line.split(':', 1)
                tag_name = tag_name.strip().lower()
                value = value.strip()
                
                if tag_name and tag_name in get_valid_tag_fields():
                    tags[tag_name] = value
        
        # التحقق من وجود بيانات صالحة
        if not tags:
            bot.send_message(
                message.chat.id,
                "❌ لم يتم العثور على بيانات صالحة. الرجاء اتباع التنسيق المطلوب:\n\ntitle: العنوان\nartist: الفنان\n..."
            )
            return
        
        # تخزين البيانات مؤقتاً وطلب اسم القالب
        user_data[user_id] = user_data.get(user_id, {})
        user_data[user_id]['manual_template_tags'] = tags
        
        # تغيير الحالة لانتظار اسم القالب
        bot.set_state(user_id, BotStates.waiting_for_manual_template_name, message.chat.id)
        
        # إنشاء نص يعرض الوسوم التي تم تحليلها
        tag_text = "📋 تم تحليل الوسوم التالية:\n\n"
        arabic_names = get_tag_field_names_arabic()
        
        for tag, value in tags.items():
            arabic_name = arabic_names.get(tag, tag)
            if value:
                tag_text += f"• {arabic_name}: {value}\n"
        
        # إنشاء لوحة مفاتيح مع خيار إلغاء
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("إلغاء ❌", callback_data="cancel_template_creation"))
        
        # إرسال رسالة تأكيد وطلب اسم للقالب
        bot.send_message(
            message.chat.id,
            f"{tag_text}\n\nالرجاء إدخال اسم للقالب:",
            reply_markup=markup
        )
    
    # معالج استلام اسم القالب اليدوي
    @bot.message_handler(content_types=['text'], state=BotStates.waiting_for_manual_template_name)
    def receive_manual_template_name(message):
        """استلام اسم القالب اليدوي وحفظ القالب"""
        user_id = message.from_user.id
        template_name = message.text.strip()
        
        if not template_name:
            bot.send_message(
                message.chat.id,
                "يجب إدخال اسم للقالب. الرجاء المحاولة مرة أخرى."
            )
            return
        
        # التأكد من وجود بيانات القالب
        if user_id not in user_data or 'manual_template_tags' not in user_data[user_id]:
            bot.send_message(
                message.chat.id,
                "حدث خطأ: لم يتم العثور على بيانات القالب. الرجاء المحاولة مرة أخرى."
            )
            bot.delete_state(user_id, message.chat.id)
            return
        
        # استخراج الوسوم المخزنة مؤقتاً
        tags = user_data[user_id]['manual_template_tags']
        
        # استخراج اسم الفنان من القالب أو استخدام "عام"
        artist_name = tags.get('artist', 'عام')
        
        # حفظ القالب
        success = save_template(template_name, artist_name, tags)
        
        if success:
            bot.send_message(
                message.chat.id,
                f"✅ تم حفظ القالب '{template_name}' بنجاح!"
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ حدث خطأ أثناء حفظ القالب. الرجاء المحاولة مرة أخرى."
            )
        
        # حذف البيانات المؤقتة
        if 'manual_template_tags' in user_data[user_id]:
            del user_data[user_id]['manual_template_tags']
        
        # حذف الحالة والعودة إلى قائمة إدارة القوالب
        bot.delete_state(user_id, message.chat.id)
        
        # العودة إلى قائمة إدارة القوالب
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 إنشاء قالب يدوي", callback_data="create_manual_template"),
            types.InlineKeyboardButton("📋 عرض القوالب", callback_data="show_templates")
        )
        markup.add(
            types.InlineKeyboardButton("❌ حذف قالب", callback_data="delete_template"),
            types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="edit_template")
        )
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_start"))
        
        bot.send_message(
            message.chat.id,
            "🗂️ *إدارة القوالب*\n\n"
            "• استخدم *إنشاء قالب يدوي* لإضافة قالب جديد عن طريق إدخال الوسوم يدوياً\n"
            "• استخدم *عرض القوالب* لاستعراض القوالب المحفوظة وتطبيقها\n"
            "• استخدم *حذف قالب* لإزالة قالب موجود\n"
            "• استخدم *تعديل قالب* لتغيير محتوى قالب موجود",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    def receive_template_name(message):
        """استقبال اسم القالب من المستخدم وحفظ القالب"""
        user_id = message.from_user.id
        template_name = message.text.strip()
        
        if not template_name:
            bot.send_message(
                message.chat.id,
                "يجب إدخال اسم للقالب. الرجاء المحاولة مرة أخرى."
            )
            return
        
        # التأكد من وجود بيانات المستخدم
        if user_id not in user_data:
            bot.send_message(
                message.chat.id,
                "لا توجد وسوم لحفظها كقالب. الرجاء إرسال ملف صوتي أولاً."
            )
            return
            
        # استخدام current_tags لأنه يحتوي على الوسوم الحالية للملف
        if 'file_path' not in user_data[user_id]:
            bot.send_message(
                message.chat.id,
                "لا توجد وسوم لحفظها كقالب. الرجاء إرسال ملف صوتي أولاً."
            )
            return
            
        # استخراج الوسوم الحالية من الملف
        file_path = user_data[user_id]['file_path']
        current_tags = get_audio_tags(file_path)
        
        # إذا تم تعديل بعض الوسوم، استخدم الوسوم المعدلة
        if 'new_tags' in user_data[user_id] and user_data[user_id]['new_tags']:
            # دمج الوسوم الحالية مع التعديلات
            for tag, value in user_data[user_id]['new_tags'].items():
                current_tags[tag] = value
        
        # استخراج اسم الفنان من الوسوم
        artist_name = extract_artist_from_tags(current_tags)
        
        # محاولة استخراج صورة الغلاف من الملف
        from tag_handler import extract_album_art
        album_art_data = extract_album_art(file_path)
        album_art = None
        album_art_mime = None
        
        if album_art_data and album_art_data[0]:
            album_art, album_art_mime = album_art_data
            
        # إذا كان المستخدم قد قام بتعديل صورة الغلاف، استخدم الصورة المعدلة
        if 'album_art' in user_data[user_id] and user_data[user_id]['album_art']:
            album_art = user_data[user_id]['album_art']
            album_art_mime = user_data[user_id].get('album_art_mime', 'image/jpeg')
        
        # حفظ القالب باستخدام وظيفة save_template
        success = save_template(
            template_name=template_name,
            artist_name=artist_name,
            tags=current_tags,
            album_art=album_art,
            album_art_mime=album_art_mime
        )
        
        if success:
            bot.send_message(
                message.chat.id,
                f"✅ تم حفظ القالب '{template_name}' للفنان '{artist_name}' بنجاح!"
            )
        else:
            bot.send_message(
                message.chat.id,
                "⚠️ حدث خطأ أثناء حفظ القالب. الرجاء المحاولة مرة أخرى."
            )
        
        # العودة إلى حالة تحرير الوسوم
        bot.set_state(user_id, BotStates.editing_tags, message.chat.id)
        
        # العودة إلى قائمة تحرير الوسوم
        handle_edit_tags(message, user_id)
    # ===== نهاية وظائف إدارة القوالب =====
    
    # ===== بداية وظائف لوحة الإدارة =====
    # استيراد مكونات لوحة الإدارة
    import admin_panel
    import admin_handlers
    
    @bot.message_handler(commands=['admin'])
    def admin_command(message):
        """فتح لوحة الإدارة للمشرف"""
        user_id = message.from_user.id
        logger.info(f"Received /admin command from user {user_id}")
        
        # التحقق من أن المستخدم مشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            return
        
        # تحديث بيانات المستخدم
        admin_panel.update_user_data(
            user_id, 
            message.from_user.username, 
            message.from_user.first_name
        )
        
        # فتح لوحة الإدارة
        admin_handlers.open_admin_panel(bot, message)
        
        # تعيين حالة المستخدم إلى لوحة الإدارة
        bot.set_state(user_id, BotStates.admin_panel, message.chat.id)
    
    @bot.message_handler(commands=['addadmin'])
    def add_admin_command(message):
        """إضافة مستخدم كمشرف"""
        admin_handlers.add_admin_command(bot, message)
    
    @bot.message_handler(commands=['removeadmin'])
    def remove_admin_command(message):
        """إزالة مستخدم من المشرفين"""
        admin_handlers.remove_admin_command(bot, message)
    
    @bot.message_handler(commands=['block'])
    def block_user_command(message):
        """حظر مستخدم"""
        admin_handlers.block_user_command(bot, message)
    
    @bot.message_handler(commands=['unblock'])
    def unblock_user_command(message):
        """إلغاء حظر مستخدم"""
        admin_handlers.unblock_user_command(bot, message)
    
    @bot.message_handler(commands=['broadcast'])
    def broadcast_command(message):
        """إرسال رسالة جماعية"""
        admin_handlers.broadcast_command(bot, message)
    
    # معالجة أزرار لوحة الإدارة المختلفة
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
    def admin_callback_handler(call):
        """معالجة أزرار لوحة الإدارة"""
        user_id = call.from_user.id
        logger.info(f"Received admin callback query: {call.data} from user {user_id}")
        
        # استدعاء معالج الأزرار من ملف admin_handlers
        admin_handlers.handle_admin_callback(bot, call)
    
    # معالج استقبال معرّف المشرف الجديد
    @bot.message_handler(state=BotStates.admin_waiting_for_admin_id)
    def receive_admin_id(message):
        """استقبال معرّف المشرف الجديد"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من أن المستخدم مشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            bot.delete_state(user_id, chat_id)
            return
        
        # التحقق من صحة المعرّف
        try:
            new_admin_id = int(message.text.strip())
            
            # التحقق من أن المستخدم ليس مشرفًا بالفعل
            if admin_panel.is_admin(new_admin_id):
                bot.reply_to(message, f"⚠️ المستخدم {new_admin_id} مشرف بالفعل.")
                # العودة إلى لوحة الإدارة
                admin_handlers.open_admin_panel(bot, message)
                bot.set_state(user_id, BotStates.admin_panel, chat_id)
                return
            
            # إضافة المشرف
            admin_panel.add_admin(new_admin_id)
            bot.reply_to(message, f"✅ تمت إضافة المستخدم {new_admin_id} كمشرف.")
            
            # تسجيل العملية
            admin_panel.log_action(user_id, "add_admin", "success", f"إضافة مشرف جديد: {new_admin_id}")
            
            # إرسال إشعار للمشرف الجديد إذا كان موجودًا في قاعدة البيانات
            user_data = admin_panel.admin_data['users'].get(str(new_admin_id))
            if user_data:
                try:
                    bot.send_message(
                        new_admin_id,
                        f"🎉 تهانينا! تمت إضافتك كمشرف في البوت.\n\n"
                        f"يمكنك الآن استخدام أوامر المشرف مثل /admin لفتح لوحة الإدارة."
                    )
                except Exception as e:
                    logger.error(f"Error sending admin notification: {e}")
        except ValueError:
            bot.reply_to(message, "⚠️ معرّف غير صالح. يرجى إدخال رقم صحيح.")
            return
        
        # العودة إلى لوحة الإدارة
        admin_handlers.open_admin_panel(bot, message)
        bot.set_state(user_id, BotStates.admin_panel, chat_id)
    
    # معالج استقبال معرّف المستخدم للحظر
    @bot.message_handler(state=BotStates.admin_waiting_for_user_id)
    def receive_user_id_to_block(message):
        """استقبال معرّف المستخدم للحظر"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من أن المستخدم مشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            bot.delete_state(user_id, chat_id)
            return
        
        # التحقق من صحة المعرّف
        try:
            block_user_id = int(message.text.strip())
            
            # التحقق من أن المستخدم ليس مشرفًا
            if admin_panel.is_admin(block_user_id):
                bot.reply_to(message, f"⚠️ لا يمكن حظر المستخدم {block_user_id} لأنه مشرف.")
                # العودة إلى لوحة الإدارة
                admin_handlers.open_admin_panel(bot, message)
                bot.set_state(user_id, BotStates.admin_panel, chat_id)
                return
            
            # التحقق من أن المستخدم ليس محظورًا بالفعل
            if admin_panel.is_blocked(block_user_id):
                bot.reply_to(message, f"⚠️ المستخدم {block_user_id} محظور بالفعل.")
                # العودة إلى لوحة الإدارة
                admin_handlers.open_admin_panel(bot, message)
                bot.set_state(user_id, BotStates.admin_panel, chat_id)
                return
            
            # حظر المستخدم
            admin_panel.block_user(block_user_id)
            bot.reply_to(message, f"✅ تم حظر المستخدم {block_user_id} بنجاح.")
            
            # تسجيل العملية
            admin_panel.log_action(user_id, "block_user", "success", f"حظر مستخدم: {block_user_id}")
            
        except ValueError:
            bot.reply_to(message, "⚠️ معرّف غير صالح. يرجى إدخال رقم صحيح.")
            return
        
        # العودة إلى لوحة الإدارة
        admin_handlers.open_admin_panel(bot, message)
        bot.set_state(user_id, BotStates.admin_panel, chat_id)
    
    # معالج استقبال نص الرسالة الجماعية
    @bot.message_handler(state=BotStates.admin_waiting_for_broadcast)
    def receive_broadcast_message(message):
        """استقبال نص الرسالة الجماعية"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من أن المستخدم مشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            bot.delete_state(user_id, chat_id)
            return
        
        # الحصول على نص الرسالة
        broadcast_text = message.text
        
        # تأكيد الإرسال
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ نعم", callback_data="admin_confirm_broadcast"),
            types.InlineKeyboardButton("❌ لا", callback_data="admin_cancel_broadcast")
        )
        
        # حفظ نص الرسالة في بيانات المستخدم المؤقتة
        # استخدام user_states لتخزين البيانات المؤقتة
        if not hasattr(bot, 'user_broadcast_data'):
            bot.user_broadcast_data = {}
        bot.user_broadcast_data[user_id] = broadcast_text
        
        bot.reply_to(
            message,
            f"📢 *تأكيد الرسالة الجماعية*\n\nهل أنت متأكد من رغبتك في إرسال الرسالة التالية إلى جميع المستخدمين؟\n\n{broadcast_text}",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        # العودة إلى لوحة الإدارة (ستتم معالجة الرد على زر التأكيد في معالج الأزرار)
        bot.set_state(user_id, BotStates.admin_panel, chat_id)
    
    # معالج استقبال رسالة الترحيب الجديدة
    @bot.message_handler(state=BotStates.admin_waiting_for_welcome_msg)
    def receive_welcome_message(message):
        """استقبال رسالة الترحيب الجديدة"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من أن المستخدم مشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            bot.delete_state(user_id, chat_id)
            return
        
        # تحديث رسالة الترحيب
        welcome_message = message.text
        admin_panel.update_welcome_message(welcome_message)
        
        bot.reply_to(message, "✅ تم تحديث رسالة الترحيب بنجاح.")
        
        # تسجيل العملية
        admin_panel.log_action(user_id, "update_welcome_message", "success")
        
        # العودة إلى لوحة الإدارة
        admin_handlers.open_admin_panel(bot, message)
        bot.set_state(user_id, BotStates.admin_panel, chat_id)
    
    # معالج استقبال استبدال نصي جديد (للتعديل التلقائي)
    @bot.message_handler(state=BotStates.admin_waiting_for_replacement)
    def receive_tag_replacement(message):
        """استقبال استبدال نصي جديد"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من أن المستخدم مشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            bot.delete_state(user_id, chat_id)
            return
        
        # تحليل النص المدخل
        input_text = message.text
        if '|' not in input_text:
            bot.reply_to(message, "❌ تنسيق غير صحيح. الرجاء إدخال الاستبدال بالتنسيق: النص القديم|النص الجديد")
            return
        
        old_text, new_text = input_text.split('|', 1)
        old_text = old_text.strip()
        new_text = new_text.strip()
        
        if not old_text:
            bot.reply_to(message, "❌ النص القديم لا يمكن أن يكون فارغًا.")
            return
        
        # إضافة الاستبدال
        admin_panel.add_tag_replacement(old_text, new_text)
        admin_panel.log_action(user_id, "add_tag_replacement", "success", f"إضافة استبدال: {old_text} -> {new_text}")
        
        bot.reply_to(message, f"✅ تم إضافة الاستبدال بنجاح:\n\n•{old_text}• ➡️ •{new_text}•")
        
        # العودة إلى صفحة استبدالات الوسوم
        markup = admin_handlers.get_admin_tag_replacements_markup()
        bot.send_message(
            chat_id,
            "🏷️ استبدالات الوسوم",
            reply_markup=markup
        )
        
        bot.set_state(user_id, BotStates.admin_panel, chat_id)
    
    # معالج استقبال قالب ذكي جديد (للتعديل التلقائي)
    @bot.message_handler(state=BotStates.admin_waiting_for_watermark_size)
    def receive_watermark_size(message):
        """استلام حجم العلامة المائية"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من صلاحيات المشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ ليس لديك صلاحيات كافية لاستخدام هذا الأمر.")
            return
        
        # التحقق من صحة الإدخال
        try:
            size = int(message.text.strip())
            if size < 1 or size > 100:
                bot.reply_to(message, "❌ يجب أن يكون الحجم بين 1 و 100. الرجاء المحاولة مرة أخرى.")
                return
                
            # تحديث إعدادات العلامة المائية
            if admin_panel.set_image_watermark_size(size):
                # إعادة تعيين حالة المستخدم
                bot.delete_state(user_id, chat_id)
                
                # تأكيد التحديث
                bot.send_message(
                    chat_id,
                    f"✅ تم تحديث حجم العلامة المائية بنجاح إلى {size}%.",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 العودة لإعدادات العلامة المائية", callback_data="admin_image_watermark")
                    )
                )
            else:
                bot.reply_to(message, "❌ حدث خطأ أثناء تحديث حجم العلامة المائية. الرجاء المحاولة مرة أخرى.")
        except ValueError:
            bot.reply_to(message, "❌ الرجاء إدخال قيمة رقمية صحيحة للحجم (1-100).")
    
    @bot.message_handler(state=BotStates.admin_waiting_for_watermark_opacity)
    def receive_watermark_opacity(message):
        """استلام شفافية العلامة المائية"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من صلاحيات المشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ ليس لديك صلاحيات كافية لاستخدام هذا الأمر.")
            return
        
        # التحقق من صحة الإدخال
        try:
            opacity = int(message.text.strip())
            if opacity < 1 or opacity > 100:
                bot.reply_to(message, "❌ يجب أن تكون الشفافية بين 1 و 100. الرجاء المحاولة مرة أخرى.")
                return
                
            # تحديث إعدادات العلامة المائية
            if admin_panel.set_image_watermark_opacity(opacity):
                # إعادة تعيين حالة المستخدم
                bot.delete_state(user_id, chat_id)
                
                # تأكيد التحديث
                bot.send_message(
                    chat_id,
                    f"✅ تم تحديث شفافية العلامة المائية بنجاح إلى {opacity}%.",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 العودة لإعدادات العلامة المائية", callback_data="admin_image_watermark")
                    )
                )
            else:
                bot.reply_to(message, "❌ حدث خطأ أثناء تحديث شفافية العلامة المائية. الرجاء المحاولة مرة أخرى.")
        except ValueError:
            bot.reply_to(message, "❌ الرجاء إدخال قيمة رقمية صحيحة للشفافية (1-100).")
    
    @bot.message_handler(state=BotStates.admin_waiting_for_watermark_padding)
    def receive_watermark_padding(message):
        """استلام تباعد العلامة المائية"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من صلاحيات المشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ ليس لديك صلاحيات كافية لاستخدام هذا الأمر.")
            return
        
        # التحقق من صحة الإدخال
        try:
            padding = int(message.text.strip())
            if padding < 1 or padding > 100:
                bot.reply_to(message, "❌ يجب أن يكون التباعد بين 1 و 100. الرجاء المحاولة مرة أخرى.")
                return
                
            # تحديث إعدادات العلامة المائية
            if admin_panel.set_image_watermark_padding(padding):
                # إعادة تعيين حالة المستخدم
                bot.delete_state(user_id, chat_id)
                
                # تأكيد التحديث
                bot.send_message(
                    chat_id,
                    f"✅ تم تحديث تباعد العلامة المائية بنجاح إلى {padding} بكسل.",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 العودة لإعدادات العلامة المائية", callback_data="admin_image_watermark")
                    )
                )
            else:
                bot.reply_to(message, "❌ حدث خطأ أثناء تحديث تباعد العلامة المائية. الرجاء المحاولة مرة أخرى.")
        except ValueError:
            bot.reply_to(message, "❌ الرجاء إدخال قيمة رقمية صحيحة للتباعد (1-100).")
    
    @bot.message_handler(content_types=['photo'], state=BotStates.admin_waiting_for_watermark_image)
    def receive_watermark_image(message):
        """استلام صورة العلامة المائية"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من صلاحيات المشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ ليس لديك صلاحيات كافية لاستخدام هذا الأمر.")
            return
        
        try:
            # الحصول على الصورة بأعلى دقة
            file_info = bot.get_file(message.photo[-1].file_id)
            if file_info.file_path:
                downloaded_file = bot.download_file(file_info.file_path)
                
                # حفظ الصورة بشكل مؤقت
                temp_path = f"temp_watermark_{user_id}.png"
                with open(temp_path, 'wb') as f:
                    f.write(downloaded_file)
                
                # تحديث إعدادات العلامة المائية
                if admin_panel.save_image_watermark(temp_path):
                    # إعادة تعيين حالة المستخدم
                    bot.delete_state(user_id, chat_id)
                    
                    # تأكيد التحديث
                    bot.send_message(
                        chat_id,
                        "✅ تم تعيين صورة العلامة المائية بنجاح.",
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 العودة لإعدادات العلامة المائية", callback_data="admin_image_watermark")
                        )
                    )
                    
                    # حذف الملف المؤقت
                    try:
                        import os
                        os.remove(temp_path)
                    except Exception as e:
                        logger.error(f"فشل في حذف الملف المؤقت: {temp_path} - {e}")
                else:
                    bot.reply_to(message, "❌ حدث خطأ أثناء حفظ صورة العلامة المائية. الرجاء المحاولة مرة أخرى.")
            else:
                bot.reply_to(message, "❌ لم يتم العثور على الصورة. الرجاء المحاولة مرة أخرى.")
        except Exception as e:
            logger.error(f"خطأ أثناء معالجة صورة العلامة المائية: {e}")
            bot.reply_to(message, f"❌ حدث خطأ أثناء معالجة الصورة. الرجاء المحاولة مرة أخرى.")
    
    # الرد على رسائل النص أثناء انتظار صورة العلامة المائية
    @bot.message_handler(content_types=['text'], state=BotStates.admin_waiting_for_watermark_image)
    def text_for_watermark_image(message):
        """معالجة الرسائل النصية أثناء انتظار صورة العلامة المائية"""
        bot.reply_to(message, "🖼️ يرجى إرسال صورة لاستخدامها كعلامة مائية.\n\nإذا كنت تريد العودة لقائمة الإعدادات، اضغط على زر الإلغاء أدناه.")
    
    @bot.message_handler(state=BotStates.admin_waiting_for_smart_template)
    def receive_smart_template(message):
        """استقبال قالب ذكي جديد"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # التحقق من أن المستخدم مشرف
        if not admin_panel.is_admin(user_id):
            bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
            bot.delete_state(user_id, chat_id)
            return
        
        # تحليل النص المدخل
        input_text = message.text
        if '|' not in input_text:
            bot.reply_to(message, "❌ تنسيق غير صحيح. الرجاء إدخال القالب الذكي بالتنسيق: اسم الفنان|معرف القالب")
            return
        
        artist_name, template_id = input_text.split('|', 1)
        artist_name = artist_name.strip()
        template_id = template_id.strip()
        
        if not artist_name or not template_id:
            bot.reply_to(message, "❌ اسم الفنان ومعرف القالب لا يمكن أن يكونوا فارغين.")
            return
        
        # التحقق من وجود القالب
        template = get_template(template_id)
        if not template:
            bot.reply_to(message, f"❌ القالب بالمعرف {template_id} غير موجود.")
            return
        
        # إضافة القالب الذكي
        admin_panel.add_smart_template(artist_name, template_id)
        admin_panel.log_action(user_id, "add_smart_template", "success", f"إضافة قالب ذكي للفنان: {artist_name}")
        
        bot.reply_to(message, f"✅ تم إضافة القالب الذكي بنجاح:\nالفنان: {artist_name}\nالقالب: {template_id}")
        
        # العودة إلى صفحة القوالب الذكية
        markup = admin_handlers.get_admin_smart_templates_markup()
        bot.send_message(
            chat_id,
            "🎯 القوالب الذكية",
            reply_markup=markup
        )
        
        bot.set_state(user_id, BotStates.admin_panel, chat_id)
    
    # ===== نهاية وظائف لوحة الإدارة =====
    
    # Configure retry and timeouts for better stability
    telebot.apihelper.READ_TIMEOUT = 30
    telebot.apihelper.CONNECT_TIMEOUT = 20
    
    # Start the bot with improved error handling
    try:
        logger.info("Starting bot polling with error handling...")
        bot.polling(none_stop=True, interval=2, timeout=30)
    except Exception as e:
        logger.error(f"Critical error in bot polling: {str(e)}")
        import time
        time.sleep(10) # Wait a bit before potentially restarting
        logger.info("Attempting to recover from bot polling error")
        


if __name__ == "__main__":
    start_bot()
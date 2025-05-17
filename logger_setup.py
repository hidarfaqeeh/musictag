"""
وحدة إعداد نظام تسجيل السجلات للبوت
تُستخدم لتتبع العمليات والأخطاء بشكل منظم ومفصل
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import traceback
from datetime import datetime

# إعداد مجلد السجلات
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# تكوين اسم ملفات السجلات
MAIN_LOG_FILE = os.path.join(LOG_DIR, "bot.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "errors.log")
DEBUG_LOG_FILE = os.path.join(LOG_DIR, "debug.log")
USER_ACTIONS_LOG_FILE = os.path.join(LOG_DIR, "user_actions.log")
ADMIN_ACTIONS_LOG_FILE = os.path.join(LOG_DIR, "admin_actions.log")
AUTO_PROCESSING_LOG_FILE = os.path.join(LOG_DIR, "auto_processing.log")

# إنشاء أداة تنسيق السجلات
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]')

# إعداد السجل الرئيسي
def setup_main_logger():
    """إعداد السجل الرئيسي للبوت"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # إضافة مُخرج إلى وحدة التحكم
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # إضافة مُخرج إلى ملف السجل الرئيسي مع دوران الملفات
    file_handler = RotatingFileHandler(
        MAIN_LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    
    return logger

# إعداد سجل الأخطاء
def setup_error_logger():
    """إعداد سجل خاص للأخطاء"""
    error_logger = logging.getLogger('errors')
    error_logger.setLevel(logging.ERROR)
    
    # إضافة مُخرج إلى ملف سجل الأخطاء
    error_handler = RotatingFileHandler(
        ERROR_LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    error_handler.setFormatter(log_formatter)
    error_logger.addHandler(error_handler)
    
    return error_logger

# إعداد سجل إجراءات المستخدمين
def setup_user_actions_logger():
    """إعداد سجل خاص لعمليات المستخدمين"""
    user_logger = logging.getLogger('user_actions')
    user_logger.setLevel(logging.INFO)
    
    # إضافة مُخرج إلى ملف سجل إجراءات المستخدمين
    user_handler = RotatingFileHandler(
        USER_ACTIONS_LOG_FILE, maxBytes=8*1024*1024, backupCount=5, encoding='utf-8'
    )
    user_handler.setFormatter(log_formatter)
    user_logger.addHandler(user_handler)
    
    return user_logger

# إعداد سجل إجراءات المشرفين
def setup_admin_actions_logger():
    """إعداد سجل خاص لعمليات المشرفين"""
    admin_logger = logging.getLogger('admin_actions')
    admin_logger.setLevel(logging.INFO)
    
    # إضافة مُخرج إلى ملف سجل إجراءات المشرفين
    admin_handler = RotatingFileHandler(
        ADMIN_ACTIONS_LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    admin_handler.setFormatter(log_formatter)
    admin_logger.addHandler(admin_handler)
    
    return admin_logger

# إعداد سجل المعالجة التلقائية
def setup_auto_processing_logger():
    """إعداد سجل خاص للمعالجة التلقائية للقنوات"""
    auto_logger = logging.getLogger('auto_processing')
    auto_logger.setLevel(logging.INFO)
    
    # إضافة مُخرج إلى ملف سجل المعالجة التلقائية
    auto_handler = RotatingFileHandler(
        AUTO_PROCESSING_LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    auto_handler.setFormatter(log_formatter)
    auto_logger.addHandler(auto_handler)
    
    return auto_logger

# إعداد سجل التصحيح
def setup_debug_logger():
    """إعداد سجل خاص للتصحيح"""
    debug_logger = logging.getLogger('debug')
    debug_logger.setLevel(logging.DEBUG)
    
    # إضافة مُخرج إلى ملف سجل التصحيح
    debug_handler = RotatingFileHandler(
        DEBUG_LOG_FILE, maxBytes=10*1024*1024, backupCount=2, encoding='utf-8'
    )
    debug_handler.setFormatter(log_formatter)
    debug_logger.addHandler(debug_handler)
    
    return debug_logger

# دالة لتسجيل عمليات المستخدمين
def log_user_action(user_id, username, action, details=None):
    """تسجيل عملية مستخدم"""
    user_logger = logging.getLogger('user_actions')
    message = f"User ID: {user_id}, Username: {username}, Action: {action}"
    if details:
        message += f", Details: {details}"
    user_logger.info(message)

# دالة لتسجيل عمليات المشرفين
def log_admin_action(admin_id, username, action, details=None):
    """تسجيل عملية مشرف"""
    admin_logger = logging.getLogger('admin_actions')
    message = f"Admin ID: {admin_id}, Username: {username}, Action: {action}"
    if details:
        message += f", Details: {details}"
    admin_logger.info(message)

# دالة لتسجيل الأخطاء
def log_error(error, context=None, user_id=None, function_name=None, extra_details=None):
    """تسجيل خطأ مع تفاصيل الاستثناء
    
    Args:
        error: رسالة الخطأ أو كائن الاستثناء
        context: سياق الخطأ (نص اختياري)
        user_id: معرف المستخدم (اختياري)
        function_name: اسم الوظيفة التي حدث فيها الخطأ (اختياري)
        extra_details: تفاصيل إضافية (اختياري)
    """
    error_logger = logging.getLogger('errors')
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # جمع معلومات الاستثناء
    exc_info = sys.exc_info()
    if exc_info[0]:
        trace_details = "".join(traceback.format_exception(*exc_info))
    else:
        trace_details = str(error)
    
    # بناء رسالة الخطأ
    error_message = f"Error at {error_time}: {str(error)}\n"
    
    # إضافة المعلومات الإضافية إذا كانت متوفرة
    if user_id:
        error_message += f"User ID: {user_id}\n"
    if function_name:
        error_message += f"Function: {function_name}\n"
    if context:
        error_message += f"Context: {context}\n"
    if extra_details:
        error_message += f"Details: {extra_details}\n"
        
    error_message += f"Traceback:\n{trace_details}"
    
    # تسجيل الخطأ
    error_logger.error(error_message)
    
    # طباعة الخطأ للتصحيح أيضاً
    logging.getLogger('debug').debug(error_message)

# دالة لتسجيل العمليات التلقائية
def log_auto_processing(channel_id, channel_name, action, status, details=None):
    """تسجيل عملية معالجة تلقائية"""
    auto_logger = logging.getLogger('auto_processing')
    message = f"Channel: {channel_id} ({channel_name}), Action: {action}, Status: {status}"
    if details:
        message += f", Details: {details}"
    auto_logger.info(message)

# تهيئة جميع السجلات
def init_all_loggers():
    """تهيئة جميع السجلات للاستخدام"""
    main_logger = setup_main_logger()
    setup_error_logger()
    setup_user_actions_logger()
    setup_admin_actions_logger()
    setup_auto_processing_logger()
    setup_debug_logger()
    
    # تعطيل السجلات غير المرغوبة من المكتبات الخارجية
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telebot').setLevel(logging.WARNING)
    
    main_logger.info("تم تهيئة نظام السجلات بنجاح")
    
    return main_logger

# تحسين المعالج الافتراضي للاستثناءات غير المعالجة
def setup_exception_handler():
    """إعداد معالج الاستثناءات غير المعالجة"""
    def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
        """معالجة الاستثناءات غير المعالجة"""
        if issubclass(exc_type, KeyboardInterrupt):
            # السماح للانقطاع بالفأرة بالعمل بشكل طبيعي
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        # تسجيل الاستثناء غير المعالج
        error_logger = logging.getLogger('errors')
        error_message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        error_logger.critical(f"UNCAUGHT EXCEPTION: {error_message}")
        
        # عرض رسالة في وحدة التحكم
        print(f"CRITICAL ERROR: Uncaught exception - See logs/errors.log for details")
    
    # تعيين معالج الاستثناءات
    sys.excepthook = handle_uncaught_exception
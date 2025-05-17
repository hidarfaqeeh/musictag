"""
وحدة إعدادات البوت
تقوم بتحميل المتغيرات البيئية من ملف .env وتوفيرها للتطبيق
"""

import os
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

# تحميل المتغيرات من ملف .env
load_dotenv()

# إعداد سجل خاص بالإعدادات
logger = logging.getLogger('config')

class Config:
    """فئة الإعدادات العامة للبوت"""
    
    # معلومات المطورين
    DEVELOPER_ID = int(os.getenv('DEVELOPER_ID', '1174919068'))
    DEVELOPER_IDS = [int(id.strip()) for id in os.getenv('DEVELOPER_IDS', '1174919068,6556918772,6602517122').split(',') if id.strip()]
    
    # معلومات البوت
    BOT_TOKEN = os.getenv('TELEGRAM_TOKEN') or os.getenv('BOT_TOKEN', '')
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'Audio_tag_edit_bot')
    BOT_NAME = os.getenv('BOT_NAME', 'بوت تعديل وسوم الصوت')
    
    # قنوات الدعم
    SUPPORT_CHANNEL = os.getenv('SUPPORT_CHANNEL', '')
    SUPPORT_GROUP = os.getenv('SUPPORT_GROUP', '')
    
    # حدود الاستخدام
    DAILY_USER_LIMIT_MB = int(os.getenv('DAILY_USER_LIMIT_MB', '50'))
    MAX_AUDIO_SIZE_MB = int(os.getenv('MAX_AUDIO_SIZE_MB', '30'))
    
    # إعدادات المعالجة التلقائية
    AUTO_PROCESSING_ENABLED = os.getenv('AUTO_PROCESSING_ENABLED', 'false').lower() == 'true'
    SOURCE_CHANNEL = os.getenv('SOURCE_CHANNEL', '')
    KEEP_CAPTION = os.getenv('KEEP_CAPTION', 'true').lower() == 'true'
    AUTO_PUBLISH = os.getenv('AUTO_PUBLISH', 'true').lower() == 'true'
    
    # المجلدات
    TEMP_DIR = os.getenv('TEMP_DIR', 'temp_audio_files')
    TEMPLATES_DIR = os.getenv('TEMPLATES_DIR', 'templates')
    
    # إعدادات السجلات
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_TO_CHANNEL = os.getenv('LOG_TO_CHANNEL', 'false').lower() == 'true'
    LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID', '')
    
    # بيئة التشغيل
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    
    @classmethod
    def is_production(cls) -> bool:
        """التحقق مما إذا كانت البيئة هي بيئة إنتاج"""
        return cls.ENVIRONMENT.lower() == 'production'
    
    @classmethod
    def is_developer(cls, user_id: int) -> bool:
        """التحقق مما إذا كان المستخدم مطوراً للبوت"""
        return user_id in cls.DEVELOPER_IDS
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """الحصول على قاموس يحتوي على جميع الإعدادات"""
        config_dict = {}
        for key in dir(cls):
            if not key.startswith('__') and not callable(getattr(cls, key)):
                config_dict[key] = getattr(cls, key)
        return config_dict
    
    @classmethod
    def log_config(cls) -> None:
        """تسجيل الإعدادات الحالية (مع إخفاء المعلومات الحساسة)"""
        config_dict = cls.get_config_dict()
        
        # إخفاء المعلومات الحساسة
        if 'BOT_TOKEN' in config_dict and config_dict['BOT_TOKEN']:
            config_dict['BOT_TOKEN'] = '***************'
        
        logger.info(f"تم تحميل الإعدادات: {config_dict}")
    
    @classmethod
    def init_directories(cls) -> None:
        """إنشاء المجلدات المطلوبة إذا لم تكن موجودة"""
        os.makedirs(cls.TEMP_DIR, exist_ok=True)
        os.makedirs(cls.TEMPLATES_DIR, exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        logger.info(f"تم التأكد من وجود المجلدات المطلوبة: {cls.TEMP_DIR}, {cls.TEMPLATES_DIR}, logs")

# تهيئة المجلدات والسجلات عند استيراد الوحدة
Config.init_directories()
Config.log_config()
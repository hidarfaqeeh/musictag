import os
import json
import time
import logging
import psutil
from datetime import datetime
from collections import defaultdict
from telebot import types
from typing import Dict, List, Set, Optional, Union, Any, Tuple

# إعداد التسجيل
logger = logging.getLogger('admin_panel')
logger.setLevel(logging.INFO)

# تخزين بيانات المشرفين والمستخدمين والإحصائيات
admin_data = {
    'admins': set(),  # مجموعة معرّفات المشرفين
    'blocked_users': set(),  # مجموعة المستخدمين المحظورين
    'statistics': {
        'total_files_processed': 0,  # عدد الملفات التي تم معالجتها
        'successful_edits': 0,  # عدد التعديلات الناجحة
        'failed_operations': 0,  # عدد العمليات الفاشلة
        'daily_files_processed': 0,  # عدد الملفات المعالجة اليوم
        'daily_data_usage': 0,  # إجمالي حجم البيانات المستهلكة اليوم (ميجابايت)
        'bot_start_time': time.time(),  # وقت بدء تشغيل البوت
        'last_reset_time': time.time(),  # وقت آخر إعادة تعيين للإحصائيات
        'daily_stats_reset': time.time(),  # وقت آخر إعادة تعيين للإحصائيات اليومية
    },
    'users': {},  # معلومات المستخدمين: {user_id: {'username': '', 'first_name': '', 'last_seen': timestamp, 'files_processed': 0, 'daily_usage': 0, 'daily_reset': timestamp}}
    'logs': [],  # سجل العمليات: [{'time': timestamp, 'user_id': user_id, 'action': '', 'status': 'success|failed', 'details': ''}]
    'scheduled_broadcasts': [],  # البث المجدول: [{'time': timestamp, 'message': '', 'type': 'text|photo|video|document', 'file_id': '', 'sent': False}]
    'global_templates': {},  # القوالب العامة: {template_name: {tag1: value1, tag2: value2, ...}}
    'settings': {
        'welcome_message': 'مرحباً بك في بوت تعديل الوسوم الصوتية! أرسل ملف صوتي لبدء التعديل.\n\nيدعم البوت تعديل الوسوم التالية: العنوان، الفنان، الألبوم، فنان الألبوم، السنة، النوع، الملحن، التعليق، رقم المسار، المدة، كلمات الأغنية، وصورة الغلاف.\n\nيمكنك استخدام زر \'إدارة القوالب\' لإنشاء وعرض وتعديل القوالب.\n\nاستخدم /help للحصول على مزيد من المعلومات.',  # رسالة الترحيب المخصصة
        'bot_description': 'بوت متخصص في تعديل وسوم الملفات الصوتية (MP3, FLAC, WAV, وغيرها) بواجهة سهلة الاستخدام بالكامل باللغة العربية.',  # وصف البوت
        'usage_notes': 'لاستخدام البوت، فقط أرسل ملف صوتي وسيعرض البوت الوسوم الحالية. يمكنك الضغط على زر "تحرير الوسوم" لتعديلها.\n\nيتيح البوت حفظ القوالب واستخدامها لاحقاً، ويدعم صور الألبوم وكلمات الأغاني.',  # ملاحظات استخدام البوت
        'max_file_size_mb': 50,  # الحد الأقصى لحجم الملف بالميجابايت
        'processing_delay': 0,  # وقت التأخير بين تعديل كل ملف (بالثواني)
        'daily_user_limit_mb': 0,  # حد البيانات اليومي لكل مستخدم (0 = غير محدود)
        'log_channel': "",  # معرّف قناة سجل الأحداث
        'required_channels': [],  # قنوات الاشتراك الإجباري: [{"channel_id": "@channel", "title": "اسم القناة"}]
        'features_enabled': {  # الميزات المفعّلة/المعطّلة
            'templates': True,
            'lyrics': True,
            'album_art': True,
            'required_subscription': False,  # تفعيل/تعطيل الاشتراك الإجباري
            'auto_tags': False,  # إضافة وسوم تلقائية
            'auto_processing': False,  # التعديل التلقائي للقنوات
        },
        'auto_tags': {  # الوسوم التي تضاف تلقائياً
            'artist': '',
            'album_artist': '',
            'album': '',
            'genre': '',
            'year': '',
            'comment': ''
        },
        'audio_watermark': {  # إعدادات العلامة المائية الصوتية
            'enabled': False,
            'file_path': '',  # مسار ملف العلامة المائية
            'position': 'start',  # موضع العلامة المائية (start, end)
            'volume': 0.5  # مستوى صوت العلامة المائية (0.0-1.0)
        },
        'auto_processing': {  # إعدادات المعالجة التلقائية للقنوات
            'enabled': False,  # تفعيل/تعطيل المعالجة التلقائية
            'source_channel': "",  # معرف قناة المصدر
            'keep_caption': True,  # الحفاظ على الكابشن الأصلي
            'auto_publish': True,  # نشر الرسالة تلقائياً بعد التعديل
            'tag_replacements': {},  # استبدالات الوسوم: {"من": "إلى"}
            'enabled_tags': {  # الوسوم المفعلة للاستبدال
                'artist': True,
                'album_artist': True,
                'album': True,
                'genre': True,
                'year': True,
                'composer': True,
                'comment': True,
                'title': True
            },
            'smart_templates': {}  # القوالب الذكية حسب الفنان: {"اسم الفنان": "معرف القالب"}
        },
        'notifications': {  # إشعارات المشرفين
            'new_users': True,
            'errors': True,
            'admin_login': True,  # إشعار عند تسجيل دخول مشرف
            'daily_report': False  # إرسال تقرير يومي
        }
    }
}

# المسار للملف الذي يخزن بيانات المشرفين والإحصائيات
ADMIN_DATA_FILE = 'admin_data.json'

def load_admin_data():
    """تحميل بيانات المشرفين والإحصائيات من الملف"""
    global admin_data
    try:
        if os.path.exists(ADMIN_DATA_FILE):
            with open(ADMIN_DATA_FILE, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                # تحويل المعرّفات من سلاسل نصية إلى أرقام صحيحة وتحويل القوائم إلى مجموعات
                if 'admins' in file_data:
                    admin_data['admins'] = set(int(admin_id) for admin_id in file_data['admins'])
                if 'blocked_users' in file_data:
                    admin_data['blocked_users'] = set(int(user_id) for user_id in file_data['blocked_users'])
                # نسخ بقية البيانات
                if 'statistics' in file_data:
                    admin_data['statistics'] = file_data['statistics']
                if 'users' in file_data:
                    admin_data['users'] = file_data['users']
                if 'logs' in file_data:
                    admin_data['logs'] = file_data['logs']
                if 'settings' in file_data:
                    admin_data['settings'] = file_data['settings']
                logger.info("تم تحميل بيانات المشرفين والإحصائيات بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تحميل بيانات المشرفين والإحصائيات: {e}")

def save_admin_data():
    """حفظ بيانات المشرفين والإحصائيات في الملف"""
    try:
        # تحويل المجموعات إلى قوائم للتمكن من تحويلها إلى JSON
        data_to_save = admin_data.copy()
        data_to_save['admins'] = list(admin_data['admins'])
        data_to_save['blocked_users'] = list(admin_data['blocked_users'])
        
        with open(ADMIN_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        logger.info("تم حفظ بيانات المشرفين والإحصائيات بنجاح")
    except Exception as e:
        logger.error(f"خطأ في حفظ بيانات المشرفين والإحصائيات: {e}")

def is_admin(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم مشرفًا"""
    # إضافة معرفك كمشرف إذا لم يكن موجودًا بالفعل (معرّفات متعددة للمطورين)
    developer_ids = [1174919068, 6556918772, 6602517122]
    
    if user_id in developer_ids and user_id not in admin_data['admins']:
        admin_data['admins'].add(user_id)
        save_admin_data()
        logger.info(f"تمت إضافة المستخدم {user_id} كمشرف (مطور البوت)")
    
    return user_id in admin_data['admins'] or user_id in developer_ids

def add_admin(user_id: int) -> bool:
    """إضافة مستخدم كمشرف"""
    if user_id not in admin_data['admins']:
        admin_data['admins'].add(user_id)
        save_admin_data()
        logger.info(f"تمت إضافة المستخدم {user_id} كمشرف")
        return True
    return False

def remove_admin(user_id: int) -> bool:
    """إزالة مستخدم من المشرفين"""
    if user_id in admin_data['admins']:
        admin_data['admins'].remove(user_id)
        save_admin_data()
        logger.info(f"تمت إزالة المستخدم {user_id} من المشرفين")
        return True
    return False

def block_user(user_id: int) -> bool:
    """حظر مستخدم"""
    if user_id not in admin_data['blocked_users']:
        admin_data['blocked_users'].add(user_id)
        save_admin_data()
        logger.info(f"تم حظر المستخدم {user_id}")
        return True
    return False

def unblock_user(user_id: int) -> bool:
    """إلغاء حظر مستخدم"""
    if user_id in admin_data['blocked_users']:
        admin_data['blocked_users'].remove(user_id)
        save_admin_data()
        logger.info(f"تم إلغاء حظر المستخدم {user_id}")
        return True
    return False

def is_blocked(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم محظورًا"""
    return user_id in admin_data['blocked_users']

def log_action(user_id: int, action: str, status: str = 'success', details: str = ''):
    """تسجيل عملية في سجل العمليات"""
    log_entry = {
        'time': time.time(),
        'user_id': user_id,
        'action': action,
        'status': status,
        'details': details
    }
    admin_data['logs'].append(log_entry)
    # الاحتفاظ بآخر 1000 عملية فقط
    if len(admin_data['logs']) > 1000:
        admin_data['logs'] = admin_data['logs'][-1000:]
    save_admin_data()

def update_user_data(user_id: int, username: str = None, first_name: str = None, files_processed: int = 0, file_size_mb: float = 0):
    """تحديث بيانات المستخدم"""
    user_id_str = str(user_id)
    now = time.time()
    
    if user_id_str not in admin_data['users']:
        admin_data['users'][user_id_str] = {
            'username': username if username else "",
            'first_name': first_name if first_name else "",
            'last_seen': now,
            'files_processed': 0,
            'first_seen': now,
            'daily_usage': 0,
            'daily_reset': now  # توقيت آخر إعادة تعيين للاستخدام اليومي
        }
        # إذا كانت ميزة إشعارات المستخدمين الجدد مفعّلة، سجّل ذلك للإشعار
        if admin_data['settings']['notifications']['new_users']:
            for admin_id in admin_data['admins']:
                notify_admin(admin_id, f"مستخدم جديد: {first_name} (@{username})")
            
            # إرسال إلى قناة السجل إذا كانت مفعّلة
            log_channel = admin_data['settings'].get('log_channel', "")
            if log_channel:
                try:
                    send_to_log_channel(f"👤 مستخدم جديد: {first_name} (@{username}) - المعرف: {user_id}")
                except:
                    pass
    
    # تحديث بيانات المستخدم
    user_data = admin_data['users'][user_id_str]
    if username:
        user_data['username'] = username
    if first_name:
        user_data['first_name'] = first_name
    user_data['last_seen'] = now
    user_data['files_processed'] += files_processed
    
    # تحديث الاستخدام اليومي
    # إعادة تعيين العداد اليومي إذا مر أكثر من 24 ساعة
    daily_reset_time = user_data.get('daily_reset', 0)
    if now - daily_reset_time > 86400:  # 24 ساعة
        user_data['daily_usage'] = 0
        user_data['daily_reset'] = now
    
    # زيادة الاستخدام اليومي
    if 'daily_usage' not in user_data:
        user_data['daily_usage'] = 0
    user_data['daily_usage'] += file_size_mb
    
    save_admin_data()
    
    return user_data

def increment_statistic(stat_name: str, value: int = 1):
    """زيادة قيمة إحصائية"""
    if stat_name in admin_data['statistics']:
        admin_data['statistics'][stat_name] += value
        save_admin_data()

def reset_statistics():
    """إعادة تعيين الإحصائيات"""
    admin_data['statistics']['total_files_processed'] = 0
    admin_data['statistics']['successful_edits'] = 0
    admin_data['statistics']['failed_operations'] = 0
    admin_data['statistics']['last_reset_time'] = time.time()
    save_admin_data()

def get_system_info() -> Dict:
    """الحصول على معلومات النظام"""
    return {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'uptime': time.time() - admin_data['statistics']['bot_start_time']
    }

def get_active_users(days: int = 7) -> List[Dict]:
    """الحصول على المستخدمين النشطين في الأيام الأخيرة"""
    active_users = []
    now = time.time()
    days_seconds = days * 24 * 60 * 60
    
    for user_id, user_data in admin_data['users'].items():
        if now - user_data.get('last_seen', 0) <= days_seconds:
            user_info = user_data.copy()
            user_info['user_id'] = user_id
            if 'daily_usage' not in user_info:
                user_info['daily_usage'] = 0
            active_users.append(user_info)
    
    # ترتيب المستخدمين حسب آخر ظهور
    active_users.sort(key=lambda x: x['last_seen'], reverse=True)
    return active_users

def get_top_users(limit: int = 10) -> List[Dict]:
    """الحصول على أكثر المستخدمين نشاطًا"""
    users = []
    for user_id, user_data in admin_data['users'].items():
        user_info = user_data.copy()
        user_info['user_id'] = user_id
        users.append(user_info)
    
    # ترتيب المستخدمين حسب عدد الملفات المعالجة
    users.sort(key=lambda x: x['files_processed'], reverse=True)
    return users[:limit]

def get_recent_logs(limit: int = 20) -> List[Dict]:
    """الحصول على آخر سجلات العمليات"""
    return admin_data['logs'][-limit:]

def get_logs_by_user(user_id: int, limit: int = 20) -> List[Dict]:
    """الحصول على سجلات عمليات مستخدم معين"""
    user_logs = [log for log in admin_data['logs'] if log['user_id'] == user_id]
    return user_logs[-limit:]

def get_error_logs(limit: int = 20) -> List[Dict]:
    """الحصول على سجلات الأخطاء"""
    error_logs = [log for log in admin_data['logs'] if log['status'] == 'failed']
    return error_logs[-limit:]

def update_setting(setting_path: str, value: Any) -> bool:
    """تحديث إعداد معين"""
    try:
        global admin_data
        
        # التأكد من وجود المفاتيح الأساسية
        if 'settings' not in admin_data:
            admin_data['settings'] = {}
        
        path_parts = setting_path.split('.')
        current = admin_data['settings']
        
        # إنشاء القواميس المفقودة في الهيكل
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            
        # تعيين القيمة
        current[path_parts[-1]] = value
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث الإعداد {setting_path}: {e}")
        return False

def get_setting(setting_path: str, default: Any = None) -> Any:
    """الحصول على قيمة إعداد معين"""
    try:
        # التحقق من وجود settings
        if 'settings' not in admin_data:
            return default
            
        path_parts = setting_path.split('.')
        current = admin_data['settings']
        
        # متابعة المسار
        for part in path_parts:
            if part not in current:
                return default
            current = current[part]
            
        return current
    except Exception:
        return default

def notify_admin(admin_id: int, message: str) -> bool:
    """إرسال إشعار لمشرف معين"""
    # ملاحظة: هذه الدالة تحتاج إلى كائن البوت للإرسال
    # سيتم استدعاؤها من خارج هذا الملف
    return True

def send_broadcast(bot, message: str, user_ids: List[int] = None):
    """إرسال رسالة جماعية للمستخدمين"""
    if user_ids is None:
        # إرسال لجميع المستخدمين
        user_ids = [int(user_id) for user_id in admin_data['users'].keys()]
    
    success_count = 0
    fail_count = 0
    
    for user_id in user_ids:
        try:
            if not is_blocked(user_id):
                bot.send_message(user_id, message)
                success_count += 1
        except Exception as e:
            logger.error(f"خطأ في إرسال رسالة جماعية للمستخدم {user_id}: {e}")
            fail_count += 1
    
    return success_count, fail_count

def clean_temp_files():
    """تنظيف الملفات المؤقتة"""
    temp_dir = "temp_audio_files"
    try:
        if os.path.exists(temp_dir):
            files_removed = 0
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    files_removed += 1
            logger.info(f"تم تنظيف {files_removed} ملف مؤقت")
            return files_removed
        return 0
    except Exception as e:
        logger.error(f"خطأ في تنظيف الملفات المؤقتة: {e}")
        return -1

def export_data(data_type: str = 'all') -> str:
    """تصدير البيانات إلى ملف"""
    try:
        export_filename = f"export_{data_type}_{int(time.time())}.json"
        data_to_export = {}
        
        if data_type == 'all':
            data_to_export = admin_data.copy()
            data_to_export['admins'] = list(admin_data['admins'])
            data_to_export['blocked_users'] = list(admin_data['blocked_users'])
        elif data_type == 'users':
            data_to_export = admin_data['users']
        elif data_type == 'logs':
            data_to_export = admin_data['logs']
        elif data_type == 'statistics':
            data_to_export = admin_data['statistics']
        elif data_type == 'settings':
            data_to_export = admin_data['settings']
        elif data_type == 'templates':
            # هنا يتم تصدير قوالب ID3 من مجلد templates
            data_to_export = {'templates': []}
            templates_dir = "templates"
            if os.path.exists(templates_dir):
                for filename in os.listdir(templates_dir):
                    if filename.endswith(".json"):
                        template_path = os.path.join(templates_dir, filename)
                        try:
                            with open(template_path, 'r', encoding='utf-8') as tf:
                                template_data = json.load(tf)
                                data_to_export['templates'].append({
                                    'filename': filename,
                                    'data': template_data
                                })
                        except Exception as te:
                            logger.error(f"خطأ في قراءة ملف القالب {filename}: {te}")
        
        with open(export_filename, 'w', encoding='utf-8') as f:
            json.dump(data_to_export, f, ensure_ascii=False, indent=2)
        
        return export_filename
    except Exception as e:
        logger.error(f"خطأ في تصدير البيانات: {e}")
        return None

def import_data(filename: str, data_type: str = 'all') -> bool:
    """استيراد البيانات من ملف"""
    try:
        if not os.path.exists(filename):
            return False
        
        with open(filename, 'r', encoding='utf-8') as f:
            imported_data = json.load(f)
        
        if data_type == 'all':
            # تحديث كل البيانات باستثناء المشرفين المحظورين (للأمان)
            admin_data['statistics'] = imported_data.get('statistics', admin_data['statistics'])
            admin_data['users'] = imported_data.get('users', admin_data['users'])
            admin_data['logs'] = imported_data.get('logs', admin_data['logs'])
            admin_data['settings'] = imported_data.get('settings', admin_data['settings'])
            # استيراد القوالب إذا كانت موجودة
            if 'templates' in imported_data:
                import_templates(imported_data['templates'])
        elif data_type == 'users':
            admin_data['users'] = imported_data
        elif data_type == 'logs':
            admin_data['logs'] = imported_data
        elif data_type == 'statistics':
            admin_data['statistics'] = imported_data
        elif data_type == 'settings':
            admin_data['settings'] = imported_data
        elif data_type == 'templates':
            # استيراد القوالب فقط
            if 'templates' in imported_data:
                import_templates(imported_data['templates'])
            else:
                # إذا كان الملف يحتوي على قائمة القوالب مباشرة
                import_templates(imported_data)
        
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في استيراد البيانات: {e}")
        return False

def import_templates(templates_data):
    """استيراد القوالب من البيانات المستوردة"""
    try:
        templates_dir = "templates"
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir)
        
        success_count = 0
        for template in templates_data:
            if isinstance(template, dict):
                if 'filename' in template and 'data' in template:
                    # حفظ القالب كملف
                    template_path = os.path.join(templates_dir, template['filename'])
                    with open(template_path, 'w', encoding='utf-8') as tf:
                        json.dump(template['data'], tf, ensure_ascii=False, indent=2)
                    success_count += 1
                elif 'name' in template and 'artist' in template and 'tags' in template:
                    # قالب مستورد بتنسيق مباشر
                    template_id = f"{template['artist']}_{template['name']}"
                    template_path = os.path.join(templates_dir, f"{template_id}.json")
                    with open(template_path, 'w', encoding='utf-8') as tf:
                        json.dump(template, tf, ensure_ascii=False, indent=2)
                    success_count += 1
        
        logger.info(f"تم استيراد {success_count} قالب بنجاح")
        return success_count
    except Exception as e:
        logger.error(f"خطأ في استيراد القوالب: {e}")
        return 0

def reset_user_limit(user_id: int = None) -> bool:
    """إعادة تعيين الحد اليومي لمستخدم معين أو لكل المستخدمين"""
    try:
        if user_id:
            # إعادة تعيين الحد لمستخدم محدد
            user_id_str = str(user_id)
            if user_id_str in admin_data['users']:
                admin_data['users'][user_id_str]['daily_usage'] = 0
                admin_data['users'][user_id_str]['daily_reset'] = time.time()
                save_admin_data()
                return True
            return False
        else:
            # إعادة تعيين الحد لكل المستخدمين
            for user_id_str in admin_data['users']:
                admin_data['users'][user_id_str]['daily_usage'] = 0
                admin_data['users'][user_id_str]['daily_reset'] = time.time()
            
            # إعادة تعيين الإحصائيات اليومية
            admin_data['statistics']['daily_files_processed'] = 0
            admin_data['statistics']['daily_data_usage'] = 0
            admin_data['statistics']['daily_stats_reset'] = time.time()
            
            save_admin_data()
            return True
    except Exception as e:
        logger.error(f"خطأ في إعادة تعيين الحد اليومي: {e}")
        return False

def schedule_broadcast(message_text: str, timestamp: float = None, message_type: str = 'text', file_id: str = None) -> bool:
    """جدولة رسالة بث جماعي
    
    Args:
        message_text: نص الرسالة
        timestamp: وقت الإرسال (unix timestamp)، إذا كان None سيتم الإرسال حالاً
        message_type: نوع الرسالة ('text', 'photo', 'video', 'document')
        file_id: معرف الملف في حالة الصورة أو الفيديو أو المستند
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if timestamp is None:
            timestamp = time.time()  # الآن
        
        broadcast_data = {
            'time': timestamp,
            'message': message_text,
            'type': message_type,
            'file_id': file_id if file_id else '',
            'sent': False,
            'scheduled_id': int(time.time() * 1000)  # معرف فريد للبث المجدول
        }
        
        admin_data['scheduled_broadcasts'].append(broadcast_data)
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في جدولة البث الجماعي: {e}")
        return False

def get_pending_broadcasts() -> List[Dict]:
    """الحصول على البث المجدول المعلق (الذي لم يتم إرساله بعد)
    
    Returns:
        List[Dict]: قائمة البث المجدول المعلق
    """
    now = time.time()
    return [b for b in admin_data['scheduled_broadcasts'] if not b.get('sent', False) and b.get('time', 0) <= now]

def mark_broadcast_sent(scheduled_id: int) -> bool:
    """تحديد بث مجدول كمرسل
    
    Args:
        scheduled_id: معرف البث المجدول
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        for broadcast in admin_data['scheduled_broadcasts']:
            if broadcast.get('scheduled_id') == scheduled_id:
                broadcast['sent'] = True
                save_admin_data()
                return True
        return False
    except Exception as e:
        logger.error(f"خطأ في تحديد البث المجدول كمرسل: {e}")
        return False

def get_scheduled_broadcasts() -> List[Dict]:
    """الحصول على قائمة البث المجدول
    
    Returns:
        List[Dict]: قائمة البث المجدول
    """
    return sorted(admin_data['scheduled_broadcasts'], key=lambda b: b.get('time', 0))

def remove_scheduled_broadcast(scheduled_id: int) -> bool:
    """إزالة بث مجدول
    
    Args:
        scheduled_id: معرف البث المجدول
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        for i, broadcast in enumerate(admin_data['scheduled_broadcasts']):
            if broadcast.get('scheduled_id') == scheduled_id:
                admin_data['scheduled_broadcasts'].pop(i)
                save_admin_data()
                return True
        return False
    except Exception as e:
        logger.error(f"خطأ في إزالة البث المجدول: {e}")
        return False

def update_bot_description(description: str) -> bool:
    """تحديث وصف البوت
    
    Args:
        description: وصف البوت الجديد
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        admin_data['settings']['bot_description'] = description
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث وصف البوت: {e}")
        return False

def update_usage_notes(notes: str) -> bool:
    """تحديث ملاحظات استخدام البوت
    
    Args:
        notes: ملاحظات الاستخدام الجديدة
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        admin_data['settings']['usage_notes'] = notes
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث ملاحظات استخدام البوت: {e}")
        return False

def add_tag_replacement(old_text: str, new_text: str) -> bool:
    """إضافة استبدال نصي للتعديل التلقائي
    
    Args:
        old_text: النص المراد استبداله
        new_text: النص البديل
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'auto_processing' not in admin_data['settings']:
            admin_data['settings']['auto_processing'] = {
                'tag_replacements': {}
            }
        elif 'tag_replacements' not in admin_data['settings']['auto_processing']:
            admin_data['settings']['auto_processing']['tag_replacements'] = {}
        
        # إضافة الاستبدال
        admin_data['settings']['auto_processing']['tag_replacements'][old_text] = new_text
        save_admin_data()
        logger.info(f"تمت إضافة استبدال نصي: {old_text} -> {new_text}")
        return True
    except Exception as e:
        logger.error(f"خطأ في إضافة استبدال نصي: {e}")
        return False
        
def remove_tag_replacement(old_text: str) -> bool:
    """إزالة استبدال نصي للتعديل التلقائي
    
    Args:
        old_text: النص المراد إزالة استبداله
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if ('auto_processing' in admin_data['settings'] and 
            'tag_replacements' in admin_data['settings']['auto_processing'] and
            old_text in admin_data['settings']['auto_processing']['tag_replacements']):
            
            del admin_data['settings']['auto_processing']['tag_replacements'][old_text]
            save_admin_data()
            logger.info(f"تمت إزالة استبدال نصي: {old_text}")
            return True
        return False
    except Exception as e:
        logger.error(f"خطأ في إزالة استبدال نصي: {e}")
        return False

def add_smart_template(artist_name: str, template_id: str) -> bool:
    """إضافة قالب ذكي للتعديل التلقائي حسب اسم الفنان
    
    Args:
        artist_name: اسم الفنان
        template_id: معرف القالب
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'auto_processing' not in admin_data['settings']:
            admin_data['settings']['auto_processing'] = {
                'smart_templates': {}
            }
        elif 'smart_templates' not in admin_data['settings']['auto_processing']:
            admin_data['settings']['auto_processing']['smart_templates'] = {}
        
        # إضافة القالب الذكي
        admin_data['settings']['auto_processing']['smart_templates'][artist_name] = template_id
        save_admin_data()
        logger.info(f"تمت إضافة قالب ذكي للفنان: {artist_name} -> {template_id}")
        return True
    except Exception as e:
        logger.error(f"خطأ في إضافة قالب ذكي: {e}")
        return False
        
def remove_smart_template(artist_name: str) -> bool:
    """إزالة قالب ذكي للتعديل التلقائي
    
    Args:
        artist_name: اسم الفنان المراد إزالة قالبه
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if ('auto_processing' in admin_data['settings'] and 
            'smart_templates' in admin_data['settings']['auto_processing'] and
            artist_name in admin_data['settings']['auto_processing']['smart_templates']):
            
            del admin_data['settings']['auto_processing']['smart_templates'][artist_name]
            save_admin_data()
            logger.info(f"تمت إزالة قالب ذكي للفنان: {artist_name}")
            return True
        return False
    except Exception as e:
        logger.error(f"خطأ في إزالة قالب ذكي: {e}")
        return False
        
def set_source_channel(channel_id: str) -> bool:
    """تعيين قناة المصدر للمعالجة التلقائية
    
    Args:
        channel_id: معرف القناة
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'auto_processing' not in admin_data['settings']:
            admin_data['settings']['auto_processing'] = {}
        
        admin_data['settings']['auto_processing']['source_channel'] = channel_id
        save_admin_data()
        logger.info(f"تم تعيين قناة المصدر: {channel_id}")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين قناة المصدر: {e}")
        return False
        
def set_target_channel(channel_id: str) -> bool:
    """تعيين قناة الهدف للنشر التلقائي
    
    Args:
        channel_id: معرف القناة
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'auto_processing' not in admin_data['settings']:
            admin_data['settings']['auto_processing'] = {}
        
        admin_data['settings']['auto_processing']['target_channel'] = channel_id
        save_admin_data()
        logger.info(f"تم تعيين قناة الهدف: {channel_id}")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين قناة الهدف: {e}")
        return False
        
def set_forward_to_target(enabled: bool = True) -> bool:
    """تفعيل/تعطيل النشر التلقائي للقناة الهدف
    
    Args:
        enabled: حالة التفعيل
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'auto_processing' not in admin_data['settings']:
            admin_data['settings']['auto_processing'] = {}
        
        admin_data['settings']['auto_processing']['forward_to_target'] = enabled
        save_admin_data()
        status = "تفعيل" if enabled else "تعطيل"
        logger.info(f"تم {status} النشر التلقائي للقناة الهدف")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين حالة النشر التلقائي للقناة الهدف: {e}")
        return False

def set_tag_footer(footer_text: str) -> bool:
    """تعيين نص التذييل للوسوم
    
    Args:
        footer_text: نص التذييل
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'auto_processing' not in admin_data['settings']:
            admin_data['settings']['auto_processing'] = {}
        
        admin_data['settings']['auto_processing']['tag_footer'] = footer_text
        save_admin_data()
        logger.info(f"تم تعيين نص التذييل: {footer_text}")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين نص التذييل: {e}")
        return False

def set_tag_footer_enabled(enabled: bool = True) -> bool:
    """تفعيل/تعطيل إضافة التذييل للوسوم
    
    Args:
        enabled: حالة التفعيل
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'auto_processing' not in admin_data['settings']:
            admin_data['settings']['auto_processing'] = {}
        
        admin_data['settings']['auto_processing']['footer_enabled'] = enabled
        save_admin_data()
        status = "تفعيل" if enabled else "تعطيل"
        logger.info(f"تم {status} إضافة التذييل للوسوم")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين حالة إضافة التذييل للوسوم: {e}")
        return False

def update_footer_tag_settings(tag_settings: dict) -> bool:
    """تحديث إعدادات الوسوم التي يضاف إليها التذييل
    
    Args:
        tag_settings: قاموس الوسوم وحالاتها {اسم الوسم: True/False}
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'auto_processing' not in admin_data['settings']:
            admin_data['settings']['auto_processing'] = {}
        
        admin_data['settings']['auto_processing']['footer_tag_settings'] = tag_settings
        save_admin_data()
        logger.info(f"تم تحديث إعدادات الوسوم التي يضاف إليها التذييل: {len(tag_settings)} وسم")
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث إعدادات الوسوم التي يضاف إليها التذييل: {e}")
        return False

def update_auto_tags(auto_tags: Dict) -> bool:
    """تحديث الوسوم التلقائية
    
    Args:
        auto_tags: قاموس الوسوم التلقائية
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        admin_data['settings']['auto_tags'] = auto_tags
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث الوسوم التلقائية: {e}")
        return False

def set_audio_watermark(file_path: str, position: str = 'start', volume: float = 0.5) -> bool:
    """تعيين ملف العلامة المائية الصوتية
    
    Args:
        file_path: مسار ملف العلامة المائية
        position: موضع العلامة المائية ('start', 'end')
        volume: مستوى صوت العلامة المائية (0.0-1.0)
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        admin_data['settings']['audio_watermark']['file_path'] = file_path
        admin_data['settings']['audio_watermark']['position'] = position
        admin_data['settings']['audio_watermark']['volume'] = max(0.0, min(1.0, volume))
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين العلامة المائية الصوتية: {e}")
        return False

def enable_audio_watermark(enabled: bool = True) -> bool:
    """تفعيل/تعطيل العلامة المائية الصوتية
    
    Args:
        enabled: حالة التفعيل
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        admin_data['settings']['audio_watermark']['enabled'] = enabled
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تفعيل/تعطيل العلامة المائية الصوتية: {e}")
        return False

def enable_image_watermark(enabled: bool = True) -> bool:
    """تفعيل/تعطيل العلامة المائية للصور
    
    Args:
        enabled: حالة التفعيل
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'image_watermark' not in admin_data['settings']:
            admin_data['settings']['image_watermark'] = {}
        admin_data['settings']['image_watermark']['enabled'] = enabled
        save_admin_data()
        logger.info(f"تم {'تفعيل' if enabled else 'تعطيل'} العلامة المائية للصور")
        return True
    except Exception as e:
        logger.error(f"خطأ في تفعيل/تعطيل العلامة المائية للصور: {e}")
        return False
    
def set_image_watermark(file_path: str) -> bool:
    """تعيين ملف العلامة المائية للصور
    
    Args:
        file_path: مسار ملف العلامة المائية
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        if 'image_watermark' not in admin_data['settings']:
            admin_data['settings']['image_watermark'] = {}
        
        # التحقق من وجود الملف
        if not os.path.exists(file_path):
            logger.error(f"ملف العلامة المائية غير موجود: {file_path}")
            return False
            
        admin_data['settings']['image_watermark']['path'] = file_path
        save_admin_data()
        logger.info(f"تم تعيين ملف العلامة المائية للصور: {file_path}")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين ملف العلامة المائية للصور: {e}")
        return False
        
def set_image_watermark_position(position: str) -> bool:
    """تعيين موضع العلامة المائية للصور
    
    Args:
        position: موضع العلامة المائية (top-left, top-right, bottom-left, bottom-right, center)
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        valid_positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center']
        if position not in valid_positions:
            logger.error(f"موضع غير صالح للعلامة المائية: {position}")
            return False
        
        if 'image_watermark' not in admin_data['settings']:
            admin_data['settings']['image_watermark'] = {}
            
        admin_data['settings']['image_watermark']['position'] = position
        save_admin_data()
        logger.info(f"تم تعيين موضع العلامة المائية للصور: {position}")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين موضع العلامة المائية للصور: {e}")
        return False
    
def set_image_watermark_size(size_percent: int) -> bool:
    """تعيين حجم العلامة المائية للصور
    
    Args:
        size_percent: نسبة حجم العلامة المائية (1-100)
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        # التحقق من صلاحية القيمة
        if not isinstance(size_percent, int) or size_percent < 1 or size_percent > 100:
            logger.error(f"حجم غير صالح للعلامة المائية: {size_percent}")
            return False
        
        if 'image_watermark' not in admin_data['settings']:
            admin_data['settings']['image_watermark'] = {}
            
        admin_data['settings']['image_watermark']['size'] = size_percent
        save_admin_data()
        logger.info(f"تم تعيين حجم العلامة المائية للصور: {size_percent}%")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين حجم العلامة المائية للصور: {e}")
        return False
    
def set_image_watermark_opacity(opacity: float) -> bool:
    """تعيين شفافية العلامة المائية للصور
    
    Args:
        opacity: نسبة الشفافية (0.0-1.0)
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        # التحقق من صلاحية القيمة
        if not isinstance(opacity, (int, float)) or opacity < 0 or opacity > 1:
            logger.error(f"شفافية غير صالحة للعلامة المائية: {opacity}")
            return False
        
        if 'image_watermark' not in admin_data['settings']:
            admin_data['settings']['image_watermark'] = {}
            
        admin_data['settings']['image_watermark']['opacity'] = opacity
        save_admin_data()
        logger.info(f"تم تعيين شفافية العلامة المائية للصور: {opacity}")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين شفافية العلامة المائية للصور: {e}")
        return False
    
def set_image_watermark_padding(padding: int) -> bool:
    """تعيين التباعد من الحافة للعلامة المائية
    
    Args:
        padding: التباعد بالبكسل
    
    Returns:
        bool: نتيجة العملية
    """
    try:
        # التحقق من صلاحية القيمة
        if not isinstance(padding, int) or padding < 0:
            logger.error(f"تباعد غير صالح للعلامة المائية: {padding}")
            return False
        
        if 'image_watermark' not in admin_data['settings']:
            admin_data['settings']['image_watermark'] = {}
            
        admin_data['settings']['image_watermark']['padding'] = padding
        save_admin_data()
        logger.info(f"تم تعيين تباعد العلامة المائية للصور: {padding} بكسل")
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين تباعد العلامة المائية للصور: {e}")
        return False

# تهيئة البيانات عند تحميل الملف
load_admin_data()

# تعريف دالة إرسال سجلات إلى قناة محددة
def send_to_log_channel(message: str, bot=None):
    """إرسال رسالة إلى قناة السجل"""
    log_channel = admin_data['settings'].get('log_channel', "")
    if not log_channel or not bot:
        return False
    
    try:
        bot.send_message(log_channel, message, parse_mode="Markdown")
        return True
    except Exception as e:
        logger.error(f"خطأ في إرسال رسالة إلى قناة السجل: {e}")
        return False

# دالة للتحقق من اشتراك المستخدم في القنوات المطلوبة
def check_subscription(user_id: int, bot) -> Tuple[bool, List[Dict]]:
    """التحقق من اشتراك المستخدم في القنوات المطلوبة
    
    Returns:
        Tuple[bool, List[Dict]]: الاشتراك بنجاح، قائمة القنوات غير المشترك بها
    """
    # التحقق مما إذا كانت ميزة الاشتراك الإجباري مفعّلة
    if not admin_data['settings']['features_enabled'].get('required_subscription', False):
        return True, []
    
    # الحصول على قائمة القنوات المطلوبة
    required_channels = admin_data['settings'].get('required_channels', [])
    if not required_channels:
        return True, []
    
    not_subscribed = []
    for channel in required_channels:
        channel_id = channel.get('channel_id', '')
        if not channel_id:
            continue
        
        try:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(channel)
        except Exception as e:
            logger.error(f"خطأ في التحقق من اشتراك المستخدم {user_id} في القناة {channel_id}: {e}")
            not_subscribed.append(channel)
    
    return len(not_subscribed) == 0, not_subscribed

# دالة تحديث رسالة الترحيب
def update_welcome_message(message: str) -> bool:
    """تحديث رسالة الترحيب"""
    try:
        admin_data['settings']['welcome_message'] = message
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث رسالة الترحيب: {e}")
        return False

# دالة إضافة قناة اشتراك إجباري
def add_required_channel(channel_id: str, title: str) -> bool:
    """إضافة قناة اشتراك إجباري"""
    try:
        # التأكد من أن معرف القناة يبدأ بـ @ إذا كان معرفاً وليس رقماً
        if not channel_id.startswith('@') and not channel_id.startswith('-'):
            channel_id = '@' + channel_id
        
        # التحقق من وجود القناة مسبقاً
        for channel in admin_data['settings'].get('required_channels', []):
            if channel.get('channel_id') == channel_id:
                # تحديث العنوان إذا كان مختلفاً
                if channel.get('title') != title:
                    channel['title'] = title
                    save_admin_data()
                return True
        
        # إضافة القناة إلى القائمة
        if 'required_channels' not in admin_data['settings']:
            admin_data['settings']['required_channels'] = []
        
        admin_data['settings']['required_channels'].append({
            'channel_id': channel_id,
            'title': title
        })
        
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في إضافة قناة اشتراك إجباري: {e}")
        return False

# دالة إزالة قناة اشتراك إجباري
def remove_required_channel(channel_id: str) -> bool:
    """إزالة قناة اشتراك إجباري"""
    try:
        # التأكد من أن معرف القناة يبدأ بـ @ إذا كان معرفاً وليس رقماً
        if not channel_id.startswith('@') and not channel_id.startswith('-'):
            channel_id = '@' + channel_id
        
        # البحث عن القناة وإزالتها
        channels = admin_data['settings'].get('required_channels', [])
        for i, channel in enumerate(channels):
            if channel.get('channel_id') == channel_id:
                channels.pop(i)
                save_admin_data()
                return True
        
        return False
    except Exception as e:
        logger.error(f"خطأ في إزالة قناة اشتراك إجباري: {e}")
        return False

# دالة تعيين قناة السجل
def set_log_channel(channel_id: str) -> bool:
    """تعيين قناة السجل"""
    try:
        # التأكد من أن معرف القناة يبدأ بـ @ إذا كان معرفاً وليس رقماً
        if channel_id and not channel_id.startswith('@') and not channel_id.startswith('-'):
            channel_id = '@' + channel_id
        
        admin_data['settings']['log_channel'] = channel_id
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين قناة السجل: {e}")
        return False

# دالة تعيين وقت التأخير بين تعديل كل ملف
def set_processing_delay(delay_seconds: int) -> bool:
    """تعيين وقت التأخير بين تعديل كل ملف"""
    try:
        admin_data['settings']['processing_delay'] = max(0, delay_seconds)
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين وقت التأخير: {e}")
        return False

# دالة تعيين حد البيانات اليومي لكل مستخدم
def set_daily_user_limit(limit_mb: int) -> bool:
    """تعيين حد البيانات اليومي لكل مستخدم بالميجابايت"""
    try:
        admin_data['settings']['daily_user_limit_mb'] = max(0, limit_mb)
        save_admin_data()
        return True
    except Exception as e:
        logger.error(f"خطأ في تعيين حد البيانات اليومي: {e}")
        return False

# دالة التحقق من تجاوز المستخدم للحد اليومي
def check_user_limit(user_id: int, file_size_mb: float) -> bool:
    """التحقق من تجاوز المستخدم للحد اليومي
    
    Returns:
        bool: True إذا كان المستخدم ضمن الحد المسموح، False إذا تجاوز الحد
    """
    user_limit = admin_data['settings'].get('daily_user_limit_mb', 0)
    if user_limit <= 0:
        return True  # عدم وجود حد
    
    user_id_str = str(user_id)
    if user_id_str not in admin_data['users']:
        return True  # مستخدم جديد
    
    user_data = admin_data['users'][user_id_str]
    daily_usage = user_data.get('daily_usage', 0)
    
    # التحقق من إعادة تعيين العداد اليومي
    now = time.time()
    daily_reset_time = user_data.get('daily_reset', 0)
    if now - daily_reset_time > 86400:  # 24 ساعة
        user_data['daily_usage'] = 0
        user_data['daily_reset'] = now
        daily_usage = 0
        save_admin_data()
    
    # التحقق من الحد
    return daily_usage + file_size_mb <= user_limit

# دوال العلامة المائية للصور
def enable_image_watermark(enable=True):
    """تفعيل أو تعطيل العلامة المائية للصور"""
    try:
        admin_data['settings'].setdefault('image_watermark', {})
        admin_data['settings']['image_watermark']['enabled'] = enable
        save_admin_data()
        logger.info(f"تم {'تفعيل' if enable else 'تعطيل'} العلامة المائية للصور")
        return True
    except Exception as e:
        logger.error(f"خطأ أثناء تفعيل/تعطيل العلامة المائية: {e}")
        return False

def set_image_watermark_position(position):
    """تعيين موضع العلامة المائية"""
    try:
        admin_data['settings'].setdefault('image_watermark', {})
        admin_data['settings']['image_watermark']['position'] = position
        save_admin_data()
        logger.info(f"تم تعيين موضع العلامة المائية إلى: {position}")
        return True
    except Exception as e:
        logger.error(f"خطأ أثناء تعيين موضع العلامة المائية: {e}")
        return False
        
def set_image_watermark_size(size):
    """تعيين حجم العلامة المائية (1-100)"""
    try:
        size = int(size)
        if size < 1 or size > 100:
            return False
            
        admin_data['settings'].setdefault('image_watermark', {})
        admin_data['settings']['image_watermark']['size'] = size
        save_admin_data()
        logger.info(f"تم تعيين حجم العلامة المائية إلى: {size}%")
        return True
    except Exception as e:
        logger.error(f"خطأ أثناء تعيين حجم العلامة المائية: {e}")
        return False
        
def set_image_watermark_opacity(opacity):
    """تعيين شفافية العلامة المائية (1-100)"""
    try:
        opacity = int(opacity)
        if opacity < 1 or opacity > 100:
            return False
            
        admin_data['settings'].setdefault('image_watermark', {})
        admin_data['settings']['image_watermark']['opacity'] = opacity
        save_admin_data()
        logger.info(f"تم تعيين شفافية العلامة المائية إلى: {opacity}%")
        return True
    except Exception as e:
        logger.error(f"خطأ أثناء تعيين شفافية العلامة المائية: {e}")
        return False
        
def set_image_watermark_padding(padding):
    """تعيين تباعد العلامة المائية من الحافة (1-100)"""
    try:
        padding = int(padding)
        if padding < 1 or padding > 100:
            return False
            
        admin_data['settings'].setdefault('image_watermark', {})
        admin_data['settings']['image_watermark']['padding'] = padding
        save_admin_data()
        logger.info(f"تم تعيين تباعد العلامة المائية إلى: {padding} بكسل")
        return True
    except Exception as e:
        logger.error(f"خطأ أثناء تعيين تباعد العلامة المائية: {e}")
        return False
        
def save_image_watermark(image_path):
    """حفظ صورة العلامة المائية"""
    try:
        import os
        import base64
        
        # التأكد من وجود الصورة
        if not os.path.exists(image_path):
            return False
            
        # فتح الصورة وتحويلها إلى base64
        with open(image_path, 'rb') as f:
            image_data = f.read()
            
        # حفظ البيانات كـ base64 string
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        admin_data['settings'].setdefault('image_watermark', {})
        admin_data['settings']['image_watermark']['image'] = image_base64
        
        # حفظ نوع الصورة (امتدادها)
        _, ext = os.path.splitext(image_path)
        admin_data['settings']['image_watermark']['format'] = ext.lower().replace('.', '')
        
        save_admin_data()
        logger.info(f"تم حفظ صورة العلامة المائية بنجاح")
        return True
    except Exception as e:
        logger.error(f"خطأ أثناء حفظ صورة العلامة المائية: {e}")
        return False

# إضافة حساب بمعرّف 1234567890 كمشرف إذا لم تكن هناك مشرفين (للتجربة)
if not admin_data['admins']:
    admin_data['admins'].add(1174919068)  # هذا مجرد مثال، يمكن تغييره

# وظائف إدارة القوالب العامة
def add_global_template(template_name: str, template_data: dict) -> bool:
    """
    إضافة قالب عام جديد أو تحديث قالب موجود
    
    Args:
        template_name: اسم القالب
        template_data: بيانات القالب (وسوم وقيمها)
        
    Returns:
        bool: True إذا تمت الإضافة بنجاح، False خلاف ذلك
    """
    try:
        # إضافة مفتاح global_templates إذا لم يكن موجوداً
        if 'global_templates' not in admin_data:
            admin_data['global_templates'] = {}
            
        # إضافة القالب إلى القوالب العامة
        admin_data['global_templates'][template_name] = template_data
        
        # حفظ البيانات
        save_admin_data()
        
        logger.info(f"تمت إضافة/تحديث القالب العام '{template_name}' بنجاح - عدد الوسوم: {len(template_data)}")
        return True
    except Exception as e:
        logger.error(f"حدث خطأ أثناء إضافة القالب العام '{template_name}': {str(e)}")
        return False

def delete_global_template(template_name: str) -> bool:
    """
    حذف قالب عام موجود
    
    Args:
        template_name: اسم القالب المراد حذفه
        
    Returns:
        bool: True إذا تم الحذف بنجاح، False خلاف ذلك
    """
    try:
        # التحقق من وجود global_templates في البيانات
        if 'global_templates' not in admin_data:
            return False
            
        # التحقق من وجود القالب
        if template_name in admin_data['global_templates']:
            # حذف القالب
            del admin_data['global_templates'][template_name]
            
            # حفظ البيانات
            save_admin_data()
            
            logger.info(f"تم حذف القالب العام '{template_name}' بنجاح")
            return True
        else:
            logger.warning(f"لم يتم العثور على القالب العام '{template_name}' للحذف")
            return False
    except Exception as e:
        logger.error(f"حدث خطأ أثناء حذف القالب العام '{template_name}': {str(e)}")
        return False

def get_global_templates() -> dict:
    """
    الحصول على جميع القوالب العامة
    
    Returns:
        dict: قاموس يحتوي على جميع القوالب العامة {template_name: template_data, ...}
    """
    return admin_data.get('global_templates', {})
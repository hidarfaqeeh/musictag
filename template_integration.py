"""
وحدة التكامل بين قوالب المستخدم ونظام البوت
تعمل هذه الوحدة كواجهة بين نظام البوت وقوالب المستخدم المخزنة في قاعدة البيانات
"""

import logging
import os
from typing import Dict, List, Optional, Tuple, Any

# استيراد وحدات التعامل مع القوالب
import template_handler
import user_template_handler
from models import db, User, UserTemplate

logger = logging.getLogger(__name__)

def save_template(user_id: int, template_name: str, tags: Dict, album_art=None, album_art_mime=None) -> bool:
    """
    حفظ قالب للمستخدم
    
    Args:
        user_id: معرف المستخدم
        template_name: اسم القالب
        tags: قاموس يحتوي على الوسوم
        album_art: بيانات صورة الألبوم (اختياري)
        album_art_mime: نوع ملف صورة الألبوم (اختياري)
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        # استخراج اسم الفنان من الوسوم
        artist_name = extract_artist_from_tags(tags)
        
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        result = user_template_handler.save_user_template(
            user_id=user_id,
            template_name=template_name,
            artist_name=artist_name,
            tags=tags,
            album_art=album_art,
            album_art_mime=album_art_mime
        )
        
        logger.info(f"تم حفظ قالب للمستخدم {user_id} باسم {template_name} للفنان {artist_name}")
        return result
    except Exception as e:
        logger.error(f"خطأ في حفظ قالب المستخدم: {e}")
        return False

def get_template(user_id: int, template_id: int) -> Optional[Dict]:
    """
    استرجاع قالب للمستخدم
    
    Args:
        user_id: معرف المستخدم
        template_id: معرف القالب
        
    Returns:
        Optional[Dict]: بيانات القالب أو None إذا لم يتم العثور عليه
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.get_user_template(user_id, template_id)
    except Exception as e:
        logger.error(f"خطأ في استرجاع قالب المستخدم: {e}")
        return None

def get_artists_with_templates(user_id: int) -> List[str]:
    """
    استرجاع قائمة بالفنانين الذين لديهم قوالب للمستخدم
    
    Args:
        user_id: معرف المستخدم
        
    Returns:
        List[str]: قائمة بأسماء الفنانين
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.get_user_artists_with_templates(user_id)
    except Exception as e:
        logger.error(f"خطأ في استرجاع قائمة الفنانين للمستخدم: {e}")
        return []

def list_templates(user_id: int, filter_artist: str = None) -> List[Dict]:
    """
    استرجاع قائمة بقوالب المستخدم
    
    Args:
        user_id: معرف المستخدم
        filter_artist: تصفية النتائج حسب الفنان (اختياري)
        
    Returns:
        List[Dict]: قائمة بمعلومات القوالب
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.list_user_templates(user_id, filter_artist)
    except Exception as e:
        logger.error(f"خطأ في استرجاع قائمة قوالب المستخدم: {e}")
        return []

def delete_template(user_id: int, template_id: int) -> bool:
    """
    حذف قالب للمستخدم
    
    Args:
        user_id: معرف المستخدم
        template_id: معرف القالب
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.delete_user_template(user_id, template_id)
    except Exception as e:
        logger.error(f"خطأ في حذف قالب المستخدم: {e}")
        return False

def extract_artist_from_tags(tags: Dict) -> str:
    """
    استخراج اسم الفنان من الوسوم
    
    Args:
        tags: قاموس الوسوم
        
    Returns:
        str: اسم الفنان أو "عام" إذا لم يتم العثور على الفنان
    """
    # استخدام دالة من وحدة user_template_handler
    return user_template_handler.extract_artist_from_tags(tags)

def get_all_templates(user_id: int) -> List[Dict]:
    """
    استرجاع جميع قوالب المستخدم
    
    Args:
        user_id: معرف المستخدم
        
    Returns:
        List[Dict]: قائمة بجميع قوالب المستخدم
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.get_all_user_templates(user_id)
    except Exception as e:
        logger.error(f"خطأ في استرجاع جميع قوالب المستخدم: {e}")
        return []

def export_templates(user_id: int) -> Tuple[str, int]:
    """
    تصدير قوالب المستخدم إلى ملف
    
    Args:
        user_id: معرف المستخدم
        
    Returns:
        Tuple[str, int]: مسار ملف التصدير، عدد القوالب المصدرة
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.export_user_templates(user_id)
    except Exception as e:
        logger.error(f"خطأ في تصدير قوالب المستخدم: {e}")
        return None, 0

def import_templates(user_id: int, zip_path: str) -> Tuple[bool, int]:
    """
    استيراد قوالب للمستخدم من ملف
    
    Args:
        user_id: معرف المستخدم
        zip_path: مسار ملف الاستيراد
        
    Returns:
        Tuple[bool, int]: نتيجة العملية، عدد القوالب المستوردة
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.import_user_templates(user_id, zip_path)
    except Exception as e:
        logger.error(f"خطأ في استيراد قوالب المستخدم: {e}")
        return False, 0

def share_template(user_id: int, template_id: int, make_public: bool = True) -> bool:
    """
    مشاركة قالب المستخدم أو جعله خاصاً
    
    Args:
        user_id: معرف المستخدم
        template_id: معرف القالب
        make_public: جعل القالب عام (True) أو خاص (False)
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.share_template(user_id, template_id, make_public)
    except Exception as e:
        logger.error(f"خطأ في تغيير حالة مشاركة القالب: {e}")
        return False

def list_public_templates(filter_artist: str = None) -> List[Dict]:
    """
    استرجاع قائمة بالقوالب العامة
    
    Args:
        filter_artist: تصفية النتائج حسب الفنان (اختياري)
        
    Returns:
        List[Dict]: قائمة بالقوالب العامة
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.list_public_templates(filter_artist)
    except Exception as e:
        logger.error(f"خطأ في استرجاع قائمة القوالب العامة: {e}")
        return []

def copy_public_template(template_id: int, user_id: int, new_template_name: str = None) -> bool:
    """
    نسخ قالب عام إلى مستخدم
    
    Args:
        template_id: معرف القالب العام
        user_id: معرف المستخدم المستهدف
        new_template_name: اسم جديد للقالب (اختياري)
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.copy_public_template_to_user(template_id, user_id, new_template_name)
    except Exception as e:
        logger.error(f"خطأ في نسخ القالب العام إلى المستخدم: {e}")
        return False

def get_template_by_name(user_id: int, template_name: str) -> Optional[Dict]:
    """
    استرجاع قالب للمستخدم حسب الاسم
    
    Args:
        user_id: معرف المستخدم
        template_name: اسم القالب
        
    Returns:
        Optional[Dict]: بيانات القالب أو None إذا لم يتم العثور عليه
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        return user_template_handler.get_user_template_by_name(user_id, template_name)
    except Exception as e:
        logger.error(f"خطأ في استرجاع قالب المستخدم حسب الاسم: {e}")
        return None

def get_template_list(user_id: int) -> Dict[str, str]:
    """
    استرجاع قاموس بمعرفات وأسماء قوالب المستخدم
    
    Args:
        user_id: معرف المستخدم
        
    Returns:
        Dict[str, str]: قاموس بمعرفات القوالب وأسمائها {معرف_القالب: اسم_القالب}
    """
    try:
        # استخدام نظام قوالب المستخدم في قاعدة البيانات
        templates = user_template_handler.list_user_templates(user_id)
        
        # تحويل القائمة إلى قاموس بالمعرفات والأسماء
        template_dict = {str(template['id']): template['name'] for template in templates}
        return template_dict
    except Exception as e:
        logger.error(f"خطأ في استرجاع قائمة قوالب المستخدم: {e}")
        return {}

# دوال المساعدة للتكامل مع ملفات القوالب القديمة والتحويل للنظام الجديد

def migrate_template_files_to_db() -> Tuple[int, int]:
    """
    ترحيل القوالب من نظام الملفات إلى قاعدة البيانات
    
    Returns:
        Tuple[int, int]: عدد القوالب التي تم ترحيلها، عدد القوالب التي فشل ترحيلها
    """
    try:
        # التأكد من وجود مجلد القوالب
        if not os.path.exists(template_handler.TEMPLATES_DIR):
            logger.warning(f"مجلد القوالب غير موجود: {template_handler.TEMPLATES_DIR}")
            return 0, 0
            
        # الحصول على قائمة ملفات القوالب
        template_files = [f for f in os.listdir(template_handler.TEMPLATES_DIR) if f.endswith('.json')]
        if not template_files:
            logger.info("لا توجد قوالب لترحيلها")
            return 0, 0
            
        # الحصول على المستخدم الافتراضي (المشرف الأول)
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            logger.error("لم يتم العثور على مشرف لترحيل القوالب إليه")
            return 0, 0
            
        admin_id = admin.id
        migrated = 0
        failed = 0
        
        # ترحيل كل قالب
        for file_name in template_files:
            try:
                # استرجاع بيانات القالب
                template_id = file_name[:-5]  # إزالة .json
                template_data = template_handler.get_template(template_id)
                
                if not template_data:
                    logger.warning(f"فشل في قراءة بيانات القالب: {template_id}")
                    failed += 1
                    continue
                    
                # استخراج البيانات
                template_name = template_data.get('name', template_id)
                artist_name = template_data.get('artist', 'عام')
                tags = template_data.get('tags', {})
                
                # معالجة صورة الألبوم إن وجدت
                album_art = None
                album_art_mime = None
                if 'album_art' in template_data:
                    album_art = template_data.get('album_art')
                    album_art_mime = template_data.get('album_art_mime', 'image/jpeg')
                
                # حفظ القالب في النظام الجديد
                if user_template_handler.save_user_template(
                    admin_id, template_name, artist_name, tags, album_art, album_art_mime
                ):
                    migrated += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"خطأ في ترحيل القالب {file_name}: {e}")
                failed += 1
                continue
                
        logger.info(f"تم ترحيل {migrated} قالب بنجاح، فشل في ترحيل {failed} قالب")
        return migrated, failed
        
    except Exception as e:
        logger.error(f"خطأ في ترحيل القوالب: {e}")
        return 0, 0
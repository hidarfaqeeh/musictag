"""
وحدة التعامل مع قوالب المستخدم الخاصة باستخدام قاعدة البيانات
"""

import os
import json
import base64
import logging
import shutil
import zipfile
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime

from models import db, User, UserTemplate

# إعداد التسجيل
logger = logging.getLogger(__name__)

def save_user_template(user_id: int, template_name: str, artist_name: str, tags: Dict, album_art=None, album_art_mime=None) -> bool:
    """
    حفظ قالب جديد لمستخدم محدد مع الوسوم وصورة الألبوم (إن وجدت)
    
    Args:
        user_id: معرف المستخدم
        template_name: اسم القالب
        artist_name: اسم الفنان الذي ينتمي إليه القالب
        tags: قاموس يحتوي على الوسوم
        album_art: بيانات صورة الألبوم (اختياري)
        album_art_mime: نوع ملف صورة الألبوم (اختياري)
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        # البحث عن المستخدم
        user = User.query.get(user_id)
        if not user:
            logger.error(f"المستخدم غير موجود: {user_id}")
            return False
        
        # البحث عن قالب موجود بنفس الاسم للمستخدم
        existing_template = UserTemplate.query.filter_by(
            user_id=user_id, 
            template_name=template_name
        ).first()
        
        if existing_template:
            # تحديث القالب الموجود
            existing_template.artist_name = artist_name
            existing_template.set_tags(tags)
            existing_template.updated_at = datetime.utcnow()
            
            # تحديث صورة الألبوم إن وجدت
            if album_art and album_art_mime:
                existing_template.album_art = album_art
                existing_template.album_art_mime = album_art_mime
                
            db.session.commit()
            logger.info(f"تم تحديث القالب: {template_name} للمستخدم {user_id}")
            return True
        else:
            # إنشاء قالب جديد
            new_template = UserTemplate(
                user_id=user_id,
                template_name=template_name,
                artist_name=artist_name,
                album_art=album_art,
                album_art_mime=album_art_mime
            )
            new_template.set_tags(tags)
            
            db.session.add(new_template)
            db.session.commit()
            logger.info(f"تم إنشاء قالب جديد: {template_name} للمستخدم {user_id}")
            return True
            
    except Exception as e:
        logger.error(f"خطأ في حفظ قالب المستخدم: {e}")
        db.session.rollback()
        return False

def get_user_template(user_id: int, template_id: int) -> Optional[Dict]:
    """
    استرجاع قالب موجود لمستخدم محدد
    
    Args:
        user_id: معرف المستخدم
        template_id: معرف القالب
        
    Returns:
        dict: قاموس يحتوي على بيانات القالب أو None في حالة عدم وجود القالب
    """
    try:
        template = UserTemplate.query.filter_by(
            user_id=user_id,
            id=template_id
        ).first()
        
        if not template:
            return None
            
        result = {
            'id': template.id,
            'name': template.template_name,
            'artist': template.artist_name,
            'tags': template.get_tags(),
            'created_at': template.created_at,
            'updated_at': template.updated_at
        }
        
        # إضافة صورة الألبوم إن وجدت
        if template.album_art and template.album_art_mime:
            result['album_art'] = template.album_art
            result['album_art_mime'] = template.album_art_mime
            
        return result
        
    except Exception as e:
        logger.error(f"خطأ في استرجاع قالب المستخدم: {e}")
        return None

def get_user_template_by_name(user_id: int, template_name: str) -> Optional[Dict]:
    """
    استرجاع قالب موجود لمستخدم محدد حسب الاسم
    
    Args:
        user_id: معرف المستخدم
        template_name: اسم القالب
        
    Returns:
        dict: قاموس يحتوي على بيانات القالب أو None في حالة عدم وجود القالب
    """
    try:
        template = UserTemplate.query.filter_by(
            user_id=user_id,
            template_name=template_name
        ).first()
        
        if not template:
            return None
            
        result = {
            'id': template.id,
            'name': template.template_name,
            'artist': template.artist_name,
            'tags': template.get_tags(),
            'created_at': template.created_at,
            'updated_at': template.updated_at
        }
        
        # إضافة صورة الألبوم إن وجدت
        if template.album_art and template.album_art_mime:
            result['album_art'] = template.album_art
            result['album_art_mime'] = template.album_art_mime
            
        return result
        
    except Exception as e:
        logger.error(f"خطأ في استرجاع قالب المستخدم حسب الاسم: {e}")
        return None

def list_user_templates(user_id: int, filter_artist: str = None) -> List[Dict]:
    """
    استرجاع قائمة بجميع قوالب المستخدم المحدد
    
    Args:
        user_id: معرف المستخدم
        filter_artist: تصفية النتائج حسب الفنان (اختياري)
        
    Returns:
        list: قائمة بأسماء القوالب ومعلوماتها
    """
    try:
        # إنشاء الاستعلام الأساسي
        query = UserTemplate.query.filter_by(user_id=user_id)
        
        # إضافة تصفية حسب الفنان إذا تم تحديده
        if filter_artist:
            query = query.filter(UserTemplate.artist_name.ilike(f"%{filter_artist}%"))
            
        # تنفيذ الاستعلام
        templates = query.all()
        
        result = []
        for template in templates:
            template_info = {
                'id': template.id,
                'name': template.template_name,
                'artist': template.artist_name,
                'has_image': template.album_art is not None,
                'updated_at': template.updated_at
            }
            result.append(template_info)
            
        # ترتيب القوالب حسب الفنان ثم الاسم
        result.sort(key=lambda x: (x["artist"], x["name"]))
        
        return result
        
    except Exception as e:
        logger.error(f"خطأ في استرجاع قائمة قوالب المستخدم: {e}")
        return []

def get_user_artists_with_templates(user_id: int) -> List[str]:
    """
    استرجاع قائمة بجميع الفنانين الذين لديهم قوالب للمستخدم المحدد
    
    Args:
        user_id: معرف المستخدم
        
    Returns:
        list: قائمة بأسماء الفنانين
    """
    try:
        # استخدام distinct للحصول على أسماء الفنانين الفريدة
        artists = db.session.query(UserTemplate.artist_name).filter_by(
            user_id=user_id
        ).distinct().all()
        
        # تحويل النتائج إلى قائمة أسماء
        artists_list = [artist[0] for artist in artists]
        
        # ترتيب الفنانين أبجدياً مع وضع "عام" في الأعلى
        artists_list = sorted(artists_list)
        if "عام" in artists_list:
            artists_list.remove("عام")
            artists_list.insert(0, "عام")
        
        return artists_list
        
    except Exception as e:
        logger.error(f"خطأ في استرجاع قائمة الفنانين للمستخدم: {e}")
        return []

def delete_user_template(user_id: int, template_id: int) -> bool:
    """
    حذف قالب موجود لمستخدم محدد
    
    Args:
        user_id: معرف المستخدم
        template_id: معرف القالب
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        template = UserTemplate.query.filter_by(
            user_id=user_id,
            id=template_id
        ).first()
        
        if not template:
            logger.warning(f"لم يتم العثور على القالب {template_id} للمستخدم {user_id}")
            return False
            
        db.session.delete(template)
        db.session.commit()
        logger.info(f"تم حذف القالب {template.template_name} للمستخدم {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"خطأ في حذف قالب المستخدم: {e}")
        db.session.rollback()
        return False

def extract_artist_from_tags(tags: Dict) -> str:
    """
    استخراج اسم الفنان من الوسوم
    
    Args:
        tags: قاموس الوسوم
        
    Returns:
        str: اسم الفنان أو "عام" إذا لم يتم العثور على الفنان
    """
    # محاولة البحث عن اسم الفنان من وسوم الملف
    artist = tags.get("artist") or tags.get("album_artist") or "عام"
    return artist

def get_all_user_templates(user_id: int) -> List[Dict]:
    """
    الحصول على جميع قوالب المستخدم المحدد
    
    Args:
        user_id: معرف المستخدم
        
    Returns:
        list: قائمة بجميع قوالب المستخدم المحدد
    """
    try:
        templates = UserTemplate.query.filter_by(user_id=user_id).all()
        
        result = []
        for template in templates:
            template_data = {
                'id': template.id,
                'name': template.template_name,
                'artist': template.artist_name,
                'tags': template.get_tags(),
                'created_at': template.created_at,
                'updated_at': template.updated_at
            }
            result.append(template_data)
            
        # ترتيب القوالب حسب اسم الفنان ثم اسم القالب
        result.sort(key=lambda x: (x.get('artist', 'عام'), x.get('name', '')))
        
        return result
        
    except Exception as e:
        logger.error(f"خطأ في استرجاع جميع قوالب المستخدم: {e}")
        return []

def export_user_templates(user_id: int, export_dir='templates_export') -> Tuple[str, int]:
    """
    تصدير جميع قوالب المستخدم المحدد إلى ملف مضغوط
    
    Args:
        user_id: معرف المستخدم
        export_dir: مسار مجلد التصدير
        
    Returns:
        tuple: (مسار ملف التصدير، عدد القوالب المصدرة)
    """
    try:
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = int(time.time())
        zip_filename = f"user_{user_id}_templates_backup_{timestamp}.zip"
        zip_path = os.path.join(export_dir, zip_filename)
        
        templates = UserTemplate.query.filter_by(user_id=user_id).all()
        template_count = 0
        
        # إنشاء ملف مؤقت للتصدير
        temp_dir = os.path.join(export_dir, f"temp_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for template in templates:
                # إنشاء اسم الملف المؤقت
                sanitized_artist = template.artist_name.replace(" ", "_").replace("/", "_").lower()
                sanitized_name = template.template_name.replace(" ", "_").replace("/", "_").lower()
                temp_filename = f"{sanitized_artist}_{sanitized_name}.json"
                temp_filepath = os.path.join(temp_dir, temp_filename)
                
                # إنشاء بيانات القالب
                template_data = {
                    "name": template.template_name,
                    "artist": template.artist_name,
                    "tags": template.get_tags()
                }
                
                # إضافة صورة الألبوم إن وجدت
                if template.album_art and template.album_art_mime:
                    encoded_art = base64.b64encode(template.album_art).decode('utf-8')
                    template_data["album_art"] = encoded_art
                    template_data["album_art_mime"] = template.album_art_mime
                
                # حفظ البيانات في الملف المؤقت
                with open(temp_filepath, 'w', encoding='utf-8') as f:
                    json.dump(template_data, f, ensure_ascii=False, indent=2)
                
                # إضافة الملف المؤقت إلى الأرشيف
                zipf.write(temp_filepath, os.path.basename(temp_filepath))
                template_count += 1
                
        # تنظيف المجلد المؤقت
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        logger.info(f"تم تصدير {template_count} قالب للمستخدم {user_id} إلى {zip_path}")
        return zip_path, template_count
        
    except Exception as e:
        logger.error(f"خطأ في تصدير قوالب المستخدم: {e}")
        return None, 0

def import_user_templates(user_id: int, zip_path: str) -> Tuple[bool, int]:
    """
    استيراد قوالب للمستخدم المحدد من ملف مضغوط
    
    Args:
        user_id: معرف المستخدم
        zip_path: مسار الملف المضغوط
    
    Returns:
        tuple: (نجاح العملية، عدد القوالب المستوردة)
    """
    try:
        if not os.path.exists(zip_path):
            logger.error(f"ملف القوالب غير موجود: {zip_path}")
            return False, 0
            
        # إنشاء مجلد مؤقت للاستيراد
        timestamp = int(time.time())
        temp_dir = os.path.join(os.path.dirname(zip_path), f"temp_import_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)
        
        imported_count = 0
        
        # استخراج الملفات
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # استيراد القوالب
        for file in os.listdir(temp_dir):
            if file.endswith('.json'):
                try:
                    file_path = os.path.join(temp_dir, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    
                    # استخراج البيانات
                    template_name = template_data.get('name')
                    artist_name = template_data.get('artist', 'عام')
                    tags = template_data.get('tags', {})
                    
                    # معالجة صورة الألبوم إن وجدت
                    album_art = None
                    album_art_mime = None
                    if 'album_art' in template_data and 'album_art_mime' in template_data:
                        album_art = base64.b64decode(template_data['album_art'])
                        album_art_mime = template_data['album_art_mime']
                    
                    # حفظ القالب
                    if template_name and tags:
                        if save_user_template(user_id, template_name, artist_name, tags, album_art, album_art_mime):
                            imported_count += 1
                            
                except Exception as e:
                    logger.error(f"خطأ في استيراد القالب {file}: {e}")
                    continue
        
        # تنظيف المجلد المؤقت
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        logger.info(f"تم استيراد {imported_count} قالب للمستخدم {user_id}")
        return True, imported_count
        
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
        template = UserTemplate.query.filter_by(
            user_id=user_id,
            id=template_id
        ).first()
        
        if not template:
            logger.warning(f"لم يتم العثور على القالب {template_id} للمستخدم {user_id}")
            return False
            
        template.is_public = make_public
        db.session.commit()
        
        status = "عام" if make_public else "خاص"
        logger.info(f"تم تغيير حالة القالب {template.template_name} للمستخدم {user_id} إلى {status}")
        return True
        
    except Exception as e:
        logger.error(f"خطأ في تغيير حالة مشاركة القالب: {e}")
        db.session.rollback()
        return False

def list_public_templates(filter_artist: str = None) -> List[Dict]:
    """
    استرجاع قائمة بجميع القوالب العامة
    
    Args:
        filter_artist: تصفية النتائج حسب الفنان (اختياري)
        
    Returns:
        list: قائمة بالقوالب العامة
    """
    try:
        # إنشاء الاستعلام الأساسي
        query = UserTemplate.query.filter_by(is_public=True)
        
        # إضافة تصفية حسب الفنان إذا تم تحديده
        if filter_artist:
            query = query.filter(UserTemplate.artist_name.ilike(f"%{filter_artist}%"))
            
        # تنفيذ الاستعلام
        templates = query.all()
        
        result = []
        for template in templates:
            user = User.query.get(template.user_id)
            username = user.username if user else "مستخدم غير معروف"
            
            template_info = {
                'id': template.id,
                'name': template.template_name,
                'artist': template.artist_name,
                'has_image': template.album_art is not None,
                'owner_id': template.user_id,
                'owner_username': username,
                'updated_at': template.updated_at
            }
            result.append(template_info)
            
        # ترتيب القوالب حسب الفنان ثم الاسم
        result.sort(key=lambda x: (x["artist"], x["name"]))
        
        return result
        
    except Exception as e:
        logger.error(f"خطأ في استرجاع قائمة القوالب العامة: {e}")
        return []

def copy_public_template_to_user(template_id: int, user_id: int, new_template_name: str = None) -> bool:
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
        # البحث عن القالب العام
        template = UserTemplate.query.filter_by(
            id=template_id,
            is_public=True
        ).first()
        
        if not template:
            logger.warning(f"لم يتم العثور على القالب العام {template_id}")
            return False
            
        # تعيين اسم جديد للقالب أو استخدام الاسم الحالي
        template_name = new_template_name or template.template_name
        
        # نسخ القالب إلى المستخدم المستهدف
        new_template = UserTemplate(
            user_id=user_id,
            template_name=template_name,
            artist_name=template.artist_name,
            album_art=template.album_art,
            album_art_mime=template.album_art_mime,
            is_public=False  # جعل النسخة خاصة افتراضياً
        )
        new_template.set_tags(template.get_tags())
        
        db.session.add(new_template)
        db.session.commit()
        
        logger.info(f"تم نسخ القالب العام {template.template_name} إلى المستخدم {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"خطأ في نسخ القالب العام إلى المستخدم: {e}")
        db.session.rollback()
        return False
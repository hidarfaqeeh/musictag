import os
import json
import base64
import logging
import shutil
import zipfile
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

# إعداد التسجيل
logger = logging.getLogger(__name__)

# الدليل الذي سيتم تخزين القوالب فيه
TEMPLATES_DIR = "templates"

def ensure_templates_dir():
    """التأكد من وجود دليل القوالب"""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

def save_template(template_name, artist_name, tags, album_art=None, album_art_mime=None):
    """
    حفظ قالب جديد مع الوسوم وصورة الألبوم (إن وجدت)
    
    Args:
        template_name: اسم القالب
        artist_name: اسم الفنان الذي ينتمي إليه القالب (يمكن أن يكون "عام" للقوالب العامة)
        tags: قاموس يحتوي على الوسوم
        album_art: بيانات صورة الألبوم (اختياري)
        album_art_mime: نوع ملف صورة الألبوم (اختياري)
        
    Returns:
        bool: نتيجة العملية
    """
    ensure_templates_dir()
    
    # إنشاء قاموس البيانات
    template_data = {
        "name": template_name,
        "artist": artist_name,
        "tags": tags
    }
    
    # إضافة صورة الألبوم إن وجدت
    if album_art and album_art_mime:
        # تحويل البيانات الثنائية إلى نص base64
        encoded_art = base64.b64encode(album_art).decode('utf-8')
        template_data["album_art"] = encoded_art
        template_data["album_art_mime"] = album_art_mime
    
    # إنشاء اسم الملف باستخدام الفنان واسم القالب
    # استخدام اسم الفنان في اسم الملف للفرز والتنظيم بشكل أفضل
    sanitized_artist = artist_name.replace(" ", "_").replace("/", "_").lower()
    sanitized_name = template_name.replace(" ", "_").replace("/", "_").lower()
    file_name = f"{sanitized_artist}_{sanitized_name}.json"
    
    # حفظ البيانات في ملف
    file_path = os.path.join(TEMPLATES_DIR, file_name)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
        logger.info(f"تم حفظ القالب: {template_name} للفنان {artist_name}")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ القالب: {e}")
        return False

def get_template(template_id):
    """
    استرجاع قالب موجود باستخدام معرف القالب
    
    Args:
        template_id: معرف القالب (اسم الملف بدون .json)
        
    Returns:
        dict: قاموس يحتوي على بيانات القالب أو None في حالة عدم وجود القالب
    """
    file_path = os.path.join(TEMPLATES_DIR, f"{template_id}.json")
    if not os.path.exists(file_path):
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
            
        # تحويل صورة الألبوم من base64 إلى بيانات ثنائية
        if "album_art" in template_data:
            template_data["album_art"] = base64.b64decode(template_data["album_art"])
            
        return template_data
    except Exception as e:
        logger.error(f"خطأ في قراءة القالب: {e}")
        return None

def get_template_list():
    """
    الحصول على قاموس يحتوي على معرفات وأسماء القوالب المتاحة
    
    Returns:
        Dict[str, str]: قاموس بمعرفات القوالب وأسمائها {معرف_القالب: اسم_القالب}
    """
    ensure_templates_dir()
    
    templates_dict = {}
    for file in os.listdir(TEMPLATES_DIR):
        if file.endswith('.json'):
            try:
                with open(os.path.join(TEMPLATES_DIR, file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    template_id = file[:-5]
                    template_name = data.get("name", "قالب بدون اسم")
                    templates_dict[template_id] = template_name
            except Exception as e:
                logger.error(f"خطأ في قراءة معلومات القالب {file}: {e}")
    
    return templates_dict

def list_templates(filter_artist=None):
    """
    استرجاع قائمة بجميع القوالب المتاحة
    
    Args:
        filter_artist: تصفية النتائج حسب الفنان (اختياري)
        
    Returns:
        list: قائمة بأسماء القوالب ومعلوماتها
    """
    ensure_templates_dir()
    
    templates = []
    for file in os.listdir(TEMPLATES_DIR):
        if file.endswith('.json'):
            try:
                with open(os.path.join(TEMPLATES_DIR, file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                template_info = {
                    "id": file[:-5],  # استخدام اسم الملف بدون .json كمعرف فريد
                    "name": data.get("name", "قالب بدون اسم"),
                    "artist": data.get("artist", "عام"),
                    "has_image": "album_art" in data
                }
                
                # تصفية حسب الفنان إذا تم تحديده
                if not filter_artist or filter_artist.lower() == template_info["artist"].lower():
                    templates.append(template_info)
            except Exception as e:
                logger.error(f"خطأ في قراءة معلومات القالب {file}: {e}")
    
    # ترتيب القوالب حسب الفنان ثم الاسم
    templates.sort(key=lambda x: (x["artist"], x["name"]))
    
    return templates

def get_artists_with_templates():
    """
    استرجاع قائمة بجميع الفنانين الذين لديهم قوالب
    
    Returns:
        list: قائمة بأسماء الفنانين
    """
    ensure_templates_dir()
    
    artists = set()
    for file in os.listdir(TEMPLATES_DIR):
        if file.endswith('.json'):
            try:
                with open(os.path.join(TEMPLATES_DIR, file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    artist = data.get("artist", "عام")
                    artists.add(artist)
            except Exception:
                continue
    
    # ترتيب الفنانين أبجدياً مع وضع "عام" في الأعلى
    artists_list = sorted(list(artists))
    if "عام" in artists_list:
        artists_list.remove("عام")
        artists_list.insert(0, "عام")
    
    return artists_list

def get_template_path(template_name):
    """
    الحصول على مسار ملف القالب
    
    Args:
        template_name: اسم القالب
        
    Returns:
        str: مسار ملف القالب
    """
    return os.path.join(TEMPLATES_DIR, f"{template_name}.json")

def delete_template(template_id):
    """
    حذف قالب موجود
    
    Args:
        template_id: معرف القالب (اسم الملف بدون .json)
        
    Returns:
        bool: نتيجة العملية
    """
    file_path = os.path.join(TEMPLATES_DIR, f"{template_id}.json")
    if not os.path.exists(file_path):
        return False
    
    try:
        os.remove(file_path)
        logger.info(f"تم حذف القالب: {template_id}")
        return True
    except Exception as e:
        logger.error(f"خطأ في حذف القالب: {e}")
        return False

def extract_artist_from_tags(tags):
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

def get_all_templates():
    """
    الحصول على جميع القوالب المحفوظة
    
    Returns:
        list: قائمة بجميع القوالب المحفوظة
    """
    ensure_templates_dir()
    templates = []
    
    for file_name in os.listdir(TEMPLATES_DIR):
        if file_name.endswith('.json'):
            template_path = os.path.join(TEMPLATES_DIR, file_name)
            
            try:
                with open(template_path, 'r', encoding='utf-8') as file:
                    template_data = json.load(file)
                    
                    # إضافة اسم القالب (اسم الملف بدون .json)
                    template_data['name'] = file_name[:-5]
                    templates.append(template_data)
            except Exception as e:
                logger.error(f"خطأ في قراءة القالب {file_name}: {e}")
    
    # ترتيب القوالب حسب اسم الفنان ثم اسم القالب
    templates.sort(key=lambda x: (x.get('artist', 'عام'), x.get('name', '')))
    
    return templates

def export_all_templates(export_dir='templates_export'):
    """
    تصدير جميع القوالب إلى ملف مضغوط
    
    Args:
        export_dir: مسار مجلد التصدير
        
    Returns:
        tuple: (مسار ملف التصدير، عدد القوالب المصدرة)
    """
    ensure_templates_dir()
    os.makedirs(export_dir, exist_ok=True)
    
    timestamp = int(time.time())
    zip_filename = f"templates_backup_{timestamp}.zip"
    zip_path = os.path.join(export_dir, zip_filename)
    
    template_count = 0
    
    try:
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file_name in os.listdir(TEMPLATES_DIR):
                if file_name.endswith('.json'):
                    template_path = os.path.join(TEMPLATES_DIR, file_name)
                    zipf.write(template_path, file_name)
                    template_count += 1
        
        logger.info(f"تم تصدير {template_count} قالب إلى {zip_path}")
        return zip_path, template_count
    except Exception as e:
        logger.error(f"خطأ في تصدير القوالب: {e}")
        return None, 0
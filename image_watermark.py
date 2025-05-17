#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
وحدة معالجة صور الألبوم وإضافة العلامة المائية
- دعم إضافة علامة مائية للصور بالوضع التلقائي أو اليدوي
- التحكم بموضع وحجم وشفافية العلامة المائية
- معالجة الصور بأحجام مختلفة ودعم تنسيق PNG مع الشفافية
"""

import os
import io
import logging
from typing import Tuple, Optional, Union, List, Dict, Any
from PIL import Image, ImageEnhance

# استيراد مكتبات mutagen
import mutagen
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC
import mutagen.mp3
import mutagen.flac
import mutagen.mp4

# إعداد السجل
logger = logging.getLogger(__name__)

def apply_watermark(original_image: Union[str, bytes, Image.Image], 
                   watermark_image: Union[str, bytes, Image.Image],
                   position: str = 'bottom-right',
                   size_percent: int = 25,
                   opacity: float = 0.5,
                   padding: int = 10) -> Image.Image:
    """
    إضافة علامة مائية إلى صورة
    
    Args:
        original_image: مسار الملف أو البيانات الثنائية أو كائن صورة للصورة الأصلية
        watermark_image: مسار الملف أو البيانات الثنائية أو كائن صورة للعلامة المائية
        position: موضع العلامة المائية (top-left, top-right, bottom-left, bottom-right, center)
        size_percent: نسبة حجم العلامة المائية بالنسبة للصورة الأصلية (1-100)
        opacity: نسبة الشفافية للعلامة المائية (0.0-1.0)
        padding: التباعد من حافة الصورة بالبكسل
        
    Returns:
        Image.Image: كائن الصورة بعد إضافة العلامة المائية
    """
    try:
        # فتح الصورة الأصلية إذا كانت مسار ملف أو بيانات ثنائية
        if isinstance(original_image, str):
            original = Image.open(original_image).convert('RGBA')
        elif isinstance(original_image, bytes):
            original = Image.open(io.BytesIO(original_image)).convert('RGBA')
        else:
            original = original_image.convert('RGBA')
            
        # فتح صورة العلامة المائية إذا كانت مسار ملف أو بيانات ثنائية
        if isinstance(watermark_image, str):
            watermark = Image.open(watermark_image).convert('RGBA')
        elif isinstance(watermark_image, bytes):
            watermark = Image.open(io.BytesIO(watermark_image)).convert('RGBA')
        else:
            watermark = watermark_image.convert('RGBA')
            
        # تعديل حجم العلامة المائية
        original_width, original_height = original.size
        watermark_width, watermark_height = watermark.size
        
        # حساب الحجم الجديد للعلامة المائية
        new_watermark_width = int(original_width * size_percent / 100)
        new_watermark_height = int(watermark_height * (new_watermark_width / watermark_width))
        
        # تعديل حجم العلامة المائية
        watermark = watermark.resize((new_watermark_width, new_watermark_height), Image.Resampling.LANCZOS)
        
        # تعديل شفافية العلامة المائية
        watermark_with_opacity = Image.new('RGBA', watermark.size, (0, 0, 0, 0))
        for x in range(watermark.width):
            for y in range(watermark.height):
                r, g, b, a = watermark.getpixel((x, y))
                watermark_with_opacity.putpixel((x, y), (r, g, b, int(a * opacity)))
        
        # تحديد موضع العلامة المائية
        wm_position = (0, 0)  # تهيئة أولية للمتغير
        if position == 'top-left':
            wm_position = (padding, padding)
        elif position == 'top-right':
            wm_position = (original_width - new_watermark_width - padding, padding)
        elif position == 'bottom-left':
            wm_position = (padding, original_height - new_watermark_height - padding)
        elif position == 'bottom-right':
            wm_position = (original_width - new_watermark_width - padding, original_height - new_watermark_height - padding)
        elif position == 'center':
            wm_position = ((original_width - new_watermark_width) // 2, (original_height - new_watermark_height) // 2)
        else:
            # افتراضياً أسفل اليمين
            wm_position = (original_width - new_watermark_width - padding, original_height - new_watermark_height - padding)
            
        # إنشاء صورة جديدة بنفس أبعاد الصورة الأصلية
        result = Image.new('RGBA', original.size, (0, 0, 0, 0))
        
        # نسخ الصورة الأصلية
        result.paste(original, (0, 0))
        
        # إضافة العلامة المائية
        result.paste(watermark_with_opacity, wm_position, watermark_with_opacity)
        
        return result
    except Exception as e:
        logger.error(f"خطأ في إضافة العلامة المائية: {e}")
        # إرجاع الصورة الأصلية في حالة الخطأ
        if isinstance(original_image, str):
            return Image.open(original_image)
        elif isinstance(original_image, bytes):
            return Image.open(io.BytesIO(original_image))
        else:
            return original_image

def save_image_with_watermark(original_image_path: str, 
                             watermark_image_path: str,
                             output_path: str,
                             position: str = 'bottom-right',
                             size_percent: int = 25,
                             opacity: float = 0.5,
                             padding: int = 10,
                             format: str = 'PNG') -> bool:
    """
    إضافة علامة مائية إلى صورة وحفظها
    
    Args:
        original_image_path: مسار الصورة الأصلية
        watermark_image_path: مسار صورة العلامة المائية
        output_path: مسار حفظ الصورة الناتجة
        position: موضع العلامة المائية (top-left, top-right, bottom-left, bottom-right, center)
        size_percent: نسبة حجم العلامة المائية بالنسبة للصورة الأصلية (1-100)
        opacity: نسبة الشفافية للعلامة المائية (0.0-1.0)
        padding: التباعد من حافة الصورة بالبكسل
        format: تنسيق الصورة الناتجة (PNG, JPEG, etc.)
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        # التحقق من وجود الملفات
        if not os.path.exists(original_image_path):
            logger.error(f"الملف الأصلي غير موجود: {original_image_path}")
            return False
            
        if not os.path.exists(watermark_image_path):
            logger.error(f"ملف العلامة المائية غير موجود: {watermark_image_path}")
            return False
            
        # إضافة العلامة المائية
        result = apply_watermark(
            original_image_path,
            watermark_image_path,
            position,
            size_percent,
            opacity,
            padding
        )
        
        # إنشاء المجلد إذا لم يكن موجوداً
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # حفظ الصورة
        if format.upper() == 'PNG':
            result.save(output_path, format=format, compress_level=9)
        else:
            # تحويل RGBA إلى RGB للتنسيقات التي لا تدعم الشفافية
            if result.mode == 'RGBA':
                rgb_image = Image.new('RGB', result.size, (255, 255, 255))
                rgb_image.paste(result, mask=result.split()[3])  # استخدام قناة alpha كقناع
                rgb_image.save(output_path, format=format, quality=95)
            else:
                result.save(output_path, format=format, quality=95)
        
        logger.info(f"تم حفظ الصورة بنجاح: {output_path}")
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ الصورة مع العلامة المائية: {e}")
        return False

def extract_album_art(audio_file_path: str, output_path: str = None) -> Tuple[bool, Optional[str]]:
    """
    استخراج صورة الألبوم من ملف صوتي
    
    Args:
        audio_file_path: مسار الملف الصوتي
        output_path: مسار حفظ صورة الألبوم (اختياري)
        
    Returns:
        Tuple[bool, Optional[str]]: نتيجة العملية ومسار الصورة المستخرجة (إن وجدت)
    """
    try:
        # استخدام مكتبة mutagen لاستخراج صورة الألبوم
        import mutagen
        from mutagen.id3 import ID3, APIC
        
        audio = mutagen.File(audio_file_path)
        
        # التعامل مع ملفات MP3
        if isinstance(audio, mutagen.mp3.MP3):
            id3 = ID3(audio_file_path)
            for tag in id3.values():
                if isinstance(tag, APIC):
                    image_data = tag.data
                    if output_path:
                        with open(output_path, 'wb') as img_file:
                            img_file.write(image_data)
                        return True, output_path
                    else:
                        return True, image_data
        
        # التعامل مع ملفات FLAC
        elif isinstance(audio, mutagen.flac.FLAC):
            for picture in audio.pictures:
                image_data = picture.data
                if output_path:
                    with open(output_path, 'wb') as img_file:
                        img_file.write(image_data)
                    return True, output_path
                else:
                    return True, image_data
        
        # التعامل مع ملفات M4A
        elif isinstance(audio, mutagen.mp4.MP4):
            if 'covr' in audio:
                image_data = audio['covr'][0]
                if output_path:
                    with open(output_path, 'wb') as img_file:
                        img_file.write(image_data)
                    return True, output_path
                else:
                    return True, image_data
        
        # لم يتم العثور على صورة ألبوم
        logger.warning(f"لم يتم العثور على صورة ألبوم في الملف: {audio_file_path}")
        return False, None
    except Exception as e:
        logger.error(f"خطأ في استخراج صورة الألبوم: {e}")
        return False, None

def apply_watermark_to_audio_cover(audio_file_path: str, 
                                 watermark_image_path: str,
                                 position: str = 'bottom-right',
                                 size_percent: int = 25,
                                 opacity: float = 0.5,
                                 padding: int = 10) -> Tuple[bool, Optional[Image.Image]]:
    """
    إضافة علامة مائية إلى صورة ألبوم ملف صوتي
    
    Args:
        audio_file_path: مسار الملف الصوتي
        watermark_image_path: مسار صورة العلامة المائية
        position: موضع العلامة المائية
        size_percent: نسبة حجم العلامة المائية
        opacity: نسبة الشفافية
        padding: التباعد من الحافة
        
    Returns:
        Tuple[bool, Optional[Image.Image]]: نتيجة العملية وكائن الصورة بعد إضافة العلامة المائية
    """
    try:
        # استخراج صورة الألبوم
        success, album_art = extract_album_art(audio_file_path)
        if not success:
            logger.warning(f"لم يتم العثور على صورة ألبوم في الملف: {audio_file_path}")
            return False, None
            
        # التحقق من وجود ملف العلامة المائية
        if not os.path.exists(watermark_image_path):
            logger.error(f"ملف العلامة المائية غير موجود: {watermark_image_path}")
            return False, None
            
        # إضافة العلامة المائية
        if isinstance(album_art, bytes):
            album_art_image = Image.open(io.BytesIO(album_art))
        else:
            album_art_image = Image.open(album_art)
            
        result = apply_watermark(
            album_art_image,
            watermark_image_path,
            position,
            size_percent,
            opacity,
            padding
        )
        
        logger.info(f"تم إضافة العلامة المائية لصورة الألبوم بنجاح")
        return True, result
    except Exception as e:
        logger.error(f"خطأ في إضافة العلامة المائية لصورة الألبوم: {e}")
        return False, None

def update_audio_cover_with_watermark(audio_file_path: str, 
                                     watermark_image_path: str,
                                     position: str = 'bottom-right',
                                     size_percent: int = 25,
                                     opacity: float = 0.5,
                                     padding: int = 10) -> bool:
    """
    تحديث صورة الألبوم في ملف صوتي بإضافة علامة مائية
    
    Args:
        audio_file_path: مسار الملف الصوتي
        watermark_image_path: مسار صورة العلامة المائية
        position: موضع العلامة المائية
        size_percent: نسبة حجم العلامة المائية
        opacity: نسبة الشفافية
        padding: التباعد من الحافة
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        # إضافة العلامة المائية لصورة الألبوم
        success, watermarked_image = apply_watermark_to_audio_cover(
            audio_file_path,
            watermark_image_path,
            position,
            size_percent,
            opacity,
            padding
        )
        
        if not success or watermarked_image is None:
            return False
            
        # تحويل الصورة إلى بيانات ثنائية
        img_byte_arr = io.BytesIO()
        watermarked_image.save(img_byte_arr, format='PNG')
        img_data = img_byte_arr.getvalue()
        
        # تحديث صورة الألبوم في الملف الصوتي
        import mutagen
        from mutagen.id3 import ID3, APIC
        
        audio = mutagen.File(audio_file_path)
        
        # التعامل مع ملفات MP3
        if isinstance(audio, mutagen.mp3.MP3):
            id3 = ID3(audio_file_path)
            # حذف جميع صور APIC
            for tag in list(id3.keys()):
                if tag.startswith('APIC'):
                    del id3[tag]
            
            # إضافة الصورة الجديدة
            id3.add(
                APIC(
                    encoding=3,  # UTF-8
                    mime='image/png',
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=img_data
                )
            )
            id3.save()
            
        # التعامل مع ملفات FLAC
        elif isinstance(audio, mutagen.flac.FLAC):
            from mutagen.flac import Picture
            
            # حذف جميع الصور
            audio.clear_pictures()
            
            # إضافة الصورة الجديدة
            picture = Picture()
            picture.type = 3  # Cover (front)
            picture.mime = 'image/png'
            picture.desc = 'Cover'
            picture.data = img_data
            
            audio.add_picture(picture)
            audio.save()
            
        # التعامل مع ملفات M4A
        elif isinstance(audio, mutagen.mp4.MP4):
            from mutagen.mp4 import MP4Cover, MP4Tags
            
            # إضافة الصورة الجديدة
            audio['covr'] = [MP4Cover(img_data, imageformat=MP4Cover.FORMAT_PNG)]
            audio.save()
            
        else:
            logger.warning(f"نوع الملف غير مدعوم: {audio_file_path}")
            return False
            
        logger.info(f"تم تحديث صورة الألبوم بنجاح: {audio_file_path}")
        return True
    except Exception as e:
        logger.error(f"خطأ في تحديث صورة الألبوم: {e}")
        return False
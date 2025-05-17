import logging
import os
from mutagen.id3 import ID3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen._file import File

logger = logging.getLogger(__name__)

def get_file_type(file_path):
    """
    تحديد نوع الملف الصوتي
    
    Args:
        file_path: مسار الملف الصوتي
        
    Returns:
        str: نوع الملف ('mp3', 'flac', 'm4a', 'ogg', 'unknown')
    """
    _, ext = os.path.splitext(file_path.lower())
    
    if ext == '.mp3':
        return 'mp3'
    elif ext == '.flac':
        return 'flac'
    elif ext in ['.m4a', '.mp4', '.aac']:
        return 'm4a'
    elif ext in ['.ogg', '.oga', '.opus']:
        return 'ogg'
    else:
        return 'unknown'

def extract_album_art_as_bytes(file_path):
    """
    استخراج صورة الألبوم من ملف صوتي كبيانات ثنائية (bytes)
    
    Args:
        file_path: مسار الملف الصوتي
        
    Returns:
        bytes: بيانات صورة الألبوم أو None إذا لم تكن موجودة
    """
    try:
        file_type = get_file_type(file_path)
        logger.info(f"محاولة استخراج صورة الألبوم من ملف {file_path} (النوع: {file_type})")
        
        if file_type == 'mp3':
            try:
                audio = ID3(file_path)
                
                # البحث عن أول صورة ألبوم
                for tag in list(audio.keys()):
                    if tag.startswith('APIC'):
                        logger.info(f"تم العثور على صورة ألبوم في إطار {tag}")
                        return audio[tag].data
                
                logger.info("لم يتم العثور على صورة ألبوم في ملف MP3")
                return None
            except Exception as e:
                logger.error(f"خطأ في استخراج صورة ألبوم من ملف MP3: {e}")
                return None
        
        elif file_type == 'flac':
            try:
                audio = FLAC(file_path)
                
                # البحث عن الصور في ملف FLAC
                if audio.pictures:
                    # أخذ أول صورة
                    logger.info(f"تم العثور على {len(audio.pictures)} صورة في ملف FLAC")
                    return audio.pictures[0].data
                
                logger.info("لم يتم العثور على صورة ألبوم في ملف FLAC")
                return None
            except Exception as e:
                logger.error(f"خطأ في استخراج صورة ألبوم من ملف FLAC: {e}")
                return None
        
        elif file_type == 'm4a':
            try:
                audio = MP4(file_path)
                
                # البحث عن الصور في ملف MP4/M4A
                if 'covr' in audio:
                    artwork = audio['covr']
                    if artwork:
                        # أخذ أول صورة
                        logger.info(f"تم العثور على صورة ألبوم في ملف M4A")
                        return artwork[0]
                
                logger.info("لم يتم العثور على صورة ألبوم في ملف M4A")
                return None
            except Exception as e:
                logger.error(f"خطأ في استخراج صورة ألبوم من ملف M4A: {e}")
                return None
        
        elif file_type == 'ogg':
            try:
                # البحث عن الصور في الميتاداتا
                general_audio = File(file_path)
                
                if general_audio and hasattr(general_audio, 'pictures') and general_audio.pictures:
                    # أخذ أول صورة
                    logger.info(f"تم العثور على صورة ألبوم في ملف OGG")
                    return general_audio.pictures[0].data
                
                logger.info("لم يتم العثور على صورة ألبوم في ملف OGG")
                return None
            except Exception as e:
                logger.error(f"خطأ في استخراج صورة ألبوم من ملف OGG: {e}")
                return None
        
        # نوع ملف غير مدعوم
        logger.info(f"نوع الملف {file_type} غير مدعوم لاستخراج صورة الألبوم")
        return None
    
    except Exception as e:
        logger.error(f"خطأ في استخراج صورة الألبوم: {e}")
        return None
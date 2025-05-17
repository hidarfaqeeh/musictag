"""
وحدة معالجة الملفات الصوتية التلقائية للقنوات
- مراقبة قناة معينة للملفات الصوتية الجديدة
- تعديل الوسوم تلقائياً وفقاً للإعدادات
- استبدال النصوص في الوسوم
- تطبيق القوالب الذكية حسب اسم الفنان
"""

import os
import re
import logging
import telebot
import tempfile
import shutil
from tag_handler import get_audio_tags, set_audio_tags
from thumbnail_helper import extract_album_art_as_bytes
from template_handler import get_template
import admin_panel
from config import Config
from logger_setup import log_auto_processing, log_error

# إعداد التسجيل
logger = logging.getLogger('auto_processor')

def remove_links(text):
    """
    حذف الروابط من النص
    
    Args:
        text: النص المراد معالجته
        
    Returns:
        str: النص بعد حذف الروابط
    """
    if not text:
        return text
    
    # نمط للروابط http/https
    http_pattern = r'https?://\S+'
    
    # نمط لروابط www
    www_pattern = r'www\.\S+'
    
    # نمط لروابط تيليجرام
    telegram_pattern = r't\.me/\S+'
    
    # حذف الروابط في نفس الوقت باستخدام OR |
    link_pattern = r'(https?://\S+|www\.\S+|t\.me/\S+)'
    result = re.sub(link_pattern, '', text)
    
    # حذف روابط تيليجرام بتنسيق @username
    telegram_username_pattern = r'@[a-zA-Z][a-zA-Z0-9_]{4,}'
    result = re.sub(telegram_username_pattern, '', result)
    
    # تنظيف الأسطر الفارغة المتكررة
    result = re.sub(r'\n\s*\n', '\n\n', result)
    
    # تنظيف المسافات الزائدة
    result = re.sub(r' +', ' ', result)
    
    return result.strip()
logger.setLevel(logging.INFO)

def is_enabled():
    """التحقق مما إذا كانت المعالجة التلقائية مفعلة أم لا"""
    # استخدام القيمة من ملف الإعدادات أولاً، ثم من الإعدادات المخزنة في قاعدة البيانات
    from_env = Config.AUTO_PROCESSING_ENABLED
    from_db = admin_panel.get_setting("features_enabled.auto_processing", None)
    
    if from_db is not None:
        return from_db
    return from_env

def get_source_channel():
    """الحصول على معرف قناة المصدر"""
    return admin_panel.get_setting("auto_processing.source_channel", "")

def get_target_channel():
    """الحصول على معرف قناة الهدف للنشر التلقائي"""
    return admin_panel.get_setting("auto_processing.target_channel", "")

def should_keep_caption():
    """التحقق مما إذا كان يجب الحفاظ على الكابشن الأصلي"""
    return admin_panel.get_setting("auto_processing.keep_caption", True)

def should_auto_publish():
    """التحقق مما إذا كان يجب النشر التلقائي بعد التعديل"""
    return admin_panel.get_setting("auto_processing.auto_publish", True)
    
def should_forward_to_target():
    """التحقق مما إذا كان يجب نشر الملف المعدل لقناة الهدف"""
    return admin_panel.get_setting("auto_processing.forward_to_target", False)
    
def should_remove_links():
    """التحقق مما إذا كان يجب حذف الروابط تلقائيًا من الوسوم"""
    return admin_panel.get_setting("auto_processing.remove_links", False)
    
def should_add_footer():
    """التحقق مما إذا كان يجب إضافة التذييل للوسوم"""
    return admin_panel.get_setting("auto_processing.footer_enabled", False)

def get_tag_footer():
    """الحصول على نص التذييل للوسوم"""
    return admin_panel.get_setting("auto_processing.tag_footer", "")

def get_footer_tag_settings():
    """الحصول على إعدادات الوسوم التي يضاف إليها التذييل"""
    return admin_panel.get_setting("auto_processing.footer_tag_settings", {})

def get_tag_replacements():
    """الحصول على استبدالات النصوص للوسوم"""
    return admin_panel.get_setting("auto_processing.tag_replacements", {})

def get_enabled_tags():
    """الحصول على الوسوم المفعلة للمعالجة"""
    return admin_panel.get_setting("auto_processing.enabled_tags", {
        'artist': True,
        'album_artist': True,
        'album': True,
        'genre': True,
        'year': True,
        'composer': True,
        'comment': True,
        'title': True,
        'lyrics': True  # إضافة دعم كلمات الأغاني للاستبدال
    })

def get_smart_templates():
    """الحصول على القوالب الذكية حسب اسم الفنان"""
    return admin_panel.get_setting("auto_processing.smart_templates", {})

def apply_replacements(text, replacements):
    """
    تطبيق استبدالات النصوص على نص معين
    
    Args:
        text: النص الأصلي
        replacements: قاموس الاستبدالات {من: إلى}
    
    Returns:
        str: النص بعد الاستبدالات
    """
    if not text:
        return text
    
    result = text
    for old_text, new_text in replacements.items():
        if old_text and new_text is not None:  # تجنب الاستبدالات الفارغة
            result = result.replace(old_text, new_text)
    
    return result

def apply_tag_replacements(tags, replacements, enabled_tags):
    """
    تطبيق استبدالات النصوص على الوسوم وحذف الروابط إذا كانت الميزة مفعلة
    
    Args:
        tags: الوسوم الأصلية
        replacements: قاموس الاستبدالات {من: إلى}
        enabled_tags: قاموس الوسوم المفعلة {اسم الوسم: True/False}
    
    Returns:
        dict: الوسوم بعد الاستبدالات
    """
    # التحقق من وجود استبدالات أو تفعيل حذف الروابط
    remove_links_enabled = should_remove_links()
    add_footer_enabled = should_add_footer()
    footer_text = get_tag_footer() if add_footer_enabled else ""
    footer_tag_settings = get_footer_tag_settings() if add_footer_enabled else {}
    
    if not replacements and not remove_links_enabled and not add_footer_enabled:
        return tags
    
    result = tags.copy()
    
    # إضافة سجل لعرض الوسوم المفعلة
    logger.info(f"الوسوم المفعلة للاستبدال: {enabled_tags}")
    
    # تخطي الاستبدال إذا كانت قائمة الوسوم المفعلة فارغة
    if not enabled_tags:
        logger.warning("قائمة الوسوم المفعلة فارغة، يتم تخطي الاستبدال")
        return result
    
    # إضافة سجل إذا كان حذف الروابط مفعلاً
    if remove_links_enabled:
        logger.info("ميزة حذف الروابط مفعلة، سيتم حذف الروابط من الوسوم المفعلة")
        
    # إضافة سجل إذا كان إضافة التذييل مفعلاً
    if add_footer_enabled and footer_text:
        logger.info(f"ميزة إضافة التذييل مفعلة، سيتم إضافة نص التذييل للوسوم المحددة: {footer_text}")
    
    for tag_name, value in tags.items():
        # التحقق من أن الوسم مفعل، وإذا لم يكن موجوداً في القائمة نفترض أنه مفعل
        tag_enabled = enabled_tags.get(tag_name, True)  
        logger.debug(f"معالجة الوسم: {tag_name}, مفعل: {tag_enabled}, القيمة: {value[:50] if isinstance(value, str) else value}")
        
        # تطبيق المعالجة فقط على الوسوم المفعلة
        if tag_enabled and isinstance(value, str) and value:
            # معالجة خاصة لكلمات الأغنية لتحافظ على تنسيق الأسطر
            if tag_name == 'lyrics':
                logger.info(f"معالجة كلمات الأغنية ({len(value)} حرف)")
                
                processed_value = value
                
                # معالجة كلمات الأغنية بالكامل بدلاً من سطر بسطر لتجنب أي مشاكل في التنسيق
                
                # حذف الروابط إذا كانت الميزة مفعلة
                if remove_links_enabled:
                    logger.info("تطبيق حذف الروابط على كلمات الأغنية")
                    processed_value = remove_links(processed_value)
                
                # تطبيق الاستبدالات إذا وجدت
                if replacements:
                    logger.info("تطبيق استبدالات النصوص على كلمات الأغنية")
                    
                    # معالجة استبدالات النصوص سطراً سطراً للحفاظ على التنسيق
                    lines = processed_value.split('\n')
                    processed_lines = [apply_replacements(line, replacements) for line in lines]
                    processed_value = '\n'.join(processed_lines)
                
                # إضافة التذييل إذا كانت الميزة مفعلة وهذا الوسم مسموح بإضافة التذييل له
                if add_footer_enabled and footer_text and footer_tag_settings.get(tag_name, True):
                    logger.info(f"إضافة التذييل إلى كلمات الأغنية")
                    # إضافة سطر فارغ قبل التذييل إذا لم تكن الكلمات تنتهي بسطر فارغ
                    if processed_value.strip() and not processed_value.strip().endswith('\n\n'):
                        processed_value += '\n\n'
                    elif not processed_value.strip().endswith('\n'):
                        processed_value += '\n'
                    # إضافة التذييل
                    processed_value += footer_text
                
                result[tag_name] = processed_value
                # حساب عدد الأسطر
                num_lines = processed_value.count('\n') + 1 if processed_value else 0
                logger.info(f"تم معالجة كلمات الأغنية بنجاح ({num_lines} سطر)")
            else:
                # معالجة عادية للوسوم الأخرى
                processed_value = value
                
                # حذف الروابط إذا كانت الميزة مفعلة
                if remove_links_enabled:
                    logger.debug(f"حذف الروابط من الوسم: {tag_name}")
                    processed_value = remove_links(processed_value)
                
                # تطبيق الاستبدالات إذا وجدت
                if replacements:
                    logger.debug(f"تطبيق استبدالات النصوص على الوسم: {tag_name}")
                    processed_value = apply_replacements(processed_value, replacements)
                
                # إضافة التذييل إذا كانت الميزة مفعلة وهذا الوسم مسموح بإضافة التذييل له
                if add_footer_enabled and footer_text and footer_tag_settings.get(tag_name, True):
                    logger.debug(f"إضافة التذييل إلى الوسم: {tag_name}")
                    # إضافة فاصل مناسب
                    if processed_value.strip():
                        # للوسوم النصية الطويلة مثل التعليقات، نضيف سطر جديد
                        if len(processed_value) > 50 or '\n' in processed_value:
                            if not processed_value.endswith('\n'):
                                processed_value += '\n\n'
                            else:
                                if not processed_value.endswith('\n\n'):
                                    processed_value += '\n'
                        else:
                            # للوسوم القصيرة نضيف مسافة
                            if not processed_value.endswith(' '):
                                processed_value += ' - '
                            else:
                                processed_value += '- '
                    # إضافة التذييل
                    processed_value += footer_text
                
                result[tag_name] = processed_value
    
    return result

def apply_smart_template(tags, smart_templates):
    """
    تطبيق القالب الذكي المناسب حسب اسم الفنان
    
    Args:
        tags: الوسوم الأصلية
        smart_templates: قاموس القوالب الذكية {اسم الفنان: معرف القالب}
    
    Returns:
        dict: الوسوم بعد تطبيق القالب (إن وجد)
    """
    if not smart_templates or 'artist' not in tags or not tags['artist']:
        return tags
    
    artist_name = tags['artist']
    
    # البحث عن القالب المناسب حسب اسم الفنان
    for template_artist, template_id in smart_templates.items():
        if template_artist.lower() in artist_name.lower() or artist_name.lower() in template_artist.lower():
            # الحصول على القالب
            template = get_template(template_id)
            if template and 'tags' in template:
                # دمج الوسوم مع الحفاظ على العنوان والفنان والألبوم الأصليين
                merged_tags = tags.copy()
                for tag_name, value in template['tags'].items():
                    # لا نقوم بتغيير العنوان والفنان والألبوم من القالب
                    if tag_name not in ['title', 'artist', 'album']:
                        # معالجة خاصة لكلمات الأغنية - تطبيق القالب فقط إذا كانت كلمات الأغنية غير موجودة أو فارغة في الملف الأصلي
                        if tag_name == 'lyrics':
                            # إذا كان الملف الأصلي لا يحتوي على كلمات أغنية أو كانت فارغة
                            if 'lyrics' not in merged_tags or not merged_tags['lyrics'] or merged_tags['lyrics'].strip() == '':
                                logger.info(f"إضافة كلمات الأغنية من القالب ({len(value)} حرف)")
                                merged_tags[tag_name] = value
                            else:
                                logger.info(f"تم تجاهل كلمات الأغنية من القالب لأن الملف الأصلي يحتوي بالفعل على كلمات أغنية")
                        else:
                            merged_tags[tag_name] = value
                
                logger.info(f"تم تطبيق القالب الذكي ({template_id}) للفنان: {artist_name}")
                return merged_tags
    
    return tags

def process_audio_file(bot, message, temp_dir='temp_audio_files'):
    """
    معالجة ملف صوتي من رسالة في القناة
    
    Args:
        bot: كائن البوت
        message: كائن الرسالة
        temp_dir: مسار المجلد المؤقت
        
    Returns:
        bool: نتيجة العملية
    """
    if not is_enabled():
        logger.info("المعالجة التلقائية غير مفعلة")
        return False
    
    if not message.audio:
        logger.info("الرسالة لا تحتوي على ملف صوتي")
        return False
    
    # التأكد من وجود المجلد المؤقت
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        file_info = bot.get_file(message.audio.file_id)
        file_path = os.path.join(temp_dir, f"ch_{message.message_id}_{message.audio.file_name}")
        downloaded_file = bot.download_file(file_info.file_path)
        
        # حفظ الملف في المجلد المؤقت
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        logger.info(f"تم تنزيل الملف الصوتي: {file_path}")
        
        # إنشاء نسخة من الملف للتعديل
        edited_file_path = os.path.join(temp_dir, f"edited_{message.message_id}_{message.audio.file_name}")
        shutil.copy2(file_path, edited_file_path)
        
        # الحصول على الوسوم الحالية
        tags = get_audio_tags(edited_file_path)
        
        # تطبيق التعديلات
        replacements = get_tag_replacements()
        enabled_tags = get_enabled_tags()
        smart_templates = get_smart_templates()
        
        # تطبيق القالب الذكي أولاً
        tags = apply_smart_template(tags, smart_templates)
        
        # ثم تطبيق استبدالات النصوص
        tags = apply_tag_replacements(tags, replacements, enabled_tags)
        
        # حفظ التغييرات
        set_audio_tags(edited_file_path, tags)
        
        logger.info(f"تم تعديل الملف الصوتي: {edited_file_path}")
        
        # حذف الرسالة الأصلية وإرسال الملف المعدل
        caption = message.caption if should_keep_caption() and message.caption else ""
        
        # إرسال الملف المعدل كرسالة جديدة مع تحسين العرض
        with open(edited_file_path, 'rb') as audio_file:
            # استخراج صورة الألبوم لاستخدامها كصورة مصغرة إن وجدت
            thumbnail = None
            thumbnail_path = None
            try:
                # محاولة استخراج صورة الألبوم من الملف المعدل
                thumbnail_data = extract_album_art_as_bytes(edited_file_path)
                
                if thumbnail_data:
                    # تحسين جودة الصورة المصغرة قبل استخدامها
                    from io import BytesIO
                    from PIL import Image
                    
                    try:
                        # تحويل بيانات الصورة إلى كائن PIL
                        image_stream = BytesIO(thumbnail_data)
                        img = Image.open(image_stream)
                        
                        # تعديل حجم الصورة لتيليغرام 
                        # Telegram يفضل صور مربعة بأبعاد محددة للصور المصغرة
                        size = 512  # حجم مثالي لتيليغرام (يجب أن يكون أكبر من 320px على الأقل)
                        width, height = img.size
                        
                        # الحصول على مربع من وسط الصورة للحفاظ على التناسب
                        min_dim = min(width, height)
                        left = (width - min_dim) // 2
                        top = (height - min_dim) // 2
                        right = left + min_dim
                        bottom = top + min_dim
                        img = img.crop((left, top, right, bottom))
                        
                        # تغيير الحجم إلى 512×512 للحصول على أفضل نتيجة في تيليغرام
                        img = img.resize((size, size), Image.Resampling.LANCZOS)
                        
                        # حفظ بجودة 100% لضمان أفضل جودة ممكنة
                        thumbnail_path = f"{os.path.splitext(edited_file_path)[0]}_thumb.jpg"
                        img.save(thumbnail_path, format='JPEG', quality=100, optimize=True)
                        
                        # فتح الصورة المحسنة للإرسال
                        thumbnail = open(thumbnail_path, 'rb')
                        logger.info(f"تم تحسين الصورة المصغرة بأبعاد {size}×{size} بكسل")
                    except Exception as img_err:
                        logger.error(f"خطأ في معالجة الصورة المصغرة: {img_err}")
                        # استخدام الصورة الأصلية بدون معالجة في حالة حدوث خطأ
                        thumbnail_path = f"{os.path.splitext(edited_file_path)[0]}_thumb.jpg"
                        with open(thumbnail_path, 'wb') as thumb_file:
                            thumb_file.write(thumbnail_data)
                        thumbnail = open(thumbnail_path, 'rb')
                        logger.info(f"تم استخدام الصورة الأصلية كمصغرة بحجم {len(thumbnail_data)} بايت")
            except Exception as thumb_error:
                logger.error(f"خطأ في استخراج الصورة المصغرة: {thumb_error}")
                thumbnail = None
            
            # إرسال الملف المعدل مع تحسين العرض
            try:
                sent_message = bot.send_audio(
                    chat_id=message.chat.id,
                    audio=audio_file,
                    caption=caption,
                    title=tags.get('title', message.audio.title),
                    performer=tags.get('artist', message.audio.performer),
                    thumb=thumbnail,
                    duration=message.audio.duration if hasattr(message.audio, 'duration') else None,
                    parse_mode='Markdown'  # لدعم التنسيق في التسمية التوضيحية
                )
                
                # تسجيل العملية
                logger.info(f"تم إرسال الملف المعدل برسالة جديدة برقم {sent_message.message_id}")
                
                # إغلاق وحذف ملف الصورة المصغرة المؤقت إن وجد
                if thumbnail:
                    thumbnail.close()
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                
            except Exception as send_error:
                logger.error(f"خطأ في إرسال الملف المعدل: {send_error}")
                # محاولة إرسال الملف بدون خيارات متقدمة
                sent_message = bot.send_audio(
                    chat_id=message.chat.id,
                    audio=audio_file,
                    caption=caption
                )
                logger.info(f"تم إرسال الملف المعدل بالطريقة البسيطة برقم {sent_message.message_id}")
                
            # تسجيل العملية
            logger.info(f"تم إرسال الملف المعدل برسالة جديدة برقم {sent_message.message_id}")
        
        # حذف الرسالة الأصلية
        try:
            bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            logger.info(f"تم حذف الرسالة الأصلية برقم {message.message_id}")
        except Exception as e:
            logger.error(f"خطأ في حذف الرسالة الأصلية: {e}")
        
        # نشر الرسالة الجديدة تلقائياً إذا كانت الخاصية مفعلة
        if should_auto_publish() and hasattr(message.chat, 'type') and message.chat.type == 'channel':
            try:
                # استخدام دالة النشر المباشرة للقنوات بدلاً من إعادة التوجيه
                bot.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=message.chat.id,
                    message_id=sent_message.message_id
                )
                logger.info(f"تم نشر الرسالة الجديدة تلقائياً")
            except Exception as e:
                logger.error(f"خطأ في نشر الرسالة الجديدة: {e}")
        
        # إرسال الملف المعدل إلى قناة الهدف إذا كانت الميزة مفعلة
        if should_forward_to_target():
            target_channel = get_target_channel()
            if target_channel:
                try:
                    logger.info(f"جاري إرسال الملف المعدل إلى قناة الهدف: {target_channel}")
                    forwarded_msg = bot.copy_message(
                        chat_id=target_channel,
                        from_chat_id=message.chat.id,
                        message_id=sent_message.message_id,
                        caption=caption if should_keep_caption() else None
                    )
                    logger.info(f"تم إرسال الملف المعدل إلى قناة الهدف بنجاح")
                except Exception as e:
                    logger.error(f"خطأ في إرسال الملف المعدل إلى قناة الهدف: {e}")
        
        # تنظيف الملفات المؤقتة
        try:
            os.remove(file_path)
            os.remove(edited_file_path)
        except Exception as e:
            logger.error(f"خطأ في حذف الملفات المؤقتة: {e}")
        
        # تسجيل العملية
        admin_panel.log_action(
            None, 
            "auto_process_channel_file", 
            "success", 
            f"معالجة ملف صوتي من القناة: {message.chat.title if hasattr(message.chat, 'title') else message.chat.id}"
        )
        
        return True
    
    except Exception as e:
        logger.error(f"خطأ في معالجة الملف الصوتي التلقائية: {e}")
        admin_panel.log_action(
            None, 
            "auto_process_channel_file", 
            "failed", 
            f"خطأ: {str(e)}"
        )
        return False

def setup_channel_handlers(bot):
    """
    إعداد معالجات الرسائل للقنوات
    
    Args:
        bot: كائن البوت
    """
    @bot.channel_post_handler(content_types=['audio'])
    def handle_channel_audio(message):
        """معالجة الملفات الصوتية في القنوات"""
        if not is_enabled():
            return
        
        source_channel = get_source_channel()
        
        # التحقق من أن الرسالة من القناة المحددة
        if source_channel and hasattr(message.chat, 'username'):
            if message.chat.username == source_channel.replace('@', '') or (
                hasattr(message.chat, 'id') and str(message.chat.id) == source_channel.replace('@', '')
            ):
                logger.info(f"استلام ملف صوتي من القناة: {message.chat.title if hasattr(message.chat, 'title') else message.chat.id}")
                process_audio_file(bot, message)
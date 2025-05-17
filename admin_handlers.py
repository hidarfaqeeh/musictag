import os
import time
import logging
import psutil
from datetime import datetime
from telebot import types
from typing import Dict, List, Optional, Union, Any, Tuple

import admin_panel
from config import Config
import template_handler
import smart_rules
from models import db, SmartRule, User
from main import app

# إعداد التسجيل
logger = logging.getLogger('admin_handlers')
logger.setLevel(logging.INFO)

# تعريف الأزرار الرئيسية للوحة الإدارة
def get_admin_panel_markup():
    """إنشاء أزرار لوحة الإدارة الرئيسية"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")
    )
    markup.add(
        types.InlineKeyboardButton("🗂️ إدارة القوالب", callback_data="admin_templates"),
        types.InlineKeyboardButton("⚙️ إعدادات البوت", callback_data="admin_settings")
    )
    markup.add(
        types.InlineKeyboardButton("🧠 القواعد الذكية", callback_data="admin_smart_rules"),
        types.InlineKeyboardButton("📋 سجل العمليات", callback_data="admin_logs")
    )
    markup.add(
        types.InlineKeyboardButton("📢 إدارة البث الجماعي", callback_data="admin_broadcast_menu"),
        types.InlineKeyboardButton("🔔 إدارة الإشعارات", callback_data="admin_notifications")
    )
    markup.add(
        types.InlineKeyboardButton("🛠️ أدوات صيانة", callback_data="admin_tools"),
        types.InlineKeyboardButton("🤖 التعديل التلقائي", callback_data="admin_auto_processing")
    )
    markup.add(
        types.InlineKeyboardButton("💾 النسخ والاسترجاع", callback_data="admin_backup_menu")
    )
    markup.add(
        types.InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")
    )
    return markup

def get_admin_stats_markup():
    """إنشاء أزرار صفحة الإحصائيات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("♻️ إعادة تعيين الإحصائيات", callback_data="admin_reset_stats"),
        types.InlineKeyboardButton("📊 إحصائيات مفصلة", callback_data="admin_detailed_stats")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_users_markup():
    """إنشاء أزرار صفحة إدارة المستخدمين"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👤 المستخدمين النشطين", callback_data="admin_active_users"),
        types.InlineKeyboardButton("🔝 أكثر المستخدمين نشاطًا", callback_data="admin_top_users")
    )
    markup.add(
        types.InlineKeyboardButton("🚫 المستخدمين المحظورين", callback_data="admin_blocked_users"),
        types.InlineKeyboardButton("👮‍♂️ المشرفين", callback_data="admin_admins")
    )
    markup.add(
        types.InlineKeyboardButton("➕ إضافة مشرف", callback_data="admin_add_admin"),
        types.InlineKeyboardButton("➖ إزالة مشرف", callback_data="admin_remove_admin")
    )
    markup.add(
        types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_block_user"),
        types.InlineKeyboardButton("✅ إلغاء حظر مستخدم", callback_data="admin_unblock_user")
    )
    markup.add(
        types.InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_templates_markup():
    """إنشاء أزرار صفحة إدارة القوالب"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👀 عرض جميع القوالب", callback_data="admin_view_templates"),
        types.InlineKeyboardButton("✨ إنشاء قالب عام", callback_data="admin_create_template")
    )
    markup.add(
        types.InlineKeyboardButton("❌ حذف قالب", callback_data="admin_delete_template"),
        types.InlineKeyboardButton("✏️ تعديل قالب", callback_data="admin_edit_template")
    )
    markup.add(
        types.InlineKeyboardButton("📤 تصدير القوالب", callback_data="admin_export_templates"),
        types.InlineKeyboardButton("📥 استيراد القوالب", callback_data="admin_import_templates")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_settings_markup():
    """إنشاء أزرار صفحة الإعدادات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # تأكد من حالة الميزات المختلفة
    templates_status = "✅" if admin_panel.get_setting("features_enabled.templates", True) else "❌"
    lyrics_status = "✅" if admin_panel.get_setting("features_enabled.lyrics", True) else "❌"
    album_art_status = "✅" if admin_panel.get_setting("features_enabled.album_art", True) else "❌"
    required_subscription_status = "✅" if admin_panel.get_setting("features_enabled.required_subscription", False) else "❌"
    
    # الحصول على قيم الإعدادات الأخرى
    max_file_size = admin_panel.get_setting("max_file_size_mb", 50)
    processing_delay = admin_panel.get_setting("processing_delay", 0)
    daily_user_limit = admin_panel.get_setting("daily_user_limit_mb", 0)
    daily_limit_text = f"{daily_user_limit} ميجا" if daily_user_limit > 0 else "غير محدود"
    log_channel = admin_panel.get_setting("log_channel", "")
    log_channel_text = log_channel if log_channel else "غير معين"
    
    markup.add(
        types.InlineKeyboardButton(f"🔖 القوالب: {templates_status}", callback_data="admin_toggle_templates"),
        types.InlineKeyboardButton(f"📝 كلمات الأغاني: {lyrics_status}", callback_data="admin_toggle_lyrics")
    )
    markup.add(
        types.InlineKeyboardButton(f"🖼 صور الألبومات: {album_art_status}", callback_data="admin_toggle_album_art"),
        types.InlineKeyboardButton(f"📢 الاشتراك الإجباري: {required_subscription_status}", callback_data="admin_toggle_required_subscription")
    )
    markup.add(
        types.InlineKeyboardButton("📝 تعديل رسالة الترحيب", callback_data="admin_edit_welcome_msg")
    )
    markup.add(
        types.InlineKeyboardButton(f"⏱ تأخير المعالجة: {processing_delay} ثانية", callback_data="admin_set_delay"),
        types.InlineKeyboardButton(f"📊 حد البيانات اليومي: {daily_limit_text}", callback_data="admin_set_daily_limit")
    )
    markup.add(
        types.InlineKeyboardButton("📢 قنوات الاشتراك الإجباري", callback_data="admin_required_channels"),
        types.InlineKeyboardButton(f"📋 قناة السجل: {log_channel_text}", callback_data="admin_set_log_channel")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ إعدادات متقدمة", callback_data="admin_advanced_settings")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_advanced_settings_markup():
    """إنشاء أزرار صفحة الإعدادات المتقدمة"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الحصول على حالة العلامة المائية
    watermark_enabled = "✅" if admin_panel.get_setting("audio_watermark.enabled", False) else "❌"
    
    markup.add(
        types.InlineKeyboardButton(f"💧 العلامة المائية الصوتية ({watermark_enabled})", callback_data="admin_watermark_settings"),
        types.InlineKeyboardButton("🏷 الوسوم المفعلة", callback_data="admin_enabled_tags")
    )
    markup.add(
        types.InlineKeyboardButton("📝 تعديل وصف البوت", callback_data="admin_edit_description"),
        types.InlineKeyboardButton("ℹ️ تعديل ملاحظات الاستخدام", callback_data="admin_edit_usage_notes")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
    )
    return markup

def get_admin_enabled_tags_markup():
    """إنشاء أزرار صفحة إدارة الوسوم المفعلة للاستبدال"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الحصول على الوسوم المفعلة حالياً
    enabled_tags = admin_panel.get_setting("auto_processing.enabled_tags", {
        'artist': True,
        'album_artist': True,
        'album': True,
        'genre': True,
        'year': True,
        'composer': True,
        'comment': True,
        'title': True,
        'lyrics': True  # إضافة كلمات الأغنية
    })
    
    # قائمة أسماء الوسوم بالعربية
    arabic_tags = {
        'artist': 'الفنان',
        'album_artist': 'فنان الألبوم',
        'album': 'الألبوم',
        'genre': 'النوع',
        'year': 'السنة',
        'composer': 'الملحن',
        'comment': 'تعليق',
        'title': 'العنوان',
        'lyrics': 'كلمات الأغنية'
    }
    
    # إضافة زر لكل وسم مع حالته الحالية
    for tag, enabled in enabled_tags.items():
        tag_arabic = arabic_tags.get(tag, tag)
        status = "✅" if enabled else "❌"
        markup.add(
            types.InlineKeyboardButton(f"{tag_arabic}: {status}", callback_data=f"admin_toggle_tag_{tag}")
        )
    
    # إضافة زر العودة
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_proc_settings")
    )
    
    return markup

def get_admin_tag_replacements_markup():
    """إنشاء أزرار صفحة استبدالات الوسوم"""
    # الحصول على استبدالات الوسوم الحالية
    tag_replacements = admin_panel.get_setting("auto_processing.tag_replacements", {})
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # إضافة زر لكل استبدال نصي
    for i, (old_text, new_text) in enumerate(tag_replacements.items()):
        # اقتطاع النصوص الطويلة
        display_old = old_text[:15] + "..." if len(old_text) > 15 else old_text
        display_new = new_text[:15] + "..." if len(new_text) > 15 else new_text
        
        # استخدام رقم معرف بدلًا من النص الكامل
        markup.add(
            types.InlineKeyboardButton(
                f"{display_old} ➡️ {display_new}",
                callback_data=f"admin_remove_replacement_{i}"
            )
        )
    
    # إضافة أزرار إضافية
    markup.add(
        types.InlineKeyboardButton("➕ إضافة استبدال جديد", callback_data="admin_add_replacement")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing")
    )
    return markup

def get_admin_smart_templates_markup():
    """إنشاء أزرار صفحة القوالب الذكية"""
    # الحصول على القوالب الذكية الحالية
    smart_templates = admin_panel.get_setting("auto_processing.smart_templates", {})
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # إضافة زر لكل قالب ذكي
    for artist_name, template_id in smart_templates.items():
        # اقتطاع أسماء الفنانين الطويلة
        display_artist = artist_name[:25] + "..." if len(artist_name) > 25 else artist_name
        
        markup.add(
            types.InlineKeyboardButton(
                f"{display_artist} ➡️ {template_id}",
                callback_data=f"admin_edit_smart_template_{artist_name}"
            )
        )
    
    # إضافة أزرار إضافية
    markup.add(
        types.InlineKeyboardButton("➕ إضافة قالب ذكي جديد", callback_data="admin_add_smart_template")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing")
    )
    return markup

# Note: Esta función ha sido movida y mejorada más abajo en el archivo para evitar duplicación

def get_admin_backup_menu_markup():
    """إنشاء أزرار صفحة النسخ الاحتياطي والاسترجاع"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💾 تصدير بيانات البوت", callback_data="admin_export_data"),
        types.InlineKeyboardButton("📥 استيراد بيانات البوت", callback_data="admin_import_data")
    )
    markup.add(
        types.InlineKeyboardButton("💿 نسخ احتياطي للقوالب", callback_data="admin_export_templates"),
        types.InlineKeyboardButton("📀 استيراد القوالب", callback_data="admin_import_templates")
    )
    markup.add(
        types.InlineKeyboardButton("🧹 تنظيف الملفات المؤقتة", callback_data="admin_clean_temp")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_broadcast_menu_markup():
    """إنشاء أزرار صفحة إدارة البث الجماعي"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الحصول على عدد البث المجدول
    scheduled_broadcasts = admin_panel.get_setting("broadcasts.scheduled", [])
    scheduled_count = len(scheduled_broadcasts)
    
    markup.add(
        types.InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_send_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton("📅 جدولة رسالة جماعية", callback_data="admin_schedule_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton(f"📋 البث المجدول ({scheduled_count})", callback_data="admin_view_scheduled_broadcasts")
    )
    markup.add(
        types.InlineKeyboardButton("🎯 تحديد فئة محددة", callback_data="admin_target_broadcast")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_notifications_markup():
    """إنشاء أزرار صفحة إدارة الإشعارات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الحصول على حالة الإشعارات
    admin_notifications = admin_panel.get_setting("notifications.admin", True)
    admin_status = "✅" if admin_notifications else "❌"
    
    error_notifications = admin_panel.get_setting("notifications.errors", True)
    error_status = "✅" if error_notifications else "❌"
    
    user_notifications = admin_panel.get_setting("notifications.users", False)
    user_status = "✅" if user_notifications else "❌"
    
    markup.add(
        types.InlineKeyboardButton(f"👮‍♂️ إشعارات المشرفين: {admin_status}", callback_data="admin_toggle_admin_notifications"),
        types.InlineKeyboardButton(f"⚠️ إشعارات الأخطاء: {error_status}", callback_data="admin_toggle_error_notifications")
    )
    markup.add(
        types.InlineKeyboardButton(f"👥 إشعارات المستخدمين: {user_status}", callback_data="admin_toggle_user_notifications")
    )
    markup.add(
        types.InlineKeyboardButton("✏️ تخصيص رسائل الإشعارات", callback_data="admin_customize_notifications")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_logs_markup():
    """إنشاء أزرار صفحة السجلات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 سجل العمليات", callback_data="admin_action_logs"),
        types.InlineKeyboardButton("⚠️ سجل الأخطاء", callback_data="admin_error_logs")
    )
    markup.add(
        types.InlineKeyboardButton("👤 سجل عمليات مستخدم", callback_data="admin_user_logs"),
        types.InlineKeyboardButton("📊 إحصائيات السجل", callback_data="admin_log_stats")
    )
    markup.add(
        types.InlineKeyboardButton("🧹 تنظيف السجلات", callback_data="admin_clear_logs")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_tools_markup():
    """إنشاء أزرار صفحة أدوات الصيانة"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔄 إعادة تعيين حد المستخدمين", callback_data="admin_reset_user_limits"),
        types.InlineKeyboardButton("🧹 تنظيف الملفات المؤقتة", callback_data="admin_clean_temp")
    )
    markup.add(
        types.InlineKeyboardButton("📊 حالة النظام", callback_data="admin_system_status"),
        types.InlineKeyboardButton("🔍 اختبار ميزات البوت", callback_data="admin_test_features")
    )
    markup.add(
        types.InlineKeyboardButton("🏗 الصيانة التلقائية", callback_data="admin_auto_maintenance")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

# Note: Esta función ha sido movida y mejorada más abajo en el archivo
# para evitar duplicación y errores de LSP

def get_admin_settings_markup():
    """إنشاء أزرار صفحة الإعدادات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # تأكد من حالة الميزات المختلفة
    templates_status = "✅" if admin_panel.get_setting("features_enabled.templates", True) else "❌"
    lyrics_status = "✅" if admin_panel.get_setting("features_enabled.lyrics", True) else "❌"
    album_art_status = "✅" if admin_panel.get_setting("features_enabled.album_art", True) else "❌"
    required_subscription_status = "✅" if admin_panel.get_setting("features_enabled.required_subscription", False) else "❌"
    
    # الحصول على قيم الإعدادات الأخرى
    max_file_size = admin_panel.get_setting("max_file_size_mb", 50)
    processing_delay = admin_panel.get_setting("processing_delay", 0)
    daily_user_limit = admin_panel.get_setting("daily_user_limit_mb", 0)
    daily_limit_text = f"{daily_user_limit} ميجا" if daily_user_limit > 0 else "غير محدود"
    log_channel = admin_panel.get_setting("log_channel", "")
    log_channel_text = log_channel if log_channel else "غير معين"
    
    markup.add(
        types.InlineKeyboardButton(f"🔖 القوالب: {templates_status}", callback_data="admin_toggle_templates"),
        types.InlineKeyboardButton(f"📝 كلمات الأغاني: {lyrics_status}", callback_data="admin_toggle_lyrics")
    )
    markup.add(
        types.InlineKeyboardButton(f"🖼️ صور الألبومات: {album_art_status}", callback_data="admin_toggle_album_art"),
        types.InlineKeyboardButton(f"🔒 اشتراك إجباري: {required_subscription_status}", callback_data="admin_toggle_required_subscription")
    )
    markup.add(
        types.InlineKeyboardButton("📝 رسالة الترحيب", callback_data="admin_welcome_msg"),
        types.InlineKeyboardButton(f"📏 حد الملف: {max_file_size} ميجا", callback_data="admin_file_size")
    )
    markup.add(
        types.InlineKeyboardButton(f"⏱ تأخير المعالجة: {processing_delay}ث", callback_data="admin_processing_delay"),
        types.InlineKeyboardButton(f"🔄 حد يومي: {daily_limit_text}", callback_data="admin_daily_limit")
    )
    markup.add(
        types.InlineKeyboardButton("📢 قنوات الاشتراك", callback_data="admin_required_channels"),
        types.InlineKeyboardButton(f"📋 قناة السجل: {log_channel_text}", callback_data="admin_log_channel")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ إعدادات متقدمة", callback_data="admin_advanced_settings")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_advanced_settings_markup():
    """إنشاء أزرار صفحة الإعدادات المتقدمة"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # تأكد من حالة الميزات المتقدمة
    auto_tags_status = "✅" if admin_panel.get_setting("features_enabled.auto_tags", False) else "❌"
    audio_watermark_status = "✅" if admin_panel.get_setting("audio_watermark.enabled", False) else "❌"
    
    markup.add(
        types.InlineKeyboardButton(f"🏷️ الوسوم التلقائية: {auto_tags_status}", callback_data="admin_auto_tags"),
        types.InlineKeyboardButton(f"💧 علامة مائية صوتية: {audio_watermark_status}", callback_data="admin_audio_watermark")
    )
    markup.add(
        types.InlineKeyboardButton("📝 وصف البوت", callback_data="admin_bot_description"),
        types.InlineKeyboardButton("📖 ملاحظات الاستخدام", callback_data="admin_usage_notes")
    )
    markup.add(
        types.InlineKeyboardButton("♻️ إعادة تعيين حدود المستخدمين", callback_data="admin_reset_all_limits")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
    )
    return markup

def get_admin_auto_processing_markup():
    """إنشاء أزرار صفحة التعديل التلقائي للقنوات"""
    auto_proc_enabled = admin_panel.get_setting("features_enabled.auto_processing", False)
    forward_to_target_enabled = admin_panel.get_setting("auto_processing.forward_to_target", False)
    status = "✅ مفعّل" if auto_proc_enabled else "❌ معطّل"
    forward_status = "✅ مفعّل" if forward_to_target_enabled else "❌ معطّل"
    
    # الحصول على إعدادات المعالجة التلقائية
    source_channel = admin_panel.get_setting("auto_processing.source_channel", "غير محدد")
    target_channel = admin_panel.get_setting("auto_processing.target_channel", "غير محدد")
    tag_replacements_count = len(admin_panel.get_setting("auto_processing.tag_replacements", {}))
    smart_templates_count = len(admin_panel.get_setting("auto_processing.smart_templates", {}))
    footer_enabled = admin_panel.get_setting("auto_processing.tag_footer_enabled", False)
    footer_status = "✅ مفعّل" if footer_enabled else "❌ معطّل"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"{'⏸️ إيقاف' if auto_proc_enabled else '▶️ تفعيل'} التعديل التلقائي", 
            callback_data="admin_toggle_auto_processing")
    )
    markup.add(
        types.InlineKeyboardButton(f"📡 قناة المصدر: {source_channel}", 
            callback_data="admin_set_source_channel")
    )
    markup.add(
        types.InlineKeyboardButton(f"📡 قناة الهدف: {target_channel}", 
            callback_data="admin_set_target_channel")
    )
    markup.add(
        types.InlineKeyboardButton(f"{'⏸️ إيقاف' if forward_to_target_enabled else '▶️ تفعيل'} النشر التلقائي للقناة الهدف ({forward_status})", 
            callback_data="admin_toggle_forward_to_target")
    )
    markup.add(
        types.InlineKeyboardButton(f"🏷️ استبدالات الوسوم ({tag_replacements_count})", 
            callback_data="admin_tag_replacements")
    )
    markup.add(
        types.InlineKeyboardButton(f"🎯 القوالب الذكية ({smart_templates_count})", 
            callback_data="admin_smart_templates")
    )
    markup.add(
        types.InlineKeyboardButton(f"📝 تذييل الوسوم ({footer_status})", 
            callback_data="admin_tag_footer")
    )
    
    markup.add(
        types.InlineKeyboardButton("⚙️ إعدادات متقدمة", 
            callback_data="admin_auto_proc_settings")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", 
            callback_data="admin_panel")
    )
    return markup
    
def get_admin_smart_rules_markup():
    """إنشاء أزرار صفحة القواعد الذكية"""
    # الحصول على عدد القواعد الذكية
    smart_rules_count = 0
    try:
        with app.app_context():
            smart_rules_count = SmartRule.query.count()
    except Exception as e:
        logger.error(f"خطأ في الحصول على عدد القواعد الذكية: {e}")
        
    active_rules_count = 0
    try:
        with app.app_context():
            active_rules_count = SmartRule.query.filter_by(is_active=True).count()
    except Exception as e:
        logger.error(f"خطأ في الحصول على عدد القواعد الذكية النشطة: {e}")
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # معلومات حول القواعد
    markup.add(
        types.InlineKeyboardButton(f"📋 عرض القواعد الذكية ({smart_rules_count})", 
            callback_data="admin_view_smart_rules")
    )
    
    # إضافة قاعدة جديدة
    markup.add(
        types.InlineKeyboardButton("➕ إضافة قاعدة ذكية جديدة", 
            callback_data="admin_add_smart_rule")
    )
    
    # إحصائيات
    markup.add(
        types.InlineKeyboardButton(f"📊 القواعد النشطة: {active_rules_count} من {smart_rules_count}", 
            callback_data="admin_smart_rules_stats")
    )
    
    # تجربة القواعد
    markup.add(
        types.InlineKeyboardButton("🧪 تجربة القواعد الذكية على نص", 
            callback_data="admin_test_smart_rules")
    )
    
    # زر الرجوع
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", 
            callback_data="admin_panel")
    )
    
    return markup

def get_admin_image_watermark_markup():
    """إنشاء أزرار صفحة العلامة المائية للصور"""
    watermark_enabled = admin_panel.get_setting("image_watermark.enabled", False)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # زر تفعيل/تعطيل العلامة المائية
    markup.add(
        types.InlineKeyboardButton(
            f"{'✅' if watermark_enabled else '❌'} تفعيل العلامة المائية", 
            callback_data="admin_toggle_image_watermark"
        )
    )
    
    # إذا كانت العلامة المائية مفعلة، أظهر خيارات التعديل
    if watermark_enabled:
        # تعيين صورة العلامة المائية
        markup.add(
            types.InlineKeyboardButton("🖼️ تعيين صورة العلامة المائية", callback_data="admin_set_image_watermark")
        )
        
        # خيارات موضع العلامة المائية
        markup.add(
            types.InlineKeyboardButton("📍 تغيير موضع العلامة المائية", callback_data="admin_change_watermark_position")
        )
        
        # حجم وشفافية العلامة المائية في صف واحد
        markup.add(
            types.InlineKeyboardButton("📏 تغيير حجم العلامة المائية", callback_data="admin_change_watermark_size"),
            types.InlineKeyboardButton("🔍 تغيير شفافية العلامة المائية", callback_data="admin_change_watermark_opacity")
        )
        
        # التباعد من الحافة
        markup.add(
            types.InlineKeyboardButton("↔️ تغيير التباعد من الحافة", callback_data="admin_change_watermark_padding")
        )
    
    # زر الرجوع
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_proc_settings"))
    
    return markup

def get_admin_tag_footer_markup():
    """إنشاء أزرار صفحة تذييل الوسوم"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الحصول على إعدادات التذييل
    footer_enabled = admin_panel.get_setting("auto_processing.tag_footer_enabled", False)
    footer_text = admin_panel.get_setting("auto_processing.tag_footer", "")
    footer_tag_settings = admin_panel.get_setting("auto_processing.footer_tag_settings", {
        'artist': True,
        'album_artist': False,
        'album': False,
        'genre': False,
        'year': False,
        'composer': False,
        'comment': True,
        'title': False,
        'lyrics': True
    })
    
    # أزرار التفعيل والتعطيل
    footer_status = "✅ مفعّل" if footer_enabled else "❌ معطّل"
    markup.add(
        types.InlineKeyboardButton(f"{'⏸️ إيقاف' if footer_enabled else '▶️ تفعيل'} تذييل الوسوم", 
            callback_data="admin_toggle_tag_footer")
    )
    
    # تعديل نص التذييل
    footer_text_display = footer_text[:20] + "..." if footer_text and len(footer_text) > 20 else footer_text or "غير محدد"
    markup.add(
        types.InlineKeyboardButton(f"✏️ تعديل نص التذييل: {footer_text_display}", 
            callback_data="admin_edit_tag_footer")
    )
    
    # إعدادات الوسوم التي يضاف إليها التذييل
    markup.add(
        types.InlineKeyboardButton("⚙️ تخصيص الوسوم المضاف إليها التذييل", 
            callback_data="admin_footer_tag_settings")
    )
    
    # زر الرجوع
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing")
    )
    
    return markup

def get_admin_image_watermark_markup():
    """إنشاء أزرار صفحة العلامة المائية للصور"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الحصول على إعدادات العلامة المائية للصور
    watermark_enabled = admin_panel.get_setting("image_watermark.enabled", False)
    watermark_image = admin_panel.get_setting("image_watermark.file", "")
    watermark_position = admin_panel.get_setting("image_watermark.position", "bottom-right")
    watermark_size = admin_panel.get_setting("image_watermark.size_percent", 20)
    watermark_opacity = admin_panel.get_setting("image_watermark.opacity", 0.7)
    watermark_padding = admin_panel.get_setting("image_watermark.padding", 10)
    
    # حالة العلامة المائية
    status = "✅ مفعّلة" if watermark_enabled else "❌ معطّلة"
    markup.add(
        types.InlineKeyboardButton(f"{'⏸️ إيقاف' if watermark_enabled else '▶️ تفعيل'} العلامة المائية", 
            callback_data="admin_toggle_image_watermark")
    )
    
    # تعيين صورة العلامة المائية
    image_status = "تم تعيينها" if watermark_image else "غير محددة"
    markup.add(
        types.InlineKeyboardButton(f"🖼️ تعيين صورة العلامة المائية: {image_status}", 
            callback_data="admin_set_image_watermark")
    )
    
    # إعدادات العلامة المائية
    position_names = {
        "top-left": "أعلى اليسار",
        "top-right": "أعلى اليمين",
        "bottom-left": "أسفل اليسار",
        "bottom-right": "أسفل اليمين",
        "center": "الوسط"
    }
    position_name = position_names.get(watermark_position, watermark_position)
    
    markup.add(
        types.InlineKeyboardButton(f"📍 موضع العلامة: {position_name}", 
            callback_data="admin_change_watermark_position")
    )
    
    # حجم العلامة المائية
    markup.add(
        types.InlineKeyboardButton(f"📏 حجم العلامة: {watermark_size}%", 
            callback_data="admin_change_watermark_size")
    )
    
    # شفافية العلامة المائية
    opacity_percent = int(watermark_opacity * 100)
    markup.add(
        types.InlineKeyboardButton(f"🔍 شفافية العلامة: {opacity_percent}%", 
            callback_data="admin_change_watermark_opacity")
    )
    
    # التباعد من الحافة
    markup.add(
        types.InlineKeyboardButton(f"↔️ التباعد من الحافة: {watermark_padding} بكسل", 
            callback_data="admin_change_watermark_padding")
    )
    
    # زر الرجوع
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_proc_settings")
    )
    
    return markup

def get_admin_footer_tag_settings_markup():
    """إنشاء أزرار صفحة إعدادات الوسوم المضاف إليها التذييل"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الحصول على إعدادات الوسوم
    footer_tag_settings = admin_panel.get_setting("auto_processing.footer_tag_settings", {
        'artist': True,
        'album_artist': False,
        'album': False,
        'genre': False,
        'year': False,
        'composer': False,
        'comment': True,
        'title': False,
        'lyrics': True
    })
    
    # قائمة أسماء الوسوم بالعربية
    arabic_tags = {
        'artist': 'الفنان',
        'album_artist': 'فنان الألبوم',
        'album': 'الألبوم',
        'genre': 'النوع',
        'year': 'السنة',
        'composer': 'الملحن',
        'comment': 'تعليق',
        'title': 'العنوان',
        'lyrics': 'كلمات الأغنية'
    }
    
    # إنشاء أزرار تبديل حالة كل وسم
    for tag, is_enabled in footer_tag_settings.items():
        if tag in arabic_tags:
            button_text = f"{'✅' if is_enabled else '❌'} {arabic_tags[tag]}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=f"admin_toggle_footer_tag_{tag}"))
    
    # زر الرجوع
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tag_footer")
    )
    
    return markup

def get_admin_tag_replacements_markup():
    """إنشاء أزرار صفحة استبدالات الوسوم"""
    replacements = admin_panel.get_setting("auto_processing.tag_replacements", {})
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # عرض الاستبدالات الحالية
    if replacements:
        markup.add(types.InlineKeyboardButton("➕ إضافة استبدال جديد", callback_data="admin_add_replacement"))
        for old_text, new_text in replacements.items():
            if len(old_text) > 15:
                old_text_display = old_text[:15] + "..."
            else:
                old_text_display = old_text
                
            if len(new_text) > 15:
                new_text_display = new_text[:15] + "..."
            else:
                new_text_display = new_text
                
            button_text = f"🔄 {old_text_display} → {new_text_display}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=f"admin_edit_replacement_{old_text}"))
    else:
        markup.add(types.InlineKeyboardButton("➕ إضافة استبدال أول", callback_data="admin_add_replacement"))
        
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing"))
    return markup

def get_admin_smart_templates_markup():
    """إنشاء أزرار صفحة القوالب الذكية"""
    smart_templates = admin_panel.get_setting("auto_processing.smart_templates", {})
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # عرض القوالب الذكية الحالية
    if smart_templates:
        markup.add(types.InlineKeyboardButton("➕ إضافة قالب ذكي جديد", callback_data="admin_add_smart_template"))
        for artist, template_id in smart_templates.items():
            if len(artist) > 20:
                artist_display = artist[:20] + "..."
            else:
                artist_display = artist
                
            button_text = f"🎵 {artist_display}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=f"admin_edit_smart_template_{artist}"))
    else:
        markup.add(types.InlineKeyboardButton("➕ إضافة قالب ذكي أول", callback_data="admin_add_smart_template"))
        
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing"))
    return markup

def get_admin_auto_proc_settings_markup():
    """إنشاء أزرار صفحة إعدادات التعديل التلقائي المتقدمة"""
    keep_caption = admin_panel.get_setting("auto_processing.keep_caption", True)
    auto_publish = admin_panel.get_setting("auto_processing.auto_publish", True)
    remove_links = admin_panel.get_setting("auto_processing.remove_links", False)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"{'✅' if keep_caption else '❌'} الحفاظ على الكابشن الأصلي", 
            callback_data="admin_toggle_keep_caption")
    )
    markup.add(
        types.InlineKeyboardButton(f"{'✅' if auto_publish else '❌'} النشر التلقائي بعد التعديل", 
            callback_data="admin_toggle_auto_publish")
    )
    markup.add(
        types.InlineKeyboardButton(f"{'✅' if remove_links else '❌'} حذف الروابط من الوسوم تلقائياً", 
            callback_data="admin_toggle_remove_links")
    )
    
    # إدارة الوسوم المفعلة
    markup.add(types.InlineKeyboardButton("🏷️ إدارة الوسوم المفعلة", callback_data="admin_enabled_tags"))
    
    # القواعد الذكية
    markup.add(types.InlineKeyboardButton("🧠 القواعد الذكية", callback_data="admin_smart_rules"))
    
    # العلامة المائية للصور
    watermark_enabled = admin_panel.get_setting("image_watermark.enabled", False)
    watermark_status = "✅ مفعّلة" if watermark_enabled else "❌ معطّلة"
    markup.add(types.InlineKeyboardButton(f"🖼️ العلامة المائية للصور ({watermark_status})", callback_data="admin_image_watermark"))
    
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing"))
    return markup

def get_admin_enabled_tags_markup():
    """إنشاء أزرار صفحة إدارة الوسوم المفعلة للاستبدال"""
    enabled_tags = admin_panel.get_setting("auto_processing.enabled_tags", {
        'artist': True,
        'album_artist': True,
        'album': True,
        'genre': True,
        'year': True,
        'composer': True,
        'comment': True,
        'title': True
    })
    
    tag_arabic_names = {
        'title': 'العنوان',
        'artist': 'الفنان',
        'album': 'الألبوم',
        'album_artist': 'فنان الألبوم',
        'year': 'السنة',
        'genre': 'النوع',
        'composer': 'الملحن',
        'comment': 'تعليق'
    }
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for tag_name, enabled in enabled_tags.items():
        if tag_name in tag_arabic_names:
            arabic_name = tag_arabic_names[tag_name]
            markup.add(types.InlineKeyboardButton(
                f"{'✅' if enabled else '❌'} {arabic_name}",
                callback_data=f"admin_toggle_tag_{tag_name}"
            ))
    
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_proc_settings"))
    return markup
    
def get_admin_backup_menu_markup():
    """إنشاء أزرار صفحة النسخ الاحتياطي والاسترجاع"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💾 نسخة احتياطية كاملة", callback_data="admin_export_all"),
        types.InlineKeyboardButton("📥 استرجاع نسخة كاملة", callback_data="admin_import_all")
    )
    markup.add(
        types.InlineKeyboardButton("👥 تصدير المستخدمين", callback_data="admin_export_users"),
        types.InlineKeyboardButton("🗂️ تصدير القوالب", callback_data="admin_export_templates")
    )
    markup.add(
        types.InlineKeyboardButton("⚙️ تصدير الإعدادات", callback_data="admin_export_settings"),
        types.InlineKeyboardButton("📊 تصدير الإحصائيات", callback_data="admin_export_statistics")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_broadcast_menu_markup():
    """إنشاء أزرار صفحة إدارة البث الجماعي"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # الحصول على عدد الرسائل المجدولة
    scheduled_broadcasts = admin_panel.get_scheduled_broadcasts()
    pending_count = sum(1 for b in scheduled_broadcasts if not b.get('sent', False))
    
    markup.add(
        types.InlineKeyboardButton("📢 رسالة جماعية نصية", callback_data="admin_new_broadcast_text"),
        types.InlineKeyboardButton("🖼️ رسالة جماعية بصورة", callback_data="admin_new_broadcast_photo")
    )
    markup.add(
        types.InlineKeyboardButton("🎞️ رسالة جماعية بفيديو", callback_data="admin_new_broadcast_video"),
        types.InlineKeyboardButton("📎 رسالة جماعية بملف", callback_data="admin_new_broadcast_document")
    )
    markup.add(
        types.InlineKeyboardButton(f"📅 الرسائل المجدولة ({pending_count})", callback_data="admin_view_scheduled")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_tag_arabic_name(tag):
    """الحصول على الاسم العربي للوسم"""
    tag_names = {
        'artist': 'الفنان',
        'album_artist': 'فنان الألبوم',
        'album': 'الألبوم',
        'genre': 'النوع',
        'year': 'السنة',
        'comment': 'التعليق',
        'title': 'العنوان',
        'track': 'رقم المسار',
        'composer': 'الملحن',
        'lyrics': 'كلمات الأغنية'
    }
    return tag_names.get(tag, tag)

def get_admin_logs_markup():
    """إنشاء أزرار صفحة السجلات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📃 آخر العمليات", callback_data="admin_recent_logs"),
        types.InlineKeyboardButton("⚠️ سجل الأخطاء", callback_data="admin_error_logs")
    )
    markup.add(
        types.InlineKeyboardButton("👤 بحث حسب المستخدم", callback_data="admin_user_logs"),
        types.InlineKeyboardButton("🔍 بحث متقدم", callback_data="admin_search_logs")
    )
    markup.add(
        types.InlineKeyboardButton("📤 تصدير السجلات", callback_data="admin_export_logs"),
        types.InlineKeyboardButton("🗑️ مسح السجلات", callback_data="admin_clear_logs")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_tools_markup():
    """إنشاء أزرار صفحة أدوات الصيانة"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🧹 تنظيف الملفات المؤقتة", callback_data="admin_clean_temp"),
        types.InlineKeyboardButton("🔄 إعادة تشغيل البوت", callback_data="admin_restart_bot")
    )
    markup.add(
        types.InlineKeyboardButton("💾 عمل نسخة احتياطية", callback_data="admin_backup"),
        types.InlineKeyboardButton("⚡ حالة النظام", callback_data="admin_system_status")
    )
    markup.add(
        types.InlineKeyboardButton("📊 تشخيص الأداء", callback_data="admin_performance"),
        types.InlineKeyboardButton("🧪 اختبار الوظائف", callback_data="admin_test_features")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def get_admin_notifications_markup():
    """إنشاء أزرار صفحة إدارة الإشعارات"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # تأكد من حالة الإشعارات المختلفة
    new_users_status = "✅" if admin_panel.get_setting("notifications.new_users", True) else "❌"
    errors_status = "✅" if admin_panel.get_setting("notifications.errors", True) else "❌"
    
    markup.add(
        types.InlineKeyboardButton(f"👤 مستخدمين جدد: {new_users_status}", callback_data="admin_toggle_new_users_notif"),
        types.InlineKeyboardButton(f"⚠️ أخطاء: {errors_status}", callback_data="admin_toggle_errors_notif")
    )
    markup.add(
        types.InlineKeyboardButton("✉️ إعداد رسائل الإشعارات", callback_data="admin_notification_messages"),
        types.InlineKeyboardButton("⏰ جدولة تقارير دورية", callback_data="admin_schedule_reports")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    return markup

def format_timestamp(timestamp):
    """تنسيق الطابع الزمني إلى سلسلة نصية مقروءة"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def format_duration(seconds):
    """تنسيق المدة من الثواني إلى سلسلة نصية مقروءة"""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{int(days)} يوم")
    if hours > 0:
        parts.append(f"{int(hours)} ساعة")
    if minutes > 0:
        parts.append(f"{int(minutes)} دقيقة")
    if seconds > 0 or not parts:
        parts.append(f"{int(seconds)} ثانية")
    
    return " و ".join(parts)

def get_stats_message():
    """إنشاء رسالة الإحصائيات"""
    stats = admin_panel.admin_data['statistics']
    system_info = admin_panel.get_system_info()
    
    message = "📊 *إحصائيات البوت*\n\n"
    
    # إحصائيات الاستخدام
    message += "*📈 إحصائيات الاستخدام:*\n"
    message += f"• الملفات المعالجة: {stats['total_files_processed']}\n"
    message += f"• التعديلات الناجحة: {stats['successful_edits']}\n"
    message += f"• العمليات الفاشلة: {stats['failed_operations']}\n"
    message += f"• عدد المستخدمين: {len(admin_panel.admin_data['users'])}\n"
    message += f"• المستخدمين المحظورين: {len(admin_panel.admin_data['blocked_users'])}\n\n"
    
    # معلومات النظام
    message += "*💻 معلومات النظام:*\n"
    message += f"• استخدام المعالج: {system_info['cpu_percent']}%\n"
    message += f"• استخدام الذاكرة: {system_info['memory_percent']}%\n"
    message += f"• استخدام القرص: {system_info['disk_percent']}%\n"
    message += f"• وقت التشغيل: {format_duration(system_info['uptime'])}\n\n"
    
    # الأوقات
    message += "*⏱ الأوقات:*\n"
    message += f"• وقت بدء التشغيل: {format_timestamp(stats['bot_start_time'])}\n"
    message += f"• آخر إعادة تعيين: {format_timestamp(stats['last_reset_time'])}\n"
    
    return message

def get_user_list_message(users, title):
    """إنشاء رسالة قائمة المستخدمين"""
    message = f"👥 *{title}*\n\n"
    
    if not users:
        message += "لا يوجد مستخدمين."
        return message
    
    for i, user in enumerate(users, start=1):
        username = user.get('username', 'غير معروف')
        first_name = user.get('first_name', 'غير معروف')
        user_id = user.get('user_id', 'غير معروف')
        last_seen = format_timestamp(user.get('last_seen', 0))
        files_processed = user.get('files_processed', 0)
        
        message += f"{i}. *{first_name}* (@{username})\n"
        message += f"   • معرّف: {user_id}\n"
        message += f"   • آخر نشاط: {last_seen}\n"
        message += f"   • ملفات معالجة: {files_processed}\n\n"
        
        # تقسيم الرسائل الطويلة
        if i % 10 == 0 and i < len(users):
            message += "..."
            break
    
    return message

def get_logs_message(logs, title):
    """إنشاء رسالة سجل العمليات"""
    message = f"📋 *{title}*\n\n"
    
    if not logs:
        message += "لا يوجد سجلات."
        return message
    
    for i, log in enumerate(logs, start=1):
        time_str = format_timestamp(log.get('time', 0))
        user_id = log.get('user_id', 'غير معروف')
        action = log.get('action', 'غير معروف')
        status = log.get('status', 'غير معروف')
        status_emoji = "✅" if status == 'success' else "❌"
        details = log.get('details', '')
        
        message += f"{i}. *{action}* {status_emoji}\n"
        message += f"   • وقت: {time_str}\n"
        message += f"   • مستخدم: {user_id}\n"
        if details:
            message += f"   • تفاصيل: {details[:50]}{'...' if len(details) > 50 else ''}\n"
        message += "\n"
        
        # تقسيم الرسائل الطويلة
        if i % 5 == 0 and i < len(logs):
            message += "..."
            break
    
    return message

def get_system_status_message():
    """إنشاء رسالة حالة النظام"""
    system_info = admin_panel.get_system_info()
    
    message = "⚡ *حالة النظام*\n\n"
    
    # استخدام الموارد
    message += "*💻 استخدام الموارد:*\n"
    message += f"• استخدام المعالج: {system_info['cpu_percent']}%\n"
    message += f"• استخدام الذاكرة: {system_info['memory_percent']}%\n"
    message += f"• استخدام القرص: {system_info['disk_percent']}%\n\n"
    
    # معلومات التشغيل
    message += "*⏱ معلومات التشغيل:*\n"
    message += f"• وقت التشغيل: {format_duration(system_info['uptime'])}\n"
    
    # الملفات المؤقتة
    temp_dir = "temp_audio_files"
    temp_files_count = 0
    temp_files_size = 0
    if os.path.exists(temp_dir):
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                temp_files_count += 1
                temp_files_size += os.path.getsize(file_path)
    
    message += f"• عدد الملفات المؤقتة: {temp_files_count}\n"
    message += f"• حجم الملفات المؤقتة: {temp_files_size / (1024 * 1024):.2f} ميجابايت\n\n"
    
    # معلومات القواعد الذكية
    try:
        with app.app_context():
            smart_rules_count = SmartRule.query.count()
            active_rules_count = SmartRule.query.filter_by(is_active=True).count()
        
        message += "*🧠 القواعد الذكية:*\n"
        message += f"• عدد القواعد: {smart_rules_count}\n"
        message += f"• القواعد النشطة: {active_rules_count}\n"
    except Exception as e:
        logger.error(f"خطأ في الحصول على معلومات القواعد الذكية: {e}")
    
    return message

# دالة للتعامل مع جميع أزرار لوحة الإدارة
def handle_admin_callback(bot, call):
    """معالجة الأزرار الخاصة بلوحة الإدارة"""
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        
        # التأكد من أن المستخدم هو مشرف أو مطور
        is_dev = Config.is_developer(user_id)
        
        # إذا كان مطوراً ولكن ليس مشرفاً، أضفه كمشرف
        if is_dev and not admin_panel.is_admin(user_id):
            admin_panel.add_admin(user_id)
            logger.info(f"تمت إضافة مطور البوت {user_id} كمشرف تلقائياً")
        
        if not admin_panel.is_admin(user_id) and not is_dev:
            bot.answer_callback_query(call.id, "غير مصرح لك بالوصول إلى لوحة الإدارة.")
            return
        
        # إرسال إشعار استلام الضغطة للمستخدم
        bot.answer_callback_query(call.id)
        
        # سجل معلومات التتبع
        logger.info(f"معالجة زر لوحة الإدارة {call.data} للمستخدم {user_id}")
        
        # معالجة الأزرار المختلفة
        if call.data == "admin_panel":
            # عرض لوحة الإدارة الرئيسية
            bot.edit_message_text(
                "⚙️ *لوحة إدارة البوت*\n\nاختر إحدى الوظائف التالية:",
                chat_id, message_id,
                reply_markup=get_admin_panel_markup(),
                parse_mode="Markdown"
            )
        
        elif call.data == "admin_close":
            # إغلاق لوحة الإدارة
            bot.delete_message(chat_id, message_id)
            
        elif call.data == "admin_stats":
            # عرض إحصائيات البوت
            bot.edit_message_text(
                get_stats_message(),
                chat_id, message_id,
                reply_markup=get_admin_stats_markup(),
                parse_mode="Markdown"
            )
            
        elif call.data == "admin_reset_stats":
            # إعادة تعيين الإحصائيات
            admin_panel.reset_statistics()
            bot.answer_callback_query(call.id, "تمت إعادة تعيين الإحصائيات.")
            # تحديث الرسالة
            bot.edit_message_text(
                get_stats_message(),
                chat_id, message_id,
                reply_markup=get_admin_stats_markup(),
                parse_mode="Markdown"
            )
        
        elif call.data == "admin_back":
            # عودة إلى اللوحة الرئيسية
            bot.edit_message_text(
                "⚙️ *لوحة إدارة البوت*\n\nاختر إحدى الوظائف التالية:",
                chat_id, message_id,
                reply_markup=get_admin_panel_markup(),
                parse_mode="Markdown"
            )
            
        elif call.data == "admin_users":
            # عرض صفحة إدارة المستخدمين
            active_users = admin_panel.get_active_users(7)
            top_users = admin_panel.get_top_users(10)
            
            text = "*👥 إدارة المستخدمين*\n\n"
            text += f"🔹 *إجمالي المستخدمين:* {len(admin_panel.admin_data['users'])}\n"
            text += f"🔹 *المستخدمين النشطين (7 أيام):* {len(active_users)}\n"
            text += f"🔹 *المستخدمين المحظورين:* {len(admin_panel.admin_data['blocked_users'])}\n\n"
            text += "*اختر إحدى الخيارات التالية:*"
            
            bot.edit_message_text(
                text,
                chat_id, message_id,
                reply_markup=get_admin_users_markup(),
                parse_mode="Markdown"
            )
        
        elif call.data == "admin_tools":
            # عرض صفحة أدوات الصيانة
            bot.edit_message_text(
                "*🛠️ أدوات الصيانة*\n\nاختر أحد الأدوات التالية:",
                chat_id, message_id,
                reply_markup=get_admin_tools_markup(),
                parse_mode="Markdown"
            )
            
        else:
            # معالجة زر التعديل التلقائي للقنوات
            if call.data == "admin_auto_processing":
                bot.edit_message_text(
                    "🤖 *التعديل التلقائي للقنوات*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_auto_processing_markup(),
                    parse_mode="Markdown"
                )
            # معالجة زر إدارة البث الجماعي
            elif call.data == "admin_broadcast_menu":
                bot.edit_message_text(
                    "📢 *إدارة البث الجماعي*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_broadcast_menu_markup(),
                    parse_mode="Markdown"
                )
            # معالجة زر إدارة النسخ الاحتياطي
            elif call.data == "admin_backup_menu":
                bot.edit_message_text(
                    "💾 *النسخ الاحتياطي والاسترجاع*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_backup_menu_markup(),
                    parse_mode="Markdown"
                )
            # معالجة زر إدارة الإشعارات
            elif call.data == "admin_notifications":
                bot.edit_message_text(
                    "🔔 *إدارة الإشعارات*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_notifications_markup(),
                    parse_mode="Markdown"
                )
            # معالجة زر إدارة المستخدمين
            elif call.data == "admin_users":
                bot.edit_message_text(
                    "👥 *إدارة المستخدمين*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_users_markup(),
                    parse_mode="Markdown"
                )
            # معالجة زر إدارة القوالب
            elif call.data == "admin_templates":
                bot.edit_message_text(
                    "📂️ *إدارة القوالب*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_templates_markup(),
                    parse_mode="Markdown"
                )
            # معالجة زر إعدادات البوت
            elif call.data == "admin_settings":
                bot.edit_message_text(
                    "⚙️ *إعدادات البوت*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_settings_markup(),
                    parse_mode="Markdown"
                )
                
            # معالجة زر القواعد الذكية
            elif call.data == "admin_smart_rules":
                # الحصول على عدد القواعد الذكية
                smart_rules_count = 0
                active_rules_count = 0
                try:
                    with app.app_context():
                        smart_rules_count = SmartRule.query.count()
                        active_rules_count = SmartRule.query.filter_by(is_active=True).count()
                except Exception as e:
                    logger.error(f"خطأ في الحصول على عدد القواعد الذكية: {e}")
                
                bot.edit_message_text(
                    f"🧠 *القواعد الذكية*\n\n"
                    f"باستخدام هذه الميزة يمكنك تعليم البوت معالجة الملفات الصوتية بذكاء بناءً على شروط مخصصة.\n\n"
                    f"• *إجمالي القواعد*: {smart_rules_count}\n"
                    f"• *القواعد النشطة*: {active_rules_count}\n\n"
                    f"اختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_smart_rules_markup(),
                    parse_mode="Markdown"
                )
                
            # معالجة زر تجربة القواعد الذكية على نص
            elif call.data == "admin_test_smart_rules":
                # إنشاء قائمة بأنواع الحقول المتاحة للاختبار
                tag_fields = smart_rules.get_available_fields()
                field_options = []
                
                # تحضير أزرار اختيار نوع الحقل
                markup = types.InlineKeyboardMarkup(row_width=2)
                for field in tag_fields:
                    if field['id'] != '*':  # استبعاد خيار "جميع الحقول" للتجربة
                        markup.add(
                            types.InlineKeyboardButton(
                                f"{field['name']} ({field['id']})",
                                callback_data=f"admin_test_field_{field['id']}"
                            )
                        )
                
                # إضافة زر العودة
                markup.add(
                    types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_rules")
                )
                
                # عرض واجهة اختيار نوع الحقل
                bot.edit_message_text(
                    "🧪 *تجربة القواعد الذكية*\n\n"
                    "اختر نوع الحقل الذي تريد تجربة القواعد عليه:\n\n"
                    "سيتم تطبيق جميع القواعد الذكية النشطة على النص الذي ستقوم بإدخاله.",
                    chat_id, message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            # معالجة زر اختيار نوع الحقل للتجربة
            elif call.data.startswith("admin_test_field_"):
                field_id = call.data.replace("admin_test_field_", "")
                
                # تخزين نوع الحقل المختار في حالة المستخدم
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_test_text", {
                    'message_id': message_id,
                    'field_id': field_id
                })
                
                # توجيه المستخدم لإدخال النص
                field_name = next((field['name'] for field in smart_rules.get_available_fields() if field['id'] == field_id), field_id)
                
                bot.edit_message_text(
                    f"🧪 *تجربة القواعد الذكية - {field_name}*\n\n"
                    f"قم بإرسال النص الذي تريد تجربة القواعد عليه كحقل *{field_name}*.\n\n"
                    f"سيتم تطبيق جميع القواعد الذكية النشطة على النص الذي سترسله ومن ثم عرض النتيجة.",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 إلغاء", callback_data="admin_test_smart_rules")
                    ),
                    parse_mode="Markdown"
                )
            
            # معالجة زر سجل العمليات
            elif call.data == "admin_logs":
                bot.edit_message_text(
                    "📋 *سجل العمليات*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_logs_markup(),
                    parse_mode="Markdown"
                )
            # معالجة زر أدوات الصيانة
            elif call.data == "admin_tools":
                bot.edit_message_text(
                    "🛠️ *أدوات الصيانة*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_tools_markup(),
                    parse_mode="Markdown"
                )
            # معالجة أزرار التعديل التلقائي للقنوات
            elif call.data == "admin_toggle_auto_processing":
                # تبديل حالة تفعيل المعالجة التلقائية
                current_state = admin_panel.get_setting("features_enabled.auto_processing", False)
                admin_panel.update_setting("features_enabled.auto_processing", not current_state)
                new_state = not current_state
                state_text = "تفعيل" if new_state else "تعطيل"
                
                bot.answer_callback_query(call.id, f"تم {state_text} المعالجة التلقائية للقنوات.")
                
                # تحديث واجهة التعديل التلقائي
                bot.edit_message_text(
                    "🤖 *التعديل التلقائي للقنوات*\n\nاختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_auto_processing_markup(),
                    parse_mode="Markdown"
                )
                
                # تسجيل العملية
                admin_panel.log_action(
                    user_id, 
                    f"auto_processing_{state_text}", 
                    "success", 
                    f"تم {state_text} المعالجة التلقائية للقنوات"
                )
                
            elif call.data == "admin_set_source_channel":
                # إرسال رسالة للمستخدم لطلب إدخال معرف القناة
                msg = bot.send_message(
                    chat_id,
                    "📝 *تعيين قناة المصدر للمعالجة التلقائية*\n\n"
                    "أرسل معرف القناة بالتنسيق التالي:\n"
                    "- معرف القناة العامة: مثل `@channel_name`\n"
                    "- معرف القناة الخاصة: مثل `-1001234567890`\n\n"
                    "🔄 أو أرسل `الغاء` للإلغاء.",
                    parse_mode="Markdown"
                )
                
                # تعيين حالة المستخدم للانتظار لإدخال معرف القناة
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_source_channel", {"message_id": msg.message_id})
                
            elif call.data == "admin_set_target_channel":
                # إرسال رسالة للمستخدم لطلب إدخال معرف قناة الهدف
                msg = bot.send_message(
                    chat_id,
                    "📝 *تعيين قناة الهدف للنشر التلقائي*\n\n"
                    "أرسل معرف القناة بالتنسيق التالي:\n"
                    "- معرف القناة العامة: مثل `@channel_name`\n"
                    "- معرف القناة الخاصة: مثل `-1001234567890`\n\n"
                    "🔄 أو أرسل `الغاء` للإلغاء.",
                    parse_mode="Markdown"
                )
                
                # تعيين حالة المستخدم للانتظار لإدخال معرف قناة الهدف
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_target_channel", {"message_id": msg.message_id})
                
            elif call.data == "admin_toggle_forward_to_target":
                # تبديل حالة النشر التلقائي للقناة الهدف
                current_state = admin_panel.get_setting("auto_processing.forward_to_target", False)
                new_state = not current_state
                
                # تحديث الحالة
                admin_panel.set_forward_to_target(new_state)
                
                # إرسال رسالة تأكيد
                status = "✅ تفعيل" if new_state else "❌ تعطيل"
                bot.answer_callback_query(
                    call.id,
                    f"تم {status} ميزة النشر التلقائي للقناة الهدف",
                    show_alert=True
                )
                
                # تحديث لوحة الإدارة
                bot.edit_message_text(
                    "⚙️ *إدارة التعديل التلقائي للقنوات*\n\n"
                    "يمكنك تعديل إعدادات المعالجة التلقائية للملفات الصوتية في القنوات من هنا.",
                    chat_id, message_id,
                    reply_markup=get_admin_auto_processing_markup(),
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_tag_replacements":
                # عرض صفحة استبدالات الوسوم
                try:
                    # استخدام كيبورد بسيط 
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    
                    # إضافة زر تفعيل/تعطيل الاستبدالات
                    replacements_enabled = admin_panel.get_setting("auto_processing.replacements_enabled", True)
                    status_text = "✅ مفعل" if replacements_enabled else "❌ معطل"
                    markup.add(
                        types.InlineKeyboardButton(f"حالة الاستبدالات: {status_text}", 
                                                 callback_data="admin_toggle_replacements")
                    )
                    
                    # زر إضافة استبدال جديد
                    markup.add(types.InlineKeyboardButton("➕ إضافة استبدال جديد", callback_data="admin_add_replacement"))
                    
                    # عرض الاستبدالات الحالية
                    replacements = admin_panel.get_setting("auto_processing.tag_replacements", {})
                    text = "🏷️ *استبدالات الوسوم للتعديل التلقائي*\n\n"
                    
                    if replacements:
                        text += f"الاستبدالات الحالية ({len(replacements)}):\n\n"
                        for i, (old_text, new_text) in enumerate(replacements.items()):
                            # تنظيف النصوص من أحرف السطر الجديد
                            old_clean = old_text.replace('\n', ' ').strip()
                            new_clean = new_text.replace('\n', ' ').strip()
                            
                            # اقتصار النصوص الطويلة
                            if len(old_clean) > 20:
                                old_clean = old_clean[:20] + "..."
                            if len(new_clean) > 20:
                                new_clean = new_clean[:20] + "..."
                                
                            text += f"{i+1}. `{old_clean}` ➡️ `{new_clean}`\n"
                        
                        # إضافة زر حذف استبدال
                        markup.add(types.InlineKeyboardButton("🗑️ حذف استبدال", callback_data="admin_delete_replacement"))
                        
                        # إضافة زر حذف كل الاستبدالات
                        markup.add(types.InlineKeyboardButton("🗑️ حذف كل الاستبدالات", callback_data="admin_delete_all_replacements"))
                    else:
                        text += "لا توجد استبدالات مضافة حتى الآن."
                    
                    text += "\n\nهذه النصوص سيتم استبدالها تلقائياً في وسوم الملفات الصوتية التي تنشر في قنوات المصدر."
                    
                    # حالة التفعيل
                    if not replacements_enabled:
                        text += "\n\n⚠️ *ملاحظة: الاستبدالات معطلة حالياً. اضغط على زر التفعيل لتشغيلها.*"
                    
                    # إضافة زر الرجوع
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing"))
                    
                    bot.edit_message_text(
                        text,
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطأ في عرض صفحة استبدالات الوسوم: {e}")
                    bot.edit_message_text(
                        "❌ حدث خطأ أثناء عرض استبدالات الوسوم.",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing")
                        )
                    )
                
            elif call.data == "admin_smart_templates":
                # عرض صفحة القوالب الذكية
                try:
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    
                    # إضافة زر تفعيل/تعطيل القوالب الذكية
                    templates_enabled = admin_panel.get_setting("auto_processing.smart_templates_enabled", True)
                    status_text = "✅ مفعل" if templates_enabled else "❌ معطل"
                    markup.add(
                        types.InlineKeyboardButton(f"حالة القوالب الذكية: {status_text}", 
                                                 callback_data="admin_toggle_smart_templates")
                    )
                    
                    # زر إضافة قالب ذكي جديد
                    markup.add(types.InlineKeyboardButton("➕ إضافة قالب ذكي", callback_data="admin_add_smart_template"))
                    
                    # عرض القوالب الذكية الحالية
                    smart_templates = admin_panel.get_setting("auto_processing.smart_templates", {})
                    text = "🎯 *القوالب الذكية للتعديل التلقائي*\n\n"
                    
                    if smart_templates:
                        text += f"القوالب الذكية الحالية ({len(smart_templates)}):\n\n"
                        for i, (artist, template_id) in enumerate(smart_templates.items()):
                            # اقتصار النصوص الطويلة
                            artist_name = artist
                            if len(artist_name) > 25:
                                artist_name = artist_name[:25] + "..."
                                
                            text += f"{i+1}. الفنان: `{artist_name}` \n   القالب: `{template_id}`\n\n"
                        
                        # إضافة زر حذف قالب ذكي
                        markup.add(types.InlineKeyboardButton("🗑️ حذف قالب ذكي", callback_data="admin_delete_smart_template"))
                        
                        # إضافة زر حذف كل القوالب الذكية
                        markup.add(types.InlineKeyboardButton("🗑️ حذف كل القوالب الذكية", callback_data="admin_delete_all_smart_templates"))
                    else:
                        text += "لا توجد قوالب ذكية مضافة حتى الآن."
                    
                    text += "\n\nسيتم تطبيق هذه القوالب تلقائياً على الملفات الصوتية حسب اسم الفنان."
                    
                    # حالة التفعيل
                    if not templates_enabled:
                        text += "\n\n⚠️ *ملاحظة: القوالب الذكية معطلة حالياً. اضغط على زر التفعيل لتشغيلها.*"
                    
                    # إضافة زر الرجوع
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing"))
                    
                    bot.edit_message_text(
                        text,
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطأ في عرض صفحة القوالب الذكية: {e}")
                    bot.edit_message_text(
                        "❌ حدث خطأ أثناء عرض القوالب الذكية.",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing")
                        )
                    )
                
            elif call.data == "admin_auto_proc_settings":
                # عرض صفحة الإعدادات المتقدمة للتعديل التلقائي
                bot.edit_message_text(
                    "⚙️ *إعدادات التعديل التلقائي المتقدمة*\n\n"
                    "اضبط خيارات التعديل التلقائي للقنوات.",
                    chat_id, message_id,
                    reply_markup=get_admin_auto_proc_settings_markup(),
                    parse_mode="Markdown"
                )
                
            # معالجة زر العلامة المائية للصور
            elif call.data == "admin_image_watermark":
                # عرض صفحة العلامة المائية للصور
                bot.edit_message_text(
                    "🖼️ *العلامة المائية للصور*\n\n"
                    "يمكنك إضافة علامة مائية على الصور تلقائياً (صورة الألبوم).\n\n"
                    "اختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_image_watermark_markup(),
                    parse_mode="Markdown"
                )
            
            # معالجة تفعيل/تعطيل العلامة المائية
            elif call.data == "admin_toggle_image_watermark":
                watermark_enabled = admin_panel.get_setting("image_watermark.enabled", False)
                if admin_panel.enable_image_watermark(not watermark_enabled):
                    bot.answer_callback_query(call.id, f"تم {'تعطيل' if watermark_enabled else 'تفعيل'} العلامة المائية للصور بنجاح")
                    
                    # إعادة تحميل صفحة العلامة المائية
                    handle_admin_callback(bot, types.CallbackQuery(
                        id=call.id, from_user=call.from_user, message=call.message, 
                        data="admin_image_watermark", chat_instance=call.chat_instance
                    ))
                else:
                    bot.answer_callback_query(call.id, "حدث خطأ أثناء تغيير حالة العلامة المائية")
            
            # معالجة تغيير موضع العلامة المائية
            elif call.data == "admin_change_watermark_position":
                current_position = admin_panel.get_setting("image_watermark.position", "bottom-right")
                
                # إنشاء قائمة المواضع
                positions = [
                    ("top-left", "أعلى اليسار"),
                    ("top-right", "أعلى اليمين"),
                    ("bottom-left", "أسفل اليسار"),
                    ("bottom-right", "أسفل اليمين"),
                    ("center", "الوسط")
                ]
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                for pos_id, pos_name in positions:
                    selected = "✅ " if pos_id == current_position else ""
                    markup.add(types.InlineKeyboardButton(f"{selected}{pos_name}", callback_data=f"admin_set_watermark_position_{pos_id}"))
                
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_image_watermark"))
                
                bot.edit_message_text(
                    "📍 *اختر موضع العلامة المائية*\n\n"
                    "حدد مكان ظهور العلامة المائية على الصور:",
                    chat_id, message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            
            # معالجة تحديد موضع العلامة المائية
            elif call.data.startswith("admin_set_watermark_position_"):
                position = call.data.replace("admin_set_watermark_position_", "")
                
                if admin_panel.set_image_watermark_position(position):
                    bot.answer_callback_query(call.id, f"تم تغيير موضع العلامة المائية بنجاح")
                    
                    # إعادة تحميل صفحة العلامة المائية
                    handle_admin_callback(bot, types.CallbackQuery(
                        id=call.id, from_user=call.from_user, message=call.message, 
                        data="admin_image_watermark", chat_instance=call.chat_instance
                    ))
                else:
                    bot.answer_callback_query(call.id, "حدث خطأ أثناء تغيير موضع العلامة المائية")
            
            # معالجة تعيين حجم العلامة المائية
            elif call.data == "admin_change_watermark_size":
                # حفظ حالة المستخدم وإرسال رسالة طلب حجم العلامة المائية
                from bot import set_user_state
                set_user_state(call.from_user.id, "admin_waiting_for_watermark_size")
                bot.send_message(
                    chat_id,
                    "📏 *تعديل حجم العلامة المائية*\n\n"
                    "يرجى إدخال نسبة حجم العلامة المائية (1-100%):",
                    parse_mode="Markdown",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 إلغاء", callback_data="admin_image_watermark")
                    )
                )
            
            # معالجة تعيين شفافية العلامة المائية
            elif call.data == "admin_change_watermark_opacity":
                # حفظ حالة المستخدم وإرسال رسالة طلب شفافية العلامة المائية
                from bot import set_user_state
                set_user_state(call.from_user.id, "admin_waiting_for_watermark_opacity")
                bot.send_message(
                    chat_id,
                    "🔍 *تعديل شفافية العلامة المائية*\n\n"
                    "يرجى إدخال نسبة شفافية العلامة المائية (1-100%):",
                    parse_mode="Markdown",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 إلغاء", callback_data="admin_image_watermark")
                    )
                )
            
            # معالجة تعيين التباعد من الحافة
            elif call.data == "admin_change_watermark_padding":
                # حفظ حالة المستخدم وإرسال رسالة طلب التباعد
                from bot import set_user_state
                set_user_state(call.from_user.id, "admin_waiting_for_watermark_padding")
                bot.send_message(
                    chat_id,
                    "↔️ *تعديل التباعد من الحافة*\n\n"
                    "يرجى إدخال قيمة التباعد من الحافة بالبكسل (1-100):",
                    parse_mode="Markdown",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 إلغاء", callback_data="admin_image_watermark")
                    )
                )
            
            # معالجة تعيين صورة العلامة المائية
            elif call.data == "admin_set_image_watermark":
                # حفظ حالة المستخدم وإرسال رسالة طلب صورة العلامة المائية
                from bot import set_user_state
                set_user_state(call.from_user.id, "admin_waiting_for_watermark_image")
                bot.send_message(
                    chat_id,
                    "🖼️ *تعيين صورة العلامة المائية*\n\n"
                    "يرجى إرسال صورة PNG شفافة لاستخدامها كعلامة مائية.\n"
                    "ملاحظة: يفضل أن تكون الصورة شفافة للحصول على أفضل نتيجة.",
                    parse_mode="Markdown",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 إلغاء", callback_data="admin_image_watermark")
                    )
                )
                
            elif call.data == "admin_enabled_tags":
                # عرض صفحة إدارة الوسوم المفعلة للاستبدال
                bot.edit_message_text(
                    "🏷️ *إدارة الوسوم المفعلة للاستبدال*\n\n"
                    "هذه الوسوم هي التي سيتم تعديلها تلقائياً عند المعالجة.",
                    chat_id, message_id,
                    reply_markup=get_admin_enabled_tags_markup(),
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_toggle_keep_caption":
                # تبديل خيار الحفاظ على الكابشن الأصلي
                current_state = admin_panel.get_setting("auto_processing.keep_caption", True)
                admin_panel.update_setting("auto_processing.keep_caption", not current_state)
                
                new_state = not current_state
                state_text = "تفعيل" if new_state else "تعطيل"
                bot.answer_callback_query(call.id, f"تم {state_text} الحفاظ على الكابشن الأصلي.")
                
                # تحديث واجهة الإعدادات المتقدمة
                bot.edit_message_text(
                    "⚙️ *إعدادات التعديل التلقائي المتقدمة*\n\n"
                    "اضبط خيارات التعديل التلقائي للقنوات.",
                    chat_id, message_id,
                    reply_markup=get_admin_auto_proc_settings_markup(),
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_toggle_auto_publish":
                # تبديل خيار النشر التلقائي
                current_state = admin_panel.get_setting("auto_processing.auto_publish", True)
                admin_panel.update_setting("auto_processing.auto_publish", not current_state)
                
                new_state = not current_state
                state_text = "تفعيل" if new_state else "تعطيل"
                bot.answer_callback_query(call.id, f"تم {state_text} النشر التلقائي بعد التعديل.")
                
                # تحديث واجهة الإعدادات المتقدمة
                bot.edit_message_text(
                    "⚙️ *إعدادات التعديل التلقائي المتقدمة*\n\n"
                    "اضبط خيارات التعديل التلقائي للقنوات.",
                    chat_id, message_id,
                    reply_markup=get_admin_auto_proc_settings_markup(),
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_toggle_remove_links":
                # تبديل خيار حذف الروابط تلقائياً
                current_state = admin_panel.get_setting("auto_processing.remove_links", False)
                admin_panel.update_setting("auto_processing.remove_links", not current_state)
                
                new_state = not current_state
                state_text = "تفعيل" if new_state else "تعطيل"
                bot.answer_callback_query(call.id, f"تم {state_text} حذف الروابط من الوسوم تلقائياً.")
                
                # تحديث واجهة الإعدادات المتقدمة
                bot.edit_message_text(
                    "⚙️ *إعدادات التعديل التلقائي المتقدمة*\n\n"
                    "اضبط خيارات التعديل التلقائي للقنوات.",
                    chat_id, message_id,
                    reply_markup=get_admin_auto_proc_settings_markup(),
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_toggle_replacements":
                # تبديل حالة تفعيل الاستبدالات
                current_state = admin_panel.get_setting("auto_processing.replacements_enabled", True)
                admin_panel.update_setting("auto_processing.replacements_enabled", not current_state)
                
                new_state = not current_state
                state_text = "تفعيل" if new_state else "تعطيل"
                bot.answer_callback_query(call.id, f"تم {state_text} استبدالات الوسوم.")
                
                # تحديث واجهة استبدالات الوسوم
                # إعادة تحميل الواجهة (من خلال استدعاء admin_tag_replacements)
                call.data = "admin_tag_replacements"
                return handle_admin_callback(bot, call)
                
            elif call.data == "admin_toggle_smart_templates":
                # تبديل حالة تفعيل القوالب الذكية
                current_state = admin_panel.get_setting("auto_processing.smart_templates_enabled", True)
                admin_panel.update_setting("auto_processing.smart_templates_enabled", not current_state)
                
                new_state = not current_state
                state_text = "تفعيل" if new_state else "تعطيل"
                bot.answer_callback_query(call.id, f"تم {state_text} القوالب الذكية.")
                
                # تحديث واجهة القوالب الذكية
                # إعادة تحميل الواجهة (من خلال استدعاء admin_smart_templates)
                call.data = "admin_smart_templates"
                return handle_admin_callback(bot, call)
                
            elif call.data == "admin_delete_replacement":
                # حذف استبدال
                msg = bot.send_message(
                    chat_id,
                    "🗑️ *حذف استبدال*\n\n"
                    "أرسل رقم الاستبدال الذي تريد حذفه من القائمة.\n\n"
                    "🔄 أو أرسل `الغاء` للإلغاء.",
                    parse_mode="Markdown"
                )
                
                # تعيين حالة المستخدم لانتظار رقم الاستبدال
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_replacement_number", {"message_id": msg.message_id})
                
            elif call.data == "admin_delete_all_replacements":
                # حذف كل الاستبدالات
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("✅ نعم، حذف الكل", callback_data="admin_confirm_delete_all_replacements"),
                    types.InlineKeyboardButton("❌ إلغاء", callback_data="admin_tag_replacements")
                )
                
                bot.edit_message_text(
                    "⚠️ *تأكيد حذف كل الاستبدالات*\n\n"
                    "هل أنت متأكد من أنك تريد حذف جميع استبدالات الوسوم؟\n"
                    "هذا الإجراء لا يمكن التراجع عنه.",
                    chat_id, message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_confirm_delete_all_replacements":
                # تأكيد حذف كل الاستبدالات
                admin_panel.update_setting("auto_processing.tag_replacements", {})
                bot.answer_callback_query(call.id, "تم حذف جميع استبدالات الوسوم بنجاح.")
                
                # العودة إلى صفحة الاستبدالات
                call.data = "admin_tag_replacements"
                return handle_admin_callback(bot, call)
                
            elif call.data == "admin_delete_smart_template":
                # حذف قالب ذكي
                msg = bot.send_message(
                    chat_id,
                    "🗑️ *حذف قالب ذكي*\n\n"
                    "أرسل رقم القالب الذي تريد حذفه من القائمة.\n\n"
                    "🔄 أو أرسل `الغاء` للإلغاء.",
                    parse_mode="Markdown"
                )
                
                # تعيين حالة المستخدم لانتظار رقم القالب
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_template_number", {"message_id": msg.message_id})
                
            elif call.data == "admin_delete_all_smart_templates":
                # حذف كل القوالب الذكية
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("✅ نعم، حذف الكل", callback_data="admin_confirm_delete_all_smart_templates"),
                    types.InlineKeyboardButton("❌ إلغاء", callback_data="admin_smart_templates")
                )
                
                bot.edit_message_text(
                    "⚠️ *تأكيد حذف كل القوالب الذكية*\n\n"
                    "هل أنت متأكد من أنك تريد حذف جميع القوالب الذكية؟\n"
                    "هذا الإجراء لا يمكن التراجع عنه.",
                    chat_id, message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_confirm_delete_all_smart_templates":
                # تأكيد حذف كل القوالب الذكية
                admin_panel.update_setting("auto_processing.smart_templates", {})
                bot.answer_callback_query(call.id, "تم حذف جميع القوالب الذكية بنجاح.")
                
                # العودة إلى صفحة القوالب الذكية
                call.data = "admin_smart_templates"
                return handle_admin_callback(bot, call)
                
            elif call.data == "admin_enabled_tags":
                # عرض صفحة الوسوم المفعلة للاستبدال
                try:
                    markup = get_admin_enabled_tags_markup()
                    bot.edit_message_text(
                        "🏷️ *إدارة الوسوم المفعلة للاستبدال*\n\n"
                        "حدد الوسوم التي تريد تفعيلها أو تعطيلها لعمليات الاستبدال التلقائي.\n"
                        "الوسوم المفعلة (✅) ستتم معالجتها واستبدال النصوص فيها، بينما الوسوم المعطلة (❌) لن يتم تغييرها.",
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطأ في عرض صفحة الوسوم المفعلة: {e}")
                    bot.edit_message_text(
                        "❌ حدث خطأ أثناء عرض صفحة الوسوم المفعلة.",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_proc_settings")
                        )
                    )
                    
            elif call.data.startswith("admin_toggle_tag_"):
                # تبديل حالة تفعيل/تعطيل وسم معين
                tag_name = call.data.replace("admin_toggle_tag_", "")
                
                # الحصول على الوسوم المفعلة الحالية
                enabled_tags = admin_panel.get_setting("auto_processing.enabled_tags", {
                    'artist': True,
                    'album_artist': True,
                    'album': True,
                    'genre': True,
                    'year': True,
                    'composer': True,
                    'comment': True,
                    'title': True,
                    'lyrics': True
                })
                
                # تبديل حالة الوسم
                current_state = enabled_tags.get(tag_name, True)
                enabled_tags[tag_name] = not current_state
                
                # حفظ التغييرات
                admin_panel.update_setting("auto_processing.enabled_tags", enabled_tags)
                
                # عرض رسالة تأكيد
                new_state = "تفعيل" if enabled_tags[tag_name] else "تعطيل"
                arabic_tags = {
                    'artist': 'الفنان',
                    'album_artist': 'فنان الألبوم',
                    'album': 'الألبوم',
                    'genre': 'النوع',
                    'year': 'السنة',
                    'composer': 'الملحن',
                    'comment': 'تعليق',
                    'title': 'العنوان',
                    'lyrics': 'كلمات الأغنية'
                }
                arabic_name = arabic_tags.get(tag_name, tag_name)
                bot.answer_callback_query(call.id, f"تم {new_state} وسم {arabic_name} بنجاح.")
                
                # تحديث واجهة الوسوم المفعلة
                markup = get_admin_enabled_tags_markup()
                bot.edit_message_text(
                    "🏷️ *إدارة الوسوم المفعلة للاستبدال*\n\n"
                    "حدد الوسوم التي تريد تفعيلها أو تعطيلها لعمليات الاستبدال التلقائي.\n"
                    "الوسوم المفعلة (✅) ستتم معالجتها واستبدال النصوص فيها، بينما الوسوم المعطلة (❌) لن يتم تغييرها.",
                    chat_id, message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_add_tag_replacement":
                # إرسال رسالة للمستخدم لطلب إدخال النص الأصلي
                msg = bot.send_message(
                    chat_id,
                    "📝 *إضافة استبدال نصي للوسوم*\n\n"
                    "أرسل النص الأصلي المراد استبداله.\n\n"
                    "🔄 أو أرسل `الغاء` للإلغاء.",
                    parse_mode="Markdown"
                )
                
                # تعيين حالة المستخدم للانتظار لإدخال النص الأصلي
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_old_text", {"message_id": msg.message_id})
                
            elif call.data == "admin_add_smart_template":
                # إرسال رسالة للمستخدم لطلب إدخال اسم الفنان
                msg = bot.send_message(
                    chat_id,
                    "📝 *إضافة قالب ذكي جديد*\n\n"
                    "أرسل اسم الفنان:\n\n"
                    "🔄 أو أرسل `الغاء` للإلغاء.",
                    parse_mode="Markdown"
                )
                
                # تعيين حالة المستخدم للانتظار لإدخال اسم الفنان
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_artist_name", {"message_id": msg.message_id})
                
            # معالجة أزرار الإعدادات
            elif call.data == "admin_welcome_msg":
                # تعيين رسالة الترحيب
                msg = bot.edit_message_text(
                    "📝 *تعديل رسالة الترحيب*\n\n"
                    "الرسالة الحالية:\n"
                    f"{admin_panel.get_setting('settings.welcome_message', 'غير محددة')}\n\n"
                    "أرسل الرسالة الجديدة:",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_welcome_msg", {"message_id": msg.message_id})
                
            elif call.data == "admin_file_size":
                # تعيين الحد الأقصى لحجم الملف
                current_size = admin_panel.get_setting("settings.max_file_size_mb", 50)
                msg = bot.edit_message_text(
                    "📊 *تعديل الحد الأقصى لحجم الملف*\n\n"
                    f"الحد الحالي: {current_size} ميجابايت\n\n"
                    "أرسل القيمة الجديدة بالميجابايت:",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_file_size", {"message_id": msg.message_id})
                
            elif call.data == "admin_processing_delay":
                # تعيين وقت التأخير بين معالجة الملفات
                current_delay = admin_panel.get_setting("settings.processing_delay", 0)
                msg = bot.edit_message_text(
                    "⏱️ *تعديل وقت التأخير بين المعالجة*\n\n"
                    f"الوقت الحالي: {current_delay} ثانية\n\n"
                    "أرسل القيمة الجديدة بالثواني:",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_delay", {"message_id": msg.message_id})
                
            elif call.data == "admin_daily_limit":
                # تعيين الحد اليومي للمستخدم
                current_limit = admin_panel.get_setting("settings.daily_user_limit_mb", 0)
                limit_str = f"{current_limit} ميجابايت" if current_limit > 0 else "غير محدود"
                msg = bot.edit_message_text(
                    "📈 *تعديل الحد اليومي للمستخدم*\n\n"
                    f"الحد الحالي: {limit_str}\n\n"
                    "أرسل القيمة الجديدة بالميجابايت (0 = غير محدود):",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_limit", {"message_id": msg.message_id})
                
            elif call.data == "admin_required_channels":
                # إدارة قنوات الاشتراك الإجباري
                channels = admin_panel.get_setting("settings.required_channels", [])
                channels_str = ""
                for idx, channel in enumerate(channels):
                    channels_str += f"{idx+1}. {channel['title']} ({channel['channel_id']})\n"
                
                if not channels_str:
                    channels_str = "لا توجد قنوات مضافة حاليًا."
                
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("➕ إضافة قناة", callback_data="admin_add_channel"),
                    types.InlineKeyboardButton("❌ إزالة قناة", callback_data="admin_remove_channel"),
                    types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
                )
                
                bot.edit_message_text(
                    "📢 *إدارة قنوات الاشتراك الإجباري*\n\n"
                    "القنوات الحالية:\n"
                    f"{channels_str}",
                    chat_id, message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_add_channel":
                # إضافة قناة اشتراك جديدة
                msg = bot.edit_message_text(
                    "📢 *إضافة قناة اشتراك إجباري*\n\n"
                    "أرسل معرف القناة بالتنسيق التالي:\n"
                    "- معرف القناة العامة: مثل @channel_name\n"
                    "- معرف القناة الخاصة: مثل -1001234567890\n\n"
                    "🔄 أو أرسل الغاء للإلغاء.",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_channel_id", {"message_id": msg.message_id})
                
            elif call.data == "admin_remove_channel":
                # إزالة قناة اشتراك
                channels = admin_panel.get_setting("settings.required_channels", [])
                if not channels:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_required_channels"))
                    bot.edit_message_text(
                        "📢 *إزالة قناة اشتراك إجباري*\n\n"
                        "لا توجد قنوات مضافة حاليًا.",
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                else:
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    for idx, channel in enumerate(channels):
                        markup.add(types.InlineKeyboardButton(
                            f"{channel['title']} ({channel['channel_id']})", 
                            callback_data=f"admin_del_channel_{idx}"
                        ))
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_required_channels"))
                    
                    bot.edit_message_text(
                        "📢 *إزالة قناة اشتراك إجباري*\n\n"
                        "اختر القناة التي تريد إزالتها:",
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    
            elif call.data.startswith("admin_del_channel_"):
                # حذف قناة محددة
                idx = int(call.data.split("_")[-1])
                channels = admin_panel.get_setting("settings.required_channels", [])
                if 0 <= idx < len(channels):
                    channel = channels[idx]
                    channels.pop(idx)
                    admin_panel.update_setting("settings.required_channels", channels)
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_required_channels"))
                    bot.edit_message_text(
                        f"✅ تم حذف القناة {channel['title']} بنجاح!",
                        chat_id, message_id,
                        reply_markup=markup
                    )
                    
            elif call.data == "admin_log_channel":
                # تعيين قناة السجل
                current_channel = admin_panel.get_setting("settings.log_channel", "")
                msg = bot.edit_message_text(
                    "📋 *تعيين قناة السجل*\n\n"
                    f"القناة الحالية: {current_channel or 'غير محددة'}\n\n"
                    "أرسل معرف القناة بالتنسيق التالي:\n"
                    "- معرف القناة العامة: مثل @channel_name\n"
                    "- معرف القناة الخاصة: مثل -1001234567890\n\n"
                    "أو أرسل `حذف` لإزالة قناة السجل الحالية.\n"
                    "🔄 أو أرسل الغاء للإلغاء.",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_log_channel", {"message_id": msg.message_id})
                
            elif call.data == "admin_advanced_settings":
                # الإعدادات المتقدمة
                markup = get_admin_advanced_settings_markup()
                bot.edit_message_text(
                    "⚙️ *الإعدادات المتقدمة*\n\n"
                    "اختر الإعداد الذي تريد تعديله:",
                    chat_id, message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_toggle_templates":
                # تفعيل/تعطيل ميزة القوالب
                current = admin_panel.get_setting("settings.features_enabled.templates", True)
                admin_panel.update_setting("settings.features_enabled.templates", not current)
                markup = get_admin_advanced_settings_markup()
                status = "✅ مفعلة" if not current else "❌ معطلة"
                bot.edit_message_text(
                    f"✅ تم تغيير حالة ميزة القوالب إلى: {status}",
                    chat_id, message_id,
                    reply_markup=markup
                )
                
            elif call.data == "admin_toggle_lyrics":
                # تفعيل/تعطيل ميزة كلمات الأغنية
                current = admin_panel.get_setting("settings.features_enabled.lyrics", True)
                admin_panel.update_setting("settings.features_enabled.lyrics", not current)
                markup = get_admin_advanced_settings_markup()
                status = "✅ مفعلة" if not current else "❌ معطلة"
                bot.edit_message_text(
                    f"✅ تم تغيير حالة ميزة كلمات الأغنية إلى: {status}",
                    chat_id, message_id,
                    reply_markup=markup
                )
                
            elif call.data == "admin_toggle_album_art":
                # تفعيل/تعطيل ميزة صورة الغلاف
                current = admin_panel.get_setting("settings.features_enabled.album_art", True)
                admin_panel.update_setting("settings.features_enabled.album_art", not current)
                markup = get_admin_advanced_settings_markup()
                status = "✅ مفعلة" if not current else "❌ معطلة"
                bot.edit_message_text(
                    f"✅ تم تغيير حالة ميزة صورة الغلاف إلى: {status}",
                    chat_id, message_id,
                    reply_markup=markup
                )
                
            elif call.data == "admin_toggle_required_subscription":
                # تفعيل/تعطيل الاشتراك الإجباري
                current = admin_panel.get_setting("settings.features_enabled.required_subscription", False)
                admin_panel.update_setting("settings.features_enabled.required_subscription", not current)
                markup = get_admin_advanced_settings_markup()
                status = "✅ مفعل" if not current else "❌ معطل"
                bot.edit_message_text(
                    f"✅ تم تغيير حالة الاشتراك الإجباري إلى: {status}",
                    chat_id, message_id,
                    reply_markup=markup
                )
                
            # معالجة أزرار صفحة الإحصائيات
            elif call.data == "admin_detailed_stats":
                # عرض إحصائيات مفصلة
                stats = admin_panel.get_setting("statistics", {})
                system_info = admin_panel.get_system_info()
                
                stats_text = "📊 *إحصائيات مفصلة للبوت*\n\n"
                stats_text += "*◉ إحصائيات المستخدمين:*\n"
                stats_text += f"• إجمالي المستخدمين: {len(admin_panel.get_setting('users', {}))}\n"
                stats_text += f"• المستخدمين النشطين (7 أيام): {len(admin_panel.get_active_users(7))}\n"
                stats_text += f"• المستخدمين المحظورين: {len(admin_panel.get_setting('blocked_users', []))}\n"
                stats_text += f"• المشرفين: {len(admin_panel.get_setting('admins', []))}\n\n"
                
                stats_text += "*◉ إحصائيات الملفات:*\n"
                stats_text += f"• إجمالي الملفات المعالجة: {stats.get('files_processed', 0)}\n"
                stats_text += f"• حجم الملفات المعالجة: {stats.get('processed_size_mb', 0):.2f} ميجابايت\n"
                stats_text += f"• متوسط حجم الملف: {stats.get('processed_size_mb', 0) / max(stats.get('files_processed', 1), 1):.2f} ميجابايت\n\n"
                
                stats_text += "*◉ إحصائيات الوسوم:*\n"
                stats_text += f"• تعديلات العنوان: {stats.get('tag_edits_title', 0)}\n"
                stats_text += f"• تعديلات الفنان: {stats.get('tag_edits_artist', 0)}\n"
                stats_text += f"• تعديلات الألبوم: {stats.get('tag_edits_album', 0)}\n"
                stats_text += f"• تعديلات كلمات الأغنية: {stats.get('tag_edits_lyrics', 0)}\n"
                stats_text += f"• تعديلات صورة الغلاف: {stats.get('tag_edits_albumart', 0)}\n\n"
                
                stats_text += "*◉ إحصائيات القوالب:*\n"
                stats_text += f"• عدد القوالب: {stats.get('templates_count', 0)}\n"
                stats_text += f"• مرات تطبيق القوالب: {stats.get('templates_applied', 0)}\n\n"
                
                stats_text += "*◉ إحصائيات النظام:*\n"
                stats_text += f"• استخدام المعالج: {system_info.get('cpu_percent', 0)}%\n"
                stats_text += f"• استخدام الذاكرة: {system_info.get('memory_percent', 0)}%\n"
                stats_text += f"• مساحة القرص المتاحة: {system_info.get('disk_free_gb', 0):.2f} جيجابايت\n"
                stats_text += f"• وقت تشغيل البوت: {format_duration(system_info.get('uptime_seconds', 0))}\n"
                
                markup = get_admin_stats_markup()
                bot.edit_message_text(
                    stats_text,
                    chat_id, message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
            # معالجة أزرار صفحة إدارة المستخدمين
            elif call.data == "admin_active_users":
                # عرض المستخدمين النشطين
                active_users = admin_panel.get_active_users(7)
                users_text = get_user_list_message(active_users, "المستخدمين النشطين في آخر 7 أيام")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_users"))
                
                bot.edit_message_text(
                    users_text, 
                    chat_id, message_id,
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_top_users":
                # عرض أكثر المستخدمين نشاطًا
                top_users = admin_panel.get_top_users(10)
                users_text = get_user_list_message(top_users, "أكثر المستخدمين نشاطًا")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_users"))
                
                bot.edit_message_text(
                    users_text, 
                    chat_id, message_id,
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_blocked_users":
                # عرض المستخدمين المحظورين
                blocked_ids = admin_panel.get_setting("blocked_users", [])
                blocked_users = []
                users_data = admin_panel.get_setting("users", {})
                
                for user_id in blocked_ids:
                    user_id = int(user_id)
                    user_data = users_data.get(str(user_id), {})
                    blocked_users.append({
                        "id": user_id,
                        "username": user_data.get("username", "غير معروف"),
                        "first_name": user_data.get("first_name", "غير معروف"),
                        "blocked_at": user_data.get("blocked_at", 0),
                        "files_processed": user_data.get("files_processed", 0)
                    })
                
                users_text = get_user_list_message(blocked_users, "المستخدمين المحظورين")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_users"))
                
                bot.edit_message_text(
                    users_text, 
                    chat_id, message_id,
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_admins":
                # عرض المشرفين
                admin_ids = admin_panel.get_setting("admins", [])
                admins = []
                users_data = admin_panel.get_setting("users", {})
                
                for user_id in admin_ids:
                    user_id = int(user_id)
                    user_data = users_data.get(str(user_id), {})
                    admins.append({
                        "id": user_id,
                        "username": user_data.get("username", "غير معروف"),
                        "first_name": user_data.get("first_name", "غير معروف"),
                        "added_at": user_data.get("admin_added_at", 0)
                    })
                
                users_text = get_user_list_message(admins, "المشرفين")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_users"))
                
                bot.edit_message_text(
                    users_text, 
                    chat_id, message_id,
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                
            # معالجة أزرار صفحة إدارة القوالب
            elif call.data == "admin_view_templates":
                # عرض جميع القوالب
                try:
                    from template_handler import get_all_templates
                    templates = get_all_templates()
                    
                    if not templates:
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                        bot.edit_message_text(
                            "📋 قائمة القوالب\n\n"
                            "لا توجد قوالب محفوظة حالياً.",
                            chat_id, message_id,
                            reply_markup=markup
                        )
                    else:
                        templates_text = "📋 قائمة القوالب\n\n"
                        for idx, template in enumerate(templates):
                            # استخدام نص عادي بدلاً من تنسيق Markdown
                            templates_text += f"{idx+1}. {template['name']} (الفنان: {template.get('artist', 'غير محدد')})\n"
                        
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                        
                        bot.edit_message_text(
                            templates_text,
                            chat_id, message_id,
                            reply_markup=markup
                        )
                except Exception as e:
                    logger.error(f"خطأ في عرض القوالب: {e}")
                    bot.answer_callback_query(call.id, "حدث خطأ أثناء محاولة عرض القوالب")
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                    bot.edit_message_text(
                        "❌ حدث خطأ أثناء محاولة عرض القوالب، يرجى المحاولة مرة أخرى.",
                        chat_id, message_id,
                        reply_markup=markup
                    )
                    
            elif call.data == "admin_create_template":
                # إنشاء قالب عام
                msg = bot.edit_message_text(
                    "✏️ *إنشاء قالب عام*\n\n"
                    "أرسل بيانات القالب بالتنسيق التالي:\n\n"
                    "الفنان: اسم الفنان\n"
                    "العنوان: عنوان الأغنية\n"
                    "الألبوم: اسم الألبوم\n"
                    "السنة: 2024\n"
                    "النوع: نوع الموسيقى\n"
                    "الملحن: اسم الملحن\n"
                    "التعليق: أي تعليق إضافي\n"
                    "الكلمات: كلمات الأغنية\n\n"
                    "🔄 أرسل `الغاء` للإلغاء.",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_template_data", {"message_id": msg.message_id})
                
            elif call.data == "admin_delete_template":
                # حذف قالب
                from template_handler import get_all_templates
                templates = get_all_templates()
                
                if not templates:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                    bot.edit_message_text(
                        "🗑️ *حذف قالب*\n\n"
                        "لا توجد قوالب محفوظة حالياً.",
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                else:
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    for idx, template in enumerate(templates):
                        markup.add(types.InlineKeyboardButton(
                            f"{template['name']} ({template.get('artist', 'غير محدد')})",
                            callback_data=f"admin_delete_template_{idx}"
                        ))
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                    
                    bot.edit_message_text(
                        "🗑️ *حذف قالب*\n\n"
                        "اختر القالب الذي تريد حذفه:",
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    
            elif call.data.startswith("admin_delete_template_"):
                # حذف قالب محدد
                idx = int(call.data.split("_")[-1])
                from template_handler import get_all_templates, delete_template
                templates = get_all_templates()
                
                if 0 <= idx < len(templates):
                    template = templates[idx]
                    template_name = template['name']
                    
                    from template_handler import get_template_path
                    template_path = get_template_path(template_name)
                    delete_result = delete_template(template_path)
                    
                    if delete_result:
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                        bot.edit_message_text(
                            f"✅ تم حذف القالب '{template_name}' بنجاح.",
                            chat_id, message_id,
                            reply_markup=markup
                        )
                    else:
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                        bot.edit_message_text(
                            f"❌ فشل في حذف القالب '{template_name}'.",
                            chat_id, message_id,
                            reply_markup=markup
                        )
                
            elif call.data == "admin_export_templates":
                # تصدير القوالب
                # تحديد مجلد للتصدير
                export_dir = "templates_export"
                os.makedirs(export_dir, exist_ok=True)
                
                from template_handler import export_all_templates
                export_path, count = export_all_templates(export_dir)
                
                if count > 0 and export_path:
                    # إرسال ملف التصدير
                    with open(export_path, 'rb') as export_file:
                        bot.send_document(
                            chat_id=chat_id,
                            document=export_file,
                            caption=f"✅ تم تصدير {count} قالب بنجاح."
                        )
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                    bot.edit_message_text(
                        f"✅ تم تصدير {count} قالب بنجاح. تم إرسال الملف.",
                        chat_id, message_id,
                        reply_markup=markup
                    )
                else:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_templates"))
                    bot.edit_message_text(
                        "❌ فشل تصدير القوالب أو لا توجد قوالب للتصدير.",
                        chat_id, message_id,
                        reply_markup=markup
                    )
                
            elif call.data == "admin_import_templates":
                # استيراد القوالب
                msg = bot.edit_message_text(
                    "📥 *استيراد القوالب*\n\n"
                    "أرسل ملف القوالب المضغوط (ZIP) لاستيراده.\n\n"
                    "🔄 أرسل `الغاء` للإلغاء.",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_templates_file", {"message_id": msg.message_id})
                
            # معالجة أزرار صفحة السجلات
            elif call.data == "admin_recent_logs":
                # عرض آخر السجلات
                recent_logs = admin_panel.get_recent_logs(20)
                logs_text = get_logs_message(recent_logs, "آخر السجلات")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_logs"))
                
                bot.edit_message_text(
                    logs_text, 
                    chat_id, message_id,
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_error_logs":
                # عرض سجلات الأخطاء
                error_logs = admin_panel.get_error_logs(20)
                logs_text = get_logs_message(error_logs, "سجلات الأخطاء")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_logs"))
                
                bot.edit_message_text(
                    logs_text, 
                    chat_id, message_id,
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                
            elif call.data == "admin_admin_logs":
                # عرض سجلات المشرفين
                admin_logs = [log for log in admin_panel.get_recent_logs(50) if log.get('user_id') in admin_panel.get_setting('admins', [])]
                logs_text = get_logs_message(admin_logs, "سجلات المشرفين")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_logs"))
                
                bot.edit_message_text(
                    logs_text, 
                    chat_id, message_id,
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                
            # معالجة أزرار البث الجماعي
            elif call.data == "admin_scheduled_broadcasts":
                # عرض البث المجدول
                scheduled = admin_panel.get_scheduled_broadcasts()
                
                if not scheduled:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_broadcast_menu"))
                    bot.edit_message_text(
                        "📅 *البث المجدول*\n\n"
                        "لا يوجد بث مجدول حالياً.",
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                else:
                    broadcasts_text = "📅 *قائمة البث المجدول*\n\n"
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    
                    for idx, broadcast in enumerate(scheduled):
                        broadcast_time = datetime.fromtimestamp(broadcast.get("timestamp", 0))
                        time_str = broadcast_time.strftime("%Y-%m-%d %H:%M:%S")
                        message_preview = broadcast.get("message_text", "")[:50] + "..." if len(broadcast.get("message_text", "")) > 50 else broadcast.get("message_text", "")
                        
                        broadcasts_text += f"{idx+1}. {time_str}\n{message_preview}\n\n"
                        markup.add(types.InlineKeyboardButton(
                            f"❌ إلغاء البث {idx+1}",
                            callback_data=f"admin_cancel_broadcast_{broadcast.get('id')}"
                        ))
                    
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_broadcast_menu"))
                    
                    bot.edit_message_text(
                        broadcasts_text,
                        chat_id, message_id,
                        reply_markup=markup,
                        parse_mode="Markdown"
                    )
                    
            elif call.data.startswith("admin_cancel_broadcast_"):
                # إلغاء بث مجدول
                broadcast_id = int(call.data.split("_")[-1])
                result = admin_panel.remove_scheduled_broadcast(broadcast_id)
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_scheduled_broadcasts"))
                
                status_text = "✅ تم إلغاء البث المجدول بنجاح." if result else "❌ فشل في إلغاء البث المجدول."
                bot.edit_message_text(
                    status_text,
                    chat_id, message_id,
                    reply_markup=markup
                )
                
            # معالجة أزرار النسخ الاحتياطي
            elif call.data == "admin_backup_data":
                # إنشاء نسخة احتياطية
                backup_data = admin_panel.export_data()
                
                if backup_data:
                    with open(backup_data, 'rb') as backup_file:
                        bot.send_document(
                            chat_id=chat_id,
                            document=backup_file,
                            caption="✅ تم إنشاء نسخة احتياطية بنجاح."
                        )
                    
                    # حذف الملف المؤقت بعد الإرسال
                    try:
                        os.remove(backup_data)
                    except:
                        pass
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_backup_menu"))
                    bot.edit_message_text(
                        "✅ تم إنشاء وإرسال النسخة الاحتياطية بنجاح.",
                        chat_id, message_id,
                        reply_markup=markup
                    )
                else:
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_backup_menu"))
                    bot.edit_message_text(
                        "❌ فشل في إنشاء النسخة الاحتياطية.",
                        chat_id, message_id,
                        reply_markup=markup
                    )
                
            elif call.data == "admin_restore_data":
                # استرجاع من نسخة احتياطية
                msg = bot.edit_message_text(
                    "📤 *استرجاع البيانات*\n\n"
                    "أرسل ملف النسخة الاحتياطية للاسترجاع.\n\n"
                    "⚠️ تحذير: سيتم استبدال جميع البيانات الحالية بالبيانات من النسخة الاحتياطية.\n\n"
                    "🔄 أرسل `الغاء` للإلغاء.",
                    chat_id, message_id,
                    parse_mode="Markdown"
                )
                
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_backup_file", {"message_id": msg.message_id})
                
            elif call.data == "admin_clean_temp":
                # تنظيف الملفات المؤقتة
                result = admin_panel.clean_temp_files()
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_backup_menu"))
                
                if isinstance(result, tuple):
                    count, size_mb = result
                    bot.edit_message_text(
                        f"✅ تم تنظيف {count} ملف مؤقت ({size_mb:.2f} ميجابايت) بنجاح.",
                        chat_id, message_id,
                        reply_markup=markup
                    )
                else:
                    bot.edit_message_text(
                        "✅ تم تنظيف الملفات المؤقتة بنجاح.",
                        chat_id, message_id,
                        reply_markup=markup
                    )
                
            # معالجة أزرار القواعد الذكية
            elif call.data == "admin_smart_rules":
                # صفحة القواعد الذكية
                try:
                    with app.app_context():
                        smart_rules_count = SmartRule.query.count()
                        active_rules_count = SmartRule.query.filter_by(is_active=True).count()
                
                    bot.edit_message_text(
                        f"🧠 *القواعد الذكية*\n\nيمكنك إدارة القواعد الذكية للبوت من هنا. هذه القواعد تعمل على تطبيق تغييرات تلقائية على الوسوم بناءً على شروط محددة.\n\nعدد القواعد الحالية: {smart_rules_count}\nالقواعد النشطة: {active_rules_count}",
                        chat_id, message_id,
                        parse_mode="Markdown",
                        reply_markup=get_admin_smart_rules_markup()
                    )
                except Exception as e:
                    logger.error(f"خطأ في صفحة القواعد الذكية: {e}")
                
            elif call.data == "admin_add_smart_rule":
                # إضافة قاعدة ذكية جديدة
                try:
                    # إنشاء رسالة الإضافة مع النموذج
                    field_options = []
                    operator_options = []
                    action_options = []
                    
                    for field in smart_rules.get_available_fields():
                        field_options.append(f"• {field['id']}: {field['name']}")
                    
                    for op in smart_rules.get_available_operators():
                        operator_options.append(f"• {op['id']}: {op['name']}")
                    
                    for action in smart_rules.get_available_actions():
                        action_options.append(f"• {action['id']}: {action['name']}")
                    
                    # إنشاء رسالة بسيطة للتعليمات بدون Markdown
                    bot.edit_message_text(
                        "🆕 إضافة قاعدة ذكية جديدة\n\n"
                        "قم بإرسال بيانات القاعدة بالتنسيق التالي:\n\n"
                        "الاسم: [اسم القاعدة]\n"
                        "الوصف: [وصف القاعدة]\n"
                        "حقل الشرط: [معرف الحقل]\n"
                        "العملية: [معرف العملية]\n"
                        "قيمة الشرط: [قيمة الشرط]\n"
                        "نوع الإجراء: [معرف الإجراء]\n"
                        "حقل الإجراء: [معرف الحقل]\n"
                        "قيمة الإجراء: [قيمة الإجراء]",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_rules")
                        )
                    )
                    
                    # إرسال رسالة منفصلة للحقول المتاحة
                    fields_text = "الحقول المتاحة:\n"
                    for field in field_options:
                        fields_text += field + "\n"
                    bot.send_message(chat_id, fields_text)
                    
                    # إرسال رسالة منفصلة للعمليات المتاحة
                    operators_text = "العمليات المتاحة:\n"
                    for op in operator_options:
                        operators_text += op + "\n"
                    bot.send_message(chat_id, operators_text)
                    
                    # إرسال رسالة منفصلة للإجراءات المتاحة
                    actions_text = "الإجراءات المتاحة:\n"
                    for action in action_options:
                        actions_text += action + "\n"
                    bot.send_message(chat_id, actions_text)
                    
                    # إرسال مثال
                    example_text = "مثال:\n\n"
                    example_text += "الاسم: تعديل عيسى الليث\n"
                    example_text += "الوصف: إضافة السنة لأناشيد عيسى الليث\n"
                    example_text += "حقل الشرط: artist\n"
                    example_text += "العملية: contains\n"
                    example_text += "قيمة الشرط: عيسى الليث\n"
                    example_text += "نوع الإجراء: set\n"
                    example_text += "حقل الإجراء: year\n"
                    example_text += "قيمة الإجراء: 1446"
                    bot.send_message(chat_id, example_text)
                    
                    # تعيين حالة المستخدم لانتظار بيانات القاعدة
                    from bot import set_user_state
                    set_user_state(user_id, "admin_waiting_rule_data", {"message_id": message_id})
                    
                except Exception as e:
                    logger.error(f"خطأ في صفحة إضافة قاعدة ذكية: {e}")
                    
            elif call.data == "admin_view_smart_rules":
                # عرض القواعد الذكية الحالية
                try:
                    with app.app_context():
                        rules = SmartRule.query.order_by(SmartRule.priority).all()
                        
                    if not rules:
                        bot.edit_message_text(
                            "🧠 *القواعد الذكية*\n\nلا توجد قواعد ذكية مضافة بعد.",
                            chat_id, message_id,
                            parse_mode="Markdown",
                            reply_markup=types.InlineKeyboardMarkup().add(
                                types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_rules")
                            )
                        )
                        return
                    
                    rules_text = "🧠 *القواعد الذكية الحالية*\n\n"
                    for i, rule in enumerate(rules):
                        status = "✅" if rule.is_active else "❌"
                        rules_text += f"{i+1}. {status} *{rule.name}*\n"
                        rules_text += f"• الشرط: `{rule.condition_field} {rule.condition_operator} {rule.condition_value}`\n"
                        rules_text += f"• الإجراء: `{rule.action_type} {rule.action_field} {rule.action_value[:20]}{'...' if len(rule.action_value) > 20 else ''}`\n"
                        rules_text += f"• الأولوية: {rule.priority}\n\n"
                    
                    # إنشاء أزرار للقواعد
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    for i, rule in enumerate(rules):
                        markup.add(
                            types.InlineKeyboardButton(
                                f"{i+1}. {'✅' if rule.is_active else '❌'} {rule.name[:15]}...",
                                callback_data=f"admin_rule_{rule.id}"
                            )
                        )
                    markup.add(
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_rules")
                    )
                    
                    bot.edit_message_text(
                        rules_text,
                        chat_id, message_id,
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                except Exception as e:
                    logger.error(f"خطأ في عرض القواعد الذكية: {e}")
                    
            elif call.data == "admin_smart_rules_stats":
                # عرض إحصائيات القواعد الذكية
                try:
                    with app.app_context():
                        total_rules = SmartRule.query.count()
                        active_rules = SmartRule.query.filter_by(is_active=True).count()
                        
                        # الإحصائيات حسب نوع الإجراء
                        rules_by_action = {}
                        for action_type in ['add', 'set', 'replace']:
                            count = SmartRule.query.filter_by(action_type=action_type).count()
                            action_name = {"add": "إضافة", "set": "تعيين", "replace": "استبدال"}.get(action_type, action_type)
                            rules_by_action[action_name] = count
                        
                        # الإحصائيات حسب الحقل
                        field_counts = {}
                        for rule in SmartRule.query.all():
                            field = rule.condition_field
                            field_name = {"artist": "الفنان", "title": "العنوان", "album": "الألبوم", 
                                        "genre": "النوع", "year": "السنة"}.get(field, field)
                            
                            if field_name in field_counts:
                                field_counts[field_name] += 1
                            else:
                                field_counts[field_name] = 1
                    
                    stats_text = "📊 *إحصائيات القواعد الذكية*\n\n"
                    stats_text += f"• إجمالي القواعد: {total_rules}\n"
                    stats_text += f"• القواعد النشطة: {active_rules}\n"
                    stats_text += f"• القواعد المعطلة: {total_rules - active_rules}\n\n"
                    
                    if rules_by_action:
                        stats_text += "*القواعد حسب نوع الإجراء:*\n"
                        for action_name, count in rules_by_action.items():
                            if count > 0:
                                stats_text += f"• {action_name}: {count}\n"
                        stats_text += "\n"
                    
                    if field_counts:
                        stats_text += "*القواعد حسب حقل الشرط:*\n"
                        for field_name, count in field_counts.items():
                            stats_text += f"• {field_name}: {count}\n"
                    
                    bot.edit_message_text(
                        stats_text,
                        chat_id, message_id,
                        parse_mode="Markdown",
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_rules")
                        )
                    )
                except Exception as e:
                    logger.error(f"خطأ في عرض إحصائيات القواعد الذكية: {e}")
                    
            elif call.data.startswith("admin_rule_"):
                # عرض تفاصيل قاعدة ذكية محددة
                try:
                    rule_id = int(call.data.split("_")[2])
                    with app.app_context():
                        rule = SmartRule.query.get(rule_id)
                        
                    if not rule:
                        bot.answer_callback_query(call.id, "القاعدة غير موجودة")
                        return
                    
                    # تحويل معرفات الحقول والعمليات إلى أسماء عربية
                    field_names = {f["id"]: f["name"] for f in smart_rules.get_available_fields()}
                    operator_names = {o["id"]: o["name"] for o in smart_rules.get_available_operators()}
                    action_names = {a["id"]: a["name"] for a in smart_rules.get_available_actions()}
                    
                    rule_text = f"🧠 *تفاصيل القاعدة: {rule.name}*\n\n"
                    rule_text += f"*الوصف:* {rule.description or 'لا يوجد وصف'}\n\n"
                    rule_text += "*الشرط:*\n"
                    rule_text += f"• الحقل: {field_names.get(rule.condition_field, rule.condition_field)}\n"
                    rule_text += f"• العملية: {operator_names.get(rule.condition_operator, rule.condition_operator)}\n"
                    rule_text += f"• القيمة: `{rule.condition_value}`\n\n"
                    
                    rule_text += "*الإجراء:*\n"
                    rule_text += f"• النوع: {action_names.get(rule.action_type, rule.action_type)}\n"
                    rule_text += f"• الحقل: {field_names.get(rule.action_field, rule.action_field)}\n"
                    rule_text += f"• القيمة: `{rule.action_value}`\n\n"
                    
                    rule_text += f"*الأولوية:* {rule.priority}\n"
                    rule_text += f"*الحالة:* {'نشطة ✅' if rule.is_active else 'معطلة ❌'}\n"
                    rule_text += f"*تاريخ الإنشاء:* {rule.created_at.strftime('%Y-%m-%d')}\n"
                    rule_text += f"*آخر تحديث:* {rule.updated_at.strftime('%Y-%m-%d')}\n"
                    
                    # إنشاء أزرار التحكم
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        types.InlineKeyboardButton(
                            f"{'تعطيل ❌' if rule.is_active else 'تفعيل ✅'}",
                            callback_data=f"admin_toggle_rule_{rule_id}"
                        ),
                        types.InlineKeyboardButton("حذف 🗑", callback_data=f"admin_delete_rule_{rule_id}")
                    )
                    markup.add(
                        types.InlineKeyboardButton("تعديل الأولوية", callback_data=f"admin_edit_rule_priority_{rule_id}")
                    )
                    markup.add(
                        types.InlineKeyboardButton("🔙 رجوع للقواعد", callback_data="admin_view_smart_rules")
                    )
                    
                    bot.edit_message_text(
                        rule_text,
                        chat_id, message_id,
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                except Exception as e:
                    logger.error(f"خطأ في عرض تفاصيل القاعدة: {e}")
                    
            elif call.data.startswith("admin_toggle_rule_"):
                # تفعيل/تعطيل قاعدة ذكية
                try:
                    rule_id = int(call.data.split("_")[3])
                    result = smart_rules.toggle_rule_status(rule_id)
                    
                    if result:
                        with app.app_context():
                            rule = SmartRule.query.get(rule_id)
                            status = "تفعيل" if rule.is_active else "تعطيل"
                        bot.answer_callback_query(call.id, f"تم {status} القاعدة بنجاح")
                        # إعادة عرض تفاصيل القاعدة
                        handle_admin_callback(bot, types.CallbackQuery(
                            id=call.id, from_user=call.from_user, message=call.message, 
                            data=f"admin_rule_{rule_id}", chat_instance=call.chat_instance
                        ))
                    else:
                        bot.answer_callback_query(call.id, "فشل في تغيير حالة القاعدة")
                except Exception as e:
                    logger.error(f"خطأ في تغيير حالة القاعدة: {e}")
                    
            elif call.data.startswith("admin_delete_rule_"):
                # حذف قاعدة ذكية
                try:
                    rule_id = int(call.data.split("_")[3])
                    
                    # عرض رسالة تأكيد الحذف
                    with app.app_context():
                        rule = SmartRule.query.get(rule_id)
                        rule_name = rule.name if rule else "القاعدة"
                    
                    bot.edit_message_text(
                        f"⚠️ *تأكيد حذف القاعدة*\n\nهل أنت متأكد من حذف القاعدة **{rule_name}**؟ هذا الإجراء لا يمكن التراجع عنه.",
                        chat_id, message_id,
                        parse_mode="Markdown",
                        reply_markup=types.InlineKeyboardMarkup(row_width=2).add(
                            types.InlineKeyboardButton("نعم، حذف ✅", callback_data=f"admin_confirm_delete_rule_{rule_id}"),
                            types.InlineKeyboardButton("إلغاء ❌", callback_data=f"admin_rule_{rule_id}")
                        )
                    )
                except Exception as e:
                    logger.error(f"خطأ في صفحة حذف القاعدة: {e}")
                    
            elif call.data.startswith("admin_confirm_delete_rule_"):
                # تأكيد حذف القاعدة
                try:
                    rule_id = int(call.data.split("_")[4])
                    result = smart_rules.delete_rule(rule_id)
                    
                    if result:
                        bot.answer_callback_query(call.id, "تم حذف القاعدة بنجاح")
                        # العودة لقائمة القواعد
                        handle_admin_callback(bot, types.CallbackQuery(
                            id=call.id, from_user=call.from_user, message=call.message, 
                            data="admin_view_smart_rules", chat_instance=call.chat_instance
                        ))
                    else:
                        bot.answer_callback_query(call.id, "فشل في حذف القاعدة")
                except Exception as e:
                    logger.error(f"خطأ في حذف القاعدة: {e}")
                    
            elif call.data.startswith("admin_edit_rule_priority_"):
                # تعديل أولوية القاعدة
                try:
                    rule_id = int(call.data.split("_")[4])
                    
                    with app.app_context():
                        rule = SmartRule.query.get(rule_id)
                        
                    if not rule:
                        bot.answer_callback_query(call.id, "القاعدة غير موجودة")
                        return
                    
                    bot.edit_message_text(
                        f"🔢 *تعديل أولوية القاعدة*\n\nالقاعدة: **{rule.name}**\nالأولوية الحالية: **{rule.priority}**\n\nأدخل قيمة الأولوية الجديدة (رقم بين 1 و100، الرقم الأقل يعني أولوية أعلى):",
                        chat_id, message_id,
                        parse_mode="Markdown",
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 إلغاء", callback_data=f"admin_rule_{rule_id}")
                        )
                    )
                    
                    # تعيين حالة المستخدم لانتظار الأولوية الجديدة
                    from bot import set_user_state
                    set_user_state(user_id, f"admin_waiting_rule_priority_{rule_id}", {"message_id": message_id})
                    
                except Exception as e:
                    logger.error(f"خطأ في صفحة تعديل الأولوية: {e}")
            
            # معالجة زر إضافة مشرف
            elif call.data == "admin_add_admin":
                bot.edit_message_text(
                    "👤 *إضافة مشرف جديد*\n\n"
                    "أرسل معرّف المستخدم (User ID) الذي تريد إضافته كمشرف جديد.",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_users")
                    ),
                    parse_mode="Markdown"
                )
                # تغيير حالة المستخدم لانتظار معرف المستخدم الجديد
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_admin_id")
            
            # معالجة زر إلغاء حظر مستخدم
            elif call.data == "admin_unblock_user":
                bot.edit_message_text(
                    "🔓 *إلغاء حظر مستخدم*\n\n"
                    "أرسل معرّف المستخدم (User ID) الذي تريد إلغاء حظره.",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("📋 قائمة المحظورين", callback_data="admin_blocked_users"),
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_users")
                    ),
                    parse_mode="Markdown"
                )
                # تغيير حالة المستخدم لانتظار معرف المستخدم
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_unblock_id")
            
            # معالجة زر حظر مستخدم
            elif call.data == "admin_block_user":
                bot.edit_message_text(
                    "🚫 *حظر مستخدم*\n\n"
                    "أرسل معرّف المستخدم (User ID) الذي تريد حظره من استخدام البوت.",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_users")
                    ),
                    parse_mode="Markdown"
                )
                # تغيير حالة المستخدم لانتظار معرف المستخدم
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_block_id")
            
            # معالجة زر البث الجماعي
            elif call.data == "admin_broadcast":
                bot.edit_message_text(
                    "📢 *البث الجماعي*\n\n"
                    "اختر نوع البث الذي تريد إرساله:",
                    chat_id, message_id,
                    reply_markup=get_admin_broadcast_menu_markup(),
                    parse_mode="Markdown"
                )
            
            # معالجة زر إرسال رسالة نصية للجميع
            elif call.data == "admin_broadcast_text":
                bot.edit_message_text(
                    "📝 *إرسال رسالة نصية لجميع المستخدمين*\n\n"
                    "أرسل النص الذي تريد بثه لجميع مستخدمي البوت.\n"
                    "يمكنك استخدام تنسيق Markdown.\n\n"
                    "مثال: *نص غامق* _نص مائل_ `نص برمجي`",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_broadcast")
                    ),
                    parse_mode="Markdown"
                )
                # تغيير حالة المستخدم لانتظار نص البث
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_broadcast_text")
            
            # معالجة زر ملاحظات الاستخدام
            elif call.data == "admin_usage_notes":
                current_notes = admin_panel.get_setting("bot_info.usage_notes", "لا توجد ملاحظات حالياً")
                bot.edit_message_text(
                    "📝 *تعديل ملاحظات الاستخدام*\n\n"
                    f"الملاحظات الحالية:\n{current_notes}\n\n"
                    "أرسل ملاحظات الاستخدام الجديدة التي ستظهر للمستخدمين.",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
                    ),
                    parse_mode="Markdown"
                )
                # تغيير حالة المستخدم لانتظار ملاحظات الاستخدام
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_usage_notes")
            
            # معالجة زر وصف البوت
            elif call.data == "admin_bot_description":
                current_description = admin_panel.get_setting("bot_info.description", "لا يوجد وصف حالياً")
                bot.edit_message_text(
                    "📝 *تعديل وصف البوت*\n\n"
                    f"الوصف الحالي:\n{current_description}\n\n"
                    "أرسل وصف البوت الجديد الذي سيظهر في القائمة الرئيسية وعند استخدام أمر /start.",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
                    ),
                    parse_mode="Markdown"
                )
                # تغيير حالة المستخدم لانتظار وصف البوت
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_bot_description")
            
            # معالجة زر إعادة تعيين حدود المستخدمين
            elif call.data == "admin_reset_all_limits":
                # إعادة تعيين حدود جميع المستخدمين
                result = admin_panel.reset_user_limit()
                if result:
                    bot.edit_message_text(
                        "✅ تم إعادة تعيين حدود جميع المستخدمين بنجاح!",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
                        )
                    )
                else:
                    bot.edit_message_text(
                        "❌ حدث خطأ أثناء إعادة تعيين حدود المستخدمين.",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
                        )
                    )
            
            # معالجة زر العلامة المائية الصوتية
            elif call.data == "admin_audio_watermark":
                watermark_enabled = admin_panel.get_setting("audio_watermark.enabled", False)
                watermark_file = admin_panel.get_setting("audio_watermark.file", "غير محدد")
                watermark_position = admin_panel.get_setting("audio_watermark.position", "start")
                watermark_volume = admin_panel.get_setting("audio_watermark.volume", 0.5)
                
                status = "✅ مفعلة" if watermark_enabled else "❌ معطلة"
                position_text = "بداية الملف" if watermark_position == "start" else "نهاية الملف"
                
                bot.edit_message_text(
                    f"🔊 *إعدادات العلامة المائية الصوتية*\n\n"
                    f"• الحالة: {status}\n"
                    f"• الملف الحالي: {watermark_file}\n"
                    f"• الموضع: {position_text}\n"
                    f"• مستوى الصوت: {int(watermark_volume * 100)}%\n\n"
                    "اختر الإجراء الذي تريد تنفيذه:",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup(row_width=1).add(
                        types.InlineKeyboardButton(
                            "✅ تفعيل العلامة المائية" if not watermark_enabled else "❌ تعطيل العلامة المائية", 
                            callback_data="admin_toggle_watermark"
                        ),
                        types.InlineKeyboardButton("📁 تغيير ملف العلامة المائية", callback_data="admin_change_watermark_file"),
                        types.InlineKeyboardButton(
                            f"📍 تغيير الموضع ({position_text})", 
                            callback_data="admin_toggle_watermark_position"
                        ),
                        types.InlineKeyboardButton(f"🔊 ضبط مستوى الصوت ({int(watermark_volume * 100)}%)", callback_data="admin_watermark_volume"),
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
                    ),
                    parse_mode="Markdown"
                )
            
            # معالجة زر تبديل حالة العلامة المائية
            elif call.data == "admin_toggle_watermark":
                current_state = admin_panel.get_setting("audio_watermark.enabled", False)
                new_state = not current_state
                result = admin_panel.enable_audio_watermark(new_state)
                
                if result:
                    bot.answer_callback_query(call.id, "تم تغيير حالة العلامة المائية بنجاح")
                    # إعادة تحميل صفحة العلامة المائية
                    handle_admin_callback(bot, types.CallbackQuery(
                        id=call.id, from_user=call.from_user, message=call.message, 
                        data="admin_audio_watermark", chat_instance=call.chat_instance
                    ))
                else:
                    bot.answer_callback_query(call.id, "حدث خطأ أثناء تغيير حالة العلامة المائية")
            
            # معالجة زر تغيير موضع العلامة المائية
            elif call.data == "admin_toggle_watermark_position":
                current_position = admin_panel.get_setting("audio_watermark.position", "start")
                new_position = "end" if current_position == "start" else "start"
                
                # تحديث الموضع
                watermark_file = admin_panel.get_setting("audio_watermark.file", "")
                volume = admin_panel.get_setting("audio_watermark.volume", 0.5)
                
                if watermark_file:
                    result = admin_panel.set_audio_watermark(watermark_file, new_position, volume)
                    if result:
                        bot.answer_callback_query(call.id, "تم تغيير موضع العلامة المائية بنجاح")
                    else:
                        bot.answer_callback_query(call.id, "حدث خطأ أثناء تغيير موضع العلامة المائية")
                else:
                    bot.answer_callback_query(call.id, "يجب تحديد ملف العلامة المائية أولاً")
                
                # إعادة تحميل صفحة العلامة المائية
                handle_admin_callback(bot, types.CallbackQuery(
                    id=call.id, from_user=call.from_user, message=call.message, 
                    data="admin_audio_watermark", chat_instance=call.chat_instance
                ))
            
            # معالجة زر تذييل الوسوم
            elif call.data == "admin_tag_footer":
                bot.edit_message_text(
                    "📝 *تذييل الوسوم*\n\n"
                    "يمكنك إضافة نص تذييل موحد للوسوم المختلفة ليتم إضافته تلقائياً عند معالجة الملفات الصوتية.\n"
                    "مثال: إضافة اسم قناتك أو موقعك في نهاية وسوم معينة.\n\n"
                    "اختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_tag_footer_markup(),
                    parse_mode="Markdown"
                )
                
            # معالجة زر إعدادات التذييل للوسوم المحددة
            elif call.data == "admin_footer_tag_settings":
                bot.edit_message_text(
                    "⚙️ *إعدادات الوسوم المضاف إليها التذييل*\n\n"
                    "اختر الوسوم التي ترغب في إضافة التذييل إليها:\n"
                    "(اضغط على وسم لتغيير حالته)",
                    chat_id, message_id,
                    reply_markup=get_admin_footer_tag_settings_markup(),
                    parse_mode="Markdown"
                )
            
            # معالجة زر تفعيل/تعطيل تذييل الوسوم
            elif call.data == "admin_toggle_tag_footer":
                footer_enabled = admin_panel.get_setting("auto_processing.tag_footer_enabled", False)
                if admin_panel.set_tag_footer_enabled(not footer_enabled):
                    bot.answer_callback_query(call.id, f"تم {'تعطيل' if footer_enabled else 'تفعيل'} تذييل الوسوم بنجاح")
                    
                    # إعادة تحميل صفحة تذييل الوسوم
                    handle_admin_callback(bot, types.CallbackQuery(
                        id=call.id, from_user=call.from_user, message=call.message, 
                        data="admin_tag_footer", chat_instance=call.chat_instance
                    ))
                else:
                    bot.answer_callback_query(call.id, "حدث خطأ أثناء تغيير حالة تذييل الوسوم")
            
            # معالجة زر تعديل نص التذييل
            elif call.data == "admin_edit_tag_footer":
                # حفظ حالة المستخدم وإرسال رسالة طلب إدخال نص التذييل
                from bot import set_user_state
                set_user_state(call.from_user.id, "waiting_for_footer_text")
                bot.send_message(
                    chat_id,
                    "📝 *تعديل نص التذييل*\n\n"
                    "يرجى إدخال النص الذي ترغب في إضافته كتذييل للوسوم:\n"
                    "(يمكنك استخدام النص العادي أو Markdown)",
                    parse_mode="Markdown",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 إلغاء", callback_data="admin_tag_footer")
                    )
                )
            
            # معالجة أزرار تبديل حالة وسوم التذييل
            elif call.data.startswith("admin_toggle_footer_tag_"):
                tag_name = call.data.replace("admin_toggle_footer_tag_", "")
                footer_tag_settings = admin_panel.get_setting("auto_processing.footer_tag_settings", {
                    'artist': True,
                    'album_artist': False,
                    'album': False,
                    'genre': False,
                    'year': False,
                    'composer': False,
                    'comment': True,
                    'title': False,
                    'lyrics': True
                })
                
                # تغيير حالة الوسم
                if tag_name in footer_tag_settings:
                    footer_tag_settings[tag_name] = not footer_tag_settings[tag_name]
                    if admin_panel.update_footer_tag_settings(footer_tag_settings):
                        arabic_name = get_tag_arabic_name(tag_name)
                        bot.answer_callback_query(call.id, f"تم {'تفعيل' if footer_tag_settings[tag_name] else 'تعطيل'} التذييل لوسم {arabic_name}")
                        
                        # إعادة تحميل صفحة إعدادات التذييل
                        handle_admin_callback(bot, types.CallbackQuery(
                            id=call.id, from_user=call.from_user, message=call.message, 
                            data="admin_footer_tag_settings", chat_instance=call.chat_instance
                        ))
                    else:
                        bot.answer_callback_query(call.id, "حدث خطأ أثناء تحديث إعدادات الوسوم")
            
            # معالجة زر الوسوم التلقائية
            elif call.data == "admin_tag_replacements":
                bot.edit_message_text(
                    "🏷️ *إدارة استبدال الوسوم التلقائي*\n\n"
                    "استبدال الوسوم يتيح لك تعديل قيم الوسوم تلقائياً أثناء المعالجة.\n"
                    "مثال: استبدال كلمة 'Artist' بكلمة 'الفنان'.\n\n"
                    "اختر إحدى الوظائف التالية:",
                    chat_id, message_id,
                    reply_markup=get_admin_tag_replacements_markup(),
                    parse_mode="Markdown"
                )
            
            # معالجة زر قناة السجل
            elif call.data == "admin_log_channel":
                current_channel = admin_panel.get_setting("settings.log_channel", "غير محددة")
                bot.edit_message_text(
                    f"📋 *إعداد قناة السجل*\n\n"
                    f"قناة السجل الحالية: {current_channel}\n\n"
                    "أرسل معرّف القناة الجديدة بالتنسيق التالي:\n"
                    "- للقنوات العامة: @channel_name\n"
                    "- للقنوات الخاصة: -100123456789\n\n"
                    "أو أرسل كلمة 'حذف' لإزالة قناة السجل الحالية.",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_advanced_settings")
                    ),
                    parse_mode="Markdown"
                )
                # تغيير حالة المستخدم لانتظار معرف القناة
                from bot import set_user_state
                set_user_state(user_id, "admin_waiting_for_log_channel")
            
            # معالجة زر الإحصائيات المفصلة
            elif call.data == "admin_user_stats":
                user_count = 0
                active_users_today = 0
                active_users_week = 0
                files_processed_today = 0
                files_processed_week = 0
                total_files_processed = 0
                
                try:
                    # عدد المستخدمين الإجمالي
                    user_count = len(admin_panel.admin_data.get("users", {}))
                    
                    # المستخدمين النشطين اليوم
                    active_today = admin_panel.get_active_users(1)
                    active_users_today = len(active_today)
                    
                    # المستخدمين النشطين هذا الأسبوع
                    active_week = admin_panel.get_active_users(7)
                    active_users_week = len(active_week)
                    
                    # الملفات المعالجة
                    for user_data in admin_panel.admin_data.get("users", {}).values():
                        if "files_processed" in user_data:
                            total_files_processed += user_data["files_processed"]
                        
                        # التحقق من آخر نشاط
                        if "last_activity" in user_data:
                            last_activity = user_data["last_activity"]
                            now = time.time()
                            # النشاط اليوم
                            if now - last_activity < 24 * 60 * 60:
                                files_processed_today += user_data.get("files_processed_today", 0)
                            
                            # النشاط هذا الأسبوع
                            if now - last_activity < 7 * 24 * 60 * 60:
                                files_processed_week += user_data.get("files_processed_week", 0)
                except Exception as e:
                    logger.error(f"خطأ في الحصول على إحصائيات المستخدمين: {e}")
                
                bot.edit_message_text(
                    f"📊 *إحصائيات المستخدمين المفصلة*\n\n"
                    f"• إجمالي المستخدمين: {user_count}\n"
                    f"• المستخدمين النشطين اليوم: {active_users_today}\n"
                    f"• المستخدمين النشطين هذا الأسبوع: {active_users_week}\n\n"
                    f"• الملفات المعالجة اليوم: {files_processed_today}\n"
                    f"• الملفات المعالجة هذا الأسبوع: {files_processed_week}\n"
                    f"• إجمالي الملفات المعالجة: {total_files_processed}\n",
                    chat_id, message_id,
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔍 أكثر المستخدمين نشاطاً", callback_data="admin_top_users"),
                        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_stats")
                    ),
                    parse_mode="Markdown"
                )
            
            # معالجة زر إعادة تشغيل البوت
            elif call.data == "admin_restart_bot":
                try:
                    bot.edit_message_text(
                        "🔄 *إعادة تشغيل البوت*\n\n"
                        "هل أنت متأكد أنك تريد إعادة تشغيل البوت؟ سيؤدي ذلك إلى قطع جميع الاتصالات الحالية.",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("✅ نعم، إعادة التشغيل", callback_data="admin_confirm_restart"),
                            types.InlineKeyboardButton("❌ لا، إلغاء", callback_data="admin_tools")
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطأ في صفحة إعادة تشغيل البوت: {e}")
            
            # معالجة زر تأكيد إعادة تشغيل البوت
            elif call.data == "admin_confirm_restart":
                try:
                    bot.edit_message_text(
                        "🔄 *جاري إعادة تشغيل البوت...*\n\n"
                        "سيتم إعادة تشغيل البوت خلال لحظات. الرجاء الانتظار.",
                        chat_id, message_id,
                        parse_mode="Markdown"
                    )
                    
                    # إرسال إشعار للمشرفين الآخرين
                    admin_ids = admin_panel.admin_data.get("admins", [])
                    admin_message = f"ℹ️ تم إعادة تشغيل البوت بواسطة المشرف {user_id}"
                    
                    for admin_id in admin_ids:
                        if admin_id != user_id:
                            try:
                                bot.send_message(admin_id, admin_message)
                            except Exception as e:
                                logger.error(f"فشل في إرسال إشعار إعادة التشغيل للمشرف {admin_id}: {e}")
                    
                    # تسجيل العملية
                    admin_panel.log_action(user_id, "restart_bot", "success")
                    
                    # إعادة تشغيل البوت
                    import os, sys
                    logger.info(f"إعادة تشغيل البوت بواسطة المشرف {user_id}")
                    os.execl(sys.executable, sys.executable, *sys.argv)
                    
                except Exception as e:
                    logger.error(f"خطأ في إعادة تشغيل البوت: {e}")
                    bot.edit_message_text(
                        f"❌ *فشل في إعادة تشغيل البوت*\n\n"
                        f"حدث خطأ أثناء محاولة إعادة تشغيل البوت: {str(e)}",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tools")
                        ),
                        parse_mode="Markdown"
                    )
            
            # معالجة زر تشخيص الأداء
            elif call.data == "admin_performance":
                try:
                    # الحصول على معلومات النظام
                    system_info = admin_panel.get_system_info()
                    
                    # عرض المعلومات
                    bot.edit_message_text(
                        f"📊 *تشخيص أداء النظام*\n\n"
                        f"• وحدة المعالجة المركزية:\n"
                        f"  - الاستخدام: {system_info['cpu_percent']}%\n"
                        f"  - عدد النوى: {system_info['cpu_count']}\n\n"
                        f"• الذاكرة:\n"
                        f"  - المستخدمة: {system_info['memory_used']} MB\n"
                        f"  - الإجمالية: {system_info['memory_total']} MB\n"
                        f"  - نسبة الاستخدام: {system_info['memory_percent']}%\n\n"
                        f"• القرص:\n"
                        f"  - المستخدم: {system_info['disk_used']} GB\n"
                        f"  - الإجمالي: {system_info['disk_total']} GB\n"
                        f"  - نسبة الاستخدام: {system_info['disk_percent']}%\n\n"
                        f"• النظام:\n"
                        f"  - وقت التشغيل: {format_duration(system_info['uptime'])}\n"
                        f"  - عدد العمليات: {system_info['process_count']}\n",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔄 تحديث", callback_data="admin_performance"),
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tools")
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطأ في صفحة تشخيص الأداء: {e}")
                    bot.edit_message_text(
                        f"❌ *فشل في تحميل معلومات الأداء*\n\n"
                        f"حدث خطأ أثناء محاولة تحميل معلومات النظام: {str(e)}",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tools")
                        ),
                        parse_mode="Markdown"
                    )
            
            # معالجة زر تنظيف الملفات المؤقتة
            elif call.data == "admin_clean_temp":
                try:
                    # قبل التنظيف
                    before_count = len(os.listdir("temp_audio_files"))
                    before_size = sum(os.path.getsize(os.path.join("temp_audio_files", f)) for f in os.listdir("temp_audio_files") if os.path.isfile(os.path.join("temp_audio_files", f)))
                    before_size_mb = before_size / (1024 * 1024)
                    
                    # تنظيف الملفات المؤقتة
                    admin_panel.clean_temp_files()
                    
                    # بعد التنظيف
                    after_count = len(os.listdir("temp_audio_files"))
                    after_size = sum(os.path.getsize(os.path.join("temp_audio_files", f)) for f in os.listdir("temp_audio_files") if os.path.isfile(os.path.join("temp_audio_files", f)))
                    after_size_mb = after_size / (1024 * 1024)
                    
                    bot.edit_message_text(
                        f"🧹 *تم تنظيف الملفات المؤقتة بنجاح*\n\n"
                        f"• قبل التنظيف:\n"
                        f"  - عدد الملفات: {before_count}\n"
                        f"  - الحجم الإجمالي: {before_size_mb:.2f} MB\n\n"
                        f"• بعد التنظيف:\n"
                        f"  - عدد الملفات: {after_count}\n"
                        f"  - الحجم الإجمالي: {after_size_mb:.2f} MB\n\n"
                        f"• تم توفير: {before_size_mb - after_size_mb:.2f} MB",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tools")
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطأ في تنظيف الملفات المؤقتة: {e}")
                    bot.edit_message_text(
                        f"❌ *فشل في تنظيف الملفات المؤقتة*\n\n"
                        f"حدث خطأ أثناء محاولة تنظيف الملفات المؤقتة: {str(e)}",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tools")
                        ),
                        parse_mode="Markdown"
                    )
            
            # معالجة زر حالة النظام
            elif call.data == "admin_system_status":
                try:
                    bot.edit_message_text(
                        get_system_status_message(),
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔄 تحديث", callback_data="admin_system_status"),
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tools")
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"خطأ في عرض حالة النظام: {e}")
                    bot.edit_message_text(
                        f"❌ *فشل في تحميل حالة النظام*\n\n"
                        f"حدث خطأ أثناء محاولة تحميل حالة النظام: {str(e)}",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tools")
                        ),
                        parse_mode="Markdown"
                    )
            
            # معالجة زر إضافة قاعدة ذكية
            elif call.data == "admin_add_smart_rule":
                try:
                    # إعداد نموذج لإدخال بيانات القاعدة
                    rule_template = (
                        "الاسم: قاعدة جديدة\n"
                        "الوصف: وصف القاعدة\n"
                        "حقل الشرط: artist\n"
                        "العملية: contains\n"
                        "قيمة الشرط: اسم الفنان\n"
                        "نوع الإجراء: replace\n"
                        "حقل الإجراء: title\n"
                        "قيمة الإجراء: القيمة الجديدة"
                    )
                    
                    bot.edit_message_text(
                        "🆕 *إضافة قاعدة ذكية جديدة*\n\n"
                        "أرسل بيانات القاعدة بالتنسيق التالي:\n\n"
                        f"```\n{rule_template}\n```\n\n"
                        "العمليات المتاحة: equals, contains, startswith, endswith\n"
                        "أنواع الإجراءات المتاحة: replace, add, set\n"
                        "حقول الشرط والإجراء المتاحة: artist, title, album, year, genre, composer, comment, track, length, lyrics, albumartist",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_rules")
                        ),
                        parse_mode="Markdown"
                    )
                    
                    # تعيين حالة المستخدم لانتظار بيانات القاعدة
                    from bot import set_user_state
                    set_user_state(user_id, "admin_waiting_rule_data", {"message_id": message_id})
                    
                except Exception as e:
                    logger.error(f"خطأ في صفحة إضافة قاعدة ذكية: {e}")
                    bot.edit_message_text(
                        f"❌ *فشل في تحميل صفحة إضافة قاعدة ذكية*\n\n"
                        f"حدث خطأ: {str(e)}",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_rules")
                        ),
                        parse_mode="Markdown"
                    )
            
            # معالجة أزرار التبديل (toggle) للإعدادات المختلفة
            elif call.data.startswith("admin_toggle_"):
                feature_name = call.data.replace("admin_toggle_", "")
                
                try:
                    current_state = admin_panel.get_setting(f"features_enabled.{feature_name}", True)
                    new_state = not current_state
                    
                    if admin_panel.update_setting(f"features_enabled.{feature_name}", new_state):
                        state_text = "تفعيل" if new_state else "تعطيل"
                        feature_text = {
                            "lyrics": "كلمات الأغاني",
                            "album_art": "صورة الألبوم",
                            "templates": "القوالب",
                            "required_subscription": "الاشتراك الإجباري",
                            "auto_processing": "المعالجة التلقائية"
                        }.get(feature_name, feature_name)
                        
                        bot.answer_callback_query(call.id, f"تم {state_text} {feature_text} بنجاح")
                        
                        # إعادة تحميل صفحة الإعدادات
                        handle_admin_callback(bot, types.CallbackQuery(
                            id=call.id, from_user=call.from_user, message=call.message, 
                            data="admin_settings", chat_instance=call.chat_instance
                        ))
                    else:
                        bot.answer_callback_query(call.id, "فشل في تحديث الإعداد")
                except Exception as e:
                    logger.error(f"خطأ في تبديل حالة الميزة '{feature_name}': {e}")
                    bot.answer_callback_query(call.id, f"حدث خطأ: {str(e)}")
            
            # معالجة زر إضافة استبدال نصي
            elif call.data == "admin_add_replacement":
                try:
                    # إنشاء نموذج رسالة للاستبدال النصي
                    bot.edit_message_text(
                        "🆕 *إضافة استبدال نصي جديد*\n\n"
                        "أرسل النص المراد استبداله والنص البديل بالتنسيق التالي:\n\n"
                        "```\n"
                        "النص القديم\n"
                        "النص الجديد\n"
                        "```\n\n"
                        "مثال:\n"
                        "```\n"
                        "حيدر غولي\n"
                        "حيدر الغولي\n"
                        "```\n\n"
                        "ملاحظة: سيتم استبدال السطر الأول بالسطر الثاني في جميع وسوم الملفات الصوتية.",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tag_replacements")
                        ),
                        parse_mode="Markdown"
                    )
                    
                    # تعيين حالة المستخدم لانتظار بيانات الاستبدال
                    from bot import set_user_state
                    set_user_state(user_id, "admin_waiting_old_text", {"message_id": message_id})
                    
                except Exception as e:
                    logger.error(f"خطأ في صفحة إضافة استبدال نصي: {e}")
                    bot.edit_message_text(
                        f"❌ *فشل في تحميل صفحة إضافة استبدال نصي*\n\n"
                        f"حدث خطأ: {str(e)}",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_tag_replacements")
                        ),
                        parse_mode="Markdown"
                    )
                    
            # معالجة زر تعيين قناة المصدر
            elif call.data == "admin_set_source_channel":
                try:
                    current_channel = admin_panel.get_setting("auto_processing.source_channel", "غير محدد")
                    
                    bot.edit_message_text(
                        "📡 *تعيين قناة المصدر للتعديل التلقائي*\n\n"
                        f"القناة الحالية: `{current_channel}`\n\n"
                        "أرسل معرّف القناة المراد تعيينها كمصدر للتعديل التلقائي.\n"
                        "يمكن أن يكون على شكل @username أو -100xxxxxxxxxx.\n\n"
                        "ملاحظة: تأكد من إضافة البوت كمشرف في القناة مع صلاحيات رفع الملفات والتعديل.",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing")
                        ),
                        parse_mode="Markdown"
                    )
                    
                    # تعيين حالة المستخدم لانتظار معرف القناة
                    from bot import set_user_state
                    set_user_state(user_id, "admin_waiting_source_channel", {"message_id": message_id})
                    
                except Exception as e:
                    logger.error(f"خطأ في صفحة تعيين قناة المصدر: {e}")
                    bot.edit_message_text(
                        f"❌ *فشل في تحميل صفحة تعيين قناة المصدر*\n\n"
                        f"حدث خطأ: {str(e)}",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_auto_processing")
                        ),
                        parse_mode="Markdown"
                    )
                    
            # معالجة زر إضافة قالب ذكي
            elif call.data == "admin_add_smart_template":
                try:
                    # الحصول على قائمة القوالب المتاحة
                    from template_handler import get_templates_list
                    templates = get_templates_list()
                    templates_options = []
                    
                    # إنشاء قائمة بالقوالب المتاحة
                    for template in templates:
                        template_name = template.get('name', 'غير معروف')
                        artist_name = template.get('artist', 'غير معروف')
                        templates_options.append(f"{template_name} - {artist_name}")
                    
                    if not templates_options:
                        templates_options = ["لا توجد قوالب متاحة بعد. قم بإنشاء قوالب أولاً."]
                    
                    templates_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(templates_options)])
                    
                    bot.edit_message_text(
                        "🎯 *إضافة قالب ذكي جديد*\n\n"
                        "القوالب الذكية تسمح بتطبيق قالب تلقائياً على الملفات الصوتية بناءً على اسم الفنان.\n\n"
                        "أرسل اسم الفنان ومعرف القالب بالتنسيق التالي:\n\n"
                        "```\n"
                        "اسم الفنان\n"
                        "معرف القالب\n"
                        "```\n\n"
                        "مثال:\n"
                        "```\n"
                        "عدي الغولي\n"
                        "oday_template\n"
                        "```\n\n"
                        "القوالب المتاحة:\n"
                        f"```\n{templates_text}\n```",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_templates")
                        ),
                        parse_mode="Markdown"
                    )
                    
                    # تعيين حالة المستخدم لانتظار بيانات القالب الذكي
                    from bot import set_user_state
                    set_user_state(user_id, "admin_waiting_smart_template", {"message_id": message_id})
                    
                except Exception as e:
                    logger.error(f"خطأ في صفحة إضافة قالب ذكي: {e}")
                    bot.edit_message_text(
                        f"❌ *فشل في تحميل صفحة إضافة قالب ذكي*\n\n"
                        f"حدث خطأ: {str(e)}",
                        chat_id, message_id,
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_smart_templates")
                        ),
                        parse_mode="Markdown"
                    )
            
            # معالجة باقي الأزرار
            else:
                logger.info(f"زر غير معالج بشكل خاص: {call.data}")
                # يمكن إضافة المزيد من الأزرار هنا حسب الحاجة
        
    except Exception as e:
        logger.error(f"خطأ في معالجة زر لوحة الإدارة {call.data}: {e}")
        try:
            if 'chat_id' in locals():
                bot.send_message(chat_id, f"⚠️ حدث خطأ في معالجة الطلب: {str(e)}")
            else:
                bot.send_message(call.message.chat.id, f"⚠️ حدث خطأ في معالجة الطلب: {str(e)}")
        except Exception as inner_e:
            logger.error(f"خطأ إضافي أثناء إرسال رسالة الخطأ: {inner_e}")

# Funciones de administración
def open_admin_panel(bot, message):
    """فتح لوحة الإدارة للمشرف"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # التحقق من أن المستخدم مشرف أو مطور
    developer_ids = [1174919068, 6556918772, 6602517122]
    is_dev = user_id in developer_ids
    
    # إذا كان مطوراً ولكن ليس مشرفاً، أضفه كمشرف
    if is_dev and not admin_panel.is_admin(user_id):
        admin_panel.add_admin(user_id)
        logger.info(f"تمت إضافة مطور البوت {user_id} كمشرف تلقائياً")
    
    if not admin_panel.is_admin(user_id) and not is_dev:
        bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
        return
    
    # إرسال لوحة الإدارة الرئيسية
    try:
        bot.send_message(
            chat_id,
            "⚙️ *لوحة إدارة البوت*\n\nمرحبًا بك في لوحة إدارة البوت. اختر إحدى الوظائف التالية:",
            reply_markup=get_admin_panel_markup(),
            parse_mode="Markdown"
        )
        logger.info(f"تم فتح لوحة الإدارة للمستخدم {user_id}")
    except Exception as e:
        logger.error(f"خطأ في فتح لوحة الإدارة: {e}")
        bot.reply_to(message, f"⚠️ حدث خطأ في فتح لوحة الإدارة: {str(e)}")

def add_admin_command(bot, message):
    """إضافة مستخدم كمشرف"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # التحقق من أن المستخدم مشرف
    if not admin_panel.is_admin(user_id):
        bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
        return
    
    # استخراج معرف المشرف الجديد
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "⚠️ صيغة الأمر غير صحيحة. الصيغة الصحيحة: /add_admin [معرف المستخدم]")
        return
    
    try:
        new_admin_id = int(command_parts[1])
        if admin_panel.add_admin(new_admin_id):
            bot.reply_to(message, f"✅ تمت إضافة المستخدم {new_admin_id} كمشرف بنجاح.")
        else:
            bot.reply_to(message, f"ℹ️ المستخدم {new_admin_id} مشرف بالفعل.")
    except ValueError:
        bot.reply_to(message, "⚠️ معرف المستخدم يجب أن يكون رقمًا.")
    except Exception as e:
        logger.error(f"خطأ في إضافة مشرف: {e}")
        bot.reply_to(message, f"⚠️ حدث خطأ في إضافة المشرف: {str(e)}")

def remove_admin_command(bot, message):
    """إزالة مستخدم من المشرفين"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # التحقق من أن المستخدم مشرف
    if not admin_panel.is_admin(user_id):
        bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
        return
    
    # استخراج معرف المشرف المراد إزالته
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "⚠️ صيغة الأمر غير صحيحة. الصيغة الصحيحة: /remove_admin [معرف المستخدم]")
        return
    
    try:
        admin_id = int(command_parts[1])
        
        # التحقق من عدم إزالة النفس
        if admin_id == user_id:
            bot.reply_to(message, "⚠️ لا يمكنك إزالة نفسك من المشرفين.")
            return
        
        if admin_panel.remove_admin(admin_id):
            bot.reply_to(message, f"✅ تمت إزالة المستخدم {admin_id} من المشرفين بنجاح.")
        else:
            bot.reply_to(message, f"ℹ️ المستخدم {admin_id} ليس مشرفًا.")
    except ValueError:
        bot.reply_to(message, "⚠️ معرف المستخدم يجب أن يكون رقمًا.")
    except Exception as e:
        logger.error(f"خطأ في إزالة مشرف: {e}")
        bot.reply_to(message, f"⚠️ حدث خطأ في إزالة المشرف: {str(e)}")

def block_user_command(bot, message):
    """حظر مستخدم"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # التحقق من أن المستخدم مشرف
    if not admin_panel.is_admin(user_id):
        bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
        return
    
    # استخراج معرف المستخدم المراد حظره
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "⚠️ صيغة الأمر غير صحيحة. الصيغة الصحيحة: /block [معرف المستخدم]")
        return
    
    try:
        blocked_user_id = int(command_parts[1])
        
        # التحقق من عدم حظر مشرف
        if admin_panel.is_admin(blocked_user_id):
            bot.reply_to(message, "⚠️ لا يمكن حظر مشرف.")
            return
        
        if admin_panel.block_user(blocked_user_id):
            bot.reply_to(message, f"✅ تم حظر المستخدم {blocked_user_id} بنجاح.")
        else:
            bot.reply_to(message, f"ℹ️ المستخدم {blocked_user_id} محظور بالفعل.")
    except ValueError:
        bot.reply_to(message, "⚠️ معرف المستخدم يجب أن يكون رقمًا.")
    except Exception as e:
        logger.error(f"خطأ في حظر مستخدم: {e}")
        bot.reply_to(message, f"⚠️ حدث خطأ في حظر المستخدم: {str(e)}")

def unblock_user_command(bot, message):
    """إلغاء حظر مستخدم"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # التحقق من أن المستخدم مشرف
    if not admin_panel.is_admin(user_id):
        bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
        return
    
    # استخراج معرف المستخدم المراد إلغاء حظره
    command_parts = message.text.split()
    if len(command_parts) != 2:
        bot.reply_to(message, "⚠️ صيغة الأمر غير صحيحة. الصيغة الصحيحة: /unblock [معرف المستخدم]")
        return
    
    try:
        unblocked_user_id = int(command_parts[1])
        if admin_panel.unblock_user(unblocked_user_id):
            bot.reply_to(message, f"✅ تم إلغاء حظر المستخدم {unblocked_user_id} بنجاح.")
        else:
            bot.reply_to(message, f"ℹ️ المستخدم {unblocked_user_id} غير محظور.")
    except ValueError:
        bot.reply_to(message, "⚠️ معرف المستخدم يجب أن يكون رقمًا.")
    except Exception as e:
        logger.error(f"خطأ في إلغاء حظر مستخدم: {e}")
        bot.reply_to(message, f"⚠️ حدث خطأ في إلغاء حظر المستخدم: {str(e)}")

def broadcast_command(bot, message):
    """إرسال رسالة جماعية"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # التحقق من أن المستخدم مشرف
    if not admin_panel.is_admin(user_id):
        bot.reply_to(message, "⛔ غير مصرح لك بالوصول إلى لوحة الإدارة.")
        return
    
    # استخراج نص الرسالة
    command_parts = message.text.split(' ', 1)
    if len(command_parts) != 2:
        bot.reply_to(message, "⚠️ صيغة الأمر غير صحيحة. الصيغة الصحيحة: /broadcast [نص الرسالة]")
        return
    
    broadcast_text = command_parts[1].strip()
    if not broadcast_text:
        bot.reply_to(message, "⚠️ يجب إدخال نص للرسالة.")
        return
    
    try:
        admin_panel.send_broadcast(bot, broadcast_text)
        bot.reply_to(message, "✅ تم إرسال الرسالة الجماعية بنجاح.")
    except Exception as e:
        logger.error(f"خطأ في إرسال رسالة جماعية: {e}")
        bot.reply_to(message, f"⚠️ حدث خطأ في إرسال الرسالة الجماعية: {str(e)}")

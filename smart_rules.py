"""
وحدة إدارة القواعد الذكية للبوت
"""

import logging
from datetime import datetime
from flask import current_app
from models import db, SmartRule, User
from main import app

# إعداد التسجيل
logger = logging.getLogger(__name__)

# ثوابت عامة
CONDITION_OPERATORS = [
    {'id': 'contains', 'name': 'يحتوي على'},
    {'id': 'equals', 'name': 'يساوي تماماً'},
    {'id': 'starts_with', 'name': 'يبدأ بـ'},
    {'id': 'ends_with', 'name': 'ينتهي بـ'}
]

ACTION_TYPES = [
    {'id': 'add', 'name': 'إضافة إلى'},
    {'id': 'set', 'name': 'تعيين قيمة'},
    {'id': 'replace', 'name': 'استبدال نص'}
]

TAG_FIELDS = [
    {'id': 'title', 'name': 'العنوان'},
    {'id': 'artist', 'name': 'الفنان'},
    {'id': 'album', 'name': 'الألبوم'},
    {'id': 'album_artist', 'name': 'فنان الألبوم'},
    {'id': 'year', 'name': 'السنة'},
    {'id': 'genre', 'name': 'النوع'},
    {'id': 'composer', 'name': 'الملحن'},
    {'id': 'comment', 'name': 'تعليق'},
    {'id': 'track', 'name': 'رقم المسار'},
    {'id': 'lyrics', 'name': 'كلمات الأغنية'},
    {'id': '*', 'name': 'جميع الحقول'} # فقط للاستبدال
]

def create_rule(name, description, condition_field, condition_operator, condition_value,
               action_type, action_field, action_value, creator_id, priority=10, is_active=True):
    """
    إنشاء قاعدة ذكية جديدة
    
    Args:
        name: اسم القاعدة
        description: وصف القاعدة
        condition_field: الحقل الذي سيتم التحقق منه
        condition_operator: نوع العملية (يحتوي، يساوي، إلخ)
        condition_value: القيمة المستخدمة في الشرط
        action_type: نوع الإجراء (إضافة، تعيين، استبدال)
        action_field: الحقل الذي سيتم تطبيق الإجراء عليه
        action_value: قيمة الإجراء
        creator_id: معرف المستخدم المنشئ
        priority: أولوية التنفيذ (الأقل يتم تنفيذه أولاً)
        is_active: هل القاعدة نشطة
        
    Returns:
        int: معرف القاعدة الجديدة، أو None في حالة الخطأ
    """
    try:
        with app.app_context():
            # التحقق من وجود المستخدم
            user = User.query.get(creator_id)
            if not user:
                logger.error(f"المستخدم {creator_id} غير موجود")
                return None
                
            # التحقق من صحة البيانات
            if not all([name, condition_field, condition_operator, condition_value, 
                        action_type, action_field, action_value]):
                logger.error("بيانات القاعدة غير مكتملة")
                return None
                
            # إنشاء القاعدة
            rule = SmartRule(
                name=name,
                description=description,
                condition_field=condition_field,
                condition_operator=condition_operator,
                condition_value=condition_value,
                action_type=action_type,
                action_field=action_field,
                action_value=action_value,
                creator_id=creator_id,
                priority=priority,
                is_active=is_active
            )
            
            db.session.add(rule)
            db.session.commit()
            
            logger.info(f"تم إنشاء قاعدة ذكية جديدة: {name} بواسطة المستخدم {creator_id}")
            return rule.id
    except Exception as e:
        logger.error(f"خطأ في إنشاء قاعدة ذكية: {e}")
        db.session.rollback()
        return None
        
def get_rule(rule_id):
    """
    الحصول على قاعدة ذكية بمعرفها
    
    Args:
        rule_id: معرف القاعدة
        
    Returns:
        SmartRule: كائن القاعدة، أو None في حالة عدم وجودها
    """
    try:
        with app.app_context():
            rule = SmartRule.query.get(rule_id)
            return rule
    except Exception as e:
        logger.error(f"خطأ في استرجاع القاعدة: {e}")
        return None
        
def update_rule(rule_id, **kwargs):
    """
    تحديث قاعدة ذكية موجودة
    
    Args:
        rule_id: معرف القاعدة
        **kwargs: القيم المراد تحديثها
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        with app.app_context():
            rule = SmartRule.query.get(rule_id)
            if not rule:
                logger.error(f"القاعدة {rule_id} غير موجودة")
                return False
                
            # تحديث الحقول المطلوبة
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
                    
            db.session.commit()
            logger.info(f"تم تحديث القاعدة {rule_id} بنجاح")
            return True
    except Exception as e:
        logger.error(f"خطأ في تحديث القاعدة: {e}")
        db.session.rollback()
        return False
        
def delete_rule(rule_id):
    """
    حذف قاعدة ذكية
    
    Args:
        rule_id: معرف القاعدة
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        with app.app_context():
            rule = SmartRule.query.get(rule_id)
            if not rule:
                logger.error(f"القاعدة {rule_id} غير موجودة")
                return False
                
            db.session.delete(rule)
            db.session.commit()
            logger.info(f"تم حذف القاعدة {rule_id} بنجاح")
            return True
    except Exception as e:
        logger.error(f"خطأ في حذف القاعدة: {e}")
        db.session.rollback()
        return False
        
def list_rules(creator_id=None, active_only=False):
    """
    الحصول على قائمة القواعد الذكية
    
    Args:
        creator_id: معرف المستخدم المنشئ (اختياري للتصفية)
        active_only: تصفية القواعد النشطة فقط
        
    Returns:
        list: قائمة بكائنات القواعد
    """
    try:
        with app.app_context():
            query = SmartRule.query
            
            if creator_id:
                query = query.filter_by(creator_id=creator_id)
                
            if active_only:
                query = query.filter_by(is_active=True)
                
            rules = query.order_by(SmartRule.priority).all()
            return rules
    except Exception as e:
        logger.error(f"خطأ في استرجاع قائمة القواعد: {e}")
        return []
        
def toggle_rule_status(rule_id):
    """
    تبديل حالة القاعدة (نشطة/غير نشطة)
    
    Args:
        rule_id: معرف القاعدة
        
    Returns:
        bool: نتيجة العملية
    """
    try:
        with app.app_context():
            rule = SmartRule.query.get(rule_id)
            if not rule:
                logger.error(f"القاعدة {rule_id} غير موجودة")
                return False
                
            rule.is_active = not rule.is_active
            db.session.commit()
            status = "نشطة" if rule.is_active else "غير نشطة"
            logger.info(f"تم تغيير حالة القاعدة {rule_id} إلى {status}")
            return True
    except Exception as e:
        logger.error(f"خطأ في تغيير حالة القاعدة: {e}")
        db.session.rollback()
        return False
        
def apply_smart_rules(tags):
    """
    تطبيق جميع القواعد الذكية النشطة على مجموعة من الوسوم
    
    Args:
        tags: قاموس الوسوم الحالية
        
    Returns:
        tuple: (قاموس الوسوم المعدلة، قائمة بأسماء القواعد المطبقة)
    """
    try:
        with app.app_context():
            return SmartRule.apply_all_rules(tags)
    except Exception as e:
        logger.error(f"خطأ في تطبيق القواعد الذكية: {e}")
        return tags, []
        
def get_available_fields():
    """
    الحصول على قائمة الحقول المتاحة للقواعد
    
    Returns:
        list: قائمة بالحقول المتاحة
    """
    return TAG_FIELDS + [{'id': '*', 'name': 'جميع الحقول'}]
    
def test_smart_rules_on_text(text, field_id):
    """
    اختبار تطبيق القواعد الذكية على نص محدد
    
    Args:
        text: النص المراد اختباره
        field_id: معرف الحقل (مثل "title", "artist", إلخ)
        
    Returns:
        tuple: (النص بعد التطبيق، قائمة القواعد المطبقة، عدد القواعد النشطة)
    """
    try:
        # إنشاء قاموس وسوم افتراضي يحتوي فقط على الحقل المطلوب
        dummy_tags = {field_id: text}
        
        # الحصول على عدد القواعد النشطة
        active_rules_count = 0
        
        with app.app_context():
            active_rules_count = SmartRule.query.filter_by(is_active=True).count()
            
            # تطبيق جميع القواعد النشطة
            modified_tags, applied_rules = SmartRule.apply_all_rules(dummy_tags)
            
            # استرجاع النص المعدل
            modified_text = modified_tags.get(field_id, text)
            
            return modified_text, applied_rules, active_rules_count
            
    except Exception as e:
        logger.error(f"خطأ في اختبار القواعد الذكية: {e}")
        return text, [], 0
    
def get_available_operators():
    """
    الحصول على قائمة العمليات المتاحة للقواعد
    
    Returns:
        list: قائمة بالعمليات المتاحة
    """
    return CONDITION_OPERATORS
    
def get_available_actions():
    """
    الحصول على قائمة الإجراءات المتاحة للقواعد
    
    Returns:
        list: قائمة بالإجراءات المتاحة
    """
    return ACTION_TYPES

def suggest_rule(user_id, old_tags, new_tags):
    """
    اقتراح قاعدة ذكية بناءً على تغييرات المستخدم
    
    Args:
        user_id: معرف المستخدم
        old_tags: الوسوم القديمة
        new_tags: الوسوم الجديدة
        
    Returns:
        dict: قاعدة مقترحة أو None
    """
    suggestions = []
    
    # البحث عن التغييرات في الوسوم
    for field in new_tags:
        if field in old_tags:
            old_value = old_tags[field]
            new_value = new_tags[field]
            
            # إذا تم تغيير القيمة
            if old_value != new_value and field != 'picture':
                # البحث عن قاعدة محتملة
                if field == 'artist' and 'genre' in new_tags:
                    suggestions.append({
                        'name': f"قاعدة مقترحة لـ {old_value}",
                        'description': f"تعيين النوع تلقائياً للفنان {old_value}",
                        'condition_field': 'artist',
                        'condition_operator': 'contains',
                        'condition_value': old_value,
                        'action_type': 'set',
                        'action_field': 'genre',
                        'action_value': new_tags['genre']
                    })
                # اقتراح قاعدة استبدال
                if isinstance(old_value, str) and isinstance(new_value, str) and len(old_value) > 0 and len(new_value) > 0:
                    # البحث عن استبدالات محتملة
                    for i in range(min(len(old_value), 10)):
                        if i + 3 <= len(old_value) and old_value[i:i+3] in new_value:
                            continue
                        if len(old_value) >= 3 and old_value[i:i+3] not in new_value:
                            suggestions.append({
                                'name': f"استبدال في {field}",
                                'description': f"استبدال النص تلقائياً",
                                'condition_field': field,
                                'condition_operator': 'contains',
                                'condition_value': old_value,
                                'action_type': 'replace',
                                'action_field': field,
                                'action_value': new_value
                            })
                            break
    
    return suggestions[0] if suggestions else None


def test_smart_rules(sample_text, field_name='comment', active_only=True, rules_subset=None):
    """
    اختبار تطبيق القواعد الذكية على نص معين
    
    Args:
        sample_text: النص المراد اختباره
        field_name: اسم الحقل الذي سيتم وضع النص فيه (افتراضياً: comment)
        active_only: تطبيق القواعد النشطة فقط
        rules_subset: قائمة بمعرفات قواعد محددة لاختبارها (اختياري)
        
    Returns:
        dict: {
            'original_text': النص الأصلي,
            'modified_text': النص بعد التعديل,
            'applied_rules': قائمة بأسماء القواعد المطبقة ومعلوماتها,
            'changes': التغييرات التي حدثت
        }
    """
    try:
        with app.app_context():
            # إنشاء وسوم تجريبية بالنص المدخل
            tags = {field_name: sample_text}
            
            # تحديد القواعد المراد تطبيقها
            if rules_subset:
                rules = SmartRule.query.filter(SmartRule.id.in_(rules_subset))
                if active_only:
                    rules = rules.filter_by(is_active=True)
                rules = rules.order_by(SmartRule.priority).all()
            else:
                if active_only:
                    rules = SmartRule.query.filter_by(is_active=True).order_by(SmartRule.priority).all()
                else:
                    rules = SmartRule.query.order_by(SmartRule.priority).all()
            
            # تطبيق كل قاعدة وتسجيل نتائجها
            applied_rules_details = []
            original_text = sample_text
            
            for rule in rules:
                before_text = tags.get(field_name, "")
                
                # تطبيق القاعدة
                tags, applied = rule.apply_rule(tags)
                
                after_text = tags.get(field_name, "")
                
                if applied:
                    applied_rules_details.append({
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'before': before_text,
                        'after': after_text,
                        'description': rule.description
                    })
            
            # حساب التغييرات
            modified_text = tags.get(field_name, "")
            
            return {
                'original_text': original_text,
                'modified_text': modified_text,
                'applied_rules': applied_rules_details,
                'changes': len(applied_rules_details) > 0
            }
            
    except Exception as e:
        logger.error(f"خطأ في اختبار القواعد الذكية: {e}")
        return {
            'original_text': sample_text,
            'modified_text': sample_text,
            'applied_rules': [],
            'error': str(e),
            'changes': False
        }


def test_rule_on_text(rule_id, sample_text, field_name='comment'):
    """
    اختبار قاعدة ذكية محددة على نص معين
    
    Args:
        rule_id: معرف القاعدة المراد اختبارها
        sample_text: النص المراد اختباره
        field_name: اسم الحقل الذي سيتم وضع النص فيه
        
    Returns:
        dict: {
            'original_text': النص الأصلي,
            'modified_text': النص بعد التعديل,
            'rule_applied': هل تم تطبيق القاعدة,
            'rule_details': تفاصيل القاعدة
        }
    """
    try:
        with app.app_context():
            rule = SmartRule.query.get(rule_id)
            if not rule:
                return {
                    'original_text': sample_text,
                    'modified_text': sample_text,
                    'rule_applied': False,
                    'error': "القاعدة غير موجودة"
                }
            
            # إنشاء وسوم تجريبية بالنص المدخل
            tags = {field_name: sample_text}
            
            # تطبيق القاعدة
            tags, applied = rule.apply_rule(tags)
            
            return {
                'original_text': sample_text,
                'modified_text': tags.get(field_name, sample_text),
                'rule_applied': applied,
                'rule_details': {
                    'id': rule.id,
                    'name': rule.name,
                    'description': rule.description,
                    'condition': f"{rule.condition_field} {rule.condition_operator} '{rule.condition_value}'",
                    'action': f"{rule.action_type} {rule.action_field} '{rule.action_value}'"
                }
            }
    except Exception as e:
        logger.error(f"خطأ في اختبار القاعدة الذكية: {e}")
        return {
            'original_text': sample_text,
            'modified_text': sample_text,
            'rule_applied': False,
            'error': str(e)
        }
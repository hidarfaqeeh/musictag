from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    """نموذج بيانات المستخدم"""
    id = db.Column(db.Integer, primary_key=True)  # معرف تيليجرام للمستخدم
    username = db.Column(db.String(128), nullable=True)  # اسم المستخدم في تيليجرام
    first_name = db.Column(db.String(128), nullable=True)  # الاسم الأول
    last_name = db.Column(db.String(128), nullable=True)  # الاسم الأخير
    is_admin = db.Column(db.Boolean, default=False)  # هل المستخدم مشرف؟
    is_blocked = db.Column(db.Boolean, default=False)  # هل المستخدم محظور؟
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # وقت إنشاء الحساب
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)  # آخر نشاط
    
    # إحصائيات المستخدم
    files_processed = db.Column(db.Integer, default=0)  # عدد الملفات المعالجة
    total_file_size_mb = db.Column(db.Float, default=0.0)  # إجمالي حجم الملفات بالميجابايت
    daily_usage_mb = db.Column(db.Float, default=0.0)  # الاستخدام اليومي بالميجابايت
    daily_reset_date = db.Column(db.Date, nullable=True)  # تاريخ إعادة تعيين الاستخدام اليومي
    
    # بيانات إضافية (json)
    settings = db.Column(db.Text, default='{}')  # إعدادات المستخدم المخصصة
    
    # العلاقات
    user_templates = db.relationship('UserTemplate', backref='user', lazy=True, cascade="all, delete-orphan")
    user_logs = db.relationship('UserLog', backref='user', lazy=True, cascade="all, delete-orphan")
    
    def get_settings(self):
        """استرجاع إعدادات المستخدم كقاموس"""
        try:
            return json.loads(self.settings)
        except:
            return {}
    
    def set_settings(self, settings_dict):
        """تعيين إعدادات المستخدم من قاموس"""
        self.settings = json.dumps(settings_dict, ensure_ascii=False)
    
    def get_setting(self, key, default=None):
        """استرجاع إعداد محدد للمستخدم"""
        settings = self.get_settings()
        return settings.get(key, default)
    
    def set_setting(self, key, value):
        """تعيين إعداد محدد للمستخدم"""
        settings = self.get_settings()
        settings[key] = value
        self.set_settings(settings)
    
    def update_activity(self):
        """تحديث وقت آخر نشاط"""
        self.last_activity = datetime.utcnow()
    
    def increment_stats(self, file_size_mb=0):
        """زيادة إحصائيات المستخدم"""
        self.files_processed += 1
        self.total_file_size_mb += file_size_mb
        self.daily_usage_mb += file_size_mb
    
    def reset_daily_usage(self):
        """إعادة تعيين الاستخدام اليومي"""
        self.daily_usage_mb = 0
        self.daily_reset_date = datetime.utcnow().date()

class UserTemplate(db.Model):
    """نموذج قوالب المستخدم الخاصة"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    template_name = db.Column(db.String(128), nullable=False)  # اسم القالب
    artist_name = db.Column(db.String(128), nullable=False)  # اسم الفنان
    is_public = db.Column(db.Boolean, default=False)  # هل القالب عام؟
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # وقت إنشاء القالب
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # وقت آخر تحديث
    
    # بيانات القالب (json)
    tags = db.Column(db.Text, nullable=False)  # الوسوم بتنسيق JSON
    album_art = db.Column(db.LargeBinary, nullable=True)  # صورة الألبوم
    album_art_mime = db.Column(db.String(50), nullable=True)  # نوع ملف صورة الألبوم
    
    def get_tags(self):
        """استرجاع الوسوم كقاموس"""
        try:
            return json.loads(self.tags)
        except:
            return {}
    
    def set_tags(self, tags_dict):
        """تعيين الوسوم من قاموس"""
        self.tags = json.dumps(tags_dict, ensure_ascii=False)

class UserLog(db.Model):
    """نموذج سجلات عمليات المستخدم"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(128), nullable=False)  # نوع العملية
    status = db.Column(db.String(50), default='success')  # حالة العملية
    details = db.Column(db.Text, nullable=True)  # تفاصيل العملية
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # وقت العملية
    file_name = db.Column(db.String(256), nullable=True)  # اسم الملف (إن وجد)
    file_size_mb = db.Column(db.Float, default=0.0)  # حجم الملف بالميجابايت (إن وجد)
    
class SmartRule(db.Model):
    """نموذج القواعد الذكية للبوت"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)  # اسم القاعدة
    description = db.Column(db.Text, nullable=True)  # وصف القاعدة
    
    # شروط التطبيق
    condition_field = db.Column(db.String(50), nullable=False)  # الحقل (اسم الفنان، العنوان، إلخ)
    condition_operator = db.Column(db.String(20), nullable=False)  # العملية (يحتوي، يساوي، يبدأ بـ)
    condition_value = db.Column(db.String(255), nullable=False)  # القيمة
    
    # الإجراء المطلوب تنفيذه
    action_type = db.Column(db.String(20), nullable=False)  # نوع الإجراء (إضافة، استبدال، تعيين)
    action_field = db.Column(db.String(50), nullable=False)  # حقل الإجراء
    action_value = db.Column(db.Text, nullable=False)  # قيمة الإجراء
    
    priority = db.Column(db.Integer, default=10)  # أولوية التنفيذ
    is_active = db.Column(db.Boolean, default=True)  # هل القاعدة نشطة
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # المستخدم الذي أنشأ القاعدة
    creator = db.relationship('User', backref='smart_rules')
    
    def apply_rule(self, tags):
        """تطبيق القاعدة على مجموعة من الوسوم"""
        if not self.is_active:
            return tags, False
            
        # التحقق من الشرط
        field_value = tags.get(self.condition_field, "")
        if not field_value:
            return tags, False
            
        rule_applied = False
        
        # تطبيق الشرط
        if self.condition_operator == 'contains' and self.condition_value.lower() in str(field_value).lower():
            rule_applied = True
        elif self.condition_operator == 'equals' and str(field_value).lower() == self.condition_value.lower():
            rule_applied = True
        elif self.condition_operator == 'starts_with' and str(field_value).lower().startswith(self.condition_value.lower()):
            rule_applied = True
        elif self.condition_operator == 'ends_with' and str(field_value).lower().endswith(self.condition_value.lower()):
            rule_applied = True
            
        # تنفيذ الإجراء إذا تحقق الشرط
        if rule_applied:
            if self.action_type == 'add':
                # إضافة إلى الحقل الحالي إذا كان موجودًا
                current_value = tags.get(self.action_field, "")
                if current_value:
                    tags[self.action_field] = f"{current_value}, {self.action_value}"
                else:
                    tags[self.action_field] = self.action_value
            elif self.action_type == 'set':
                # تعيين قيمة الحقل بغض النظر عن قيمته الحالية
                tags[self.action_field] = self.action_value
            elif self.action_type == 'replace':
                # استبدال في جميع الحقول
                if self.action_field == '*':
                    for key in tags:
                        if isinstance(tags[key], str):
                            tags[key] = tags[key].replace(self.condition_value, self.action_value)
                # استبدال في حقل محدد
                elif self.action_field in tags and isinstance(tags[self.action_field], str):
                    tags[self.action_field] = tags[self.action_field].replace(self.condition_value, self.action_value)
            
        return tags, rule_applied
    
    @staticmethod
    def apply_all_rules(tags):
        """تطبيق جميع القواعد النشطة على مجموعة من الوسوم"""
        rules = SmartRule.query.filter_by(is_active=True).order_by(SmartRule.priority).all()
        applied_rules = []
        
        for rule in rules:
            tags, applied = rule.apply_rule(tags)
            if applied:
                applied_rules.append(rule.name)
                
        return tags, applied_rules
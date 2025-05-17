# استخدام صورة Python الرسمية
FROM python:3.10-slim

# تعيين دليل العمل داخل الحاوية
WORKDIR /app

# نسخ ملفات المشروع إلى الحاوية
COPY . .

# تثبيت Poetry لإدارة التبعيات
RUN pip install --no-cache-dir poetry

# تثبيت التبعيات المحددة في pyproject.toml
RUN poetry install --no-root

# تحديد المتغير البيئي لبيئة التشغيل
ENV PYTHONUNBUFFERED=1

# الأمر الافتراضي لتشغيل البوت
CMD ["poetry", "run", "python", "main.py"]

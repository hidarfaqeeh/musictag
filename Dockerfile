# صورة أساس Python
FROM python:3.11-slim

# تعيين مجلد العمل
WORKDIR /app

# تثبيت pipx لتثبيت الأدوات بشكل معزول (مثل poetry إذا لزم)
RUN apt-get update && apt-get install -y gcc libpq-dev && \
    pip install --upgrade pip && \
    pip install poetry && \
    apt-get clean

# نسخ ملفات المشروع
COPY . .

# تثبيت التبعيات من pyproject.toml
RUN poetry config virtualenvs.create false \
    && poetry install --only main

# تعيين متغيرات البيئة (يمكنك تعديلها أو إدارتها من منصة النشر)
ENV PYTHONUNBUFFERED=1

# الأمر الافتراضي لتشغيل البوت
CMD ["python", "bot.py"]

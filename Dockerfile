FROM python:3.11-slim

WORKDIR /app

# Python buferlashni o'chirish
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Koyeb uchun port
EXPOSE 8000

CMD ["python", "bot.py"]

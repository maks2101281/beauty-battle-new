FROM python:3.10-slim

WORKDIR /app

# Копируем файлы проекта
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем базу данных (если не существует)
RUN touch facemash.db

# Переменные окружения
ENV MODE=webhook
ENV PORT=10000
ENV PYTHONUNBUFFERED=1

# Открываем порт
EXPOSE $PORT

# Запускаем приложение через Gunicorn для лучшей производительности
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 bot:app 
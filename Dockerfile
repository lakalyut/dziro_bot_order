# Используем минимальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY . .

# Переменные окружения будут передаваться через docker-compose
ENV PYTHONUNBUFFERED=1

# Команда запуска
CMD ["python", "bot1.py"]

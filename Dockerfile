FROM python:3.11-slim

WORKDIR /app

# Копируем requirements
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY bot_prometheus_fixed.py main.py

# Открываем порты
EXPOSE 8000

# Запускаем бота
CMD ["python", "main.py"]

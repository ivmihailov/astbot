FROM python:3.12-slim

WORKDIR /app

# Зависимости отдельным слоем (кэшируется при изменении только кода)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Исходный код
COPY *.py .
COPY .env.example .

# Бот слушает long-polling, порты не нужны
CMD ["python", "bot.py"]

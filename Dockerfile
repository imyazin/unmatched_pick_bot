FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos '' botuser && chown -R botuser:botuser /app

USER botuser

EXPOSE 8080

CMD ["python", "bot/bot.py"]
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug", "--access-log"]

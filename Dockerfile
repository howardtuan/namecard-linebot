FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV GUNICORN_TIMEOUT=180

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

WORKDIR /app

EXPOSE 8080

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn bot.wsgi:application --bind 0.0.0.0:${PORT:-8080} --timeout ${GUNICORN_TIMEOUT:-180}"]

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install gunicorn whitenoise

COPY . .

RUN mkdir -p logs

CMD gunicorn agri_ops_project.wsgi:application --bind "0.0.0.0:${PORT}" --workers 2 --timeout 120 --access-logfile - --error-logfile -

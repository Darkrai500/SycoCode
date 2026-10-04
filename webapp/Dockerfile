FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/webapp
COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 sycocode
COPY webapp/manage.py /app/webapp/manage.py
COPY webapp/config /app/webapp/config
COPY webapp/annotations /app/webapp/annotations
COPY webapp/templates /app/webapp/templates
COPY webapp/static /app/webapp/static
COPY webapp/backup.py /app/webapp/backup.py
COPY eval /app/eval
COPY scripts/gold_annotator.py /app/scripts/gold_annotator.py
COPY data/goldset/pool.jsonl data/goldset/pool_manifest.json /app/data/goldset/
COPY data/goldset/payloads /app/data/goldset/payloads
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput && mkdir -p /state && chown -R sycocode:sycocode /state
USER sycocode
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 60 --access-logfile - --error-logfile -"]

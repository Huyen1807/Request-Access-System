FROM python:3.12-slim

WORKDIR /app

# Copy toàn bộ project
COPY . .

# Cài pip từ requirements.txt trong folder reqsys
RUN pip install --no-cache-dir -r reqsys/requirements.txt

# Collect static files
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

RUN chmod +x build.sh

CMD ["/bin/sh", "-c", "./build.sh && gunicorn reqsys.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
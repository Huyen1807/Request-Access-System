FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r reqsys/requirements.txt

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Thêm reqsys/ prefix
RUN chmod +x reqsys/build.sh

# Thêm reqsys/ prefix
CMD ["/bin/sh", "-c", "reqsys/build.sh && gunicorn reqsys.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
FROM docker.io/library/python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py mobile.py app_config.py mailer.py ./
COPY templates templates
ENV DB_PATH=/data/attendance.db
VOLUME /data
EXPOSE 8000
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:8000", "--access-logfile", "-", "app:app"]

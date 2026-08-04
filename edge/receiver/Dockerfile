FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py uploader.py ./
COPY templates ./templates

EXPOSE 5001
# Flask's dev server is fine here (one client, one request per press), but
# gunicorn keeps it tidy and handles the background export threads well.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "1", "--threads", "4", "app:app"]

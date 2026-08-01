FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Multiple workers on purpose: unlike the edge app (--workers 1, in-process
# cooldown state), this app is stateless — sessions are signed cookies, all
# shared state lives in Postgres.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "wsgi:app"]

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=wsgi.py
EXPOSE 8000

# Shell form on purpose, so $PORT expands: most hosts (Render, Railway,
# Heroku) inject the port to bind and drop traffic if you ignore it.
#
# Migrations run here rather than in a separate release step to keep a test
# deploy to one moving part. With more than one instance they'd race — move
# `flask db upgrade` to the host's release/pre-deploy hook before scaling up.
#
# Multiple workers on purpose: unlike the edge app (--workers 1, in-process
# cooldown state), this app is stateless — sessions are signed cookies, all
# shared state lives in Postgres.
CMD flask db upgrade && \
    exec gunicorn --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-4}" wsgi:app

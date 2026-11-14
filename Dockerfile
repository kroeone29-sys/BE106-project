# Dockerfile
#
# Builds a production-ready container image for the Flask EngineLog service.
# The image includes the Python runtime, application dependencies, and
# application code, but excludes environment-specific configuration such as
# JWT secrets and database URLs. Those are supplied at runtime as
# environment variables when the container is started.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY wsgi.py .

ENV PORT=8000

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "wsgi:app"]
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home court
COPY --chown=court:court . .
USER court
ENV PORT=8080 APP_REQUIRE_AUTH=true PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:application"]

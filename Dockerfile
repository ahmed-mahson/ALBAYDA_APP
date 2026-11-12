FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALBAYDA_HOST=0.0.0.0
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py case_records.py court_source.py ./
COPY assets ./assets
COPY web ./web

RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 10000
CMD ["python", "app.py"]

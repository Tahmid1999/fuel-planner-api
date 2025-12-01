FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt /app/

RUN python -m pip install --upgrade pip && \
    pip install -r requirements-dev.txt

COPY . /app

EXPOSE 8000

CMD ["gunicorn", "fuelplanner.wsgi:application", "--bind", "0.0.0.0:8000"]


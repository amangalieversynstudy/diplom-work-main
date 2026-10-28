FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends build-essential libpq-dev wget \
	&& rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt ./requirements-dev.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt -r /app/requirements-dev.txt

COPY . /app

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "core.asgi:application"]

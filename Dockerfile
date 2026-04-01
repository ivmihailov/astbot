FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system astbot \
    && useradd --system --gid astbot --create-home --home-dir /home/astbot astbot

COPY . /app

RUN pip install --upgrade pip \
    && pip install .

RUN mkdir -p /app/data /app/logs /app/storage/photos /app/docker \
    && chmod +x /app/docker/entrypoint.sh \
    && chown -R astbot:astbot /app

USER astbot

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["python", "-u", "bot.py"]

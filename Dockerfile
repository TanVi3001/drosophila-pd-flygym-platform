FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    MPLCONFIGDIR=/tmp/matplotlib \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY configs ./configs
COPY scripts ./scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install '.[workbench]' \
    && groupadd --system --gid 10001 workbench \
    && useradd --system --uid 10001 --gid 10001 --no-create-home workbench \
    && mkdir -p /var/lib/workbench \
    && chown -R 10001:10001 /var/lib/workbench

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2).read()" || exit 1

ENTRYPOINT ["python", "-m", "drosophila_pd.workbench.server"]
CMD ["--db", "/var/lib/workbench/workbench.sqlite3", "--artifacts", "/var/lib/workbench/artifacts", "--host", "0.0.0.0", "--port", "8000"]

# Cloud Run sets PORT=8080 by default; uvicorn must bind to it.
# Linux uses SelectorEventLoop by default so the dev.py wrapper isn't needed
# in production -- uvicorn main:app works directly.
FROM python:3.12-slim

WORKDIR /app

# Install uv: fastest cold-start for a small dep tree.
RUN pip install --no-cache-dir uv

# Copy lockfile first so dependency layer is cached when only source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PORT=8080
EXPOSE 8080
CMD ["uv", "run", "--no-dev", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

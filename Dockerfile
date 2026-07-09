# Start from a small official Python 3.12 image (Linux).
FROM python:3.12-slim

# Copy the uv binary in from its official image, so we can use uv inside the build.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# All following commands run inside this folder in the image.
WORKDIR /app

# Copy ONLY the dependency files first, then install.
# Docker caches this layer, so deps reinstall only when these files change —
# editing your app code won't trigger a slow re-install.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Now copy your application code.
COPY app ./app

# Put the project's virtual environment on PATH so "uvicorn" is found directly.
ENV PATH="/app/.venv/bin:$PATH"

# Document that the app listens on port 8000.
EXPOSE 8000

# The command that runs when the container starts.
# host 0.0.0.0 = "accept connections from outside the container" (required in Docker).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

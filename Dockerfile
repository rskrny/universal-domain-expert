FROM python:3.11-slim

WORKDIR /app

# Install only production dependencies (no ML models)
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code
COPY prompts/ prompts/
COPY retrieval/ retrieval/
COPY dashboard/ dashboard/
COPY scripts/ scripts/
COPY CLAUDE.md .

# Build BM25-only index at build time (no semantic model needed)
RUN python scripts/setup.py --lite

# Expose port
EXPOSE 8501

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "dashboard.server:app", "--host", "0.0.0.0", "--port", "8501"]

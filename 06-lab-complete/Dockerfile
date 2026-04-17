FROM python:3.11-slim

WORKDIR /app

# Install dependencies as ROOT
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user AFTER install
RUN groupadd -r agent && useradd -r -g agent -d /app agent

# Copy app
COPY app/ ./app/
COPY utils/ ./utils/

RUN chown -R agent:agent /app

USER agent

ENV PYTHONPATH=/app

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
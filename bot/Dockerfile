FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY trader ./trader
RUN useradd -m bot && mkdir -p /app/data && chown bot /app/data
USER bot
CMD ["python", "-m", "trader", "run"]

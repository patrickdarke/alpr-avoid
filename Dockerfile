FROM python:3.12-slim

# app.py shells out to `curl` for the routing/geocoding calls.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app.py index.html ./
COPY data/cameras.bin ./data/cameras.bin

# Bind to all interfaces so the app is reachable from outside the container.
ENV HOST=0.0.0.0 PORT=8787
EXPOSE 8787

CMD ["python", "app.py"]

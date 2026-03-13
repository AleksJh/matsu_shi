FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    git curl build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# uv — same package manager as in backend/Dockerfile
RUN pip install uv

WORKDIR /workspace
CMD ["sleep", "infinity"]

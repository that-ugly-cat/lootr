FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# docker compose build --build-arg GIT_COMMIT=$(git rev-parse --short=12 HEAD)
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT}

ENV LOOTR_DB=/data/lootr.db
EXPOSE 8016

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8016"]

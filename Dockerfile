FROM python:3.11-slim

WORKDIR /code

# install deps first so this layer caches when only app code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY mock_data ./mock_data

# memory + audit dbs and logs are written here at runtime
RUN mkdir -p data logs
VOLUME ["/code/data"]

EXPOSE 8000
# shell form so $PORT (injected by the host) is honoured; falls back to 8000 locally
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

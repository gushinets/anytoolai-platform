FROM python:3.12-slim
WORKDIR /app
COPY . .
CMD ["python", "apps/platform-worker/src/anytoolai_platform_worker/main.py"]

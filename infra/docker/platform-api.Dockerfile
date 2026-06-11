FROM python:3.12-slim
WORKDIR /app
COPY . .
CMD ["python", "-m", "apps.platform-api.src.anytoolai_platform_api.main"]

FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend-build /frontend/dist ./frontend/dist
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 1888
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "web.index:app", "--host", "0.0.0.0", "--port", "1888"]

# Multi-stage build for RestoBot webapp
# Usage (optional): docker build -t restobot-webapp -f frontend/webapp/Dockerfile frontend/webapp

# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve static files via nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY <<EOF /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;
    location / {
        try_files \$uri \$uri/ /index.html;
    }
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
}
EOF
EXPOSE 80

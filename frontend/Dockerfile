# Stage 1: Build
FROM node:18-alpine as build-stage

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

# Build with API URL set to relative path for Nginx proxying
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Stage 2: Production
FROM nginx:stable-alpine as production-stage

COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

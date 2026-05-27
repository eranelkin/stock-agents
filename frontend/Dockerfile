FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend/package.json .
RUN npm install

COPY frontend/ .
RUN npm run build

FROM node:20-alpine
RUN npm install -g serve
WORKDIR /app
COPY --from=builder /app/dist ./dist

CMD ["serve", "-s", "dist", "-l", "4100"]

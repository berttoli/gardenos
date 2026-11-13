FROM node:22-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_GARDENOS_API_BASE_URL=http://127.0.0.1:8000/api/v1
ENV VITE_GARDENOS_API_BASE_URL=${VITE_GARDENOS_API_BASE_URL}
RUN npm run build

FROM node:22-bookworm-slim AS runtime

ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY serve.mjs ./serve.mjs
USER node

EXPOSE 3000

CMD ["node", "serve.mjs"]

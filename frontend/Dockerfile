FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG API_BASE_URL
ENV API_BASE_URL=${API_BASE_URL}
ENV NUXT_PUBLIC_API_BASE=${API_BASE_URL}

RUN npm run build

ENV HOST=0.0.0.0
ENV PORT=3000
EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]

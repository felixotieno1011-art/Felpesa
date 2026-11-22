FROM node:20-slim

WORKDIR /app

# Install deps first (layer caching)
COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]

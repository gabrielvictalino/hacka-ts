FROM node:22-alpine
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
COPY packages /app/packages
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

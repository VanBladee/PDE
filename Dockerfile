FROM node:20-alpine

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

WORKDIR /app

ENV TZ=America/Denver

# Copy package files
COPY package*.json ./

# Install dependencies - production only for smaller image
RUN npm ci --omit=dev

# Copy TypeScript config and source
COPY tsconfig.json ./
COPY src ./src
COPY scripts ./scripts

# Build the application
RUN npm install -g typescript && npm run build

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Copy and set permissions for entrypoint
COPY --chmod=755 ./scripts/docker-entrypoint.sh /docker-entrypoint.sh

# Change ownership
RUN chown -R nodejs:nodejs /app

USER nodejs

EXPOSE 3000

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--", "/docker-entrypoint.sh"]
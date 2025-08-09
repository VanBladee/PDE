#!/bin/sh
set -e

echo "🚀 Starting PDE container..."

# Run create-indexes script
echo "📇 Creating database indexes..."
node dist/scripts/create-indexes.js

# Run db-health check (allow failure)
echo "🏥 Checking database health..."
node dist/scripts/db-health.js || true

# Start the server
echo "🌐 Starting PDE server..."
exec node dist/index.js
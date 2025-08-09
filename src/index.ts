import express from 'express';
import { MongoClient } from 'mongodb';
import routes from './routes';
import { errorHandler } from './middleware/error-handler';

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Routes
app.use('/', routes);

// Error handler (must be last)
app.use(errorHandler);

// MongoDB connection and server start
async function start() {
  const mongoUri = process.env.MONGO_URI;
  if (!mongoUri) {
    console.error('MONGO_URI environment variable is required');
    process.exit(1);
  }

  try {
    const client = new MongoClient(mongoUri);
    await client.connect();
    console.log('Connected to MongoDB');

    // Make client available to routes
    app.locals.mongoClient = client;

    app.listen(PORT, () => {
      console.log(`Server running on port ${PORT}`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down...');
  const client = app.locals.mongoClient as MongoClient;
  if (client) {
    await client.close();
  }
  process.exit(0);
});

// Start server
if (require.main === module) {
  start();
}

export default app;
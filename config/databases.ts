import mongoose, { Connection, Schema } from 'mongoose';
import { env } from './env';

export const DATABASE_NAMES = {
  REGISTRY: 'registry',
  OD_LIVE: 'od_live',
  ACTIVITY: 'activity',
  CRUCIBLE: 'crucible',
  DEFAULT: env.MONGO_DB_NAME
} as const;

export type DatabaseName = typeof DATABASE_NAMES[keyof typeof DATABASE_NAMES];
const dbConnections: Map<DatabaseName, Connection> = new Map();
let isInitialized = false;

export const initializeDatabases = () => {
  if (isInitialized) return;
  console.log('Initializing all database connections uniformly...');
  Object.values(DATABASE_NAMES).forEach(dbName => {
    try {
      // Treat all databases equally. Get the connection and store it.
      const dbConnection = mongoose.connection.useDb(dbName);
      dbConnections.set(dbName, dbConnection);
      console.log(`Connection for database '${dbName}' established and stored.`);
    } catch (error) {
      console.error(`Failed to establish connection for database ${dbName}:`, error);
    }
  });
  isInitialized = true;
};

export const getDatabase = (dbName: DatabaseName): Connection => {
  if (!isInitialized) initializeDatabases();
  const connection = dbConnections.get(dbName);
  if (!connection) throw new Error(`Database connection for ${dbName} not found.`);
  return connection;
};

// Original, complex proxy logic restored
export const createModel = <T extends mongoose.Document>(
  dbName: DatabaseName,
  modelName: string,
  schema: Schema<T>
): mongoose.Model<T> => {
  let actualModel: mongoose.Model<T>;
  const handler: ProxyHandler<any> = {
    get(target, prop) {
      if (!actualModel) {
        const db = getDatabase(dbName);
        try {
          actualModel = db.model<T>(modelName, schema);
        } catch (e) {
          actualModel = db.model<T>(modelName);
        }
      }
      const value = actualModel[prop as keyof typeof actualModel];
      return typeof value === 'function' ? (value as any).bind(actualModel) : value;
    }
  };
  return new Proxy({}, handler) as mongoose.Model<T>;
};

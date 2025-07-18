import neo4j, { Driver, Session } from 'neo4j-driver';
import { config } from '../utils/config.js';
import { logger } from '../utils/logger.js';

class Neo4jClient {
  private driver: Driver;

  constructor() {
    try {
      const auth = config.neo4jPassword 
        ? neo4j.auth.basic(config.neo4jUser, config.neo4jPassword)
        : neo4j.auth.basic(config.neo4jUser, '');
      
      this.driver = neo4j.driver(config.neo4jUri, auth);
      this.initializeDatabase();
    } catch (error) {
      logger.error('Failed to connect to Neo4j', error);
      throw error;
    }
  }

  private async initializeDatabase(): Promise<void> {
    try {
      await this.driver.verifyConnectivity();
      logger.info('Successfully connected to Neo4j.');
      
      // Create necessary indexes and constraints
      await this.createIndexesAndConstraints();
      
    } catch (error) {
      logger.error('Failed to initialize Neo4j database:', error);
      // Don't throw here to allow the application to continue
    }
  }

  private async createIndexesAndConstraints(): Promise<void> {
    const session = this.getSession();
    try {
      // Create constraints for unique identifiers
      const constraints = [
        'CREATE CONSTRAINT function_name_unique IF NOT EXISTS FOR (f:Function) REQUIRE f.name IS UNIQUE',
        'CREATE CONSTRAINT class_name_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.name IS UNIQUE',
        'CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.file_path IS UNIQUE'
      ];

      // Create indexes for better performance
      const indexes = [
        'CREATE INDEX function_name_index IF NOT EXISTS FOR (f:Function) ON (f.name)',
        'CREATE INDEX class_name_index IF NOT EXISTS FOR (c:Class) ON (c.name)',
        'CREATE INDEX file_name_index IF NOT EXISTS FOR (f:File) ON (f.name)',
        'CREATE INDEX file_path_index IF NOT EXISTS FOR (f:File) ON (f.file_path)'
      ];

      for (const constraint of constraints) {
        try {
          await session.run(constraint);
        } catch (error) {
          // Constraint might already exist, log but continue
          logger.debug(`Constraint creation result: ${error instanceof Error ? error.message : String(error)}`);
        }
      }

      for (const index of indexes) {
        try {
          await session.run(index);
        } catch (error) {
          // Index might already exist, log but continue
          logger.debug(`Index creation result: ${error instanceof Error ? error.message : String(error)}`);
        }
      }

      logger.info('Neo4j indexes and constraints initialized successfully');
    } catch (error) {
      logger.error('Error creating Neo4j indexes and constraints:', error);
    } finally {
      await session.close();
    }
  }

  public getSession(): Session {
    return this.driver.session({
      database: process.env.NEO4J_DATABASE || 'neo4j'
    });
  }

  public async close(): Promise<void> {
    await this.driver.close();
    logger.info('Neo4j connection closed.');
  }

  /**
   * A helper to execute a query and format the results into a clean JSON array.
   */
  public async executeQuery(query: string, params: Record<string, any> = {}) {
    const session = this.getSession();
    try {
      const result = await session.run(query, params);
      // Convert Neo4j's integer objects to standard numbers and records to plain objects
      return result.records.map((record: any) => {
        const obj: Record<string, any> = {};
        record.keys.forEach((key: string) => {
          obj[key] = record.get(key);
        });
        return obj;
      });
    } finally {
      await session.close();
    }
  }
}

export const neo4jClient = new Neo4jClient();

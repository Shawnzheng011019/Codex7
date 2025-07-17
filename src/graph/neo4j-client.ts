import neo4j, { Driver, Session } from 'neo4j-driver';
import { config } from '../utils/config.js';
import { logger } from '../utils/logger.js';

class Neo4jClient {
  private driver: Driver;

  constructor() {
    try {
      const auth = config.neo4j.password 
        ? neo4j.auth.basic(config.neo4j.user, config.neo4j.password)
        : neo4j.auth.basic(config.neo4j.user, '');
      
      this.driver = neo4j.driver(config.neo4j.uri, auth);
      this.driver.verifyConnectivity().then(() => {
        logger.info('Successfully connected to Neo4j.');
      });
    } catch (error) {
      logger.error('Failed to connect to Neo4j', error);
      throw error;
    }
  }

  public getSession(): Session {
    return this.driver.session({
      database: config.neo4j.database || 'neo4j'
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

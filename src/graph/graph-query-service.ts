import { neo4jClient } from './neo4j-client.js';
import { logger } from '../utils/logger.js';

export class GraphQueryService {
  /**
   * Finds all functions and classes that might be affected by a change
   * in a given function (downstream impact analysis).
   * This is a multi-hop query that traverses the graph backwards.
   * @param functionName The name of the function to analyze.
   * @param maxHops The maximum number of hops to traverse.
   */
  async findDownstreamImpact(functionName: string, maxHops = 5) {
    logger.info(`Finding downstream impact for function: ${functionName}`);
    try {
      const query = `
        MATCH (startNode:Function {name: $functionName})
        // Follow CALLS relationships backwards
        MATCH (startNode)<-[:CALLS*1..${maxHops}]-(caller)
        RETURN DISTINCT
          caller.name as entityName,
          labels(caller)[0] as entityType,
          caller.file_path as filePath
      `;
      return await neo4jClient.executeQuery(query, { functionName });
    } catch (error) {
      logger.error(`Error finding downstream impact for ${functionName}:`, error);
      return []; // Return empty array on error
    }
  }

  /**
   * Finds all functions and classes that a given function depends on
   * (upstream dependency analysis).
   * This is a multi-hop query that traverses the graph forwards.
   * @param functionName The name of the function to analyze.
   * @param maxHops The maximum number of hops to traverse.
   */
  async findUpstreamDependencies(functionName: string, maxHops = 5) {
    logger.info(`Finding upstream dependencies for function: ${functionName}`);
    try {
      const query = `
        MATCH (startNode:Function {name: $functionName})
        // Follow CALLS relationships forwards
        MATCH (startNode)-[:CALLS*1..${maxHops}]->(callee)
        RETURN DISTINCT
          callee.name as entityName,
          labels(callee)[0] as entityType,
          callee.file_path as filePath
      `;
      return await neo4jClient.executeQuery(query, { functionName });
    } catch (error) {
      logger.error(`Error finding upstream dependencies for ${functionName}:`, error);
      return []; // Return empty array on error
    }
  }

  /**
   * Retrieves the full inheritance chain for a given class.
   * @param className The name of the class.
   */
  async getClassInheritance(className: string) {
    logger.info(`Getting inheritance chain for class: ${className}`);
    try {
      const query = `
        MATCH (startClass:Class {name: $className})
        // Match both superclasses (up the chain) and subclasses (down the chain)
        MATCH path = (startClass)-[:INHERITS_FROM*0..]-(relatedClass)
        WITH collect(path) as paths
        UNWIND paths as p
        WITH nodes(p) as classNodes
        UNWIND classNodes as node
        RETURN DISTINCT node.name as className, node.file_path as filePath
      `;
      return await neo4jClient.executeQuery(query, { className });
    } catch (error) {
      logger.error(`Error getting inheritance chain for ${className}:`, error);
      return []; // Return empty array on error
    }
  }

  /**
   * Takes a natural language query, extracts potential entity names,
   * and finds related terms from the knowledge graph to expand the query.
   * @param queryString The natural language query.
   * @returns An array of expansion terms.
   */
  async expandQueryWithGraph(queryString: string): Promise<string[]> {
    try {
      // 1. Extract potential entity names from the query.
      // This is a simple implementation. A more advanced version could use an LLM or NLP library.
      const potentialTerms = queryString
        .toLowerCase()
        .split(/[\s\W]+/) // Split by spaces and non-alphanumeric characters
        .filter(term => term.length > 3 && !['the', 'for', 'with', 'how', 'does'].includes(term)); // Basic stopword removal

      if (potentialTerms.length === 0) {
        return [];
      }

      logger.debug(`Graph expansion: potential terms found: ${potentialTerms.join(', ')}`);

      // 2. Query the graph to find nodes matching these terms.
      // We look for nodes where the name CONTAINS one of our terms.
      const query = `
        UNWIND $terms as term
        MATCH (n)
        WHERE toLower(n.name) CONTAINS term
        // Also find the file that contains this node, as its name is very valuable context
        OPTIONAL MATCH (file:File)-[:CONTAINS]->(n)
        WITH n, file
        LIMIT 10 // Limit to avoid overly broad queries
        RETURN n.name as entityName, file.name as fileName
      `;

      const results = await neo4jClient.executeQuery(query, { terms: potentialTerms });

      // 3. Collect unique, relevant terms for expansion.
      const expansionTerms = new Set<string>();
      for (const record of results) {
        if (record.entityName) {
          expansionTerms.add(record.entityName);
        }
        if (record.fileName) {
          expansionTerms.add(record.fileName);
        }
      }
      
      const finalTerms = Array.from(expansionTerms);
      logger.info(`Graph expansion: found terms: ${finalTerms.join(', ')}`);
      
      return finalTerms;
    } catch (error) {
      logger.error(`Error expanding query with graph for "${queryString}":`, error);
      return []; // Return empty array on error
    }
  }
}

export const graphQueryService = new GraphQueryService();

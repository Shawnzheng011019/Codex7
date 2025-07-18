import { neo4jClient } from './neo4j-client.js';
import { logger } from '../utils/logger.js';
import { CodeEntity, ASTAnalysisResult } from '../parser/ast-parser.js';

export interface GraphEntity {
  id: string;
  type: string;
  name: string;
  filePath: string;
  startLine: number;
  endLine: number;
  signature?: string;
  body?: string;
  parameters?: string[];
  returnType?: string;
  modifiers?: string[];
  language: string;
  repo: string;
}

export interface GraphRelationship {
  from: string;
  to: string;
  type: string;
  properties?: Record<string, any>;
}

export class CodeGraphService {
  /**
   * Store code entities and relationships in Neo4j graph database
   */
async storeCodeStructure(
    analysis: ASTAnalysisResult,
    filePath: string,
    repo: string,
    language: string
  ): Promise<void> {
    const session = neo4jClient.getSession();
    
    try {
      logger.info(`Storing code structure for ${filePath} in Neo4j`);
      
      // Create file node
      await this.createFileNode(session, filePath, repo);
      
      // Create entities (functions, classes, methods, variables)
      const entityMap = new Map<string, string>();
      
      for (const entity of analysis.entities) {
        const entityId = await this.createEntityNode(session, {
          ...entity,
          filePath,
          repo,
          language
        });
        entityMap.set(entity.name, entityId);
      }
      
      // Create relationships
      for (const relationship of analysis.relationships) {
        await this.createRelationship(session, relationship, filePath, repo);
      }
      
      // Create imports and exports
      for (const imp of analysis.imports) {
        await this.createImportRelationship(session, filePath, imp);
      }
      
      for (const exp of analysis.exports) {
        await this.createExportRelationship(session, filePath, exp, repo);
      }
      
      logger.info(`Successfully stored code structure for ${filePath}`);
      
    } catch (error) {
      logger.error(`Error storing code structure for ${filePath}:`, error);
      throw error;
    } finally {
      await session.close();
    }
  }

  private async createFileNode(session: any, filePath: string, repo: string): Promise<void> {
    const query = `
      MERGE (f:File {file_path: $filePath, repo: $repo})
      ON CREATE SET 
        f.created_at = datetime(),
        f.name = split($filePath, '/')[-1]
      ON MATCH SET 
        f.updated_at = datetime()
    `;
    
    await session.run(query, { filePath, repo });
  }

  private async createEntityNode(
    session: any, 
    entity: CodeEntity & { repo: string; language: string }
  ): Promise<string> {
    // Use a more robust composite key that includes all identifying information
    const entityId = `${entity.repo}::${entity.filePath}::${entity.name}::${entity.type}::${entity.startLine}`;
    
    // Ensure name is unique by adding file context to avoid constraint violations
    const uniqueName = `${entity.name}_${entity.filePath.split('/').pop()?.replace(/\./g, '_')}_${entity.startLine}`;
    
    let query = '';
    let params: any = {
      id: entityId,
      name: entity.name, // Keep original name for display
      uniqueName: uniqueName, // Use unique name for constraints
      filePath: entity.filePath,
      startLine: entity.startLine,
      endLine: entity.endLine,
      language: entity.language,
      repo: entity.repo
    };

    switch (entity.type) {
      case 'class':
        query = `
          MERGE (c:Class {id: $id})
          SET c.name = $name,
              c.unique_name = $uniqueName,
              c.file_path = $filePath,
              c.start_line = $startLine,
              c.end_line = $endLine,
              c.language = $language,
              c.repo = $repo,
              c.signature = $signature,
              c.extends = $extends,
              c.implements = $implements,
              c.updated_at = datetime()
        `;
        params.signature = entity.signature || '';
        params.extends = entity.extends || [];
        params.implements = entity.implements || [];
        break;
        
      case 'function':
        query = `
          MERGE (f:Function {id: $id})
          SET f.name = $name,
              f.unique_name = $uniqueName,
              f.file_path = $filePath,
              f.start_line = $startLine,
              f.end_line = $endLine,
              f.language = $language,
              f.repo = $repo,
              f.signature = $signature,
              f.parameters = $parameters,
              f.return_type = $returnType,
              f.updated_at = datetime()
        `;
        params.signature = entity.signature || '';
        params.parameters = entity.parameters || [];
        params.returnType = entity.returnType || '';
        break;
        
      case 'method':
        query = `
          MERGE (m:Method {id: $id})
          SET m.name = $name,
              m.unique_name = $uniqueName,
              m.file_path = $filePath,
              m.start_line = $startLine,
              m.end_line = $endLine,
              m.language = $language,
              m.repo = $repo,
              m.signature = $signature,
              m.parameters = $parameters,
              m.return_type = $returnType,
              m.updated_at = datetime()
        `;
        params.signature = entity.signature || '';
        params.parameters = entity.parameters || [];
        params.returnType = entity.returnType || '';
        break;
        
      case 'variable':
        query = `
          MERGE (v:Variable {id: $id})
          SET v.name = $name,
              v.file_path = $filePath,
              v.start_line = $startLine,
              v.end_line = $endLine,
              v.language = $language,
              v.repo = $repo,
              v.updated_at = datetime()
        `;
        break;
        
      case 'interface':
        query = `
          MERGE (i:Interface {id: $id})
          SET i.name = $name,
              i.file_path = $filePath,
              i.start_line = $startLine,
              i.end_line = $endLine,
              i.language = $language,
              i.repo = $repo,
              i.signature = $signature,
              i.updated_at = datetime()
        `;
        params.signature = entity.signature || '';
        break;
        
      case 'enum':
        query = `
          MERGE (e:Enum {id: $id})
          SET e.name = $name,
              e.file_path = $filePath,
              e.start_line = $startLine,
              e.end_line = $endLine,
              e.language = $language,
              e.repo = $repo,
              e.updated_at = datetime()
        `;
        break;
    }

    await session.run(query, params);
    
    // Create CONTAINS relationship between File and Entity
    const containsQuery = `
      MATCH (f:File {file_path: $filePath, repo: $repo})
      MATCH (e {id: $entityId})
      MERGE (f)-[:CONTAINS]->(e)
    `;
    
    await session.run(containsQuery, { 
      filePath: entity.filePath, 
      repo: entity.repo, 
      entityId 
    });
    
    return entityId;
  }

  private async createRelationship(
    session: any, 
    relationship: { caller: string; callee: string; type: string; filePath?: string; repo?: string },
    filePath: string,
    repo: string
  ): Promise<void> {
    const query = `
      MATCH (caller {name: $callerName, file_path: $filePath, repo: $repo})
      MATCH (callee {name: $calleeName, file_path: $filePath, repo: $repo})
      MERGE (caller)-[r:${relationship.type}]->(callee)
      SET r.created_at = datetime()
    `;
    
    await session.run(query, {
      callerName: relationship.caller,
      calleeName: relationship.callee,
      filePath,
      repo
    });
  }

  private async createImportRelationship(
    session: any, 
    filePath: string, 
    imp: { module: string; names: string[] }
  ): Promise<void> {
    const query = `
      MATCH (f:File {file_path: $filePath})
      MERGE (m:Module {name: $moduleName})
      ON CREATE SET m.created_at = datetime()
      MERGE (f)-[:IMPORTS {names: $names}]->(m)
    `;
    
    await session.run(query, {
      filePath,
      moduleName: imp.module,
      names: imp.names
    });
  }

  private async createExportRelationship(
    session: any, 
    filePath: string, 
    exp: { name: string; type: string },
    repo: string
  ): Promise<void> {
    const query = `
      MATCH (f:File {file_path: $filePath, repo: $repo})
      MATCH (e {name: $name, file_path: $filePath, repo: $repo})
      MERGE (f)-[:EXPORTS {type: $type}]->(e)
    `;
    
    await session.run(query, {
      filePath,
      repo,
      name: exp.name,
      type: exp.type
    });
  }

  /**
   * Query code structure from Neo4j
   */
  async findFunction(name: string, repo?: string): Promise<any[]> {
    const query = `
      MATCH (f:Function)
      ${repo ? 'WHERE f.repo = $repo' : ''}
      AND f.name CONTAINS $name
      RETURN f
      LIMIT 10
    `;
    
    const result = await neo4jClient.executeQuery(query, { name, repo });
    return result.map(r => r.f);
  }

  async findClass(name: string, repo?: string): Promise<any[]> {
    const query = `
      MATCH (c:Class)
      ${repo ? 'WHERE c.repo = $repo' : ''}
      AND c.name CONTAINS $name
      RETURN c
      LIMIT 10
    `;
    
    const result = await neo4jClient.executeQuery(query, { name, repo });
    return result.map(r => r.c);
  }

  async findUpstreamDependencies(functionName: string, maxHops: number = 5): Promise<string[]> {
    const query = `
      MATCH (start:Function {name: $functionName})
      MATCH path = (start)-[:CALLS*1..${maxHops}]->(callee)
      RETURN DISTINCT callee.name as entityName
      ORDER BY length(path)
    `;
    
    const result = await neo4jClient.executeQuery(query, { functionName });
    return result.map(r => r.entityName);
  }

  async findDownstreamImpact(functionName: string, maxHops: number = 5): Promise<string[]> {
    const query = `
      MATCH (start:Function {name: $functionName})
      MATCH path = (caller)-[:CALLS*1..${maxHops}]->(start)
      RETURN DISTINCT caller.name as entityName
      ORDER BY length(path)
    `;
    
    const result = await neo4jClient.executeQuery(query, { functionName });
    return result.map(r => r.entityName);
  }

  async getClassInheritance(className: string, repo?: string): Promise<string[]> {
    const query = `
      MATCH (start:Class {name: $className})
      ${repo ? 'WHERE start.repo = $repo' : ''}
      MATCH (start)-[:INHERITS_FROM*0..]->(parent)
      RETURN DISTINCT parent.name as className, parent.file_path as filePath
    `;
    
    const result = await neo4jClient.executeQuery(query, { className, repo });
    return result.map(r => r.className as string).filter(Boolean);
  }

  async getFileStructure(filePath: string, repo: string): Promise<any> {
    const query = `
      MATCH (f:File {file_path: $filePath, repo: $repo})
      OPTIONAL MATCH (f)-[:CONTAINS]->(entity)
      RETURN f as file, collect(entity) as entities
    `;
    
    const result = await neo4jClient.executeQuery(query, { filePath, repo });
    return result.length > 0 ? result[0] : null;
  }

  async getProjectStructure(repo: string): Promise<any> {
    const query = `
      MATCH (f:File {repo: $repo})
      OPTIONAL MATCH (f)-[:CONTAINS]->(entity)
      RETURN f.file_path as filePath, 
             f.name as fileName,
             collect({
               type: labels(entity)[0],
               name: entity.name,
               start_line: entity.start_line,
               end_line: entity.end_line
             }) as entities
      ORDER BY f.file_path
    `;
    
    const result = await neo4jClient.executeQuery(query, { repo });
    return result;
  }

  /**
   * Clean up graph data for a specific file or repo
   */
  async cleanupFile(filePath: string, repo: string): Promise<void> {
    const session = neo4jClient.getSession();
    
    try {
      // Delete all entities and relationships for this file
      const query = `
        MATCH (f:File {file_path: $filePath, repo: $repo})
        OPTIONAL MATCH (f)-[:CONTAINS]->(entity)
        DETACH DELETE entity
        DETACH DELETE f
      `;
      
      await session.run(query, { filePath, repo });
      logger.info(`Cleaned up graph data for ${filePath}`);
      
    } catch (error) {
      logger.error(`Error cleaning up graph data for ${filePath}:`, error);
    } finally {
      await session.close();
    }
  }

  /**
   * Get graph statistics
   */
  async getGraphStats(): Promise<any> {
    const queries = [
      'MATCH (n) RETURN labels(n)[0] as type, count(n) as count',
      'MATCH ()-[r]-() RETURN type(r) as rel_type, count(r) as count',
      'MATCH (f:File) RETURN count(f) as file_count',
      'MATCH (f:File) RETURN f.repo as repo, count(f) as file_count ORDER BY file_count DESC'
    ];

    const results: Record<string, any> = {};
    
    for (const query of queries) {
      try {
        const result = await neo4jClient.executeQuery(query);
        results[query.substring(0, 30)] = result;
      } catch (error) {
        logger.error('Error getting graph stats:', error);
      }
    }
    
    return results;
  }

  /**
   * Check if a codebase already exists in the graph
   */
  async codebaseExists(repo: string): Promise<boolean> {
    const session = neo4jClient.getSession();
    
    try {
      const result = await session.run(
        'MATCH (f:File {repo: $repo}) RETURN count(f) as count',
        { repo }
      );
      
      const count = result.records[0].get('count').toNumber();
      return count > 0;
      
    } catch (error) {
      logger.error(`Error checking if codebase ${repo} exists:`, error);
      return false;
    } finally {
      await session.close();
    }
  }

  /**
   * Clean up specific codebase data from Neo4j
   */
  async cleanupCodebase(repo: string): Promise<void> {
    const session = neo4jClient.getSession();
    
    try {
      logger.info(`Cleaning up Neo4j data for codebase: ${repo}`);
      
      // Delete all entities and relationships for this repo
      const query = `
        MATCH (f:File {repo: $repo})
        OPTIONAL MATCH (f)-[:CONTAINS]->(entity)
        DETACH DELETE entity
        DETACH DELETE f
      `;
      
      await session.run(query, { repo });
      logger.info(`Successfully cleaned up Neo4j data for codebase: ${repo}`);
      
    } catch (error) {
      logger.error(`Error cleaning up Neo4j data for codebase ${repo}:`, error);
    } finally {
      await session.close();
    }
  }
}
import { logger } from '../utils/logger.js';

export interface CodeEntity {
  type: 'function' | 'class' | 'method' | 'variable' | 'import' | 'export' | 'interface' | 'enum';
  name: string;
  filePath: string;
  startLine: number;
  endLine: number;
  signature?: string;
  body?: string;
  parameters?: string[];
  returnType?: string;
  modifiers?: string[];
  extends?: string[];
  implements?: string[];
  calls?: string[];
  references?: string[];
  imports?: string[];
  exports?: string[];
}

export interface ASTAnalysisResult {
  entities: CodeEntity[];
  relationships: any[];
  imports: Array<{ module: string; names: string[] }>;
  exports: Array<{ name: string; type: string }>;
}

export interface FileStructure {
  filePath: string;
  entities: CodeEntity[];
  imports: Array<{ module: string; names: string[] }>;
  exports: Array<{ name: string; type: string }>;
}

export class ASTParser {
  private supportedLanguages = [
    'javascript', 'typescript', 'python', 'go', 'java', 'c', 'cpp', 'rust'
  ];

  getSupportedLanguages(): string[] {
    return this.supportedLanguages;
  }

  parseFile(content: string, filePath: string, language: string): ASTAnalysisResult {
    try {
      const entities: CodeEntity[] = [];
      
      // Basic regex-based parsing for common patterns
      this.parseFunctions(content, filePath, entities, language);
      this.parseClasses(content, filePath, entities, language);
      this.parseVariables(content, filePath, entities, language);
      
      return {
        entities,
        relationships: [],
        imports: this.extractImports(content, language),
        exports: this.extractExports(content, language)
      };
    } catch (error) {
      logger.error('Error parsing AST:', error);
      return {
        entities: [],
        relationships: [],
        imports: [],
        exports: []
      };
    }
  }

  private parseFunctions(content: string, filePath: string, entities: CodeEntity[], language: string): void {
    const functionPatterns = this.getFunctionPatterns(language);
    
    for (const pattern of functionPatterns) {
      const matches = content.matchAll(pattern.regex);
      for (const match of matches) {
        entities.push({
          type: 'function',
          name: match[pattern.nameIndex] || 'anonymous',
          filePath,
          startLine: this.getLineNumber(content, match.index || 0),
          endLine: this.getLineNumber(content, match.index || 0) + 1,
          signature: match[0].substring(0, 100),
          parameters: this.extractParameters(match[0])
        });
      }
    }
  }

  private parseClasses(content: string, filePath: string, entities: CodeEntity[], language: string): void {
    const classPatterns = this.getClassPatterns(language);
    
    for (const pattern of classPatterns) {
      const matches = content.matchAll(pattern.regex);
      for (const match of matches) {
        entities.push({
          type: 'class',
          name: match[pattern.nameIndex] || 'anonymous',
          filePath,
          startLine: this.getLineNumber(content, match.index || 0),
          endLine: this.getLineNumber(content, match.index || 0) + 1,
          signature: match[0].substring(0, 100)
        });
      }
    }
  }

  private parseVariables(content: string, filePath: string, entities: CodeEntity[], language: string): void {
    const varPatterns = this.getVariablePatterns(language);
    
    for (const pattern of varPatterns) {
      const matches = content.matchAll(pattern.regex);
      for (const match of matches) {
        entities.push({
          type: 'variable',
          name: match[pattern.nameIndex] || 'unknown',
          filePath,
          startLine: this.getLineNumber(content, match.index || 0),
          endLine: this.getLineNumber(content, match.index || 0) + 1
        });
      }
    }
  }

  private getFunctionPatterns(language: string): Array<{ regex: RegExp; nameIndex: number }> {
    switch (language.toLowerCase()) {
      case 'javascript':
      case 'typescript':
        return [
          { regex: /function\s+(\w+)\s*\(/g, nameIndex: 1 },
          { regex: /(\w+)\s*=\s*function\s*\(/g, nameIndex: 1 },
          { regex: /(\w+)\s*:\s*function\s*\(/g, nameIndex: 1 },
          { regex: /(\w+)\s*\([^)]*\)\s*\{/g, nameIndex: 1 }
        ];
      case 'python':
        return [
          { regex: /def\s+(\w+)\s*\(/g, nameIndex: 1 },
          { regex: /(\w+)\s*=\s*lambda/g, nameIndex: 1 }
        ];
      case 'go':
        return [
          { regex: /func\s+(\w+)\s*\(/g, nameIndex: 1 }
        ];
      case 'java':
        return [
          { regex: /(?:public|private|protected)?\s*(?:static)?\s*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*\{/g, nameIndex: 1 }
        ];
      default:
        return [];
    }
  }

  private getClassPatterns(language: string): Array<{ regex: RegExp; nameIndex: number }> {
    switch (language.toLowerCase()) {
      case 'javascript':
      case 'typescript':
        return [
          { regex: /class\s+(\w+)/g, nameIndex: 1 }
        ];
      case 'python':
        return [
          { regex: /class\s+(\w+)/g, nameIndex: 1 }
        ];
      case 'java':
        return [
          { regex: /class\s+(\w+)/g, nameIndex: 1 },
          { regex: /interface\s+(\w+)/g, nameIndex: 1 }
        ];
      case 'go':
        return [
          { regex: /type\s+(\w+)\s+struct/g, nameIndex: 1 }
        ];
      default:
        return [];
    }
  }

  private getVariablePatterns(language: string): Array<{ regex: RegExp; nameIndex: number }> {
    switch (language.toLowerCase()) {
      case 'javascript':
      case 'typescript':
        return [
          { regex: /(?:const|let|var)\s+(\w+)\s*=/g, nameIndex: 1 }
        ];
      case 'python':
        return [
          { regex: /(\w+)\s*=/g, nameIndex: 1 }
        ];
      case 'go':
        return [
          { regex: /(\w+)\s*:=/g, nameIndex: 1 },
          { regex: /var\s+(\w+)/g, nameIndex: 1 }
        ];
      case 'java':
        return [
          { regex: /(?:public|private|protected)?\s*(?:static|final)?\s*(\w+)\s+(\w+)\s*=/g, nameIndex: 2 }
        ];
      default:
        return [];
    }
  }

  private extractImports(content: string, language: string): Array<{ module: string; names: string[] }> {
    const imports: Array<{ module: string; names: string[] }> = [];
    
    switch (language.toLowerCase()) {
      case 'javascript':
      case 'typescript':
        const jsImports = content.matchAll(/import\s+(?:\{([^}]+)\}|\*)?\s*(?:\w+\s+from\s+)?['"]([^'"]+)['"]/g);
        for (const match of jsImports) {
          const names = match[1] ? match[1].split(',').map(n => n.trim()) : [];
          imports.push({ module: match[2], names });
        }
        break;
      case 'python':
        const pyImports = content.matchAll(/import\s+(\w+)|from\s+(\w+)\s+import\s+([^\n]+)/g);
        for (const match of pyImports) {
          const module = match[1] || match[2];
          const names = match[3] ? match[3].split(',').map(n => n.trim()) : [];
          imports.push({ module, names });
        }
        break;
      case 'go':
        const goImports = content.matchAll(/import\s+['"]([^'"]+)['"]/g);
        for (const match of goImports) {
          imports.push({ module: match[1], names: [] });
        }
        break;
      case 'java':
        const javaImports = content.matchAll(/import\s+([\w.]+)/g);
        for (const match of javaImports) {
          imports.push({ module: match[1], names: [] });
        }
        break;
    }
    
    return imports;
  }

  private extractExports(content: string, language: string): Array<{ name: string; type: string }> {
    const exports: Array<{ name: string; type: string }> = [];
    
    switch (language.toLowerCase()) {
      case 'javascript':
      case 'typescript':
        const jsExports = content.matchAll(/export\s+(?:default\s+)?(?:function|class|const|let|var)?\s*(\w+)/g);
        for (const match of jsExports) {
          exports.push({ name: match[1], type: 'default' });
        }
        break;
      case 'python':
        const pyExports = content.matchAll(/__all__\s*=\s*\[([^\]]+)\]/g);
        for (const match of pyExports) {
          exports.push(...match[1].split(',').map((s: string) => ({ 
            name: s.trim().replace(/['"]/g, ''), 
            type: 'export' 
          })));
        }
        break;
      case 'go':
        const goExports = content.matchAll(/func\s+([A-Z]\w+)/g);
        for (const match of goExports) {
          exports.push({ name: match[1], type: 'function' });
        }
        break;
      case 'java':
        const javaExports = content.matchAll(/public\s+(?:class|interface|enum)\s+(\w+)/g);
        for (const match of javaExports) {
          exports.push({ name: match[1], type: 'public' });
        }
        break;
    }
    
    return exports;
  }

  private extractParameters(signature: string): string[] {
    const match = signature.match(/\(([^)]*)\)/);
    if (!match) return [];
    return match[1].split(',').map(p => p.trim()).filter(p => p.length > 0);
  }

  private getLineNumber(content: string, index: number): number {
    return content.substring(0, index).split('\n').length;
  }
}
/**
 * Local Codebase Scanner
 * 
 * Scans local directories and files to extract code and documentation content
 * for processing by the RAG system. Replaces the GitHub crawler functionality.
 */

import fs from 'fs/promises';
import path from 'path';
import { logger } from '../utils/logger.js';
import { ProjectInfo, ExtractedContent, ContentMetadata } from '../types/index.js';

export interface ScanOptions {
  maxFileSize?: number; // in bytes
  includeHidden?: boolean;
  maxDepth?: number;
  excludePatterns?: string[];
}

export class LocalCodebaseScanner {
  private readonly supportedExtensions = new Set([
    // Code files
    '.js', '.ts', '.jsx', '.tsx', '.py', '.go', '.rs', '.java', '.cpp', '.c', '.h', '.hpp',
    '.php', '.rb', '.swift', '.kt', '.scala', '.r', '.m', '.sh', '.sql', '.vue',
    '.html', '.css', '.scss', '.sass', '.less', '.xml', '.json', '.yaml', '.yml',
    
    // Documentation files
    '.md', '.rst', '.txt', '.adoc', '.wiki',
    
    // Configuration files
    '.toml', '.ini', '.cfg', '.conf', '.properties', '.env'
  ]);

  private readonly skipDirectories = new Set([
    '.git', '.github', '.vscode', '.idea', 'node_modules', 'dist', 'build',
    'target', '.next', '.nuxt', '__pycache__', '.pytest_cache', 'vendor',
    'packages', 'deps', '.deps', 'coverage', '.coverage', '.nyc_output',
    'logs', 'log', '.log', 'tmp', 'temp', 'cache', '.cache', '.DS_Store',
    'bin', 'obj', 'out', '.output', '.venv', 'venv', 'env', '.env_dir'
  ]);

  private readonly skipFiles = new Set([
    '.gitignore', '.gitkeep', '.dockerignore', 'Dockerfile', 'docker-compose.yml',
    'package-lock.json', 'yarn.lock', 'composer.lock', 'Gemfile.lock',
    'Cargo.lock', 'poetry.lock'
  ]);

  private readonly defaultOptions: Required<ScanOptions> = {
    maxFileSize: 5 * 1024 * 1024, // 5MB
    includeHidden: false,
    maxDepth: 10,
    excludePatterns: []
  };

  async scanProject(projectPath: string, projectName?: string, options?: ScanOptions): Promise<ExtractedContent[]> {
    const opts = { ...this.defaultOptions, ...options };
    const resolvedPath = path.resolve(projectPath);
    
    try {
      await fs.access(resolvedPath);
    } catch (error) {
      throw new Error(`Project path does not exist or is not accessible: ${resolvedPath}`);
    }

    const stats = await fs.stat(resolvedPath);
    if (!stats.isDirectory()) {
      throw new Error(`Project path is not a directory: ${resolvedPath}`);
    }

    const name = projectName || path.basename(resolvedPath);
    logger.info(`Scanning local project: ${name} at ${resolvedPath}`);

    // Analyze project structure
    const projectInfo = await this.analyzeProjectStructure(resolvedPath, name);
    logger.info(`Detected project type: ${projectInfo.type}, main language: ${projectInfo.mainLanguage}`);

    // Scan all files
    const allFiles = await this.scanDirectoryRecursive(resolvedPath, opts, 0);
    logger.info(`Found ${allFiles.length} files in project ${name}`);

    // Extract content from files
    const extractedContent: ExtractedContent[] = [];
    for (const filePath of allFiles) {
      try {
        const content = await this.extractFileContent(filePath, projectInfo, resolvedPath);
        if (content) {
          extractedContent.push(content);
        }
      } catch (error) {
        logger.debug(`Failed to extract content from ${filePath}: ${error}`);
      }
    }

    logger.info(`Successfully extracted ${extractedContent.length} content items from ${name}`);
    return extractedContent;
  }

  async scanMultipleProjects(projectPaths: string[], options?: ScanOptions): Promise<ExtractedContent[]> {
    const allContent: ExtractedContent[] = [];

    for (const projectPath of projectPaths) {
      try {
        const projectContent = await this.scanProject(projectPath, undefined, options);
        allContent.push(...projectContent);
      } catch (error) {
        logger.error(`Failed to scan project ${projectPath}: ${error}`);
      }
    }

    return allContent;
  }

  private async analyzeProjectStructure(projectPath: string, projectName: string): Promise<ProjectInfo> {
    let projectType = 'unknown';
    let mainLanguage = 'unknown';
    const languages = new Set<string>();

    // Detect project type by configuration files
    const configFiles = {
      'package.json': 'nodejs',
      'tsconfig.json': 'typescript',
      'requirements.txt': 'python',
      'setup.py': 'python',
      'pyproject.toml': 'python',
      'Cargo.toml': 'rust',
      'go.mod': 'go',
      'pom.xml': 'java',
      'build.gradle': 'java',
      'composer.json': 'php',
      'Gemfile': 'ruby'
    };

    for (const [configFile, detectedType] of Object.entries(configFiles)) {
      try {
        await fs.access(path.join(projectPath, configFile));
        projectType = detectedType;
        break;
      } catch {
        // File doesn't exist, continue
      }
    }

    // Count file extensions to determine main language
    const extensionCounts = new Map<string, number>();
    
    try {
      const files = await this.getAllFiles(projectPath);
      for (const filePath of files) {
        const ext = path.extname(filePath).toLowerCase();
        if (this.supportedExtensions.has(ext)) {
          extensionCounts.set(ext, (extensionCounts.get(ext) || 0) + 1);
          
          const lang = this.extensionToLanguage(ext);
          if (lang) {
            languages.add(lang);
          }
        }
      }
    } catch (error) {
      logger.debug(`Error counting extensions: ${error}`);
    }

    // Determine main language by most common extension
    if (extensionCounts.size > 0) {
      const mostCommonExt = Array.from(extensionCounts.entries())
        .sort((a, b) => b[1] - a[1])[0][0];
      mainLanguage = this.extensionToLanguage(mostCommonExt) || 'unknown';
    }

    return {
      name: projectName,
      path: projectPath,
      type: projectType,
      mainLanguage,
      languages: Array.from(languages),
      fileCount: extensionCounts.size,
      totalSize: await this.getDirectorySize(projectPath)
    };
  }

  private async getAllFiles(dirPath: string): Promise<string[]> {
    const files: string[] = [];
    
    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);
        
        if (entry.isFile()) {
          files.push(fullPath);
        } else if (entry.isDirectory() && !this.shouldSkipDirectory(entry.name)) {
          const subFiles = await this.getAllFiles(fullPath);
          files.push(...subFiles);
        }
      }
    } catch (error) {
      logger.debug(`Error reading directory ${dirPath}: ${error}`);
    }
    
    return files;
  }

  private async scanDirectoryRecursive(
    dirPath: string, 
    options: Required<ScanOptions>, 
    currentDepth: number
  ): Promise<string[]> {
    if (currentDepth >= options.maxDepth) {
      return [];
    }

    const files: string[] = [];

    try {
      const entries = await fs.readdir(dirPath, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);

        if (entry.isFile()) {
          if (this.shouldIncludeFile(fullPath, options)) {
            try {
              const stats = await fs.stat(fullPath);
              if (stats.size <= options.maxFileSize) {
                files.push(fullPath);
              } else {
                logger.debug(`Skipping large file: ${fullPath} (${stats.size} bytes)`);
              }
            } catch (error) {
              logger.debug(`Error checking file ${fullPath}: ${error}`);
            }
          }
        } else if (entry.isDirectory()) {
          if (!this.shouldSkipDirectory(entry.name)) {
            const subFiles = await this.scanDirectoryRecursive(fullPath, options, currentDepth + 1);
            files.push(...subFiles);
          }
        }
      }
    } catch (error) {
      logger.warn(`Permission denied or error accessing ${dirPath}: ${error}`);
    }

    return files;
  }

  private async extractFileContent(
    filePath: string, 
    projectInfo: ProjectInfo, 
    projectRoot: string
  ): Promise<ExtractedContent | null> {
    try {
      // Check if file is binary
      if (await this.isBinaryFile(filePath)) {
        return null;
      }

      // Read file content
      const content = await fs.readFile(filePath, 'utf-8');
      if (!content || !content.trim()) {
        return null;
      }

      // Determine file type and language
      const language = this.detectFileLanguage(filePath);
      const contentType = this.determineContentType(filePath);

      // Create relative path from project root
      const relativePath = path.relative(projectRoot, filePath);

      // Get file stats
      const stats = await fs.stat(filePath);

      // Create metadata
      const metadata: ContentMetadata = {
        repo: projectInfo.name,
        path: relativePath,
        language: language || 'unknown',
        fileSize: stats.size,
        lastModified: stats.mtime.toISOString(),
        contentType,
        projectType: projectInfo.type,
        mainLanguage: projectInfo.mainLanguage
      };

      return {
        repo: projectInfo.name,
        path: relativePath,
        type: contentType,
        language: language || 'unknown',
        content,
        metadata,
        isBinary: false
      };

    } catch (error) {
      logger.debug(`Error extracting content from ${filePath}: ${error}`);
      return null;
    }
  }

  private shouldIncludeFile(filePath: string, options: Required<ScanOptions>): boolean {
    const fileName = path.basename(filePath);
    const ext = path.extname(filePath).toLowerCase();

    // Skip hidden files unless explicitly included
    if (!options.includeHidden && fileName.startsWith('.') && !fileName.match(/^\.(env|gitignore)$/)) {
      return false;
    }

    // Skip specific files
    if (this.skipFiles.has(fileName)) {
      return false;
    }

    // Check file extension
    if (!this.supportedExtensions.has(ext)) {
      return false;
    }

    // Check exclude patterns
    for (const pattern of options.excludePatterns) {
      if (filePath.includes(pattern)) {
        return false;
      }
    }

    return true;
  }

  private shouldSkipDirectory(dirName: string): boolean {
    return this.skipDirectories.has(dirName) || dirName.startsWith('.');
  }

  private async isBinaryFile(filePath: string): Promise<boolean> {
    try {
      // Read first 8192 bytes
      const buffer = Buffer.alloc(8192);
      const fd = await fs.open(filePath, 'r');
      const { bytesRead } = await fd.read(buffer, 0, 8192, 0);
      await fd.close();

      // Check for null bytes (common in binary files)
      for (let i = 0; i < bytesRead; i++) {
        if (buffer[i] === 0) {
          return true;
        }
      }

      return false;
    } catch (error) {
      logger.debug(`Error checking if file is binary ${filePath}: ${error}`);
      return true; // Assume binary if we can't read it
    }
  }

  private detectFileLanguage(filePath: string): string | undefined {
    return this.extensionToLanguage(path.extname(filePath).toLowerCase());
  }

  private extensionToLanguage(extension: string): string | undefined {
    const extToLang: Record<string, string> = {
      '.js': 'JavaScript',
      '.ts': 'TypeScript',
      '.jsx': 'JavaScript',
      '.tsx': 'TypeScript',
      '.py': 'Python',
      '.go': 'Go',
      '.rs': 'Rust',
      '.java': 'Java',
      '.cpp': 'C++',
      '.c': 'C',
      '.h': 'C',
      '.hpp': 'C++',
      '.php': 'PHP',
      '.rb': 'Ruby',
      '.swift': 'Swift',
      '.kt': 'Kotlin',
      '.scala': 'Scala',
      '.r': 'R',
      '.m': 'Objective-C',
      '.sh': 'Shell',
      '.sql': 'SQL',
      '.html': 'HTML',
      '.css': 'CSS',
      '.scss': 'SCSS',
      '.sass': 'Sass',
      '.less': 'Less',
      '.vue': 'Vue',
      '.xml': 'XML',
      '.json': 'JSON',
      '.yaml': 'YAML',
      '.yml': 'YAML',
      '.toml': 'TOML',
      '.md': 'Markdown',
      '.rst': 'reStructuredText',
      '.txt': 'Text',
      '.adoc': 'AsciiDoc'
    };

    return extToLang[extension];
  }

  private determineContentType(filePath: string): 'readme' | 'doc' | 'wiki' | 'issue' | 'code' | 'function' | 'class' | 'config' | 'other' {
    const fileName = path.basename(filePath).toLowerCase();

    if (fileName.includes('readme')) {
      return 'readme';
    } else if (fileName.endsWith('.md') || fileName.endsWith('.rst')) {
      return 'doc';
    } else if (filePath.toLowerCase().includes('doc') || filePath.toLowerCase().includes('wiki')) {
      return 'doc';
    } else if (this.isCodeFile(filePath)) {
      return 'code';
    } else if (this.isConfigFile(filePath)) {
      return 'config';
    } else {
      return 'other';
    }
  }

  private isCodeFile(filePath: string): boolean {
    const codeExtensions = new Set([
      '.js', '.ts', '.jsx', '.tsx', '.py', '.go', '.rs', '.java', '.cpp', '.c', '.h', '.hpp',
      '.php', '.rb', '.swift', '.kt', '.scala', '.r', '.m', '.sh', '.sql', '.vue', '.html', '.css'
    ]);
    
    return codeExtensions.has(path.extname(filePath).toLowerCase());
  }

  private isConfigFile(filePath: string): boolean {
    const configExtensions = new Set(['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf']);
    return configExtensions.has(path.extname(filePath).toLowerCase());
  }

  private async getDirectorySize(dirPath: string): Promise<number> {
    let totalSize = 0;
    
    try {
      const files = await this.getAllFiles(dirPath);
      for (const filePath of files) {
        try {
          const stats = await fs.stat(filePath);
          totalSize += stats.size;
        } catch (error) {
          // Skip files we can't stat
        }
      }
    } catch (error) {
      logger.debug(`Error calculating directory size for ${dirPath}: ${error}`);
    }

    return totalSize;
  }
} 
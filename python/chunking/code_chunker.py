"""
Code chunker for function-level code analysis.
"""

import re
import ast
import json
from typing import List, Optional, Dict, Any, NamedTuple
from pathlib import Path
from loguru import logger


class CodeUnit(NamedTuple):
    """Represents a unit of code (function, class, etc.)."""
    content: str
    start_line: int
    end_line: int
    unit_type: str  # 'function', 'class', 'method', 'module'
    name: str
    language: str


class CodeChunker:
    """Code chunker that extracts functions and classes."""
    
    def __init__(self):
        """Initialize code chunker."""
        self.language_parsers = {
            '.py': self._parse_python,
            '.js': self._parse_javascript,
            '.ts': self._parse_typescript,
            '.jsx': self._parse_javascript,
            '.tsx': self._parse_typescript,
            '.java': self._parse_java,
            '.cpp': self._parse_cpp,
            '.c': self._parse_c,
            '.h': self._parse_c,
            '.hpp': self._parse_cpp,
            '.cs': self._parse_csharp,
            '.php': self._parse_php,
            '.rb': self._parse_ruby,
            '.go': self._parse_go,
            '.rs': self._parse_rust,
            '.swift': self._parse_swift
        }
    
    async def extract_code_units(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """
        Extract code units from source code.
        
        Args:
            code_content: Source code content
            file_path: Path to the source file
            
        Returns:
            List of code units
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension not in self.language_parsers:
            logger.debug(f"No parser available for {extension}, using fallback")
            return await self._parse_generic(code_content, extension)
        
        try:
            parser = self.language_parsers[extension]
            return await parser(code_content, file_path)
        except Exception as e:
            logger.warning(f"Error parsing {file_path}: {e}, using fallback")
            return await self._parse_generic(code_content, extension)
    
    async def _parse_python(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse Python code using AST."""
        units = []
        
        try:
            tree = ast.parse(code_content)
            lines = code_content.split('\n')
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    unit = self._extract_python_function(node, lines)
                    if unit:
                        units.append(unit)
                elif isinstance(node, ast.ClassDef):
                    unit = self._extract_python_class(node, lines)
                    if unit:
                        units.append(unit)
            
        except SyntaxError as e:
            logger.warning(f"Python syntax error in {file_path}: {e}")
            return []
        
        return units
    
    def _extract_python_function(self, node: ast.FunctionDef, lines: List[str]) -> Optional[CodeUnit]:
        """Extract Python function."""
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', start_line)
        
        if end_line is None:
            # Estimate end line for older Python versions
            end_line = start_line + 10  # Default estimate
            
        content = '\n'.join(lines[start_line-1:end_line])
        
        return CodeUnit(
            content=content,
            start_line=start_line,
            end_line=end_line,
            unit_type='function',
            name=node.name,
            language='python'
        )
    
    def _extract_python_class(self, node: ast.ClassDef, lines: List[str]) -> Optional[CodeUnit]:
        """Extract Python class."""
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', start_line)
        
        if end_line is None:
            # Estimate end line for older Python versions
            for i in range(start_line, min(len(lines), start_line + 100)):
                if i < len(lines) and lines[i].strip() and not lines[i].startswith((' ', '\t')):
                    if i > start_line:
                        end_line = i
                        break
            else:
                end_line = min(len(lines), start_line + 50)
                
        content = '\n'.join(lines[start_line-1:end_line])
        
        return CodeUnit(
            content=content,
            start_line=start_line,
            end_line=end_line,
            unit_type='class',
            name=node.name,
            language='python'
        )
    
    async def _parse_javascript(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse JavaScript/JSX code using regex patterns."""
        units = []
        lines = code_content.split('\n')
        
        # Function patterns
        function_patterns = [
            r'^\s*function\s+(\w+)\s*\(',  # function name()
            r'^\s*const\s+(\w+)\s*=\s*function',  # const name = function
            r'^\s*const\s+(\w+)\s*=\s*\(',  # const name = ()
            r'^\s*(\w+)\s*:\s*function',  # name: function
            r'^\s*async\s+function\s+(\w+)',  # async function
        ]
        
        # Class patterns
        class_patterns = [
            r'^\s*class\s+(\w+)',  # class Name
            r'^\s*export\s+class\s+(\w+)',  # export class Name
        ]
        
        for i, line in enumerate(lines):
            # Check for functions
            for pattern in function_patterns:
                match = re.search(pattern, line)
                if match:
                    name = match.group(1)
                    start_line = i + 1
                    end_line = self._find_javascript_block_end(lines, i)
                    
                    content = '\n'.join(lines[i:end_line])
                    
                    units.append(CodeUnit(
                        content=content,
                        start_line=start_line,
                        end_line=end_line,
                        unit_type='function',
                        name=name,
                        language='javascript'
                    ))
                    break
            
            # Check for classes
            for pattern in class_patterns:
                match = re.search(pattern, line)
                if match:
                    name = match.group(1)
                    start_line = i + 1
                    end_line = self._find_javascript_block_end(lines, i)
                    
                    content = '\n'.join(lines[i:end_line])
                    
                    units.append(CodeUnit(
                        content=content,
                        start_line=start_line,
                        end_line=end_line,
                        unit_type='class',
                        name=name,
                        language='javascript'
                    ))
                    break
        
        return units
    
    async def _parse_typescript(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse TypeScript code."""
        # Similar to JavaScript but with additional patterns
        units = await self._parse_javascript(code_content, file_path)
        
        # Update language
        for unit in units:
            unit = unit._replace(language='typescript')
        
        return units
    
    async def _parse_java(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse Java code using regex patterns."""
        units = []
        lines = code_content.split('\n')
        
        # Java method pattern
        method_pattern = r'^\s*(public|private|protected|static|\s)*\s*\w+\s+(\w+)\s*\('
        
        # Java class pattern  
        class_pattern = r'^\s*(public|private|protected)?\s*class\s+(\w+)'
        
        for i, line in enumerate(lines):
            # Check for methods
            match = re.search(method_pattern, line)
            if match and not re.search(r'^\s*//', line):  # Not a comment
                name = match.group(2)
                start_line = i + 1
                end_line = self._find_java_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='method',
                    name=name,
                    language='java'
                ))
            
            # Check for classes
            match = re.search(class_pattern, line)
            if match:
                name = match.group(2)
                start_line = i + 1
                end_line = self._find_java_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='class',
                    name=name,
                    language='java'
                ))
        
        return units
    
    async def _parse_cpp(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse C++ code."""
        units = []
        lines = code_content.split('\n')
        
        # C++ function pattern
        function_pattern = r'^\s*\w+\s+(\w+)\s*\([^)]*\)\s*{'
        
        # C++ class pattern
        class_pattern = r'^\s*class\s+(\w+)'
        
        for i, line in enumerate(lines):
            # Check for functions
            match = re.search(function_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_c_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='function',
                    name=name,
                    language='cpp'
                ))
            
            # Check for classes
            match = re.search(class_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_c_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='class',
                    name=name,
                    language='cpp'
                ))
        
        return units
    
    async def _parse_c(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse C code."""
        units = []
        lines = code_content.split('\n')
        
        # C function pattern
        function_pattern = r'^\w+\s+(\w+)\s*\([^)]*\)\s*{'
        
        for i, line in enumerate(lines):
            match = re.search(function_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_c_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='function',
                    name=name,
                    language='c'
                ))
        
        return units
    
    async def _parse_csharp(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse C# code."""
        # Similar to Java
        units = await self._parse_java(code_content, file_path)
        
        # Update language
        for unit in units:
            unit = unit._replace(language='csharp')
        
        return units
    
    async def _parse_php(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse PHP code."""
        units = []
        lines = code_content.split('\n')
        
        # PHP function pattern
        function_pattern = r'^\s*function\s+(\w+)\s*\('
        
        # PHP class pattern
        class_pattern = r'^\s*class\s+(\w+)'
        
        for i, line in enumerate(lines):
            # Check for functions
            match = re.search(function_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_php_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='function',
                    name=name,
                    language='php'
                ))
            
            # Check for classes
            match = re.search(class_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_php_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='class',
                    name=name,
                    language='php'
                ))
        
        return units
    
    async def _parse_ruby(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse Ruby code."""
        units = []
        lines = code_content.split('\n')
        
        # Ruby method pattern
        method_pattern = r'^\s*def\s+(\w+)'
        
        # Ruby class pattern
        class_pattern = r'^\s*class\s+(\w+)'
        
        for i, line in enumerate(lines):
            # Check for methods
            match = re.search(method_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_ruby_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='method',
                    name=name,
                    language='ruby'
                ))
            
            # Check for classes
            match = re.search(class_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_ruby_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='class',
                    name=name,
                    language='ruby'
                ))
        
        return units
    
    async def _parse_go(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse Go code."""
        units = []
        lines = code_content.split('\n')
        
        # Go function pattern
        function_pattern = r'^\s*func\s+(\w+)\s*\('
        
        # Go struct pattern
        struct_pattern = r'^\s*type\s+(\w+)\s+struct'
        
        for i, line in enumerate(lines):
            # Check for functions
            match = re.search(function_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_go_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='function',
                    name=name,
                    language='go'
                ))
            
            # Check for structs
            match = re.search(struct_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_go_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='struct',
                    name=name,
                    language='go'
                ))
        
        return units
    
    async def _parse_rust(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse Rust code."""
        units = []
        lines = code_content.split('\n')
        
        # Rust function pattern
        function_pattern = r'^\s*fn\s+(\w+)\s*\('
        
        # Rust struct pattern
        struct_pattern = r'^\s*struct\s+(\w+)'
        
        for i, line in enumerate(lines):
            # Check for functions
            match = re.search(function_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_rust_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='function',
                    name=name,
                    language='rust'
                ))
            
            # Check for structs
            match = re.search(struct_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_rust_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='struct',
                    name=name,
                    language='rust'
                ))
        
        return units
    
    async def _parse_swift(self, code_content: str, file_path: str) -> List[CodeUnit]:
        """Parse Swift code."""
        units = []
        lines = code_content.split('\n')
        
        # Swift function pattern
        function_pattern = r'^\s*func\s+(\w+)\s*\('
        
        # Swift class pattern
        class_pattern = r'^\s*class\s+(\w+)'
        
        for i, line in enumerate(lines):
            # Check for functions
            match = re.search(function_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_swift_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='function',
                    name=name,
                    language='swift'
                ))
            
            # Check for classes
            match = re.search(class_pattern, line)
            if match:
                name = match.group(1)
                start_line = i + 1
                end_line = self._find_swift_block_end(lines, i)
                
                content = '\n'.join(lines[i:end_line])
                
                units.append(CodeUnit(
                    content=content,
                    start_line=start_line,
                    end_line=end_line,
                    unit_type='class',
                    name=name,
                    language='swift'
                ))
        
        return units
    
    async def _parse_generic(self, code_content: str, extension: str) -> List[CodeUnit]:
        """Generic fallback parser."""
        units = []
        lines = code_content.split('\n')
        language = extension.lstrip('.')
        
        # Generic function patterns
        generic_patterns = [
            r'^\s*def\s+(\w+)',  # def name
            r'^\s*function\s+(\w+)',  # function name
            r'^\s*(\w+)\s*:\s*function',  # name: function
        ]
        
        for i, line in enumerate(lines):
            for pattern in generic_patterns:
                match = re.search(pattern, line)
                if match:
                    name = match.group(1)
                    start_line = i + 1
                    end_line = min(len(lines), i + 20)  # Default chunk size
                    
                    content = '\n'.join(lines[i:end_line])
                    
                    units.append(CodeUnit(
                        content=content,
                        start_line=start_line,
                        end_line=end_line,
                        unit_type='function',
                        name=name,
                        language=language
                    ))
                    break
        
        return units
    
    def _find_javascript_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find end of JavaScript block using brace matching."""
        brace_count = 0
        for i in range(start_idx, len(lines)):
            line = lines[i]
            brace_count += line.count('{') - line.count('}')
            
            if brace_count == 0 and '{' in lines[start_idx]:
                return i + 1
            elif i - start_idx > 100:  # Safety limit
                break
        
        return min(len(lines), start_idx + 50)
    
    def _find_java_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find end of Java block."""
        return self._find_javascript_block_end(lines, start_idx)
    
    def _find_c_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find end of C/C++ block."""
        return self._find_javascript_block_end(lines, start_idx)
    
    def _find_php_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find end of PHP block."""
        return self._find_javascript_block_end(lines, start_idx)
    
    def _find_ruby_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find end of Ruby block using end keyword."""
        for i in range(start_idx + 1, len(lines)):
            line = lines[i].strip()
            if line == 'end' or i - start_idx > 100:
                return i + 1
        
        return min(len(lines), start_idx + 50)
    
    def _find_go_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find end of Go block."""
        return self._find_javascript_block_end(lines, start_idx)
    
    def _find_rust_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find end of Rust block."""
        return self._find_javascript_block_end(lines, start_idx)
    
    def _find_swift_block_end(self, lines: List[str], start_idx: int) -> int:
        """Find end of Swift block."""
        return self._find_javascript_block_end(lines, start_idx) 
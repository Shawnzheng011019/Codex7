import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.processor.content_processor import ContentProcessor, ASTParser
from src.types import CodeFile, FileType


class TestASTParser:
    """Test AST parser functionality."""
    
    def test_ast_parser_initialization(self):
        """Test AST parser initialization."""
        parser = ASTParser()
        
        # Check that parsers were initialized
        assert hasattr(parser, 'parsers')
        assert isinstance(parser.parsers, dict)
        
        # Should have Python parser at minimum
        if parser.parsers:
            print(f"Available parsers: {list(parser.parsers.keys())}")
        
    def test_parse_python_code(self):
        """Test parsing Python code."""
        parser = ASTParser()
        
        # Skip if Python parser not available
        if 'python' not in parser.parsers:
            pytest.skip("Python parser not available")
            
        python_code = """
def hello_world():
    print("Hello, World!")
    return True

class TestClass:
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        return f"Hello, {self.name}!"

def main():
    test = TestClass("Test")
    print(test.greet())
    hello_world()
"""
        
        nodes = parser.parse_code(python_code, 'python')
        
        # Should find function and class definitions
        assert len(nodes) > 0
        
        function_nodes = [n for n in nodes if n['type'] == 'function_definition']
        class_nodes = [n for n in nodes if n['type'] == 'class_definition']
        
        assert len(function_nodes) >= 2  # hello_world, main, and possibly greet
        assert len(class_nodes) >= 1  # TestClass
        
        # Check node structure
        for node in nodes:
            assert 'type' in node
            assert 'start_line' in node
            assert 'end_line' in node
            assert 'content' in node
            assert node['start_line'] <= node['end_line']
            
    def test_parse_unsupported_language(self):
        """Test parsing unsupported language."""
        parser = ASTParser()
        
        code = "int main() { return 0; }"
        nodes = parser.parse_code(code, 'unsupported_language')
        
        # Should return empty list for unsupported languages
        assert nodes == []
        
    def test_parse_invalid_syntax(self):
        """Test parsing code with invalid syntax."""
        parser = ASTParser()
        
        # Skip if Python parser not available
        if 'python' not in parser.parsers:
            pytest.skip("Python parser not available")
            
        invalid_code = """
def invalid_function(
    # Missing closing parenthesis and colon
    print("This won't parse")
"""
        
        # Should handle errors gracefully
        nodes = parser.parse_code(invalid_code, 'python')
        assert isinstance(nodes, list)  # Should return empty list, not crash


class TestContentProcessor:
    """Test content processor functionality."""
    
    def test_processor_initialization(self):
        """Test content processor initialization."""
        processor = ContentProcessor()
        
        assert hasattr(processor, 'ast_parser')
        assert hasattr(processor, 'text_splitter')
        assert isinstance(processor.ast_parser, ASTParser)
        
    def test_process_file_with_ast(self, content_processor: ContentProcessor, sample_code_file):
        """Test processing file with AST parser."""
        # Skip if no AST parsers available
        if not content_processor.ast_parser.parsers:
            pytest.skip("No AST parsers available")
            
        # Skip if Python parser specifically not available
        if 'python' not in content_processor.ast_parser.parsers:
            pytest.skip("Python AST parser not available")
            
        chunks = content_processor.process_file(sample_code_file)
        
        # Should return chunks (may be empty if no AST nodes found)
        assert isinstance(chunks, list)
        
        if chunks:
            # Verify chunk structure
            for chunk in chunks:
                assert hasattr(chunk, 'id')
                assert hasattr(chunk, 'file_path')
                assert hasattr(chunk, 'content')
                assert hasattr(chunk, 'start_line')
                assert hasattr(chunk, 'end_line')
                assert hasattr(chunk, 'language')
                assert hasattr(chunk, 'chunk_type')
                assert hasattr(chunk, 'metadata')
                
                # Verify metadata structure
                assert 'file_size' in chunk.metadata
                assert 'file_type' in chunk.metadata
                assert 'ast_node_type' in chunk.metadata
                
                # Verify line numbers are reasonable
                assert chunk.start_line > 0
                assert chunk.end_line >= chunk.start_line
                
                # Verify content is not empty
                assert len(chunk.content.strip()) > 0
                
    def test_process_file_unsupported_language(self, content_processor: ContentProcessor):
        """Test processing file with unsupported language."""
        unsupported_file = CodeFile(
            path="test.unknown",
            absolute_path="/tmp/test.unknown",
            file_type=FileType.CODE,
            language="unknown_language",
            size=100,
            last_modified=0.0,
            content="some content here"
        )
        
        chunks = content_processor.process_file(unsupported_file)
        
        # Should return empty list (file skipped)
        assert chunks == []
        
    def test_process_file_no_language(self, content_processor: ContentProcessor):
        """Test processing file with no language detected."""
        no_lang_file = CodeFile(
            path="test.unknown",
            absolute_path="/tmp/test.unknown",
            file_type=FileType.CODE,
            language=None,
            size=100,
            last_modified=0.0,
            content="some content here"
        )
        
        chunks = content_processor.process_file(no_lang_file)
        
        # Should return empty list (file skipped)
        assert chunks == []
        
    def test_process_file_empty_content(self, content_processor: ContentProcessor):
        """Test processing file with empty content."""
        empty_file = CodeFile(
            path="empty.py",
            absolute_path="/tmp/empty.py",
            file_type=FileType.CODE,
            language="python",
            size=0,
            last_modified=0.0,
            content=""
        )
        
        chunks = content_processor.process_file(empty_file)
        
        # Should return empty list
        assert chunks == []
        
    def test_process_file_no_ast_nodes(self, content_processor: ContentProcessor):
        """Test processing file that produces no AST nodes."""
        # Skip if Python parser not available
        if 'python' not in content_processor.ast_parser.parsers:
            pytest.skip("Python AST parser not available")
            
        comment_only_file = CodeFile(
            path="comments.py",
            absolute_path="/tmp/comments.py",
            file_type=FileType.CODE,
            language="python",
            size=50,
            last_modified=0.0,
            content="# Just a comment\n# Another comment\n"
        )
        
        chunks = content_processor.process_file(comment_only_file)
        
        # Should return empty list (no AST nodes found)
        assert chunks == []
        
    def test_process_multiple_files(self, content_processor: ContentProcessor):
        """Test processing multiple files."""
        files = []
        
        # Only create files for available parsers
        if 'python' in content_processor.ast_parser.parsers:
            files.append(CodeFile(
                path="test1.py",
                absolute_path="/tmp/test1.py",
                file_type=FileType.CODE,
                language="python",
                size=100,
                last_modified=0.0,
                content="def test1():\n    pass\n"
            ))
            
        if 'javascript' in content_processor.ast_parser.parsers:
            files.append(CodeFile(
                path="test2.js",
                absolute_path="/tmp/test2.js",
                file_type=FileType.CODE,
                language="javascript",
                size=100,
                last_modified=0.0,
                content="function test2() {\n    return true;\n}\n"
            ))
        
        # Add unsupported file (should be skipped)
        files.append(CodeFile(
            path="test3.unknown",
            absolute_path="/tmp/test3.unknown",
            file_type=FileType.CODE,
            language="unknown",
            size=100,
            last_modified=0.0,
            content="unknown content"
        ))
        
        if not files:
            pytest.skip("No supported languages available")
            
        all_chunks = content_processor.process_files(files)
        
        # Should return list of chunks from supported files only
        assert isinstance(all_chunks, list)
        
        # Verify that unsupported files were skipped
        file_paths_in_chunks = {chunk.file_path for chunk in all_chunks}
        assert "test3.unknown" not in file_paths_in_chunks
        
    def test_chunk_id_generation(self, content_processor: ContentProcessor):
        """Test chunk ID generation."""
        # Test that IDs are unique and consistent
        id1 = content_processor._generate_chunk_id("test.py", 1, 10)
        id2 = content_processor._generate_chunk_id("test.py", 1, 10)
        id3 = content_processor._generate_chunk_id("test.py", 2, 10)
        
        # Same parameters should generate same ID
        assert id1 == id2
        
        # Different parameters should generate different ID
        assert id1 != id3
        
        # IDs should be valid strings
        assert isinstance(id1, str)
        assert len(id1) > 0
        
    def test_ast_error_handling(self, content_processor: ContentProcessor):
        """Test AST parser error handling."""
        # Skip if Python parser not available
        if 'python' not in content_processor.ast_parser.parsers:
            pytest.skip("Python AST parser not available")
            
        # File with syntax errors that might break AST parsing
        problematic_file = CodeFile(
            path="problematic.py",
            absolute_path="/tmp/problematic.py",
            file_type=FileType.CODE,
            language="python",
            size=100,
            last_modified=0.0,
            content="def broken(\n    # incomplete function definition"
        )
        
        # Should handle errors gracefully and return empty list
        chunks = content_processor.process_file(problematic_file)
        assert chunks == []
        
    def test_force_ast_usage_setting(self, content_processor: ContentProcessor):
        """Test that processor enforces AST-only usage."""
        # This test verifies the behavioral change where text splitter fallback is removed
        
        # Create a file for a language that might not have AST support
        unsupported_file = CodeFile(
            path="test.xyz",
            absolute_path="/tmp/test.xyz",
            file_type=FileType.CODE,
            language="xyz_language",
            size=100,
            last_modified=0.0,
            content="function test() { return 42; }"
        )
        
        chunks = content_processor.process_file(unsupported_file)
        
        # Should return empty list instead of falling back to text splitter
        assert chunks == []
        
        # Verify that process_file method doesn't call text splitter methods
        assert not hasattr(content_processor, '_process_with_text_splitter') or \
               '_process_with_text_splitter' not in str(content_processor.process_file.__code__.co_names) 
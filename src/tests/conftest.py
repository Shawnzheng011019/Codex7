import pytest
import os
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any
import time
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.graph.neo4j_client import Neo4jClient
from src.query.milvus_client import MilvusClient
from src.processor.content_processor import ContentProcessor
from src.scanner.local_codebase_scanner import LocalCodebaseScanner
from src.types import CodeFile, FileType


@pytest.fixture(scope="session")
def test_settings():
    """Override settings for testing."""
    original_settings = {}
    
    # Store original values
    original_settings['neo4j_uri'] = settings.neo4j_uri
    original_settings['neo4j_username'] = settings.neo4j_username
    original_settings['neo4j_password'] = settings.neo4j_password
    original_settings['milvus_host'] = settings.milvus_host
    original_settings['milvus_port'] = settings.milvus_port
    
    # Use standard environment variables
    settings.neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    settings.neo4j_username = os.getenv('NEO4J_USERNAME', 'neo4j')
    settings.neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
    settings.milvus_host = os.getenv('MILVUS_HOST', 'localhost')
    settings.milvus_port = int(os.getenv('MILVUS_PORT', '19530'))
    
    yield settings
    
    # Restore original values
    for key, value in original_settings.items():
        setattr(settings, key, value)


@pytest.fixture
def neo4j_client(test_settings) -> Generator[Neo4jClient, None, None]:
    """Create Neo4j client for testing."""
    client = Neo4jClient()
    
    yield client
    
    # Cleanup: Clear test data
    try:
        client.clear_database()
        client.close()
    except Exception as e:
        print(f"Error cleaning up Neo4j: {e}")


@pytest.fixture
def milvus_client(test_settings) -> Generator[MilvusClient, None, None]:
    """Create Milvus client for testing."""
    client = MilvusClient()
    
    yield client
    
    # Cleanup: Drop test collections
    try:
        client.drop_collection()
        client.close()
    except Exception as e:
        print(f"Error cleaning up Milvus: {e}")


@pytest.fixture
def content_processor() -> ContentProcessor:
    """Create content processor for testing."""
    return ContentProcessor()


@pytest.fixture
def temp_codebase() -> Generator[Path, None, None]:
    """Create temporary codebase for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test Python file
        python_file = temp_path / "test_file.py"
        python_file.write_text("""
def hello_world():
    '''A simple hello world function.'''
    print("Hello, World!")
    return "Hello"

class TestClass:
    '''A test class.'''
    
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        return f"Hello, {self.name}!"
    
    def calculate(self, x, y):
        '''Calculate sum of two numbers.'''
        return x + y

def main():
    test = TestClass("Test")
    print(test.greet())
    hello_world()

if __name__ == "__main__":
    main()
""")
        
        # Create test JavaScript file
        js_file = temp_path / "test_file.js"
        js_file.write_text("""
function helloWorld() {
    console.log("Hello, World!");
    return "Hello";
}

class TestClass {
    constructor(name) {
        this.name = name;
    }
    
    greet() {
        return `Hello, ${this.name}!`;
    }
    
    calculate(x, y) {
        return x + y;
    }
}

function main() {
    const test = new TestClass("Test");
    console.log(test.greet());
    helloWorld();
}

main();
""")
        
        # Create test markdown file
        md_file = temp_path / "README.md"
        md_file.write_text("""
# Test Project

This is a test project for testing the code analysis system.

## Features

- Test functions
- Test classes
- Documentation

## Usage

Run the test files to see the output.
""")
        
        yield temp_path


@pytest.fixture
def sample_code_file() -> CodeFile:
    """Create sample code file for testing."""
    return CodeFile(
        path="test_sample.py",
        absolute_path="/tmp/test_sample.py",
        file_type=FileType.CODE,
        language="python",
        size=500,
        last_modified=time.time(),
        content="""
def sample_function():
    '''A sample function for testing.'''
    x = 10
    y = 20
    return x + y

class SampleClass:
    '''A sample class for testing.'''
    
    def __init__(self, value):
        self.value = value
    
    def get_value(self):
        return self.value
    
    def set_value(self, new_value):
        self.value = new_value
        return self.value
"""
    )


@pytest.fixture
def sample_metadata() -> Dict[str, Any]:
    """Sample metadata for testing."""
    return {
        'file_size': 1024,
        'file_type': 'code',
        'chunk_index': 0,
        'ast_node_type': 'function_definition'
    } 
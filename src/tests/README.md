# Test Suite for Codex7

This directory contains comprehensive tests for the Codex7 codebase analysis system.

## Test Structure

### Core Tests
- `test_requirements.py` - Environment and dependency verification
- `test_neo4j_client.py` - Neo4j graph database client tests
- `test_milvus_client.py` - Milvus vector database client tests  
- `test_content_processor.py` - AST-based content processing tests
- `test_integration.py` - End-to-end integration tests

### Test Configuration
- `conftest.py` - pytest fixtures and configuration
- `run_tests.py` - Test runner script with various options

## Key Test Areas

### 1. Neo4j Client Tests (`test_neo4j_client.py`)
Tests the **fixed** Neo4j client that resolves the metadata Map object error:
- ✅ File node creation with flattened metadata  
- ✅ Chunk node creation without nested Map objects
- ✅ Function and class node creation
- ✅ Relationship creation and querying
- ✅ Error handling and edge cases
- ✅ Database cleanup verification

### 2. Content Processor Tests (`test_content_processor.py`)  
Tests the **enforced AST-only** processing:
- ✅ AST parser initialization and language support
- ✅ File processing with mandatory AST usage
- ✅ Skipping files without AST support (as requested)
- ✅ Error handling for malformed code
- ✅ No fallback to text splitter (enforced AST-only)

### 3. Integration Tests (`test_integration.py`)
End-to-end tests covering:
- ✅ Complete scan → process → graph pipeline
- ✅ Error recovery and partial processing
- ✅ Large file handling
- ✅ Cleanup verification

## Running Tests

### Prerequisites
1. **Databases Running**: Ensure Neo4j and Milvus are running and accessible
2. **Environment**: Set up environment variables in `.env` file
3. **Dependencies**: Install all required packages from `requirements.txt`

### Environment Variables
Set these in your `.env` file or environment:
```bash
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Milvus Configuration  
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Optional: OpenAI for embedding tests
OPENAI_API_KEY=your_api_key
```

### Quick Start
```bash
# Run all tests
python src/tests/run_tests.py

# Check environment only
python src/tests/run_tests.py --env-only

# Test specific components
python src/tests/run_tests.py --neo4j-only
python src/tests/run_tests.py --processor-only

# Verbose output
python src/tests/run_tests.py --verbose
```

### Using pytest directly
```bash
# Run all tests
pytest src/tests/ -v

# Run specific test file
pytest src/tests/test_neo4j_client.py -v

# Run specific test
pytest src/tests/test_neo4j_client.py::TestNeo4jClient::test_create_file_node -v
```

## Test Features

### Automatic Cleanup
- **Neo4j**: Clears all test data after each test
- **Milvus**: Drops test collections after each test
- **Temporary files**: Automatically cleaned up

### Error Testing
- Tests verify the **metadata Map object fix** works correctly
- Tests verify **AST-only enforcement** skips unsupported files
- Comprehensive error handling and recovery testing

### Mock Data
- Temporary codebases with Python, JavaScript, and Markdown files
- Sample chunks with proper metadata structure
- Deterministic test data for reproducible results

## Expected Test Results

### With Working Environment
- `test_requirements.py`: All dependencies available
- `test_neo4j_client.py`: All tests pass (no Map object errors)  
- `test_content_processor.py`: Tests pass, some files skipped if AST unavailable
- `test_milvus_client.py`: All vector operations work
- `test_integration.py`: End-to-end pipeline completes

### With Limited Environment
- Some tests may be skipped if dependencies unavailable
- AST parser tests skip if tree-sitter not installed
- Database tests skip if connections unavailable
- System gracefully handles missing components

## Troubleshooting

### Neo4j Connection Issues
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Test connection
python -c "from src.graph.neo4j_client import Neo4jClient; Neo4jClient()"
```

### Milvus Connection Issues  
```bash
# Check Milvus is running
docker ps | grep milvus

# Test connection
python -c "from src.query.milvus_client import MilvusClient; MilvusClient()"
```

### Tree-sitter Issues
```bash
# Install tree-sitter languages
pip install tree-sitter tree-sitter-python tree-sitter-javascript
```

## Test Data Cleanup

Tests automatically clean up after themselves, but you can manually clean:

```bash
# Clean Neo4j test data
python -c "
from src.graph.neo4j_client import Neo4jClient
client = Neo4jClient()
client.clear_database()
client.close()
"

# Clean Milvus test data  
python -c "
from src.query.milvus_client import MilvusClient
client = MilvusClient()
client.drop_collection()
client.close()
"
```

## Test Coverage

The tests verify all the key fixes and requirements:
- ✅ **Neo4j metadata Map object error fixed**
- ✅ **AST-only processing enforced** 
- ✅ **File skipping when AST unavailable**
- ✅ **End-to-end pipeline functionality**
- ✅ **Proper cleanup and error handling** 
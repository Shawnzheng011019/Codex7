import pytest
import sys
import importlib
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestRequirements:
    """Test that all required dependencies are available."""
    
    def test_python_version(self):
        """Test Python version is supported."""
        assert sys.version_info >= (3, 8), f"Python 3.8+ required, got {sys.version_info}"
        
    def test_core_dependencies(self):
        """Test that core dependencies can be imported."""
        required_modules = [
            'pymilvus', 
            'numpy',
            'pandas',
            'langchain',
            'pydantic',
            'loguru'
        ]
        
        missing_modules = []
        for module_name in required_modules:
            try:
                importlib.import_module(module_name)
                print(f"✓ {module_name} available")
            except ImportError:
                missing_modules.append(module_name)
                print(f"✗ {module_name} missing")
        
        if missing_modules:
            pytest.fail(f"Missing required modules: {missing_modules}")
    
    def test_optional_dependencies(self):
        """Test optional dependencies and report their status."""
        optional_modules = [
            'tree_sitter',
            'tree_sitter_languages', 
            'openai',
            'httpx',
            'aiofiles'
        ]
        
        available_optional = []
        missing_optional = []
        
        for module_name in optional_modules:
            try:
                importlib.import_module(module_name)
                available_optional.append(module_name)
                print(f"✓ {module_name} available (optional)")
            except ImportError:
                missing_optional.append(module_name)
                print(f"? {module_name} missing (optional)")
        
        print(f"Optional modules available: {available_optional}")
        print(f"Optional modules missing: {missing_optional}")
        
        # This test always passes, just reports status
        assert True
    
    def test_tree_sitter_languages(self):
        """Test tree-sitter language support."""
        try:
            from tree_sitter_languages import get_language
            
            test_languages = ['python', 'javascript', 'typescript', 'java', 'cpp', 'c', 'go', 'rust']
            supported_languages = []
            unsupported_languages = []
            
            for lang in test_languages:
                try:
                    get_language(lang)
                    supported_languages.append(lang)
                    print(f"✓ tree-sitter {lang} available")
                except Exception:
                    unsupported_languages.append(lang)
                    print(f"✗ tree-sitter {lang} not available")
            
            print(f"Supported AST languages: {supported_languages}")
            print(f"Unsupported AST languages: {unsupported_languages}")
            
            # Test passes if tree-sitter is available, regardless of language support
            assert True
            
        except ImportError:
            print("tree-sitter not available - AST parsing will be disabled")
            pytest.skip("tree-sitter not available")
    
    def test_database_connections(self):
        """Test database connection configuration."""
        import os
        
        # Check Milvus configuration  
        milvus_host = os.getenv('MILVUS_HOST', 'localhost')
        milvus_port = os.getenv('MILVUS_PORT', '19530')
        
        print(f"Milvus config: {milvus_host}:{milvus_port}")
        
        # Check Graph storage configuration
        graph_storage_path = os.getenv('GRAPH_STORAGE_PATH', 'graph_data.json')
        print(f"Graph storage: {graph_storage_path}")
        
        # This test just reports configuration, doesn't test actual connections
        assert milvus_host is not None
    
    def test_environment_setup(self):
        """Test environment setup and configuration."""
        import os
        from pathlib import Path
        
        # Check if .env file exists
        env_file = Path('.env')
        if env_file.exists():
            print("✓ .env file found")
        else:
            print("? .env file not found (using environment variables)")
        
        # Check critical environment variables
        critical_vars = [
            'OPENAI_API_KEY',
            'MILVUS_HOST',
            'GRAPH_STORAGE_PATH'
        ]
        
        set_vars = []
        missing_vars = []
        
        for var in critical_vars:
            if os.getenv(var):
                set_vars.append(var)
                print(f"✓ {var} set")
            else:
                missing_vars.append(var)
                print(f"? {var} not set")
        
        print(f"Environment variables set: {set_vars}")
        print(f"Environment variables missing: {missing_vars}")
        
        # Test passes regardless - this is just for information
        assert True 
#!/usr/bin/env python3
"""
Test runner script for the codebase analysis system.

This script runs comprehensive tests including:
- Environment verification
- Neo4j client tests (with metadata fix verification)
- Milvus client tests  
- Content processor tests (with AST enforcement)
- End-to-end integration tests

Usage:
    python src/tests/run_tests.py [options]

Options:
    --env-only      Only run environment tests
    --neo4j-only    Only run Neo4j tests
    --milvus-only   Only run Milvus tests
    --processor-only Only run content processor tests
    --integration-only Only run integration tests
    --no-cleanup    Skip cleanup operations
    --verbose       Verbose output
"""

import sys
import os
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_tests(args):
    """Run tests based on arguments."""
    import pytest
    
    pytest_args = []
    
    # Determine which tests to run
    test_files = []
    
    if args.env_only:
        test_files.append("src/tests/test_requirements.py")
    elif args.neo4j_only:
        test_files.append("src/tests/test_neo4j_client.py")
    elif args.milvus_only:
        test_files.append("src/tests/test_milvus_client.py")
    elif args.processor_only:
        test_files.append("src/tests/test_content_processor.py")
    elif args.integration_only:
        test_files.append("src/tests/test_integration.py")
    else:
        # Run all tests
        test_files = [
            "src/tests/test_requirements.py",
            "src/tests/test_content_processor.py",
            "src/tests/test_neo4j_client.py", 
            "src/tests/test_milvus_client.py",
            "src/tests/test_integration.py"
        ]
    
    pytest_args.extend(test_files)
    
    # Add verbose flag
    if args.verbose:
        pytest_args.append("-v")
        pytest_args.append("-s")
    
    # Add other pytest options
    pytest_args.extend([
        "--tb=short",  # Shorter traceback format
        "--durations=10",  # Show 10 slowest tests
    ])
    
    if not args.no_cleanup:
        pytest_args.append("--setup-show")  # Show fixture setup/teardown
    
    print("Running tests with arguments:", pytest_args)
    print("=" * 60)
    
    # Run tests
    exit_code = pytest.main(pytest_args)
    
    print("=" * 60)
    if exit_code == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ Tests failed with exit code: {exit_code}")
    
    return exit_code


def check_environment():
    """Check if the environment is ready for testing."""
    print("Checking environment...")
    
    # Check if we're in the right directory
    if not Path("src/tests").exists():
        print("Error: src/tests directory not found. Please run from project root.")
        return False
    
    # Check if critical files exist
    critical_files = [
        "src/config.py",
        "src/types.py",
        "src/graph/neo4j_client.py",
        "src/query/milvus_client.py",
        "src/processor/content_processor.py"
    ]
    
    missing_files = []
    for file_path in critical_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"Error: Missing critical files: {missing_files}")
        return False
    
    print("✓ Environment check passed")
    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive tests for the codebase analysis system"
    )
    
    parser.add_argument("--env-only", action="store_true", 
                       help="Only run environment verification tests")
    parser.add_argument("--neo4j-only", action="store_true",
                       help="Only run Neo4j client tests")
    parser.add_argument("--milvus-only", action="store_true", 
                       help="Only run Milvus client tests")
    parser.add_argument("--processor-only", action="store_true",
                       help="Only run content processor tests")
    parser.add_argument("--integration-only", action="store_true",
                       help="Only run integration tests")
    parser.add_argument("--no-cleanup", action="store_true",
                       help="Skip cleanup operations (keep test data)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    # Check environment first
    if not check_environment():
        sys.exit(1)
    
    # Run tests
    exit_code = run_tests(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main() 
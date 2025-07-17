"""
Builds a knowledge graph from source code files using Tree-sitter.
"""
from typing import List, Tuple, Optional
from pathlib import Path
from loguru import logger
from tree_sitter import Language, Parser
from .models import Node, Relationship

# Pre-compile languages for performance
def _load_tree_sitter_languages():
    """Load tree-sitter languages with proper error handling and path resolution."""
    import tree_sitter_python as tsp
    import tree_sitter_typescript as tsts
    
    try:
        # Use the vendor bindings if available, fallback to installed packages
        py_language = Language(tsp.language())
        ts_language = Language(tsts.language_typescript())
        logger.info("Successfully loaded tree-sitter languages from installed packages")
        return py_language, ts_language
    except Exception as e:
        logger.error(f"Failed to load tree-sitter languages: {e}")
        raise RuntimeError("Tree-sitter languages not available. Please install tree-sitter-python and tree-sitter-typescript packages.")

PY_LANGUAGE, TS_LANGUAGE = _load_tree_sitter_languages()


class GraphBuilder:
    """Parses code and builds a graph representation."""

    def __init__(self):
        self.parser = Parser()

    def _get_language_from_extension(self, file_path: str) -> Optional[Language]:
        """Get tree-sitter language based on file extension with error handling."""
        try:
            ext = Path(file_path).suffix.lower()
            if ext == '.py':
                return PY_LANGUAGE
            elif ext in ['.ts', '.tsx']:
                return TS_LANGUAGE
            # Add other languages here
            else:
                logger.debug(f"Unsupported file extension: {ext}")
                return None
        except Exception as e:
            logger.error(f"Error determining language for {file_path}: {e}")
            return None

    def build_graph_for_file(self, file_path: str, code_content: str) -> Tuple[List[Node], List[Relationship]]:
        """
        Builds a graph for a single file.
        Returns a tuple of nodes and relationships.
        """
        language = self._get_language_from_extension(file_path)
        if not language:
            logger.debug(f"Unsupported file type for graph construction: {file_path}")
            return [], []

        try:
            self.parser.set_language(language)
            tree = self.parser.parse(bytes(code_content, "utf8"))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return [], []
        
        nodes = []
        relationships = []

        # 1. Create a node for the file itself
        file_node = Node(label="File", properties={"name": Path(file_path).name, "path": file_path})
        nodes.append(file_node)

        # 2. Extract entities and relationships
        entities, relationships = self._extract_entities_and_relations(tree.root_node, file_node, code_content, language)
        nodes.extend(entities)
        relationships.extend(relationships)

        return nodes, relationships

    def _extract_entities_and_relations(self, root_node, file_node: Node, code: str, language: Language) -> Tuple[List[Node], List[Relationship]]:
        """
        Extracts a rich set of entities (classes, functions) and their
        relationships (imports, inheritance, calls).
        """
        nodes = []
        relationships = []
        
        # A map to quickly find a node's ID by its name
        entity_map = {}
        # A list to hold function definitions with their locations
        function_definitions = []

        # Define language-specific queries
        queries = {
            "python": {
                "imports": """(import_from_statement module_name: (dotted_name) @name)""",
                "functions": """(function_definition name: (identifier) @name) @func_def""",
                "classes": """
                    (class_definition
                        name: (identifier) @name
                        superclasses: (argument_list . (identifier) @superclass)?
                    ) @class_def
                """,
                "calls": """(call function: (identifier) @name) @call_expr""",
            },
            "typescript": {
                "imports": """(import_statement source: (string) @name)""",
                "functions": """(function_declaration name: (identifier) @name) @func_def""",
                "classes": """
                    (class_declaration
                        name: (type_identifier) @name
                        (class_heritage (extends_clause (identifier) @superclass))?
                    ) @class_def
                """,
                "calls": """(call_expression function: (identifier) @name) @call_expr""",
            }
        }
        
        lang_str = 'python' if language == PY_LANGUAGE else 'typescript'
        lang_queries = queries.get(lang_str, {})

        # --- Pass 1: Extract all top-level entities (Files, Classes, Functions, Imports) ---
        
        # Imports
        if "imports" in lang_queries:
            query = language.query(lang_queries["imports"])
            for capture, _ in query.captures(root_node):
                name = capture.text.decode('utf8').strip("'"")
                if name not in entity_map:
                    node = Node(label="Module", properties={"name": name})
                    nodes.append(node)
                    entity_map[name] = {"id": node.id, "type": "Module"}
                    relationships.append(Relationship(source_id=file_node.id, target_id=node.id, type="IMPORTS"))

        # Classes and Inheritance
        if "classes" in lang_queries:
            query = language.query(lang_queries["classes"])
            current_class_name = None
            for node, name in query.captures(root_node):
                if name == "class_def":
                    # Reset on each new class definition
                    current_class_name = None
                elif name == "name":
                    class_name = node.text.decode('utf8')
                    current_class_name = class_name
                    class_node = Node(label="Class", properties={"name": class_name, "file_path": file_node.properties["path"]})
                    nodes.append(class_node)
                    entity_map[class_name] = {"id": class_node.id, "type": "Class"}
                    relationships.append(Relationship(source_id=file_node.id, target_id=class_node.id, type="CONTAINS"))
                elif name == "superclass" and current_class_name:
                    superclass_name = node.text.decode('utf8')
                    # Create superclass node if it doesn't exist
                    if superclass_name not in entity_map:
                        superclass_node = Node(label="Class", properties={"name": superclass_name})
                        nodes.append(superclass_node)
                        entity_map[superclass_name] = {"id": superclass_node.id, "type": "Class"}
                    # Create inheritance relationship
                    relationships.append(Relationship(source_id=entity_map[current_class_name]["id"], target_id=entity_map[superclass_name]["id"], type="INHERITS_FROM"))

        # Functions
        if "functions" in lang_queries:
            query = language.query(lang_queries["functions"])
            for node, _ in query.captures(root_node):
                func_name_node = node.child_by_field_name('name')
                if func_name_node:
                    func_name = func_name_node.text.decode('utf8')
                    func_node = Node(label="Function", properties={"name": func_name, "file_path": file_node.properties["path"]})
                    nodes.append(func_node)
                    entity_map[func_name] = {"id": func_node.id, "type": "Function"}
                    relationships.append(Relationship(source_id=file_node.id, target_id=func_node.id, type="CONTAINS"))
                    function_definitions.append({
                        "name": func_name,
                        "id": func_node.id,
                        "start_line": node.start_point[0],
                        "end_line": node.end_point[0]
                    })

        # --- Pass 2: Extract precise CALLS relationships ---
        if "calls" in lang_queries and function_definitions:
            query = language.query(lang_queries["calls"])
            for node, _ in query.captures(root_node):
                call_name_node = node.child_by_field_name('function')
                if not call_name_node: continue
                
                called_func_name = call_name_node.text.decode('utf8')
                call_line = node.start_point[0]

                # Find which function this call belongs to
                caller_func = None
                for func_def in function_definitions:
                    if func_def["start_line"] <= call_line <= func_def["end_line"]:
                        caller_func = func_def
                        break
                
                # If we found the caller and the callee exists in our map, create the relationship
                if caller_func and called_func_name in entity_map:
                    caller_id = caller_func["id"]
                    callee_id = entity_map[called_func_name]["id"]
                    relationships.append(Relationship(source_id=caller_id, target_id=callee_id, type="CALLS"))

        return nodes, relationships

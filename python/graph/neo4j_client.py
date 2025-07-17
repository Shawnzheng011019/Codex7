"""
Neo4j client for graph database operations.
"""
from typing import List
from neo4j import GraphDatabase, Driver
from loguru import logger
from .models import Node, Relationship
from utils.config import config

class Neo4jClient:
    """A client to interact with a Neo4j database."""

    def __init__(self):
        """Initializes the Neo4j client."""
        self.uri = config.neo4j_uri
        self.user = config.neo4j_user
        self.password = config.neo4j_password
        self._driver: Driver = None

    def connect(self):
        """Establishes a connection to the database."""
        try:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self._driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j.")
            self._create_constraints()
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Closes the database connection."""
        if self._driver is not None:
            self._driver.close()
            logger.info("Neo4j connection closed.")

    def _create_constraints(self):
        """Create unique constraints and indexes for faster lookups."""
        with self._driver.session() as session:
            # Constraints ensure nodes are unique
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE")
            
            # Indexes speed up matching nodes
            session.run("CREATE INDEX file_path_index IF NOT EXISTS FOR (n:File) ON (n.path)")
            session.run("CREATE INDEX function_name_index IF NOT EXISTS FOR (n:Function) ON (n.name)")
            session.run("CREATE INDEX class_name_index IF NOT EXISTS FOR (n:Class) ON (n.name)")
            
            logger.info("Ensured constraints and indexes are in place.")

    def add_data(self, nodes: List[Node], relationships: List[Relationship]):
        """
        Adds a batch of nodes and relationships to the graph using a single,
        efficient UNWIND transaction.
        """
        if not self._driver:
            logger.warning("Driver not connected. Call connect() first.")
            return
        if not nodes and not relationships:
            logger.debug("No new nodes or relationships to add.")
            return

        nodes_to_create = [node.dict() for node in nodes]
        rels_to_create = [rel.dict() for rel in relationships]

        # This single query handles batch creation of nodes and relationships
        query = """
        // Create all nodes first
        UNWIND $nodes as node_data
        MERGE (n {id: node_data.id})
        ON CREATE SET n = node_data.properties, n.id = node_data.id, n.label = node_data.label
        WITH n
        CALL apoc.create.addLabels(n, [node_data.label]) YIELD node

        // Create all relationships
        WITH 'data' as separator // Dummy variable to separate node and rel creation
        UNWIND $rels as rel_data
        MATCH (source {id: rel_data.source_id})
        MATCH (target {id: rel_data.target_id})
        MERGE (source)-[r_new:%s]->(target)
        ON CREATE SET r_new = rel_data.properties
        """

        with self._driver.session() as session:
            # Note: Relationship types cannot be parameterized directly in Cypher.
            # We handle this by grouping relationships by type.
            rels_by_type = {}
            for rel in rels_to_create:
                rel_type = rel.pop('type')
                if rel_type not in rels_by_type:
                    rels_by_type[rel_type] = []
                rels_by_type[rel_type].append(rel)

            # Run the node creation part once
            if nodes_to_create:
                # Try APOC first, fallback to manual label setting
                try:
                    node_creation_query = """
                    UNWIND $nodes as node_data
                    MERGE (n {id: node_data.id})
                    ON CREATE SET n = node_data.properties, n.id = node_data.id
                    WITH n, node_data
                    CALL apoc.create.addLabels(n, [node_data.label]) YIELD node
                    RETURN count(node)
                    """
                    session.run(node_creation_query, nodes=nodes_to_create)
                    logger.info(f"Merged {len(nodes_to_create)} nodes using APOC.")
                except Exception as apoc_error:
                    logger.warning(f"APOC not available ({apoc_error}), using manual label setting")
                    # Fallback: group nodes by label and create them separately
                    nodes_by_label = {}
                    for node in nodes_to_create:
                        label = node.pop('label')
                        if label not in nodes_by_label:
                            nodes_by_label[label] = []
                        nodes_by_label[label].append(node)
                    
                    for label, label_nodes in nodes_by_label.items():
                        fallback_query = f"""
                        UNWIND $nodes as node_data
                        MERGE (n:{label} {{id: node_data.id}})
                        ON CREATE SET n = node_data.properties, n.id = node_data.id
                        RETURN count(n)
                        """
                        session.run(fallback_query, nodes=label_nodes)
                    logger.info(f"Merged {len(nodes_to_create)} nodes using fallback method.")

            # Run relationship creation for each type
            for rel_type, rels in rels_by_type.items():
                rel_creation_query = """
                UNWIND $rels as rel_data
                MATCH (source {id: rel_data.source_id})
                MATCH (target {id: rel_data.target_id})
                MERGE (source)-[r:%s]->(target)
                SET r += rel_data.properties
                """ % rel_type  # Safely format the relationship type
                session.run(rel_creation_query, rels=rels)
                logger.info(f"Merged {len(rels)} relationships of type {rel_type}.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

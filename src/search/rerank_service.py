from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from collections import defaultdict
import re

from ..config import settings
from ..types import SearchResult, CodeChunk, GraphResult
from ..utils.logger import app_logger


class GraphReranker:
    """Reranker that uses graph references to improve search results."""
    
    def __init__(self, neo4j_client):
        self.logger = app_logger.bind(component="graph_reranker")
        self.neo4j_client = neo4j_client
        self.threshold = settings.rerank_threshold
    
    async def rerank_results(self, results: List[SearchResult], 
                           query: str, 
                           top_k: int = 10) -> List[SearchResult]:
        """Rerank search results using graph information."""
        if not results:
            return results
        
        self.logger.info(f"Reranking {len(results)} results using graph information")
        
        # Calculate graph-based scores for each result
        reranked_results = []
        
        for result in results:
            # Get graph context for the chunk
            graph_score = await self._calculate_graph_score(result, query)
            
            # Combine original score with graph score
            combined_score = self._combine_scores(result.score, graph_score)
            
            # Update result
            result.score = combined_score
            result.metadata["graph_score"] = graph_score
            result.metadata["combined_score"] = combined_score
            
            reranked_results.append(result)
        
        # Sort by combined score
        reranked_results.sort(key=lambda x: x.score, reverse=True)
        
        # Re-rank
        for i, result in enumerate(reranked_results):
            result.rank = i + 1
        
        self.logger.info(f"Reranking completed, top result score: {reranked_results[0].score if reranked_results else 0}")
        
        return reranked_results[:top_k]
    
    async def _calculate_graph_score(self, result: SearchResult, query: str) -> float:
        """Calculate graph-based score for a result."""
        try:
            chunk_id = result.chunk.id
            
            # Get related chunks from graph
            graph_result = self.neo4j_client.find_related_chunks(
                chunk_id,
                relationship_types=["CALLS", "DEFINED_IN", "CONTAINS", "HAS_METHOD"],
                max_hops=2
            )
            
            # Calculate various graph-based features
            features = await self._extract_graph_features(result, query, graph_result)
            
            # Calculate final graph score
            graph_score = self._calculate_feature_score(features)
            
            return graph_score
            
        except Exception as e:
            self.logger.error(f"Error calculating graph score for {chunk_id}: {e}")
            return 0.0
    
    async def _extract_graph_features(self, result: SearchResult, query: str, 
                                    graph_result: GraphResult) -> Dict[str, Any]:
        """Extract graph-based features for reranking."""
        features = {}
        
        # Basic graph metrics
        features["node_count"] = len(graph_result.nodes)
        features["edge_count"] = len(graph_result.edges)
        features["degree_centrality"] = self._calculate_degree_centrality(graph_result)
        
        # Query relevance features
        features["query_function_matches"] = self._count_query_function_matches(query, graph_result)
        features["query_class_matches"] = self._count_query_class_matches(query, graph_result)
        
        # Code structure features
        features["function_depth"] = self._calculate_function_depth(result, graph_result)
        features["class_hierarchy_depth"] = self._calculate_class_hierarchy_depth(result, graph_result)
        
        # Importance features
        features["call_frequency"] = self._calculate_call_frequency(result, graph_result)
        features["inheritance_importance"] = self._calculate_inheritance_importance(result, graph_result)
        
        # Code quality features
        features["code_complexity"] = self._estimate_code_complexity(result)
        features["documentation_score"] = self._calculate_documentation_score(result)
        
        return features
    
    def _calculate_degree_centrality(self, graph_result: GraphResult) -> float:
        """Calculate degree centrality of the chunk in the graph."""
        if not graph_result.nodes:
            return 0.0
        
        # Count connections for each node
        node_degrees = defaultdict(int)
        
        for edge in graph_result.edges:
            node_degrees[edge.source_id] += 1
            node_degrees[edge.target_id] += 1
        
        if not node_degrees:
            return 0.0
        
        # Return max degree (representing the most connected node)
        return max(node_degrees.values()) / len(graph_result.nodes)
    
    def _count_query_function_matches(self, query: str, graph_result: GraphResult) -> int:
        """Count how many function names in the graph match the query."""
        query_lower = query.lower()
        function_nodes = [node for node in graph_result.nodes if node.type == "Function"]
        
        matches = 0
        for node in function_nodes:
            if query_lower in node.id.lower():
                matches += 1
        
        return matches
    
    def _count_query_class_matches(self, query: str, graph_result: GraphResult) -> int:
        """Count how many class names in the graph match the query."""
        query_lower = query.lower()
        class_nodes = [node for node in graph_result.nodes if node.type == "Class"]
        
        matches = 0
        for node in class_nodes:
            if query_lower in node.id.lower():
                matches += 1
        
        return matches
    
    def _calculate_function_depth(self, result: SearchResult, graph_result: GraphResult) -> int:
        """Calculate the depth of function calls."""
        # Find the function containing this chunk
        function_nodes = [
            node for node in graph_result.nodes 
            if node.type == "Function" and node.id != result.chunk.id
        ]
        
        if not function_nodes:
            return 0
        
        # Calculate maximum call depth
        max_depth = 0
        for node in function_nodes:
            depth = self._calculate_function_call_depth(node.id, graph_result, 0)
            max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _calculate_function_call_depth(self, function_id: str, graph_result: GraphResult, 
                                     current_depth: int) -> int:
        """Recursively calculate function call depth."""
        if current_depth > 10:  # Prevent infinite recursion
            return current_depth
        
        # Find functions called by this function
        called_functions = []
        for edge in graph_result.edges:
            if edge.source_id == function_id and edge.relationship_type == "CALLS":
                called_functions.append(edge.target_id)
        
        if not called_functions:
            return current_depth
        
        max_depth = current_depth
        for called_func in called_functions:
            depth = self._calculate_function_call_depth(called_func, graph_result, current_depth + 1)
            max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _calculate_class_hierarchy_depth(self, result: SearchResult, graph_result: GraphResult) -> int:
        """Calculate the depth of class hierarchy."""
        class_nodes = [node for node in graph_result.nodes if node.type == "Class"]
        
        if not class_nodes:
            return 0
        
        max_depth = 0
        for node in class_nodes:
            depth = self._calculate_class_inheritance_depth(node.id, graph_result, 0)
            max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _calculate_class_inheritance_depth(self, class_id: str, graph_result: GraphResult, 
                                         current_depth: int) -> int:
        """Recursively calculate class inheritance depth."""
        if current_depth > 10:  # Prevent infinite recursion
            return current_depth
        
        # Find parent classes
        parent_classes = []
        for edge in graph_result.edges:
            if edge.source_id == class_id and edge.relationship_type == "INHERITS_FROM":
                parent_classes.append(edge.target_id)
        
        if not parent_classes:
            return current_depth
        
        max_depth = current_depth
        for parent_class in parent_classes:
            depth = self._calculate_class_inheritance_depth(parent_class, graph_result, current_depth + 1)
            max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _calculate_call_frequency(self, result: SearchResult, graph_result: GraphResult) -> float:
        """Calculate how frequently this chunk is called by other functions."""
        chunk_id = result.chunk.id
        
        # Count incoming calls
        incoming_calls = 0
        for edge in graph_result.edges:
            if edge.target_id == chunk_id and edge.relationship_type == "CALLS":
                incoming_calls += 1
        
        # Normalize by total nodes
        total_nodes = len(graph_result.nodes)
        if total_nodes == 0:
            return 0.0
        
        return incoming_calls / total_nodes
    
    def _calculate_inheritance_importance(self, result: SearchResult, graph_result: GraphResult) -> float:
        """Calculate inheritance importance (how many classes inherit from this)."""
        chunk_id = result.chunk.id
        
        # Count children classes
        children_classes = 0
        for edge in graph_result.edges:
            if edge.target_id == chunk_id and edge.relationship_type == "INHERITS_FROM":
                children_classes += 1
        
        # Normalize by total nodes
        total_nodes = len(graph_result.nodes)
        if total_nodes == 0:
            return 0.0
        
        return children_classes / total_nodes
    
    def _estimate_code_complexity(self, result: SearchResult) -> float:
        """Estimate code complexity based on chunk content."""
        content = result.chunk.content
        
        # Simple complexity metrics
        lines = content.split('\n')
        complexity_score = 0
        
        # Count control structures
        control_keywords = ['if', 'else', 'elif', 'for', 'while', 'try', 'except', 'catch', 'switch']
        for line in lines:
            for keyword in control_keywords:
                if keyword in line.lower():
                    complexity_score += 1
        
        # Count nested structures (approximate by indentation)
        max_indentation = 0
        for line in lines:
            if line.strip():  # Skip empty lines
                indent = len(line) - len(line.lstrip())
                max_indentation = max(max_indentation, indent)
        
        complexity_score += max_indentation // 4  # Assuming 4 spaces per indent
        
        # Normalize by content length
        content_length = len(content)
        if content_length > 0:
            complexity_score = complexity_score / (content_length / 1000)  # Per 1000 characters
        
        return min(complexity_score, 1.0)  # Cap at 1.0
    
    def _calculate_documentation_score(self, result: SearchResult) -> float:
        """Calculate documentation score based on comments and docstrings."""
        content = result.chunk.content
        lines = content.split('\n')
        
        documentation_lines = 0
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*'):
                documentation_lines += 1
            elif '"""' in stripped or "'''" in stripped:
                documentation_lines += 1
        
        # Calculate ratio of documentation lines to total lines
        total_lines = len([line for line in lines if line.strip()])
        if total_lines == 0:
            return 0.0
        
        doc_ratio = documentation_lines / total_lines
        return min(doc_ratio, 1.0)  # Cap at 1.0
    
    def _calculate_feature_score(self, features: Dict[str, Any]) -> float:
        """Calculate final graph score from features."""
        # Feature weights (can be tuned)
        weights = {
            "degree_centrality": 0.2,
            "query_function_matches": 0.3,
            "query_class_matches": 0.3,
            "function_depth": 0.1,
            "class_hierarchy_depth": 0.1,
            "call_frequency": 0.2,
            "inheritance_importance": 0.2,
            "code_complexity": 0.1,
            "documentation_score": 0.1,
        }
        
        # Normalize features
        normalized_features = {}
        for key, value in features.items():
            if key in weights:
                normalized_features[key] = min(value / max(1, weights[key]), 1.0)
        
        # Calculate weighted score
        total_score = 0
        total_weight = 0
        
        for key, weight in weights.items():
            if key in normalized_features:
                total_score += normalized_features[key] * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return total_score / total_weight
    
    def _combine_scores(self, original_score: float, graph_score: float) -> float:
        """Combine original search score with graph score."""
        # Use threshold to determine how much to weight graph score
        if graph_score > self.threshold:
            # High graph score, give it more weight
            graph_weight = 0.4
            original_weight = 0.6
        else:
            # Low graph score, rely more on original score
            graph_weight = 0.2
            original_weight = 0.8
        
        combined_score = original_score * original_weight + graph_score * graph_weight
        return combined_score
    
    def get_rerank_stats(self) -> Dict[str, Any]:
        """Get reranker statistics."""
        return {
            "threshold": self.threshold,
            "feature_weights": {
                "degree_centrality": 0.2,
                "query_function_matches": 0.3,
                "query_class_matches": 0.3,
                "function_depth": 0.1,
                "class_hierarchy_depth": 0.1,
                "call_frequency": 0.2,
                "inheritance_importance": 0.2,
                "code_complexity": 0.1,
                "documentation_score": 0.1,
            },
        }


class ConflictResolutionReranker:
    """Reranker that resolves conflicts between vector and BM25 results."""
    
    def __init__(self):
        self.logger = app_logger.bind(component="conflict_resolution")
    
    def resolve_conflicts(self, vector_results: List[SearchResult], 
                         bm25_results: List[SearchResult],
                         query: str,
                         top_k: int = 10) -> List[SearchResult]:
        """Resolve conflicts between vector and BM25 search results."""
        self.logger.info(f"Resolving conflicts between {len(vector_results)} vector and {len(bm25_results)} BM25 results")
        
        # Identify conflicts
        conflicts = self._identify_conflicts(vector_results, bm25_results)
        
        if not conflicts:
            # No conflicts, return simple combination
            return self._combine_without_conflicts(vector_results, bm25_results, top_k)
        
        # Resolve conflicts
        resolved_results = self._resolve_conflicts(conflicts, query)
        
        # Combine with non-conflicting results
        final_results = self._combine_results(vector_results, bm25_results, resolved_results, top_k)
        
        return final_results
    
    def _identify_conflicts(self, vector_results: List[SearchResult], 
                           bm25_results: List[SearchResult]) -> List[Dict[str, Any]]:
        """Identify conflicts between vector and BM25 results."""
        conflicts = []
        
        # Get top results from each method
        vector_top = set(r.chunk.id for r in vector_results[:5])
        bm25_top = set(r.chunk.id for r in bm25_results[:5])
        
        # Find results that are high in one but low in the other
        for v_result in vector_results[:5]:
            if v_result.chunk.id not in bm25_top:
                # High in vector, low in BM25
                bm25_rank = next((r.rank for r in bm25_results if r.chunk.id == v_result.chunk.id), len(bm25_results))
                conflicts.append({
                    "chunk_id": v_result.chunk.id,
                    "type": "vector_high_bm25_low",
                    "vector_rank": v_result.rank,
                    "bm25_rank": bm25_rank,
                    "vector_result": v_result,
                    "bm25_result": next((r for r in bm25_results if r.chunk.id == v_result.chunk.id), None),
                })
        
        for b_result in bm25_results[:5]:
            if b_result.chunk.id not in vector_top:
                # High in BM25, low in vector
                vector_rank = next((r.rank for r in vector_results if r.chunk.id == b_result.chunk.id), len(vector_results))
                conflicts.append({
                    "chunk_id": b_result.chunk.id,
                    "type": "bm25_high_vector_low",
                    "bm25_rank": b_result.rank,
                    "vector_rank": vector_rank,
                    "bm25_result": b_result,
                    "vector_result": next((r for r in vector_results if r.chunk.id == b_result.chunk.id), None),
                })
        
        return conflicts
    
    def _resolve_conflicts(self, conflicts: List[Dict[str, Any]], query: str) -> Dict[str, float]:
        """Resolve conflicts using query analysis."""
        resolved_scores = {}
        
        for conflict in conflicts:
            chunk_id = conflict["chunk_id"]
            
            # Analyze query type
            query_type = self._analyze_query_type(query)
            
            # Choose winner based on query type
            if query_type == "semantic":
                # Prefer vector results for semantic queries
                if conflict["type"] == "vector_high_bm25_low":
                    resolved_scores[chunk_id] = 1.0
                else:
                    resolved_scores[chunk_id] = 0.7
            elif query_type == "keyword":
                # Prefer BM25 results for keyword queries
                if conflict["type"] == "bm25_high_vector_low":
                    resolved_scores[chunk_id] = 1.0
                else:
                    resolved_scores[chunk_id] = 0.7
            else:
                # Mixed query, use average
                resolved_scores[chunk_id] = 0.8
        
        return resolved_scores
    
    def _analyze_query_type(self, query: str) -> str:
        """Analyze query type to determine search strategy."""
        query_lower = query.lower()
        
        # Check for keyword indicators
        keyword_indicators = ['function', 'class', 'method', 'variable', 'import', 'def', 'class']
        semantic_indicators = ['how to', 'what is', 'explain', 'implement', 'algorithm', 'pattern']
        
        keyword_count = sum(1 for indicator in keyword_indicators if indicator in query_lower)
        semantic_count = sum(1 for indicator in semantic_indicators if indicator in query_lower)
        
        if semantic_count > keyword_count:
            return "semantic"
        elif keyword_count > semantic_count:
            return "keyword"
        else:
            return "mixed"
    
    def _combine_without_conflicts(self, vector_results: List[SearchResult], 
                                 bm25_results: List[SearchResult],
                                 top_k: int) -> List[SearchResult]:
        """Combine results when there are no conflicts."""
        # Simple average of scores
        combined_dict = {}
        
        for result in vector_results + bm25_results:
            chunk_id = result.chunk.id
            if chunk_id not in combined_dict:
                combined_dict[chunk_id] = []
            combined_dict[chunk_id].append(result)
        
        final_results = []
        for chunk_id, results in combined_dict.items():
            avg_score = sum(r.score for r in results) / len(results)
            best_result = max(results, key=lambda x: x.score)
            
            final_result = SearchResult(
                chunk=best_result.chunk,
                score=avg_score,
                rank=0,  # Will be set later
                search_type="combined",
                metadata={"original_scores": [r.score for r in results]},
            )
            final_results.append(final_result)
        
        # Sort and rank
        final_results.sort(key=lambda x: x.score, reverse=True)
        for i, result in enumerate(final_results):
            result.rank = i + 1
        
        return final_results[:top_k]
    
    def _combine_results(self, vector_results: List[SearchResult], 
                         bm25_results: List[SearchResult],
                         resolved_scores: Dict[str, float],
                         top_k: int) -> List[SearchResult]:
        """Combine all results with conflict resolution."""
        # Create a dictionary of all results
        all_results = {}
        
        for result in vector_results + bm25_results:
            chunk_id = result.chunk.id
            if chunk_id not in all_results:
                all_results[chunk_id] = []
            all_results[chunk_id].append(result)
        
        # Apply conflict resolution
        final_results = []
        for chunk_id, results in all_results.items():
            if chunk_id in resolved_scores:
                # Apply resolution score
                resolution_factor = resolved_scores[chunk_id]
                avg_score = sum(r.score for r in results) / len(results)
                final_score = avg_score * resolution_factor
            else:
                # No conflict, use average
                final_score = sum(r.score for r in results) / len(results)
            
            best_result = max(results, key=lambda x: x.score)
            
            final_result = SearchResult(
                chunk=best_result.chunk,
                score=final_score,
                rank=0,  # Will be set later
                search_type="resolved",
                metadata={
                    "original_scores": [r.score for r in results],
                    "resolved": chunk_id in resolved_scores,
                },
            )
            final_results.append(final_result)
        
        # Sort and rank
        final_results.sort(key=lambda x: x.score, reverse=True)
        for i, result in enumerate(final_results):
            result.rank = i + 1
        
        return final_results[:top_k]
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import os
from pathlib import Path

from src.graph.json_graph_client import JsonGraphClient
from src.search.hybrid_search import HybridSearch
from src.query.milvus_client import MilvusClient
from src.embedding.embedding_service import EmbeddingService
from src.config import settings
from src.utils.logger import app_logger


app = FastAPI(title="Code Graph Visualizer API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
graph_client = JsonGraphClient(settings.graph_storage_path)
milvus_client = MilvusClient()
embedding_service = EmbeddingService()
hybrid_search = HybridSearch(milvus_client, graph_client, embedding_service)

# Mount static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class GraphDataResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class NodeDetailsResponse(BaseModel):
    node: Dict[str, Any]
    related_edges: List[Dict[str, Any]]
    related_nodes: List[Dict[str, Any]]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    vector_weight: float = 0.6
    bm25_weight: float = 0.4
    use_graph: bool = True


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_results: int


@app.get("/")
async def root():
    """Serve the main HTML page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Code Graph Visualizer</title>
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 20px;
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 30px;
            }
            .search-section {
                margin-bottom: 20px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
            }
            .search-box {
                width: 70%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 16px;
            }
            .search-btn {
                padding: 10px 20px;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }
            .search-btn:hover {
                background-color: #0056b3;
            }
            .graph-container {
                border: 1px solid #ddd;
                border-radius: 5px;
                height: 600px;
                overflow: hidden;
            }
            .node-details {
                margin-top: 20px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
                border-left: 4px solid #007bff;
            }
            .node-details h3 {
                margin-top: 0;
                color: #007bff;
            }
            .stats {
                display: flex;
                justify-content: space-around;
                margin-bottom: 20px;
            }
            .stat-item {
                text-align: center;
                padding: 10px;
                background-color: #e9ecef;
                border-radius: 5px;
                min-width: 100px;
            }
            .stat-number {
                font-size: 24px;
                font-weight: bold;
                color: #007bff;
            }
            .stat-label {
                font-size: 12px;
                color: #666;
            }
            .controls {
                margin-bottom: 15px;
            }
            .btn {
                padding: 8px 16px;
                margin-right: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                cursor: pointer;
                background-color: white;
            }
            .btn:hover {
                background-color: #f8f9fa;
            }
            .btn.active {
                background-color: #007bff;
                color: white;
            }
            #tooltip {
                position: absolute;
                padding: 8px;
                background-color: rgba(0, 0, 0, 0.8);
                color: white;
                border-radius: 4px;
                font-size: 12px;
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.3s;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Code Graph Visualizer</h1>
            
            <div class="stats" id="stats">
                <div class="stat-item">
                    <div class="stat-number" id="nodeCount">0</div>
                    <div class="stat-label">Nodes</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="edgeCount">0</div>
                    <div class="stat-label">Edges</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="fileCount">0</div>
                    <div class="stat-label">Files</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="functionCount">0</div>
                    <div class="stat-label">Functions</div>
                </div>
            </div>
            
            <div class="search-section">
                <h3>Search Code</h3>
                <input type="text" id="searchInput" class="search-box" placeholder="Enter your search query...">
                <button id="searchBtn" class="search-btn">Search</button>
                <div id="searchResults" style="margin-top: 10px;"></div>
            </div>
            
            <div class="controls">
                <button class="btn active" id="loadGraphBtn">Load Graph</button>
                <button class="btn" id="resetGraphBtn">Reset View</button>
                <button class="btn" id="centerGraphBtn">Center Graph</button>
            </div>
            
            <div class="graph-container">
                <svg id="graph"></svg>
            </div>
            
            <div class="node-details" id="nodeDetails" style="display: none;">
                <h3>Node Details</h3>
                <div id="nodeContent"></div>
            </div>
        </div>
        
        <div id="tooltip"></div>
        
        <script>
            let graphData = { nodes: [], edges: [] };
            let simulation;
            let svg;
            let width = 1160;
            let height = 600;
            
            // Initialize the graph
            function initGraph() {
                svg = d3.select("#graph")
                    .attr("width", width)
                    .attr("height", height);
                
                // Add zoom behavior
                const zoom = d3.zoom()
                    .scaleExtent([0.1, 4])
                    .on("zoom", (event) => {
                        g.attr("transform", event.transform);
                    });
                
                svg.call(zoom);
                
                // Create main group
                const g = svg.append("g");
                
                // Create arrow markers for directed edges
                svg.append("defs").append("marker")
                    .attr("id", "arrowhead")
                    .attr("viewBox", "0 -5 10 10")
                    .attr("refX", 15)
                    .attr("refY", 0)
                    .attr("markerWidth", 6)
                    .attr("markerHeight", 6)
                    .attr("orient", "auto")
                    .append("path")
                    .attr("d", "M0,-5L10,0L0,5")
                    .attr("fill", "#999");
            }
            
            // Load graph data
            async function loadGraph() {
                try {
                    const response = await fetch('/api/graph');
                    graphData = await response.json();
                    
                    updateStats();
                    renderGraph();
                    
                    document.getElementById('loadGraphBtn').textContent = 'Reload Graph';
                } catch (error) {
                    console.error('Error loading graph:', error);
                    alert('Error loading graph data');
                }
            }
            
            // Update statistics
            function updateStats() {
                const nodes = graphData.nodes;
                const edges = graphData.edges;
                
                document.getElementById('nodeCount').textContent = nodes.length;
                document.getElementById('edgeCount').textContent = edges.length;
                
                const fileCount = nodes.filter(n => n.type === 'File').length;
                const functionCount = nodes.filter(n => n.type === 'Function').length;
                
                document.getElementById('fileCount').textContent = fileCount;
                document.getElementById('functionCount').textContent = functionCount;
            }
            
            // Render the graph
            function renderGraph() {
                const g = svg.select("g");
                
                // Clear existing elements
                g.selectAll("*").remove();
                
                if (graphData.nodes.length === 0) {
                    g.append("text")
                        .attr("x", width / 2)
                        .attr("y", height / 2)
                        .attr("text-anchor", "middle")
                        .attr("font-size", "18px")
                        .attr("fill", "#666")
                        .text("No graph data available");
                    return;
                }
                
                // Create force simulation
                simulation = d3.forceSimulation(graphData.nodes)
                    .force("link", d3.forceLink(graphData.edges).id(d => d.id).distance(100))
                    .force("charge", d3.forceManyBody().strength(-300))
                    .force("center", d3.forceCenter(width / 2, height / 2))
                    .force("collision", d3.forceCollide().radius(30));
                
                // Create edges
                const edges = g.append("g")
                    .selectAll("line")
                    .data(graphData.edges)
                    .enter().append("line")
                    .attr("stroke", "#999")
                    .attr("stroke-width", 2)
                    .attr("marker-end", "url(#arrowhead)");
                
                // Create nodes
                const nodes = g.append("g")
                    .selectAll("circle")
                    .data(graphData.nodes)
                    .enter().append("circle")
                    .attr("r", d => getNodeRadius(d.type))
                    .attr("fill", d => getNodeColor(d.type))
                    .attr("stroke", "#fff")
                    .attr("stroke-width", 2)
                    .style("cursor", "pointer")
                    .call(d3.drag()
                        .on("start", dragstarted)
                        .on("drag", dragged)
                        .on("end", dragended))
                    .on("click", showNodeDetails)
                    .on("mouseover", showTooltip)
                    .on("mouseout", hideTooltip);
                
                // Add labels
                const labels = g.append("g")
                    .selectAll("text")
                    .data(graphData.nodes)
                    .enter().append("text")
                    .text(d => getNodeLabel(d))
                    .attr("font-size", "12px")
                    .attr("dx", 15)
                    .attr("dy", 4)
                    .style("pointer-events", "none");
                
                // Update positions on tick
                simulation.on("tick", () => {
                    edges
                        .attr("x1", d => d.source.x)
                        .attr("y1", d => d.source.y)
                        .attr("x2", d => d.target.x)
                        .attr("y2", d => d.target.y);
                    
                    nodes
                        .attr("cx", d => d.x)
                        .attr("cy", d => d.y);
                    
                    labels
                        .attr("x", d => d.x)
                        .attr("y", d => d.y);
                });
            }
            
            // Get node color based on type
            function getNodeColor(type) {
                const colors = {
                    'File': '#007bff',
                    'Chunk': '#28a745',
                    'Function': '#ffc107',
                    'Class': '#dc3545'
                };
                return colors[type] || '#6c757d';
            }
            
            // Get node radius based on type
            function getNodeRadius(type) {
                const radii = {
                    'File': 20,
                    'Chunk': 8,
                    'Function': 12,
                    'Class': 15
                };
                return radii[type] || 10;
            }
            
            // Get node label
            function getNodeLabel(node) {
                if (node.type === 'File') {
                    return node.file_path.split('/').pop();
                } else if (node.type === 'Function' || node.type === 'Class') {
                    return node.id.split('::').pop();
                }
                return node.id;
            }
            
            // Show node details
            async function showNodeDetails(event, d) {
                try {
                    const response = await fetch(`/api/node/${d.id}`);
                    const details = await response.json();
                    
                    const detailsDiv = document.getElementById('nodeDetails');
                    const contentDiv = document.getElementById('nodeContent');
                    
                    let content = `<strong>Type:</strong> ${details.node.type}<br>`;
                    content += `<strong>ID:</strong> ${details.node.id}<br>`;
                    
                    if (details.node.file_path) {
                        content += `<strong>File:</strong> ${details.node.file_path}<br>`;
                    }
                    
                    if (details.node.line_number) {
                        content += `<strong>Line:</strong> ${details.node.line_number}<br>`;
                    }
                    
                    // Add properties
                    if (details.node.properties) {
                        content += '<br><strong>Properties:</strong><br>';
                        for (const [key, value] of Object.entries(details.node.properties)) {
                            if (key !== 'content' || value.length <= 100) {
                                content += `<strong>${key}:</strong> ${value}<br>`;
                            } else {
                                content += `<strong>${key}:</strong> ${value.substring(0, 100)}...<br>`;
                            }
                        }
                    }
                    
                    // Add related nodes
                    if (details.related_nodes.length > 0) {
                        content += '<br><strong>Related Nodes:</strong><br>';
                        details.related_nodes.forEach(node => {
                            content += `- ${node.type}: ${node.id}<br>`;
                        });
                    }
                    
                    contentDiv.innerHTML = content;
                    detailsDiv.style.display = 'block';
                    
                } catch (error) {
                    console.error('Error loading node details:', error);
                }
            }
            
            // Show tooltip
            function showTooltip(event, d) {
                const tooltip = document.getElementById('tooltip');
                tooltip.style.opacity = 1;
                tooltip.style.left = (event.pageX + 10) + 'px';
                tooltip.style.top = (event.pageY - 10) + 'px';
                tooltip.innerHTML = `${d.type}: ${getNodeLabel(d)}`;
            }
            
            // Hide tooltip
            function hideTooltip() {
                document.getElementById('tooltip').style.opacity = 0;
            }
            
            // Drag functions
            function dragstarted(event, d) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }
            
            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }
            
            function dragended(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }
            
            // Search functionality
            async function performSearch() {
                const query = document.getElementById('searchInput').value;
                if (!query) return;
                
                try {
                    const response = await fetch('/api/search', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            query: query,
                            top_k: 10,
                            vector_weight: 0.6,
                            bm25_weight: 0.4,
                            use_graph: true
                        })
                    });
                    
                    const results = await response.json();
                    displaySearchResults(results.results);
                } catch (error) {
                    console.error('Error searching:', error);
                }
            }
            
            // Display search results
            function displaySearchResults(results) {
                const resultsDiv = document.getElementById('searchResults');
                
                if (results.length === 0) {
                    resultsDiv.innerHTML = '<p style="color: #666;">No results found</p>';
                    return;
                }
                
                let html = '<h4>Search Results:</h4><ul>';
                results.forEach(result => {
                    const chunk = result.chunk;
                    html += `<li style="margin-bottom: 8px;">
                        <strong>${chunk.file_path}:${chunk.start_line}-${chunk.end_line}</strong>
                        <br><small>Score: ${result.score.toFixed(4)} | Type: ${chunk.chunk_type}</small>
                    </li>`;
                });
                html += '</ul>';
                
                resultsDiv.innerHTML = html;
            }
            
            // Reset graph view
            function resetGraph() {
                if (simulation) {
                    simulation.alpha(1).restart();
                }
            }
            
            // Center graph
            function centerGraph() {
                svg.transition().duration(750).call(
                    d3.zoom().transform,
                    d3.zoomIdentity
                );
            }
            
            // Event listeners
            document.getElementById('loadGraphBtn').addEventListener('click', loadGraph);
            document.getElementById('searchBtn').addEventListener('click', performSearch);
            document.getElementById('resetGraphBtn').addEventListener('click', resetGraph);
            document.getElementById('centerGraphBtn').addEventListener('click', centerGraph);
            
            document.getElementById('searchInput').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });
            
            // Initialize on load
            initGraph();
            loadGraph();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/graph", response_model=GraphDataResponse)
async def get_graph_data():
    """Get complete graph data for visualization."""
    try:
        graph_data = graph_client.get_graph_data()
        return GraphDataResponse(**graph_data)
    except Exception as e:
        logger.error(f"Error getting graph data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/node/{node_id}", response_model=NodeDetailsResponse)
async def get_node_details(node_id: str):
    """Get detailed information about a specific node."""
    try:
        details = graph_client.get_node_details(node_id)
        if not details:
            raise HTTPException(status_code=404, detail="Node not found")
        return NodeDetailsResponse(**details)
    except Exception as e:
        logger.error(f"Error getting node details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search", response_model=SearchResponse)
async def search_code(request: SearchRequest):
    """Search code using hybrid search."""
    try:
        results = await hybrid_search.search(
            query=request.query,
            top_k=request.top_k,
            vector_weight=request.vector_weight,
            bm25_weight=request.bm25_weight,
            use_graph=request.use_graph
        )
        
        formatted_results = [result.to_dict() for result in results]
        return SearchResponse(results=formatted_results, total_results=len(results))
    except Exception as e:
        logger.error(f"Error searching code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get database statistics."""
    try:
        stats = graph_client.get_database_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files")
async def get_files():
    """Get all files in the graph."""
    try:
        nodes = graph_client.get_all_nodes()
        files = [node.to_dict() for node in nodes if node.type == "File"]
        return {"files": files}
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/file/{file_path:path}/structure")
async def get_file_structure(file_path: str):
    """Get structure of a specific file."""
    try:
        result = graph_client.get_file_structure(file_path)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error getting file structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger = app_logger.bind(component="api_server")
    logger.info("Starting Code Graph Visualizer API server")
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
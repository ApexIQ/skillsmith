"""Understand-Anything (UA) Bridge - Architectural Knowledge Ingestion Service."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from ..commands import console

@dataclass
class CodebaseHotspot:
    """Represents a high-complexity or high-dependency module in the graph."""
    path: str
    dependency_count: int
    complexity_score: float
    description: str

class GraphBridge:
    """Service for bridging Understand-Anything's Knowledge Graph into Skillsmith."""

    def __init__(self, project_root: Path):
        self.root = project_root
        # Move CK data into the managed .agent/context folder (CK = Codebase Knowledge)
        self.ck_dir = self.root / ".agent" / "context" / "ck"
        self.graph_path = self.ck_dir / "knowledge-graph.json"

    def has_knowledge_graph(self) -> bool:
        """Check if a CK knowledge graph already exists."""
        return self.graph_path.exists()

    def scan_baseline(self) -> Dict[str, Any]:
        """Scans the project for architectural patterns to create a baseline graph.
        
        This is a fallback for when the actual Codebase Knowledge (CK) graph 
        is not available, ensuring a 'Nothing Happened' experience is avoided.
        """
        nodes = []
        edges = []
        
        # Scan for common project folders: app, src, lib, source
        scan_dirs = ["app", "src", "lib", "source"]
        found_dirs = [d for d in scan_dirs if (self.root / d).exists()]
        
        if not found_dirs:
            found_dirs = ["."] # Fallback to root if none found
            
        for d in found_dirs:
            # Recursively scan for important files
            search_path = self.root / d
            for f in search_path.rglob("*.py"):
                if "__pycache__" in str(f) or ".venv" in str(f) or "tests" in str(f):
                    continue
                    
                rel_path = f.relative_to(self.root).as_posix()
                file_size = f.stat().st_size
                
                # Heuristic: Complexity approx based on size/LOC-ish
                complexity = min(1.0, file_size / 25000) 
                
                # Determine layer
                layer = "unknown"
                if "api" in rel_path or "routes" in rel_path or "controllers" in rel_path:
                    layer = "ui"
                elif "models" in rel_path or "db" in rel_path or "database" in rel_path:
                    layer = "data"
                elif "services" in rel_path or "logic" in rel_path or "core" in rel_path:
                    layer = "business-logic"
                
                nodes.append({
                    "id": rel_path,
                    "path": rel_path,
                    "metadata": {
                        "layer": layer,
                        "complexity": complexity,
                        "description": "Skillsmith Baseline Auto-Scan node"
                    }
                })
        
        return {"nodes": nodes, "edges": edges}

    def generate_knowledge_graph(self, data: Dict[str, Any]) -> bool:
        """Automatically creates the CK context directory and graph."""
        try:
            self.ck_dir.mkdir(parents=True, exist_ok=True)
            self.graph_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def ingest_graph(self) -> Optional[Dict[str, Any]]:
        """Parse the CK knowledge graph JSON.
        
        Returns:
            Dictionary containing the graph data or None if not found.
        """
        if not self.has_knowledge_graph():
            return None
            
        try:
            return json.loads(self.graph_path.read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"[red][ERROR][/red] Failed to parse CK Knowledge Graph: {e}")
            return None

    def extract_architectural_layers(self, graph_data: Dict[str, Any]) -> List[str]:
        """Extract higher-level architectural layers from the graph.
        
        CK classifies nodes into layers (e.g. 'ui', 'business-logic', 'data').
        """
        layers = set()
        nodes = graph_data.get("nodes", [])
        
        for node in nodes:
            layer = node.get("metadata", {}).get("layer")
            if layer:
                layers.add(layer)
        
        return sorted(list(layers))

    def detect_hotspots(self, graph_data: Dict[str, Any], limit: int = 5) -> List[CodebaseHotspot]:
        """Identify code modules with high complexity or incoming dependency counts.
        
        These hotspots are primary candidates for 'Deep-Sync' skill recommendations.
        """
        hotspots = []
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        # Calculate incoming dependency counts
        edge_counts = {}
        for edge in edges:
            target = edge.get("target")
            edge_counts[target] = edge_counts.get(target, 0) + 1
            
        for node in nodes:
            node_id = node.get("id")
            if not node_id:
                continue
                
            dep_count = edge_counts.get(node_id, 0)
            complexity = node.get("metadata", {}).get("complexity", 0.0)
            
            # Heuristic for a 'Hotspot'
            if dep_count > 5 or complexity > 0.7:
                hotspots.append(CodebaseHotspot(
                    path=node.get("path", node_id),
                    dependency_count=dep_count,
                    complexity_score=float(complexity),
                    description=node.get("metadata", {}).get("description", "Structural dependency node")
                ))
        
        # Sort by dependency count descending
        return sorted(hotspots, key=lambda x: x.dependency_count, reverse=True)[:limit]

    def sync_to_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Merge CK architectural intelligence into a Skillsmith Project Profile."""
        graph_data = self.ingest_graph()
        if not graph_data:
            return profile
            
        updated = dict(profile)
        
        # 1. Update layers (mapped to 'frameworks' context in current schema)
        layers = self.extract_architectural_layers(graph_data)
        if layers:
             updated.setdefault("frameworks", [])
             for layer in layers:
                 if layer not in updated["frameworks"]:
                     updated["frameworks"].append(f"arch-{layer}")
        
        # 2. Inject hotspots as 'Priority Areas'
        hotspots = self.detect_hotspots(graph_data)
        if hotspots:
            updated["priorities"] = list(set(updated.get("priorities", []) + ["architectural-integrity"]))
            # We add metadata for the composer to recognize high-impact files
            updated["_ck_hotspots"] = [h.__dict__ for h in hotspots]
            
        return updated

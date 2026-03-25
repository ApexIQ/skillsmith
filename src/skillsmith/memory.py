import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
import yaml

class MemoryManager:
    """Implements the Five-Layer Memory Reliability Pattern."""
    
    def __init__(self, project_root: Path):
        self.root = project_root
        self.agent_dir = self.root / ".agent"
        self.log_dir = self.agent_dir / "logs"
        self.context_dir = self.agent_dir / "context"
        
        # Ensure directories exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.context_dir.mkdir(parents=True, exist_ok=True)
        
        self.raw_log_path = self.log_dir / "raw_events.jsonl"
        self.lessons_path = self.agent_dir / "lessons.md"
        
        # Ensure files exist (Layer 1 & 2 placeholders)
        if not self.raw_log_path.exists():
            self.raw_log_path.touch()

    # --- Layer 1: Observer ---
    def log_event(self, event_type: str, data: Dict):
        """Record a raw event (tool call, output, or reasoning step)."""
        event = {
            "timestamp": time.time(),
            "type": event_type,
            "data": data
        }
        with open(self.raw_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    # --- Layer 2: Reflector (Logic for CLI) ---
    def compact_logs(self, model_hint: str = "gpt-4o-mini") -> str:
        """Logic to prepare logs for LLM compaction (CLI handles the actual LLM call)."""
        if not self.raw_log_path.exists():
            return "No raw logs found for compaction."
        
        # In a real tool, this would call an LLM to distill raw_events into lessons.md
        # For the library, we provide the ingestion logic.
        return f"Ready to reflect {self.raw_log_path.stat().st_size} bytes of raw history using {model_hint}."

    # --- Layer 4: Watcher (Fingerprinting) ---
    def get_file_fingerprint(self, file_path: Path) -> str:
        """Calculate SHA-256 hash for drift detection using specialized hashing utility."""
        from .utils.hashing import get_file_sha256
        return get_file_sha256(file_path)

    def verify_memory_integrity(self, memory_metadata: Dict) -> bool:
        """Check if a memory chunk is stale based on its linked file hash (L4)."""
        target_file = self.root / memory_metadata.get("file_path", "")
        if not target_file.exists():
            return False
        
        current_hash = self.get_file_fingerprint(target_file)
        return current_hash == memory_metadata.get("fingerprint")

    # --- Layer 5: Safeguard ---
    def get_token_utilization(self, current_context_tokens: int, limit: int = 128000) -> float:
        """Returns the context window usage percentage."""
        return (current_context_tokens / limit) * 100

    def trigger_safeguard(self, current_tokens: int, threshold: float = 80.0) -> bool:
        """Returns True if compaction should be forced."""
        usage = self.get_token_utilization(current_tokens)
        return usage >= threshold

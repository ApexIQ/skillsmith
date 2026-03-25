import hashlib
from pathlib import Path

def get_file_sha256(file_path: Path) -> str:
    """Calculate the SHA-256 hash of a file for drift detection (L4 Watcher)."""
    if not file_path.exists():
        return ""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in 4KB chunks
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_string_sha256(content: str) -> str:
    """Calculate the SHA-256 hash of a string."""
    return hashlib.sha256(content.encode()).hexdigest()

"""Binary Index Manager — Anchor Engine index cache (JSON + NPZ)."""
import json, logging
from pathlib import Path
from typing import Any, Optional
import numpy as np

logger = logging.getLogger(__name__)
DEFAULT_INDEX_FILENAME = "binary_index.json"
DEFAULT_NPZ_FILENAME = "binary_index.npz"

class BinaryIndexManager:
    FORMAT_VERSION = 4

    def __init__(self, rules_path: str, index_path: Optional[str] = None):
        self.rules_path = Path(rules_path)
        self.index_dir = Path(index_path) if index_path else self.rules_path
        self.index_path = self.index_dir / DEFAULT_INDEX_FILENAME
        self.npz_path = self.index_dir / DEFAULT_NPZ_FILENAME

    def index_mtime(self) -> float:
        return self.index_path.stat().st_mtime

    def is_stale(self) -> bool:
        if not self.index_path.exists() or not self.npz_path.exists():
            return True
        if not self._verify_integrity():
            return True
        index_mtime = self.index_mtime()
        for fpath in self.rules_path.rglob("*.md"):
            if fpath.stat().st_mtime > index_mtime:
                return True
        return False

    def _verify_integrity(self) -> bool:
        try:
            with open(self.index_path) as f:
                data = json.load(f)
            return data.get("format_version", 0) == self.FORMAT_VERSION
        except Exception:
            return False

    def load(self) -> Optional[dict[str, Any]]:
        try:
            with open(self.index_path) as f:
                data = json.load(f)
            try:
                with np.load(self.npz_path) as npz:
                    data["embeddings"] = dict(npz)
            except Exception:
                data["embeddings"] = {}
            return data
        except Exception as e:
            logger.warning("Binary index load failed: %s", e)
            return None

    def save(self, shard_map, bloom, semantic, rule_metadata, distinctive_keyword_index):
        try:
            embeddings = {}
            for rm in rule_metadata:
                rid = rm.get("id", "")
                if "fact_embeddings" in rm:
                    emb = rm.pop("fact_embeddings")
                    if emb is not None:
                        embeddings[f"emb_{rid}"] = emb
            data = {
                "format_version": self.FORMAT_VERSION,
                "shard_map": shard_map,
                "bloom": bloom,
                "semantic": semantic,
                "rule_metadata": rule_metadata,
                "distinctive_keyword_index": distinctive_keyword_index,
            }
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.index_path, "w") as f:
                json.dump(data, f, default=str, ensure_ascii=False)
            if embeddings:
                np.savez_compressed(self.npz_path, **embeddings)
            else:
                np.savez_compressed(self.npz_path)
            logger.debug("Binary index saved: %d rules, %d embeddings", len(rule_metadata), len(embeddings))
        except Exception as e:
            logger.warning("Binary index save failed: %s", e)

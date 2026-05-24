"""
Binary Index Serialization — Cold start'ı hızlandırmak için.

.anchor.idx dosyası:
  - JSON: shard_map, bloom_items, rule_metadata
  - .npz: TF-IDF vocab, idf, doc_vectors

JSON tabanlı (pickle DEĞİL) — güvenli, arbitrary code execution yok.
NPZ (numpy compressed) — TF-IDF vektörleri için.

Yeniden build gerektiğinde:
  1. .anchor.idx varsa → direkt yükle (~10ms)
  2. Yoksa veya rules dizini daha yeniyse → rebuild + save
"""

import base64
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from anchor import Rule
from anchor.organize.domain_shard import ShardRouter
from anchor.organize.bloom_index import BloomIndex
from anchor.organize.semantic_index import SemanticIndex


# Versiyon: format değişikliklerinde artır
FORMAT_VERSION = 4  # v4: distinctive_keyword_index (TF-IDF keyword matching)

logger = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    """Extended JSON encoder for numpy + set types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("ascii")
        return super().default(obj)


class SecureBinaryIndexManager:
    """
    Güvenli binary index lifecycle:
      build → save → load → invalidate
    
    pickle yok, JSON + NPZ kullanır.
    """
    
    def __init__(self, rules_path: str, index_path: Optional[str] = None):
        self.rules_path = Path(rules_path)
        self.index_path = Path(index_path) if index_path else self.rules_path.parent / ".anchor.idx"
        self.npz_path = self.index_path.with_suffix(".idx.npz")
        
        # Integrity check için hash
        self._data_hash: Optional[str] = None
    
    def _load_rule_source_hashes(self) -> str:
        """Rules dizinindeki tüm .md dosyalarının hash'ini hesapla."""
        if not self.rules_path.exists():
            return ""
        hasher = hashlib.sha256()
        for fpath in sorted(self.rules_path.rglob("*.md")):
            try:
                hasher.update(fpath.read_bytes())
            except Exception:
                pass
        return hasher.hexdigest()
    
    def is_stale(self) -> bool:
        """
        Index dosyası rules dizininden daha eski mi (veya bozuk mu)?
        
        Returns:
            True → rebuild gerekli
            False → mevcut index kullanılabilir
        """
        if not self.index_path.exists() or not self.npz_path.exists():
            return True
        
        # Önce integrity check
        if not self._verify_integrity():
            return True
        
        index_mtime = self.index_mtime()
        
        # Herhangi bir .md dosyası index'ten daha yeniyse?
        for fpath in self.rules_path.rglob("*.md"):
            if fpath.stat().st_mtime > index_mtime:
                return True
        
        return False
    
    def index_mtime(self) -> float:
        """Index dosyasının en son değişim zamanı."""
        return max(
            self.index_path.stat().st_mtime if self.index_path.exists() else 0,
            self.npz_path.stat().st_mtime if self.npz_path.exists() else 0,
        )
    
    def _compute_hash(self, data: dict) -> str:
        """JSON verisinin hash'ini hesapla."""
        serialized = json.dumps(data, sort_keys=True, cls=JSONEncoder)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def _verify_integrity(self) -> bool:
        """JSON index dosyasının integrity'ini kontrol et."""
        try:
            with open(self.index_path, "r") as f:
                data = json.load(f)
            
            stored_hash = data.get("_hash", "")
            version = data.get("_version", 0)
            
            if version != FORMAT_VERSION and version == 1:
                # v1 was pickle-based, always stale
                return False
            if version != FORMAT_VERSION:
                return False
            if not stored_hash:
                return False
            
            # Hash doğrulama
            data_copy = dict(data)
            data_copy.pop("_hash", None)
            computed = self._compute_hash(data_copy)
            
            return computed == stored_hash
        except (json.JSONDecodeError, IOError, KeyError):
            return False
    
    def save(self,
             shard_map: dict[str, str],
             bloom: BloomIndex,
             semantic: SemanticIndex,
             rule_metadata: list[dict],
             distinctive_keyword_index: dict[str, list[str]] | None = None):
        """
        Mevcut index'leri disk'e serialize et (JSON + NPZ).
        
        Args:
            shard_map: {topic_lower → shard_name}
            bloom: BloomIndex instance
            semantic: SemanticIndex instance
            rule_metadata: [{id, topic, priority, strictness, path, aliases, tags}]
        """
        t0 = time.perf_counter()
        
        # NPZ verisi (numpy native — embedding'ler burada saklanır)
        npz_data = {}
        
        if semantic._vocab and semantic._doc_vectors:
            vocab_keys = np.array(list(semantic._vocab.keys()), dtype=object)
            vocab_indices = np.array(list(semantic._vocab.values()), dtype=np.int32)
            idf_array = np.array(
                [semantic._idf.get(k, 1.0) for k in semantic._vocab.keys()],
                dtype=np.float32,
            )
            doc_ids = []
            doc_vecs = []
            for rid, vec in semantic._doc_vectors.items():
                doc_ids.append(rid)
                doc_vecs.append(vec)
            npz_data["vocab"] = vocab_keys
            npz_data["vocab_indices"] = vocab_indices
            npz_data["idf"] = idf_array
            npz_data["doc_ids"] = np.array(doc_ids, dtype=object)
            npz_data["doc_vecs"] = np.array(doc_vecs, dtype=np.float32)
        
        # Pre-computed fact embedding'leri NPZ'de sakla (numpy native)
        # JSON list olur, numpy array kaybolur
        fact_emb_keys = set()
        for meta in rule_metadata:
            emb = meta.pop("fact_embeddings", None)  # JSON'dan çıkar → NPZ'ye koy
            if emb is not None:
                rid = meta.get("id", "unknown")
                key = f"emb_{rid}"
                npz_data[key] = emb  # float16 native
                fact_emb_keys.add(key)
                logger.log(5, "Saved fact embeddings for %s to NPZ key=%s", rid, key)
        
        # 1. JSON: metadata + bloom + shard_map
        json_data = {
            "_version": FORMAT_VERSION,
            "_created_at": time.time(),
            "shard_map": shard_map,
            "bloom_items": list(bloom._set),
            "rule_metadata": rule_metadata,
            "distinctive_keyword_index": distinctive_keyword_index or {},
        }
        
        # Hash ekle (integrity check için)
        json_data["_hash"] = self._compute_hash(
            {k: v for k, v in json_data.items() if k != "_hash"}
        )
        
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, cls=JSONEncoder, ensure_ascii=False, indent=2)
        
        # 2. NPZ: TF-IDF vectors + fact embeddings
        if npz_data:
            np.savez(self.npz_path, **npz_data)
        
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info("Binary index saved: %s + %s (%.1fms, %d emb keys)",
                     self.index_path, self.npz_path, elapsed, len(fact_emb_keys))
    
    def load(self) -> Optional[dict]:
        """
        Disk'ten binary index yükle.
        
        Returns:
            {
                "shard_map": dict,
                "bloom": BloomIndex (hazır),
                "semantic": SemanticIndex (hazır),
                "rule_metadata": list[dict],
            }
            veya None (yükleme başarısız)
        """
        if not self.index_path.exists():
            return None
        
        t0 = time.perf_counter()
        
        try:
            # 1. JSON load
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Version kontrol
            version = data.get("_version", 0)
            if version != FORMAT_VERSION:
                print(f"⚠️  Binary index version mismatch: got {version}, expected {FORMAT_VERSION}")
                return None
            
            # Bloom reconstruct
            bloom = BloomIndex()
            for item in data.get("bloom_items", []):
                bloom.add(item)
            
            # Semantic reconstruct (NPZ'den)
            semantic = SemanticIndex()
            if self.npz_path.exists():
                npz = np.load(self.npz_path, allow_pickle=True)
                
                # Check if NPZ has TF-IDF vocab
                if "vocab" in npz:
                    vocab_keys = npz["vocab"]
                    vocab_indices = npz["vocab_indices"]
                    semantic._vocab = {str(k): int(v) for k, v in zip(vocab_keys, vocab_indices)}
                    
                    idf_vals = npz["idf"]
                    for k, v in zip(vocab_keys, idf_vals):
                        semantic._idf[str(k)] = float(v)
                    
                    doc_ids = npz["doc_ids"]
                    doc_vecs = npz["doc_vecs"]
                    for rid, vec in zip(doc_ids, doc_vecs):
                        semantic._doc_vectors[str(rid)] = vec.astype(np.float32)
                    
                    semantic._total_docs = len(doc_ids)
                    semantic._rebuild_matrix()
                
                # Reconstruct pre-computed fact embeddings from NPZ
                rule_metadata = data.get("rule_metadata", [])
                for meta in rule_metadata:
                    rid = meta.get("id", "")
                    key = f"emb_{rid}"
                    if key in npz:
                        meta["fact_embeddings"] = npz[key]  # float16
                        logger.log(5, "Loaded fact embeddings for %s from NPZ", rid)
            
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"📂 Binary index loaded: {elapsed:.1f}ms (JSON format)")
            
            return {
                "shard_map": data["shard_map"],
                "bloom": bloom,
                "semantic": semantic,
                "rule_metadata": rule_metadata,
                "distinctive_keyword_index": data.get("distinctive_keyword_index", {}),
            }
        
        except Exception as e:
            print(f"⚠️  Binary index load failed: {e}")
            return None
    
    def invalidate(self):
        """Index'i geçersiz kıl (sil)."""
        if self.index_path.exists():
            self.index_path.unlink()
        if self.npz_path.exists():
            self.npz_path.unlink()
        print("🗑️  Binary index invalidated")


# Backward compatibility alias
BinaryIndexManager = SecureBinaryIndexManager

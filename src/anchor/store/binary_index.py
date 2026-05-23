"""
Binary Index Serialization — Cold start'ı hızlandırmak için.

.anchor.idx dosyası:
  - pickle: shard_map, bloom_items, rule_metadata
  - .npz: TF-IDF vocab, idf, doc_vectors

Yeniden build gerektiğinde:
  1. .anchor.idx varsa → direkt yükle (~10ms)
  2. Yoksa veya rules dizini daha yeniyse → rebuild + save
"""

import pickle
import time
from pathlib import Path
from typing import Optional

import numpy as np

from anchor import Rule
from anchor.organize.domain_shard import ShardRouter
from anchor.organize.bloom_index import BloomIndex
from anchor.organize.semantic_index import SemanticIndex


class BinaryIndexManager:
    """
    Anchor binary index lifecycle:
      build → save → load → invalidate
    """
    
    def __init__(self, rules_path: str, index_path: Optional[str] = None):
        self.rules_path = Path(rules_path)
        self.index_path = Path(index_path) if index_path else self.rules_path.parent / ".anchor.idx"
        self.npz_path = self.index_path.with_suffix(".idx.npz")
    
    def is_stale(self) -> bool:
        """
        Index dosyası rules dizininden daha eski mi?
        
        Returns:
            True → rebuild gerekli
            False → mevcut index kullanılabilir
        """
        if not self.index_path.exists() or not self.npz_path.exists():
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
    
    def save(self, 
             shard_map: dict[str, str],
             bloom: BloomIndex,
             semantic: SemanticIndex,
             rule_metadata: list[dict]):
        """
        Mevcut index'leri disk'e serialize et.
        
        Args:
            shard_map: {topic_lower → shard_name}
            bloom: BloomIndex instance
            semantic: SemanticIndex instance
            rule_metadata: [{id, topic, priority, strictness, path, aliases, tags}]
        """
        t0 = time.perf_counter()
        
        # 1. Pickle: metadata + bloom + shard_map
        pickle_data = {
            "version": 1,
            "shard_map": shard_map,
            "bloom_items": list(bloom._set),
            "rule_metadata": rule_metadata,
        }
        
        with open(self.index_path, "wb") as f:
            pickle.dump(pickle_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        # 2. NPZ: TF-IDF vectors
        if semantic._vocab and semantic._doc_vectors:
            vocab_array = np.array(list(semantic._vocab.keys()), dtype=object)
            vocab_indices = np.array(list(semantic._vocab.values()), dtype=np.int32)
            idf_array = np.array([semantic._idf.get(k, 1.0) for k in semantic._vocab.keys()], dtype=np.float32)
            
            # Doc vectors: rule_id → vector
            doc_ids = []
            doc_vecs = []
            for rid, vec in semantic._doc_vectors.items():
                doc_ids.append(rid)
                doc_vecs.append(vec)
            
            np.savez(
                self.npz_path,
                vocab=vocab_array,
                vocab_indices=vocab_indices,
                idf=idf_array,
                doc_ids=np.array(doc_ids, dtype=object),
                doc_vecs=np.array(doc_vecs, dtype=np.float32),
            )
        
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"💾 Binary index saved: {self.index_path} + {self.npz_path} ({elapsed:.1f}ms)")
    
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
            # 1. Pickle load
            with open(self.index_path, "rb") as f:
                data = pickle.load(f)
            
            # Bloom reconstruct
            bloom = BloomIndex()
            for item in data.get("bloom_items", []):
                bloom.add(item)
            
            # Semantic reconstruct (NPZ'den)
            semantic = SemanticIndex()
            if self.npz_path.exists():
                npz = np.load(self.npz_path, allow_pickle=True)
                
                vocab_keys = npz["vocab"]
                vocab_indices = npz["vocab_indices"]
                semantic._vocab = {k: int(v) for k, v in zip(vocab_keys, vocab_indices)}
                
                idf_vals = npz["idf"]
                for k, v in zip(vocab_keys, idf_vals):
                    semantic._idf[str(k)] = float(v)
                
                doc_ids = npz["doc_ids"]
                doc_vecs = npz["doc_vecs"]
                for rid, vec in zip(doc_ids, doc_vecs):
                    semantic._doc_vectors[str(rid)] = vec.astype(np.float32)
                
                semantic._total_docs = len(doc_ids)
            
            elapsed = (time.perf_counter() - t0) * 1000
            print(f"📂 Binary index loaded: {elapsed:.1f}ms")
            
            return {
                "shard_map": data["shard_map"],
                "bloom": bloom,
                "semantic": semantic,
                "rule_metadata": data.get("rule_metadata", []),
            }
        
        except Exception as e:
            print(f"⚠️ Binary index load failed: {e}")
            return None
    
    def invalidate(self):
        """Index'i geçersiz kıl (sil)."""
        if self.index_path.exists():
            self.index_path.unlink()
        if self.npz_path.exists():
            self.npz_path.unlink()
        print("🗑️ Binary index invalidated")

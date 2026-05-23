"""
Semantic Index — Basit TF-IDF tabanlı topic similarity.

Amaç: LLM çıktısındaki bir konunun, KB'deki rule'larla 
semantic (anlamsal) olarak ne kadar eşleştiğini ölçmek.

Bağımlılık: numpy (minimal)
sentence-transformers gibi ağır modeller yok.
"""

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import numpy as np


class SemanticIndex:
    """
    TF-IDF vectorizer + cosine similarity.
    
    Her rule'un content'i bir vektöre dönüştürülür.
    LLM çıktısı da aynı uzayda bir vektöre dönüştürülür.
    Cosine similarity ile en yakın rule'lar bulunur.
    """
    
    def __init__(self, max_features: int = 5000):
        self.max_features = max_features
        self._vocab: dict[str, int] = {}      # token → index
        self._idf: dict[str, float] = {}      # token → idf
        self._doc_vectors: dict[str, np.ndarray] = {}  # rule_id → vector
        self._rule_paths: dict[str, Path] = {}  # rule_id → path
        
        self._doc_freq: dict[str, int] = defaultdict(int)
        self._total_docs = 0
    
    def _tokenize(self, text: str) -> list[str]:
        """Basit tokenization."""
        text = text.lower()
        # Markdown syntax'ı temizle
        text = re.sub(r'[#*|\-\[\]()`]', ' ', text)
        # Kelimeleri çıkar (Türkçe karakterler dahil)
        words = re.findall(r'\b[a-zçğıöşü0-9_]{3,}\b', text)
        # Stopwords (Türkçe + İngilizce)
        stopwords = {
            'bir', 've', 'bu', 'için', 'ile', 'olan', 'gibi', 'kadar',
            'the', 'and', 'for', 'with', 'this', 'that', 'from',
            'nedir', 'hakkında', 'nasıl', 'olarak', 'tarafından',
            'is', 'are', 'was', 'were', 'have', 'has', 'had',
            'not', 'but', 'or', 'as', 'to', 'of', 'in', 'on', 'at',
        }
        return [w for w in words if w not in stopwords]
    
    def fit(self, rules_path: str):
        """Tüm rule'ları oku, vocab ve IDF hesapla."""
        root = Path(rules_path)
        if not root.exists():
            return
        
        # Pass 1: Tüm dokümanları topla
        docs: list[tuple[str, list[str]]] = []  # (rule_id, tokens)
        
        for fpath in root.rglob("*.md"):
            try:
                text = fpath.read_text(encoding="utf-8")
                # Sadece content kısmı (frontmatter hariç)
                if text.startswith("---"):
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        text = parts[2]
                
                tokens = self._tokenize(text)
                if tokens:
                    rule_id = fpath.stem
                    docs.append((rule_id, tokens))
                    self._rule_paths[rule_id] = fpath
                    
                    # Document frequency hesapla
                    unique_tokens = set(tokens)
                    for tok in unique_tokens:
                        self._doc_freq[tok] += 1
            except Exception:
                pass
        
        self._total_docs = len(docs)
        if self._total_docs == 0:
            return
        
        # IDF hesapla
        for tok, df in self._doc_freq.items():
            self._idf[tok] = math.log(self._total_docs / (df + 1)) + 1.0
        
        # Vocab oluştur (en sık max_features token)
        sorted_tokens = sorted(self._idf.keys(), key=lambda t: self._idf[t], reverse=True)
        for i, tok in enumerate(sorted_tokens[:self.max_features]):
            self._vocab[tok] = i
        
        # Pass 2: Her dokümanı vektöre dönüştür
        vocab_size = len(self._vocab)
        for rule_id, tokens in docs:
            vec = np.zeros(vocab_size, dtype=np.float32)
            tf = Counter(tokens)
            
            for tok, count in tf.items():
                if tok in self._vocab:
                    idx = self._vocab[tok]
                    tf_val = 1 + math.log(count)  # sublinear tf
                    idf_val = self._idf.get(tok, 1.0)
                    vec[idx] = tf_val * idf_val
            
            # L2 normalize
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            
            self._doc_vectors[rule_id] = vec
    
    def query(self, text: str, top_k: int = 5) -> list[tuple[str, float]]:
        """
        Bir metin ver, en yakın rule'ları döndür.
        
        Returns:
            [(rule_id, cosine_similarity), ...]
        """
        if not self._vocab or not self._doc_vectors:
            return []
        
        tokens = self._tokenize(text)
        if not tokens:
            return []
        
        vocab_size = len(self._vocab)
        q_vec = np.zeros(vocab_size, dtype=np.float32)
        tf = Counter(tokens)
        
        for tok, count in tf.items():
            if tok in self._vocab:
                idx = self._vocab[tok]
                tf_val = 1 + math.log(count)
                idf_val = self._idf.get(tok, 1.0)
                q_vec[idx] = tf_val * idf_val
        
        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec /= norm
        
        # Cosine similarity (dot product, çünkü vektörler normalize)
        scores = []
        for rule_id, doc_vec in self._doc_vectors.items():
            sim = float(np.dot(q_vec, doc_vec))
            if sim > 0.01:  # Noise threshold
                scores.append((rule_id, sim))
        
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]
    
    def stats(self) -> dict:
        return {
            "vocab_size": len(self._vocab),
            "total_docs": self._total_docs,
            "indexed_vectors": len(self._doc_vectors),
        }

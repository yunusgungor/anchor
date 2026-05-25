"""
ContextManager — Multi-turn conversation context for Anchor Agent.

Özellikler:
  - Mesaj geçmişi (maks boyut kontrollü)
  - Aktif mod takibi
  - Görülmüş claim'ler (seen_claims) dedup — Anchor'ın aynı düzeltmeyi
    tekrar tekrar üretmesini engeller
  - Context özeti (token limiti için)
"""

import time
from collections import deque

MAX_MESSAGES = 50
MAX_CLAIMS = 500


class ContextManager:
    """
    Multi-turn conversation context manager.
    
    Kullanım:
        ctx = ContextManager()
        ctx.add_message("user", "NPX1 nedir?")
        ctx.add_message("assistant", "NPX1 bir AI hızlandırıcısıdır...")
        ctx.add_claims(["NPX1 bir hızlandırıcıdır"])
        
        history = ctx.get_history(recent=5)
        is_seen = ctx.is_seen("NPX1 bir hızlandırıcıdır")
        # → True
    """
    
    def __init__(self, max_messages: int = MAX_MESSAGES, max_claims: int = MAX_CLAIMS):
        self._messages: deque[dict] = deque(maxlen=max_messages)
        self._seen_claims: set[str] = set()
        self._max_claims = max_claims
        self._current_mode: str = "factcheck"
        self._session_id: str | None = None
        self._metadata: dict = {}
    
    # ------------------------------------------------------------------ #
    # Message History
    # ------------------------------------------------------------------ #
    
    def add_message(self, role: str, content: str, mode: str | None = None, **extra) -> None:
        """
        Conversation'a mesaj ekle.
        
        Args:
            role: "user", "assistant", veya "system"
            content: Mesaj metni
            mode: Şu anki mod (opsiyonel, değişmediyse None)
            extra: Metadata (latency_ms, correction_count, vb.)
        """
        entry = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        if mode:
            entry["mode"] = mode
            self._current_mode = mode
        if extra:
            entry.update(extra)
        
        self._messages.append(entry)
    
    def get_history(
        self, recent: int | None = None, role: str | None = None
    ) -> list[dict]:
        """Konuşma geçmişini döndür."""
        msgs = list(self._messages)
        
        if role:
            msgs = [m for m in msgs if m["role"] == role]
        
        if recent:
            return msgs[-recent:]
        return list(msgs)
    
    def get_message_count(self) -> int:
        """Toplam mesaj sayısı."""
        return len(self._messages)
    
    def format_for_llm(self, max_tokens: int = 2000) -> str:
        """
        Geçmişi LLM context'ine uygun string'e çevir.
        
        Token limitini aşmamak için son mesajlara öncelik verir.
        """
        if not self._messages:
            return ""
        
        # Son N mesajı al (token budget'e göre)
        estimated_tokens_per_msg = 50  # rough estimate
        recent_count = max(1, max_tokens // estimated_tokens_per_msg)
        recent = list(self._messages)[-recent_count:]
        
        lines = []
        for msg in recent:
            role = msg["role"].upper()
            content = msg["content"][:200]  # truncate long messages
            lines.append(f"[{role}]: {content}")
        
        return "\n".join(lines)
    
    # ------------------------------------------------------------------ #
    # Seen Claims (Dedup)
    # ------------------------------------------------------------------ #
    
    def add_claims(self, claims: list[str]) -> None:
        """Görülmüş claim'leri ekle. Set limitini aşarsa eski claim'leri temizle."""
        if not claims:
            return
        
        for c in claims:
            normalized = self._normalize_claim(c)
            if normalized:
                self._seen_claims.add(normalized)
        
        # Set limit aşımı — anomaly detection eski claim'leri temizle
        if len(self._seen_claims) > self._max_claims:
            self._prune_claims()
    
    def is_seen(self, claim: str) -> bool:
        """Bu claim daha önce görüldü mü?"""
        return self._normalize_claim(claim) in self._seen_claims
    
    def get_new_claims(self, claims: list[str]) -> list[str]:
        """Daha önce görülmemiş claim'leri filtrele."""
        return [c for c in claims if not self.is_seen(c)]
    
    def _normalize_claim(self, claim: str) -> str:
        """Claim normalize et: lowercase, strip, whitespace tekilleştir."""
        if not claim or not isinstance(claim, str):
            return ""
        return " ".join(claim.lower().strip().split())
    
    def _prune_claims(self) -> None:
        """En eski %25 claim'i temizle."""
        # Set → list → sırala → ilk %25'i at
        ordered = sorted(self._seen_claims)
        keep_count = int(len(ordered) * 0.75)
        self._seen_claims = set(ordered[-keep_count:])
    
    # ------------------------------------------------------------------ #
    # Mode Tracking
    # ------------------------------------------------------------------ #
    
    @property
    def current_mode(self) -> str:
        return self._current_mode
    
    @current_mode.setter
    def current_mode(self, mode: str) -> None:
        if mode in ("factcheck", "workflow", "creative"):
            self._current_mode = mode
    
    # ------------------------------------------------------------------ #
    # Session Management
    # ------------------------------------------------------------------ #
    
    @property
    def session_id(self) -> str | None:
        return self._session_id
    
    def new_session(self, session_id: str | None = None) -> str:
        """Yeni oturum başlat (geçmişi temizle)."""
        self.reset()
        self._session_id = session_id or f"session_{int(time.time())}"
        return self._session_id
    
    def set_metadata(self, **kwargs) -> None:
        """Session metadata güncelle."""
        self._metadata.update(kwargs)
    
    def get_metadata(self, key: str | None = None):
        """Metadata oku."""
        if key:
            return self._metadata.get(key)
        return dict(self._metadata)
    
    def reset(self) -> None:
        """Tüm context'i temizle."""
        self._messages.clear()
        self._seen_claims.clear()
        self._current_mode = "factcheck"
        self._metadata = {}
    
    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    
    @property
    def stats(self) -> dict:
        return {
            "message_count": len(self._messages),
            "seen_claims_count": len(self._seen_claims),
            "current_mode": self._current_mode,
            "session_id": self._session_id,
        }

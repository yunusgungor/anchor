"""
Anchor Chat UI — FastAPI Web Application.

Çalıştırma:
    cd /workspace/anchor
    pip install fastapi uvicorn
    ANCHOR_LLM_PROVIDER=mock python -m uvicorn src.anchor.ui.app:app --host 0.0.0.0 --port 8080

Endpoint:
    POST /api/ask    → Agent'a soru sor, düzeltilmiş cevap al
    GET  /           → Chat UI
"""

import os
import sys
from pathlib import Path

# Anchor path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from anchor.agent import SafeLLMAgent
from anchor.agent.llm_client import BaseLLMClient, LLMClient

# ==================== CONFIG ====================
RULES_PATH = os.getenv("ANCHOR_RULES", str(Path(__file__).parent.parent.parent.parent / "rules"))
INDEX_PATH = os.getenv("ANCHOR_INDEX", str(Path(__file__).parent.parent.parent.parent / ".anchor_chat.idx"))
LLM_PROVIDER = os.getenv("ANCHOR_LLM_PROVIDER", "mock")
LLM_API_KEY = os.getenv("ANCHOR_LLM_API_KEY", "")

# ==================== MOCK LLM (Demo) ====================
class DemoLLMClient(BaseLLMClient):
    """Demo mock LLM — gerçek LLM yerine sabit cevaplar."""
    
    RESPONSES = {
        "npx1": "NPX1, genel amaçlı bir AI hızlandırıcısıdır ve TSMC 7nm'de üretilir. NVIDIA Jetson ile rekabet eder.",
        "mimari": "NPX1, RISC-V mimarili bir işlemcidir.",
        "doğru": "NPX1, edge AI işlemcisidir. SKY130 (130nm) açık kaynak PDK'da üretilir.",
        "stateguard": "StateGuard, pasif bir güvenlik aracıdır. Uygulama güvenliği için kullanılır.",
        "sky130": "SKY130, Global Foundries'in 130nm sürecidir.",
    }
    
    def chat(self, prompt: str, system=None) -> str:
        p = prompt.lower()
        for key, value in self.RESPONSES.items():
            if key in p:
                return value
        return f"Mock LLM cevabı: {prompt[:30]}..."
    
    def stream_chat(self, prompt: str, system=None):
        text = self.chat(prompt, system)
        for word in text.split():
            yield word + " "

# Register mock provider
LLMClient.PROVIDERS["mock"] = DemoLLMClient

# ==================== FASTAPI APP ====================
app = FastAPI(title="Anchor Chat", version="2.0")

# Statik dosyalar
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Global agent (singleton)
_agent = None

def get_agent() -> SafeLLMAgent:
    """Lazy agent initialization."""
    global _agent
    if _agent is None:
        # Demo mod: mock provider'ı LLMClient'a ekle
        LLMClient.PROVIDERS["mock"] = DemoLLMClient
        
        _agent = SafeLLMAgent(
            rules_path=RULES_PATH,
            llm_provider=LLM_PROVIDER,
            llm_api_key=LLM_API_KEY,
            index_path=INDEX_PATH,
        )
        # SafeLLMAgent __init__ içinde engine.build() zaten çağrılıyor
    
    return _agent

# ==================== MODELS ====================
class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    query: str
    raw: str
    corrected: str
    modified: bool
    confidence: float
    corrections: list[dict]
    latency_ms: float
    topics: list[str]
    rules_activated: list[str]
    report: str

# ==================== ROUTES ====================
@app.get("/")
async def index():
    """Chat UI ana sayfa."""
    return FileResponse(static_path / "index.html")

@app.post("/api/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """Agent'a soru sor, düzeltilmiş cevap al."""
    agent = get_agent()
    result = agent.ask(req.question)
    
    return AskResponse(
        query=result.query,
        raw=result.raw,
        corrected=result.corrected,
        modified=result.modified,
        confidence=result.confidence,
        corrections=result.corrections,
        latency_ms=result.latency_ms,
        topics=result.topics,
        rules_activated=result.rules_activated,
        report=result.report,
    )

@app.get("/api/stats")
async def stats():
    """Agent istatistikleri."""
    agent = get_agent()
    return agent.stats

@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok", "anchor": "v2.0", "rules_loaded": len(get_agent().engine.store._rule_meta)}

# ==================== MAIN ====================
if __name__ == "__main__":
    import uvicorn
    print(f"⚓ Anchor Chat UI başlatılıyor...")
    print(f"   Rules: {RULES_PATH}")
    print(f"   Index: {INDEX_PATH}")
    print(f"   URL: http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)

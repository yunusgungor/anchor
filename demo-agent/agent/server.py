"""
Anchor Agent — FastAPI Server.

API Endpoints:
  POST /ask          → Tek sorgu
  POST /chat         → Multi-turn chat
  POST /stream       → Streaming sorgu (SSE)
  POST /batch        → Toplu işleme
  POST /reset        → Konuşmayı sıfırla
  GET  /stats        → İstatistikler
  GET  /modes        → Mod listesi
  GET  /health       → Health check

Kullanım:
    anchor-agent serve --port 8080
    # veya
    python -m agent.server
"""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError(
        "FastAPI server için gerekli paketler: pip install fastapi uvicorn pydantic"
    )

from .core.agent import AnchorAgent
from .core.classifier import MODE_REGISTRY

logger = logging.getLogger("anchor-agent")

# ------------------------------------------------------------------ #
# Global agent instance
# ------------------------------------------------------------------ #

_agent: AnchorAgent | None = None


def get_agent() -> AnchorAgent:
    """Global agent instance'ını döndür."""
    global _agent
    if _agent is None:
        _agent = AnchorAgent(
            rules_path=os.environ.get("ANCHOR_RULES_PATH", "rules"),
            llm_provider=os.environ.get("ANCHOR_LLM_PROVIDER", "openai"),
            llm_api_key=os.environ.get("ANCHOR_LLM_API_KEY"),
            llm_model=os.environ.get("ANCHOR_LLM_MODEL"),
            llm_base_url=os.environ.get("ANCHOR_LLM_BASE_URL"),
            index_path=os.environ.get("ANCHOR_INDEX_PATH"),
        )
    return _agent


# ------------------------------------------------------------------ #
# Models
# ------------------------------------------------------------------ #

class AskRequest(BaseModel):
    query: str = Field(..., description="Soru metni")
    mode: Optional[str] = Field(None, description="Zorla mod (factcheck/workflow/creative)")
    verbose: bool = Field(False, description="Detaylı rapor")


class AskResponse(BaseModel):
    mode: str
    query: str
    raw: str
    corrected: str
    modified: bool
    corrections: list[dict] = []
    topics: list[str] = []
    rules_activated: list[str] = []
    confidence: float
    latency_ms: float
    report: str = ""


class ChatRequest(BaseModel):
    message: str = Field(..., description="Kullanıcı mesajı")
    mode: Optional[str] = Field(None, description="Zorla mod")


class BatchRequest(BaseModel):
    queries: list[str] = Field(..., description="Sorgu listesi")
    mode: Optional[str] = Field(None, description="Zorla mod")


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ------------------------------------------------------------------ #
# App Factory
# ------------------------------------------------------------------ #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama lifecycle."""
    logger.info("🚀 Anchor Agent API starting...")
    agent = get_agent()
    logger.info(f"   Rules: {agent._safe.engine.rules_path}")
    logger.info(f"   LLM: {agent._safe.llm.provider}")
    yield
    logger.info("👋 Anchor Agent API shutting down...")


def create_app() -> FastAPI:
    """FastAPI uygulaması oluştur."""
    app = FastAPI(
        title="Anchor Agent API",
        description="🔍 Anchor ile güvence altına alınmış AI Agent",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ------------------------------------------------------------------ #
    # Routes
    # ------------------------------------------------------------------ #
    
    @app.get("/health", tags=["System"])
    async def health():
        """Health check."""
        return {
            "status": "ok",
            "timestamp": time.time(),
            "agent_alive": _agent is not None,
        }
    
    @app.get("/modes", tags=["System"])
    async def list_modes():
        """Kullanılabilir modları listele."""
        return {"modes": MODE_REGISTRY}
    
    @app.get("/stats", tags=["System"])
    async def stats():
        """Agent istatistikleri."""
        agent = get_agent()
        return agent.stats
    
    @app.post("/reset", tags=["Conversation"])
    async def reset_conversation():
        """Konuşma geçmişini sıfırla."""
        agent = get_agent()
        agent.reset_conversation()
        return {"status": "ok", "message": "Conversation reset"}
    
    @app.post("/ask", response_model=AskResponse, tags=["Query"])
    async def ask(request: AskRequest):
        """Tek sorgu işle."""
        agent = get_agent()
        
        try:
            result = agent.ask(
                query=request.query,
                mode=request.mode,
                verbose=request.verbose,
            )
            return AskResponse(
                mode=getattr(result, "_mode", "factcheck"),
                query=result.query,
                raw=result.raw,
                corrected=result.corrected,
                modified=result.modified,
                corrections=getattr(result, "corrections", []),
                topics=getattr(result, "topics", []),
                rules_activated=getattr(result, "rules_activated", []),
                confidence=getattr(result, "confidence", 0.0),
                latency_ms=getattr(result, "latency_ms", 0.0),
                report=getattr(result, "report", ""),
            )
        except Exception as e:
            logger.exception("Ask error")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/chat", response_model=AskResponse, tags=["Conversation"])
    async def chat(request: ChatRequest):
        """Multi-turn chat."""
        agent = get_agent()
        
        try:
            result = agent.chat(
                message=request.message,
                mode=request.mode,
            )
            return AskResponse(
                mode=getattr(result, "_mode", "factcheck"),
                query=result.query,
                raw=result.raw,
                corrected=result.corrected,
                modified=result.modified,
                corrections=getattr(result, "corrections", []),
                topics=getattr(result, "topics", []),
                rules_activated=getattr(result, "rules_activated", []),
                confidence=getattr(result, "confidence", 0.0),
                latency_ms=getattr(result, "latency_ms", 0.0),
                report=getattr(result, "report", ""),
            )
        except Exception as e:
            logger.exception("Chat error")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/batch", tags=["Query"])
    async def batch(request: BatchRequest):
        """Toplu sorgu işle."""
        agent = get_agent()
        
        try:
            results = agent.batch_ask(
                queries=request.queries,
                mode=request.mode,
            )
            return {
                "count": len(results),
                "results": [
                    AskResponse(
                        mode=getattr(r, "_mode", "factcheck"),
                        query=r.query,
                        raw=r.raw,
                        corrected=r.corrected,
                        modified=r.modified,
                        corrections=getattr(r, "corrections", []),
                        topics=getattr(r, "topics", []),
                        rules_activated=getattr(r, "rules_activated", []),
                        confidence=getattr(r, "confidence", 0.0),
                        latency_ms=getattr(r, "latency_ms", 0.0),
                        report=getattr(r, "report", ""),
                    )
                    for r in results
                ],
            }
        except Exception as e:
            logger.exception("Batch error")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/stream", tags=["Query"])
    async def stream_ask(request: AskRequest):
        """
        Streaming sorgu (SSE).
        
        Önce LLM chunk'ları, sonra final düzeltme.
        """
        agent = get_agent()
        
        async def event_stream():
            for event in agent.stream_ask(
                query=request.query,
                mode=request.mode,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    
    @app.get("/", tags=["UI"])
    async def root():
        """API ana sayfa."""
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Anchor Agent API</title>
            <style>
                body { font-family: -apple-system, sans-serif; max-width: 640px; margin: 3em auto; padding: 0 1em; }
                h1 { font-size: 2em; }
                .card { background: #f5f5f5; padding: 1.5em; border-radius: 12px; margin: 1em 0; }
                code { background: #e8e8e8; padding: 2px 6px; border-radius: 4px; }
            </style>
        </head>
        <body>
            <h1>🔍 Anchor Agent API</h1>
            <p>Anchor ile güvence altına alınmış AI Agent REST API</p>
            <div class="card">
                <strong>📖 API Documentation:</strong><br>
                <a href="/docs">Swagger UI</a> | <a href="/redoc">ReDoc</a>
            </div>
            <div class="card">
                <strong>🎯 Modes:</strong>
                <ul>
                    <li><code>factcheck</code> — A1-A4 pipeline + Negation + Judge</li>
                    <li><code>workflow</code> — Workflow Governor + Step Validation</li>
                    <li><code>creative</code> — C5 Constraint Engine + Format Enforcement</li>
                </ul>
            </div>
            <div class="card">
                <strong>🔌 Endpoints:</strong>
                <ul>
                    <li><code>POST /ask</code> — Single query</li>
                    <li><code>POST /chat</code> — Multi-turn conversation</li>
                    <li><code>POST /stream</code> — Streaming response (SSE)</li>
                    <li><code>POST /batch</code> — Batch processing</li>
                    <li><code>GET /health</code> — Health check</li>
                </ul>
            </div>
        </body>
        </html>
        """)
    
    return app


# Export for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "agent.server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )

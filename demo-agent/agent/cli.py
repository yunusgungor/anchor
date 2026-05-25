"""
Anchor Agent — CLI Entry Point.

Kullanım:
    # Tek sorgu
    anchor-agent ask "NPX1 nedir?" --mode factcheck
    
    # Multi-turn chat
    anchor-agent chat
    
    # Batch işleme
    anchor-agent batch queries.txt
    
    # API sunucusu
    anchor-agent serve --port 8080
    
    # İstatistikler
    anchor-agent stats
    
    # Modları listele
    anchor-agent modes
"""

import argparse
import json
import os
import sys
import time

from .core.agent import AnchorAgent


def build_parser() -> argparse.ArgumentParser:
    """CLI argument parser'ı oluştur."""
    parser = argparse.ArgumentParser(
        prog="anchor-agent",
        description="🔍 Anchor Agent — AI doğruluk katmanı ile güvence altına alınmış LLM asistanı",
        epilog="Döküman: https://anchor.nousresearch.com",
    )
    
    parser.add_argument(
        "--rules", "-r",
        default=os.environ.get("ANCHOR_RULES_PATH", "rules"),
        help="Anchor rules dizini (env: ANCHOR_RULES_PATH, default: rules/)",
    )
    parser.add_argument(
        "--provider", "-p",
        default=os.environ.get("ANCHOR_LLM_PROVIDER", "openai"),
        help="LLM provider (openai/anthropic/ollama/openai-compatible, env: ANCHOR_LLM_PROVIDER)",
    )
    parser.add_argument(
        "--api-key", "-k",
        default=os.environ.get("ANCHOR_LLM_API_KEY"),
        help="LLM API key (env: ANCHOR_LLM_API_KEY)",
    )
    parser.add_argument(
        "--model", "-m",
        default=os.environ.get("ANCHOR_LLM_MODEL"),
        help="LLM model (env: ANCHOR_LLM_MODEL)",
    )
    parser.add_argument(
        "--base-url", "-u",
        default=os.environ.get("ANCHOR_LLM_BASE_URL"),
        help="Custom API base URL (env: ANCHOR_LLM_BASE_URL)",
    )
    parser.add_argument(
        "--index", "-i",
        default=os.environ.get("ANCHOR_INDEX_PATH"),
        help="Anchor binary index yolu (env: ANCHOR_INDEX_PATH)",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Alt komutlar")
    
    # ---- ask ----
    ask_parser = subparsers.add_parser("ask", help="Tek soru sor")
    ask_parser.add_argument("query", nargs="?", help="Soru metni (boşsa interaktif)")
    ask_parser.add_argument("--mode", "-M", choices=["factcheck", "workflow", "creative"],
                           help="Zorla mod (default: auto-classify)")
    ask_parser.add_argument("--verbose", "-v", action="store_true", help="Detaylı rapor")
    ask_parser.add_argument("--json", "-j", action="store_true", help="JSON çıktı")
    ask_parser.add_argument("--html", action="store_true", help="HTML rapor çıktısı")
    ask_parser.add_argument("--output", "-o", help="Çıktı dosyası")
    
    # ---- chat ----
    chat_parser = subparsers.add_parser("chat", help="İnteraktif multi-turn chat")
    chat_parser.add_argument("--mode", "-M", choices=["factcheck", "workflow", "creative"],
                            help="Zorla mod (default: auto-classify)")
    chat_parser.add_argument("--no-color", action="store_true", help="Renksiz çıktı")
    
    # ---- batch ----
    batch_parser = subparsers.add_parser("batch", help="Toplu sorgu işleme")
    batch_parser.add_argument("file", help="Sorgu dosyası (her satır bir sorgu)")
    batch_parser.add_argument("--mode", "-M", choices=["factcheck", "workflow", "creative"],
                             help="Zorla mod")
    batch_parser.add_argument("--json", "-j", action="store_true", help="JSON çıktı")
    batch_parser.add_argument("--output", "-o", help="Çıktı dosyası")
    
    # ---- serve ----
    serve_parser = subparsers.add_parser("serve", help="FastAPI sunucusu başlat")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Sunucu host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8080, help="Sunucu port (default: 8080)")
    serve_parser.add_argument("--reload", action="store_true", help="Hot reload (dev)")
    
    # ---- stats ----
    subparsers.add_parser("stats", help="Agent istatistiklerini göster")
    
    # ---- modes ----
    subparsers.add_parser("modes", help="Kullanılabilir modları listele")
    
    return parser


def cmd_ask(args):
    """ask komutu — tek sorgu işle."""
    agent = _create_agent(args)
    
    if not args.query:
        # İnteraktif tek sorgu
        print("🔍 Anchor Agent — Sorunu yaz (Ctrl+D bitir):")
        try:
            query = sys.stdin.read().strip()
        except EOFError:
            return
        if not query:
            return
    else:
        query = args.query
    
    result = agent.ask(query, mode=args.mode)
    
    if args.json:
        output = agent.reporter.format_json(result)
        _print_json(output, args.output)
    elif args.html:
        html = agent.reporter.format_html(result)
        _write_output(html, args.output, "html")
    else:
        report = agent.reporter.format_terminal(result, mode=result._mode if hasattr(result, '_mode') else "factcheck")
        _write_output(report, args.output)
    
    # Compact bilgi stderr'de
    if not args.json and not args.html:
        compact = agent.reporter.format_terminal_compact(result)
        print(f"\n{compact}", file=sys.stderr)


def cmd_chat(args):
    """chat komutu — interaktif multi-turn."""
    agent = _create_agent(args)
    reporter = agent.reporter
    
    print("\n" + "=" * 60)
    print(" 🔍  Anchor Agent — Interactive Chat")
    print("    /mode <mode>    → Mod değiştir (factcheck/workflow/creative)")
    print("    /reset          → Konuşmayı sıfırla")
    print("    /stats          → İstatistikleri göster")
    print("    /help           → Bu mesajı göster")
    print("    /quit           → Çıkış")
    print("=" * 60)
    
    mode = args.mode or "auto"
    
    while True:
        try:
            query = input(f"\n[{mode}] You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Görüşürüz!")
            break
        
        if not query:
            continue
        
        # Komutlar
        if query.startswith("/"):
            cmd_parts = query[1:].split()
            cmd_name = cmd_parts[0].lower()
            
            if cmd_name == "quit":
                print("👋 Görüşürüz!")
                break
            elif cmd_name == "reset":
                agent.reset_conversation()
                print("🔄 Konuşma sıfırlandı.")
                continue
            elif cmd_name == "stats":
                print(json.dumps(agent.stats, indent=2, default=str))
                continue
            elif cmd_name == "help":
                print("/mode <mode>  /reset  /stats  /help  /quit")
                continue
            elif cmd_name == "mode":
                if len(cmd_parts) > 1 and cmd_parts[1] in ("factcheck", "workflow", "creative"):
                    mode = cmd_parts[1]
                    print(f"🎯 Mod: {mode.upper()}")
                else:
                    print(f"Geçersiz mod. Seçenekler: factcheck, workflow, creative")
                continue
            else:
                print(f"Bilinmeyen komut: {query}")
                continue
        
        # Sorgu
        result = agent.ask(query, mode=mode if mode != "auto" else None)
        
        print()  # newline
        print(reporter.format_terminal(result))
        print(f"\n[{result._mode}] {reporter.format_terminal_compact(result)}")


def cmd_batch(args):
    """batch komutu — dosyadan toplu işleme."""
    if not os.path.exists(args.file):
        print(f"❌ Dosya bulunamadı: {args.file}", file=sys.stderr)
        sys.exit(1)
    
    with open(args.file) as f:
        queries = [line.strip() for line in f if line.strip()]
    
    print(f"📦 {len(queries)} sorgu işleniyor...", file=sys.stderr)
    
    agent = _create_agent(args)
    results = agent.batch_ask(queries, mode=args.mode)
    
    if args.json:
        output = [agent.reporter.format_json(r) for r in results]
        _print_json(output, args.output)
    else:
        lines = []
        for i, (q, r) in enumerate(zip(queries, results), 1):
            lines.append(f"--- #{i}: {q[:60]}{'...' if len(q) > 60 else ''} ---")
            lines.append(r.corrected)
            lines.append(f"↳ {agent.reporter.format_terminal_compact(r)}")
            lines.append("")
        _write_output("\n".join(lines), args.output)
    
    modified = sum(1 for r in results if r.modified)
    print(f"✅ {len(results)} sorgu tamamlandı, {modified}'inde düzeltme yapıldı.", file=sys.stderr)


def cmd_serve(args):
    """serve komutu — FastAPI sunucusu."""
    try:
        import uvicorn
    except ImportError:
        print("❌ 'uvicorn' gerekli. Kur: pip install uvicorn", file=sys.stderr)
        sys.exit(1)
    
    # Start server
    print(f"🚀 Anchor Agent API: http://{args.host}:{args.port}")
    print(f"   Docs: http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        "anchor_demo.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


def cmd_stats(args):
    """stats komutu — istatistikleri göster."""
    agent = _create_agent(args)
    stats = agent.stats
    print(json.dumps(stats, indent=2, default=str))


def cmd_modes(args):
    """modes komutu — mevcut modları listele."""
    from .core.classifier import MODE_REGISTRY
    
    print(f"\n{'='*50}")
    print("  Anchor Agent — Kullanılabilir Modlar")
    print(f"{'='*50}")
    
    for mode_id, info in MODE_REGISTRY.items():
        print(f"\n {info['emoji']}  {info['name'].upper()}")
        print(f"    {info['tagline']}")
        print(f"    {info['description']}")
    
    print(f"\n{'='*50}")
    print("  Kullanım: anchor-agent ask \"soru\" --mode <mode>")
    print(f"{'='*50}\n")


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _create_agent(args) -> AnchorAgent:
    """Argumentlerden AnchorAgent oluştur."""
    return AnchorAgent(
        rules_path=args.rules,
        llm_provider=args.provider,
        llm_api_key=args.api_key,
        llm_model=args.model,
        llm_base_url=args.base_url,
        index_path=args.index,
    )


def _print_json(data, output_path=None):
    """JSON çıktısını yaz."""
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    _write_output(text, output_path)


def _write_output(text, output_path=None, suffix="txt"):
    """Çıktıyı dosyaya veya stdout'a yaz."""
    if output_path:
        with open(output_path, "w") as f:
            f.write(text)
        print(f"📄 Çıktı kaydedildi: {output_path}", file=sys.stderr)
    else:
        print(text)


def main():
    """Ana giriş noktası."""
    parser = build_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to command
    command_map = {
        "ask": cmd_ask,
        "chat": cmd_chat,
        "batch": cmd_batch,
        "serve": cmd_serve,
        "stats": cmd_stats,
        "modes": cmd_modes,
    }
    
    cmd_func = command_map.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

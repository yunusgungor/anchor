"""Compare embedding models for Turkish technical text"""
import sys, time
sys.path.insert(0, "/workspace/anchor/src")

# Test pairs - Turkish technical sentences
pairs = [
    # Semantically SIMILAR (should have HIGH cosine = low distance)
    ("FP4-op-vs-val", "StateGuard, LLM operatoru ve orkestratorudur",
     "Prodinamik Engine in LLM ciktilarini dogrulayan validasyon katmani"),
    ("FP6a-sky-130nm", "SkyWater Technology ve Google ile 130nm PDK",
     "130nm eski bir dugum ama tamamen acik kaynak PDK"),
    ("FP1-edge-vs-edge", "NPX1 edge AI islemcisidir",
     "Edge AI tarim ve guvenlik uygulamalari"),

    # Semantically DIFFERENT (should have LOW cosine)
    ("TP-tsmc-vs-sky", "NPX1 TSMC 7nm de uretilir",
     "SKY130 130nm OpenLane ile"),
    ("FP2-risc-vs-arch", "NPX1 RISC-V mimarili bir islemcidir",
     "RISC-V Systolic Array NPU"),
]

models_to_try = [
    "all-MiniLM-L6-v2",              # English focused (baseline)
    "paraphrase-multilingual-MiniLM-L12-v2",  # Multilingual (12 layers)
]

for model_name in models_to_try:
    print(f"\n{'='*70}")
    print(f"  Model: {model_name}")
    print(f"{'='*70}")

    # Flush sentence-transformers cache
    import anchor.judge.embedding as emb
    emb._model = None
    emb._model_name = None

    t0 = time.perf_counter()
    ok = emb.load_model(model_name)
    if not ok:
        print(f"  SKIP - could not load")
        continue
    print(f"  Load time: {time.perf_counter() - t0:.1f}s")

    for label, a, b in pairs:
        cd = emb.semantic_distance(a, b)
        cs = 1 - cd if cd is not None else 0.0

        # Jaccard for comparison
        wa = set(a.lower().split())
        wb = set(b.lower().split())
        jac = 1 - len(wa & wb) / len(wa | wb) if wa and wb else 1.0

        verdict = ""
        if cs > 0.5: verdict = "SIMILAR"
        elif cs < 0.3: verdict = "DIFFERENT"
        else: verdict = "BORDERLINE"

        print(f"  {label:<15s} cos={cs:.3f} jac={jac:.3f} [{verdict}]")

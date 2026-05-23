"""
C5: Constraint Engine — Creative Compliance Layer.

Her türlü kuralı (format, style, strategy) LLM çıktısına uygular.
Deterministik auto-fix + flag + suggest.

Kullanım:
    from anchor.compliance import ConstraintEngine
    
    engine = ConstraintEngine("rules/")
    violations = engine.check(llm_output, rule_type="creative_compliance")
    fixes = engine.auto_fix(violations)
"""

from .constraint_engine import ConstraintEngine, ConstraintViolation, ViolationSeverity, FixStrategy

__all__ = ["ConstraintEngine", "ConstraintViolation", "ViolationSeverity", "FixStrategy"]

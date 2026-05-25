"""
Anchor Agent — Demo package.

Anchor'ın tüm yeteneklerini sergileyen AI Agent.
"""

__version__ = "1.0.0"
__author__ = "Anchor Labs"

from .core.agent import AnchorAgent
from .core.classifier import TaskClassifier
from .core.context import ContextManager
from .core.reporter import Reporter
from .cli import main as cli_main

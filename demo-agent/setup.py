"""
Anchor Agent Setup.
"""

from setuptools import setup, find_packages

setup(
    name="anchor-agent",
    version="1.0.0",
    description="🔍 Anchor Agent — AI doğruluk katmanı ile güvence altına alınmış LLM asistanı",
    author="Anchor Labs",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "anchor",
    ],
    extras_require={
        "server": ["fastapi>=0.104", "uvicorn>=0.24", "pydantic>=2.0"],
    },
    entry_points={
        "console_scripts": [
            "anchor-agent=agent.cli:main",
        ],
    },
    python_requires=">=3.10",
)

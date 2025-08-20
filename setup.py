#!/usr/bin/env python3
"""
LLM主动提问与推理增强系统 - 安装脚本
"""

from setuptools import setup, find_packages
import pathlib

# 读取README文件
HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text(encoding='utf-8')

# 读取requirements文件
def read_requirements():
    req_path = HERE / "requirements.txt"
    if req_path.exists():
        with open(req_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="llm-active-questioning",
    version="0.2.0",
    description="通过增强LLM主动提问能力来提升推理能力并创造新的人机交互范式",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/llm-active-questioning",
    author="LLM Active Questioning Research Team",
    author_email="your-email@example.com",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="llm, artificial-intelligence, question-answering, reinforcement-learning, multi-turn-dialogue",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
            "pre-commit>=2.20.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
            "myst-parser>=0.18.0",
        ],
        "notebook": [
            "jupyter>=1.0.0",
            "ipywidgets>=8.0.0",
            "matplotlib>=3.5.0",
            "seaborn>=0.11.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "llm-aq-train=src.training.main:main",
            "llm-aq-eval=src.evaluation.main:main",
            "llm-aq-demo=multi_turn_system:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.json", "*.txt", "*.md"],
    },
    project_urls={
        "Bug Reports": "https://github.com/your-org/llm-active-questioning/issues",
        "Source": "https://github.com/your-org/llm-active-questioning",
        "Documentation": "https://your-org.github.io/llm-active-questioning/",
    },
)

"""QualiAI — AI-Powered Testing Agent"""

from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="quali-ai",
    version="0.1.0",
    description="AI-Powered Testing Agent — 自然语言驱动测试",
    author="mianmian5",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "quali=cli.main:cli",
        ],
    },
    python_requires=">=3.9",
)

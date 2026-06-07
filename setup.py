from setuptools import setup, find_packages

setup(
    name="film-tracker",
    version="1.0.0",
    description="终端影视追踪工具 - 管理你的片单和观看进度",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ft=film_tracker.cli:cli",
            "film-tracker=film_tracker.cli:cli",
        ],
    },
    python_requires=">=3.8",
)

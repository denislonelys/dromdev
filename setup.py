from setuptools import setup, find_packages

setup(
    name="iistudio",
    version="1.1.0",
    description="AI Studio - Interactive AI Agent with Claude 4.6",
    author="IIStudio Team",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "click>=8.1.0",
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "rich>=13.0.0",
        "aiofiles>=23.0.0",
        "redis>=5.0.0",
        "python-dotenv>=1.0.0",
        "loguru>=0.7.0",
        "playwright>=1.40.0",
    ],
    entry_points={
        "console_scripts": [
            "iis=iistudio:main",
        ],
    },
)

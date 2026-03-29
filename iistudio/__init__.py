"""
IIStudio — AI Dev Tool
Entry point package. Exports `cli` for setuptools console_scripts.
"""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path чтобы все модули (config, arena, core...)
# находились при запуске команды `iis` из любой директории
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from iistudio.main import cli  # noqa: F401, E402

__version__ = "1.0.0"
__all__ = ["cli"]

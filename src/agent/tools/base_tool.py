# src/agent/tools/base_tool.py

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTool(ABC):
    """Base class for all agent tools."""

    def __init__(self):
        self.name = self.__class__.__name__
        self.description = self.__doc__ or "No description"
        self.call_count = 0

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """Execute the tool."""
        pass

    def __call__(self, **kwargs) -> Dict[str, Any]:
        """Wrapper that adds metadata."""
        self.call_count += 1
        result = self.run(**kwargs)

        return {"tool": self.name, "result": result, "call_count": self.call_count}

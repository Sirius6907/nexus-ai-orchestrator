from abc import ABC, abstractmethod

class BaseTool(ABC):
    name: str = "base_tool"
    description: str = "Base description"
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> str:
        pass

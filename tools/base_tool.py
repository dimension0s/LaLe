"""mcp工具基类，所有外部工具的统一接口标准"""

from abc import ABC,abstractmethod
from typing import Dict,List,Any,Optional
from dataclasses import dataclass,field

@dataclass
class ToolDefinition:
    """工具定义"""
    name:str
    description:str
    input_schema:Dict[str,Any]
    output_schema:Dict[str,Any]

@dataclass
class ToolResult:
    """工具执行结果"""
    success:bool
    data:Any = None
    error:Optional[str] = None
    metadata:Dict[str,Any] = field(default_factory=dict)


class BaseTool(ABC):
    """所有工具基类"""

    @property
    @abstractmethod
    def definition(self)->ToolDefinition:
        """返回工具的定义（名称、描述、参数格式）"""
        pass

    @abstractmethod
    async def execute(self,*kwargs)->ToolResult:
        """执行工具的核心方法"""
        pass

    async def validate_input(self,*kwargs)->bool:
        """验证输入参数（可选）"""
        return True

    def _extract_word_from_context(self,word:str)-> str:
        """从上下文中提取单词（去除标点、空格）"""
        import re
        cleaned = re.sub(r'[^\w\-\']','',word)
        return cleaned.strip().lower()
















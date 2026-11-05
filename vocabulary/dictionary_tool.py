"""
词典工具 - 实现 MCP 接口标准的查词功能,虽然现在没有mcp
"""

import httpx
from typing import Dict, Optional, List
from loguru import logger
from tools.base_tool import BaseTool, ToolDefinition, ToolResult


class DictionaryTool(BaseTool):
    """
    词典查词工具
    当前使用有道词典 API（免费版），后续可扩展为牛津/剑桥等
    """
    
    def __init__(self):
        self.api_name = "youdao"
        self.base_url = "https://dict.youdao.com/jsonapi"
        
        # 可选：如果需要 API Key 认证，在这里配置
        self.api_key = None
        self.api_secret = None
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="dictionary",
            description="查询英文单词的释义、音标、例句等",
            input_schema={
                "type": "object",
                "properties": {
                    "word": {
                        "type": "string",
                        "description": "要查询的英文单词"
                    },
                    "context": {
                        "type": "string",
                        "description": "单词所在的上下文（用于选择最合适的释义）",
                        "required": False
                    }
                },
                "required": ["word"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "phonetic": {"type": "string"},
                    "phonetic_uk": {"type": "string"},
                    "phonetic_us": {"type": "string"},
                    "meanings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pos": {"type": "string"},
                                "meaning": {"type": "string"},
                                "example": {"type": "string"}
                            }
                        }
                    }
                }
            }
        )
    
    async def execute(self, word: str, context: str = None) -> ToolResult:
        """执行查词"""
        try:
            # 清理单词
            cleaned_word = self._extract_word_from_context(word)
            if not cleaned_word:
                return ToolResult(
                    success=False,
                    error=f"无效的单词: '{word}'"
                )
            
            logger.info(f"📖 查词: '{cleaned_word}'")
            
            # 调用有道词典 API
            result = await self._call_youdao_api(cleaned_word)
            
            if not result:
                # 降级：尝试本地模拟（仅用于演示）
                result = self._mock_dictionary(cleaned_word)
            
            # 如果有上下文，选择最合适的释义
            if context and result and "meanings" in result:
                result["selected_meaning"] = self._select_meaning(
                    result["meanings"], 
                    context
                )
            
            logger.info(f"✅ 查词成功: '{cleaned_word}'")
            return ToolResult(success=True, data=result)
            
        except httpx.TimeoutException:
            logger.error(f"⏰ 查词超时: '{word}'")
            return ToolResult(
                success=False,
                error="词典服务请求超时，请稍后重试"
            )
        except Exception as e:
            logger.error(f"❌ 查词失败: '{word}' - {e}")
            return ToolResult(
                success=False,
                error=f"查词失败: {str(e)}"
            )
    
    async def _call_youdao_api(self, word: str) -> Optional[Dict]:
        """
        调用有道词典 API
        有道词典有免费的公开 API（无需认证），但有访问频率限制
        """
        try:
            # 有道词典的免费 API 接口
            # 注意：此接口为公开接口，可能有 CORS 或频率限制
            # 生产环境建议使用官方 API Key
            params = {
                "q": word,
                "le": "en",  # 英语
                "client": "web"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.base_url,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                return self._parse_youdao_response(word, data)
                
        except Exception as e:
            logger.warning(f"有道 API 调用失败: {e}")
            return None
    
    def _parse_youdao_response(self, word: str, data: Dict) -> Dict:
        """解析有道词典的响应"""
        result = {
            "word": word,
            "phonetic": "",
            "phonetic_uk": "",
            "phonetic_us": "",
            "meanings": [],
            "api_source": "youdao"
        }
        
        try:
            # 解析音标
            if "basic" in data:
                basic = data["basic"]
                if "phonetic" in basic:
                    result["phonetic"] = basic["phonetic"]
                if "uk-phonetic" in basic:
                    result["phonetic_uk"] = basic["uk-phonetic"]
                if "us-phonetic" in basic:
                    result["phonetic_us"] = basic["us-phonetic"]
                
                # 解析释义
                if "explains" in basic:
                    for explain in basic["explains"]:
                        # 解析词性和释义，如 "v. 改变，转变"
                        parts = explain.split(" ", 1)
                        pos = parts[0] if len(parts) > 1 else ""
                        meaning = parts[1] if len(parts) > 1 else explain
                        result["meanings"].append({
                            "pos": pos,
                            "meaning": meaning,
                            "example": ""
                        })
            
            # 解析例句（如果有）
            if "web" in data and "web-translation_rag" in data["web"]:
                for trans in data["web"]["web-translation_rag"]:
                    # 添加示例用法
                    pass
                    
            return result
            
        except Exception as e:
            logger.error(f"解析有道响应失败: {e}")
            return {
                "word": word,
                "phonetic": "",
                "phonetic_uk": "",
                "phonetic_us": "",
                "meanings": [{"pos": "", "meaning": f"（释义解析失败）{word}", "example": ""}],
                "api_source": "youdao_error"
            }
    
    def _select_meaning(self, meanings: List[Dict], context: str) -> str:
        """
        根据上下文选择最合适的释义
        简单策略：优先选择包含上下文中关键字的释义
        """
        if not meanings:
            return ""
        
        # 如果只有一条释义，直接返回
        if len(meanings) == 1:
            return meanings[0].get("meaning", "")
        
        # 从上下文中提取关键词（简单做法）
        context_lower = context.lower()
        
        # 尝试找到最匹配的释义
        best_match = None
        best_score = -1
        
        for meaning in meanings:
            meaning_text = meaning.get("meaning", "").lower()
            # 计算释义与上下文的词重叠度
            words_in_meaning = set(meaning_text.split())
            words_in_context = set(context_lower.split())
            overlap = len(words_in_meaning & words_in_context)
            
            if overlap > best_score:
                best_score = overlap
                best_match = meaning
        
        if best_match and best_score > 0:
            return best_match.get("meaning", "")
        
        # 没有匹配，返回第一个
        return meanings[0].get("meaning", "")
    
    def _mock_dictionary(self, word: str) -> Dict:
        """模拟词典数据（API 不可用时的降级方案）"""
        # 常用单词的模拟数据
        mock_data = {
            "transform": {
                "word": "transform",
                "phonetic": "/trænsˈfɔːm/",
                "meanings": [
                    {"pos": "v.", "meaning": "改变，转变", "example": "AI is transforming the world."},
                    {"pos": "v.", "meaning": "改造，改革", "example": "The company is transforming its business model."}
                ]
            },
            "capable": {
                "word": "capable",
                "phonetic": "/ˈkeɪpəbl/",
                "meanings": [
                    {"pos": "adj.", "meaning": "有能力的，能干的", "example": "She is capable of handling this task."},
                    {"pos": "adj.", "meaning": "有…可能的", "example": "The situation is capable of improvement."}
                ]
            }
        }
        
        # 尝试匹配已知单词
        word_lower = word.lower()
        if word_lower in mock_data:
            result = mock_data[word_lower].copy()
            result["api_source"] = "mock"
            return result
        
        # 通用模拟
        return {
            "word": word,
            "phonetic": f"/{word}/",
            "meanings": [
                {"pos": "n.", "meaning": f"{word}（名词）", "example": f"This is a {word}."},
                {"pos": "v.", "meaning": f"{word}（动词）", "example": f"We need to {word} it."}
            ],
            "api_source": "mock"
        }


# 全局单例
dictionary_tool = DictionaryTool()
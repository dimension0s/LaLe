"""从oxford_dictionary_full.json中提取并排版单词信息"""

import json,sys
from pathlib import Path
from typing import Dict,Optional,Union


# ANSI颜色代码
RED = '\033[91m'
RESET = '\033[0m'

# 设置路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = PROJECT_ROOT / "data" / "output" / "oxford_dictionary" / "oxford_dictionary_full.json"

class WordFormatter:
    """单词信息格式化"""
    def __init__(self,dict_path: Optional[Union[Path, str]] = None):
        self.dict_path = Path(dict_path) if dict_path is not None else DICT_PATH
        self._data = None

    def load_data(self) -> Dict:
        """加载 json 数据"""
        if self._data is None:
            if not self.dict_path.exists():
                raise FileNotFoundError(f"词典文件不存在: {self.dict_path}")
            with open(self.dict_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        return self._data

    def lookup(self,word:str)->Optional[Dict]:
        """查找单词，返回词条数据"""
        data = self.load_data()
        word_lower = word.lower()
        # 精确匹配
        if word_lower in data:
            return data[word_lower]
        # 大小写不敏感匹配（若key不是小写）
        for key,val in data.items():
            if key.lower() == word_lower:
                return val
        return None

    def lookup_raw(self, word: str) -> Optional[Dict]:
        """
        查词，返回原始词条 dict（不做 ANSI 格式化）

        处理跳转词条：递归解析 redirect_target。
        """
        entry = self.lookup(word)
        if entry is None:
            return None

        # 处理跳转
        if entry.get("is_redirect"):
            target = entry.get("redirect_target", "")
            if target:
                return self.lookup_raw(target)
            return None

        return entry

    def format(self, word: str) -> str:
        """格式化单词信息，返回字符串"""
        entry = self.lookup(word)
        if entry is None:
            return f"❌ 未找到单词: {word}"

        # 处理跳转
        if entry.get("is_redirect"):
            target = entry.get("redirect_target", "")
            if target:
                return self.format(target)  # 递归跳转
            else:
                return f"⚠️ 跳转词条无目标: {word}"

        lines = []
        # ========== 1. 词头 + 词性 ==========
        headword = entry.get("headword", word)
        pos_list = entry.get("pos", [])
        pos_str = " / ".join(pos_list) if pos_list else ""
        # 红色词头
        head_line = f"{RED}{headword}{RESET}"
        if pos_str:
            head_line += f"  {pos_str}"
        lines.append(head_line)

        # ========== 2. 音标 ==========
        uk_phon = entry.get("phonetic_uk") or entry.get("phonetic") or ""
        us_phon = entry.get("phonetic_us") or ""
        phon_parts = []
        if uk_phon:
            phon_parts.append(f"🇬🇧 {uk_phon}")
        if us_phon:
            phon_parts.append(f"🇺🇸 {us_phon}")
        if phon_parts:
            lines.append("  ".join(phon_parts))

        # ========== 3. 释义和例句 ==========
        senses = entry.get("senses", [])
        if not senses:
            lines.append("\n⚠️ 该词条没有释义数据")
        else:
            for idx, sense in enumerate(senses, 1):
                # 释义编号和内容
                definition = sense.get("definition", "")
                translation = sense.get("translation_rag", "")
                line = f"\n{idx}. {definition}"
                if translation:
                    line += f"\n   {translation}"
                lines.append(line)

                # 例句
                examples = sense.get("examples", [])
                if examples:
                    for ex in examples:
                        eng = ex.get("english", "").strip()
                        chn = ex.get("chinese", "").strip()
                        if eng:
                            lines.append(f"   - {eng}")
                        if chn:
                            lines.append(f"     {chn}")
                else:
                    lines.append("   (无例句)")

        # ========== 4. 统计（可选） ==========
        total_examples = sum(len(s.get('examples', [])) for s in senses)
        lines.append(f"\n📊 释义 {len(senses)} 条，例句 {total_examples} 个")

        return "\n".join(lines)

# 便捷函数
def format_word(word: str) -> str:
    """外部调用接口：返回格式化后的单词信息"""
    formatter = WordFormatter()
    return formatter.format(word)

def lookup_raw(word: str) -> Optional[Dict]:
    """外部调用接口：返回原始词条 dict（无 ANSI 格式化）"""
    formatter = WordFormatter()
    return formatter.lookup_raw(word)

def main():
    """命令行入口"""
    # 如果命令行提供了参数，使用第一个参数作为单词
    if len(sys.argv) >= 2:
        word = sys.argv[1]
    else:
        # 没有参数时，默认查询 tap
        word = "pattern"
        print(f"📖 查询单词: {word}\n")
        print("-" * 50)

    try:
        result = format_word(word)
        print(result)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"处理出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
# cd /home/bina/LaLe/tools/vocabulary
# python arrange_word.py assume

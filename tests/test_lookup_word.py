"""查词测试：从牛津词典中查询单词，看能否显示完整信息"""

import json,sys
from pathlib import Path
from typing import Dict,Optional

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 词典数据路径

DICT_PATH = PROJECT_ROOT / "data" /"output"/"oxford_dictionary" / "oxford_dictionary_full.json"

def load_dictionary()->Dict:
    """加载词典数据"""
    if not DICT_PATH.exists():
        print(f"❌ 词典文件不存在: {DICT_PATH}")
        return {}

    with open(DICT_PATH,'r',encoding='utf-8') as f:
        return json.load(f)


def lookup_word(word:str,dictionary:Dict)->Optional[Dict]:
    """查询单词"""
    # 先尝试精确匹配
    word_lower = word.lower()
    if word_lower in dictionary:
        return dictionary[word_lower]

    # 如果精确匹配失败，尝试大小写不敏感匹配
    for key,value in dictionary.items():
        if key.lower() == word_lower:
            return value

    return None

def print_sense(sense:Dict,index:int):
    """打印单个释义"""
    print(f"\n [{index}]")

    # 语法标注
    if sense.get("grammar"):
        print(f"语法: {sense['grammar']}")

    # 搭配模式
    if sense.get("pattern"):
        print(f"搭配: {sense['pattern']}")

    # 英英释义
    if sense.get("definition"):
        print(f"英英: {sense['definition']}")

    # 中文释义
    if sense.get("translation_rag"):
        print(f"中文: {sense['translation_rag']}")

    # 例句
    if sense.get("examples"):
        print(f"例句:")
        for ex in sense["examples"]:
            if ex.get("english") and ex.get("chinese"):
                print(f"- {ex['english']}")
                print(f"{ex['chinese']}")
            elif ex.get("english"):
                print(f"- {ex['english']}")
            elif ex.get("chinese"):
                print(f"- {ex['chinese']}")


def print_word_info(word:str,entry:Dict):
    """打印单词的完整信息"""
    print("\n" + "=" * 70)
    print(f"📖 单词: {word}")
    print("=" * 70)

    # 基本信息
    print(f"\n📌 基本信息:")
    if entry.get("headword"):
        print(f"  词头: {entry['headword']}")
    if entry.get("phonetic"):
        print(f"  音标: {entry['phonetic']}")
    if entry.get("phonetic_uk"):
        print(f"  英式: {entry['phonetic_uk']}")
    if entry.get("phonetic_us"):
        print(f"  美式: {entry['phonetic_us']}")
    if entry.get("cefr_level"):
        print(f"  CEFR: {entry['cefr_level']}")
    if entry.get("opal_level"):
        print(f"  OPAL: {entry['opal_level']}")

    # 词性
    if entry.get("pos"):
        print(f"  词性: {', '.join(entry['pos'])}")

    # 词形变化
    if entry.get("inflections"):
        print(f"\n📝 词形变化:")
        for key, value in entry['inflections'].items():
            print(f"  {key}: {value}")

    # 释义列表
    if entry.get("senses"):
        print(f"\n📚 释义 (共 {len(entry['senses'])} 条):")
        for i, sense in enumerate(entry['senses'], 1):
            print_sense(sense, i)
    else:
        print("\n⚠️ 该词条没有释义数据")

    # 习语
    if entry.get("idioms"):
        print(f"\n📖 习语 (共 {len(entry['idioms'])} 条):")
        for idiom in entry['idioms']:
            print(f" - {idiom.get('name', '')}")
            if idiom.get('definition'):
                print(f"{idiom['definition']}")

    # 统计信息
    total_examples = sum(len(s.get('examples', [])) for s in entry.get('senses', []))
    print(f"\n📊 统计: 释义 {len(entry.get('senses', []))} 条, 例句 {total_examples} 个")

    print("\n" + "=" * 70)

def main():
    # 1.加载词典
    print("📖 正在加载词典...")
    dictionary = load_dictionary()
    if not dictionary:
        return

    print(f"✅ 词典加载成功: {len(dictionary)} 个词条")

    # 2.查询单词
    words_to_test = ["train","flip"]

    for word in words_to_test:
        entry = lookup_word(word,dictionary)

        if entry is None:
            print(f"\n❌ 未找到单词: {word}")
            continue

        # 检查是否为跳转词条
        if entry.get("is_redirect"):
            print(f"\n🔄 跳转词条: {word} → {entry.get('redirect_target', '未知')}")
            # 尝试跳转
            target = entry.get("redirect_target")
            if target:
                target_entry = lookup_word(target, dictionary)
                if target_entry:
                    print_word_info(target, target_entry)
                else:
                    print(f"❌ 跳转目标未找到: {target}")
            continue

        print_word_info(word,entry)

if __name__ == "__main__":
    main()









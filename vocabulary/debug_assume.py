"""
调试 assume的原始HTML结构
"""

import json
import re
from readmdict import MDX

MDX_PATH = "/home/bina/LaLe/data/uploads/oxford_dictionary/oaldpe.mdx"


def inspect_assume():
    mdx = MDX(MDX_PATH)
    for key_bytes, value_bytes in mdx.items():
        key = key_bytes.decode('utf-8')
        if key == 'assume':
            value = value_bytes.decode('utf-8')
            print("=" * 70)
            print("📖 assume 的原始 HTML（仅第一个 sense 块）")
            print("=" * 70)

            # 提取第一个 sense 块
            sense_match = re.search(
                r'<li\s+[^>]*class\s*=\s*["\']sense["\'][^>]*>.*?</li>',
                value,
                re.DOTALL
            )
            if not sense_match:
                print("未找到 sense 块")
                return

            sense_block = sense_match.group(0)
            print("\n【sense_block 前500字符】")
            print(sense_block[:500])
            print("\n...")
            print("\n【查找 ul 标签】")
            ul_match = re.search(
                r'<ul\s+[^>]*class\s*=\s*["\']examples["\'][^>]*>',
                sense_block,
                re.DOTALL
            )
            if ul_match:
                print("找到 ul 标签，匹配内容：")
                print(ul_match.group(0))
                # 尝试提取完整 ul 内容
                ul_full = re.search(
                    r'<ul\s+[^>]*class\s*=\s*["\']examples["\'][^>]*>(.*?)</ul>',
                    sense_block,
                    re.DOTALL
                )
                if ul_full:
                    ul_content = ul_full.group(1)
                    print(f"ul 内容长度: {len(ul_content)} 字符")
                    print("ul 内容前200字符:")
                    print(ul_content[:200])
                else:
                    print("未能匹配到完整的 </ul>")
            else:
                print("未找到 ul 标签")

            break


if __name__ == "__main__":
    inspect_assume()

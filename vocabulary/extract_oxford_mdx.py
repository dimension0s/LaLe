"""牛津词典资源包.mdx文件提取器：从oaldpe.mdx中提取词条数据，保存为JSON格式"""
import json,re
from pathlib import Path
from typing import Dict,Optional,List,Any
from dataclasses import dataclass,field,asdict
from loguru import logger
from readmdict import MDX


@dataclass
class Sense:
    """一个释义"""
    number:str=""                      # 释义编号1,2,3...
    grammatical_label: str = ""        # 语法标注: [VN], [V-ing], [V wh-]
    pattern: str = ""                  # 搭配模式: ~ sb/sth (as) sth
    definition: str = ""               # 英英释义
    translation: str = ""              # 中文翻译
    examples: List[Dict] = field(default_factory=list)  # 例句列表

@dataclass
class Idiom:
    """习语"""
    name:str=""           # 习语名称
    definition: str = ""  # 释义
    example: str = ""     # 例句


@dataclass
class WordEntry:
    """单词词条数据结构"""
    word: str                                          # 单词
    headword:str=""                                    # 完整词头（含重音符号）
    phonetic: str = ""                                 # 音标
    phonetic_uk: str = ""                              # 英式音标
    phonetic_us: str = ""                              # 美式音标
    pos: List[str] = field(default_factory=list)       # 词性列表
    senses: List[Sense] = field(default_factory=list)  # ⭐ 核心：完整的释义列表
    idioms: List[Idiom] = field(default_factory=list)  # 习语/短语
    inflections: Dict = field(default_factory=dict)  # 词形变化
    cefr_level: str = ""  # A1-C2
    opal_level: str = ""  # OPAL学术词汇等级
    is_redirect: bool = False
    redirect_target: str = ""
    raw_html: str = ""  # 原始HTML（用于调试）


    def to_dict(self) -> Dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "word": self.word,
            "headword": self.headword,
            "phonetic": self.phonetic,
            "phonetic_uk": self.phonetic_uk,
            "phonetic_us": self.phonetic_us,
            "pos": self.pos,
            "senses": [asdict(s) for s in self.senses],
            "idioms": [asdict(i) for i in self.idioms],
            "inflections": self.inflections,
            "cefr_level": self.cefr_level,
            "opal_level": self.opal_level,
            "is_redirect": self.is_redirect,
            "redirect_target": self.redirect_target
        }

class OxfordMdxExtractor:
    """牛津词典.mda提取器，基于html结构设计提取逻辑"""
    def __init__(self,mdx_path:str,output_dir:str="./data/output/oxford_dictionary"):
        self.mdx_path = Path(mdx_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True,exist_ok=True)
        self.entries:Dict[str,WordEntry] = {}
        self.logger = logger

        # 统计信息
        self.stats = {
            "total_words": 0,
            "with_phonetic": 0,
            "with_examples": 0,
            "with_idioms": 0,
            "redirects": 0,
            "senses_total": 0,
            "examples_total": 0,
            "parse_errors": 0,
        }

    def extract(self)->Dict[str,WordEntry]:
        """执行提取"""
        self.logger.info(f"开始提取牛津词典：{self.mdx_path}")

        if not self.mdx_path.exists():
            self.logger.error(f"文件不存在：{self.mdx_path}")
            return {}

        try:
            mdx = MDX(str(self.mdx_path))

            # 遍历所有词条
            total = 0
            for key_bytes,value_bytes in mdx.items():
                total += 1
                if total%1000 == 0:  # 待解析
                    self.logger.info(f"已处理：{total}个词条")

                try:
                    # 词条解码
                    key = key_bytes.decode('utf-8')
                    value = value_bytes.decode('utf-8')

                    # 解析词条
                    entry = self._parse_entry(key,value)
                    if entry:
                        self.entries[key] = entry
                        self.stats["total_words"] +=1

                        if entry.is_redirect:
                            self.stats["redirects"] +=1
                        else:
                            if entry.phonetic or entry.phonetic_uk or entry.phonetic_us:
                                self.stats["with_phonetic"] += 1
                            if entry.senses:
                                self.stats["senses_total"] += len(entry.senses)
                            if any(s.examples for s in entry.senses):
                                self.stats["with_examples"] += 1
                            if entry.idioms:
                                self.stats["with_idioms"] += 1



                except UnicodeDecodeError:
                    self.logger.warning(f"解码失败 （key:{key_bytes[:50]})")
                    self.stats["parse_errors"] += 1
                except Exception as e:
                    self.logger.warning(f"解析失败 (key: {key_bytes[:50]}): {e}")
                    self.stats["parse_errors"] += 1

            self.logger.info(f"提取完成！")
            self.logger.info(f"总词条: {self.stats['total_words']}")
            self.logger.info(f"跳转词条: {self.stats['redirects']}")
            self.logger.info(f"总释义数: {self.stats['senses_total']}")
            self.logger.info(f"含例句词条: {self.stats['with_examples']}")
            self.logger.info(f"含习语词条: {self.stats['with_idioms']}")
            self.logger.info(f"含音标: {self.stats['with_phonetic']}")
            self.logger.info(f"解析错误: {self.stats['parse_errors']}")

            # 保存结果
            self._save_results()

            return self.entries

        except Exception as e:
            self.logger.error(f"提取失败: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _parse_entry(self,word:str,html:str)->Optional[WordEntry]:
        """解析词条中的html内容

        """
        try:
            # 检查是否是跳转链接
            if "@@@LINK=" in html:
                match = re.search(r'@@@LINK=([^\s\r\n]+)',html)
                if match:
                    target = match.group(1).strip()
                    entry = WordEntry(word=word, is_redirect=True, redirect_target=target)
                    entry.meanings = [{"meaning": f"→ {target}", "pos": "", "level": ""}]
                    return entry

            entry = WordEntry(word=word,raw_html=html[:500] if len(html) >500 else html)

            # 1.提取词头
            entry.headword = self._extract_headword(html)

            # 2.提取音标
            entry.phonetic = self._extract_phonetic(html)
            entry.phonetic_uk = self._extract_phonetic_uk(html)
            entry.phonetic_us = self._extract_phonetic_us(html)

            # 3.提取词性
            entry.pos = self._extract_pos(html)

            # 4.提取所有释义（核心）
            entry.senses = self._extract_all_senses(html)

            # 5.提取习语/短语
            entry.idioms = self._extract_idioms(html)

            # 6.提取词形变化
            entry.inflections = self._extract_inflections(html)

            # 7.提取CEFR等级
            entry.cefr_level = self._extract_cefr_level(html)

            return entry

        except Exception as e:
            self.logger.debug(f"⚠️解析词条失败: {word} - {e}")
            return None


    # -------------各字段提取方法-----------------
    def _extract_headword(self,html:str)->str:
        """提取词头（含重音符号）"""
        match = re.search(r'<h1[^>]*class="headword"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if match:
            return self._clean_text(match.group(1))
        return ""

    def _extract_phonetic(self,html:str)->str:
        """提取音标（通用）"""
        # 匹配 <span class="phon">/.../</span>
        match = re.search(r'<span[^>]*class="phon"[^>]*>(.*?)</span>',html,re.DOTALL)
        if match:
            text = self._clean_text(match.group(1))
            # 过滤掉包含 script 或 css 的误匹配
            if text and not any(key in text.lower() for key in ['script', 'css', 'jquery']):
                return text
        return ""



    def _extract_phonetic_uk(self,html:str)->str:
        """提取英式音标"""
        # 在 phons_br 中提取

        match = re.search(r'<div[^>]*class="phons_br"[^>]*>.*?<span[^>]*class="phon"[^>]*>(.*?)</span>', html,
                          re.DOTALL)
        if match:
            return self._clean_text(match.group(1))
        return ""

    def _extract_phonetic_us(self, html: str) -> str:
        """提取美式音标"""
        # 在 phons_n_am 中提取
        match = re.search(r'<div[^>]*class="phons_n_am"[^>]*>.*?<span[^>]*class="phon"[^>]*>(.*?)</span>', html,
                          re.DOTALL)
        if match:
            return self._clean_text(match.group(1))
        return ""

    def _extract_pos(self, html: str) -> List[str]:
        """提取词性"""
        pos_list = []

        # 匹配 <span class="pos">noun</span>
        matches = re.findall(r'<span[^>]*class="pos"[^>]*>(.*?)</span>', html, re.DOTALL)
        for match in matches:
            cleaned = self._clean_text(match)
            if cleaned and len(cleaned) < 20:
                if cleaned not in pos_list:
                    pos_list.append(cleaned)

        return pos_list

    def _extract_all_senses(self, html: str) -> List[Sense]:
        """提取所有释义（完整版） - 修复嵌套 li 问题"""
        senses = []
        # 使用正则找到每个 <li class="sense"> 的起始
        start_pattern = re.compile(r'<li\s+[^>]*class\s*=\s*["\']sense["\'][^>]*>', re.DOTALL)
        pos = 0
        while True:
            start_match = start_pattern.search(html, pos)
            if not start_match:
                break
            start_pos = start_match.end()
            # 手动查找匹配的 </li>（考虑嵌套）
            depth = 1
            i = start_pos
            while i < len(html) and depth > 0:
                next_open = html.find('<li', i)
                next_close = html.find('</li>', i)
                if next_close == -1:
                    break
                if next_open == -1 or next_close < next_open:
                    depth -= 1
                    i = next_close + 5
                    if depth == 0:
                        end_pos = next_close
                        break
                else:
                    # 检查是否是 <li 标签（非闭合）
                    # 简单起见，我们假设所有 <li 都是开始标签，但可能误判属性，但概率低
                    # 可以增加检查 <li 后面是否有空格或 >，但暂时这样
                    depth += 1
                    i = next_open + 4
            else:
                # 没有匹配，跳出
                break
            if depth == 0:
                block = html[start_pos:end_pos]
                # 处理这个 sense
                sense = Sense(number=str(len(senses) + 1))
                # 提取编号（sn）
                sn_match = re.search(
                    r'<span[^>]*class\s*=\s*["\']sn["\'][^>]*>(\d+)</span>',
                    block,
                    re.DOTALL
                )
                if sn_match:
                    sense.number = sn_match.group(1).strip()
                # 提取英英释义
                def_match = re.search(
                    r'<span[^>]*class\s*=\s*["\']def["\'][^>]*>(.*?)</span>',
                    block,
                    re.DOTALL
                )
                if def_match:
                    sense.definition = self._clean_text(def_match.group(1))
                # 提取中文释义
                deft_match = re.search(
                    r'<deft>.*?<chn\s+class\s*=\s*["\']simple["\'][^>]*>(.*?)</chn>.*?</deft>',
                    block,
                    re.DOTALL
                )
                if deft_match:
                    sense.translation = self._clean_text(deft_match.group(1))
                else:
                    trans_match = re.search(r'<deft>(.*?)</deft>', block, re.DOTALL)
                    if trans_match:
                        simple_match = re.search(
                            r'<chn\s+class\s*=\s*["\']simple["\'][^>]*>(.*?)</chn>',
                            trans_match.group(1),
                            re.DOTALL
                        )
                        if simple_match:
                            sense.translation = self._clean_text(simple_match.group(1))
                # 提取语法标注
                gram_match = re.search(
                    r'<span[^>]*class\s*=\s*["\']x["\'][^>]*>(\[.*?\])</span>',
                    block,
                    re.DOTALL
                )
                if gram_match:
                    sense.grammatical_label = self._clean_text(gram_match.group(1))
                # 提取例句（现在 block 包含完整 ul）
                sense.examples = self._extract_all_examples_from_sense(block)
                if sense.definition or sense.examples or sense.translation:
                    senses.append(sense)
            pos = start_match.start() + 1  # 继续下一个
        return senses

    def _extract_all_examples_from_sense(self, block: str) -> List[Dict]:
        """
        从释义块中提取所有例句（完整版）
        支持多种HTML结构
        """
        examples = []

        # ============================================================
        # 方法1：从 <ul class="examples"> 中提取所有例句
        # ============================================================
        ul_match = re.search(
            r'<ul\s+[^>]*class\s*=\s*["\']examples["\'][^>]*>(.*?)</ul>',
            block,
            re.DOTALL
        )

        if ul_match:
            ul_content = ul_match.group(1)
            li_items = re.findall(r'<li[^>]*>(.*?)</li>', ul_content, re.DOTALL)
            for li in li_items:
                full_text = self._clean_text(li)  # 使用现有的 _clean_text
                chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
                match = chinese_pattern.search(full_text)
                if match:
                    eng_text = full_text[:match.start()].strip()
                    # chn_text = full_text[match.start():].strip()
                else:
                    eng_text = full_text
                    # chn_text = ""
                chn_text = self._extract_simple_chinese(li)
                if eng_text:
                    examples.append({"english": eng_text, "chinese": chn_text})

        # ============================================================
        # 方法2：如果没有 ul，尝试匹配单独的 <p class="eg">
        # ============================================================
        if not examples:
            eg_blocks = re.findall(
                r'<p\s+[^>]*class\s*=\s*["\']eg["\'][^>]*>(.*?)</p>',
                block,
                re.DOTALL
            )

            for eg in eg_blocks:
                eng_match = re.search(
                    r'<span\s+[^>]*class\s*=\s*["\']x["\'][^>]*>(.*?)</span>',
                    eg,
                    re.DOTALL
                )
                if eng_match:
                    eng_text = self._clean_text(eng_match.group(1))
                    chn_text = self._extract_simple_chinese(eg)
                    if eng_text:
                        examples.append({
                            "english": eng_text,
                            "chinese": chn_text if chn_text else ""
                        })

        # ============================================================
        # 方法3：匹配 x + xt 结构（smooth 单词使用的格式）
        # ============================================================
        if not examples:
            # 匹配 <span class="x">...<xt>...</xt></span> 结构
            x_with_xt = re.findall(
                r'<span\s+[^>]*class\s*=\s*["\']x["\'][^>]*>(.*?)</span>',
                block,
                re.DOTALL
            )

            for item in x_with_xt:
                # 检查是否包含 xt 标签
                xt_match = re.search(
                    r'<xt>.*?<chn\s+class\s*=\s*["\']simple["\'][^>]*>(.*?)</chn>.*?</xt>',
                    item,
                    re.DOTALL
                )
                if xt_match:
                    # 有 xt 标签，英文在 x 中，中文在 xt 中
                    eng_text = self._clean_text(re.sub(r'<xt>.*?</xt>', '', item))
                    chn_text = self._clean_text(xt_match.group(1))
                    if eng_text:
                        examples.append({
                            "english": eng_text,
                            "chinese": chn_text if chn_text else ""
                        })
                else:
                    # 没有 xt 标签，尝试提取纯文本
                    cleaned = self._clean_text(item)
                    if cleaned and len(cleaned) > 3:
                        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in cleaned)
                        examples.append({
                            "english": cleaned if not has_chinese else "",
                            "chinese": cleaned if has_chinese else ""
                        })

        return examples

    def _extract_simple_chinese(self, text: str) -> str:
        """提取 simple 版本的中文翻译"""
        match = re.search(
            r'<chn\s+class\s*=\s*["\']simple["\'][^>]*>(.*?)</chn>',
            text,
            re.DOTALL
        )
        if match:
            return self._clean_text(match.group(1))

        # 如果找不到 simple，尝试匹配任何 chn
        match2 = re.search(
            r'<chn[^>]*>(.*?)</chn>',
            text,
            re.DOTALL
        )
        if match2:
            return self._clean_text(match2.group(1))

        return ""

    def _extract_full_x(self, text: str) -> str:
        """
        提取 <span class="x"> 内的完整内容，支持嵌套标签
        """
        # 查找 x 标签的起始位置
        start = re.search(r'<span\s+[^>]*class\s*=\s*["\']x["\'][^>]*>', text)
        if not start:
            return ""
        pos = start.end()
        depth = 1
        while pos < len(text) and depth > 0:
            # 查找下一个 <span 或 </span>
            next_open = text.find('<span', pos)
            next_close = text.find('</span>', pos)
            if next_close == -1:
                break
            if next_open == -1 or next_close < next_open:
                depth -= 1
                pos = next_close + 7
            else:
                depth += 1
                pos = next_open + 6
        if depth == 0:
            content = text[start.end():next_close]
            # 移除 xt 标签（中文翻译）
            content = re.sub(r'<xt>.*?</xt>', '', content, flags=re.DOTALL)
            # 移除所有HTML标签
            content = re.sub(r'<[^>]+>', '', content)
            return self._clean_text(content)
        return ""

    def _extract_x_content(self, text: str) -> str:
        """
        从文本中提取 <span class="x"> 内的完整内容，支持嵌套标签。
        返回去除所有 HTML 标签后的纯英文文本。
        """
        # 查找 <span class="x"> 的起始位置
        start_match = re.search(
            r'<span\s+[^>]*class\s*=\s*["\']x["\'][^>]*>',
            text
        )
        if not start_match:
            return ""

        start_pos = start_match.end()
        depth = 1
        pos = start_pos
        while pos < len(text) and depth > 0:
            # 找下一个 <span 或 </span>
            next_open = text.find('<span', pos)
            next_close = text.find('</span>', pos)

            if next_close == -1:
                break

            if next_open == -1 or next_close < next_open:
                depth -= 1
                pos = next_close + 7  # 跳过 </span>
                if depth == 0:
                    x_content = text[start_pos:next_close]
                    break
            else:
                depth += 1
                pos = next_open + 6  # 跳过 <span
        else:
            # 如果未找到匹配的闭合标签，回退到简单方法
            fallback = re.search(
                r'<span\s+[^>]*class\s*=\s*["\']x["\'][^>]*>(.*?)</span>',
                text,
                re.DOTALL
            )
            if fallback:
                x_content = fallback.group(1)
            else:
                return ""

        # 移除 xt 标签（中文翻译）及其他所有 HTML 标签，保留纯文本
        x_content = re.sub(r'<xt>.*?</xt>', '', x_content, flags=re.DOTALL)
        return self._clean_text(x_content)

    def _extract_complete_english_example(self, text: str) -> str:
        """
        提取完整的英文例句（处理被拆分的span标签）
        """
        # 方法1：尝试匹配 <span class="x"> 并提取完整内容
        # 使用非贪婪匹配，但允许内部包含其他span标签
        x_match = re.search(
            r'<span\s+[^>]*class\s*=\s*["\']x["\'][^>]*>(.*?)</span>',
            text,
            re.DOTALL
        )

        if x_match:
            # 获取x标签内的内容
            x_content = x_match.group(1)

            # 如果内容中包含 <span class="cl">，说明被拆分了
            if '<span class="cl"' in x_content or '<span class="cf"' in x_content:
                # 提取所有文本内容（包括子span中的文本）
                # 先移除所有HTML标签，保留文本
                clean_text = self._clean_text(x_content)

                # 检查是否包含xt标签（中文翻译），如果有则移除
                xt_match = re.search(r'<xt>.*?</xt>', x_content, re.DOTALL)
                if xt_match:
                    # 移除xt标签及其内容
                    x_content = re.sub(r'<xt>.*?</xt>', '', x_content, flags=re.DOTALL)
                    clean_text = self._clean_text(x_content)

                return clean_text
            else:
                # 简单情况，直接清理
                return self._clean_text(x_content)

        # 方法2：如果找不到x标签，尝试在li中直接查找
        # 提取li中的文本，但排除中文翻译标签
        # 移除所有 <xt> 标签及其内容
        text_without_xt = re.sub(r'<xt>.*?</xt>', '', text, flags=re.DOTALL)
        # 移除其他不需要的标签
        text_without_xt = re.sub(r'<example-audio[^>]*>.*?</example-audio>', '', text_without_xt, flags=re.DOTALL)
        # 清理并返回
        return self._clean_text(text_without_xt)

    def _extract_simple_chinese_from_deft(self, text: str) -> str:
        """提取 simple 版本的中文翻译"""
        match = re.search(
            r'<chn\s+class\s*=\s*["\']simple["\'][^>]*>(.*?)</chn>',
            text,
            re.DOTALL
        )
        if match:
            return self._clean_text(match.group(1))

        # 如果找不到 simple，尝试匹配任何 chn
        match2 = re.search(
            r'<chn[^>]*>(.*?)</chn>',
            text,
            re.DOTALL
        )
        if match2:
            return self._clean_text(match2.group(1))

        return ""

    def _extract_examples_from_block(self, block: str) -> List[Dict]:
        """从释义块中提取例句（兼容旧接口）"""
        return self._extract_all_examples_from_sense(block)

    def _parse_sense_content_with_context(self, def_content: str, preceding_text: str, number: str) -> Sense:
        """
        带上下文的释义解析（用于方法3）
        从定义标签周围提取语法标注和搭配
        """
        sense = Sense(number=number)

        # 1. 提取英英释义
        def_match = re.search(r'<span[^>]*class="def"[^>]*>(.*?)</span>', def_content, re.DOTALL)
        if def_match:
            sense.definition = self._clean_text(def_match.group(1))

        # 2. 从前面提取中文释义
        trans_match = re.search(r'<span[^>]*class="trans"[^>]*>(.*?)</span>', preceding_text, re.DOTALL)
        if trans_match:
            sense.translation = self._clean_text(trans_match.group(1))
        else:
            # 尝试在 def 之后找中文
            trans_match_after = re.search(r'<span[^>]*class="trans"[^>]*>(.*?)</span>', def_content, re.DOTALL)
            if trans_match_after:
                sense.translation = self._clean_text(trans_match_after.group(1))

        # 3. 提取语法标注 [VN], [V-ing] 等
        gram_match = re.search(r'<span[^>]*class="x"[^>]*>(\[.*?\])</span>', preceding_text, re.DOTALL)
        if not gram_match:
            gram_match = re.search(r'<span[^>]*class="gram"[^>]*>(.*?)</span>', preceding_text, re.DOTALL)
        if not gram_match:
            gram_match = re.search(r'(\[[A-Za-z\-]+\])', preceding_text)
        if gram_match:
            sense.grammatical_label = self._clean_text(gram_match.group(1))

        # 4. 提取搭配模式 (~ sb/sth (as) sth)
        pattern_match = re.search(r'<span[^>]*class="x"[^>]*>(~.*?)</span>', preceding_text, re.DOTALL)
        if pattern_match:
            pattern_text = self._clean_text(pattern_match.group(1))
            if pattern_text and pattern_text.startswith('~'):
                sense.pattern = pattern_text

        # 5. 提取例句
        # 方法3中的例句可能在 def 之前或之后
        ex_pattern = r'<span[^>]*class="x"[^>]*>(.*?)</span>\s*<span[^>]*class="trans-ex"[^>]*>(.*?)</span>'
        ex_matches = re.findall(ex_pattern, def_content + preceding_text, re.DOTALL)
        if not ex_matches:
            # 在更大的范围查找
            combined = preceding_text + def_content
            ex_matches = re.findall(ex_pattern, combined, re.DOTALL)

        for eng, chn in ex_matches[:5]:
            eng_clean = self._clean_text(eng)
            chn_clean = self._clean_text(chn)
            if eng_clean:
                sense.examples.append({
                    "english": eng_clean,
                    "chinese": chn_clean
                })

        return sense

    def _parse_sense_content(self, content: str, number: str, full_html: str = "") -> Sense:
        """
        解析单个释义的内容（简化版）
        实际上，现在由 _extract_all_senses 直接处理，这个方法主要作为备用
        """
        sense = Sense(number=number)

        if not content or len(content.strip()) < 3:
            return sense

        # 提取英英释义
        def_match = re.search(r'<span[^>]*class="[^"]*def[^"]*"[^>]*>(.*?)</span>', content, re.DOTALL)
        if def_match:
            sense.definition = self._clean_text(def_match.group(1))

        # 提取中文释义
        trans_match = re.search(r'<span[^>]*class="[^"]*trans[^"]*"[^>]*>(.*?)</span>', content, re.DOTALL)
        if trans_match:
            sense.translation = self._clean_text(trans_match.group(1))

        # 提取例句
        sense.examples = self._extract_examples_from_block(content)

        return sense

    def _extract_examples_from_region(self, region: str) -> List[Dict]:
        """
        从指定区域提取所有例句（增强版）
        使用更宽松的匹配方式
        """
        examples = []

        # ============================================================
        # 格式1：<p class="eg"> ... </p>
        # ============================================================
        eg_blocks = re.findall(r'<p[^>]*class="[^"]*eg[^"]*"[^>]*>(.*?)</p>', region, re.DOTALL)

        for block in eg_blocks:
            eng_match = re.search(r'<span[^>]*class="[^"]*x[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)
            chn_match = re.search(r'<span[^>]*class="[^"]*trans-ex[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)

            eng_clean = self._clean_text(eng_match.group(1)) if eng_match else ""
            chn_clean = self._clean_text(chn_match.group(1)) if chn_match else ""

            if eng_clean:
                examples.append({
                    "english": eng_clean,
                    "chinese": chn_clean if chn_clean else ""
                })

        # ============================================================
        # 格式2：<span class="x"> + <span class="trans-ex">
        # ============================================================
        if not examples:
            pattern = r'<span[^>]*class="[^"]*x[^"]*"[^>]*>(.*?)</span>\s*<span[^>]*class="[^"]*trans-ex[^"]*"[^>]*>(.*?)</span>'
            matches = re.findall(pattern, region, re.DOTALL)
            for eng, chn in matches:
                eng_clean = self._clean_text(eng)
                chn_clean = self._clean_text(chn)
                if eng_clean:
                    examples.append({
                        "english": eng_clean,
                        "chinese": chn_clean if chn_clean else ""
                    })

        # ============================================================
        # 格式3：单独的 <span class="x">
        # ============================================================
        if not examples:
            ex_only = re.findall(r'<span[^>]*class="[^"]*x[^"]*"[^>]*>(.*?)</span>', region, re.DOTALL)
            for ex in ex_only:
                cleaned = self._clean_text(ex)
                if cleaned and len(cleaned) > 3:
                    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in cleaned)
                    examples.append({
                        "english": cleaned if not has_chinese else "",
                        "chinese": cleaned if has_chinese else ""
                    })

        return examples

    def _extract_idioms(self, html: str) -> List[Idiom]:
        """提取习语/短语，只保留英文名称，去除中文"""
        idioms = []
        # 查找习语区域：<span class="idm">...<span class="x">名称</span>...<span class="def">释义</span></span>
        idiom_matches = re.findall(
            r'<span[^>]*class="idm"[^>]*>.*?<span[^>]*class="x"[^>]*>(.*?)</span>.*?<span[^>]*class="def"[^>]*>(.*?)</span>.*?</span>',
            html,
            re.DOTALL
        )
        for name, definition in idiom_matches:
            name_clean = self._clean_text(name)
            # 去除中文部分（只保留英文）
            chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
            match = chinese_pattern.search(name_clean)
            if match:
                name_clean = name_clean[:match.start()].strip()
            def_clean = self._clean_text(definition)
            if name_clean:
                idioms.append(Idiom(
                    name=name_clean,
                    definition=def_clean
                ))
        return idioms

    def _extract_inflections(self, html: str) -> Dict:
        """提取词形变化"""
        inflections = {}

        # 匹配 <span class="inflected_form">...</span>
        matches = re.findall(r'<span[^>]*class="inflected_form"[^>]*>(.*?)</span>', html, re.DOTALL)

        for match in matches:
            cleaned = self._clean_text(match)
            if cleaned:
                # 尝试推断类型
                if 'past' in cleaned.lower():
                    inflections['past'] = cleaned
                elif 'participle' in cleaned.lower():
                    inflections['past_participle'] = cleaned
                elif 'plural' in cleaned.lower():
                    inflections['plural'] = cleaned
                else:
                    # 保存为通用格式
                    key = f"form_{len(inflections) + 1}"
                    inflections[key] = cleaned
        return inflections

    def _extract_cefr_level(self, html: str) -> str:
        """提取CEFR等级"""
        # 匹配 <span class="ox3ksym_a1"> 等
        level_map = {
            'a1': 'A1',
            'a2': 'A2',
            'b1': 'B1',
            'b2': 'B2',
            'c1': 'C1',
            'c2': 'C2'
        }

        for code, level in level_map.items():
            if f'ox3ksym_{code}' in html:
                return level

        return ""

# ----------------工具方法-----------------------

    def _clean_text(self, text: str) -> str:
        """清理HTML标签和多余空白"""
        if not text:
            return ""

        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 保留常见的HTML实体（如 &amp; 转为 &）
        # text = re.sub(r'&amp;', '&', text)
        # text = re.sub(r'&lt;', '<', text)
        # text = re.sub(r'&gt;', '>', text)
        # text = re.sub(r'&quot;', '"', text)
        # # 移除其他HTML实体
        # text = re.sub(r'&[a-zA-Z]+;', '', text)
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 新加：移除控制字符（保留常见的空白符：\t, \n, \r, \x0b, \x0c 等会被 \s+ 处理，但为了安全移除所有非打印字符）
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # 压缩空白（包括换行、制表符等为单个空格）
        text = re.sub(r'\s+', ' ', text)
        # 移除首尾空白
        text = text.strip()

        return text

    def _is_valid_phonetic(self, text: str) -> bool:
        """检查是否是有效的音标文本"""
        if not text:
            return False
        # 音标通常较短，包含特殊字符
        if len(text) > 50:
            return False
        # 排除包含脚本或CSS关键词的文本
        invalid_keywords = ['script', 'css', 'jquery', '.js', 'http', 'html', 'div']
        for keyword in invalid_keywords:
            if keyword in text.lower():
                return False
        return True

    def _save_results(self):
        """保存结果"""
        full_data = {}
        for word, entry in self.entries.items():
            full_data[word] = entry.to_dict()

        full_path = self.output_dir / 'oxford_dictionary_full.json'
        self._save_json(full_path, full_data)
        self.logger.info(f"📝 完整数据: {full_path}")



        # 3. 保存统计
        stats_path = self.output_dir / 'extraction_stats.json'
        self._save_json(stats_path, self.stats)
        self.logger.info(f"📝 统计信息: {stats_path}")

    def _save_json(self, path: Path, data: Any):
        try:
            # 先序列化为字符串
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            # 验证是否可以正确解析回来（确保格式合法）
            json.loads(json_str)
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                # json.dump(data, f, ensure_ascii=False, indent=2)
                f.write(json_str)
        except Exception as e:
            self.logger.error(f"❌ 保存失败: {path} - {e}")
            raise


# 主函数
def main():
    """主函数"""
    # 配置路径
    MDX_PATH = "/home/bina/LaLe/data/uploads/oxford_dictionary/oaldpe.mdx"  # 替换为你的实际路径
    OUTPUT_DIR = "/home/bina/LaLe/data/output/oxford_dictionary"

    print("\n" + "-" * 60)
    print("📖 牛津词典 .mdx提取器")
    print("-" * 60)

    # 检查文件是否存在
    mdx_file = Path(MDX_PATH)
    if not mdx_file.exists():
        print(f"文件不存在: {MDX_PATH}")
        print("请将MDX_PATH变量设置为正确的文件路径")
        return

    # 创建提取器并执行
    extractor = OxfordMdxExtractor(MDX_PATH,OUTPUT_DIR)
    entries = extractor.extract()

    print("\n" + "-"*60)
    print(f"✅ 提取完成! 共 {len(entries)} 个词条")
    print(f"📂 输出目录: {OUTPUT_DIR}")
    print("-" * 60)

if __name__ == "__main__":
    main()








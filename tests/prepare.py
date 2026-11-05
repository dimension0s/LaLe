def _extract_idioms(self, html: str) -> List[Idiom]:
    """提取习语/短语"""
    idioms = []

    # 查找习语区域：<span class="idm">...<span class="x">名称</span>...<span class="def">释义</span></span>
    idiom_matches = re.findall(
        r'<span[^>]*class="idm"[^>]*>.*?<span[^>]*class="x"[^>]*>(.*?)</span>.*?<span[^>]*class="def"[^>]*>(.*?)</span>.*?</span>',
        html,
        re.DOTALL
    )

    for name, definition in idiom_matches:
        name_clean = self._clean_text(name)
        def_clean = self._clean_text(definition)
        if name_clean:
            idioms.append(Idiom(
                name=name_clean,
                definition=def_clean
            ))

    return idioms
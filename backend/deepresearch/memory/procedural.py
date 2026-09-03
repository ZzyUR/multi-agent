"""Procedural Memory — 研究策略与引用规范（配置 + Skills）。

内容：
  - 搜索策略模板
  - 引用格式规范
  - 研究质量检查清单

生命周期：跨所有 run（全局配置，不随 run 改变）。
"""

from __future__ import annotations

SEARCH_STRATEGIES = [
    "先搜索宏观背景（行业/领域概述），再深入具体细节",
    "中英文双语搜索同一话题，互为补充",
    "对核心来源使用 fetch_page 获取完整内容",
    "注意辨别信息时效性（优先选近 2 年的资料）",
]

CITATION_RULES = [
    "每条关键论断必须有 [n] 来源引用",
    "来源列表格式：[n] 标题 — URL",
    "不能确认的信息不写入报告，或标注 [未经验证]",
]

REPORT_QUALITY_CHECKLIST = [
    "执行摘要 ≥ 3 句，覆盖核心结论",
    "主要发现分章节，每章有小标题",
    "来源数量 ≥ 3",
    "无无来源断言",
]


class ProceduralMemory:
    """静态研究规程，供 Agent prompt 引用。"""

    def get_search_guide(self) -> str:
        items = "\n".join(f"- {s}" for s in SEARCH_STRATEGIES)
        return f"## 搜索策略\n{items}"

    def get_citation_guide(self) -> str:
        items = "\n".join(f"- {r}" for r in CITATION_RULES)
        return f"## 引用规范\n{items}"

    def get_quality_checklist(self) -> str:
        items = "\n".join(f"- [ ] {c}" for c in REPORT_QUALITY_CHECKLIST)
        return f"## 报告质量清单\n{items}"

    def get_full_guide(self) -> str:
        return "\n\n".join([
            self.get_search_guide(),
            self.get_citation_guide(),
            self.get_quality_checklist(),
        ])

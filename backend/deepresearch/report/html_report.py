"""HTML research-report template engine.

The LLM (SYNTHESIZE stage) outputs a structured JSON object describing the
report. This module renders that JSON into a complete, self-contained HTML
report with ECharts data visualizations — the rendering code is FIXED so the
LLM can never break it; it only supplies data.

Data contract: see REPORT_JSON_SYSTEM (the system prompt given to the model).
"""

from __future__ import annotations

import html as _html
import json
import re
from datetime import datetime
from typing import Any

# ── Styles (copied verbatim from the provided template) ─────────────────────────

_STYLE = """<style>
  :root{
    --ink:#0f1d2e; --navy:#16447a; --navy-2:#2e6fb8; --steel:#5b7185;
    --muted:#8a97a6; --paper:#ffffff; --panel:#f4f7fa; --card:#ffffff;
    --line:#e1e8ef; --grid:#eef2f6; --pos:#1f7a6d; --warn:#c08a2d;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:var(--paper);color:var(--ink);
    font-family:"PingFang SC","Noto Sans SC",-apple-system,"Segoe UI",sans-serif;
    line-height:1.75;-webkit-font-smoothing:antialiased;}
  .wrap{max-width:1080px;margin:0 auto;padding:0 28px}
  .mono{font-family:"SF Mono",ui-monospace,"Cascadia Code",Menlo,monospace}
  .cover{padding:60px 0 38px;border-bottom:3px solid var(--navy)}
  .badge-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:26px}
  .badge{font-size:12px;letter-spacing:.4px;padding:5px 12px;border:1px solid var(--line);
    border-radius:3px;background:var(--card);color:var(--steel);font-family:"SF Mono",monospace}
  .badge.live{border-color:var(--navy);color:var(--navy)}
  .badge b{color:var(--ink)}
  .eyebrow{font-size:13px;letter-spacing:3px;color:var(--navy-2);text-transform:uppercase;margin-bottom:14px;font-family:"SF Mono",monospace}
  h1.title{font-size:44px;line-height:1.16;font-weight:800;letter-spacing:-1px;margin-bottom:18px;color:var(--ink)}
  .subtitle{font-size:17px;color:var(--steel);max-width:780px}
  .dash{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);
    border:1px solid var(--line);border-radius:4px;overflow:hidden;margin:38px 0 4px}
  .stat{background:var(--card);padding:24px 20px}
  .stat .num{font-size:36px;font-weight:800;letter-spacing:-1px;line-height:1;
    font-family:"SF Mono",ui-monospace,monospace;color:var(--navy)}
  .stat .num.pos{color:var(--pos)} .stat .num.warn{color:var(--warn)}
  .stat .num u{font-size:18px;text-decoration:none;margin-left:1px}
  .stat .lbl{font-size:13px;color:var(--steel);margin-top:10px;line-height:1.5}
  .stat .cite{font-size:11px;color:var(--muted);margin-top:6px;font-family:"SF Mono",monospace}
  section{padding:46px 0;border-bottom:1px solid var(--line)}
  .sec-no{font-family:"SF Mono",monospace;font-size:13px;color:var(--navy-2);letter-spacing:2px}
  h2{font-size:29px;font-weight:800;letter-spacing:-.5px;margin:8px 0 20px;color:var(--ink)}
  h3{font-size:19px;font-weight:700;margin:28px 0 12px}
  p{margin-bottom:15px;font-size:16px;color:#28323f}
  .lead{font-size:17.5px;color:#1c2733}
  .cite-tag{font-family:"SF Mono",monospace;font-size:11px;color:var(--navy-2);vertical-align:super;margin-left:1px}
  .chart-card{background:var(--card);border:1px solid var(--line);border-radius:5px;padding:22px;margin:24px 0;box-shadow:0 1px 3px rgba(15,29,46,.04)}
  .chart-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;border-bottom:1px solid var(--grid);padding-bottom:12px}
  .chart-title{font-weight:700;font-size:16px;color:var(--ink)}
  .chart-tag{font-family:"SF Mono",monospace;font-size:11px;color:var(--muted)}
  .chart{width:100%;height:340px}
  .chart.tall{height:420px}
  .chart-note{font-size:13px;color:var(--steel);margin-top:10px;border-top:1px dashed var(--grid);padding-top:10px}
  table{width:100%;border-collapse:collapse;margin:22px 0;font-size:14.5px;background:var(--card);border:1px solid var(--line);border-radius:5px;overflow:hidden}
  th{background:var(--navy);color:#fff;text-align:left;padding:13px 14px;font-weight:600;font-size:13.5px}
  td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top;color:#28323f}
  tr:nth-child(even) td{background:var(--panel)}
  tr:last-child td{border-bottom:none}
  .tag-v{display:inline-block;font-size:11px;padding:2px 8px;border-radius:3px;background:#e7eef6;color:var(--navy);font-family:monospace;margin:1px}
  .tag-r{background:#f6ede0;color:var(--warn)}
  .concl{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:24px 0}
  .concl .c{background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--navy);padding:20px;border-radius:4px}
  .concl .c .k{font-family:monospace;font-size:12px;color:var(--navy-2);margin-bottom:8px;letter-spacing:1px}
  .concl .c .t{font-size:15px;line-height:1.6;color:#28323f}
  .callout{border-left:4px solid var(--navy);background:var(--panel);padding:18px 22px;margin:24px 0;border-radius:0 4px 4px 0}
  .callout.insight{border-left-color:var(--pos)}
  .callout.warning{border-left-color:var(--warn);background:#fbf6ec}
  .callout .ck{font-family:"SF Mono",monospace;font-size:12px;letter-spacing:1.5px;margin-bottom:7px;color:var(--navy-2);text-transform:uppercase}
  .callout.insight .ck{color:var(--pos)} .callout.warning .ck{color:var(--warn)}
  .callout .ctitle{font-weight:700;font-size:16px;color:var(--ink);margin-bottom:5px}
  .callout .ct{font-size:15.5px;color:#28323f}
  .sources{padding:38px 0 76px}
  .sources ol{list-style:none;counter-reset:s;margin-top:8px}
  .sources li{counter-increment:s;font-size:13px;color:var(--steel);padding:9px 0 9px 38px;position:relative;border-bottom:1px solid var(--grid)}
  .sources li::before{content:"["counter(s)"]";position:absolute;left:0;font-family:monospace;color:var(--navy-2)}
  .sources a{color:var(--navy-2);text-decoration:none;word-break:break-all}
  .sources a:hover{text-decoration:underline}
  .foot{text-align:center;color:var(--muted);font-size:12px;padding:28px 0;font-family:"SF Mono",monospace;border-top:1px solid var(--line)}
  @media(max-width:860px){
    .dash{grid-template-columns:repeat(2,1fr)}
    .concl{grid-template-columns:1fr}
    h1.title{font-size:32px}h2{font-size:23px}
  }
  @media print{.chart-card,table,.stat{break-inside:avoid}body{font-size:12pt}}
</style>"""

# ── ECharts render engine (fixed — data injected separately) ────────────────────

_RENDER_JS = """<script>
const C = { ink:'#0f1d2e', navy:'#16447a', navy2:'#2e6fb8', steel:'#5b7185',
            muted:'#8a97a6', grid:'#eef2f6', pos:'#1f7a6d', warn:'#c08a2d' };
const PALETTE = [C.navy, C.navy2, C.pos, C.warn, C.steel];
const FONT = '"PingFang SC","Noto Sans SC",sans-serif';
const AX = {
  axisLine:{lineStyle:{color:'#c4d0dd'}},
  axisLabel:{color:C.steel,fontFamily:FONT},
  splitLine:{lineStyle:{color:C.grid}}
};
const fmtUnit = u => u ? ('{value}'+u) : '{value}';
function renderChart(cfg){
  const el = document.getElementById(cfg.id);
  if(!el || !cfg.series) return;
  const ch = echarts.init(el);
  const lbl = {show:true,fontFamily:FONT,fontWeight:'bold',color:C.ink};
  const ml = cfg.markLine ? {markLine:{silent:true,data:[{yAxis:cfg.markLine.value}],
      lineStyle:{color:C.warn,type:'dashed'},
      label:{formatter:cfg.markLine.label,color:C.warn,fontFamily:FONT}}} : {};
  let opt;
  if(cfg.type==='bar'){
    opt={grid:{left:55,right:30,top:30,bottom:42},tooltip:{trigger:'axis'},legend:cfg.series.length>1?{top:0,textStyle:{fontFamily:FONT}}:undefined,
      xAxis:{type:'category',data:cfg.categories,...AX},
      yAxis:{type:'value',...AX,axisLabel:{...AX.axisLabel,formatter:fmtUnit(cfg.unit)}},
      series:cfg.series.map((s,i)=>({type:'bar',name:s.name,barWidth:cfg.series.length>1?'34%':'48%',
        data:s.data,itemStyle:{color:PALETTE[i%PALETTE.length]},
        label:{...lbl,position:'top',formatter:'{c}'+(cfg.unit||'')},...ml}))};
  }
  else if(cfg.type==='bar_h'){
    opt={grid:{left:140,right:46,top:20,bottom:30},tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
      xAxis:{type:'value',...AX,axisLabel:{...AX.axisLabel,formatter:fmtUnit(cfg.unit)}},
      yAxis:{type:'category',data:cfg.categories,...AX,splitLine:{show:false}},
      series:cfg.series.map((s,i)=>({type:'bar',name:s.name,barWidth:'58%',
        data:s.data,itemStyle:{color:PALETTE[i%PALETTE.length]},
        label:{...lbl,position:'right',formatter:'{c}'+(cfg.unit||'')}}))};
  }
  else if(cfg.type==='line'){
    opt={grid:{left:55,right:30,top:30,bottom:42},tooltip:{trigger:'axis'},legend:cfg.series.length>1?{top:0,textStyle:{fontFamily:FONT}}:undefined,
      xAxis:{type:'category',data:cfg.categories,boundaryGap:false,...AX},
      yAxis:{type:'value',...AX,axisLabel:{...AX.axisLabel,formatter:fmtUnit(cfg.unit)}},
      series:cfg.series.map((s,i)=>({type:'line',name:s.name,data:s.data,smooth:true,
        symbolSize:8,lineStyle:{color:PALETTE[i%PALETTE.length],width:2.5},
        itemStyle:{color:PALETTE[i%PALETTE.length]},
        areaStyle:cfg.series.length>1?undefined:{color:PALETTE[i%PALETTE.length],opacity:.08}}))};
  }
  else if(cfg.type==='line_bar'){
    opt={grid:{left:55,right:30,top:30,bottom:42},tooltip:{trigger:'axis'},
      xAxis:{type:'category',data:cfg.categories,...AX},
      yAxis:{type:'value',...AX,axisLabel:{...AX.axisLabel,formatter:fmtUnit(cfg.unit)}},
      series:[
        {type:'bar',name:cfg.series[0].name,barWidth:'46%',data:cfg.series[0].data,
          itemStyle:{color:C.navy},label:{...lbl,position:'top',formatter:'{c}'+(cfg.unit||'')}},
        {type:'line',name:cfg.series[0].name,data:cfg.series[0].data,smooth:true,
          symbolSize:8,lineStyle:{color:C.ink,width:2},itemStyle:{color:C.ink}}
      ]};
  }
  if(opt){ ch.setOption(opt); window.addEventListener('resize',()=>ch.resize()); }
}
function renderQuadrant(s){
  const el = document.getElementById(s.id);
  if(!el || !s || !s.points) return;
  const ch = echarts.init(el);
  ch.setOption({
    grid:{left:70,right:50,top:40,bottom:60},
    tooltip:{formatter:p=>`${p.data[3]}<br/>${(s.xName||'').replace(' →','')}: ${p.data[0]} · ${(s.yName||'').replace(' →','')}: ${p.data[1]}`},
    xAxis:{name:s.xName,nameLocation:'middle',nameGap:35,min:0,max:100,...AX,nameTextStyle:{fontFamily:FONT,color:C.ink}},
    yAxis:{name:s.yName,nameLocation:'middle',nameGap:45,min:0,max:100,...AX,nameTextStyle:{fontFamily:FONT,color:C.ink}},
    series:[{type:'scatter',symbolSize:v=>Math.sqrt(v[2])*9,
      data:s.points,
      itemStyle:{opacity:.78,color:C.navy2},
      label:{show:true,formatter:p=>p.data[3],position:'top',fontFamily:FONT,fontSize:11,color:C.ink},
      markLine:{silent:true,symbol:'none',lineStyle:{color:'#cdd7e1',type:'dashed'},
        data:[{xAxis:50},{yAxis:50}],label:{show:false}}
    }]
  });
  window.addEventListener('resize',()=>ch.resize());
}
(REPORT_DATA.charts||[]).forEach(renderChart);
(REPORT_DATA.quadrants||[]).forEach(renderQuadrant);
</script>"""


# ── LLM data contract (system prompt) ───────────────────────────────────────────

REPORT_JSON_SYSTEM = """\
你是一位资深研究分析师。基于多个子研究团队收集的完整材料，输出一份用于渲染**数据可视化 HTML 研报**的结构化 JSON。

研究问题：{question}

各子研究团队的完整研究材料：
{summaries}

# 核心理念：按内容自由编排，不要套固定模板
报告正文是一个 **blocks 有序数组**——你像搭积木一样，**根据本主题真实拥有的材料，自主决定用哪些块、各用几个、以什么顺序排列**。
不同主题应当长得不一样：数据多的主题多放图表，争议大的放风险提示框，有演进过程的放时间线式叙述。
**严禁机械套用"摘要→4 段→象限图→3 结论"的老套路。** 让结构服务于内容。

# 可用的块类型（按需选用、可重复、可省略）
- kpi       —— 顶部关键数字看板。{{"type":"kpi","items":[{{"value":"380","unit":"亿","label":"2025融资额·同比4倍","cite":"来源 [4]","class":"pos"}}]}}。items 取 2~4 个**真实数字**，没有就不放这个块。class: "pos"青绿/"warn"琥珀/""深蓝。
- prose     —— 叙述段落（报告的主干）。{{"type":"prose","tag_en":"UPSTREAM","heading":"区块标题","lead":"可选的导语句","paragraphs":["段落1含[n]引用","段落2"]}}。heading 为空则不显示标题。
- chart     —— 图表。{{"type":"chart","title":"图表标题","source":"数据来源 [1][6]","note":"注解","chart_type":"bar","categories":["A","B"],"series":[{{"name":"指标","data":[10,20]}}],"unit":"%","markLine":{{"value":10,"label":"阈值"}}}}。chart_type: "bar"竖柱/"bar_h"横条(排名)/"line"趋势/"line_bar"柱+线。markLine 可省。多指标放多个 series。
- table     —— 对比表。{{"type":"table","title":"可选标题","source":"[2]","headers":["列1","列2"],"rows":[["a","b"]]}}。
- callout   —— 高亮框，用于强调洞察或风险。{{"type":"callout","kind":"insight","title":"可选标题","text":"正文含[n]引用"}}。kind: "insight"洞察(青绿)/"warning"风险提示(琥珀)/"note"备注。
- quadrant  —— 2×2 象限散点图（仅当确有两个可对比维度时才用，**不是必需**）。{{"type":"quadrant","heading":"综合研判","title":"象限图标题","note":"注解","xName":"技术成熟度 →","yName":"制度适配度 →","points":[[25,30,20,"标签A"],[70,25,15,"标签B"]]}}。points: [x(0-100),y(0-100),气泡大小,"标签"]。
- conclusions —— 结论卡片组。{{"type":"conclusions","heading":"结论与建议","items":["结论1 ≤60字结论先行","结论2"]}}。items 数量自定。

# 严格要求
1. 只返回一个紧凑 JSON 对象（不缩进美化），不要任何额外文字或代码块标记。
2. 所有数字、论断必须来自上述材料；正文用 [n] 标注来源编号（n 对应 sources 下标+1）。严禁编造。来源 URL 必须是材料中真实出现的链接，**绝对禁止 example.com 等占位域名**。
3. 正文用纯文本（可含 [n]），不要写 HTML 标签。
4. 图表/象限 data 数组**只能放真实数字**，**绝对禁止 XXX、YY%、N/A 等占位符或文字**（会破坏 JSON）。没有可靠数字的维度就别配图，改用 prose 或 callout。
5. 内容要充实有深度：有数据、有分析、有洞察；总篇幅约 1200~1800 字。但**务必输出完整 JSON（所有括号闭合），不要写到一半截断**——宁可少放一个块，也要收尾完整。
6. 典型一份报告含 5~9 个块。开头通常是 kpi + 一个概述性 prose，中间按维度穿插 prose/chart/table/callout，结尾用 conclusions。但这只是参考，**最终由内容决定**。

JSON 结构：
{{
  "title": "报告标题",
  "topic_en": "英文副标，如 Embodied Intelligence · Industry Map",
  "subtitle": "一句话概述，≤80字",
  "blocks": [ {{"type":"kpi","items":[...]}}, {{"type":"prose","heading":"执行摘要","paragraphs":[...]}}, ... ],
  "sources": [{{"title":"来源标题","url":"https://完整url"}}]
}}\
"""


# ── Helpers ─────────────────────────────────────────────────────────────────────

_CITE_RE = re.compile(r"\[(\d+)\]")
_PROFILE_CN = {"fast": "快速", "standard": "标准", "deep": "深度"}


def _esc(text: Any) -> str:
    return _html.escape(str(text if text is not None else ""))


def _cite(text: Any) -> str:
    """Escape text, then turn [n] markers into cite-tag superscript spans."""
    safe = _esc(text)
    return _CITE_RE.sub(r'<span class="cite-tag">[\1]</span>', safe)


def _kpi_html(items: list[dict]) -> str:
    """Render a KPI dashboard block. Column count adapts to the number of
    items (2-4) — no padding with empty cells."""
    items = [k for k in (items or []) if isinstance(k, dict)][:4]
    if not items:
        return ""
    cells = []
    for k in items:
        cls = _esc(k.get("class", "")).strip()
        cells.append(
            f'<div class="stat"><div class="num {cls}">{_esc(k.get("value",""))}'
            f'<u>{_esc(k.get("unit",""))}</u></div>'
            f'<div class="lbl">{_esc(k.get("label",""))}</div>'
            f'<div class="cite">{_esc(k.get("cite",""))}</div></div>'
        )
    cols = min(max(len(cells), 1), 4)
    return (
        f'<div class="dash" style="grid-template-columns:repeat({cols},1fr)">'
        + "\n".join(cells)
        + "</div>"
    )


def _table_html(table: dict | None) -> str:
    if not table or not table.get("headers"):
        return ""
    title = table.get("title", "")
    cap = ""
    if title and str(title).strip():
        cap = (
            '<div class="chart-head" style="margin:18px 0 0">'
            f'<span class="chart-title">{_esc(title)}</span>'
            f'<span class="chart-tag">{_esc(table.get("source",""))}</span></div>'
        )
    headers = "".join(f"<th>{_esc(h)}</th>" for h in table["headers"])
    rows = ""
    for row in table.get("rows", []) or []:
        cells = "".join(f"<td>{_cite(c)}</td>" for c in row)
        rows += f"<tr>{cells}</tr>"
    return f"{cap}<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"


def _chart_card_html(chart: dict | None, chart_id: str) -> str:
    if not chart or not chart.get("series"):
        return ""
    return (
        '<div class="chart-card"><div class="chart-head">'
        f'<span class="chart-title">{_esc(chart.get("title",""))}</span>'
        f'<span class="chart-tag">{_esc(chart.get("source",""))}</span></div>'
        f'<div id="{chart_id}" class="chart"></div>'
        f'<div class="chart-note">{_esc(chart.get("note",""))}</div></div>'
    )


def _prose_html(b: dict, sec_no: int) -> str:
    head = _esc(b.get("heading", ""))
    sec_label = ""
    h2 = ""
    if head:
        tag = _esc(b.get("tag_en", "")) or "FINDING"
        sec_label = f'<div class="sec-no">{sec_no:02d} / {tag}</div>'
        h2 = f"<h2>{head}</h2>"
    lead = b.get("lead", "")
    lead_html = f'<p class="lead">{_cite(lead)}</p>' if lead and str(lead).strip() else ""
    paras = "".join(
        f"<p>{_cite(p)}</p>" for p in (b.get("paragraphs") or []) if str(p).strip()
    )
    return f"<section>{sec_label}{h2}{lead_html}{paras}</section>"


def _callout_html(b: dict) -> str:
    kind = _esc(b.get("kind", "note")).strip() or "note"
    if kind not in ("insight", "warning", "note"):
        kind = "note"
    label = {"insight": "核心洞察", "warning": "风险提示", "note": "备注"}[kind]
    title = b.get("title", "")
    title_html = f'<div class="ctitle">{_cite(title)}</div>' if title and str(title).strip() else ""
    return (
        f'<div class="callout {kind}"><div class="ck">{label}</div>'
        f'{title_html}<div class="ct">{_cite(b.get("text",""))}</div></div>'
    )


def _quadrant_html(b: dict, sec_no: int, quad_id: str) -> str:
    intro = b.get("intro", "")
    intro_html = f"<p>{_cite(intro)}</p>" if intro and str(intro).strip() else ""
    return (
        "<section>"
        f'<div class="sec-no">{sec_no:02d} / SYNTHESIS</div>'
        f'<h2>{_esc(b.get("heading") or "综合研判")}</h2>'
        f"{intro_html}"
        '<div class="chart-card"><div class="chart-head">'
        f'<span class="chart-title">{_esc(b.get("title","综合研判象限图"))}</span>'
        '<span class="chart-tag">DeepResearch 综合研判</span></div>'
        f'<div id="{quad_id}" class="chart tall"></div>'
        f'<div class="chart-note">{_esc(b.get("note",""))}</div></div>'
        "</section>"
    )


def _conclusions_html(b: dict, sec_no: int) -> str:
    items = [str(x) for x in (b.get("items") or []) if str(x).strip()]
    if not items:
        return ""
    cards = "".join(
        f'<div class="c"><div class="k">结论 {i+1:02d}</div><div class="t">{_cite(it)}</div></div>'
        for i, it in enumerate(items)
    )
    cols = min(max(len(items), 1), 3)
    return (
        "<section>"
        f'<div class="sec-no">{sec_no:02d} / CONCLUSIONS</div>'
        f'<h2>{_esc(b.get("heading","结论与建议"))}</h2>'
        f'<div class="concl" style="grid-template-columns:repeat({cols},1fr)">{cards}</div>'
        "</section>"
    )


def _render_blocks(blocks: list[dict]) -> tuple[str, list[dict], list[dict]]:
    """Dispatch each typed block to its renderer.

    Returns (body_html, chart_configs, quadrant_configs). Numbered sections
    (prose with heading / quadrant / conclusions) get a running 2-digit index;
    supporting blocks (kpi / chart / table / callout) flow inline."""
    html_parts: list[str] = []
    charts: list[dict] = []
    quadrants: list[dict] = []
    sec_no = 0
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        btype = b.get("type")
        if btype == "kpi":
            html_parts.append(_kpi_html(b.get("items")))
        elif btype == "prose":
            if b.get("heading"):
                sec_no += 1
            html_parts.append(_prose_html(b, sec_no))
        elif btype == "chart":
            if b.get("series"):
                cid = f"chart-{len(charts)}"
                charts.append({
                    "id": cid, "type": b.get("chart_type", "bar"),
                    "categories": b.get("categories"), "series": b.get("series"),
                    "unit": b.get("unit"), "markLine": b.get("markLine"),
                })
                html_parts.append(_chart_card_html(b, cid))
        elif btype == "table":
            html_parts.append(_table_html(b))
        elif btype == "callout":
            html_parts.append(_callout_html(b))
        elif btype == "quadrant":
            if b.get("points"):
                sec_no += 1
                qid = f"quad-{len(quadrants)}"
                quadrants.append({
                    "id": qid, "xName": b.get("xName", ""),
                    "yName": b.get("yName", ""), "points": b.get("points"),
                })
                html_parts.append(_quadrant_html(b, sec_no, qid))
        elif btype == "conclusions":
            sec_no += 1
            html_parts.append(_conclusions_html(b, sec_no))
    return "\n".join(p for p in html_parts if p), charts, quadrants


def _migrate_legacy(data: dict) -> list[dict]:
    """Bridge old fixed-shape JSON (kpis/summary/sections/synth_chart/conclusions)
    to the block array, so previously-saved report_data.json still renders."""
    blocks: list[dict] = []
    if data.get("kpis"):
        blocks.append({"type": "kpi", "items": data["kpis"]})
    if data.get("summary_lead") or data.get("summary_body"):
        blocks.append({
            "type": "prose", "tag_en": "EXECUTIVE SUMMARY", "heading": "执行摘要",
            "lead": data.get("summary_lead", ""),
            "paragraphs": [data.get("summary_body", "")],
        })
    for sec in data.get("sections", []) or []:
        blocks.append({
            "type": "prose", "tag_en": sec.get("tag_en", "FINDING"),
            "heading": sec.get("title", ""),
            "paragraphs": [p for p in (sec.get("para_1", ""), sec.get("para_2", "")) if p],
        })
        chart = sec.get("chart")
        if chart and chart.get("series"):
            cb = dict(chart)
            cb["chart_type"] = cb.pop("type", "bar")  # legacy used "type" for echart kind
            cb["type"] = "chart"
            blocks.append(cb)
        if sec.get("table"):
            blocks.append({"type": "table", **sec["table"]})
    sc = data.get("synth_chart")
    if data.get("synth_body") or sc:
        blocks.append({
            "type": "quadrant", "heading": "综合分析", "intro": data.get("synth_body", ""),
            **(sc or {}),
        })
    if data.get("conclusions"):
        blocks.append({"type": "conclusions", "items": data["conclusions"]})
    return blocks


def _sources_html(sources: list[dict]) -> str:
    items = []
    for s in sources or []:
        url = _esc(s.get("url", ""))
        title = _esc(s.get("title", "") or url)
        domain = ""
        m = re.search(r"https?://([^/]+)", str(s.get("url", "")))
        if m:
            domain = _esc(m.group(1))
        link = f'<br><a href="{url}">{domain or url}</a>' if url else ""
        items.append(f"<li>{title}{link}</li>")
    return "\n".join(items)


def render_html_report(data: dict, meta: dict) -> str:
    """Render the LLM's structured JSON into a complete HTML report.

    The body is an ordered `blocks` array — the LLM composes whichever blocks
    suit the topic. Cover + sources are fixed chrome. Legacy fixed-shape JSON
    (kpis/sections/synth_chart/...) is auto-migrated for backward compatibility."""
    data = data or {}
    blocks = data.get("blocks")
    if not blocks:
        blocks = _migrate_legacy(data)
    if not blocks:  # last-ditch: keep whatever text we have
        blocks = [{"type": "prose", "heading": "研究综述",
                   "paragraphs": [data.get("summary_body") or data.get("title") or ""]}]

    body_html, charts, quadrants = _render_blocks(blocks)

    report_data = {"charts": charts, "quadrants": quadrants}
    report_data_js = "const REPORT_DATA = " + json.dumps(report_data, ensure_ascii=False) + ";"

    sources = data.get("sources", [])
    gen_at = meta.get("generated_at") or datetime.now().strftime("%Y/%m/%d %H:%M")
    mode_cn = _PROFILE_CN.get(meta.get("profile", ""), meta.get("profile", "标准"))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(data.get('title','研究报告'))}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.4.3/echarts.min.js"></script>
{_STYLE}
</head>
<body>
<div class="wrap">
  <header class="cover">
    <div class="badge-row">
      <span class="badge live">● DeepResearch Agent 生成</span>
      <span class="badge">{_esc(mode_cn)} 模式 · <b>{_esc(meta.get('tokens','—'))}</b> tokens</span>
      <span class="badge">成本 <b>{_esc(meta.get('cost','—'))}</b></span>
      <span class="badge">引用支撑率 <b>{_esc(meta.get('citation_rate','—'))}</b></span>
      <span class="badge">{_esc(gen_at)}</span>
    </div>
    <div class="eyebrow">{_esc(data.get('topic_en',''))}</div>
    <h1 class="title">{_esc(data.get('title','研究报告'))}</h1>
    <p class="subtitle">{_esc(data.get('subtitle',''))}</p>
  </header>

  {body_html}

  <div class="sources">
    <div class="sec-no">REFERENCES</div>
    <h2 style="font-size:22px">信息来源 · {len(sources)} 项</h2>
    <ol id="source-list">
      {_sources_html(sources)}
    </ol>
  </div>

  <div class="foot">由 DeepResearch Agent 生成 · Multi-Agent + RAG + 引用溯源 · {_esc(gen_at)}</div>
</div>

<script>{report_data_js}</script>
{_RENDER_JS}
</body>
</html>"""

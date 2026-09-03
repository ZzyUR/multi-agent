"""HTML research-report rendering (template engine + LLM data contract)."""

from deepresearch.report.html_report import (
    REPORT_JSON_SYSTEM,
    render_html_report,
)

__all__ = ["REPORT_JSON_SYSTEM", "render_html_report"]

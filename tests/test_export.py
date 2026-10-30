"""导出与安全测试：CSV 公式注入、路径穿越、文件名清洗。"""
from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import pytest
from macrosope.export import export_csv, export_figure, safe_join, sanitize_cell, sanitize_filename


def test_sanitize_cell_formula_injection():
    assert sanitize_cell("=1+1") == "'=1+1"
    assert sanitize_cell("+SUM(A1)") == "'+SUM(A1)"
    assert sanitize_cell("-1") == "'-1"
    assert sanitize_cell("@cmd") == "'@cmd"
    assert sanitize_cell("正常文本") == "正常文本"


def test_export_csv_neutralizes_formula(tmp_path):
    df = pd.DataFrame({"name": ["=cmd|' /C calc'!A0", "正常"], "v": [1, 2]})
    export_csv(df, tmp_path, "out.csv")
    text = (tmp_path / "out.csv").read_text(encoding="utf-8-sig")
    # 公式注入的单元格应被单引号前缀
    assert "'=cmd" in text


def test_sanitize_filename():
    # 路径分隔符被替换，前导点号被去除（防隐藏文件/穿越）
    assert sanitize_filename("../etc/passwd") == "_etc_passwd"
    assert sanitize_filename("a/b\\c") == "a_b_c"


def test_safe_join_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, "../outside.csv")


def test_safe_join_allows_normal(tmp_path):
    p = safe_join(tmp_path, "ok.csv")
    assert p.parent == tmp_path.resolve()


def test_html_export_embeds_plotly_for_offline_use(tmp_path):
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    path = export_figure(fig, tmp_path, "offline.html", "html")
    html = tmp_path.joinpath("offline.html").read_text(encoding="utf-8")
    assert path == str(tmp_path / "offline.html")
    assert "Plotly.newPlot" in html
    assert "plotly.js" in html
    assert not re.search(r"<script\b[^>]*\bsrc\s*=", html, re.IGNORECASE)

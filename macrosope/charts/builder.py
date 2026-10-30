"""Plotly 图表构建器。

默认配色采用经过 CVD（色盲）校验的分类色板，固定顺序、不循环。
统一使用浅色图表表面与分层墨色，保证可读性与一致性。
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from macrosope.db import Repository
from macrosope.models import ChartSpec

# 验证过的分类色板（浅色模式，固定顺序）
DEFAULT_CATEGORICAL = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]
# 顺序色（蓝，用于热力图等连续量）
SEQUENTIAL_BLUE = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"]

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

_MAX_SERIES = len(DEFAULT_CATEGORICAL)


def prepare_series_data(repo: Repository, series_ids: list[int]) -> pd.DataFrame:
    """取多条序列，返回长表 DataFrame：series_id, date, value, name。"""
    if not series_ids:
        return pd.DataFrame(columns=["series_id", "date", "value", "name"])
    obs = repo.get_many_observations(series_ids)
    if obs.empty:
        return obs.assign(name="")
    # list_series 带指标名称的关联查询；get_series 只返回 series 表的原始列。
    meta = {item["series_id"]: item for item in repo.list_series()}
    obs["name"] = obs["series_id"].map(
        lambda sid: (meta.get(sid) or {}).get("indicator_name")
        or (meta.get(sid) or {}).get("entity")
        or f"序列{sid}"
    )
    return obs


def _series_color(idx: int) -> str:
    return DEFAULT_CATEGORICAL[idx % _MAX_SERIES]


def _apply_common(fig: go.Figure, spec: ChartSpec) -> go.Figure:
    opts = spec.options or {}
    title = spec.title
    if spec.subtitle:
        title = f"{title}<br><sub>{spec.subtitle}</sub>"
    foot_parts = []
    if spec.source:
        foot_parts.append(f"数据来源：{spec.source}")
    if spec.updated_at:
        foot_parts.append(f"更新时间：{spec.updated_at}")
    if spec.footnote:
        foot_parts.append(spec.footnote)
    fig.update_layout(
        title={"text": title, "x": 0.06, "xanchor": "left"} if title else None,
        xaxis_title=spec.x_label or None,
        yaxis_title=spec.y_label or (spec.unit if spec.unit else None),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": "system-ui, -apple-system, Segoe UI, sans-serif",
              "color": INK_PRIMARY},
        showlegend=opts.get("show_legend", True),
        width=opts.get("width", 900),
        height=opts.get("height", 500),
        legend={"title_text": ""},
        margin={"l": 60, "r": 30, "t": 70 if title else 40,
                "b": 95 + 16 * (len(foot_parts) - 1) if foot_parts else 60},
        hovermode="x unified",
    )
    fig.update_xaxes(
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
        zeroline=False,
        showline=True,
    )
    fig.update_yaxes(
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
        zeroline=opts.get("zero_line", False),
        zerolinecolor=BASELINE,
        showline=True,
        type="category" if spec.chart_type == "heatmap" else (
            "log" if opts.get("log_y") else "linear"
        ),
    )
    # 图下注释（来源 + 更新时间 + 口径）
    if foot_parts:
        fig.add_annotation(
            text="<br>".join(foot_parts),
            xref="paper", yref="paper", x=0.0, y=0.0, yshift=-60,
            xanchor="left", yanchor="top",
            showarrow=False, font={"size": 11, "color": MUTED}, align="left",
        )
    return fig


def _fmt(decimals: int | None) -> str:
    if decimals is None:
        return ""
    return f".{decimals}f"


def _value_fmt(spec: ChartSpec) -> str:
    d = (spec.options or {}).get("decimals")
    return _fmt(d)


# ------------------------------------------------------------------ 折线
def _line(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    fig = go.Figure()
    fmt = _value_fmt(spec)
    for i, (_, grp) in enumerate(data.groupby("series_id", sort=False)):
        fig.add_trace(
            go.Scatter(
                x=grp["date"], y=grp["value"], mode="lines",
                name=str(grp["name"].iloc[0]),
                line={"color": _series_color(i), "width": 2},
                text=grp["value"].map(lambda v: f"{v:{fmt}}" if fmt else str(v)),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y}<extra></extra>",
            )
        )
    return _apply_common(fig, spec)


# ------------------------------------------------------------------ 柱状
def _bar(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    fig = go.Figure()
    for i, (_, grp) in enumerate(data.groupby("series_id", sort=False)):
        fig.add_trace(
            go.Bar(
                x=grp["date"], y=grp["value"],
                name=str(grp["name"].iloc[0]),
                marker_color=_series_color(i),
            )
        )
    return _apply_common(fig, spec)


# ------------------------------------------------------------------ 面积
def _area(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    fig = go.Figure()
    stack = (spec.options or {}).get("stacked", True)
    for i, (_, grp) in enumerate(data.groupby("series_id", sort=False)):
        fig.add_trace(
            go.Scatter(
                x=grp["date"], y=grp["value"], mode="lines",
                name=str(grp["name"].iloc[0]),
                line={"color": _series_color(i), "width": 1.5},
                stackgroup="one" if stack else None,
                fill="tonexty" if (stack and i > 0) else "tozeroy",
                fillcolor=_series_color(i),
                opacity=0.6,
            )
        )
    return _apply_common(fig, spec)


# ------------------------------------------------------------------ 散点
def _scatter(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    fig = go.Figure()
    series = sorted(data["series_id"].unique())
    if len(series) >= 2:
        a = data[data["series_id"] == series[0]][["date", "value"]]
        b = data[data["series_id"] == series[1]][["date", "value"]]
        m = pd.merge(a, b, on="date", suffixes=("_x", "_y"))
        fig.add_trace(
            go.Scatter(
                x=m["value_x"], y=m["value_y"], mode="markers",
                marker={"color": DEFAULT_CATEGORICAL[0], "size": 8},
                name="散点",
                text=m["date"].astype(str),
                hovertemplate="%{x}, %{y}<br>%{text}<extra></extra>",
            )
        )
        fig.update_xaxes(title_text=spec.x_label or "序列 A")
        fig.update_yaxes(title_text=spec.y_label or "序列 B")
    else:
        grp = data[data["series_id"] == series[0]]
        fig.add_trace(
            go.Scatter(
                x=grp["date"], y=grp["value"], mode="markers",
                marker={"color": DEFAULT_CATEGORICAL[0], "size": 7},
                name=str(grp["name"].iloc[0]),
            )
        )
    return _apply_common(fig, spec)


# ------------------------------------------------------------------ 热力图
def _heatmap(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    wide = data.pivot_table(index="date", columns="name", values="value")
    corr = wide.corr()
    fig = go.Figure(
        go.Heatmap(
            z=corr.values,
            x=corr.columns.tolist(),
            y=corr.index.tolist(),
            colorscale=[[0.0, SEQUENTIAL_BLUE[0]], [0.5, SEQUENTIAL_BLUE[1]],
                        [1.0, SEQUENTIAL_BLUE[3]]],
            zmin=-1, zmax=1,
            colorbar={"title": "相关系数"},
        )
    )
    fig.update_layout(title={"text": spec.title or "相关系数热力图", "x": 0.0})
    return _apply_common(fig, spec)


# ------------------------------------------------------------------ 直方图 / 箱线图
def _histogram(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    fig = go.Figure(go.Histogram(x=data["value"], marker_color=DEFAULT_CATEGORICAL[0]))
    return _apply_common(fig, spec)


def _box(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    fig = go.Figure()
    for i, (_, grp) in enumerate(data.groupby("series_id", sort=False)):
        fig.add_trace(go.Box(y=grp["value"], name=str(grp["name"].iloc[0]),
                             marker_color=_series_color(i)))
    return _apply_common(fig, spec)


# ------------------------------------------------------------------ 堆叠柱状
def _stacked_bar(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    fig = go.Figure()
    for i, (_, grp) in enumerate(data.groupby("series_id", sort=False)):
        fig.add_trace(
            go.Bar(x=grp["date"], y=grp["value"],
                   name=str(grp["name"].iloc[0]),
                   marker_color=_series_color(i))
        )
    fig.update_layout(barmode="stack")
    return _apply_common(fig, spec)


# ------------------------------------------------------------------ 双轴（谨慎使用，可信度检查会警告）
def _dual_axis(data: pd.DataFrame, spec: ChartSpec) -> go.Figure:
    fig = go.Figure()
    series = sorted(data["series_id"].unique())
    for i, sid in enumerate(series[:2]):
        grp = data[data["series_id"] == sid]
        fig.add_trace(
            go.Scatter(
                x=grp["date"], y=grp["value"], mode="lines",
                name=str(grp["name"].iloc[0]),
                line={"color": _series_color(i), "width": 2},
                yaxis="y" if i == 0 else "y2",
            )
        )
    fig.update_layout(
        yaxis2={"title": spec.y_label, "overlaying": "y", "side": "right",
                "showgrid": False},
    )
    return _apply_common(fig, spec)


_BUILDERS = {
    "line": _line,
    "bar": _bar,
    "area": _area,
    "scatter": _scatter,
    "heatmap": _heatmap,
    "histogram": _histogram,
    "box": _box,
    "stacked_bar": _stacked_bar,
    "dual_axis": _dual_axis,
}


def build_figure(spec: ChartSpec, data: pd.DataFrame) -> go.Figure:
    """按 spec 构建 Plotly 图。data 为 prepare_series_data 的输出。"""
    if spec.chart_type not in _BUILDERS:
        raise ValueError(f"未知图表类型：{spec.chart_type}")
    if data.empty or data["value"].isna().all():
        fig = go.Figure()
        fig.add_annotation(
            text="无可用数据", xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font={"color": MUTED, "size": 16},
        )
        return _apply_common(fig, spec)
    return _BUILDERS[spec.chart_type](data, spec)

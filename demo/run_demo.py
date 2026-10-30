"""完整端到端演示（无界面）：导入 → 质量 → 变换 → 图表 → 可信度 → 项目 → 导出。

使用 sample_data/ 下的虚构数据，默认写入独立的 data/demo/ 目录。
可用 MACROSOPE_DATA_DIR / MACROSOPE_DB_PATH 环境变量覆盖。
所有数据均为合成数据，不代表真实经济；重复运行会增加演示记录。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

if __name__ == "__main__":
    os.environ.setdefault("MACROSOPE_DATA_DIR", str(PROJECT / "data" / "demo"))

from macrosope.charts import build_figure, check_chart, prepare_series_data  # noqa: E402
from macrosope.config import EXPORT_DIR  # noqa: E402
from macrosope.db import Repository  # noqa: E402
from macrosope.export import export_csv, export_figure, to_json  # noqa: E402
from macrosope.models import ChartSpec, IndicatorMeta  # noqa: E402
from macrosope.quality import run_frame_checks  # noqa: E402
from macrosope.services import ingest  # noqa: E402
from macrosope.transforms import Pipeline  # noqa: E402

SAMPLE = PROJECT / "sample_data"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

log: list[str] = []


def step(msg: str) -> None:
    log.append(msg)
    print(msg)


def main(*, static_images: bool = True) -> None:
    repo = Repository()
    pipe = Pipeline(repo)
    series: dict[str, int] = {}

    # ---------------------------------------------------------- 1. 导入
    step("== 1. 导入示例数据（6 个文件，4 种格式） ==")
    # 宽表 CSV（UTF-8）：CPI/PPI/M2 同比
    did, sids = ingest(
        repo, str(SAMPLE / "cpi_ppi_m2_wide.csv"), "csv",
        {"encoding": None, "delimiter": None, "header_row": 0, "skiprows": 0},
        {"日期": "date", "CPI同比": "value", "PPI同比": "value", "M2同比": "value"},
        IndicatorMeta(unit="%", frequency="monthly", region="示例国", currency="CNY",
                      source_org="宏观数据工作台虚构数据"),
        dataset_name="示例·通胀与货币（宽表CSV）",
    )
    for s in sids:
        series[repo.get_indicator(repo.get_series(s)["indicator_id"]).name] = s
    step(f"  宽表CSV -> 数据集#{did}，序列 {sids}")

    # 长表 CSV：GDP、固定资产投资（季度）
    _, sids = ingest(
        repo, str(SAMPLE / "gdp_investment_long.csv"), "csv",
        {"encoding": None, "delimiter": None, "header_row": 0, "skiprows": 0},
        {"日期": "date", "指标": "indicator", "数值": "value", "单位": "unit"},
        IndicatorMeta(frequency="quarterly", region="示例国",
                      source_org="宏观数据工作台虚构数据"),
        dataset_name="示例·GDP与投资（长表CSV）",
    )
    for s in sids:
        series[repo.get_indicator(repo.get_series(s)["indicator_id"]).name] = s
    step(f"  长表CSV -> GDP、固定资产投资 序列 {sids}（单位取自「单位」列）")

    # GBK + 分号 + 千分位 + 百分号 CSV
    _, sids = ingest(
        repo, str(SAMPLE / "social_finance_gbk.csv"), "csv",
        {"encoding": None, "delimiter": None, "header_row": 0, "skiprows": 0},
        {"月份": "date", "社会融资规模存量": "value", "人民币贷款": "value", "同比增长": "value"},
        IndicatorMeta(frequency="monthly", region="示例国",
                      source_org="宏观数据工作台虚构数据"),
        numeric={"thousands": ",", "percent": True},
        dataset_name="示例·社融（GBK编码+千分位+百分号）",
    )
    for s in sids:
        series[repo.get_indicator(repo.get_series(s)["indicator_id"]).name] = s
    sf = repo.get_observations(series["社会融资规模存量"])
    step(f"  GBK CSV -> 序列 {sids}；社融存量示例值：{sf['value'].iloc[0]:,.1f}（千分位已解析）")

    # Excel 多工作表
    _, sids = ingest(
        repo, str(SAMPLE / "macro_monthly.xlsx"), "xlsx",
        {"sheet_name": "CPI", "header_row": 0, "skiprows": 0},
        {"月份": "date", "CPI同比(%)": "value", "食品价格": "value"},
        IndicatorMeta(frequency="monthly", region="示例国",
                      source_org="宏观数据工作台虚构数据"),
        dataset_name="示例·Excel多工作表(CPI表)",
    )
    step(f"  XLSX(工作表CPI) -> 序列 {sids}")

    # JSON
    _, sids = ingest(
        repo, str(SAMPLE / "population.json"), "json",
        {"orient": "records"},
        {"年份": "date", "总人口(万人)": "value", "就业人员(万人)": "value"},
        IndicatorMeta(frequency="annual", region="示例国",
                      source_org="宏观数据工作台虚构数据"),
        date_format="%Y",
        dataset_name="示例·人口（JSON）",
    )
    for s in sids:
        series[repo.get_indicator(repo.get_series(s)["indicator_id"]).name] = s
    step(f"  JSON -> 序列 {sids}")

    # Parquet
    _, sids = ingest(
        repo, str(SAMPLE / "trade.parquet"), "parquet",
        {},
        {"日期": "date", "出口": "value", "进口": "value", "贸易差额": "value"},
        IndicatorMeta(unit="亿美元", frequency="monthly", region="示例国",
                      source_org="宏观数据工作台虚构数据"),
        dataset_name="示例·贸易（Parquet）",
    )
    for s in sids:
        series[repo.get_indicator(repo.get_series(s)["indicator_id"]).name] = s
    step(f"  Parquet -> 序列 {sids}")

    # ---------------------------------------------------------- 2. 质量检查
    step("== 2. 数据质量检查（GDP 序列） ==")
    gdp_df = repo.get_observations(series["GDP"])
    report = run_frame_checks(gdp_df, date_col="date", value_col="value")
    step(f"  GDP：{len(report.errors)} 错误 / {len(report.warnings)} 警告 / {len(report.infos)} 提示")

    # ---------------------------------------------------------- 3. 变换
    step("== 3. 变换（同比 / 移动平均 / 人均 / 频率转换） ==")
    gdp_yoy = pipe.apply("yoy", [series["GDP"]], {"freq": "quarterly"})[0]
    step(f"  GDP 同比（季度）-> 序列#{gdp_yoy}，首值 {repo.get_observations(gdp_yoy)['value'].iloc[0]:.2f}%")

    m2_ma = pipe.apply("moving_average", [series["M2同比"]], {"window": 3})[0]
    step(f"  M2同比 3期移动平均 -> 序列#{m2_ma}")

    gdp_pc = pipe.apply("per_capita", [series["GDP"], series["总人口(万人)"]])[0]
    step(f"  人均GDP（GDP/总人口）-> 序列#{gdp_pc}")

    export_q = pipe.apply(
        "resample", [series["出口"]], {"to_freq": "quarterly", "method": "sum"}
    )[0]
    step(f"  出口 月度->季度（求和，流量）-> 序列#{export_q}")

    cpi_idx = pipe.apply("index_first", [series["CPI同比"]])[0]
    ppi_idx = pipe.apply("index_first", [series["PPI同比"]])[0]
    step(f"  CPI/PPI 首期=100 指数化 -> 序列#{cpi_idx}, #{ppi_idx}")

    # 管道历史
    steps = repo.list_steps()
    step(f"  变换管道共 {len(steps)} 步（可查看/可撤销/可重跑）")

    # ---------------------------------------------------------- 4. 图表 + 可信度
    step("== 4. 图表与可信度检查 ==")
    spec = ChartSpec(
        name="示例：GDP与固定资产投资（季度）",
        chart_type="line", series_ids=[series["GDP"], series["固定资产投资"]],
        title="示例国 GDP 与固定资产投资（虚构数据）",
        y_label="万亿元", unit="万亿元",
        source="宏观数据工作台虚构数据", footnote="合成数据，仅用于功能演示",
        updated_at="2026-08-13",
    )
    metas = []
    for sid in spec.series_ids:
        m = repo.get_series(sid)
        ind = repo.get_indicator(m["indicator_id"])
        metas.append({**m, **ind.model_dump()})
    cred = check_chart(spec, metas)
    step(f"  折线图可信度检查：{len(cred.errors)} 错误 / {len(cred.warnings)} 警告")
    data = prepare_series_data(repo, spec.series_ids)
    fig = build_figure(spec, data)
    html = export_figure(fig, EXPORT_DIR, "demo_line_chart.html", "html")
    step(f"  导出 HTML: {html}")
    if static_images:
        png = export_figure(fig, EXPORT_DIR, "demo_line_chart.png", "png")
        step(f"  导出 PNG: {png}")
        svg = export_figure(fig, EXPORT_DIR, "demo_line_chart.svg", "svg")
        step(f"  导出 SVG: {svg}")
    else:
        step("  已按 --skip-static-images 跳过静态图片；本次不验证 PNG/SVG。")

    # 双轴图的可信度警告演示
    spec2 = ChartSpec(
        chart_type="dual_axis", series_ids=[series["CPI同比"], series["出口"]],
        title="示例：双轴图（演示警告）",
    )
    metas2 = []
    for sid in spec2.series_ids:
        m = repo.get_series(sid)
        ind = repo.get_indicator(m["indicator_id"])
        metas2.append({**m, **ind.model_dump()})
    cred2 = check_chart(spec2, metas2)
    codes = [i.code for i in cred2.warnings]
    step(f"  双轴图警告：{codes}")

    # 相关性热力图
    spec3 = ChartSpec(
        chart_type="heatmap",
        series_ids=[series["CPI同比"], series["PPI同比"], series["M2同比"], series["出口"]],
        title="示例：相关性热力图（虚构数据）",
    )
    data3 = prepare_series_data(repo, spec3.series_ids)
    fig3 = build_figure(spec3, data3)
    html3 = export_figure(fig3, EXPORT_DIR, "demo_heatmap.html", "html")
    step(f"  热力图导出 HTML: {html3}")
    if static_images:
        png3 = export_figure(fig3, EXPORT_DIR, "demo_heatmap.png", "png")
        step(f"  热力图导出 PNG: {png3}")

    # ---------------------------------------------------------- 5. 项目
    step("== 5. 研究项目 ==")
    pid = repo.create_project("示例国经济研究（虚构数据演示）", "通胀与货币环境对出口的影响")
    repo.add_project_entry(pid, "fact", "2020-2024 示例数据中，CPI 同比中枢约 2%")
    repo.add_project_entry(pid, "calculation", "GDP 同比由季度序列计算得到（4期滞后）")
    repo.add_project_entry(pid, "inference", "出口与 M2 同比存在同步波动，但相关不等于因果")
    repo.add_project_entry(pid, "hypothesis", "若货币增速放缓，出口可能滞后两个季度回落（未验证）")
    step(f"  项目#{pid} 已创建，含 事实/计算/推断/假设 四类条目")

    # ---------------------------------------------------------- 6. 导出
    step("== 6. 导出 ==")
    out_csv = export_csv(repo.get_observations(gdp_yoy), EXPORT_DIR, "demo_gdp_yoy.csv")
    step(f"  GDP同比 CSV: {out_csv}")
    pipe_json = to_json([s.model_dump() for s in repo.list_steps()], EXPORT_DIR, "demo_pipeline.json")
    step(f"  变换管道 JSON: {pipe_json}")
    backup = repo.backup(EXPORT_DIR / "demo_backup")
    step(f"  数据库备份: {backup}")

    step("== 演示完成 ==")
    step(f"  数据集：{len(repo.list_datasets())} 个；序列：{len(repo.list_series())} 条；"
         f"变换步骤：{len(repo.list_steps())} 步；项目：{len(repo.list_projects())} 个")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-static-images", action="store_true",
        help="仅导出 HTML 图表，明确跳过需要 Chrome 的静态图片验证",
    )
    args = parser.parse_args()
    if args.skip_static_images:
        main(static_images=False)
    else:
        import kaleido

        # 多张静态图复用 Chrome，避免每张图重复启动和关闭浏览器。
        kaleido.start_sync_server()
        try:
            main()
        finally:
            kaleido.stop_sync_server()

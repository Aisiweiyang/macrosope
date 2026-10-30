"""指标库页：查看、编辑指标元数据与序列。"""
from __future__ import annotations

import streamlit as st
from macrosope.models import IndicatorMeta
from macrosope.ui import get_repo, series_label

repo = get_repo()

st.title("📚 指标库")

indicators = repo.list_indicators()
if not indicators:
    st.info("还没有指标，请先导入数据。")
    st.stop()

st.subheader("指标元数据")
for ind in indicators:
    with st.expander(f"{ind.name}（{ind.frequency or '未设频率'}）"):
        c1, c2, c3 = st.columns(3)
        new_name = c1.text_input("名称", ind.name, key=f"n_{ind.indicator_id}")
        new_code = c2.text_input("代码", ind.code, key=f"c_{ind.indicator_id}")
        new_unit = c3.text_input("单位", ind.unit, key=f"u_{ind.indicator_id}")
        c4, c5, c6 = st.columns(3)
        new_freq = c4.text_input("频率", ind.frequency, key=f"f_{ind.indicator_id}")
        new_region = c5.text_input("地区", ind.region, key=f"r_{ind.indicator_id}")
        new_currency = c6.text_input("币种", ind.currency, key=f"cc_{ind.indicator_id}")
        c7, c8 = st.columns(2)
        new_def = c7.text_area("定义", ind.definition, key=f"d_{ind.indicator_id}")
        new_note = c8.text_area("口径说明/备注", ind.scope_note, key=f"sn_{ind.indicator_id}")
        if st.button("保存", key=f"save_{ind.indicator_id}"):
            updated = IndicatorMeta(
                indicator_id=ind.indicator_id,
                name=new_name, code=new_code, unit=new_unit,
                frequency=new_freq, region=new_region, currency=new_currency,
                definition=new_def, scope_note=new_note,
                nominal_or_real=ind.nominal_or_real, stock_or_flow=ind.stock_or_flow,
                period_or_cumulative=ind.period_or_cumulative,
                seasonally_adjusted=ind.seasonally_adjusted,
                base_period=ind.base_period, source_org=ind.source_org,
                source_link=ind.source_link, updated_at=ind.updated_at,
                user_note=ind.user_note,
            )
            repo.update_indicator(updated)
            st.success("已保存")
            st.rerun()

st.subheader("序列")
for s in repo.list_series():
    mark = "派生" if s["is_derived"] else "原始"
    st.markdown(f"- {series_label(s)}　`{mark}`　(`series_id={s['series_id']}`)")

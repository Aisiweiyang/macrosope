# AGENTS.md — 宏观数据工作台开发指南

供 Claude Code / 其他 AI 助手在此项目中工作时遵循。

## 项目定位

宏观数据工作台：本地单体的经济数据导入、处理、分析与制图（Streamlit + DuckDB + Plotly）。
与桌面另一个「宏观实验室」（FastAPI + React）是**两个独立项目**，不要互相改动。

## 硬性规则

1. **本地优先**：本项目已进入开源准备阶段，可维护源码、文档、测试和发布包；创建/推送远程仓库、发布 Release、部署公网须有用户明确授权。应用不接外部 API、不爬取网站。
2. **用户数据不上传**：数据库、原始归档、导出物和凭据不得进入提交或发布包。仅发布 `sample_data/` 内由生成器创建的既定合成样例。
3. **原始数据与派生数据分离**：原始文件归档 `data/raw/`（绝不覆盖）；派生序列 `is_derived=TRUE`。
4. **绝不静默处理数据**：不静默填充缺失值、不静默删除异常值；质量检查只报告（错误/警告/提示三级）。
5. **变换必须记账**：所有变换走 `macrosope/transforms/pipeline.py` 的 `Pipeline`，可查看/可撤销/可重跑。
6. **禁止低频升频插值**（伪造数据），`validate_freq_conversion` 强制校验。
7. **不把相关解释成因果**；双轴图必须触发可信度警告。
8. **导出必须防注入/防穿越**：CSV 用 `sanitize_cell`，文件名用 `sanitize_filename` + `safe_join`。
9. **删除操作二次确认**（页面层 checkbox 确认）。
10. **拒绝 XLSM**，绝不执行 Excel 宏。

## 环境与命令（Windows Python 3.13 venv）

```bash
cd macrosope
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe -m pytest            # 全部测试必须通过，数量以当次收集为准
venv\Scripts\python.exe -m ruff check macrosope app.py pages tests demo sample_data scripts
venv\Scripts\python.exe -m streamlit run app.py
```

- venv 是 **Windows venv**（Python 3.13），从 WSL 调用时注意：
  Windows Python 不认 `/mnt/c/...` 路径，须用 Windows 路径或相对路径。
- pip 安装建议用清华镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`（国内直连 PyPI 不稳）。
- pytest 的 basetemp 已配到 `data/.pytest-tmp`（规避 AppData 临时目录 ACL 问题），别改回默认。
- **pandas 3.0** 注意事项：`resample` 用 `ME/QE/YE`（不是 M/Q/Y）；读入字符串列用 `dtype=object`
  （不用 `dtype=str`，避免 arrow 字符串类型与 object 判断冲突）。

## 关键设计

- 存储长表：`observations(series_id, date, value)`；序列 = 指标 × 实体；指标 18 项元数据。
- 变换注册表在 `macrosope/transforms/base.py`（`TRANSFORM_REGISTRY`：函数 + 元数据 + 输入数）。
  新增变换：实现纯函数（输入输出为 `[date, value]` DataFrame）→ 注册 → 页面 `PARAM_SPECS` 加参数。
- 图表默认配色是经 CVD 校验的固定顺序色板（`macrosope/charts/builder.py`），不要循环取色。
- 导入流程：读取 → normalize_dataframe（仅对 % 单元格除以 100）→ 字段映射 → standardize_long →
  日期解析（解析失败即报错，不丢弃）→ 按 indicator×entity 拆序列落库 → 归档原始文件。
- 测试数据必须**小且可人工核验**；示例数据全部虚构并标注。

## 已知限制（MVP）

无在线 API、无爬虫、无 PDF/图片识别、无因果推断、无投资建议；PNG/SVG 依赖 Kaleido 和 Chrome；HTML 自包含。

## 发布检查

- 公共项目名与包名沿用 `macrosope`，不要顺手重命名现有 Python 包。
- 发布前运行完整测试、Ruff、演示和 `python scripts/prepare_release.py --check`。
- 使用 `scripts/prepare_release.py` 的白名单生成源码发布包，禁止直接压缩整个工作目录。
- 验证记录写入 `docs/VALIDATION.md`；本机验证与远程 CI 状态分开报告。

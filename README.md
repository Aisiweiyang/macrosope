# Macrosope · 宏观数据工作台

本地单体的经济金融数据**导入、处理、分析与制图**工具。面向经济学、金融工程与宏观研究。
当前版本 `0.1.0`，采用 [MIT 许可证](LICENSE)。Python 包名沿用 `macrosope`。

[GitHub 仓库](https://github.com/Aisiweiyang/macrosope) · [CI 状态](https://github.com/Aisiweiyang/macrosope/actions)

- 已验证环境：Windows + Python 3.13；其他平台状态见 [验证记录](docs/VALIDATION.md)
- 本地运行：不调用数据 API、不爬取、不主动上传业务数据；默认仅监听 `127.0.0.1`，关闭 Streamlit 使用统计
- 存储：DuckDB（原始数据与派生数据分离）
- 界面：Streamlit（首页 + 12 个功能页）
- 图表：Plotly（生成前自动做可信度检查）

---

## 一、安装与启动

下载源码 ZIP 并解压，或克隆发布后的仓库。从源码根目录执行：

```powershell
# 1. 进入解压/克隆后的项目目录（按实际目录名调整）
cd macrosope

# 2. 创建虚拟环境（首次）
py -3.13 -m venv venv

# 3. 安装依赖（首次；国内可用清华镜像）
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# 或
.\venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 4. 启动
.\venv\Scripts\python.exe -m streamlit run app.py
```

浏览器自动打开 `http://127.0.0.1:8501`，也可双击 `运行.cmd` 启动已安装的环境。
macOS/Linux 可使用 `python3.13 -m venv venv`，并将解释器路径改为 `venv/bin/python`；
平台实测情况单独记录，不把 CI 配置当成验证结果。

依赖安装需要联网；运行后只处理本地资料。`requirements.txt` 安装当前源码，运行依赖统一
维护在 `pyproject.toml`，`constraints.txt` 固定本次验证环境涉及的依赖版本。
请保留完整源码目录，单独安装 Python 核心包不能替代 Streamlit 页面与样例文件。

**静态图片导出：** PNG/SVG 需要 Kaleido 和本机 Chrome。
[Kaleido 1.x 不再内置 Chrome，要求 Plotly 6.1.1 及以上](https://github.com/plotly/Kaleido#installation)。
若没有可用 Chrome，可在联网时执行以下命令下载兼容版本：

```powershell
.\venv\Scripts\python.exe -c "import kaleido; kaleido.get_chrome_sync()"
```

HTML 图表已嵌入 Plotly 脚本，可离线打开，不依赖 Chrome 或 CDN。

## 二、功能

| 模块 | 说明 |
|------|------|
| 导入数据 | CSV（UTF-8/GBK/GB18030 等、分隔符识别、表头行、跳过说明行、千分位、百分号）、XLSX（选工作表、合并单元格检查）、JSON、Parquet。**拒绝 XLSM（不执行宏）** |
| 字段映射 | 日期/指标/数值/实体/单位/频率/来源/备注列角色确认；宽表↔长表互转；自动识别仅作建议 |
| 指标元数据 | 名称/代码/定义/单位/频率/地区/币种/来源/名义或实际/存量或流量/当期或累计/是否季调/基期/口径/备注 |
| 数据质量检查 | 空文件、空列、重复列名、重复日期、重复记录、日期无法解析、日期乱序、缺失值、非数字、异常值、单位/币种/频率/百分数/累计当期/季调/名义实际混杂 —— 分**错误/警告/提示**三级，绝不静默处理 |
| 清洗与变换 | 27 个变换（清洗 5 + 增长率 5 + 累计当期 2 + 指数化 3 + 移动统计 3 + 标准化 3 + 结构 2 + 双序列 3 + 频率转换 1），全部**可查看、可撤销、可重新运行**，每步显示公式/参数/输出单位/频率/局限 |
| 图表 | 折线、柱状、堆叠柱状、面积、散点、热力图、直方图、箱线图、双轴（谨慎） |
| 可信度检查 | 生成前检查单位/频率/口径一致、堆叠可加性、双轴误导、纵轴截断、标题口径、数据来源 |
| 研究项目 | 研究问题、笔记、数据限制、来源；条目分**原始事实/计算结果/用户推断/未验证假设**四类 |
| 导出 | CSV（防公式注入）、XLSX、Parquet、PNG/SVG/HTML 图表、配置/管道 JSON、数据库备份 |
| 备份恢复 | DuckDB 整库备份与恢复（结构校验、恢复前自动备份、失败回滚） |
| 中国经济数据 | 完全离线发现同级生产项目的版本快照，校验、预览历史差异、确认后事务导入 |

## 三、与“中国经济分析”的松耦合集成

这是**可选集成**。没有生产端项目也可独立使用全部本地文件导入、分析和制图功能。
公开源码不附带生产端缓存、真实交换快照或用户数据库。

同级的“中国经济分析”是生产者，负责联网采集、官方来源核验、质量评分、宏观分析和
生成交换文件；本项目是消费者，只读取本地 JSON，绝不在预览或导入时访问 HTTP/HTTPS、
调用外部 API、抓取网页或尝试补全官方数据。两个项目不合并代码库、不复制业务实现，
也不互相导入 Python 源码，仅共享文档化的 JSON 协议。

“中国经济数据”页默认目录按两个项目的同级关系动态推导为
`../中国经济分析/output`，用户可以修改并在当前 Streamlit 会话中保留选择；数据库不会
保存某台电脑的绝对发现路径。发现顺序为不可变的
`integration_YYYYMMDD_HHMMSS.json`、原子更新的 `integration_latest.json`，最后才是在
内存中适配最新 `分析数据_*.json`。旧文件本身绝不会改写。

协议 1.0 的顶层字段为 `schema_version`、`producer`、`generated_at`、`snapshot_id`、
`content_hash`、`source_status`、`indicator_metadata`、`observations`、`analysis`。
`content_hash` 是排除身份字段后，对 UTF-8、键名排序、紧凑 JSON 内容计算的 SHA256；
同时另记原文件 `file_sha256`。旧版内存适配使用
`schema_version = "legacy-adapter-1.0"` 与 `legacy-{file_sha256前16位}` 快照标识。

导入流程是：发现文件 → 只读预览 → 阻断性质量校验 → 历史差异识别 → 勾选确认 →
重新读取并核对哈希、大小和修改时间 → 不可变归档 → Repository 整批事务入库。
全新指标、全新日期、完全重复和历史数值修订都会明确显示；修订创建新的不可变数据集，
绝不覆盖旧值。相同 `content_hash` 返回原 `dataset_id`，不会再次写入。

`analysis` 单独保存在分析快照表，并标明自动计算、风险提示或模型推断；不写进
`observations` 数据事实。相关不代表因果，周期定位不是确定性预测。本页不会自动创建研究
项目，用户仍可在“研究项目”页主动创建和关联数据集。

## 四、使用流程

1. **导入数据**：上传文件 → 设置编码/分隔符/表头行 → 确认字段映射 → 填指标元数据 → 导入
2. **数据质量检查**：查看错误/警告/提示
3. **清洗与变换**：同比、环比、指数化、移动平均、频率转换等（可撤销）
4. **图表生成器**：选序列 → 选类型 → 可信度检查 → 生成 → 保存
5. **研究项目**：记录研究问题、数据、图表、笔记（四类分层）
6. **导出中心 / 备份与恢复**
7. **中国经济数据**：确认生产端已生成交换文件 → 发现最新文件 → 检查质量和修订 → 勾选确认 → 导入

日期为纯年份（如 `2015`）或紧凑数字（如 `20230101`）时按日历日期解析，
不会把整数当成 Unix 时间戳；可在读取设置中填写 `%Y` 或 `%Y%m%d` 明确格式。
未提供时间戳单位或 Excel 日期序列号的自动识别，遇到这类资料应先明确转换口径。

## 五、数据与存储

```
macrosope/
├── app.py                  # Streamlit 入口（首页）
├── pages/                  # 12 个功能页
├── macrosope/              # 核心包
│   ├── db/                 #   DuckDB schema + 迁移 + 仓储
│   ├── importers/          #   CSV/XLSX/JSON/Parquet 读取器
│   ├── mapping/            #   字段映射 + 宽长表转换
│   ├── quality/            #   质量检查引擎
│   ├── transforms/         #   27 个变换 + 可撤销管道
│   ├── charts/             #   Plotly 构建器 + 可信度检查
│   ├── services/           #   导入落库服务
│   ├── projects/           #   研究项目
│   ├── export/             #   导出 + 注入/穿越防护
│   └── models/             #   Pydantic 模型
├── data/
│   ├── macrosope.duckdb    # 数据库
│   ├── raw/                # 原始文件归档（绝不覆盖）
│   └── exports/            # 导出目录
├── sample_data/            # 虚构示例数据 + 生成器
├── demo/run_demo.py        # 端到端演示脚本
├── tests/                  # 自动化测试
├── scripts/prepare_release.py  # 白名单源码发布包
├── docs/                   # 验证记录与发布流程
└── LICENSE                 # MIT 许可证
```

核心数据模型（长表）：`observations(series_id, date, value)`，每条 `series` 挂一个 `indicator`
（18 项元数据）。派生序列 `is_derived=TRUE` 且与原始序列分离。

数据库 schema v2 在原结构上增加 `import_audits` 与 `analysis_snapshots`。迁移通过现有
`Repository.migrate()` 幂等执行，旧 v1 数据库可直接升级；数据事实失败时整批回滚，审计
更新为 `rolled_back`，不可变原始归档可保留作为证据。恢复旧库仍使用“备份与恢复”页；
恢复前自动备份，失败自动回滚。

生产端 `cache/macro.json` 是数据采集缓存，其中的 `verification` 是独立的官方核验缓存；
消费端 `data/raw` 是已确认导入文件的不可变审计归档，三者用途不同，不能互相替代。

## 六、测试与质量

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m ruff check macrosope app.py pages tests demo sample_data scripts
.\venv\Scripts\python.exe demo/run_demo.py   # 虚构数据端到端演示，默认写入 data/demo/
.\venv\Scripts\python.exe sample_data/generate_sample_data.py  # 覆盖重新生成合成样例
.\venv\Scripts\python.exe scripts/prepare_release.py --check  # 检查公开文件白名单
```

测试覆盖：事务导入与回滚、原始文件防覆盖、安全删除与恢复、CSV 编码、
Excel 多工作表、拒绝 XLSM、日期解析、重复日期、缺失值、
百分数/千分位、宽长表互转、同比/环比/年化、累计转当期、指数化、移动平均、
月度转季度（流量求和/存量期末）、人均、名义转实际、分母为零、单位不一致警告、
双轴警告、DuckDB 保存恢复、PNG/HTML 导出、CSV 公式注入防护、路径穿越防护。

具体执行范围与结果见 [验证记录](docs/VALIDATION.md)。PNG/SVG 的实际导出通过端到端演示
验证，不能只凭测试文件或历史测试数量推断通过。本次实际导出结果和环境条件见验证记录。
没有可用 Chrome 时可执行 `python demo/run_demo.py --skip-static-images`，验证其余流程
并导出 HTML；该模式明确不验证 PNG/SVG，默认演示仍要求静态图片导出成功。

## 七、设计原则

- 原始数据与派生数据分离，原始文件绝不覆盖
- 所有变换可查看、可撤销、可重新运行
- 质量检查只报告，**绝不静默填充缺失值或删除异常值**
- 前向填充/插值必须用户主动选择并提示失真风险
- 第一版**禁止**把低频数据插值成伪造的高频数据
- 不把相关关系自动解释成因果关系
- 图表生成前必须通过可信度检查（可显式跳过并说明）

## 八、已知限制（第一阶段 MVP）

- 仅导入本地文件；不接实时 API、不爬取、不执行 Excel 宏
- 图表 PNG/SVG 导出依赖 Kaleido 和本机 Chrome；HTML 导出不依赖二者
- 低频→高频插值在第一版明确禁止（防伪造数据）
- 双轴图仅支持 2 条序列，且可信度检查会强制警告
- 未做：因果推断、AI 自动分析、投资建议、云同步、公网部署、PDF/图片识别
- 中国经济协议 1.0 只接受固定 12 项指标；新增指标需同步更新生产和消费端映射
- LPR 以不规则实际发布日期存储，通用频率转换页面不自动重采样该序列
- 历史修订只新增不可变快照，暂不提供“更新原序列”模式

## 九、示例数据说明

`sample_data/` 下所有数据均为**合成数据**（虚构国家"示例国"），不代表任何真实经济
体。演示导入的序列名与图表中均标注"虚构数据"。

示例数据与生成器按本项目 MIT 许可证发布。用户导入的外部资料、数据库及第三方依赖
仍受其自身权利与许可证约束，不因使用本工具而改变。

## 十、贡献与发布

- [贡献指南](CONTRIBUTING.md)：开发环境、数据处理约束与提交要求。
- [更新记录](CHANGELOG.md)：首个开源候选版本范围。
- [发布流程](docs/RELEASING.md)：白名单打包、校验文件与首次建仓步骤。
- [MIT 许可证](LICENSE)：允许使用、修改和再分发，保留许可证及版权声明；完整条款以原文为准。

打包命令为 `python scripts/prepare_release.py`，结果在 `dist/`。发布包排除 `data/`、
虚拟环境、缓存、凭据与用户导出物。请勿直接压缩整个工作目录公开上传。

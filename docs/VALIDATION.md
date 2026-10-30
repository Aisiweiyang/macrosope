# 开源候选版本验证记录

日期：2026-10-30（Asia/Shanghai）。版本：0.1.0。

## 已执行

环境：Windows、Python 3.13.0。依赖版本快照见根目录 `constraints.txt`，其中包括
Streamlit 1.61.1、pandas 3.0.5、DuckDB 1.5.5、Plotly 6.9.0、Kaleido 1.3.0。

| 检查 | 结果与范围 |
| --- | --- |
| 完整测试 | 从白名单 ZIP 解压后的源码执行，119 passed；包含数字日期、英文 `value` 列、离线 HTML 和发布包检查 |
| 代码检查 | `ruff check macrosope app.py pages tests demo sample_data scripts` 通过 |
| 安装元数据 | 现有虚拟环境内执行 `pip install --no-build-isolation --no-index -r requirements-dev.txt` 成功构建并安装 editable 包 |
| 依赖一致性 | `pip check` 无冲突；该结果不等于全新机器联网安装验证 |
| 页面检查 | Streamlit AppTest 执行首页和 12 个功能页，初始状态无应用异常 |
| 交互流程 | AppTest 通过整数年份 JSON 导入和带单位、来源的折线图生成；保留图表可信度确认行为 |
| 默认演示 | 6 个合成数据集、21 条序列、6 步变换、1 个研究项目；数据导出和 DuckDB 备份完成，进程退出码 0 |
| 图片与 HTML | 实际生成折线图与热力图 PNG、SVG 和自包含 HTML；最终标题、图例、来源脚注和热力图色块已查看 |
| 无 Chrome 演示 | `--skip-static-images` 完成 HTML、数据导出、项目和备份流程；该命令不作为静态图片验证证据 |
| 本地数据完整性 | 对既有主数据库、原始归档与导出文件记录并复核 SHA256，共 36 个文件未改变 |
| 公开文件范围 | 93 个白名单文件，含六份生成器提供的合成样例；无数据库、用户归档、用户导出、虚拟环境或缓存 |
| 发布物 | 生成源码 ZIP、逐文件 SHA256 清单及 ZIP 校验文件；检查 ZIP CRC、清单内容与文件哈希 |
| 文档 | 本机绝对路径及过期测试数量已移除，文档内相对链接已检查 |

最初版本基线为 112 个测试；新增 7 个回归/发布检查后为 119 个。
图例名称和热力图类别轴也已加入现有测试的验收条件。

## 环境条件与限制

- 中国经济归档使用 Windows 硬链接。受限运行环境最初阻止四个既有测试；在普通本机权限下
  运行后全部通过，没有为了绕过限制改变归档的不可覆盖语义。
- Kaleido 在本机曾出现逐次启动/关闭 Chrome 的异常。演示现已按
  [官方复用浏览器方式](https://github.com/plotly/Kaleido#generate-multiple-images-faster-by-reusing-the-same-chrome-instance)
  在一次运行内复用 Chrome，并使用可写的工作区临时目录完成验证。运行日志仍可能出现
  `kopts argument is ignored` 或浏览器收尾提示；本次最终导出文件可读取，退出码为 0。
- 临时目录权限受限时，可在当前终端将 `TEMP`、`TMP` 指向自己创建的可写目录后运行；
  本次没有修改系统级环境变量或安装/替换用户浏览器。
- 页面验证基于 AppTest。浏览器截图检查未完成，不能把它表述为完整的前端像素验收。
- 文本扫描覆盖常见凭据格式和个人目录；不是完整安全审计。合成 XLSX 的作者元数据为
  `openpyxl`，没有把用户的 Excel、真实数据快照或第三方生产项目带入公开包。
- 以上结果记录发布前的本地验收。Windows 和 Ubuntu / Python 3.13 的远程执行状态见
  [GitHub Actions](https://github.com/Aisiweiyang/macrosope/actions)，实际版本发布见
  [Releases](https://github.com/Aisiweiyang/macrosope/releases)。本地结果不替代远程 CI；
  macOS 实际运行尚未验证。应用未部署公网。
- 功能测试与演示仅使用合成数据，不证明真实经济结论、预测能力或投资效果。

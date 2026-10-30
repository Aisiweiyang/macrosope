# 贡献指南

欢迎修复问题、完善文档和增加可核验的数据处理能力。项目使用 Python 3.13，公共包名为 `macrosope`。

## 开发环境

从仓库根目录执行（Windows PowerShell）：

```powershell
py -3.13 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m ruff check macrosope app.py pages tests demo sample_data scripts
```

macOS/Linux 将解释器路径替换为 `venv/bin/python`。这些平台的实际验证状态见 [验证记录](docs/VALIDATION.md)。
`requirements*.txt` 使用 `constraints.txt` 中的已验证环境快照；依赖范围统一在 `pyproject.toml` 维护。
更新依赖时需要重新验证，不要只修改快照中的版本号。

## 提交要求

- 描述具体问题、修改后的行为和实际执行的检查。未运行的验证请明确标记。
- 复现材料使用少量合成数据，不上传个人数据库、原始导入文件、备份、凭据或本机绝对路径。
- 保持原始数据与派生数据分离；清洗和变换经过 `Pipeline`，有公式、参数和可撤销记录。
- 质量检查只报告问题；不得默认填补缺失值、删除异常点或把低频数据插值为高频数据。
- 不以相关关系宣称因果，不以合成演示结果证明真实经济预测或投资效果。
- 导出继续保留 CSV 公式注入和路径穿越防护。HTML 图表需要能离线打开。
- 变更数据处理、归档或恢复行为时，补充能够复现原问题的测试；文案和格式调整按实际影响检查。

## Issue 与 Pull Request

提交 Issue 时提供版本、操作步骤、预期行为、实际错误和最小合成样例。截图请遮盖个人信息。
Pull Request 尽量围绕一个问题，避免附带重构。新增功能请说明单位、频率、口径和限制。

提交贡献表示你有权按本项目的 [MIT 许可证](LICENSE) 提供该贡献。

## 发布

维护者使用 [发布流程](docs/RELEASING.md)。公开仓库和 Release 的实际发布状态应单独核实，
本地测试通过不等于远程 CI 已通过。

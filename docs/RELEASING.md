# 发布流程

当前公开名称建议为 **Macrosope / 宏观数据工作台**，仓库名建议为 `macrosope`，
首个版本为 `v0.1.0`。这里只准备源码发布，不上传 PyPI，也不部署在线应用。

## 本地验证与打包

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m ruff check macrosope app.py pages tests demo sample_data scripts
.\venv\Scripts\python.exe demo/run_demo.py
.\venv\Scripts\python.exe scripts/prepare_release.py --check
.\venv\Scripts\python.exe scripts/prepare_release.py
```

`dist/` 中生成源码 ZIP、逐文件 SHA256 清单和 ZIP 的 SHA256 校验文件。
脚本仅收录既定源码、文档、配置和六份合成样例，不读取 `data/` 或虚拟环境。
文本扫描检查常见凭据格式和个人目录，不等于完整的安全审计；新增第三方文件仍需核对来源与授权。

没有可用 Chrome 时，`python demo/run_demo.py --skip-static-images` 可验证 HTML、数据导出
与备份流程。该模式不能记为静态图片导出通过；完整演示中的异常需要如实写入验证记录。

不要直接压缩工作目录，也不要把它整体拖入 GitHub 上传页。首次发布应从生成的干净 ZIP
解压目录开始建仓，避免工作目录中的本地资料进入 Git 历史。

## 公开仓库步骤

取得用户对目标账号、仓库名和公开发布的授权后，在**解压后的干净源码目录**执行：

```powershell
git init -b main
git add .
git diff --cached --stat
git diff --cached --check
git commit -m "Initial open-source release of Macrosope"
gh repo create macrosope --public --source . --remote origin --push --description "Local macroeconomic data workbench with Streamlit, DuckDB and Plotly"
```

发布前检查暂存文件清单，并使用已配置的真实维护者 Git 身份；不要由工具虚构作者身份。
如果需要选择其他账号或组织，先在 GitHub CLI 中切换到正确账号，再执行创建命令。

推送后查看并等待本次提交的 GitHub Actions 完成；只有真实执行成功后才能宣称 CI 通过。
然后按已获授权的范围创建 `v0.1.0` 标签与 Release，附上源码 ZIP 和校验文件。
本流程不创建付费资源、不修改其他仓库，也不发布用户数据库。

## 检查边界

- `LICENSE` 为 MIT，版权行使用项目贡献者名称；合成样例与生成器使用相同许可证。
- 依赖仍使用各自许可证，本项目没有重新许可或打包第三方依赖。
- `docs/VALIDATION.md` 记录本地实测；CI 配置文件本身不代表已经运行。
- 如果改动版本、源码或文档，需要重新打包，不能继续引用旧 SHA256。
- 用户数据默认保存在本地；若使用环境变量改了存储路径，维护者也需要自行排除该路径。

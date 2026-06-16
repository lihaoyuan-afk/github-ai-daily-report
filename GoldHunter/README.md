# GoldHunter

GoldHunter 是一个黄金宏观环境自动监控项目。它会抓取黄金、美债收益率、美元指数、黄金 ETF 资金流向代理和原油价格，保存历史数据，并生成 Markdown 日报，判断当前环境对黄金是偏多、偏空还是震荡。

## 监控指标

- 黄金价格：优先使用 `XAUUSD=X`，失败后回退到 `GC=F` 或 `GLD`
- 美国10年期国债收益率：`^TNX`
- 美元指数：优先使用 `DX-Y.NYB`，失败后回退到 `DX=F` 或 `UUP`
- 黄金 ETF 资金流向代理：使用 `GLD` 的价格和成交量生成方向代理值
- 原油价格：优先使用 WTI `CL=F`，失败后回退到 Brent `BZ=F`

## 打分规则

- US10Y 下降：`+1`；上升：`-1`
- DXY 下降：`+1`；上升：`-1`
- 黄金价格上涨：`+1`；下跌：`-1`
- ETF 资金流向代理为正：`+1`；为负：`-1`
- 原油明显回落：`+0.5`；明显上涨：`-0.5`

综合得分 `>= 2` 判断为偏多，`<= -2` 判断为偏空，其余判断为震荡。

## 本地安装

```powershell
cd "E:\新建文件夹 (4)\fundconnecthk.com-main\GoldHunter"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux：

```bash
cd /path/to/GoldHunter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 本地运行

```bash
python main.py
```

运行后会生成或更新：

- `data/history.csv`
- `reports/daily_report.md`

如果某个公开数据源暂时不可用，程序会记录提示并继续生成报告，不会因为单个指标失败而崩溃。

## GitHub 全流程自动化

仓库根目录已配置：

```text
.github/workflows/goldhunter-daily.yml
```

自动化流程会做这些事：

- 每天北京时间 07:30 自动运行一次
- 支持在 GitHub Actions 页面手动点击 `Run workflow`
- 安装 Python 依赖
- 执行 `GoldHunter/main.py`
- 更新 `GoldHunter/data/history.csv`
- 生成 `GoldHunter/reports/daily_report.md`
- 生成简短中文邮件摘要 `GoldHunter/reports/email_summary.md`
- 把更新后的历史数据和日报自动提交回 GitHub 仓库
- 同时上传一份 30 天保留期的 Actions artifact

启用前请确认 GitHub 仓库设置：

1. 进入 `Settings`。
2. 打开 `Actions` -> `General`。
3. 在 `Workflow permissions` 中选择 `Read and write permissions`。
4. 保存设置。

如需自动发送邮件，请在 `Settings` -> `Secrets and variables` -> `Actions` 中添加：

- `MAIL_SERVER`：SMTP 服务器，例如 `smtp.gmail.com`
- `MAIL_PORT`：SMTP 端口，默认可用 `465`
- `MAIL_USERNAME`：发件邮箱账号
- `MAIL_PASSWORD`：发件邮箱密码或应用专用密码
- `MAIL_TO`：收件邮箱
- `MAIL_FROM`：发件人地址，可与 `MAIL_USERNAME` 相同

邮件正文只使用中文，并尽量保持简短。

之后把代码推送到 GitHub，GitHub Actions 就会按计划自动运行。

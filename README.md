# GoldHunter

[![GoldHunter Daily Report](https://github.com/lihaoyuan-afk/github-ai-daily-report/actions/workflows/goldhunter-daily.yml/badge.svg)](https://github.com/lihaoyuan-afk/github-ai-daily-report/actions/workflows/goldhunter-daily.yml)

GoldHunter 是一个黄金宏观环境自动监控项目。它会每天抓取黄金、美债收益率、美元指数、黄金 ETF 资金流向代理和原油价格，自动保存历史数据，并生成一份中文 Markdown 日报，判断当前环境对黄金是偏多、偏空还是震荡。

项目已经接入 GitHub Actions，可以实现无人值守运行、自动生成报告、自动提交结果，并可选发送一封简短中文邮件。

## 当前能力

| 能力 | 说明 |
| --- | --- |
| 自动抓取数据 | 使用 `yfinance` 获取公开市场数据 |
| 保存历史 | 每次运行更新 `GoldHunter/data/history.csv` |
| 对比变化 | 自动比较上一可用交易日和 7 日前变化 |
| 多空打分 | 根据利率、美元、黄金、ETF、原油五类指标综合打分 |
| 生成日报 | 输出 `GoldHunter/reports/daily_report.md` |
| 邮件摘要 | 输出 `GoldHunter/reports/email_summary.md`，内容简短中文 |
| GitHub 自动化 | 定时运行、手动运行、自动提交报告结果 |

## 数据源

| 指标 | 优先代码 | 备用代码 | 用途 |
| --- | --- | --- | --- |
| 黄金价格 | `XAUUSD=X` | `GC=F`、`GLD` | 判断黄金自身价格动能 |
| 美国10年期国债收益率 | `^TNX` | 无 | 衡量实际利率和机会成本压力 |
| 美元指数 | `DX-Y.NYB` | `DX=F`、`UUP` | 衡量美元强弱对黄金的影响 |
| 黄金 ETF 资金流向代理 | `GLD` | 无 | 用价格和成交量估算资金方向 |
| 原油价格 | `CL=F` | `BZ=F` | 观察通胀和利率预期扰动 |

公开数据源可能会出现临时不可用。程序会记录提示并继续生成报告，不会因为单个指标失败而中断。

## 打分规则

| 条件 | 得分 | 含义 |
| --- | ---: | --- |
| US10Y 下降 | `+1` | 利率压力下降，利多黄金 |
| US10Y 上升 | `-1` | 持有黄金机会成本上升 |
| DXY 下降 | `+1` | 美元走弱，利多黄金 |
| DXY 上升 | `-1` | 美元走强，压制黄金 |
| 黄金价格上涨 | `+1` | 价格动能偏强 |
| 黄金价格下跌 | `-1` | 价格动能偏弱 |
| ETF 代理资金流入 | `+1` | ETF 端买盘偏强 |
| ETF 代理资金流出 | `-1` | ETF 端卖盘偏强 |
| 原油明显回落 | `+0.5` | 通胀压力边际缓和 |
| 原油明显上涨 | `-0.5` | 通胀和利率预期可能升温 |

综合判断：

| 综合得分 | 判断 |
| ---: | --- |
| `>= 2` | 偏多 |
| `<= -2` | 偏空 |
| 其他 | 震荡 |

## 自动化流程

```mermaid
flowchart LR
    A["GitHub Actions 定时触发"] --> B["安装 Python 依赖"]
    B --> C["抓取宏观与市场数据"]
    C --> D["更新 history.csv"]
    D --> E["计算多空得分"]
    E --> F["生成 Markdown 日报"]
    E --> G["生成中文邮件摘要"]
    F --> H["自动提交到 GitHub"]
    G --> I["可选发送邮件"]
```

## 输出文件

| 文件 | 说明 |
| --- | --- |
| `GoldHunter/data/history.csv` | 每日历史数据 |
| `GoldHunter/reports/daily_report.md` | 完整中文日报 |
| `GoldHunter/reports/email_summary.md` | 简短中文邮件摘要 |

邮件摘要示例：

```text
日期：2026-06-16
结论：偏多
得分：3
简述：利多：黄金价格、美元指数；利空：原油价格
```

## 项目结构

```text
GoldHunter/
├─ main.py              # 主入口
├─ data_fetcher.py      # 数据抓取
├─ analyzer.py          # 指标分析和打分
├─ report.py            # 报告和邮件摘要生成
├─ config.py            # 配置项
├─ requirements.txt     # Python 依赖
├─ data/
│  └─ history.csv       # 运行后生成
└─ reports/
   ├─ daily_report.md   # 运行后生成
   └─ email_summary.md  # 运行后生成
```

## GitHub Actions

工作流文件：

```text
.github/workflows/goldhunter-daily.yml
```

触发方式：

| 方式 | 说明 |
| --- | --- |
| 定时运行 | 每天北京时间 `07:30` 自动执行 |
| 手动运行 | 在 GitHub Actions 页面点击 `Run workflow` |
| 代码变更 | 修改 `GoldHunter` 或工作流文件后自动执行 |

自动化会执行：

1. 拉取仓库代码。
2. 安装 Python 依赖。
3. 运行 `GoldHunter/main.py`。
4. 生成数据和报告。
5. 如已配置邮箱密钥，发送简短中文邮件。
6. 自动提交 `data` 和 `reports` 目录的变化。

## 邮件配置

如需自动发送邮件，请在仓库中添加 Actions Secrets：

路径：`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

| Secret | 必填 | 示例 |
| --- | --- | --- |
| `MAIL_SERVER` | 是 | `smtp.gmail.com` |
| `MAIL_PORT` | 否 | `465` 或 `587` |
| `MAIL_USERNAME` | 是 | 发件邮箱账号 |
| `MAIL_PASSWORD` | 是 | 邮箱密码或应用专用密码 |
| `MAIL_TO` | 是 | 收件邮箱 |
| `MAIL_FROM` | 否 | 发件人地址 |

邮件正文只输出中文摘要，并保持尽可能简短。

## 本地运行

Windows PowerShell：

```powershell
cd "E:\新建文件夹 (4)\fundconnecthk.com-main\GoldHunter"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

macOS / Linux：

```bash
cd /path/to/GoldHunter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 注意事项

- 本项目使用公开数据源，数据可能延迟、缺失或临时不可用。
- ETF 资金流向是基于 GLD 价格和成交量生成的代理指标，不等同于官方持仓变化。
- 报告仅用于宏观环境观察和研究记录，不构成投资建议。

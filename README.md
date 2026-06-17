# GoldHunter

[![GoldHunter Daily Report](https://github.com/lihaoyuan-afk/github-ai-daily-report/actions/workflows/goldhunter-daily.yml/badge.svg)](https://github.com/lihaoyuan-afk/github-ai-daily-report/actions/workflows/goldhunter-daily.yml)

GoldHunter 现在是一个 **黄金大跌风险预警系统**。它不预测明天涨跌，而是每天检查未来 10-30 个交易日出现 8%-12% 以上回撤的风险是否升高。

每日邮件只回答一句核心问题：

```text
当前黄金大跌风险：绿色 / 黄色 / 橙色 / 红色
主要风险来自：实际利率、美元、ETF流出、CFTC持仓、价格结构、流动性压力
```

## 风险灯号

| 分数 | 灯号 | 含义 |
| ---: | --- | --- |
| 0-30 | 绿色 | 大跌风险低，属于正常波动 |
| 31-55 | 黄色 | 压力开始上升，但还不是系统性危险 |
| 56-75 | 橙色 | 大跌风险明显升高，需要认真防守 |
| 76-100 | 红色 | 多个核心信号共振，存在急跌风险 |

## 模块权重

| 模块 | 权重 | 观察重点 |
| --- | ---: | --- |
| 实际利率与美元压力 | 30% | DFII10、DGS2、DGS10、DTWEXBGS |
| 黄金价格结构 | 25% | MA50、MA100、MA200、60日回撤、波动率 |
| ETF资金流压力 | 15% | GLD官方黄金持仓吨数变化 |
| CFTC持仓拥挤与反转 | 15% | COMEX Gold Managed Money 净多头 |
| 美元流动性与抛售压力 | 10% | 高收益债利差、VIX、NFCI、SOFR-IORB |
| 事件风险 | 5% | CPI、PCE、FOMC、NFP等，暂以人工提示为主 |

最终分数：

```text
Gold Crash Risk Score =
0.30 × 实际利率与美元压力
+ 0.25 × 黄金价格结构压力
+ 0.15 × ETF资金流压力
+ 0.15 × CFTC持仓压力
+ 0.10 × 美元流动性压力
+ 0.05 × 事件风险
```

## 数据源

| 数据 | 来源 | 更新频率 |
| --- | --- | --- |
| GLD价格与黄金持仓 | SPDR Gold Shares Historical Archive | 日度 |
| 10年实际利率 | FRED `DFII10` / Federal Reserve | 日度 |
| 2年美债收益率 | FRED `DGS2` / Federal Reserve H.15 | 日度 |
| 10年美债收益率 | FRED `DGS10` / Federal Reserve H.15 | 日度 |
| 美元强弱指标 | FRED `DTWEXBGS` / Federal Reserve H.10 | 日度 |
| 高收益债利差 | FRED `BAMLH0A0HYM2` / ICE BofA | 日度 |
| VIX | FRED `VIXCLS` / CBOE | 日度 |
| NFCI | FRED `NFCI` / Chicago Fed | 周度 |
| SOFR / IORB | FRED `SOFR`、`IORB` | 日度 |
| 银行准备金 | FRED `WRESBAL` | 周度 |
| 黄金期货持仓 | CFTC Disaggregated Futures Only, COMEX Gold | 周度 |

说明：ICE DXY、LBMA金价、CME实时行情通常需要商业授权。当前版本优先使用可自动抓取、无需密钥的官方公开源。

## 报告输出

运行后会生成：

| 文件 | 说明 |
| --- | --- |
| `GoldHunter/data/history.csv` | 每日历史数据 |
| `GoldHunter/reports/daily_report.md` | 完整风险日报 |
| `GoldHunter/reports/email_summary.md` | 邮件摘要 |
| `GoldHunter/reports/email_test_status.md` | 最近一次邮件测试状态 |

邮件摘要示例：

```text
日期：2026-06-18
黄金大跌风险：绿色
分数：18.4/100
主要原因：暂无多组风险共振
判断：当前更像正常波动，尚未出现大跌风险共振。
```

## 黄色/橙色/红色规则

黄色预警：满足任意两个早期压力信号，例如黄金跌破 MA50、10年实际利率20日上升超过 20bp、美元指数20日上涨超过 2%、GLD开始流出、Managed Money净多头下降。

橙色预警：满足任意三个较大回撤风险信号，例如黄金跌破 MA100、60日回撤超过 6%、实际利率60日上升超过 40bp、美元60日上涨超过 4%、ETF明显流出、CFTC多头4周下降超过 20%、高收益债利差快速扩大。

红色预警：黄金跌破 MA100 或 MA200，同时实际利率、美元、ETF、CFTC 持仓多组信号共振恶化，或者总分高于 76。

## GitHub Actions

工作流文件：

```text
.github/workflows/goldhunter-daily.yml
```

触发方式：

| 方式 | 说明 |
| --- | --- |
| 定时运行 | 每天北京时间 09:00 自动执行 |
| 手动运行 | 在 GitHub Actions 页面点击 `Run workflow` |
| 代码变更 | 修改 `GoldHunter` 或工作流文件后自动执行 |

自动化会执行：

1. 拉取仓库代码。
2. 安装 Python 依赖。
3. 运行 `GoldHunter/main.py`。
4. 生成风险日报和邮件摘要。
5. 如已配置邮箱密钥，发送简短中文邮件。
6. 自动提交 `data` 和 `reports` 目录的变化。

## 邮件配置

在仓库中添加 Actions Secrets：

路径：`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

| Secret | 示例 |
| --- | --- |
| `MAIL_SERVER` | `smtp.163.com` |
| `MAIL_PORT` | `465` |
| `MAIL_USERNAME` | `15738118466@163.com` |
| `MAIL_PASSWORD` | 网易邮箱客户端授权码 |
| `MAIL_TO` | `15738118466@163.com` |
| `MAIL_FROM` | `15738118466@163.com` |

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

- 这是风险雷达，不是自动交易系统。
- 官方公开数据可能延迟、缺失或临时不可用。
- WGC全球ETF月度流向和事件日历尚未自动接入，后续可继续扩展。
- 报告仅用于宏观风险观察和研究记录，不构成投资建议。

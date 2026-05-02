# 🤖 AI 前沿日报

每日自动抓取 AI 领域最新动态，去重后通过邮件发送。

## 数据源
- **GitHub Releases** — 追踪 Anthropic、OpenAI、Google、Meta、HuggingFace 等重点仓库
- **新项目发现** — 搜索过去24小时新创建的 AI 相关项目
- **Hacker News** — AI/LLM/Claude 相关热门讨论
- **公司博客** — Anthropic、OpenAI 官方公告

## 去重机制
- 用 `seen_urls.json` 记录已发送的 URL
- 超过 30 天的记录自动清理
- 每次运行后自动 commit 更新记录

## 配置 (GitHub Secrets)
- `SMTP_SERVER` / `SMTP_PORT` — 邮件服务器（默认 163 邮箱）
- `SENDER_ADDRESS` — 发件邮箱
- `SENDER_PASSWORD` — 邮箱授权码
- `RECIPIENT_EMAIL` — 收件邮箱
- `GITHUB_TOKEN` — GitHub Token（用于 API 调用）

## 定时
每天北京时间早 8 点自动发送。

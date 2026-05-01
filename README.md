# GitHub AI 热门日报 - 自动化邮件报告

## 📋 功能说明

每天自动从 GitHub 抓取 AI 领域最热门的 10 个项目，并发送包含**中文介绍**的邮件报告到你的 Gmail。

## 🚀 部署步骤（约 5 分钟）

### 第 1 步：创建 GitHub 仓库

1. 登录 GitHub → 右上角 **+** → **New repository**
2. 仓库名：`github-ai-daily-report`
3. 选择 **Public**（免费用户必须公开）
4. 勾选 **Add a README file**
5. 点击 **Create repository**

### 第 2 步：上传文件

在仓库页面：
1. 点击 **Add file** → **Upload files**
2. 拖拽上传这两个文件：
   - `report.py`
   - `.github/workflows/daily-report.yml`
3. 点击 **Commit changes**

### 第 3 步：添加 Secrets（密钥）

1. 进入仓库 → **Settings** → 左侧 **Secrets and variables** → **Actions**
2. 点击 **New repository secret**，依次添加：

| Name | Value |
|------|-------|
| `GMAIL_ADDRESS` | `zli638653@gmail.com` |
| `GMAIL_APP_PASSWORD` | `ozdw kgyp mnnd ctjw` |
| `RECIPIENT_EMAIL` | `zli638653@gmail.com` |

### 第 4 步：启用 Actions

1. 进入仓库 → **Actions** 标签
2. 点击 **I understand my workflows, go ahead and enable them**
3. 点击 **Daily Report** → **Run workflow** 手动测试一次

### 第 5 步：验证

- 检查 Gmail 是否收到测试邮件
- 之后每天北京时间 8:00 自动执行

## 📁 文件结构

```
github-ai-daily-report/
├── .github/
│   └── workflows/
│       └── daily-report.yml    # GitHub Actions 工作流
├── report.py                   # 主脚本
└── README.md                   # 说明文档
```

## ⚙️ 自定义配置

编辑 `report.py` 中的 `search_queries` 可修改搜索关键词：

```python
search_queries = [
    f"LLM stars:>50 pushed:>{week_ago}",
    f"AI agent stars:>30 pushed:>{week_ago}",
    # 添加更多关键词...
]
```

## 🔧 常见问题

**Q: 为什么选择 GitHub Actions？**
A: 免费、稳定、无需服务器、电脑关机也能运行。

**Q: 如何修改发送时间？**
A: 编辑 `.github/workflows/daily-report.yml` 中的 cron 表达式：
```yaml
- cron: '0 0 * * *'  # UTC 0:00 = 北京时间 8:00
```

**Q: 如何暂停/恢复？**
A: 进入仓库 → Actions → 点击 workflow → Disable/Enable workflow

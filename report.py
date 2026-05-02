#!/usr/bin/env python3
"""
AI 前沿日报 - 每日自动抓取 AI 领域最新动态并去重发送
数据源: GitHub Releases / 新项目 / Hacker News / Anthropic & OpenAI 博客
"""

import json
import os
import re
import smtplib
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from html.parser import HTMLParser

# ─── 配置 ───────────────────────────────────────────────
SEEN_FILE = "seen_urls.json"
MAX_SEEN_AGE_DAYS = 30  # 超过30天的记录自动清理

def get_config():
    return {
        "smtp_server": os.environ.get("SMTP_SERVER", "smtp.163.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "994")),
        "sender_address": os.environ.get("SENDER_ADDRESS", ""),
        "sender_password": os.environ.get("SENDER_PASSWORD", ""),
        "recipient_email": os.environ.get("RECIPIENT_EMAIL", ""),
        "github_token": os.environ.get("GITHUB_TOKEN", ""),
    }

# ─── 去重管理 ──────────────────────────────────────────────
def load_seen_urls():
    """从 seen_urls.json 加载已发送的 URL"""
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 清理超过 MAX_SEEN_AGE_DAYS 的记录
        cutoff = (datetime.now() - timedelta(days=MAX_SEEN_AGE_DAYS)).isoformat()
        return {
            url: ts for url, ts in data.items()
            if ts > cutoff
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_seen_urls(seen):
    """保存已发送的 URL 到 seen_urls.json"""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

def filter_new(items, seen):
    """过滤掉已发送的条目，返回新条目"""
    new_items = []
    for item in items:
        url = item.get("url", "")
        if url and url not in seen:
            new_items.append(item)
    return new_items

# ─── 数据源: GitHub Releases ─────────────────────────────────
# 重点追踪: Anthropic, OpenAI, Google, Meta, HuggingFace 等
WATCHED_REPOS = [
    "anthropics/claude-code",
    "anthropics/anthropic-sdk-python",
    "anthropics/anthropic-sdk-typescript",
    "openai/openai-python",
    "openai/openai-node",
    "openai/codex",
    "google/generative-ai-python",
    "meta-llama/llama",
    "huggingface/transformers",
    "huggingface/diffusers",
    "vllm-project/vllm",
    "langchain-ai/langchain",
    "crewAIInc/crewAI",
    "Significant-Gravitas/AutoGPT",
    "microsoft/semantic-kernel",
    "ollama/ollama",
    "lm-sys/FastChat",
    "ggml-org/llama.cpp",
    "pydantic/pydantic-ai",
    "instructor-ai/instructor",
    "BerriAI/litellm",
]

def fetch_github_releases(token):
    """获取重点仓库的最近 release（24小时内）"""
    items = []
    yesterday = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    for repo in WATCHED_REPOS:
        try:
            url = f"https://api.github.com/repos/{repo}/releases?per_page=5"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/vnd.github.v3+json")
            if token:
                req.add_header("Authorization", f"token {token}")
            else:
                req.add_header("User-Agent", "AI-Daily-Report")

            with urllib.request.urlopen(req, timeout=10) as resp:
                releases = json.loads(resp.read().decode())

            for rel in releases:
                published = rel.get("published_at", "")[:10]
                if published >= yesterday:
                    items.append({
                        "source": f"GitHub Release · {repo.split('/')[1]}",
                        "title": f"🚀 {repo} → {rel['name'] or rel['tag_name']}",
                        "url": rel["html_url"],
                        "description": _strip_html(rel.get("body", ""))[:200],
                        "date": published,
                    })
        except Exception as e:
            print(f"  ⚠️  {repo} release 获取失败: {e}")

    return items

def fetch_github_new_repos(token):
    """搜索过去24小时新创建的 AI 相关项目"""
    items = []
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    queries = [
        "claude created:>{date}",
        "AI agent created:>{date}",
        "LLM created:>{date}",
        "mcp server created:>{date}",
        "AI tool created:>{date}",
    ]

    for q in queries:
        try:
            query = q.format(date=yesterday)
            encoded = urllib.parse.quote(query)
            url = f"https://api.github.com/search/repositories?q={encoded}&sort=stars&order=desc&per_page=3"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/vnd.github.v3+json")
            if token:
                req.add_header("Authorization", f"token {token}")
            else:
                req.add_header("User-Agent", "AI-Daily-Report")

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            for repo in data.get("items", []):
                if repo["stargazers_count"] >= 5:
                    items.append({
                        "source": "GitHub 新项目",
                        "title": f"📦 {repo['full_name']}",
                        "url": repo["html_url"],
                        "description": repo.get("description", "")[:200],
                        "stars": repo["stargazers_count"],
                        "date": repo["created_at"][:10],
                    })
        except Exception as e:
            print(f"  ⚠️  搜索失败 '{q}': {e}")

    return items

# ─── 数据源: Hacker News (AI 相关) ─────────────────────────
def fetch_hackernews_ai():
    """从 Hacker News 获取 AI 相关热门文章"""
    items = []
    try:
        # HN Search API
        url = "https://hn.algolia.com/api/v1/search?tags=story&query=AI%20OR%20LLM%20OR%20Claude%20OR%20GPT&numericFilters=created_at_i>{}".format(
            int((datetime.now() - timedelta(days=1)).timestamp())
        )
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "AI-Daily-Report")

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        seen_ids = set()
        for hit in data.get("hits", []):
            if hit["points"] >= 20 and hit["objectID"] not in seen_ids:
                seen_ids.add(hit["objectID"])
                items.append({
                    "source": f"Hacker News · {hit['points']} points",
                    "title": f"💬 {hit['title']}",
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    "description": f"by {hit.get('author', 'unknown')}",
                    "date": hit.get("created_at", "")[:10],
                })
    except Exception as e:
        print(f"  ⚠️  Hacker News 获取失败: {e}")

    return items[:8]

# ─── 数据源: Anthropic / OpenAI 博客 ──────────────────────────
def fetch_company_blogs():
    """检查 Anthropic 和 OpenAI 的最新博客/公告"""
    items = []

    # Anthropic blog RSS
    try:
        url = "https://www.anthropic.com/rss.xml"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "AI-Daily-Report")
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml = resp.read().decode("utf-8", errors="replace")

        yesterday = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        # 简单解析 RSS
        for match in re.finditer(
            r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>.*?<description>(.*?)</description>.*?</item>",
            xml, re.DOTALL
        ):
            title, link, pub_date, desc = match.groups()
            title = _strip_html(title).strip()
            desc = _strip_html(desc).strip()[:200]
            # 粗略检查是否近期发布
            items.append({
                "source": "Anthropic Blog",
                "title": f"📝 {title}",
                "url": link.strip(),
                "description": desc,
                "date": pub_date[:16] if pub_date else "",
            })
    except Exception as e:
        print(f"  ⚠️  Anthropic 博客获取失败: {e}")

    # OpenAI blog RSS
    try:
        url = "https://openai.com/blog/rss.xml"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "AI-Daily-Report")
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml = resp.read().decode("utf-8", errors="replace")

        for match in re.finditer(
            r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<pubDate>(.*?)</pubDate>.*?</item>",
            xml, re.DOTALL
        ):
            title, link, pub_date = match.groups()
            title = _strip_html(title).strip()
            items.append({
                "source": "OpenAI Blog",
                "title": f"📝 {title}",
                "url": link.strip(),
                "description": "",
                "date": pub_date[:16] if pub_date else "",
            })
    except Exception as e:
        print(f"  ⚠️  OpenAI 博客获取失败: {e}")

    return items[:5]

# ─── 工具函数 ──────────────────────────────────────────────
class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
    def handle_data(self, d):
        self.result.append(d)
    def get_text(self):
        return "".join(self.result)

def _strip_html(html_str):
    if not html_str:
        return ""
    s = _HTMLStripper()
    try:
        s.feed(html_str)
        return s.get_text()
    except:
        return html_str

# ─── 报告生成 ──────────────────────────────────────────────
def generate_report(all_items, has_new):
    """生成 HTML 和纯文本报告"""
    date_str = datetime.now().strftime("%Y年%m月%d日")

    if not has_new:
        # 今日无新内容
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:30px;border-radius:12px;text-align:center;">
<h1 style="margin:0;">🤖 AI 前沿日报</h1>
<p style="margin:10px 0 0;opacity:0.9;">📅 {date_str}</p>
</div>
<div style="background:#fff;border-radius:8px;padding:30px;margin-top:20px;text-align:center;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
<p style="font-size:18px;color:#6a737d;">📭 今日暂无新的 AI 动态</p>
<p style="color:#999;font-size:14px;">所有内容已在昨日报告中发送过</p>
</div>
<div style="text-align:center;color:#6a737d;font-size:12px;margin-top:30px;border-top:1px solid #eee;padding-top:20px;">
📧 此报告由 GitHub Actions 自动生成
</div>
</body></html>"""

        text = f"""🤖 AI 前沿日报
{'=' * 40}
📅 {date_str}

📭 今日暂无新的 AI 动态
   所有内容已在昨日报告中发送过

{'=' * 40}
📧 此报告由 GitHub Actions 自动生成
"""
        return html, text

    # 有新内容
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:650px;margin:0 auto;padding:20px;background:#f5f5f5;">
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:30px;border-radius:12px;text-align:center;">
<h1 style="margin:0;">🤖 AI 前沿日报</h1>
<p style="margin:10px 0 0;opacity:0.9;">📅 {date_str} | {len(all_items)} 条新动态</p>
</div>
"""

    text = f"""🤖 AI 前沿日报
{'=' * 40}
📅 {date_str} | {len(all_items)} 条新动态

"""

    for i, item in enumerate(all_items, 1):
        source = item.get("source", "")
        title = item["title"]
        url = item["url"]
        desc = item.get("description", "")

        stars_html = ""
        stars_text = ""
        if "stars" in item:
            stars_html = f'<span style="margin-left:8px;color:#e36209;">⭐ {item["stars"]:,}</span>'
            stars_text = f" | ⭐ {item['stars']:,}"

        html += f"""
<div style="background:#fff;border-radius:8px;padding:18px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
  <div style="font-size:12px;color:#6a737d;margin-bottom:6px;">📌 {source}</div>
  <a href="{url}" style="color:#0366d6;text-decoration:none;font-size:16px;font-weight:600;" target="_blank">{title}</a>{stars_html}
  {f'<p style="color:#586069;margin:8px 0 0;font-size:13px;line-height:1.5;">{desc}</p>' if desc else ''}
</div>
"""

        text += f"""#{i} [{source}]
   {title}{stars_text}
   {desc}
   🔗 {url}

"""

    html += f"""
<div style="text-align:center;color:#6a737d;font-size:12px;margin-top:30px;border-top:1px solid #eee;padding-top:20px;">
📧 此报告由 GitHub Actions 自动生成
</div>
</body></html>"""

    text += f"""{'=' * 40}
📧 此报告由 GitHub Actions 自动生成
"""

    return html, text

# ─── 邮件发送 ──────────────────────────────────────────────
def send_email(config, subject, html, text):
    msg = MIMEMultipart("alternative")
    msg["From"] = f"AI Daily <{config['sender_address']}>"
    msg["To"] = config["recipient_email"]
    msg["Subject"] = subject

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"],
                              timeout=30, context=context) as server:
            server.login(config["sender_address"], config["sender_password"])
            server.send_message(msg)
        print(f"✅ 邮件已发送至 {config['recipient_email']}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False

# ─── 主流程 ────────────────────────────────────────────────
def main():
    print("🚀 AI 前沿日报生成中...")

    config = get_config()
    if not config["sender_address"] or not config["sender_password"]:
        print("⚠️  请设置环境变量: SENDER_ADDRESS, SENDER_PASSWORD, RECIPIENT_EMAIL")
        return False

    # 加载已发送记录
    seen = load_seen_urls()
    print(f"📋 已发送记录: {len(seen)} 条")

    # 收集所有数据源
    all_items = []
    print("📡 [1/4] 检查 GitHub Releases...")
    all_items.extend(fetch_github_releases(config["github_token"]))

    print("📡 [2/4] 搜索新 AI 项目...")
    all_items.extend(fetch_github_new_repos(config["github_token"]))

    print("📡 [3/4] 检查 Hacker News...")
    all_items.extend(fetch_hackernews_ai())

    print("📡 [4/4] 检查公司博客...")
    all_items.extend(fetch_company_blogs())

    print(f"📊 共获取 {len(all_items)} 条信息")

    # 去重
    new_items = filter_new(all_items, seen)
    print(f"🆕 新内容: {len(new_items)} 条 (已过滤 {len(all_items) - len(new_items)} 条重复)")

    # 生成报告
    has_new = len(new_items) > 0
    report_items = new_items if has_new else []
    html, text = generate_report(report_items, has_new)

    # 发送
    date_str = datetime.now().strftime("%m/%d")
    if has_new:
        subject = f"🤖 AI 前沿日报 - {date_str} ({len(new_items)}条新动态)"
    else:
        subject = f"🤖 AI 前沿日报 - {date_str} (暂无新内容)"

    success = send_email(config, subject, html, text)

    # 更新已发送记录
    if has_new:
        now = datetime.now().isoformat()
        for item in new_items:
            url = item.get("url", "")
            if url:
                seen[url] = now
        save_seen_urls(seen)
        print(f"💾 已更新去重记录 (共 {len(seen)} 条)")

    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

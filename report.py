#!/usr/bin/env python3
"""
GitHub AI 热门项目日报
每日自动抓取 GitHub 上 AI 相关的热门仓库并发送邮件报告
"""

import json
import os
import smtplib
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# 配置 - 从环境变量读取（GitHub Actions Secrets）
def get_config():
    return {
        'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.163.com'),
        'smtp_port': int(os.environ.get('SMTP_PORT', '994')),
        'sender_address': os.environ.get('SENDER_ADDRESS', ''),
        'sender_password': os.environ.get('SENDER_PASSWORD', ''),
        'recipient_email': os.environ.get('RECIPIENT_EMAIL', ''),
        'report_title': 'GitHub AI 热门项目日报',
        'max_results': 10,
        'search_keywords': [
            'artificial intelligence',
            'machine learning',
            'deep learning',
            'LLM',
            'GPT',
            'transformer',
            'neural network',
            'NLP',
            'computer vision',
            'reinforcement learning'
        ]
    }

def fetch_github_trending(keywords, max_results=10):
    """从 GitHub API 搜索最近一周内更新的 AI 相关热门仓库"""
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    all_repos = []
    seen_ids = set()
    
    search_queries = [
        f"LLM stars:>50 pushed:>{week_ago}",
        f"AI agent stars:>30 pushed:>{week_ago}",
        f"machine learning stars:>100 pushed:>{week_ago}",
        f"deep learning stars:>80 pushed:>{week_ago}",
        f"GPT stars:>50 pushed:>{week_ago}",
    ]
    
    for query in search_queries:
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=stars&order=desc&per_page=5"
            
            req = urllib.request.Request(url)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
                
                for repo in data.get('items', []):
                    if repo['id'] not in seen_ids:
                        seen_ids.add(repo['id'])
                        all_repos.append({
                            'name': repo['full_name'],
                            'url': repo['html_url'],
                            'description': repo.get('description', ''),
                            'stars': repo.get('stargazers_count', 0),
                            'forks': repo.get('forks_count', 0),
                            'language': repo.get('language', 'Unknown'),
                            'topics': repo.get('topics', []),
                            'updated_at': repo.get('updated_at', '')
                        })
        except Exception as e:
            print(f"⚠️  搜索 '{query}' 失败: {e}")
            continue
    
    # 按星标数排序，取 top N
    all_repos.sort(key=lambda x: x['stars'], reverse=True)
    return all_repos[:max_results]

def format_report_html(repos, config):
    """格式化 HTML 邮件报告"""
    date_str = datetime.now().strftime('%Y年%m月%d日')
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
.header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; text-align: center; margin-bottom: 20px; }}
.header h1 {{ margin: 0; font-size: 24px; }}
.header p {{ margin: 10px 0 0; opacity: 0.9; }}
.repo-card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.repo-name {{ color: #0366d6; text-decoration: none; font-size: 18px; font-weight: 600; }}
.repo-name:hover {{ text-decoration: underline; }}
.repo-desc {{ color: #586069; margin: 10px 0; font-size: 14px; line-height: 1.5; }}
.repo-stats {{ display: flex; gap: 15px; font-size: 14px; color: #586069; }}
.stat {{ display: flex; align-items: center; gap: 4px; }}
.language-badge {{ background: #e1e4e8; padding: 2px 8px; border-radius: 12px; font-size: 12px; }}
.topics {{ margin-top: 10px; }}
.topic {{ background: #f1f8ff; color: #0366d6; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-right: 5px; }}
.footer {{ text-align: center; color: #6a737d; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }}
</style>
</head>
<body>
<div class="header">
    <h1>🤖 {config['report_title']}</h1>
    <p>📅 {date_str} | 数据来源: GitHub | 近期热门项目精选</p>
</div>
"""
    
    if not repos:
        html += '<p style="text-align: center; color: #6a737d;">暂无热门 AI 项目</p>'
    else:
        for i, repo in enumerate(repos, 1):
            topics_html = ''.join(f'<span class="topic">{t}</span>' for t in repo.get('topics', [])[:5])
            html += f"""
<div class="repo-card">
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 24px; font-weight: bold; color: #667eea;">#{i}</span>
        <a href="{repo['url']}" class="repo-name" target="_blank">{repo['name']}</a>
    </div>
    <p class="repo-desc">{repo['description'][:120] if repo['description'] else '暂无描述'}</p>
    <div class="repo-stats">
        <span class="stat">⭐ {repo['stars']:,}</span>
        <span class="stat">🍴 {repo['forks']:,}</span>
        <span class="language-badge">{repo['language']}</span>
    </div>
    {f'<div class="topics">{topics_html}</div>' if topics_html else ''}
</div>
"""
    
    html += f"""
<div class="footer">
    <p>📧 此报告由 GitHub Actions 自动生成并发送</p>
    <p>🔗 <a href="https://github.com/trending">查看更多 GitHub 热门项目</a></p>
</div>
</body>
</html>
"""
    return html

def format_report_text(repos, config):
    """格式化纯文本邮件报告"""
    date_str = datetime.now().strftime('%Y年%m月%d日')
    
    text = f"""
{config['report_title']}
{'=' * 50}
📅 {date_str} | 数据来源: GitHub

"""
    
    if not repos:
        text += "暂无热门 AI 项目\n"
    else:
        for i, repo in enumerate(repos, 1):
            desc = (repo['description'] or '暂无描述')[:100]
            text += f"""
#{i} {repo['name']}
   ⭐ {repo['stars']:,} stars | 🍴 {repo['forks']:,} forks | {repo['language']}
   {desc}
   🔗 {repo['url']}
"""
    
    text += f"""
{'=' * 50}
📧 此报告由 GitHub Actions 自动生成
"""
    return text

def send_email(config, subject, html_content, text_content):
    """通过 SMTP 发送邮件"""
    smtp_server = config['smtp_server']
    smtp_port = config['smtp_port']
    sender_address = config['sender_address']
    sender_password = config['sender_password']
    recipient = config['recipient_email']
    
    # 创建邮件
    msg = MIMEMultipart('alternative')
    msg['From'] = f"Hermes AI Report <{sender_address}>"
    msg['To'] = recipient
    msg['Subject'] = subject
    
    # 添加纯文本和 HTML 版本
    msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    # 发送邮件
    try:
        import ssl
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30, context=context) as server:
            server.login(sender_address, sender_password)
            server.send_message(msg)
        print(f"✅ 邮件已成功发送至 {recipient}")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始生成 GitHub AI 热门项目日报...")
    
    # 加载配置
    config = get_config()
    
    # 检查配置
    if not config['sender_address'] or not config['sender_password']:
        print("⚠️  请设置环境变量: SENDER_ADDRESS, SENDER_PASSWORD, RECIPIENT_EMAIL")
        return False
    
    # 获取热门仓库
    print("📡 正在从 GitHub 获取 AI 热门项目...")
    repos = fetch_github_trending(config['search_keywords'], config['max_results'])
    print(f"📊 找到 {len(repos)} 个热门项目")
    
    # 生成报告
    html_report = format_report_html(repos, config)
    text_report = format_report_text(repos, config)
    
    # 生成邮件主题
    date_str = datetime.now().strftime('%m/%d')
    subject = f"🤖 GitHub AI 热门日报 - {date_str} ({len(repos)}个项目)"
    
    # 发送邮件
    success = send_email(config, subject, html_report, text_report)
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

#!/usr/bin/env python3
"""
AI Daily News Summary Generator
Uses Brave Search API to fetch latest AI news and generates a comprehensive summary

IMPORTANT: This script is designed to run ONCE per day to stay within API limits
- Brave Search API Free Tier: 2000 requests/month, 1 request/second
- Daily execution: ~30 requests/month (well within limits)
"""

import requests
import json
import os
import sys
from datetime import datetime, timedelta
from openai import OpenAI

# Import Feishu push module
try:
    from feishu_push import send_news_summary
    FEISHU_ENABLED = True
except ImportError:
    FEISHU_ENABLED = False
    print("警告: 飞书推送模块未找到，将跳过飞书推送功能")

# Configuration - Read from environment variables for GitHub Actions
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "BSAoSBQpdOGtvYY8qJDmwqjGVL2wa29")
BRAVE_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
LOCK_FILE = os.getenv("LOCK_FILE", ".ai_news_lock")

# Initialize OpenAI client
# In GitHub Actions, OPENAI_API_KEY and OPENAI_BASE_URL are set as environment variables
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
if api_key and base_url:
    client = OpenAI(api_key=api_key, base_url=base_url)
else:
    client = OpenAI()  # Use default configuration

def check_daily_execution():
    """
    Check if the script has already been executed today
    Returns True if already executed, False otherwise
    """
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                last_run = f.read().strip()
                last_run_date = datetime.strptime(last_run, "%Y-%m-%d").date()
                today = datetime.now().date()
                
                if last_run_date == today:
                    print(f"⚠️  脚本今天已经运行过了（{last_run}）")
                    print(f"⚠️  为了保护 API 配额，每天只能运行一次")
                    print(f"⚠️  如需强制运行，请删除锁文件: {LOCK_FILE}")
                    return True
        except Exception as e:
            print(f"警告: 读取锁文件时出错: {e}")
    
    return False

def update_lock_file():
    """
    Update the lock file with today's date
    """
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(datetime.now().strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"警告: 更新锁文件时出错: {e}")

def fetch_ai_news(query="artificial intelligence AI news", count=20, freshness="pd"):
    """
    Fetch AI news from Brave Search API
    
    Args:
        query: Search query string
        count: Number of results to fetch
        freshness: Time filter (pd=past day, pw=past week, pm=past month)
    
    Returns:
        List of news articles with title, url, description, and age
    """
    headers = {
        "X-Subscription-Token": BRAVE_API_KEY,
        "Accept": "application/json"
    }
    
    params = {
        "q": query,
        "count": count,
        "search_lang": "en",
        "freshness": freshness
    }
    
    try:
        print(f"正在从 Brave Search API 获取 AI 新闻...")
        print(f"📊 API 配额: 免费版 - 每月 2000 次请求")
        response = requests.get(BRAVE_BASE_URL, headers=headers, params=params, timeout=30)
        
        # Check rate limit headers
        if 'x-ratelimit-remaining' in response.headers:
            remaining = response.headers['x-ratelimit-remaining']
            print(f"📊 剩余配额: {remaining}")
        
        if response.status_code == 200:
            data = response.json()
            articles = []
            
            # Extract web results
            if 'web' in data and 'results' in data['web']:
                for result in data['web']['results']:
                    articles.append({
                        'title': result.get('title', ''),
                        'url': result.get('url', ''),
                        'description': result.get('description', ''),
                        'age': result.get('age', ''),
                        'source': 'web'
                    })
            
            # Extract news results if available
            if 'news' in data and 'results' in data['news']:
                for result in data['news']['results']:
                    articles.append({
                        'title': result.get('title', ''),
                        'url': result.get('url', ''),
                        'description': result.get('description', ''),
                        'age': result.get('age', ''),
                        'source': 'news'
                    })
            
            print(f"✅ 成功获取 {len(articles)} 篇文章")
            return articles
        else:
            print(f"❌ API 错误: 状态码 {response.status_code}")
            print(f"响应: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ 获取新闻时出错: {type(e).__name__}: {str(e)}")
        return []

def categorize_and_summarize_news(articles):
    """
    Use LLM to categorize and summarize AI news articles
    
    Args:
        articles: List of article dictionaries
    
    Returns:
        Structured summary with categories and key points
    """
    if not articles:
        return None
    
    # Prepare article text for LLM
    articles_text = ""
    for i, article in enumerate(articles[:20], 1):  # Limit to top 20 articles
        articles_text += f"\n{i}. 标题: {article['title']}\n"
        articles_text += f"   描述: {article['description']}\n"
        articles_text += f"   时间: {article.get('age', '未知')}\n"
        articles_text += f"   来源: {article['url']}\n"
    
    prompt = f"""你是一位专业的 AI 行业分析师。请分析以下今日的 AI 新闻，并生成一份结构化的每日新闻摘要。

要求：
1. 将新闻分为以下几个类别（如果适用）：
   - 🚀 重大突破与产品发布
   - 💼 商业动态与投资
   - 🔬 研究进展
   - 📊 行业趋势与分析
   - ⚖️ 政策法规
   - 🌍 社会影响

2. 每个类别下：
   - 提取 2-4 条最重要的新闻
   - 用简洁的中文概括要点（每条 1-2 句话）
   - 保留原文标题的关键信息
   - 标注信息来源（使用文章编号）

3. 在摘要开头提供"今日要闻"部分，列出 3-5 条最重要的新闻

4. 使用专业但易懂的语言，适合技术从业者和决策者阅读

今日 AI 新闻文章：
{articles_text}

请生成今日 AI 新闻摘要（使用简体中文）："""

    try:
        print("正在使用 AI 生成新闻摘要...")
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "你是一位专业的 AI 行业分析师，擅长从大量信息中提取关键要点并生成结构化的新闻摘要。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        summary = response.choices[0].message.content
        print("✅ 摘要生成成功")
        return summary
        
    except Exception as e:
        print(f"❌ 生成摘要时出错: {type(e).__name__}: {str(e)}")
        return None

def generate_markdown_report(summary, articles, output_file=None):
    """
    Generate a formatted Markdown report
    
    Args:
        summary: LLM-generated summary text
        articles: List of article dictionaries
        output_file: Output file path (optional)
    
    Returns:
        Markdown formatted report string
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    
    markdown = f"""# AI 每日新闻摘要

**日期**: {today}  
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**新闻来源**: Brave Search API  
**文章数量**: {len(articles)} 篇

---

## 📰 今日摘要

{summary}

---

## 📚 完整新闻列表

以下是今日收集的所有 AI 相关新闻文章：

"""
    
    for i, article in enumerate(articles, 1):
        markdown += f"\n### {i}. {article['title']}\n\n"
        markdown += f"**链接**: [{article['url']}]({article['url']})\n\n"
        if article.get('age'):
            markdown += f"**发布时间**: {article['age']}\n\n"
        markdown += f"**简介**: {article['description']}\n\n"
        markdown += "---\n"
    
    markdown += f"\n\n*本报告由 AI 每日新闻摘要系统自动生成*\n"
    markdown += f"\n*API 使用: Brave Search API 免费版 (每月 2000 次请求限制)*\n"
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown)
        print(f"✅ 报告已保存至: {output_file}")
    
    return markdown

def main():
    """
    Main function to generate daily AI news summary
    """
    print("=" * 80)
    print("AI 每日新闻摘要生成器")
    print("=" * 80)
    print()
    
    # Check if already executed today
    if check_daily_execution():
        today_str = datetime.now().strftime("%Y%m%d")
        existing_file = f"/home/ubuntu/ai_news_summary_{today_str}.md"
        if os.path.exists(existing_file):
            print(f"📄 今日报告已存在: {existing_file}")
        sys.exit(0)
    
    # Step 1: Fetch news from Brave Search API
    articles = fetch_ai_news(
        query="artificial intelligence AI news latest",
        count=20,
        freshness="pd"  # Past day
    )
    
    if not articles:
        print("❌ 错误: 未能获取新闻文章")
        sys.exit(1)
    
    print()
    
    # Step 2: Generate summary using LLM
    summary = categorize_and_summarize_news(articles)
    
    if not summary:
        print("❌ 错误: 未能生成摘要")
        sys.exit(1)
    
    print()
    
    # Step 3: Generate Markdown report
    today_str = datetime.now().strftime("%Y%m%d")
    output_file = f"ai_news_summary_{today_str}.md"
    
    report = generate_markdown_report(summary, articles, output_file)
    
    # Step 4: Push to Feishu
    if FEISHU_ENABLED:
        print()
        print("正在推送到飞书...")
        today = datetime.now().strftime("%Y年%m月%d日")
        try:
            if send_news_summary(today, len(articles), summary, output_file):
                print("✅ 飞书推送成功！")
            else:
                print("⚠️  飞书推送失败，但报告已生成")
        except Exception as e:
            print(f"⚠️  飞书推送异常: {e}")
    
    # Step 5: Update lock file to prevent multiple executions
    update_lock_file()
    
    print()
    print("=" * 80)
    print("✅ AI 每日新闻摘要生成完成！")
    print("=" * 80)
    print()
    print(f"📄 报告文件: {output_file}")
    print(f"📊 文章数量: {len(articles)}")
    if FEISHU_ENABLED:
        print("📱 飞书推送: 已启用")
    print(f"🔒 已更新锁文件，今天不会再次执行")
    print()
    print("💡 提示: 该脚本每天只能运行一次，以保护 API 配额")
    print("💡 Brave Search API 免费版限制: 每月 2000 次请求")
    print("💡 每日运行一次: 每月约 30 次请求（远低于限制）")
    print()

if __name__ == "__main__":
    main()

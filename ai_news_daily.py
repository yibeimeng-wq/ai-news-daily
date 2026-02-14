#!/usr/bin/env python3
"""
AI Daily News Summary Generator with Deduplication
Uses Brave Search API to fetch latest AI news and generates a comprehensive summary

IMPORTANT: This script is designed to run ONCE per day to stay within API limits
- Brave Search API Free Tier: 2000 requests/month, 1 request/second
- Daily execution: ~30 requests/month (well within limits)

NEW FEATURE: Deduplication
- Prevents duplicate news within the same day
- Prevents duplicate news within the past week
- Uses URL and title similarity for detection
"""

import requests
import json
import os
import sys
import hashlib
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
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY" )
if not BRAVE_API_KEY:
    print("❌ 错误: BRAVE_API_KEY 环境变量未设置")
    print("💡 请在 GitHub Secrets 中配置 BRAVE_API_KEY")
    sys.exit(1)

BRAVE_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
LOCK_FILE = os.getenv("LOCK_FILE", ".ai_news_lock")
HISTORY_FILE = os.getenv("HISTORY_FILE", ".ai_news_history.json")

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

def load_news_history():
    """
    Load news history from JSON file
    Returns a dictionary with news history
    """
    if not os.path.exists(HISTORY_FILE):
        print("📝 历史记录文件不存在，将创建新文件")
        return {"news_history": [], "last_cleanup": datetime.now().strftime("%Y-%m-%d")}
    
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
            print(f"✅ 加载了 {len(history.get('news_history', []))} 条历史新闻记录")
            return history
    except Exception as e:
        print(f"⚠️  读取历史记录时出错: {e}")
        print("📝 将创建新的历史记录文件")
        return {"news_history": [], "last_cleanup": datetime.now().strftime("%Y-%m-%d")}

def save_news_history(history):
    """
    Save news history to JSON file
    """
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"✅ 历史记录已更新（共 {len(history.get('news_history', []))} 条）")
    except Exception as e:
        print(f"⚠️  保存历史记录时出错: {e}")

def cleanup_old_history(history, days=7):
    """
    Remove news older than specified days from history
    """
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    original_count = len(history.get("news_history", []))
    
    history["news_history"] = [
        news for news in history.get("news_history", [])
        if news.get("last_seen", "2000-01-01") >= cutoff_date
    ]
    
    removed_count = original_count - len(history["news_history"])
    if removed_count > 0:
        print(f"🧹 清理了 {removed_count} 条超过 {days} 天的旧记录")
    
    history["last_cleanup"] = datetime.now().strftime("%Y-%m-%d")
    return history

def calculate_title_similarity(title1, title2):
    """
    Calculate similarity between two titles using Jaccard similarity
    Returns a value between 0 and 1
    """
    # Convert to lowercase and split into words
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())
    
    # Calculate Jaccard similarity
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)

def get_title_hash(title):
    """
    Generate a hash for the title for quick comparison
    """
    return hashlib.md5(title.lower().encode('utf-8')).hexdigest()

def is_duplicate_news(article, history, similarity_threshold=0.85):
    """
    Check if an article is a duplicate based on URL or title similarity
    
    Args:
        article: Article dictionary with 'url' and 'title'
        history: News history dictionary
        similarity_threshold: Threshold for title similarity (0-1)
    
    Returns:
        True if duplicate, False otherwise
    """
    url = article.get('url', '')
    title = article.get('title', '')
    
    if not url or not title:
        return False
    
    # Check URL exact match
    for news in history.get("news_history", []):
        if news.get("url") == url:
            return True
    
    # Check title similarity
    for news in history.get("news_history", []):
        similarity = calculate_title_similarity(title, news.get("title", ""))
        if similarity >= similarity_threshold:
            return True
    
    return False

def filter_duplicate_news(articles, history):
    """
    Filter out duplicate news from articles list
    
    Args:
        articles: List of article dictionaries
        history: News history dictionary
    
    Returns:
        Tuple of (filtered_articles, duplicate_count)
    """
    print("🔍 正在检查重复新闻...")
    
    filtered = []
    duplicate_count = 0
    
    for article in articles:
        if is_duplicate_news(article, history):
            duplicate_count += 1
        else:
            filtered.append(article)
    
    if duplicate_count > 0:
        print(f"⚠️  发现 {duplicate_count} 条重复新闻（已过滤）")
    else:
        print("✅ 未发现重复新闻")
    
    print(f"✅ 保留 {len(filtered)} 条新闻用于摘要生成")
    
    return filtered, duplicate_count

def update_news_history(articles, history):
    """
    Add new articles to news history
    """
    today = datetime.now().strftime("%Y-%m-%d")
    
    for article in articles:
        url = article.get('url', '')
        title = article.get('title', '')
        
        if not url or not title:
            continue
        
        # Check if already exists
        existing = False
        for news in history.get("news_history", []):
            if news.get("url") == url:
                news["last_seen"] = today
                existing = True
                break
        
        # Add new entry
        if not existing:
            history["news_history"].append({
                "url": url,
                "title": title,
                "title_hash": get_title_hash(title),
                "first_seen": today,
                "last_seen": today
            })
    
    return history

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
    """ Use LLM to categorize and summarize AI news articles """
    if not articles:
        return None

    articles_text = ""
    for i, article in enumerate(articles[:20], 1):
        articles_text += f"[{i}] 标题: {article['title']}\n"
        articles_text += f"    链接: {article['url']}\n"
        articles_text += f"    描述: {article['description']}\n\n"

    prompt = f"""你是一位专业的 AI 行业分析师。请分析以下 AI 新闻，并生成一份结构化的周度新闻摘要。

## 一级分类
将所有新闻分为三个地理区域：
- 🇨🇳 **中国** - 中国公司、机构、政府的新闻
- 🇺🇸 **美国** - 美国公司、机构、政府（不含中国）的新闻
- 🌍 **其他** - 其他国家和地区的新闻

## 二级分类
在每个一级分类下，再按以下主题分类：
- 🚀 **重大突破与产品发布**
- 💼 **商业动态与投资**
- 🔬 **研究进展**
- 📊 **行业趋势与分析**
- ⚖️ **政策法规**
- 🌍 **社会影响**

## 新闻格式要求
每条新闻必须包含：
1. 序号
2. 标题（中文概括）
3. 核心要点（1-2 句话）
4. **来源**: [原始标题](原始URL) - 必须带完整链接

## 完整格式示例
### 🇨🇳 中国

#### 🚀 重大突破与产品发布
**1. 字节跳动发布新版 AI 助手**
- 新版助手在中文理解和多轮对话方面有显著提升
- **来源**: [字节跳动官方公告](https://www.bytedance.com/news/xxx)

#### 💼 商业动态与投资
**2. 阿里云完成新一轮融资**
- 估值突破 500 亿人民币，资金将用于 AI 基础设施建设
- **来源**: [36氪报道](https://36kr.com/news/xxx)

### 🇺🇸 美国

#### 🚀 重大突破与产品发布
**1. OpenAI 发布 GPT-5 预览版**
- 新模型在推理能力和多模态理解方面有突破性进展
- **来源**: [OpenAI Blog](https://openai.com/blog/gpt-5)

---

## 新闻列表
{articles_text}

请按照上述格式生成新闻摘要（使用简体中文，所有链接必须完整可点击）：
"""

    try:
        print("正在使用 AI 生成新闻摘要...")
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "你是一位专业的 AI 行业分析师。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        summary = response.choices[0].message.content
        print("✅ 摘要生成成功")
        return summary
    except Exception as e:
        print(f"❌ 生成摘要时出错: {e}")
        return None

def generate_markdown_report(summary, articles, output_file=None, duplicate_count=0):
    """
    Generate a formatted Markdown report
    
    Args:
        summary: LLM-generated summary text
        articles: List of article dictionaries
        output_file: Output file path (optional)
        duplicate_count: Number of duplicate news filtered
    
    Returns:
        Markdown formatted report string
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    
    markdown = f"""# AI 每日新闻摘要

**日期**: {today}  
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**新闻来源**: Brave Search API  
**文章数量**: {len(articles)} 篇  
**过滤重复**: {duplicate_count} 篇

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
    markdown += f"\n*去重功能: 自动过滤一周内的重复新闻*\n"
    
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
    print("AI 每日新闻摘要生成器（带去重功能）")
    print("=" * 80)
    print()
    
    # Check if already executed today
    if check_daily_execution():
        today_str = datetime.now().strftime("%Y%m%d")
        existing_file = f"/home/ubuntu/ai_news_summary_{today_str}.md"
        if os.path.exists(existing_file):
            print(f"📄 今日报告已存在: {existing_file}")
        sys.exit(0)
    
    # Step 1: Load and cleanup news history
    print("正在加载新闻历史记录...")
    history = load_news_history()
    history = cleanup_old_history(history, days=7)
    print()
    
    # Step 2: Fetch news from Brave Search API
    articles = fetch_ai_news(
        query="artificial intelligence AI news latest",
        count=20,
        freshness="pd"  # Past day
    )
    
    if not articles:
        print("❌ 错误: 未能获取新闻文章")
        sys.exit(1)
    
    print()
    
    # Step 3: Filter duplicate news
    filtered_articles, duplicate_count = filter_duplicate_news(articles, history)
    
    if not filtered_articles:
        print("⚠️  所有新闻都是重复的，今日无新内容")
        print("💡 不会生成报告和推送通知")
        sys.exit(0)
    
    print()
    
    # Step 4: Update news history
    print("📝 更新历史记录...")
    history = update_news_history(filtered_articles, history)
    save_news_history(history)
    print()
    
    # Step 5: Generate summary using LLM
    summary = categorize_and_summarize_news(filtered_articles)
    
    if not summary:
        print("❌ 错误: 未能生成摘要")
        sys.exit(1)
    
    print()
    
    # Step 6: Generate Markdown report
    today_str = datetime.now().strftime("%Y%m%d")
    output_file = f"ai_news_summary_{today_str}.md"
    
    report = generate_markdown_report(summary, filtered_articles, output_file, duplicate_count)
    
    # Step 7: Push to Feishu
    if FEISHU_ENABLED:
        print()
        print("正在推送到飞书...")
        today = datetime.now().strftime("%Y年%m月%d日")
        try:
            if send_news_summary(today, len(filtered_articles), summary, output_file):
                print("✅ 飞书推送成功！")
            else:
                print("⚠️  飞书推送失败，但报告已生成")
        except Exception as e:
            print(f"⚠️  飞书推送异常: {e}")
    
    # Step 8: Update lock file to prevent multiple executions
    update_lock_file()
    
    print()
    print("=" * 80)
    print("✅ AI 每日新闻摘要生成完成！")
    print("=" * 80)
    print()
    print(f"📄 报告文件: {output_file}")
    print(f"📊 文章数量: {len(filtered_articles)}")
    print(f"🔍 过滤重复: {duplicate_count} 篇")
    if FEISHU_ENABLED:
        print("📱 飞书推送: 已启用")
    print(f"🔒 已更新锁文件，今天不会再次执行")
    print()
    print("💡 提示: 该脚本每天只能运行一次，以保护 API 配额")
    print("💡 Brave Search API 免费版限制: 每月 2000 次请求")
    print("💡 每日运行一次: 每月约 30 次请求（远低于限制）")
    print("💡 去重功能: 自动过滤一周内的重复新闻")
    print()

if __name__ == "__main__":
    main()

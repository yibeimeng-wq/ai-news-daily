#!/usr/bin/env python3
"""
AI Daily News Summary Generator with Deduplication
Uses Brave Search API to fetch latest AI news and generates a comprehensive summary
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

# Configuration
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
if not BRAVE_API_KEY:
    print("❌ 错误: BRAVE_API_KEY 环境变量未设置")
    sys.exit(1)

BRAVE_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
LOCK_FILE = os.getenv("LOCK_FILE", ".ai_news_lock")
HISTORY_FILE = os.getenv("HISTORY_FILE", ".ai_news_history.json")

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
if api_key and base_url:
    client = OpenAI(api_key=api_key, base_url=base_url)
else:
    client = OpenAI()


def check_daily_execution():
    """Check if the script has already been executed today"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                last_run = f.read().strip()
            last_run_date = datetime.strptime(last_run, "%Y-%m-%d").date()
            today = datetime.now().date()
            if last_run_date == today:
                print(f"⚠️ 脚本今天已经运行过了（{last_run}）")
                print(f"⚠️ 为了保护 API 配额，每天只能运行一次")
                return True
        except Exception as e:
            print(f"警告: 读取锁文件时出错: {e}")
    return False


def update_lock_file():
    """Update the lock file with today's date"""
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(datetime.now().strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"警告: 更新锁文件时出错: {e}")


def load_news_history():
    """Load news history from JSON file"""
    if not os.path.exists(HISTORY_FILE):
        print("📝 历史记录文件不存在，将创建新文件")
        return {"news_history": [], "last_cleanup": datetime.now().strftime("%Y-%m-%d")}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        print(f"✅ 加载了 {len(history.get('news_history', []))} 条历史新闻记录")
        return history
    except Exception as e:
        print(f"⚠️ 读取历史记录时出错: {e}")
        return {"news_history": [], "last_cleanup": datetime.now().strftime("%Y-%m-%d")}


def save_news_history(history):
    """Save news history to JSON file"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"✅ 历史记录已更新（共 {len(history.get('news_history', []))} 条）")
    except Exception as e:
        print(f"⚠️ 保存历史记录时出错: {e}")


def cleanup_old_history(history, days=7):
    """Remove news older than specified days from history"""
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
    """Calculate similarity between two titles using Jaccard similarity"""
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    if not union:
        return 0.0
    return len(intersection) / len(union)


def get_title_hash(title):
    """Generate a hash for the title"""
    return hashlib.md5(title.lower().encode('utf-8')).hexdigest()


def is_duplicate_news(article, history, similarity_threshold=0.85):
    """Check if an article is a duplicate"""
    url = article.get('url', '')
    title = article.get('title', '')
    if not url or not title:
        return False
    
    for news in history.get("news_history", []):
        if news.get("url") == url:
            return True
        similarity = calculate_title_similarity(title, news.get("title", ""))
        if similarity >= similarity_threshold:
            return True
    return False


def filter_duplicate_news(articles, history):
    """Filter out duplicate news"""
    print("🔍 正在检查重复新闻...")
    filtered = []
    duplicate_count = 0
    for article in articles:
        if is_duplicate_news(article, history):
            duplicate_count += 1
        else:
            filtered.append(article)
    
    if duplicate_count > 0:
        print(f"⚠️ 发现 {duplicate_count} 条重复新闻（已过滤）")
    else:
        print("✅ 未发现重复新闻")
    print(f"✅ 保留 {len(filtered)} 条新闻用于摘要生成")
    return filtered, duplicate_count


def update_news_history(articles, history):
    """Add new articles to news history"""
    today = datetime.now().strftime("%Y-%m-%d")
    for article in articles:
        url = article.get('url', '')
        title = article.get('title', '')
        if not url or not title:
            continue
        existing = False
        for news in history.get("news_history", []):
            if news.get("url") == url:
                news["last_seen"] = today
                existing = True
                break
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
    """Fetch AI news from Brave Search API"""
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
        
        if 'x-ratelimit-remaining' in response.headers:
            remaining = response.headers['x-ratelimit-remaining']
            print(f"📊 剩余配额: {remaining}")
        
        if response.status_code == 200:
            data = response.json()
            articles = []
            
            if 'web' in data and 'results' in data['web']:
                for result in data['web']['results']:
                    articles.append({
                        'title': result.get('title', ''),
                        'url': result.get('url', ''),
                        'description': result.get('description', ''),
                        'age': result.get('age', ''),
                        'source': 'web'
                    })
            
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
            return []
    except Exception as e:
        print(f"❌ 获取新闻时出错: {type(e).__name__}: {str(e)}")
        return []


def categorize_and_summarize_news(articles):
    """Use LLM to categorize and summarize AI news articles"""
    if not articles:
        return None
    
    articles_text = ""
    for i, article in enumerate(articles[:20], 1):
        articles_text += f"[{i}] 标题: {article['title']}\n"
        articles_text += f"    链接: {article['url']}\n"
        articles_text += f"    描述: {article['description']}\n\n"
    
    prompt = f"""你是一位专业的 AI 行业分析师。请分析以下 AI 新闻，并生成一份结构化的周度新闻摘要。

## ⚠️ 重要：一级分类顺序
必须严格按照以下顺序组织内容：
1. 🇨🇳 中国
2. 🇺🇸 美国
3. 🌍 其他

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

## 完整格式示例（严格按照此顺序）
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

### 🌍 其他

#### 💼 商业动态与投资
**1. 欧洲 AI 公司完成融资**
- 估值达到 10 亿欧元
- **来源**: [Reuters](https://reuters.com/xxx)

---

## 新闻列表
{articles_text}

请按照上述格式生成新闻摘要（使用简体中文，所有链接必须完整可点击）：
- 每个一级分类标题清晰
- 每个二级分类用 emoji 标识
- 所有链接必须完整可点击
- 优先选择最重要的新闻（每个二级分类 2-4 条）
- 如果某个分类无新闻，标注"本周暂无重大动态"
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
    """Generate a formatted Markdown report"""
    today = datetime.now().strftime("%Y年%m月%d日")
    markdown = f"""# AI 每周新闻摘要
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

以下是本周收集的所有 AI 相关新闻文章：

"""
    
    for i, article in enumerate(articles, 1):
        markdown += f"### {i}. {article['title']}\n\n"
        markdown += f"**链接**: [{article['url']}]({article['url']})\n\n"
        if article.get('age'):
            markdown += f"**发布时间**: {article['age']}\n\n"
        markdown += f"**简介**: {article['description']}\n\n"
        markdown += "---\n\n"
    
    markdown += f"""
*本报告由 AI 每周新闻摘要系统自动生成*
*API 使用: Brave Search API 免费版 (每月 2000 次请求限制)*
"""
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown)
        print(f"✅ 报告已保存至: {output_file}")
    
    return markdown


def main():
    """Main function to generate weekly AI news summary"""
    print("=" * 80)
    print("AI 每周新闻摘要生成器（带去重功能）")
    print("=" * 80)
    print()
    
    # Check if already executed this week
    if check_daily_execution():
        today_str = datetime.now().strftime("%Y%m%d")
        existing_file = f"ai_news_summary_{today_str}.md"
        if os.path.exists(existing_file):
            print(f"📄 今日报告已存在: {existing_file}")
        sys.exit(0)
    
    # Load and cleanup history
    print("正在加载新闻历史记录...")
    history = load_news_history()
    history = cleanup_old_history(history, days=7)
    print()
    
    # Fetch news
    articles = fetch_ai_news(
        query="artificial intelligence AI news latest",
        count=20,
        freshness="pw"  # Past week
    )
    if not articles:
        print("❌ 错误: 未能获取新闻文章")
        sys.exit(1)
    print()
    
    # Filter duplicates
    filtered_articles, duplicate_count = filter_duplicate_news(articles, history)
    if not filtered_articles:
        print("⚠️ 所有新闻都是重复的，本周无新内容")
        sys.exit(0)
    print()
    
    # Update history
    print("📝 更新历史记录...")
    history = update_news_history(filtered_articles, history)
    save_news_history(history)
    print()
    
    # Generate summary
    summary = categorize_and_summarize_news(filtered_articles)
    if not summary:
        print("❌ 错误: 未能生成摘要")
        sys.exit(1)
    print()
    
    # Generate report
    today_str = datetime.now().strftime("%Y%m%d")
    output_file = f"ai_news_summary_{today_str}.md"
    report = generate_markdown_report(summary, filtered_articles, output_file, duplicate_count)
    
    # Push to Feishu
    if FEISHU_ENABLED:
        print()
        print("正在推送到飞书...")
        today = datetime.now().strftime("%Y年%m月%d日")
        try:
            if send_news_summary(today, len(filtered_articles), summary, output_file):
                print("✅ 飞书推送成功！")
            else:
                print("⚠️ 飞书推送失败，但报告已生成")
        except Exception as e:
            print(f"⚠️ 飞书推送异常: {e}")
    
    # Update lock file
    update_lock_file()
    
    print()
    print("=" * 80)
    print("✅ AI 每周新闻摘要生成完成！")
    print("=" * 80)
    print()
    print(f"📄 报告文件: {output_file}")
    print(f"📊 文章数量: {len(filtered_articles)}")
    print(f"🔍 过滤重复: {duplicate_count} 篇")
    if FEISHU_ENABLED:
        print("📱 飞书推送: 已启用")
    print()
    print("💡 提示: 该脚本每周只能运行一次，以保护 API 配额")
    print("💡 Brave Search API 免费版限制: 每月 2000 次请求")
    print()


if __name__ == "__main__":
    main()

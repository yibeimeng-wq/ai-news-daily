#!/usr/bin/env python3
"""
Feishu Bot Push Module
Send AI news summary to Feishu group via webhook
"""

import requests
import json
import os
from datetime import datetime

# Feishu webhook URL - Read from environment variable for GitHub Actions
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/ea8f9b27-2046-4977-9588-5df48d2b5285")
FEISHU_KEYWORD = os.getenv("FEISHU_KEYWORD", "dailynews")

def send_text_message(text):
    """
    Send simple text message to Feishu
    
    Args:
        text: Text content to send
    
    Returns:
        True if successful, False otherwise
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "msg_type": "text",
        "content": {
            "text": f"{FEISHU_KEYWORD}\n\n{text}"
        }
    }
    
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        result = response.json()
        
        if result.get("code") == 0:
            return True
        else:
            print(f"飞书推送失败: {result}")
            return False
    except Exception as e:
        print(f"飞书推送异常: {type(e).__name__}: {str(e)}")
        return False

def send_rich_text_message(title, content_lines):
    """
    Send rich text message to Feishu
    
    Args:
        title: Message title
        content_lines: List of content lines
    
    Returns:
        True if successful, False otherwise
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    # Build rich text content
    content = [[{"tag": "text", "text": title, "style": ["bold"]}]]
    
    for line in content_lines:
        content.append([{"tag": "text", "text": line}])
    
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content
                }
            }
        }
    }
    
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        result = response.json()
        
        if result.get("code") == 0:
            return True
        else:
            print(f"飞书推送失败: {result}")
            return False
    except Exception as e:
        print(f"飞书推送异常: {type(e).__name__}: {str(e)}")
        return False

def send_interactive_card(summary_data):
    """
    Send interactive card message to Feishu
    
    Args:
        summary_data: Dictionary containing:
            - date: Date string
            - article_count: Number of articles
            - highlights: List of highlight news
            - categories: Dictionary of categorized news
            - report_file: Path to full report file
    
    Returns:
        True if successful, False otherwise
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    # Build card elements
    elements = []
    
    # Header section
    elements.append({
        "tag": "markdown",
        "content": f"**📅 日期**: {summary_data.get('date', '')}\n**📊 文章数量**: {summary_data.get('article_count', 0)} 篇"
    })
    
    elements.append({"tag": "hr"})
    
    # Highlights section
    if summary_data.get('highlights'):
        highlights_text = "**🔥 今日要闻**\n\n"
        for i, highlight in enumerate(summary_data['highlights'][:5], 1):
            highlights_text += f"{i}. {highlight}\n"
        
        elements.append({
            "tag": "markdown",
            "content": highlights_text
        })
        
        elements.append({"tag": "hr"})
    
    # Categories section
    if summary_data.get('categories'):
        for category, items in summary_data['categories'].items():
            if items:
                category_text = f"**{category}**\n\n"
                for item in items[:3]:  # Limit to 3 items per category
                    category_text += f"• {item}\n"
                
                elements.append({
                    "tag": "markdown",
                    "content": category_text
                })
    
    # Footer
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "markdown",
        "content": "*📄 完整报告已保存，可通过系统查看*\n*🤖 本消息由 AI 每日新闻摘要系统自动推送*"
    })
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📰 AI dailynews 每日新闻摘要"
                },
                "template": "blue"
            },
            "elements": elements
        }
    }
    
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        result = response.json()
        
        if result.get("code") == 0:
            return True
        else:
            print(f"飞书推送失败: {result}")
            return False
    except Exception as e:
        print(f"飞书推送异常: {type(e).__name__}: {str(e)}")
        return False

def send_news_summary(date, article_count, summary_text, report_file=None):
    """
    Send AI news summary to Feishu (simplified version)
    
    Args:
        date: Date string
        article_count: Number of articles
        summary_text: Summary text content
        report_file: Path to full report file (optional)
    
    Returns:
        True if successful, False otherwise
    """
    # Parse summary to extract highlights
    highlights = []
    categories = {}
    
    lines = summary_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Extract highlights
        if '【今日要闻】' in line or '今日要闻' in line:
            current_section = 'highlights'
            continue
        
        # Extract category headers
        if line.startswith('🚀') or line.startswith('💼') or line.startswith('🔬') or \
           line.startswith('📊') or line.startswith('⚖️') or line.startswith('🌍'):
            current_section = line
            categories[current_section] = []
            continue
        
        # Extract content
        if current_section == 'highlights' and (line[0].isdigit() or line.startswith('-')):
            # Remove numbering
            content = line.lstrip('0123456789.- ')
            if content:
                highlights.append(content)
        elif current_section and current_section != 'highlights':
            if line.startswith('-') or line.startswith('•'):
                content = line.lstrip('-• ')
                if content and len(content) > 10:  # Filter out short lines
                    categories[current_section].append(content)
    
    # Build summary data
    summary_data = {
        'date': date,
        'article_count': article_count,
        'highlights': highlights,
        'categories': categories,
        'report_file': report_file
    }
    
    # Send interactive card
    return send_interactive_card(summary_data)

def test_feishu_connection():
    """
    Test Feishu webhook connection
    
    Returns:
        True if successful, False otherwise
    """
    test_message = f"✅ 飞书机器人连接测试成功！\n\n🤖 AI 每日新闻摘要系统已配置完成\n⏰ 每天早上 9:00 自动推送\n📱 您将在此群组收到最新的 AI 新闻摘要\n\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return send_text_message(test_message)

if __name__ == "__main__":
    # Test the connection
    print("正在测试飞书机器人连接...")
    if test_feishu_connection():
        print("✅ 飞书机器人连接测试成功！")
    else:
        print("❌ 飞书机器人连接测试失败！")

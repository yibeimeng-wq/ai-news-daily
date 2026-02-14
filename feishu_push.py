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
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_KEYWORD = os.getenv("FEISHU_KEYWORD")

if not FEISHU_WEBHOOK:
    raise ValueError("FEISHU_WEBHOOK environment variable is not set")
if not FEISHU_KEYWORD:
    raise ValueError("FEISHU_KEYWORD environment variable is not set")


def send_text_message(text):
    """ Send simple text message to Feishu """
    headers = {"Content-Type": "application/json"}
    payload = {
        "msg_type": "text",
        "content": {"text": f"{FEISHU_KEYWORD} {text}"}
    }
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        return response.json().get("code") == 0
    except Exception as e:
        print(f"飞书推送异常: {e}")
        return False


def send_interactive_card(summary_data):
    """ Send interactive card message to Feishu """
    headers = {"Content-Type": "application/json"}
    
    elements = []
    
    # Header section
    elements.append({
        "tag": "markdown",
        "content": f"**📅 周度**: {summary_data.get('date', '')} **📊 文章数量**: {summary_data.get('article_count', 0)} 篇"
    })
    elements.append({"tag": "hr"})
    
    # Categories section - 一级分类 + 二级分类
    if summary_data.get('categories'):
        for primary_cat, secondary_cats in summary_data['categories'].items():
            for sec_cat, items in secondary_cats.items():
                if items:
                    cat_text = f"**{primary_cat} {sec_cat}**\n"
                    for item in items[:5]:  # Limit 5 items per category
                        cat_text += f"• {item}\n"
                    elements.append({
                        "tag": "markdown",
                        "content": cat_text.strip()
                    })
    
    # Footer
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "markdown",
        "content": "*📄 完整报告已保存*\n*🤖 AI 每周新闻摘要系统自动推送*"
    })
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📰 AI 周度新闻摘要"
                },
                "template": "blue"
            },
            "elements": elements
        }
    }
    
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        return response.json().get("code") == 0
    except Exception as e:
        print(f"飞书推送异常: {e}")
        return False


def send_news_summary(date, article_count, summary_text, report_file=None):
    """ Send AI news summary to Feishu """
    # Parse new format: 一级分类 + 二级分类
    categories = {}
    current_primary = None
    current_secondary = None
    
    lines = summary_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Detect 一级分类
        if '🇨🇳' in line or '中国' in line:
            current_primary = "🇨🇳 中国"
            categories[current_primary] = {}
            continue
        if '🇺🇸' in line or '美国' in line:
            current_primary = "🇺🇸 美国"
            categories[current_primary] = {}
            continue
        if '🌍' in line and ('其他' in line or '欧洲' in line or '亚洲' in line):
            current_primary = "🌍 其他"
            categories[current_primary] = {}
            continue
        
        # Detect 二级分类
        if any(x in line for x in ['🚀', '💼', '🔬', '📊', '⚖️', '🌍']):
            if current_primary:
                current_secondary = line.split('.')[0].strip() if '.' in line else line
                categories[current_primary][current_secondary] = []
            continue
        
        # Extract news items
        if current_primary and current_secondary:
            # Skip numbering lines
            if line and not line.startswith('#') and len(line) > 20:
                # Clean up the line but keep the link
                cleaned = line.lstrip('0123456789.- ')
                if cleaned and '来源:' not in cleaned:  # Don't add source lines as items
                    categories[current_primary][current_secondary].append(cleaned)
    
    summary_data = {
        'date': date,
        'article_count': article_count,
        'categories': categories,
        'report_file': report_file
    }
    
    return send_interactive_card(summary_data)


def test_feishu_connection():
    """ Test Feishu webhook connection """
    test_message = f"""✅ 飞书机器人连接测试成功！
🤖 AI 每周新闻摘要系统已配置完成
⏰ 每周一早上 9:00 自动推送
📱 您将在此群组收到最新的 AI 新闻摘要
测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    return send_text_message(test_message)


if __name__ == "__main__":
    print("正在测试飞书机器人连接...")
    if test_feishu_connection():
        print("✅ 飞书机器人连接测试成功！")
    else:
        print("❌ 飞书机器人连接测试失败！")

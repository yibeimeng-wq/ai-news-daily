#!/usr/bin/env python3
"""
Feishu Bot Push Module - 兼容各种 Markdown 格式
"""

import requests
import os
from datetime import datetime

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_KEYWORD = os.getenv("FEISHU_KEYWORD")

if not FEISHU_WEBHOOK:
    raise ValueError("FEISHU_WEBHOOK environment variable is not set")
if not FEISHU_KEYWORD:
    raise ValueError("FEISHU_KEYWORD environment variable is not set")


def send_rich_text_message(title, content_lines):
    """ 发送富文本消息 """
    headers = {"Content-Type": "application/json"}
    content = [[{"tag": "text", "text": title, "style": ["bold"]}]]
    for line in content_lines:
        content.append([{"tag": "text", "text": line}])
    payload = {"msg_type": "post", "content": {"post": {"zh_cn": {"title": title, "content": content}}}}
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        return response.json().get("code") == 0
    except Exception as e:
        print(f"飞书推送异常: {e}")
        return False


def send_news_summary(date, article_count, summary_text, report_file=None):
    """ 发送新闻摘要 - 兼容各种格式 """
    print(f"📤 推送 {article_count} 篇文章...")
    
    # 简单处理：直接推送前 3000 字
    try:
        content = summary_text[:3000]
        return send_rich_text_message(f"📰 AI 周度新闻摘要 - {date}", [content])
    except Exception as e:
        print(f"推送失败: {e}")
        return False


def test_feishu_connection():
    test_message = f"✅ 飞书连接成功！\n🤖 AI 每周摘要\n⏰ 每周一9:00推送\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    headers = {"Content-Type": "application/json"}
    payload = {"msg_type": "text", "content": {"text": f"{FEISHU_KEYWORD} {test_message}"}}
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=10)
        return response.json().get("code") == 0
    except Exception as e:
        print(f"测试失败: {e}")
        return False


if __name__ == "__main__":
    print("测试飞书连接...")
    if test_feishu_connection():
        print("✅ 连接成功！")
    else:
        print("❌ 连接失败！")
```
复制后替换文件，commit 保存，再测试一次！

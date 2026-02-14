#!/usr/bin/env python3
""" 
Feishu Push Module - 适配当前 Markdown 格式 
存放位置: /workspace/ai-news/feishu_push.py
"""

import requests
import os
from datetime import datetime

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_KEYWORD = os.getenv("FEISHU_KEYWORD")

if not FEISHU_WEBHOOK:
    raise ValueError("FEISHU_WEBHOOK not set")
if not FEISHU_KEYWORD:
    raise ValueError("FEISHU_KEYWORD not set")


def send_rich_text(title, lines):
    """ 发送富文本消息 """
    headers = {"Content-Type": "application/json"}
    content = [[{"tag": "text", "text": title, "style": ["bold"]}]]
    for line in lines:
        content.append([{"tag": "text", "text": line}])
    payload = {"msg_type": "post", "content": {"post": {"zh_cn": {"title": title, "content": content}}}}
    try:
        resp = requests.post(FEISHU_WEBHOOK, headers=headers, json=payload, timeout=30)
        return resp.json().get("code") == 0
    except Exception as e:
        print(f"推送异常: {e}")
        return False


def parse_summary(summary_text):
    """ 解析摘要，提取要闻和分类 """
    lines = [l.strip() for l in summary_text.split('\n') if l.strip()]
    
    highlights = []
    in_summary = False
    
    for line in lines:
        if '## 📰 今日摘要' in line:
            in_summary = True
            continue
        if '## 📚 完整新闻列表' in line:
            break
        if not in_summary:
            continue
            
        # 提取要闻
        if line.startswith('**') and '.' in line[:5]:
            title = line.split('-')[0].strip().lstrip('*')
            highlights.append(title)
        
        # 保留链接
        if '**来源**:' in line or '[' in line:
            highlights.append(line)
    
    return highlights[:8]


def send_news_summary(date, count, summary_text, report_file=None):
    """ 发送摘要 """
    print(f"📤 推送 {count} 条新闻...")
    
    highlights = parse_summary(summary_text)
    
    if highlights:
        content = [f"📊 共 {count} 条新闻\n"]
        for h in highlights:
            h_clean = h.replace('**', '').strip()
            if len(h_clean) > 100:
                h_clean = h_clean[:100] + "..."
            content.append(f"• {h_clean}")
    else:
        content = [f"📊 共 {count} 条新闻\n", summary_text[:2000]]
    
    title = f"📰 AI 周度摘要 - {date}"
    
    if send_rich_text(title, content):
        print("✅ 推送成功！")
        return True
    else:
        # 回退到纯文本
        text = f"{title}\n\n" + "\n".join(content[:5])
        payload = {"msg_type": "text", "content": {"text": f"{FEISHU_KEYWORD} {text}"}}
        try:
            resp = requests.post(FEISHU_WEBHOOK, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
            return resp.json().get("code") == 0
        except Exception as e:
            print(f"回退失败: {e}")
            return False


def test():
    test_msg = f"✅ 连接测试成功 - {datetime.now().strftime('%H:%M')}"
    payload = {"msg_type": "text", "content": {"text": f"{FEISHU_KEYWORD} {test_msg}"}}
    try:
        resp = requests.post(FEISHU_WEBHOOK, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
        print(f"测试响应: {resp.json()}")
    except Exception as e:
        print(f"测试失败: {e}")


if __name__ == "__main__":
    test()

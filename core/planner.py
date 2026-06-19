"""Planner — 自然语言 → 测试步骤"""

import json
import os
import re
from typing import Optional

# 默认 API Key（免费试用用）
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-f0e…83cf")
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

PLANNER_PROMPT = """You are a QA test automation expert. Given a test description in natural language, break it down into concrete, executable test steps.

Available actions:
- navigate: Go to a URL. params: {{"url": "https://..."}}
- click: Click an element. params: {{"selector": "css_selector"}}
- type: Type text into an input. params: {{"selector": "css_selector", "value": "text"}}
- assert: Verify something. params: {{"type": "url_contains|text_exists|element_exists", "expected": "..."}}
- wait: Wait for milliseconds. params: {{"ms": 1000}}
- scroll: Scroll the page. params: {{"direction": "down|up"}}

Rules:
1. Use precise CSS selectors (input[name=email], button[type=submit], .class-name)
2. For login forms, common selectors are: input[name=username/email/password], button[type=submit]
3. For search, common: input[name=q/search], button[type=submit]
4. Each assert step must have a type: "url_contains" (check URL), "text_exists" (check page text), "element_exists"
5. Steps should be sequential, numbered from 1
6. If user didn't specify a URL, the first step should still be navigate

User test description: {description}
{f"Base URL: {base_url}" if base_url else ""}

Reply ONLY this JSON array, no other text:
[
  {{"step": 1, "action": "navigate", "selector": "", "value": "", "desc": "...", "assert": {{"type": "", "expected": ""}}}},
  ...
]
"""


class AITestPlanner:
    """将自然语言测试描述拆解为可执行步骤"""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str = ""):
        self.model = model
        self.api_key = api_key or DEFAULT_API_KEY

    def plan(self, description: str, base_url: str = "") -> list[dict]:
        """解析自然语言 → 测试步骤列表"""
        if not description:
            return []

        try:
            steps = self._call_llm(description, base_url)
            if steps:
                return steps
        except Exception:
            pass

        # LLM 失败时用关键词匹配回退
        return self._keyword_fallback(description, base_url)

    def _call_llm(self, description: str, base_url: str) -> Optional[list[dict]]:
        import httpx

        prompt = PLANNER_PROMPT.format(
            description=description,
            base_url=f"\nBase URL: {base_url}" if base_url else "",
        )

        resp = httpx.post(
            f"{DEFAULT_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 2048,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            return None

        content = resp.json()["choices"][0]["message"]["content"]
        return self._parse_steps(content)

    def _parse_steps(self, text: str) -> Optional[list[dict]]:
        """从 LLM 输出中提取 JSON 步骤数组"""
        # 去掉 markdown 代码块标记
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text)

        try:
            steps = json.loads(text)
            if isinstance(steps, list) and len(steps) > 0:
                return steps
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 数组
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if match:
            try:
                steps = json.loads(match.group())
                if isinstance(steps, list):
                    return steps
            except json.JSONDecodeError:
                pass
        return None

    def _keyword_fallback(self, description: str, base_url: str) -> list[dict]:
        """LLM 失败时的关键词匹配回退"""
        desc_lower = description.lower()
        steps = []

        # 导航
        url = base_url or "https://example.com"
        steps.append({"step": 1, "action": "navigate", "selector": "",
                       "value": "", "desc": f"打开 {url}", "assert": {"type": "", "expected": ""}})

        # 登录检测
        if "登录" in desc_lower or "login" in desc_lower or "注册" in desc_lower:
            if "用户" in desc_lower or "username" in desc_lower or "邮箱" in desc_lower:
                steps.append({"step": 2, "action": "type", "selector": "input[name=username],input[name=email],input[name=login]",
                              "value": "testuser", "desc": "输入用户名/邮箱",
                              "assert": {"type": "", "expected": ""}})
            if "密码" in desc_lower or "password" in desc_lower:
                steps.append({"step": 3, "action": "type", "selector": "input[name=password],input[type=password]",
                              "value": "testpass", "desc": "输入密码",
                              "assert": {"type": "", "expected": ""}})
            steps.append({"step": len(steps) + 1, "action": "click",
                          "selector": "button[type=submit],button:has-text('登录'),button:has-text('Login')",
                          "value": "", "desc": "点击登录/提交",
                          "assert": {"type": "url_contains", "expected": "/dashboard" if "登录" in desc_lower else "/register"}})

        # 搜索检测
        elif "搜索" in desc_lower or "search" in desc_lower or "查询" in desc_lower:
            steps.append({"step": 2, "action": "type", "selector": "input[name=q],input[type=search],input[placeholder*=搜索],input[placeholder*=Search]",
                          "value": "test query", "desc": "输入搜索关键词",
                          "assert": {"type": "", "expected": ""}})
            steps.append({"step": 3, "action": "click",
                          "selector": "button[type=submit],button:has-text('搜索'),button:has-text('Search')",
                          "value": "", "desc": "点击搜索",
                          "assert": {"type": "text_exists", "expected": "result"}})

        # 断言步骤
        last_step = len(steps)
        if last_step > 1:
            steps.append({"step": last_step + 1, "action": "assert", "selector": "",
                          "value": "", "desc": "验证测试结果",
                          "assert": {"type": "text_exists", "expected": "成功"}})

        if len(steps) <= 1:
            steps.append({"step": 2, "action": "assert", "selector": "",
                          "value": "", "desc": "验证页面加载成功",
                          "assert": {"type": "element_exists", "expected": "body"}})

        return steps

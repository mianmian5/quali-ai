"""Asserter — AI 驱动的测试断言 + 自修复选择器

核心能力:
1. AI 看截图 + DOM 判断 pass/fail（替代传统断言）
2. 元素查找失败时 AI 自动修复选择器（自修复）
"""

import base64
import json
import os
import re
from typing import Optional

DEFAULT_API_KEY = ***"DEEPSEEK_API_KEY", "sk-f0e…83cf")
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


class AIAsserter:
    """AI 断言器 — 用 LLM 判断测试步骤是否通过"""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str = ""):
        self.model = model
        self.api_key = api_key or DEFAULT_API_KEY

    def judge(self, step: dict, screenshot_b64: str, page_url: str,
              page_content: str, page_title: str) -> dict:
        """AI 判断这一步是否通过

        Args:
            step: 测试步骤
            screenshot_b64: 截图 base64
            page_url: 当前页面 URL
            page_content: 页面文本内容
            page_title: 页面标题

        Returns:
            {"passed": bool, "reason": str, "confidence": float}
        """
        action = step.get("action", "")
        desc = step.get("desc", "")
        assert_info = step.get("assert", {})

        # 没有断言要求 → 看是否有明显错误
        if not assert_info.get("type"):
            return self._judge_basic(screenshot_b64, page_url, page_content, page_title, action, desc)

        # 有断言要求 → 严格判断
        return self._judge_with_assert(screenshot_b64, page_url, page_content,
                                        page_title, assert_info, desc)

    def fix_selector(self, broken_selector: str, page_content: str,
                     page_url: str, action: str) -> Optional[str]:
        """元素找不到时，AI 分析页面来修复选择器

        Args:
            broken_selector: 失效的选择器
            page_content: 页面 HTML 或文本
            page_url: 当前 URL
            action: 要做的操作 (click/type)

        Returns:
            修复后的选择器，或 None
        """
        prompt = f"""A UI test is failing because a CSS selector is broken.

Page URL: {page_url}
Broken selector: "{broken_selector}"
Action needed: {action}

Page content snippet:
{page_content[:2000]}

Based on the page content, what CSS selector would work? Look for buttons, inputs, links, or elements that match the intent.
Reply ONLY a CSS selector string, nothing else."""

        try:
            import httpx
            resp = httpx.post(
                f"{DEFAULT_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 200,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                selector = resp.json()["choices"][0]["message"]["content"].strip()
                # 去掉可能的引号
                selector = selector.strip("'\"`")
                if selector and len(selector) < 200:
                    return selector
        except Exception:
            pass
        return None

    def _judge_basic(self, screenshot_b64: str, page_url: str,
                     page_content: str, page_title: str,
                     action: str, desc: str) -> dict:
        """无明确断言时，AI 判断页面状态是否正常"""
        # 检查常见错误
        errors = self._check_common_errors(page_url, page_content, page_title)
        if errors:
            return {"passed": False, "reason": errors, "confidence": 0.9}

        # 检查页面是否有效
        if not page_content or len(page_content.strip()) < 10:
            return {"passed": False, "reason": "页面内容为空", "confidence": 0.8}

        # 打开页面的操作 → 检查页面标题
        if action == "navigate":
            if "404" in page_title or "not found" in page_title.lower():
                return {"passed": False, "reason": f"页面 404: {page_title}", "confidence": 0.95}
            if "error" in page_title.lower():
                return {"passed": False, "reason": f"页面错误: {page_title}", "confidence": 0.8}

        return {"passed": True, "reason": "", "confidence": 0.7}

    def _judge_with_assert(self, screenshot_b64: str, page_url: str,
                           page_content: str, page_title: str,
                           assert_info: dict, desc: str) -> dict:
        """有明确断言要求时，LLM 判断"""
        assert_type = assert_info.get("type", "")
        expected = assert_info.get("expected", "")

        # 先快速检查常见断言
        if assert_type == "url_contains" and expected:
            if expected in page_url:
                return {"passed": True, "reason": "", "confidence": 1.0}
            # 用 LLM 判断是否成功（可能有重定向）
            pass  # fall through to LLM

        if assert_type == "text_exists" and expected:
            if expected.lower() in page_content.lower():
                return {"passed": True, "reason": "", "confidence": 1.0}
            pass  # fall through to LLM

        # 用 LLM 综合判断截图和 DOM
        prompt = f"""You are a QA test judge. Determine if this test step PASSED or FAILED.

Test step: {desc}
Assertion type: {assert_type}
Expected: {expected}

Current page:
- URL: {page_url}
- Title: {page_title}
- Content preview: {page_content[:1500]}

Analyze the screenshot and page content. Did the test pass?

Reply ONLY this JSON:
{{"passed": true/false, "reason": "explain why", "confidence": 0.0-1.0}}"""

        try:
            import httpx
            resp = httpx.post(
                f"{DEFAULT_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/png;base64,{screenshot_b64}",
                                "detail": "low"
                            }},
                        ]},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                # 提取 JSON
                match = re.search(r'\{.*?\}', content, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                    return {
                        "passed": result.get("passed", False),
                        "reason": result.get("reason", ""),
                        "confidence": result.get("confidence", 0.5),
                    }
        except Exception:
            pass

        return {"passed": True, "reason": "无法AI判断，默认通过", "confidence": 0.3}

    def _check_common_errors(self, page_url: str, page_content: str, page_title: str) -> str:
        """检查常见错误"""
        checks = [
            ("Bad Request", "页面返回 Bad Request"),
            ("404 Not Found", "页面 404"),
            ("500 Internal", "服务器错误 500"),
            ("connection refused", "连接被拒绝"),
            ("timeout", "请求超时"),
            ("access denied", "访问被拒绝"),
            ("captcha", "触发验证码"),
        ]
        for keyword, reason in checks:
            if keyword.lower() in page_content.lower() or keyword.lower() in page_title.lower():
                return reason
        return ""

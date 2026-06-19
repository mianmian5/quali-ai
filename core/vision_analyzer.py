"""Vision Analyzer — AI 视觉分析模块

用于移动端测试：分析截图找到 UI 元素坐标，替代 CSS 选择器。
对截图进行 OCR-free 的视觉理解，通过 LLM 定位目标元素位置。
"""

import base64
import json
import os
import re
from typing import Optional

DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-f0e83cf")
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


class VisionAnalyzer:
    """视觉分析器 — 用 AI 理解屏幕内容并定位 UI 元素"""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str = ""):
        self.model = model
        self.api_key = api_key or DEFAULT_API_KEY

    def find_element(self, screenshot_b64: str, target: str, action: str,
                     screen_width: int, screen_height: int) -> Optional[dict]:
        """在截图中找到目标元素的位置

        Args:
            screenshot_b64: 截图 base64
            target: 要找的元素描述，如"登录按钮"、"搜索框"
            action: 要执行的操作 (tap/text/swipe)
            screen_width: 屏幕宽度
            screen_height: 屏幕高度

        Returns:
            {"x": int, "y": int, "label": str, "confidence": float}
            或 None
        """
        prompt = """You are a mobile UI testing assistant. Given a screenshot of an Android app,
identify the location of the specified UI element.

Screen: %dx%d

Task: Find the "%s" element to perform a "%s" action.

Analyze the screenshot and determine where this element is located.
Reply ONLY this JSON:
{"x": coordinate, "y": coordinate, "label": "element description", "confidence": 0.0-1.0}

The coordinates should be accurate pixel positions on the %dx%d screen.
For buttons/inputs, use the center of the element.""" % (screen_width, screen_height, target, action, screen_width, screen_height)

        try:
            import httpx
            resp = httpx.post(
                DEFAULT_BASE_URL + "/chat/completions",
                headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": "data:image/png;base64," + screenshot_b64,
                                "detail": "high",
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
                match = re.search(r"\{.*?\}", content, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                    x, y = int(result.get("x", 0)), int(result.get("y", 0))
                    confidence = float(result.get("confidence", 0))
                    label = result.get("label", target)
                    # Validate coordinates are within screen bounds
                    if 0 <= x <= screen_width and 0 <= y <= screen_height:
                        return {"x": x, "y": y, "label": label, "confidence": confidence}
        except Exception:
            pass

        return None

    def verify_screen(self, screenshot_b64: str, expected_state: str) -> dict:
        """验证当前屏幕是否符合预期状态

        Args:
            screenshot_b64: 截图 base64
            expected_state: 预期状态描述，如"登录成功后的首页"

        Returns:
            {"matched": bool, "reason": str, "details": str}
        """
        prompt = """Analyze this mobile app screenshot.

Expected state: %s

Is the app currently in this state? Reply ONLY this JSON:
{"matched": true/false, "reason": "why you think so", "details": "what you see on screen"}""" % expected_state

        try:
            import httpx
            resp = httpx.post(
                DEFAULT_BASE_URL + "/chat/completions",
                headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {
                                "url": "data:image/png;base64," + screenshot_b64,
                                "detail": "low",
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
                match = re.search(r"\{.*?\}", content, re.DOTALL)
                if match:
                    return json.loads(match.group())
        except Exception:
            pass

        return {"matched": False, "reason": "AI analysis failed", "details": ""}

    def find_text_input(self, screenshot_b64: str, screen_width: int, screen_height: int) -> Optional[dict]:
        """找到屏幕上的文本输入框"""
        return self.find_element(screenshot_b64, "text input field", "text",
                                 screen_width, screen_height)

"""Executor — 用 Playwright 执行测试步骤"""

import asyncio
import base64
import os
import time
from typing import Optional

from core.asserter import AIAsserter


class PlaywrightExecutor:
    """Playwright 测试执行器"""

    def __init__(self, headless: bool = True, use_ai_assert: bool = True):
        self.headless = headless
        self.use_ai_assert = use_ai_assert
        self.asserter = AIAsserter() if use_ai_assert else None
        self._playwright = None
        self._browser = None
        self._page = None
        self._self_heal_count = 0

    def run(self, steps: list[dict]) -> list[dict]:
        """执行测试步骤列表，返回结果"""
        return asyncio.run(self._run_async(steps))

    async def _run_async(self, steps: list[dict]) -> list[dict]:
        from playwright.async_api import async_playwright

        results = []

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-blink-features=AutomationControlled",
                      "--disable-gpu"],
            )
            ctx = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            )
            await ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            self._page = await ctx.new_page()

            for step in steps:
                result = await self._execute_step(step)
                results.append(result)

        except Exception as e:
            results.append({
                "step": -1, "action": "error", "desc": f"执行器异常: {e}",
                "passed": False, "reason": str(e), "screenshot": "",
            })
        finally:
            await self._cleanup()

        return results

    async def _execute_step(self, step: dict) -> dict:
        """执行单个测试步骤"""
        action = step.get("action", "")
        selector = step.get("selector", "")
        value = step.get("value", "")
        desc = step.get("desc", "")
        step_num = step.get("step", 0)
        start_time = time.time()

        result = {
            "step": step_num,
            "action": action,
            "desc": desc,
            "passed": True,
            "reason": "",
            "screenshot": "",
            "duration": 0,
            "url": "",
        }

        try:
            if action == "navigate":
                url = value or selector or "about:blank"
                try:
                    await self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await self._page.wait_for_timeout(1000)
                except Exception as e:
                    result["reason"] = f"导航超时或失败: {e}"
                result["url"] = self._page.url

            elif action == "click":
                await self._smart_click(selector)

            elif action == "type":
                await self._smart_type(selector, value)

            elif action == "wait":
                ms = min(int(value or 1000), 10000)
                await self._page.wait_for_timeout(ms)

            elif action == "scroll":
                direction = value or selector or "down"
                if direction == "down":
                    await self._page.evaluate("window.scrollBy(0, window.innerHeight)")
                else:
                    await self._page.evaluate("window.scrollBy(0, -window.innerHeight)")
                await self._page.wait_for_timeout(300)

            # 截图
            result["screenshot"] = await self._screenshot()

            # Phase 2: AI 断言
            if self.use_ai_assert and self.asserter and action != "assert":
                await self._ai_judge(step, result)

        except Exception as e:
            result["passed"] = False
            result["reason"] = str(e)[:200]
            result["screenshot"] = await self._screenshot()

        result["duration"] = round(time.time() - start_time, 2)
        result["url"] = self._page.url
        return result

    async def _ai_judge(self, step: dict, result: dict) -> None:
        """AI 综合判断步骤是否通过"""
        page_url = self._page.url
        page_title = await self._page.title()
        page_content = await self._page.evaluate("document.body.innerText")

        judge_result = self.asserter.judge(
            step=step,
            screenshot_b64=result.get("screenshot", ""),
            page_url=page_url,
            page_content=page_content[:3000],
            page_title=page_title,
        )
        if not judge_result.get("passed"):
            result["passed"] = False
            result["reason"] = judge_result.get("reason", "")
            result["reason"] += f" (AI置信度: {judge_result.get('confidence', 0)})"

    async def _smart_click(self, selector: str) -> None:
        """智能点击：尝试多种选择器 + AI 自修复"""
        selectors = [s.strip() for s in selector.split(",") if s.strip()]
        if not selectors:
            selectors = ["button", "a", "[type=submit]", "input[type=submit]"]

        for sel in selectors:
            try:
                loc = self._page.locator(sel)
                if await loc.count() > 0:
                    await loc.first.click(timeout=3000)
                    await self._page.wait_for_timeout(1000)
                    return
            except Exception:
                continue

        # AI 自修复
        if self.asserter:
            page_content = await self._page.evaluate("document.body.innerText")
            page_url = self._page.url
            fixed = self.asserter.fix_selector(selector, page_content, page_url, "click")
            if fixed:
                try:
                    loc = self._page.locator(fixed)
                    if await loc.count() > 0:
                        await loc.first.click(timeout=3000)
                        await self._page.wait_for_timeout(1000)
                        self._self_heal_count += 1
                        return
                except Exception:
                    pass

        raise Exception(f"找不到可点击元素: {selector}")

    async def _smart_type(self, selector: str, value: str) -> None:
        """智能输入：尝试多种选择器 + AI 自修复"""
        selectors = [s.strip() for s in selector.split(",") if s.strip()]
        if not selectors:
            selectors = ["input", "textarea", "[contenteditable]"]

        for sel in selectors:
            try:
                loc = self._page.locator(sel)
                if await loc.count() > 0:
                    await loc.first.fill(value, timeout=3000)
                    await self._page.wait_for_timeout(500)
                    return
            except Exception:
                continue

        # AI 自修复
        if self.asserter:
            page_content = await self._page.evaluate("document.body.innerText")
            page_url = self._page.url
            fixed = self.asserter.fix_selector(selector, page_content, page_url, "type")
            if fixed:
                try:
                    loc = self._page.locator(fixed)
                    if await loc.count() > 0:
                        await loc.first.fill(value, timeout=3000)
                        await self._page.wait_for_timeout(500)
                        self._self_heal_count += 1
                        return
                except Exception:
                    pass

        raise Exception(f"找不到可输入元素: {selector}")

    async def _screenshot(self) -> str:
        """截图返回 base64"""
        try:
            img = await self._page.screenshot(type="png", full_page=False)
            return base64.b64encode(img).decode()
        except Exception:
            return ""

    async def _cleanup(self):
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

"""Executor — 用 Playwright 执行测试步骤"""

import asyncio
import base64
import os
import time
from typing import Optional


class PlaywrightExecutor:
    """Playwright 测试执行器"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

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
        assert_info = step.get("assert", {})
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

            elif action == "assert":
                await self._do_assert(result, assert_info)

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

        except Exception as e:
            result["passed"] = False
            result["reason"] = str(e)[:200]
            result["screenshot"] = await self._screenshot()

        result["duration"] = round(time.time() - start_time, 2)
        result["url"] = self._page.url
        return result

    async def _smart_click(self, selector: str) -> None:
        """智能点击：尝试多种选择器"""
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
        raise Exception(f"找不到可点击元素: {selector}")

    async def _smart_type(self, selector: str, value: str) -> None:
        """智能输入：尝试多种选择器"""
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
        raise Exception(f"找不到可输入元素: {selector}")

    async def _do_assert(self, result: dict, assert_info: dict) -> None:
        """执行断言"""
        assert_type = assert_info.get("type", "")
        expected = assert_info.get("expected", "")

        if not assert_type:
            return

        if assert_type == "url_contains":
            current_url = self._page.url
            if expected and expected not in current_url:
                result["passed"] = False
                result["reason"] = f"URL 不包含期望值。当前: {current_url}, 期望包含: {expected}"

        elif assert_type == "text_exists":
            body_text = await self._page.evaluate("document.body.innerText")
            if expected and expected.lower() not in body_text.lower():
                result["passed"] = False
                result["reason"] = f"页面未找到期望文本: {expected}"

        elif assert_type == "element_exists":
            try:
                el = self._page.locator(expected or "body")
                count = await el.count()
                if count == 0:
                    result["passed"] = False
                    result["reason"] = f"元素不存在: {expected}"
            except Exception:
                result["passed"] = False
                result["reason"] = f"查找元素失败: {expected}"

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

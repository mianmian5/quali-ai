"""ADB Executor — 在安卓设备上执行测试步骤

结合 ADB 控制器和视觉分析器，在手机上执行 navigate/click/type/assert 等操作。
"""

import time
from typing import Optional

from core.adb_controller import ADBController
from core.vision_analyzer import VisionAnalyzer


class ADBExecutor:
    """安卓测试执行器 — 通过 ADB + AI 视觉在手机上执行测试"""

    def __init__(self, device_id: Optional[str] = None, use_vision: bool = True):
        self.adb = ADBController(device_id)
        self.vision = VisionAnalyzer() if use_vision else None
        self.use_vision = use_vision
        self._width, self._height = (1080, 1920)

    def run(self, steps: list[dict]) -> list[dict]:
        """执行测试步骤列表"""
        results = []
        try:
            if not self.adb.is_connected():
                raise RuntimeError("No Android device connected")

            self._width, self._height = self.adb.screen_size()

            for step in steps:
                result = self._execute_step(step)
                results.append(result)
        except Exception as e:
            results.append({
                "step": -1, "action": "error", "desc": "Executor error",
                "passed": False, "reason": str(e), "screenshot": "",
            })
        return results

    def _execute_step(self, step: dict) -> dict:
        """执行单个测试步骤"""
        action = step.get("action", "")
        value = step.get("value", "")
        desc = step.get("desc", "")
        step_num = step.get("step", 0)
        start = time.time()

        result = {
            "step": step_num,
            "action": action,
            "desc": desc,
            "passed": True,
            "reason": "",
            "screenshot": "",
            "duration": 0,
            "url": self.adb.current_app(),
        }

        try:
            if action == "navigate":
                # 启动 App
                package = value or step.get("selector", "")
                if package:
                    self.adb.open_app(package)
                    self.adb.wait(2000)
                result["url"] = self.adb.current_app()

            elif action == "click":
                target = value or step.get("selector", "button")
                element = self._find_element(target, "tap")
                if element:
                    self.adb.tap(element["x"], element["y"])
                    self.adb.wait(500)
                else:
                    result["passed"] = False
                    result["reason"] = "Could not locate: " + target

            elif action == "type":
                target = step.get("selector", "input")
                element = self._find_element(target, "text")
                if element:
                    self.adb.tap(element["x"], element["y"])
                    self.adb.wait(300)
                    self.adb.text(value)
                else:
                    result["passed"] = False
                    result["reason"] = "Could not locate input: " + target

            elif action == "assert":
                screenshot = self.adb.screenshot()
                assert_info = step.get("assert", {})
                expected = assert_info.get("expected", "")
                if expected and self.vision:
                    screen_state = assert_info.get("type", "")
                    if screen_state == "app_running":
                        current = self.adb.current_app()
                        if expected not in current:
                            result["passed"] = False
                            result["reason"] = "Expected app not running: " + expected

            elif action == "wait":
                ms = int(value or 1000)
                self.adb.wait(ms)

            elif action == "swipe":
                parts = value.split(",")
                if len(parts) == 4:
                    x1, y1, x2, y2 = map(int, parts)
                    self.adb.swipe(x1, y1, x2, y2)
                else:
                    # Default: swipe up
                    self.adb.swipe(self._width // 2, self._height * 3 // 4,
                                   self._width // 2, self._height // 4)

            elif action == "back":
                self.adb.press_back()
                self.adb.wait(500)

            elif action == "home":
                self.adb.press_home()
                self.adb.wait(500)

            # Screenshot after step
            result["screenshot"] = self.adb.screenshot()

        except Exception as e:
            result["passed"] = False
            result["reason"] = str(e)[:200]
            try:
                result["screenshot"] = self.adb.screenshot()
            except Exception:
                pass

        result["duration"] = round(time.time() - start, 2)
        return result

    def _find_element(self, target: str, action: str) -> Optional[dict]:
        """通过 AI 视觉找到元素坐标"""
        if not self.vision:
            return None

        screenshot = self.adb.screenshot()
        return self.vision.find_element(
            screenshot_b64=screenshot,
            target=target,
            action=action,
            screen_width=self._width,
            screen_height=self._height,
        )

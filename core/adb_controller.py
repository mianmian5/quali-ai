"""ADB Controller — 通过 ADB 控制安卓设备

提供截图、点击、输入、滑动等基础操作，作为 Playwright 的移动端替代。
"""

import base64
import io
import os
import re
import subprocess
import tempfile
import time
from typing import Optional


class ADBController:
    """安卓设备控制器，封装 ADB 命令"""

    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self._check_adb()

    def _check_adb(self):
        """检查 ADB 是否可用"""
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise RuntimeError("ADB not found. Install Android platform tools.")
        except FileNotFoundError:
            raise RuntimeError("adb command not found. Install Android platform tools.")

    def devices(self) -> list[str]:
        """列出连接的设备"""
        result = subprocess.run(
            ["adb"] + (["-s", self.device_id] if self.device_id else []) + ["devices"],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.strip().split("\n")[1:]  # skip header
        devices = []
        for line in lines:
            if line.strip() and "device" in line and "offline" not in line:
                devices.append(line.split("\t")[0])
        return devices

    def ensure_device(self) -> str:
        """确保有可用设备，返回 device_id"""
        if self.device_id:
            return self.device_id
        devices = self.devices()
        if not devices:
            raise RuntimeError("No Android device connected. Connect via USB or WiFi.")
        self.device_id = devices[0]
        return self.device_id

    def _adb(self, *args: str) -> subprocess.CompletedProcess:
        """执行 ADB 命令"""
        cmd = ["adb"]
        if self.device_id:
            cmd += ["-s", self.device_id]
        cmd += list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def screenshot(self) -> str:
        """截取屏幕截图，返回 base64"""
        self.ensure_device()
        result = self._adb("exec-out", "screencap", "-p")
        if result.returncode != 0:
            raise RuntimeError("Screenshot failed: " + result.stderr)
        return base64.b64encode(result.stdout).decode()

    def tap(self, x: int, y: int):
        """点击坐标"""
        self.ensure_device()
        self._adb("shell", "input", "tap", str(x), str(y))

    def text(self, text: str):
        """输入文本"""
        self.ensure_device()
        # Escape special characters for shell
        safe_text = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        self._adb("shell", "input", "text", safe_text)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """滑动"""
        self.ensure_device()
        self._adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2),
                   str(duration_ms))

    def keyevent(self, keycode: int):
        """发送按键事件 (keycode: 4=back, 3=home, 66=enter)"""
        self.ensure_device()
        self._adb("shell", "input", "keyevent", str(keycode))

    def press_back(self):
        """返回键"""
        self.keyevent(4)

    def press_home(self):
        """Home 键"""
        self.keyevent(3)

    def press_enter(self):
        """回车键"""
        self.keyevent(66)

    def open_app(self, package: str, activity: Optional[str] = None):
        """启动 App"""
        self.ensure_device()
        if activity:
            self._adb("shell", "am", "start", "-n", "%s/%s" % (package, activity))
        else:
            self._adb("shell", "monkey", "-p", package, "-c",
                       "android.intent.category.LAUNCHER", "1")

    def close_app(self, package: str):
        """关闭 App"""
        self.ensure_device()
        self._adb("shell", "am", "force-stop", package)

    def current_app(self) -> str:
        """获取当前前台 App 包名"""
        self.ensure_device()
        result = self._adb("shell", "dumpsys", "window", "windows")
        for line in result.stdout.split("\n"):
            if "mCurrentFocus" in line:
                match = re.search(r"([a-zA-Z0-9.]+)/", line)
                if match:
                    return match.group(1)
        return ""

    def screen_size(self) -> tuple[int, int]:
        """获取屏幕尺寸 (width, height)"""
        self.ensure_device()
        result = self._adb("shell", "wm", "size")
        match = re.search(r"(\d+)x(\d+)", result.stdout)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (1080, 1920)  # default fallback

    def wait(self, ms: int = 1000):
        """等待"""
        time.sleep(ms / 1000)

    def is_connected(self) -> bool:
        """检查设备是否连接"""
        try:
            self.ensure_device()
            return True
        except RuntimeError:
            return False

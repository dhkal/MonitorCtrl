"""配置 / 场景配置文件持久化（%APPDATA%\\MonitorCtrl）。"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional

APP_NAME = "MonitorCtrl"
APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "monitorctl.log")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "hotkeys": True,
    "tray": True,
    "start_minimized": False,
    "autostart": False,
    "apply_last_on_start": False,
    "poll_interval": 0,      # 秒；0 = 不轮询外部亮度变化
}


def ensure_dir() -> None:
    os.makedirs(APP_DIR, exist_ok=True)


class Config:
    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self.settings: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.last_state: Dict[str, Dict[str, int]] = {}
        self.load()

    # ------------------------------------------------------------------ #
    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.settings.update(data.get("settings") or {})
            self.profiles = data.get("profiles") or {}
            self.last_state = data.get("last_state") or {}
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        ensure_dir()
        payload = {
            "version": 1,
            "settings": self.settings,
            "profiles": self.profiles,
            "last_state": self.last_state,
        }
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # -- 设置 ------------------------------------------------------------ #
    def get(self, key: str, default=None):
        return self.settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.save()

    # -- 配置文件（profile） --------------------------------------------- #
    def save_profile(self, name: str, monitors: Dict[str, Dict[str, int]],
                     labels: Optional[Dict[str, str]] = None) -> None:
        self.profiles[name] = {
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "monitors": monitors,
            "labels": labels or {},
        }
        self.save()

    def delete_profile(self, name: str) -> None:
        self.profiles.pop(name, None)
        self.save()

    def remember_state(self, monitor_key: str, values: Dict[int, int]) -> None:
        self.last_state[monitor_key] = {str(k): int(v) for k, v in values.items()}

    # -- 开机自启 -------------------------------------------------------- #
    @staticmethod
    def autostart_command() -> str:
        if getattr(sys, "frozen", False):
            return '"%s"' % sys.executable
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        return '"%s" "%s"' % (sys.executable, script)

    @staticmethod
    def set_autostart(enabled: bool) -> bool:
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                if enabled:
                    winreg.SetValueEx(
                        key, APP_NAME, 0, winreg.REG_SZ, Config.autostart_command()
                    )
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
            return True
        except OSError:
            return False

    @staticmethod
    def is_autostart_enabled() -> bool:
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
            ) as key:
                winreg.QueryValueEx(key, APP_NAME)
                return True
        except OSError:
            return False

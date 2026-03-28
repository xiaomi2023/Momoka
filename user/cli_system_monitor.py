"""
user/cli_system_monitor.py —— 系统配置变更监控。

监控 Windows 注册表、Linux 和 macOS 系统配置的变更，
当检测到变更时向用户发送 WARN 提示。
"""

import sys
import threading
import time
import hashlib
import os
from pathlib import Path
from typing import Callable


class SystemConfigMonitor:
    """跨平台系统配置监控器。"""

    def __init__(self, on_change: Callable[[str], None]):
        """
        Args:
            on_change: 配置变更时的回调函数，接收变更描述字符串
        """
        self.on_change = on_change
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._snapshots: dict[str, str] = {}  # 路径 -> 哈希快照

    def start(self) -> None:
        """启动监控线程。"""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        self._initialize_snapshots()

        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self) -> None:
        """停止监控线程。"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)

    def _initialize_snapshots(self) -> None:
        """初始化监控目标的快照。"""
        if sys.platform == 'win32':
            self._init_windows_snapshots()
        elif sys.platform == 'darwin':
            self._init_macos_snapshots()
        else:  # Linux
            self._init_linux_snapshots()

    def _init_windows_snapshots(self) -> None:
        """初始化 Windows 注册表关键项的快照。"""
        try:
            import winreg

            # 监控的关键注册表路径
            self._registry_keys = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Policies"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services"),
            ]

            for hive, key_path in self._registry_keys:
                snapshot = self._get_registry_snapshot(hive, key_path)
                if snapshot is not None:
                    self._snapshots[f"REG:{key_path}"] = snapshot
        except Exception:
            pass

    def _init_macos_snapshots(self) -> None:
        """初始化 macOS plist 配置文件的快照。"""
        paths_to_monitor = [
            Path.home() / "Library/Preferences",
            "/Library/Preferences",
        ]

        for path in paths_to_monitor:
            if path.exists():
                self._snapshot_directory(path)

    def _init_linux_snapshots(self) -> None:
        """初始化 Linux 配置文件的快照。"""
        paths_to_monitor = [
            Path("/etc"),
            Path.home() / ".config",
        ]

        for path in paths_to_monitor:
            if path.exists():
                self._snapshot_directory(path)

    def _snapshot_directory(self, path: Path) -> None:
        """对目录中的配置文件创建快照。"""
        try:
            if path.is_file():
                content = self._read_file_safe(path)
                if content is not None:
                    self._snapshots[str(path)] = self._compute_hash(content)
            elif path.is_dir():
                # 只监控常见的配置文件
                config_extensions = {'.conf', '.cfg', '.ini', '.json', '.yaml', '.yml', '.xml', '.plist'}
                max_files = 100  # 限制监控文件数量

                count = 0
                for item in path.rglob('*'):
                    if count >= max_files:
                        break
                    if item.is_file() and item.suffix.lower() in config_extensions:
                        content = self._read_file_safe(item)
                        if content is not None:
                            self._snapshots[str(item)] = self._compute_hash(content)
                            count += 1
        except Exception:
            pass

    def _read_file_safe(self, path: Path) -> bytes | None:
        """安全读取文件内容。"""
        try:
            # 跳过过大的文件
            if path.stat().st_size > 1024 * 1024:  # 1MB
                return None
            return path.read_bytes()
        except Exception:
            return None

    def _compute_hash(self, content: bytes) -> str:
        """计算内容的 MD5 哈希。"""
        return hashlib.md5(content).hexdigest()

    def _get_registry_snapshot(self, hive, key_path: str) -> str | None:
        """获取 Windows 注册表项的快照。"""
        try:
            import winreg
            key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ)
            values = []

            try:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        values.append(f"{name}={value}")
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(key)

            return self._compute_hash('|'.join(sorted(values)).encode())
        except Exception:
            return None

    def _monitor_loop(self) -> None:
        """监控循环，定期检查变更。"""
        check_interval = 5.0  # 每 5 秒检查一次

        while not self._stop_event.is_set():
            try:
                self._check_changes()
            except Exception:
                pass

            # 使用事件等待，以便快速响应停止信号
            self._stop_event.wait(check_interval)

    def _check_changes(self) -> None:
        """检查是否有配置变更。"""
        if sys.platform == 'win32':
            self._check_windows_changes()
        elif sys.platform == 'darwin':
            self._check_macos_changes()
        else:
            self._check_linux_changes()

    def _check_windows_changes(self) -> None:
        """检查 Windows 注册表变更。"""
        try:
            import winreg

            for hive, key_path in getattr(self, '_registry_keys', []):
                key_name = f"REG:{key_path}"
                old_snapshot = self._snapshots.get(key_name)
                new_snapshot = self._get_registry_snapshot(hive, key_path)

                if new_snapshot is not None and old_snapshot != new_snapshot:
                    self._snapshots[key_name] = new_snapshot
                    self.on_change(
                        f"We detected some changes to the system configuration:\n"
                        f"{key_path}\n"
                        f"If this does not meet your expectations, consider STOPPING IMMEDIATELY and carefully examine what happened."
                    )
        except Exception:
            pass

    def _check_macos_changes(self) -> None:
        """检查 macOS 配置变更。"""
        changed_items = []

        # 检查现有快照
        for path_str, old_hash in list(self._snapshots.items()):
            path = Path(path_str)
            if not path.exists():
                changed_items.append(f"Removed: {path_str}")
                del self._snapshots[path_str]
                continue

            content = self._read_file_safe(path)
            if content is not None:
                new_hash = self._compute_hash(content)
                if new_hash != old_hash:
                    changed_items.append(f"Modified: {path_str}")
                    self._snapshots[path_str] = new_hash

        # 检查新文件
        paths_to_check = [
            Path.home() / "Library/Preferences",
            "/Library/Preferences",
        ]

        for base_path in paths_to_check:
            if base_path.exists():
                for item in base_path.rglob('*.plist'):
                    path_str = str(item)
                    if path_str not in self._snapshots:
                        content = self._read_file_safe(item)
                        if content is not None:
                            self._snapshots[path_str] = self._compute_hash(content)
                            changed_items.append(f"New: {path_str}")

        if changed_items:
            self.on_change(
                f"We detected some changes to the system configuration, including:\n"
                f"{', '.join(changed_items[:5])}\n"
                f"If this does not meet your expectations, consider STOPPING IMMEDIATELY and carefully examine what happened."
            )

    def _check_linux_changes(self) -> None:
        """检查 Linux 配置变更。"""
        changed_items = []

        # 检查现有快照
        for path_str, old_hash in list(self._snapshots.items()):
            path = Path(path_str)
            if not path.exists():
                changed_items.append(f"Removed: {path_str}")
                del self._snapshots[path_str]
                continue

            content = self._read_file_safe(path)
            if content is not None:
                new_hash = self._compute_hash(content)
                if new_hash != old_hash:
                    changed_items.append(f"Modified: {path_str}")
                    self._snapshots[path_str] = new_hash

        if changed_items:
            self.on_change(
                f"We detected some changes to the system configuration, including:\n"
                f"{', '.join(changed_items[:5])}\n"
                f"If this does not meet your expectations, consider STOPPING IMMEDIATELY and carefully examine what happened."
            )


# 全局监控器实例（可选，用于模块级访问）
_global_monitor: SystemConfigMonitor | None = None


def start_monitoring(on_change: Callable[[str], None]) -> SystemConfigMonitor:
    """启动系统配置监控。

    Args:
        on_change: 配置变更时的回调函数

    Returns:
        监控器实例
    """
    monitor = SystemConfigMonitor(on_change)
    monitor.start()
    return monitor


def stop_monitoring(monitor: SystemConfigMonitor | None = None) -> None:
    """停止系统配置监控。

    Args:
        monitor: 要停止的监控器，如果为 None 则停止全局监控器
    """
    global _global_monitor

    if monitor is not None:
        monitor.stop()
    elif _global_monitor is not None:
        _global_monitor.stop()
        _global_monitor = None
"""
user/cli/system_monitor.py —— 系统配置变更监控。

使用 watchdog 库实现事件驱动的系统配置监控，
在 Linux/macOS 上使用 inotify/FSEvents，性能开销极低。
"""

import sys
import os
import threading
import hashlib
import time
from pathlib import Path
from typing import Callable

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class ConfigChangeHandler(FileSystemEventHandler):
    """配置文件变更处理器。"""

    def __init__(self, on_change: Callable[[str], None], monitored_files: set[str]):
        """
        Args:
            on_change: 配置变更时的回调函数
            monitored_files: 需要监控的文件路径集合
        """
        super().__init__()
        self.on_change = on_change
        self.monitored_files = monitored_files
        self._snapshots: dict[str, str] = {}
        self._initialize_snapshots()

    def _initialize_snapshots(self) -> None:
        """初始化监控文件的快照。"""
        for path_str in self.monitored_files:
            path = Path(path_str)
            if path.exists() and path.is_file():
                content = self._read_file_safe(path)
                if content is not None:
                    self._snapshots[path_str] = self._compute_hash(content)

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

    def _handle_file_change(self, path: str, change_type: str) -> None:
        """处理文件变更事件。"""
        # 检查是否是监控的文件
        if path not in self.monitored_files:
            return

        if change_type == 'deleted':
            if path in self._snapshots:
                del self._snapshots[path]
                self.on_change(
                    f"We detected some changes to the system configuration:\n"
                    f"Removed: {path}\n"
                    f"If this does not meet your expectations, consider STOPPING IMMEDIATELY and carefully examine what happened."
                )
            return

        # 文件或内容变更
        path_obj = Path(path)
        if not path_obj.exists():
            return

        content = self._read_file_safe(path_obj)
        if content is None:
            return

        new_hash = self._compute_hash(content)
        old_hash = self._snapshots.get(path)

        if old_hash != new_hash:
            self._snapshots[path] = new_hash
            self.on_change(
                f"We detected some changes to the system configuration:\n"
                f"{change_type}: {path}\n"
                f"If this does not meet your expectations, consider STOPPING IMMEDIATELY and carefully examine what happened."
            )

    def on_modified(self, event):
        """文件修改事件。"""
        if not event.is_directory:
            self._handle_file_change(event.src_path, 'Modified')

    def on_created(self, event):
        """文件创建事件。"""
        if not event.is_directory:
            self._handle_file_change(event.src_path, 'New')

    def on_deleted(self, event):
        """文件删除事件。"""
        if not event.is_directory:
            self._handle_file_change(event.src_path, 'Removed')


class SystemConfigMonitor:
    """跨平台系统配置监控器（使用 watchdog 事件驱动）。"""

    def __init__(self, on_change: Callable[[str], None]):
        """
        Args:
            on_change: 配置变更时的回调函数，接收变更描述字符串
        """
        self.on_change = on_change
        self._observer: Observer | None = None
        self._handler: ConfigChangeHandler | None = None
        self._monitored_files: set[str] = set()
        self._running = False

    def _detect_shell_config(self) -> list[Path]:
        """动态检测当前用户的 shell 配置文件。"""
        files = []
        home = Path.home()

        # 1. 检测当前用户的默认 shell
        shell = self._get_current_shell()
        
        if shell:
            shell_name = Path(shell).name.lower()
            
            # 根据 shell 类型添加配置文件
            shell_configs = {
                'bash': ['.bashrc', '.bash_profile', '.profile'],
                'zsh': ['.zshrc', '.zprofile', '.profile'],
                'fish': ['.config/fish/config.fish'],
                'ash': ['.profile'],
                'dash': ['.profile'],
            }
            
            for config in shell_configs.get(shell_name, ['.profile']):
                config_path = home / config
                if config_path.exists():
                    files.append(config_path)

        # 2. 检测常见环境变量文件（无论 shell 类型）
        env_files = [
            home / '.profile',
            home / '.xprofile',
            home / '.pam_environment',
            home / '.xsessionrc',
        ]
        for path in env_files:
            if path.exists() and path not in files:
                files.append(path)

        return files

    def _get_current_shell(self) -> str | None:
        """获取当前用户的默认 shell 路径。"""
        try:
            # macOS / Linux: 读取 /etc/passwd 或 dscl
            if sys.platform == 'darwin':
                import subprocess
                result = subprocess.run(
                    ['dscl', '.', '-read', '/Users/' + os.environ.get('USER', ''), 'UserShell'],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    # 输出格式: "UserShell: /bin/zsh"
                    return result.stdout.split(': ', 1)[-1].strip()
            
            # Linux: 读取 /etc/passwd
            import os
            username = os.environ.get('USER', '')
            if username:
                passwd_file = Path('/etc/passwd')
                if passwd_file.exists():
                    content = passwd_file.read_text()
                    for line in content.splitlines():
                        if line.startswith(username + ':'):
                            return line.split(':')[-1]
        except Exception:
            pass

        # Fallback: 检查 SHELL 环境变量
        import os
        return os.environ.get('SHELL')

    def _get_monitored_files(self) -> set[str]:
        """获取需要监控的配置文件列表。"""
        files = set()

        if sys.platform == 'win32':
            # Windows: 监控注册表不适用 watchdog，保留原有逻辑
            return files

        # 动态检测 shell 配置文件
        shell_configs = self._detect_shell_config()
        for path in shell_configs:
            files.add(str(path))

        # 通用系统配置文件（跨平台）
        common_system_files = [
            Path('/etc/hosts'),
            Path('/etc/resolv.conf'),
            Path('/etc/hostname'),
        ]
        
        for path in common_system_files:
            if path.exists():
                files.add(str(path))

        return files

    def _get_directories_to_watch(self) -> list[tuple[str, bool]]:
        """获取需要监控的目录列表，返回 (目录路径, 是否递归)。"""
        dirs = []

        if sys.platform == 'win32':
            # Windows 不使用 watchdog
            return dirs

        # 动态获取需要监控的目录（基于已检测的配置文件）
        # 只监控存在配置文件的目录，避免监控整个 /etc
        monitored_dirs_set = set()
        
        # 1. 配置文件所在目录
        for file_path in self._monitored_files:
            parent = Path(file_path).parent
            monitored_dirs_set.add(str(parent))
        
        # 2. 系统配置目录（如果包含配置文件）
        system_dirs = [
            Path('/etc'),
            Path.home() / '.config',
        ]
        
        for sys_dir in system_dirs:
            if sys_dir.exists():
                # 只在该目录包含配置文件时才添加
                has_config = False
                config_extensions = {'.conf', '.cfg', '.ini', '.json', '.yaml', '.yml', '.xml', '.plist'}
                for ext in config_extensions:
                    if list(sys_dir.glob(f'*{ext}')):
                        has_config = True
                        break
                
                if has_config:
                    monitored_dirs_set.add(str(sys_dir))
        
        # 转换为列表（不递归监控，仅监控直接子文件）
        for dir_path in monitored_dirs_set:
            dirs.append((dir_path, False))

        return dirs

    def start(self) -> None:
        """启动监控。"""
        if self._running:
            return

        # Windows 或不支持 watchdog 时不使用事件驱动
        if sys.platform == 'win32' or not WATCHDOG_AVAILABLE:
            return

        try:
            # 获取监控目标
            self._monitored_files = self._get_monitored_files()
            dirs_to_watch = self._get_directories_to_watch()

            if not self._monitored_files and not dirs_to_watch:
                # 没有需要监控的目标，直接返回
                return

            # 创建处理器
            self._handler = ConfigChangeHandler(self.on_change, self._monitored_files)

            # 创建观察者
            self._observer = Observer()

            # 添加目录监控（用于捕获新文件的创建）
            for dir_path, recursive in dirs_to_watch:
                self._observer.schedule(
                    self._handler,
                    dir_path,
                    recursive=recursive
                )

            # 添加单个文件的目录监控（确保文件变更能被捕获）
            monitored_dirs = set()
            for file_path in self._monitored_files:
                parent_dir = str(Path(file_path).parent)
                if parent_dir not in monitored_dirs:
                    monitored_dirs.add(parent_dir)
                    # 只在目录未添加过时才添加
                    already_added = any(dir_path == parent_dir for dir_path, _ in dirs_to_watch)
                    if not already_added:
                        self._observer.schedule(
                            self._handler,
                            parent_dir,
                            recursive=False
                        )

            # 启动观察者
            self._observer.start()
            self._running = True

        except Exception:
            # 启动失败时静默失败，不影响主程序
            self.stop()

    def stop(self) -> None:
        """停止监控。"""
        if not self._running:
            return

        try:
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=2.0)
        except Exception:
            pass
        finally:
            self._observer = None
            self._handler = None
            self._running = False


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

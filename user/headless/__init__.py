"""user/headless —— 无头模式用户交互实现。

提供基于文件/管道或标准输入输出的无头接口，适合后端服务集成、
批处理任务、Docker 容器等场景。
"""

from user.headless.headless import HeadlessUser, StdioHeadlessUser, FileHeadlessUser

__all__ = ['HeadlessUser', 'StdioHeadlessUser', 'FileHeadlessUser']

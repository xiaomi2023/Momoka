"""Momoka - AI Agent 程序入口。"""

from host.momoka import Momoka
from user.cli import CLIUser


if __name__ == '__main__':
    ui = CLIUser()
    
    agent = Momoka(user=ui, call_wrapper=ui.call_wrapper)
    ui.set_agent(agent)
    
    ui.run()

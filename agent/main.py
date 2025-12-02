import sys
import os

# If this file is executed directly (python agent/main.py), ensure the project
# root is on sys.path so `import agent.*` works. When run as a module
# (python -m agent.main) this is unnecessary.
if __package__ is None or __package__ == "":
    # project root is parent dir of this file's directory
    _proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj_root not in sys.path:
        sys.path.insert(0, _proj_root)

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

# 导入自定义模块（会自动注册所有自定义动作和识别）
import agent.custom
from agent.custom.utils import TaskInterruptedException


def main():
    """Agent 主函数
    
    说明：
    - 当检测到中断信号时，会抛出 TaskInterruptedException
    - 捕获异常后优雅退出进程（exit code 0）
    - GUI 会检测到进程退出并自动重启新的 Agent 进程
    """
    try:
        print("[Agent] 正在启动...")
        Toolkit.init_option("./")

        socket_id = sys.argv[-1]
        print(f"[Agent] Socket ID: {socket_id}")

        AgentServer.start_up(socket_id)
        print("[Agent] AgentServer 已启动，等待任务...")
        
        AgentServer.join()
        
        # 正常结束
        print("[Agent] 任务完成，正在关闭...")
        AgentServer.shut_down()
        print("[Agent] Agent 正常退出")
        sys.exit(0)
        
    except TaskInterruptedException as e:
        # 中断异常：优雅退出，等待 GUI 重启
        print(f"[Agent] {e}")
        print("[Agent] 检测到中断信号，优雅退出进程...")
        print("[Agent] GUI 将自动重启 Agent")
        
        try:
            AgentServer.shut_down()
        except Exception:
            pass  # 忽略关闭时的异常
        
        # 退出码 0 表示正常退出，GUI 会重启
        sys.exit(0)
        
    except KeyboardInterrupt:
        # 用户按 Ctrl+C
        print("\n[Agent] 收到键盘中断信号，正在退出...")
        try:
            AgentServer.shut_down()
        except Exception:
            pass
        sys.exit(0)
        
    except Exception as e:
        # 其他异常：打印错误并退出
        print(f"[Agent] 发生未处理的异常: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            AgentServer.shut_down()
        except Exception:
            pass
        
        # 退出码 1 表示异常退出
        sys.exit(1)


if __name__ == "__main__":
    main()

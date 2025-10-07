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

import agent.custom.action.general as general



def main():
    Toolkit.init_option("./")

    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()

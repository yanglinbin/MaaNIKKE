import sys

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

import agent.custom.action.general as general
import agent.custom.reco.my_reco as my_reco


def main():
    Toolkit.init_option("./")

    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()

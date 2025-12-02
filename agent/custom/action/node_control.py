"""节点控制相关的自定义动作"""

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..utils import parse_custom_param


@AgentServer.custom_action("DisableNode")
class DisableNode(CustomAction):
    """将特定节点设置为禁用状态

    参数格式:
    {
        "node_name": "节点名称"
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        params = parse_custom_param(argv.custom_action_param)
        node_name = params["node_name"]
        context.override_pipeline({node_name: {"enabled": False}})
        return CustomAction.RunResult(success=True)
    

@AgentServer.custom_action("EnableNode")
class EnableNode(CustomAction):
    """将特定节点设置为启用状态

    参数格式:
    {
        "node_name": "节点名称"
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        params = parse_custom_param(argv.custom_action_param)
        node_name = params["node_name"]
        context.override_pipeline({node_name: {"enabled": True}})
        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("NodeOverride")
class NodeOverride(CustomAction):
    """批量覆盖节点配置

    参数格式:
    {
        "节点名1": {"参数名": "参数值"},
        "节点名2": {"参数名": "参数值"}
    }
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        params = parse_custom_param(argv.custom_action_param)
        if params:
            context.override_pipeline(params)
        return CustomAction.RunResult(success=True)


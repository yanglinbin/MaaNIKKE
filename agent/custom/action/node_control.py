"""节点控制相关的自定义动作"""

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..utils import (
    check_interrupt_and_raise,
    interruptible_sleep,
    TaskInterruptedException,
    parse_custom_param,
    verify_recognition_with_retry,
)


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
    
    
@AgentServer.custom_action("node_caller")
class NodeCaller(CustomAction):
    """
    节点调用器：调用指定节点并执行，完成后继续 pipeline。
    
    参数格式:
    {
        "node_name": "目标节点",                         // 必需：要调用的节点名称
        "override_node": {...}                           // 可选：覆盖节点配置
    }
    
    使用示例:
    {
        "我的任务": {
            "recognition": {"type": "DirectHit"},
            "action": {
                "type": "Custom",
                "custom_action": "node_caller",
                "custom_action_param": {
                    "node_name": "领取奖励"
                }
            },
            "next": ["继续执行其他任务"]
        }
    }
    
    说明:
    - 调用指定节点，执行完成后返回到当前 pipeline 继续执行
    - 支持覆盖节点配置，可以临时修改节点参数
    - 执行完节点后，会继续执行当前节点的 next
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        try:
            # 解析参数
            params = parse_custom_param(argv.custom_action_param)
            node_name = params.get("node_name")
            override_node = params.get("override_node")
            
            if not node_name:
                print("[NodeCaller] 错误: 未指定 node_name")
                return CustomAction.RunResult(success=False)
            
            print(f"[NodeCaller] 调用节点: {node_name}")
            
            # 如果有覆盖配置，先应用
            if override_node:
                print(f"[NodeCaller] 应用覆盖配置")
                context.override_pipeline({node_name: override_node})
            
            # 检查中断
            check_interrupt_and_raise(context, "node_caller执行")
            
            # 执行节点
            result = context.run_task(node_name)
            
            # 检查结果
            if result and hasattr(result, 'nodes') and result.nodes:
                print(f"[NodeCaller] 节点执行成功: {node_name}")
                return CustomAction.RunResult(success=True)
            else:
                print(f"[NodeCaller] 节点执行失败: {node_name}")
                return CustomAction.RunResult(success=False)
        
        except TaskInterruptedException:
            # 中断信号：返回 False 让任务自然结束
            print("[NodeCaller] 检测到中断信号，任务终止")
            return CustomAction.RunResult(success=False)
        except Exception as e:
            print(f"[NodeCaller] 执行异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return CustomAction.RunResult(success=False)


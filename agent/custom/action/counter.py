"""计数器管理相关的自定义动作"""

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..utils import parse_custom_param


class CounterManager:
    """计数器管理器（全局共享）"""
    _counters = {}
    
    @classmethod
    def get(cls, counter_name: str) -> int:
        """获取计数器值"""
        return cls._counters.get(counter_name, 0)
    
    @classmethod
    def increment(cls, counter_name: str) -> int:
        """计数器 +1，返回新值"""
        current = cls._counters.get(counter_name, 0)
        new_value = current + 1
        cls._counters[counter_name] = new_value
        return new_value
    
    @classmethod
    def set(cls, counter_name: str, value: int) -> None:
        """设置计数器值"""
        cls._counters[counter_name] = value
    
    @classmethod
    def reset(cls, counter_name: str = None) -> None:
        """重置计数器（None 表示重置所有）"""
        if counter_name is None:
            cls._counters.clear()
            print("[CounterManager] 重置所有计数器")
        else:
            if counter_name in cls._counters:
                del cls._counters[counter_name]
                print(f"[CounterManager] 重置计数器: {counter_name}")
    
    @classmethod
    def list_all(cls) -> dict:
        """列出所有计数器"""
        return cls._counters.copy()


@AgentServer.custom_action("counter_increment")
class CounterIncrement(CustomAction):
    """计数器递增：每次调用将指定计数器 +1
    
    参数格式:
    {
        "counter_name": "我的计数器"  // 必需：计数器名称
    }
    
    使用示例:
    {
        "增加计数": {
            "recognition": {"type": "DirectHit"},
            "action": {
                "type": "Custom",
                "custom_action": "counter_increment",
                "custom_action_param": {
                    "counter_name": "循环次数"
                }
            },
            "next": ["检查计数"]
        }
    }
    """
    
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        try:
            params = parse_custom_param(argv.custom_action_param)
            counter_name = params.get("counter_name")
            
            if not counter_name:
                print("[CounterIncrement] 错误: 未指定 counter_name")
                return CustomAction.RunResult(success=False)
            
            new_value = CounterManager.increment(counter_name)
            print(f"[CounterIncrement] [{counter_name}] = {new_value}")
            
            return CustomAction.RunResult(success=True)
        
        except Exception as e:
            print(f"[CounterIncrement] 执行异常: {str(e)}")
            return CustomAction.RunResult(success=False)


@AgentServer.custom_action("counter_reset")
class CounterReset(CustomAction):
    """重置计数器
    
    参数格式:
    {
        "counter_name": "我的计数器"  // 可选：计数器名称（不指定则重置所有）
    }
    
    使用示例:
    {
        "重置计数": {
            "recognition": {"type": "DirectHit"},
            "action": {
                "type": "Custom",
                "custom_action": "counter_reset",
                "custom_action_param": {
                    "counter_name": "循环次数"
                }
            }
        }
    }
    """
    
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        try:
            params = parse_custom_param(argv.custom_action_param)
            counter_name = params.get("counter_name")
            
            CounterManager.reset(counter_name)
            
            return CustomAction.RunResult(success=True)
        
        except Exception as e:
            print(f"[CounterReset] 执行异常: {str(e)}")
            return CustomAction.RunResult(success=False)


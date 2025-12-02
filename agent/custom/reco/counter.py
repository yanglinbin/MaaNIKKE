from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context

from ..action.counter import CounterManager
from ..utils import parse_custom_param


@AgentServer.custom_recognition("counter_check")
class CounterCheck(CustomRecognition):
    """计数器检测：检测计数器是否满足条件
    
    参数格式:
    {
        "counter_name": "我的计数器",    // 必需：计数器名称
        "count": 5,                      // 必需：目标计数
        "operator": "=="                 // 可选：比较运算符（==, !=, >, <, >=, <=），默认 "=="
    }
    
    使用示例:
    {
        "检查计数": {
            "recognition": {
                "type": "Custom",
                "custom_recognition": "counter_check",
                "custom_recognition_param": {
                    "counter_name": "循环次数",
                    "count": 3,
                    "operator": ">="
                }
            },
            "action": {"type": "DoNothing"},
            "next": ["达到条件后执行"]
        }
    }
    
    支持的运算符:
    - "==" : 等于（默认）
    - "!=" : 不等于
    - ">"  : 大于
    - "<"  : 小于
    - ">=" : 大于等于
    - "<=" : 小于等于
    """
    
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        try:
            # 解析参数（支持字符串和字典两种格式）
            params = parse_custom_param(argv.custom_recognition_param)
            
            counter_name = params.get("counter_name")
            target_count = params.get("count")
            operator = params.get("operator", "==")
            
            # 验证参数
            if not counter_name:
                print("[CounterCheck] 错误: 未指定 counter_name")
                return None  # 识别失败
            
            if target_count is None:
                print("[CounterCheck] 错误: 未指定 count")
                return None  # 识别失败
            
            # 获取当前计数
            current_count = CounterManager.get(counter_name)
            
            # 执行比较
            result = self._compare(current_count, operator, target_count)
            
            if result:
                print(f"[CounterCheck] [{counter_name}] {current_count} {operator} {target_count} = True")
                # 识别成功：返回一个虚拟的 box
                return CustomRecognition.AnalyzeResult(
                    box=(0, 0, 1, 1),
                    detail=f"{counter_name}={current_count}"
                )
            else:
                print(f"[CounterCheck] [{counter_name}] {current_count} {operator} {target_count} = False")
                # 识别失败：返回 None
                return None
        
        except Exception as e:
            print(f"[CounterCheck] 执行异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return None  # 异常时识别失败
    
    def _compare(self, current: int, operator: str, target: int) -> bool:
        """比较计数器值"""
        if operator == "==":
            return current == target
        elif operator == "!=":
            return current != target
        elif operator == ">":
            return current > target
        elif operator == "<":
            return current < target
        elif operator == ">=":
            return current >= target
        elif operator == "<=":
            return current <= target
        else:
            print(f"[CounterCheck] 警告: 不支持的运算符 '{operator}'，使用默认 '=='")
            return current == target


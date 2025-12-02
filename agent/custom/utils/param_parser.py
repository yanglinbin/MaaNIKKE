"""参数解析工具"""

import json
from typing import Any, Dict


def parse_custom_param(param: Any) -> Dict:
    """解析自定义动作/识别的参数
    
    MAA 框架可能以字符串或字典形式传递参数，此函数统一处理。
    
    Args:
        param: argv.custom_action_param 或 argv.custom_recognition_param
    
    Returns:
        解析后的字典
    
    Examples:
        >>> params = parse_custom_param(argv.custom_action_param)
        >>> task_name = params.get("task_name")
    """
    if isinstance(param, str):
        return json.loads(param)
    return param if param is not None else {}


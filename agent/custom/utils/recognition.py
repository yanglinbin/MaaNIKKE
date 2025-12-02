"""识别验证工具"""

import time
from typing import Optional

from maa.context import Context

from .common import check_interrupt_and_raise, interruptible_sleep, is_recognition_success
from .screencap import get_fresh_screenshot


def verify_recognition_with_retry(
    context: Context,
    node_name: str,
    timeout: float = 3.0,
    retry_interval: float = 0.3,
    log_prefix: str = ""
) -> bool:
    """验证节点识别是否成功（带重试机制）
    
    在指定超时时间内循环识别，直到成功或超时。
    
    Args:
        context: MAA 上下文
        node_name: 节点名称
        timeout: 验证超时时间（秒），默认 3.0
        retry_interval: 重试间隔（秒），默认 0.3
        log_prefix: 日志前缀，用于区分不同调用者
    
    Returns:
        True: 识别成功
        False: 识别失败（超时）
    
    Examples:
        >>> if verify_recognition_with_retry(context, "主页", timeout=5.0):
        ...     print("主页识别成功")
    """
    start_time = time.time()
    end_time = start_time + timeout
    attempts = 0
    
    prefix = f"[{log_prefix}] " if log_prefix else ""
    
    while time.time() < end_time:
        # 检查中断
        check_interrupt_and_raise(context, f"{log_prefix or '识别验证'}")
        
        attempts += 1
        
        # 刷新截图并识别
        image = get_fresh_screenshot(context)
        result = context.run_recognition(node_name, image)
        
        # 检查识别是否成功
        if is_recognition_success(result):
            elapsed = time.time() - start_time
            if attempts > 1:
                print(f"{prefix}识别成功: {node_name} (尝试 {attempts} 次, 耗时 {elapsed:.1f}s)")
            return True
        
        # 检查是否还有时间重试
        if time.time() + retry_interval >= end_time:
            break
        
        # 等待重试间隔
        interruptible_sleep(context, retry_interval)
    
    # 超时失败
    elapsed = time.time() - start_time
    print(f"{prefix}识别失败: {node_name} (尝试 {attempts} 次, 耗时 {elapsed:.1f}s)")
    return False


def run_recognition_once(
    context: Context,
    node_name: str,
    image: Optional[any] = None
) -> bool:
    """执行一次识别并返回是否成功
    
    Args:
        context: MAA 上下文
        node_name: 节点名称
        image: 可选的截图，不提供则自动截图
    
    Returns:
        True: 识别成功
        False: 识别失败
    
    Examples:
        >>> if run_recognition_once(context, "主页"):
        ...     print("主页识别成功")
    """
    if image is None:
        image = get_fresh_screenshot(context)
    
    result = context.run_recognition(node_name, image)
    return is_recognition_success(result)


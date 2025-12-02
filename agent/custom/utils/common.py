"""Common Utilities - 通用工具函数

提供常用的辅助函数，包括停止检测、可中断睡眠、识别结果判断等。
"""

import time
import sys
from maa.context import Context


class TaskInterruptedException(Exception):
    """任务中断异常
    
    当检测到停止信号时抛出此异常。
    主程序捕获此异常后应优雅退出，等待 GUI 重启。
    """
    pass


def is_stop_requested(context: Context) -> bool:
    """检查是否请求停止
    
    检查逻辑：
    1. 优先检查 tasker.stopping（正在停止中）
    2. 其次检查 not tasker.running（已经不在运行）
    
    Args:
        context: MAA上下文
        
    Returns:
        True: 请求停止或已停止
        False: 未请求停止
    """
    try:
        # 优先检查 stopping 属性（正在停止中）
        if hasattr(context.tasker, 'stopping') and context.tasker.stopping:
            return True
        
        # 其次检查 running 属性（已停止）
        if hasattr(context.tasker, 'running') and not context.tasker.running:
            return True
        
        return False
    except Exception:
        return False


def interruptible_sleep(context: Context, duration: float) -> bool:
    """可中断的睡眠
    
    在睡眠期间定期检查停止信号，如果收到停止信号则立即返回。
    
    Args:
        context: MAA上下文
        duration: 睡眠时长（秒）
        
    Returns:
        True: 正常完成睡眠
        False: 被中断
    """
    STOP_CHECK_INTERVAL = 0.1  # 每100ms检查一次停止信号
    
    end_time = time.time() + duration
    while time.time() < end_time:
        if is_stop_requested(context):
            return False
        
        remaining = end_time - time.time()
        if remaining <= 0:
            break
        
        time.sleep(min(STOP_CHECK_INTERVAL, remaining))
    
    return True


def check_interrupt_and_raise(context: Context, location: str = ""):
    """检查中断信号，如果检测到则抛出异常
    
    这是中断机制的核心函数。只在关键位置调用此函数：
    - 循环入口
    - 长时间阻塞操作后
    
    Args:
        context: MAA上下文
        location: 位置标识（用于日志）
        
    Raises:
        TaskInterruptedException: 检测到中断信号
    """
    if is_stop_requested(context):
        msg = f"检测到中断信号"
        if location:
            msg += f" - {location}"
        print(f"[Interrupt] {msg}，准备退出进程...")
        raise TaskInterruptedException(msg)


def is_recognition_success(result) -> bool:
    """检查识别是否成功
    
    判断逻辑：
    - 如果 result 为 None，识别失败
    - 如果 result 字符串表示中包含 'none'，识别失败
    - 否则，识别成功
    
    Args:
        result: 识别结果
        
    Returns:
        True: 识别成功
        False: 识别失败
    """
    if result is None:
        return False
    
    result_str = str(result).lower()
    
    # 如果包含 'none'，说明识别失败
    if 'none' in result_str:
        return False
    
    # 否则认为识别成功
    return True


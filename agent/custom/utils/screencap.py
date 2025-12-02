"""Screenshot Utilities - 截图工具函数

提供截图相关的辅助函数，包括刷新截图、获取最新截图等。
"""

from maa.context import Context


def get_fresh_screenshot(context: Context):
    """获取最新的截图
    
    主动刷新截图，确保获取的是最新的画面。
    
    Args:
        context: MAA上下文
        
    Returns:
        最新的截图对象
        
    Raises:
        Exception: 截图失败时抛出异常
    """
    # 主动刷新截图
    context.tasker.controller.post_screencap().wait()
    
    # 获取最新截图
    return context.tasker.controller.cached_image


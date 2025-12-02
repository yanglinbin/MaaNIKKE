"""Custom Utils Module - 自定义工具模块

提供通用的工具函数和类，供 custom action 和 recognition 使用。
"""

from .common import (
    TaskInterruptedException,
    is_stop_requested,
    check_interrupt_and_raise,
    interruptible_sleep,
    is_recognition_success,
)

from .screencap import (
    get_fresh_screenshot,
)

from .param_parser import (
    parse_custom_param,
)

from .recognition import (
    verify_recognition_with_retry,
    run_recognition_once,
)

__all__ = [
    "TaskInterruptedException",
    "is_stop_requested",
    "check_interrupt_and_raise",
    "interruptible_sleep",
    "is_recognition_success",
    "get_fresh_screenshot",
    "parse_custom_param",
    "verify_recognition_with_retry",
    "run_recognition_once",
]


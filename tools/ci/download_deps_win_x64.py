#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载Python依赖到deps目录的脚本
专门为Windows x86_64平台设计
"""

import os
import sys
import subprocess
import argparse
import platform
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def get_platform_tag():
    """返回Windows x86_64平台标签"""
    os_type = platform.system()
    os_arch = platform.machine()

    print(f"检测到操作系统: {os_type}, 架构: {os_arch}")

    if os_type != "Windows":
        raise ValueError("此脚本仅支持 Windows 平台")

    if os_arch != "AMD64":
        print(f"警告: 此脚本专为 x86_64 架构设计，当前架构为 {os_arch}")

    platform_tag = "win_amd64"
    print(f"使用平台标签: {platform_tag}")
    return platform_tag


def download_dependencies(deps_dir, platform_tag):
    """下载依赖到指定目录"""
    # 创建deps目录
    deps_path = Path(deps_dir)
    deps_path.mkdir(parents=True, exist_ok=True)

    print(f"开始下载平台 {platform_tag} 的依赖到 {deps_dir}")

    # 从requirements.txt读取依赖
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("错误: requirements.txt 文件不存在")
        return False

    # 首先尝试下载平台特定的wheel文件
    try:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "-r",
            str(requirements_file),
            "-d",
            str(deps_path),
            "--platform",
            platform_tag,
            "--only-binary=:all:",
        ]

        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)

        if result.stderr:
            print("警告信息:")
            print(result.stderr)

        # 列出下载的文件
        whl_files = list(deps_path.glob("*.whl"))
        print(f"\n下载的wheel文件 ({len(whl_files)} 个):")
        for whl_file in whl_files:
            print(f"  {whl_file.name}")

        print(f"依赖下载完成到: {deps_path}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"平台特定下载失败: {e}")
        if e.stderr and (
            "Could not find a version" in e.stderr
            or "No matching distribution" in e.stderr
        ):
            print("某些包可能不支持当前平台，尝试通用下载策略...")

            # 回退到通用下载策略（不指定平台）
            try:
                cmd_fallback = [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    "-r",
                    str(requirements_file),
                    "-d",
                    str(deps_path),
                    "--only-binary=:all:",
                ]

                print(f"执行回退命令: {' '.join(cmd_fallback)}")
                result = subprocess.run(
                    cmd_fallback, check=True, capture_output=True, text=True
                )
                print(result.stdout)

                if result.stderr:
                    print("警告信息:")
                    print(result.stderr)

                # 列出下载的文件
                whl_files = list(deps_path.glob("*.whl"))
                print(f"\n下载的wheel文件 ({len(whl_files)} 个):")
                for whl_file in whl_files:
                    print(f"  {whl_file.name}")

                print(f"通用策略下载完成到: {deps_path}")
                return True

            except subprocess.CalledProcessError as e2:
                print(f"通用策略也失败: {e2}")
                if e2.stdout:
                    print("stdout:", e2.stdout)
                if e2.stderr:
                    print("stderr:", e2.stderr)
                return False
        else:
            if e.stdout:
                print("stdout:", e.stdout)
            if e.stderr:
                print("stderr:", e.stderr)
            return False


def main():
    parser = argparse.ArgumentParser(description="下载Python依赖到deps目录 (Windows x86_64专用)")
    parser.add_argument("--deps-dir", default="deps", help="依赖下载目录 (默认: deps)")

    args = parser.parse_args()

    try:
        # 获取平台标签
        platform_tag = get_platform_tag()

        # 下载依赖
        success = download_dependencies(args.deps_dir, platform_tag)

        if success:
            print("✅ 依赖下载成功")
            sys.exit(0)
        else:
            print("❌ 依赖下载失败")
            sys.exit(1)

    except Exception as e:
        print(f"❌ 脚本执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
from pathlib import Path

import shutil
import sys
import json
import subprocess

import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from configure import configure_ocr_model


working_dir = Path(__file__).parent.parent.parent
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"


def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print("Please download the MaaFramework to \"deps\" first.")
        print("请先下载 MaaFramework 到 \"deps\"。")
        sys.exit(1)

    shutil.copytree(
        working_dir / "deps" / "bin",
        install_path,
        ignore=shutil.ignore_patterns(
            "*MaaDbgControlUnit*",
            "*MaaThriftControlUnit*",
            "*MaaRpc*",
            "*MaaHttp*",
        ),
        dirs_exist_ok=True,
    )
    shutil.copytree(
        working_dir / "deps" / "share" / "MaaAgentBinary",
        install_path / "MaaAgentBinary",
        dirs_exist_ok=True,
    )


def install_resource():

    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = json.load(f)

    interface["version"] = version

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(
        working_dir / "README.md",
        install_path,
    )
    shutil.copy2(
        working_dir / "LICENSE",
        install_path,
    )

def install_agent():
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
    )

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = json.load(f)

    if sys.platform.startswith("win"):
        interface["agent"]["child_exec"] = r"./python/python.exe"
    elif sys.platform.startswith("darwin"):
        interface["agent"]["child_exec"] = r"./python/bin/python3"
    elif sys.platform.startswith("linux"):
        interface["agent"]["child_exec"] = r"python3"

    interface["agent"]["child_args"] = ["-u", r"./agent/main.py"]

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)


def install_requirements():
    """安装下载的whl文件"""
    python_executable = install_path / "python" / "python.exe"
    
    if not python_executable.exists():
        print(f"Python executable not found at {python_executable}")
        return False
    
    # 检查两个可能的deps目录
    deps_dirs = [
        install_path / "deps",  # CI流程中下载依赖的位置
        working_dir / "deps"    # 项目根目录的deps
    ]
    
    all_whl_files = []
    for deps_dir in deps_dirs:
        if deps_dir.exists():
            whl_files = list(deps_dir.glob("*.whl"))
            print(f"Found {len(whl_files)} wheel files in {deps_dir}")
            all_whl_files.extend(whl_files)
    
    if not all_whl_files:
        print("No wheel files found in any deps directory")
        return False
    
    print(f"Installing {len(all_whl_files)} wheel files...")
    
    # 安装每个whl文件
    for whl_file in all_whl_files:
        print(f"Installing {whl_file.name}...")
        try:
            cmd = [
                str(python_executable),
                "-m", "pip", "install",
                str(whl_file),
                "--no-deps",  # 不安装依赖，因为我们已经下载了所有依赖
                "--force-reinstall",  # 强制重新安装
                "--no-index",  # 不连接PyPI
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Successfully installed {whl_file.name}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {whl_file.name}: {e}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
            # 不立即返回False，继续安装其他whl文件
            continue
            
    print("Wheel files installation process completed")
    return True


if __name__ == "__main__":
    # 启用install_deps函数
    install_deps()
    install_resource()
    install_chores()
    install_agent()
    
    # 安装whl文件
    install_requirements()

    print(f"Install to {install_path} successfully.")
# Copilot Instructions for MaaPracticeBoilerplate

## 项目架构概览
- 本项目基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework)，用于自动化黑盒测试，核心为图像识别与自动化控制。
- 主要目录结构：
  - `agent/`：自定义动作、推荐、工具等 Python 代码，扩展点集中于 `custom/` 子目录。
  - `assets/`：资源文件，包括接口定义、配置、OCR 资源、基础图片/模型等。
  - `deps/`：依赖的二进制库和 DLL，需从 MaaFramework Release 包获取。
  - `sample/`：示例配置、代码和资源，便于参考和二次开发。
  - `docs/`：中英文文档，详细介绍集成、协议、构建等。

## 开发与构建流程
1. **依赖准备**：
   - 运行 `git submodule update --init --recursive` 获取 MaaCommonAssets。
   - 下载 MaaFramework Release 包，解压到 `deps/`。
2. **资源配置**：
   - 执行 `python configure.py` 自动生成/校验资源配置。
3. **开发扩展**：
   - 推荐在 `agent/custom/` 下添加自定义 action/reco，按需扩展 `agent/utils/`。
   - 资源文件（如图片、模型）放入 `assets/resource/base/`。
4. **调试与测试**：
   - 主要入口为 `agent/main.py`，可直接运行或集成到上层系统。
   - 日志与调试信息可在 `debug/maa.log` 查看。
5. **发布**：
   - 按照 README 步骤打 tag，CI 自动发版。

## 约定与模式
- **命名规范**：推荐自定义模块以 `Maa`、`MXA`、`MAX` 等前缀命名。
- **配置管理**：所有资源配置集中于 `assets/config/`，接口定义在 `assets/interface.json`。
- **二进制兼容**：`deps/` 下 DLL/EXE 需与 MaaFramework 版本严格对应。
- **文档优先**：遇到问题优先查阅 `docs/zh_cn/`，常见问题见 README FAQ。

## 关键文件/目录
- `agent/main.py`：主入口，集成与调试核心。
- `agent/custom/`：自定义扩展推荐放此目录。
- `assets/config/maa_pi_config.json`：主配置文件。
- `configure.py`：资源校验与初始化脚本。
- `deps/`：所有依赖二进制，缺失会导致运行异常。

## 典型开发示例
- 新增自定义动作：在 `agent/custom/action/` 下新建 Python 文件并注册。
- 新增识别模块：在 `agent/custom/reco/` 下实现并注册。
- 配置新资源：将图片/模型放入 `assets/resource/base/` 并在配置中声明。

## 注意事项
- OCR 相关资源较大，需完整下载 `assets/MaaCommonAssets/OCR/`。
- 依赖缺失或版本不符会导致 DLL 加载失败，详见 FAQ。
- 日志文件为排查问题的重要依据。

## 开发环境：终端自动激活虚拟环境（重要）

每次打开项目终端时应自动激活项目虚拟环境（`.venv`），以确保 `pre-commit`、`python`、`pip` 和扩展在相同的环境中运行。请遵循以下可操作规则：

- 推荐设置（VS Code workspace settings）

   在 `.vscode/settings.json` 中设置：

   ```jsonc
   {
      "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "python.terminal.activateEnvironment": true,
      "terminal.integrated.defaultProfile.windows": "PowerShell"
   }
   ```

- 说明与替代方案
   - 不要在 profile 的 `args` 里直接写 `Activate.ps1`（`${workspaceFolder}` 在 args 中可能不会被正确展开或在不同系统编码下失败）。
   - 如果你使用 Git Bash / Cmd，请让 Python 扩展自动激活（`python.terminal.activateEnvironment`），或为这些 shell 添加 profile 并使用 shell 本身的 `source`/`activate` 命令。
   - 若首次终端未激活：确认左下角已选择工作区的 `.venv` 解释器（Ctrl+Shift+P → Python: Select Interpreter），然后关闭所有终端并 New Terminal。

- 常见问题
   - 错误：`pre-commit not found` 或 `Received protocol 'e:'` — 说明当前终端不是项目 venv，或 pre-commit hook 指向错误的 python（见 `.git/hooks/pre-commit`）。解决办法：在 VS Code 里新建终端以触发自动激活，或手动激活：

      ```powershell
      & ${workspaceFolder}\\.venv\\Scripts\\Activate.ps1
      ```

   - 如果 PowerShell 执行策略阻止执行 Activate.ps1，可临时使用 `-ExecutionPolicy Bypass`，或改变 CurrentUser 策略。

把这条规则作为本项目的开发环境约定写入，以便 AI agent 在执行任何仓库操作前确保激活虚拟环境。

如需详细开发规范、集成协议或接口说明，请查阅 `docs/zh_cn/` 及 MaaFramework 官方文档。

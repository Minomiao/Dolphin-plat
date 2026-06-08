# Dolphin Features

## Core

- [x] CLI chat interface with streaming output
  - CLI 聊天界面，支持流式输出
- [x] Multi-model support (deepseek-v4-flash, deepseek-v4-pro, etc.)
  - 多模型支持（deepseek-v4-flash、deepseek-v4-pro 等）
- [x] Model deprecation warning system
  - 模型废弃警告系统
- [x] Config file separation: `config.json` (non-sensitive) + `.env` (API key, work dir)
  - 配置文件分离：`config.json`（非敏感）+ `.env`（API 密钥、工作目录）
- [x] Auto migration of legacy config (api_key → .env)
  - 旧版配置自动迁移（api_key → .env）
- [x] Splash screen with pixel-art DOLPHIN and loading progress bar
  - 启动画面包含像素艺术海豚和加载进度条

## Chat

- [x] Streaming response with real-time typing effect
  - 流式响应，实时打字机效果
- [x] Thinking process display (dim text, toggled by code fence)
  - 思考过程显示（暗色文字，代码围栏切换）
- [x] Multi-turn conversation history
  - 多轮对话历史
- [x] System prompt with workspace context
  - 包含工作区上下文的系统提示词
- [x] Plain text output mode (no markdown, no emoji)
  - 纯文本输出模式（无 markdown、无表情符号）
- [x] Tool call iteration loop (initial 30 rounds, extendable +20 on user confirm, hard limit 100)
  - 工具调用迭代循环（初始 30 轮，用户确认后每次续期 +20，硬上限 100）
- [x] Configurable max_tokens, temperature
  - 可配置的 max_tokens、temperature
- [x] Context manager with token budget monitoring (70%/85%/95% thresholds)
  - 上下文管理器，带 token 预算监控（70%/85%/95% 三级阈值）

## Tool System

- [x] Unified tool execution pipeline: skill / plugin / MCP routing
  - 统一工具执行管道：技能 / 插件 / MCP 路由
- [x] `format_tool_result()` recursive JSON formatter for terminal display
  - `format_tool_result()` 递归 JSON 格式化器，用于终端显示
- [x] Tool confirmation flow (`_process_tool_confirmation`)
  - 工具确认流程（`_process_tool_confirmation`）
  - USER_INPUT: block and wait for user input
    - USER_INPUT：阻塞并等待用户输入
  - CONFIRMATION: y/n prompt
    - CONFIRMATION：y/n 提示
  - requires_confirmation: confirm → auto re-call with `confirmed=True`
    - requires_confirmation：确认 → 使用 `confirmed=True` 自动重新调用
- [x] Tool call / result display reorder fix (calls before results)
  - 工具调用 / 结果显示顺序修复（调用在结果之前）

## User Output (`user_output`)

- [x] Skill tools return `user_output` dict `{label, content}` for compact display
  - 技能工具返回 `user_output` 字典 `{label, content}` 用于紧凑显示
- [x] Tools with `user_output` skip verbose tool_calls/tool_result blocks
  - 带有 `user_output` 的工具跳过冗长的 tool_calls/tool_result 区块
- [x] Inline color support (colorama Fore/RED, Fore/GREEN, Fore/LIGHTBLACK_EX)
  - 内联颜色支持（colorama Fore/RED、Fore/GREEN、Fore/LIGHTBLACK_EX）
- [x] Legacy string `user_output` backward compatible
  - 旧版字符串 `user_output` 向后兼容

## User Output — Per Tool Display

### file_reader
- [x] `read_file` → `[Read] --filename`
- [x] `list_directory` → `[Read] --dir\` (root → `all`)
- [x] `search_files` → `[Search] --pattern`
- [x] `get_work_directory` → `[Read] dirname`

### file_manager
- [x] `create_file` → `[File Change] filename +N(green) -0(red)`
- [x] `modify_file` → `[File Change] filename +N(green) -N(red)`
- [x] `delete_file` → `[File Change] --filename Delet(red)` (with confirmation)
  - `delete_file` → `[File Change] --filename Delet(红色)`（需确认）
- [x] `set_work_directory` → `[Work Place] --path`

### random_generator
- [x] `random_int` → `[Random] --int (min-max)(gray)`
  - `random_int` → `[Random] --int (最小值-最大值)(灰色)`
- [x] `random_float` → `[Random] --float (min-max)(gray)`
  - `random_float` → `[Random] --float (最小值-最大值)(灰色)`
- [x] `random_choice` → `[Random] --choices (a, b, c, ...)(gray)`
  - `random_choice` → `[Random] --choices (选项列表)(灰色)`
- [x] `random_password` → `[Random] --password (length)(gray)`
  - `random_password` → `[Random] --password (长度)(灰色)`

### calculator
- [x] `calculate(expr)` → `[Calculator] expr(gray) result`
  - `calculate(表达式)` → `[Calculator] 表达式(灰色) 结果`
- [x] `get_current_time` → `[Calculator] --time time(gray)`
  - `get_current_time` → `[Calculator] --time 时间(灰色)`

## Skills

### file_reader
- [x] `get_work_directory` — returns current work directory
  - 返回当前工作目录
- [x] `search_files` — search by name or content (max 500 results, skip >10MB files)
  - 按名称或内容搜索（最多 500 条结果，跳过 >10MB 的文件）
- [x] `list_directory` — tree view (max 1000 files, depth 10)
  - 树状视图（最多 1000 个文件，深度 10）
- [x] `read_file` — paginated read (max 1000 lines, max 10MB)
  - 分页读取（每次最多 1000 行，最大 10MB）
- [x] Relative path validation with `_is_path_allowed`
  - 使用 `_is_path_allowed` 验证相对路径

### file_manager
- [x] `set_work_directory` — change dir (subdirs only, `..` supported, out-of-bounds → reset)
  - 更改目录（仅子目录，支持 `..`，越界 → 重置）
- [x] `create_file` — create with content (max 10MB, 1000 lines)
  - 创建文件并写入内容（最大 10MB，1000 行）
- [x] `modify_file` — modify by string replace (old_str → new_str, 3-level matching)
  - 按字符串查找替换修改（old_str → new_str，三级匹配）
- [x] `delete_file` — delete with system confirmation protection
  - 删除文件，带系统确认保护
- [x] Auto-strip line numbers from AI pasted content
  - 自动去除 AI 粘贴内容中的行号
- [x] Dead code cleanup: removed `get_work_directory`, `confirm_delete_file`, `set_confirmation_required`
  - 死代码清理：移除 `get_work_directory`、`confirm_delete_file`、`set_confirmation_required`

### powershell_executor
- [x] `run_script(script, timeout, wait_time)` — async PowerShell execution via `asyncio.create_subprocess_exec()`
  - 通过 `asyncio.create_subprocess_exec()` 异步执行 PowerShell
- [x] `check_script(command_id, wait_time)` — poll background command status and output
  - 轮询后台命令状态和输出
- [x] `kill_command(command_id)` — force terminate background command
  - 强制终止后台命令
- [x] Async I/O: stdout/stderr streamed to buffer by background asyncio tasks
  - 异步 I/O：后台 asyncio 任务将 stdout/stderr 流式传输到缓冲区
- [x] `wait_time` mechanism: command completes → instant return; timeout → return current output + `command_id`
  - `wait_time` 机制：命令完成 → 立即返回；超时 → 返回当前输出 + `command_id`
- [x] Timeout does NOT kill the process — continues in background, pollable via `check_script`
  - 超时不杀死进程 — 在后台继续运行，可通过 `check_script` 轮询
- [x] `command_id` format: `dps0001`, `dps0002`, ... (auto-increment, zero-padded)
  - `command_id` 格式：`dps0001`、`dps0002`……（自增，零填充）
- [x] Process lifecycle managed by `modules/powershell_manager.py` (separated from skill.py)
  - 进程生命周期由 `modules/powershell_manager.py` 管理（与 skill.py 分离）
- [x] Auto-cleanup on exit: `atexit` + `signal` (SIGINT/SIGTERM) kills all running subprocesses
  - 退出时自动清理：`atexit` + `signal`（SIGINT/SIGTERM）终止所有正在运行的子进程
- [x] Transport leak prevention: `_DummySock` replaces closed pipe sockets to suppress asyncio warnings
  - 传输泄漏防护：`_DummySock` 替换已关闭的管道套接字以抑制 asyncio 警告
- [x] UTF-8 output encoding via `[Console]::OutputEncoding`
  - 通过 `[Console]::OutputEncoding` 设置 UTF-8 输出编码
- [x] Output capped at 50000 chars / 500 lines
  - 输出上限为 50000 字符 / 500 行
- [x] Confirmation required before execution
  - 执行前需要确认

### random_generator
- [x] `random_int(min, max)` → random integer
  - 随机整数
- [x] `random_float(min, max)` → random float
  - 随机浮点数
- [x] `random_choice(choices)` → pick one from list
  - 从列表中随机选取一项
- [x] `random_password(length, ...)` → configurable charset password
  - 可配置字符集的随机密码

### calculator (sympy)
- [x] `calculate(expression)` — evaluate math expression via sympy.sympify
  - 通过 sympy.sympify 求值数学表达式
- [x] Support: + - * / **, sqrt, sin/cos/tan, log, factorial, pi, e
  - 支持：+ - * / **、sqrt、sin/cos/tan、log、factorial、pi、e
- [x] `get_current_time` — return current datetime string
  - 返回当前日期时间字符串
- [x] sympy Float → Python float/int conversion for JSON serialization
  - sympy Float → Python float/int 转换以支持 JSON 序列化
- [x] Replaced legacy add/subtract/multiply/divide functions
  - 替换旧版 add/subtract/multiply/divide 函数

### web_search
- [x] `search(query, num_results)` — DuckDuckGo API search
  - DuckDuckGo API 搜索

## File Operations

- [x] Centralized via `modules/file_operation.py` (create, read, modify, delete)
  - 通过 `modules/file_operation.py` 集中管理（创建、读取、修改、删除）
- [x] Path safety: all operations confined to work directory
  - 路径安全：所有操作限制在工作目录内
- [x] Auto-create parent directories on file creation
  - 创建文件时自动创建父目录
- [x] Confirm dead code removed from file_manager skill
  - 确认死代码已从 file_manager 技能中移除

## Backup System

- [x] Auto-backup before file modification (`date/backup/`)
  - 文件修改前自动备份（`date/backup/`）
- [x] Per-dialog, per-file deduplication
  - 每个对话、每个文件去重
- [x] Pending changes tracking (`backup_info.json`)
  - 待处理更改追踪（`backup_info.json`）
- [x] Quit prompt: apply / revert / skip pending changes
  - 退出提示：应用 / 还原 / 跳过待处理更改

## Conversation Management

- [x] Save / load / list conversations (`date/conversations/`)
  - 保存 / 加载 / 列出对话（`date/conversations/`）
- [x] Dialog ID generation (UUID)
  - 对话 ID 生成（UUID）
- [x] `/clear` resets history and work directory
  - `/clear` 重置历史记录和工作目录
- [x] `/new` creates new dialog
  - `/new` 创建新对话
- [x] `/load [name]` loads saved dialog
  - `/load [名称]` 加载已保存的对话
- [x] `/saveas [name]` saves current dialog
  - `/saveas [名称]` 保存当前对话

## Command System

- [x] Configurable command prefix (default `/`)
  - 可配置的命令前缀（默认 `/`）
- [x] All commands: `help`, `set`, `model`, `open`, `clear`, `new`, `load`, `saveas`, `list`, `tools`, `skills`, `toggle`, `showthinking`, `quit`
  - 所有命令：`help`、`set`、`model`、`open`、`clear`、`new`、`load`、`saveas`、`list`、`tools`、`skills`、`toggle`、`showthinking`、`quit`
- [x] Fuzzy keyword matching for unknown command suggestions
  - 未知命令的模糊关键字匹配建议
- [x] Auto-validate and repair `date/commands.json` on startup
  - 启动时自动验证并修复 `date/commands.json`
- [x] `/model` — switch model and configure API key
  - `/model` — 切换模型并配置 API 密钥
- [x] `/open [path]` — change work directory
  - `/open [路径]` — 更改工作目录

## Plugin System

- [x] Plugin loader from ZIP files in `plugins/` directory
  - 从 `plugins/` 目录中的 ZIP 文件加载插件
- [x] `manifest.json` support
  - 支持 `manifest.json`
- [x] Same `skill_info` + callable pattern as skills
  - 与技能相同的 `skill_info` + 可调用模式

## MCP Integration

- [x] MCP protocol manager (`modules/mcp_manager.py`)
  - MCP 协议管理器（`modules/mcp_manager.py`）
- [x] Tool prefix: `<server>.<tool>`
  - 工具前缀：`<服务器>.<工具>`

## Config

- [x] `date/config.json` — non-sensitive (model, max_tokens, skills, plugins, prefix)
  - `date/config.json` — 非敏感数据（模型、max_tokens、技能、插件、前缀）
- [x] `date/.env` — sensitive (API key, work directory)
  - `date/.env` — 敏感数据（API 密钥、工作目录）
- [x] `api_key` and `work_directory` auto-migrated from legacy config.json
  - `api_key` 和 `work_directory` 从旧版 config.json 自动迁移
- [x] `/set` interactive settings mode
  - `/set` 交互式设置模式
- [x] `/toggle` enable/disable tools
  - `/toggle` 启用/禁用工具
- [x] `/skills` manage per-skill enable/disable
  - `/skills` 管理每个技能的启用/禁用状态

## Logging

- [x] Module-level logging with logger names (`Dolphin.chat`, `Dolphin.skill_manager`, etc.)
  - 模块级日志，使用 logger 名称（`Dolphin.chat`、`Dolphin.skill_manager` 等）
- [x] Log file output with rotation
  - 日志文件输出，带轮转功能

## Error Handling

- [x] SympifyError / ImportError for sympy (graceful fallback)
  - sympy 的 SympifyError / ImportError（优雅降级）
- [x] JSON decode error handling in tool argument parsing
  - 工具参数解析中的 JSON 解码错误处理
- [x] Tool execution error wrapping (never crash on bad tool)
  - 工具执行错误包装（错误工具不会导致崩溃）
- [x] Max iteration guard (30 rounds, extendable to 100)
  - 最大迭代保护（30 轮，可续期至 100）
- [x] API error handling (invalid key, rate limit, server error — graceful degradation)
  - API 错误处理（无效 key、限流、服务器错误 — 优雅降级）
- [x] Unsent message rollback on API error (prevent chat history loss)
  - API 错误时回滚未发送消息（防止对话历史丢失）
- [x] PowerShell timeout and output truncation
  - PowerShell 超时和输出截断
- [x] PowerShell async subprocess transport cleanup (_DummySock pattern)
  - PowerShell 异步子进程传输清理（_DummySock 模式）

# Dolphin

Dolphin 是一个基于大语言模型的智能助手，通过技能（Skills）和插件（Plugins）系统扩展 AI 的能力，支持工具调用、对话管理、文件操作和用户交互。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

直接运行程序即可进入交互式配置，敏感数据自动保存在 `date/.env`：

```bash
# date/.env（自动管理，无需手动编辑）
QUICKAI_API_KEY=your_api_key_here
QUICKAI_WORK_DIRECTORY=workplace
```

### 3. 运行

```bash
python main.py
```

首次运行会自动创建 `workplace/` 工作目录、`date/config.json` 和 `date/.env` 文件。如果存在旧版 `date/config.json`（含 `api_key`），程序会自动将其中的敏感数据迁移到 `date/.env` 并清除。API 密钥和模型通过 `/model` 配置，工作目录通过 `/open` 配置，仅保存在 `date/.env` 中。命令前缀存储在 `date/config.json` 的 `command_prefix` 字段中，默认 `/`。

---

## 支持的模型

| 模型 | 状态 |
|------|------|
| deepseek-v4-flash | ✅ 默认模型（快速） |
| deepseek-v4-pro | ✅ 高性能模型 |
| deepseek-chat | ⚠️ 2026-07-24 废弃 |
| deepseek-reasoner | ⚠️ 2026-07-24 废弃 |
| deepseek-coder | ⚠️ 2026-07-24 废弃 |

已配置的模型若即将废弃，启动时会显示警告及剩余天数。可通过 `/model` 切换模型。

---

## 命令列表

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/set` | 进入设置模式（Token 数、命令前缀等） |
| `/model` | 切换模型和配置 API 密钥 |
| `/open [path]` | 打开/切换工作目录，不传路径时交互式输入 |
| `/clear` | 清空对话历史并重置工作目录 |
| `/new` | 创建新对话 |
| `/load [name]` | 加载已保存的对话 |
| `/saveas [name]` | 保存当前对话 |
| `/list` | 列出所有已保存的对话 |
| `/tools` | 查看可用工具列表 |
| `/skills` | 查看可用技能列表 |
| `/toggle` | 切换工具启用/禁用 |
| `/skill` | 管理各项技能的启用/禁用状态 |
| `/quit` | 退出程序 |

输入以上命令之外的任何内容，将直接发送给 AI（以命令前缀开头的输入除外，见下）。

### 命令前缀

所有命令共用一个前缀，默认为 `/`。可通过 `/set` 统一修改（例如改为 `.` 后，`/help` 变为 `.help`）。

```
date/config.json → command_prefix: "/"  (默认)
                         │
                         ▼
    所有命令自动拼接前缀: prefix + keyword
    /help → "/" + "help" = "/help"
    .help → "." + "help" = ".help"
```

修改前缀后，命令关键词（`help`、`set`、`model` 等）不可单独修改。关键词定义在 `_get_default_commands()` 中硬编码，每次启动自动校验 `date/commands.json`，发现关键词异常自动修复：

```
启动 → _validate_commands()
  ├── 内置命令关键词被篡改？ → 自动重置为默认值
  ├── 内置命令缺失？         → 自动补全
  └── 额外自定义命令？       → 原样保留
```

`date/commands.json` 仅负责 `/help` 显示，只存纯关键词（不带前缀），前缀在读取时由 `config.json` 中的 `command_prefix` 拼接。

---

## 工作目录

Dolphin 有两层工作目录：

| 层级 | 来源 | 说明 |
|------|------|------|
| 用户配置目录 | `config.json` → `work_directory` | 持久化，用户通过 `/open` 修改 |
| AI 临时目录 | 内存变量 | AI 可切换至子目录，对话保持，`/clear` `/new` `/load` 时自动重置 |

- AI 可通过 `set_work_directory` 切换到用户配置目录的**任意子目录**
- 使用相对路径 `..` 可返回上级目录，越界时自动回退到根目录
- 同一轮对话中目录保持，不会被每轮对话重置

---

## 完整执行流程

以下是用户输入一句话到 AI 完成回复的完整调用链：

### 1. 入口：main.py 命令路由

```
用户输入 ──> main.py async main()
              │
              ├── 以 prefix 开头?
              │     ├── 匹配已知命令? → 执行对应处理
              │     └── 未知命令?     → 红色报错 + continue（不发送给 AI）
              │
              └── 不以 prefix 开头?
                    └── chat_instance.chat_stream(user_input)
```

### 2. 流式对话：chat.py chat_stream()

```
chat_stream()
  │
  ├── 准备阶段
  │     ├── 构建系统提示 (含工作目录 + 目录结构)
  │     └── 组装 kwargs = {model, messages, tools, stream=True}
  │
  ├── 第1轮: 流式解析 _process_stream(stream)
  │     │
  │     │  for chunk in stream:
  │     │    ├── delta.reasoning_content  ──> callback('thinking_chunk')  实时逐字输出(暗色)
  │     │    ├── delta.content            ──> callback('response_chunk')  实时逐字输出(打字机)
  │     │    │     └── 首次到达时若思考未结束 → 先 callback('thinking_end') 分隔
  │     │    └── delta.tool_calls         ──> 累积到 tool_calls_buffer
  │     │
  │     └── 返回 (full_response, full_reasoning, tool_calls_buffer, has_tool_calls)
  │
  ├── 无 tool_calls? → add_message → 返回 ✓
  │
  ├── 有 tool_calls?
  │     │
  │     ├── callback('tool_calls')  显示工具调用列表(蓝色，有 user_output 的工具跳过)
  │     │
  │     ├── 第2轮: 逐个执行工具
  │     │     for tc in tool_calls:
  │     │       │
  │     │       ├── _execute_tool_sync()
  │     │       │     ├── 工具路由: skill_xxx / plugin_xxx / mcp_xxx
  │     │       │     ├── 检测 user_output → callback('user_output') 简约显示
  │     │       │     ├── 检测 set_work_directory 成功 → 更新 AI 临时工作目录
  │     │       │     └── 返回 result (JSON string)
  │     │       │
  │     │       ├── _process_tool_confirmation(result, tool_name, arguments)
  │     │       │     │                                      ← 抽取的公共方法
  │     │       │     ├── 非申请? → 直接返回 (result, skip=False)
  │     │       │     ├── USER_INPUT      → callback → 阻塞输入 → (result, False)
  │     │       │     ├── CONFIRMATION     → callback → 阻塞确认 → (result, False)
  │     │       │     └── requires_confirmation
  │     │       │           ├── 取消? → (error, skip=True) → 跳过该工具
  │     │       │           └── 确认?
  │     │       │                 ├── run_powershell_script → _execute_powershell_script() → powershell_manager
  │     │       │                 └── 其他 → _execute_tool_sync(confirmed=True)
  │     │       │
  │     │       ├── skip? → continue (跳过)
  │     │       └── 无 user_output → callback('tool_result')  显示执行结果(绿色)
  │     │
  │     └── messages.extend(tool_responses)
  │
  └── 第3轮: 工具调用迭代 (max 10 次)
        │
        │  while iteration < 10:
        │    ├── 重新调用 API (messages 含 tool_results)
        │    ├── _process_stream(stream)  ← 复用同一方法
        │    ├── 有 tool_calls? → 继续迭代
        │    └── 无 tool_calls? → break
        │
        └── 达到 max_iterations → callback('max_iterations_reached')
```

### 3. 回调系统：chat_callback()

所有输出通过 `chat_callback(event_type, data)` 分发到终端：

| 事件 | 触发时机 | 显示效果 |
|------|----------|----------|
| `thinking_start` | 首个 reasoning chunk | `思考过程:` |
| `thinking_chunk` | 每个 reasoning chunk | 暗色逐字 |
| `thinking_end` | 思考结束或回复开始 | `--- 思考过程结束 ---` |
| `response_chunk` | 每个 content chunk | **正常逐字**（打字机效果） |
| `response_end` | 回复结束 | 换行 |
| `tool_calls` | 检测到工具调用 | 蓝色列表 |
| `tool_result` | 工具执行完毕 | 绿色格式化 |
| `user_output` | Skill 返回面向用户输出 | 青色标签 + 内容（带内联颜色） |
| `user_input_required` | 申请需用户输入 | 提示 + 阻塞输入 |
| `confirmation_required` | 申请需确认 | 提示 + y/n |

### 4. 确认操作流程

确认处理已抽取为公共方法，三处工具执行点共享同一逻辑：

```
_execute_tool_sync()  →  result (JSON)

        │
        ▼
_process_tool_confirmation(result, tool_name, arguments)
        │
        ├── result 不是申请? → 直接返回 (result, skip=False)
        │
        ├── type == USER_INPUT
        │     └── callback('user_input_required') → 阻塞等用户输入
        │         → return ({"success": true, "input": "..."}, False)
        │
        ├── type == CONFIRMATION
        │     └── callback('confirmation_required') → 阻塞等 y/n
        │         → return ({"success": true, "confirmed": true}, False)
        │
        └── requires_confirmation == true
              │
              ├── callback('confirmation_required') → 阻塞等 y/n
              │
              ├── 用户取消?
              │     ├── callback('operation_canceled')
              │     └── return ({"error": "用户取消操作"}, skip=True)
              │         → 上层 tool_responses 添加错误 + continue
              │
              └── 用户确认?
                    ├── callback('operation_confirmed')
                    │
                    ├── action == run_powershell_script?
                    │     └── _execute_powershell_script(script, timeout, wait_time)
                    │           ├── powershell_manager.execute_script()
                    │           │     ├── asyncio.create_subprocess_exec('powershell', ...)
                    │           │     ├── 后台任务 _read_stream() 实时读取 stdout/stderr
                    │           │     ├── asyncio.wait_for(process.wait(), timeout=wait_time)
                    │           │     │     ├── wait_time 内完成 → 返回完整输出 + "completed":true
                    │           │     │     └── wait_time 超时   → 返回当前输出 + command_id
                    │           │     ├── 超时后命令继续在后台运行（不杀死）
                    │           │     └── 进程受 atexit/signal 清理保护
                    │           └── return (result, False)
                    │
                    └── 其他确认操作
                          └── _execute_tool_sync(confirmed=True) 二次调用
                              → return (result, False)

调用方 (3 处统一):
        result, skip = await self._process_tool_confirmation(result, tool_name, arguments)
        if skip:
            tool_responses.append({...error...})
            continue
```

### 5. 工作目录流转

```
config.json: work_directory = "workplace"
      │
      ├── QuickAIChat.__init__()
      │     ├── default_work_directory = config.json 的值 (持久)
      │     ├── current_work_directory = default      (内存)
      │     └── request_manager.reset_ai_work_directory() → None
      │
      ├── chat_stream() 不重置目录 (对话中保持)
      │
      ├── AI 调 set_work_directory("subdir")
      │     │
      │     ├── file_manager: 以 config.json 目录为基准校验 (非AI当前目录)
      │     ├── 返回 {work_directory: "workplace/subdir", ...}
      │     │
      │     └── _execute_tool 拦截成功结果:
      │           ├── current_work_directory = "workplace/subdir"
      │           └── request_manager.set_ai_work_directory("workplace/subdir")
      │
      ├── AI 再调 set_work_directory("..")
      │     │
      │     ├── current_path = AI当前目录 / ".." → 解析到 workplace/test ✓
      │     ├── 校验在 config.json 目录下? → 通过 ✓
      │     └── 越界? → 自动回退到 config.json 目录 (不报错)
      │
      └── /clear /new /load 时 → reset_work_directory()
            ├── current_work_directory = config.json 的值
            └── request_manager.reset_ai_work_directory() → None
```

### 6. 文件备份流程

```
AI 修改文件
  │
  ├── backup_file()  → date/backup/<safe_name>/<timestamp>.bak
  │     └── 同一对话同一文件只备份一次 (去重)
  │
  ├── record_change() → date/backup/<safe_name>/backup_info.json
  │     └── 多次修改更新同一条记录 (复用)
  │
  ├── end_dialog_backup() → 清空内存 dialog_backups
  │
  └── /quit 退出
        │
        ├── get_pending_changes_count()  → 扫描所有 backup_info.json
        │
        └── handle_pending_changes()
              ├── y → apply_all_changes()
              ├── n → revert_all_changes()  (从备份还原)
              └── s → 跳过，下次再问
```

---

## 核心架构

```
main.py                     # CLI 入口，命令路由，回调处理
modules/chat.py             # 聊天核心（流式处理、工具执行、迭代循环）
modules/config.py           # 配置管理 + 模型注册表 + 废弃检查
modules/skill_manager.py    # 技能加载与调用
modules/plugin_skill_loader.py  # 插件加载（从 ZIP 文件）
modules/request_manager.py  # 内部请求分发（PROMPT/FILE/CONFIG/LOGGER）
modules/prompt_manager.py   # 系统提示词管理
modules/file_operation.py   # 集中化文件读写
modules/backup_manager.py   # 对话级文件备份与恢复
modules/commands.py         # 命令管理（前缀化、关键词校验、启动自动修复）
modules/conversation.py     # 对话历史保存与加载
modules/logger.py           # 日志系统
modules/mcp_manager.py      # MCP 协议管理器
```

---

## 申请处理

Request Manager 处理**不需要用户交互**的内部请求，需用户交互的申请由 chat.py 直接通过 callback 处理：

| 申请类型 | 处理位置 | 说明 |
|----------|----------|------|
| `USER_INPUT` | chat.py | 阻塞等待用户输入 |
| `CONFIRMATION` | chat.py | 阻塞等待 y/n 确认 |
| `SKILL_CONFIRMATION` | chat.py | 确认后执行（PowerShell 直执行） |
| `PROMPT_REQUEST` | request_manager → prompt_manager | 获取系统提示 |
| `FILE_OPERATION` | request_manager → file_operation | 文件读写 |
| `CONFIG_REQUEST` | request_manager → config | 读/写配置 |
| `LOGGER_REQUEST` | request_manager → logger | 日志操作 |

---

## 技能系统

内置 6 个技能，位于 `skills/` 目录：

| 技能 | 功能 | 工具 |
|------|------|------|
| **calculator** | sympy 数学表达式求值、获取当前时间 | `calculate`, `get_current_time` |
| **file_reader** | 文件搜索、目录结构查看、文件内容阅读 | `get_work_directory`, `search_files`, `list_directory`, `read_file` |
| **file_manager** | 文件创建、修改、删除、工作目录切换 | `set_work_directory`, `create_file`, `modify_file`, `delete_file` |
| **powershell_executor** | PowerShell 脚本异步执行（需用户确认），支持后台轮询与强制终止 | `run_script`, `check_script`, `kill_command` |
| **random_generator** | 随机数、随机选择、随机密码生成 | `random_int`, `random_float`, `random_choice`, `random_password` |
| **web_search** | 网络搜索（DuckDuckGo） | `search` |

### 面向用户输出 (user_output)

Skill 工具可以通过返回 `user_output` 字段精简终端显示，避免冗长的原始 JSON。当存在 `user_output` 时，工具调用和结果区块自动隐藏，仅显示一行简约输出。

```python
# 返回格式
return {
    "success": True,
    "result": value,
    "user_output": {"label": "标签", "content": "内容（支持 Fore/RED 等内联色彩）"}
}
```

| 技能 | 工具 | 显示示例 |
|------|------|---------|
| file_reader | `read_file` | `[Read] --example.txt` |
| file_reader | `list_directory` | `[Read] --all\` / `[Read] --subdir\` |
| file_reader | `search_files` | `[Search] --pattern` |
| file_reader | `get_work_directory` | `[Read] workplace` |
| file_manager | `create_file` | `[File Change] test.txt +5(绿) -0(红)` |
| file_manager | `modify_file` | `[File Change] test.txt +3(绿) -2(红)` |
| file_manager | `delete_file` | `[File Change] --test.txt Delet(红)` |
| file_manager | `set_work_directory` | `[Work Place] --.` |
| random_generator | `random_int` | `[Random] --int (1-100)(灰)` |
| random_generator | `random_choice` | `[Random] --choices (a, b, c, ...)(灰)` |
| random_generator | `random_password` | `[Random] --password (12)(灰)` |
| calculator | `calculate` | `[Calculator] 2+3*4(灰) 14` |
| calculator | `get_current_time` | `[Calculator] --time 2026-01-01(灰)` |

### 确认保护

`delete_file` 和 `run_script` 采用系统级确认机制，与 `_process_tool_confirmation` 集成：首次调用返回 `requires_confirmation=True` 触发用户 y/n 确认，确认后系统自动二次调用，无需 AI 介入。

### PowerShell 异步执行架构

```
skill.py (纯确认) ─→ chat.py ─→ modules/powershell_manager.py (子进程管理)
```

| 模块 | 职责 |
|------|------|
| `skill.py` | 只做脚本长度校验 + 创建确认请求，无子进程代码 |
| `chat.py` | 确认后调用 `powershell_manager.execute_script()` |
| `powershell_manager.py` | 集中管理所有子进程：创建、等待、超时、轮询、终止、清理 |

**执行流程：**
1. `run_script(script, timeout, wait_time)` → 确认后 → `asyncio.create_subprocess_exec()`
2. 后台 task 实时读取 stdout/stderr 到缓冲区
3. `asyncio.wait_for(process.wait(), timeout=wait_time)` — 命令完成则**立即返回**，不等够时间
4. 超时未完成 → 返回当前输出 + `command_id: dps0001`，**命令不杀死继续运行**
5. `check_script(command_id, wait_time)` → 轮询状态（running/done + output）
6. `kill_command(command_id)` → 强制终止 + 清理 transport
7. 程序退出 → `atexit` + `signal` 自动清理所有子进程

---

## 插件系统

插件以 ZIP 格式存放在 `plugins/` 目录，启动时自动加载。支持 `manifest.json` 配置。

示例：`plugins/user_input_plugin.zip` — 用户输入与确认插件。

---

## 流式输出

Dolphin 使用流式输出，终端实时展示：

- **思考过程**：暗色文字逐字输出
- **回复内容**：正常颜色逐字输出（打字机效果）
- **工具调用与结果**：蓝色/绿色标识

---

## 文件备份

AI 修改文件时自动创建对话级备份，退出程序时提示用户确认是否应用或撤销更改。每个文件每轮对话只备份一次。

---

## 对话管理

- 对话历史保存在 `date/conversations/` 下
- 支持保存、加载、列表查看
- 加载对话时自动重置工作目录

---

## 技能开发

在 `skills/` 下创建新文件夹并编写 `skill.py`：

```python
skill_info = {
    "name": "my_skill",
    "description": "技能描述",
    "functions": {
        "my_function": {
            "description": "函数描述",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "参数说明"}
                },
                "required": ["param1"]
            }
        }
    }
}

def my_function(param1: str):
    return {"result": param1}
```

工具命名格式：`skill_<技能名>_<函数名>`，例如 `skill_calculator_add`。

详见 [skills/README.md](skills/README.md)。

---

## 配置结构

配置分为两个文件：

**`date/config.json`**（不含敏感数据）：

```json
{
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-v4-flash",
  "max_tokens": 8192,
  "skills": {},
  "plugins": {}
}
```

**`date/.env`**（敏感数据）：

```
QUICKAI_API_KEY=your_api_key_here
QUICKAI_WORK_DIRECTORY=workplace
```

- `api_key` 和 `work_directory` 仅在 `date/.env` 中保存，`config.json` 不再包含这两项
- 旧版 `config.json` 中的存量数据会在首次加载时自动迁移到 `.env` 并清除
- 所有配置均可通过 `/set`、`/model` 和 `/open` 修改，`date/.env` 无需手动编辑

---

## 依赖

```
openai>=1.0.0
python-dotenv>=1.0.0
mcp>=1.0.0
requests>=2.31.0
flask>=2.0.0
flask-cors>=3.0.0
colorama>=0.4.6
sympy>=1.12
```

---

## 许可证

MIT License

# Dolphin Skill 使用说明

## 概述

Dolphin 通过技能（Skills）系统扩展 AI 能力，AI 可自动调用工具完成文件操作、计算、搜索等任务。

## 内置技能

### calculator — 数学计算与时间
| 工具 | 说明 |
|------|------|
| `calculate(expression)` | 通过 sympy 求值数学表达式（支持 + - * / **、sqrt、sin/cos/tan、log、pi、e 等） |
| `get_current_time()` | 返回当前日期时间字符串 |

### file_reader — 文件读取与搜索
| 工具 | 说明 |
|------|------|
| `get_work_directory()` | 返回当前工作目录 |
| `search_files(pattern, ...)` | 按名称或内容搜索（最多 500 条结果，跳过 >10MB 文件） |
| `list_directory(path, ...)` | 树状视图列出目录（最多 1000 个文件，深度 10） |
| `read_file(path, ...)` | 分页读取文件内容（每次最多 1000 行，最大 10MB） |

### file_manager — 文件管理
| 工具 | 说明 |
|------|------|
| `set_work_directory(path)` | 切换工作目录（仅限子目录，支持 `..`，越界自动回退） |
| `create_file(path, content)` | 创建文件并写入内容（最大 10MB，1000 行） |
| `modify_file(path, old_string, new_string)` | 字符串查找替换修改（三级匹配） |
| `delete_file(path)` | 删除文件（需用户确认） |

### powershell_executor — PowerShell 脚本执行
| 工具 | 说明 |
|------|------|
| `run_script(script, timeout, wait_time)` | 异步执行 PowerShell 脚本（需用户确认） |
| `check_script(command_id, wait_time)` | 轮询后台命令状态和输出 |
| `kill_command(command_id)` | 强制终止后台命令 |

超时后命令继续在后台运行，不自动杀死。程序退出时通过 `atexit` + signal 自动清理所有子进程。

### random_generator — 随机生成
| 工具 | 说明 |
|------|------|
| `random_int(min, max)` | 随机整数 |
| `random_float(min, max)` | 随机浮点数 |
| `random_choice(choices)` | 从列表中随机选取一项 |
| `random_password(length, ...)` | 可配置字符集的随机密码 |

### web_search — 网络搜索
| 工具 | 说明 |
|------|------|
| `search(query, num_results)` | DuckDuckGo API 搜索 |

---

## 创建自定义技能

### 文件夹结构

```
skills/
├── my_skill/
│   └── skill.py
├── calculator/
│   └── skill.py
└── web_search/
    └── skill.py
```

### skill.py 模板

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
                    "param1": {"type": "string", "description": "参数1"},
                    "param2": {"type": "number", "description": "参数2"}
                },
                "required": ["param1"]
            }
        }
    }
}

def my_function(param1: str, param2: float = 0.0) -> str:
    return f"结果: {param1}, {param2}"
```

### 要求

1. 每个技能一个独立文件夹，名称即技能名
2. 必须包含 `skill.py`
3. `skill_info` 必须定义 `name`、`description`、`functions`
4. 函数参数类型需与 JSON Schema 兼容
5. 文件夹名不能以下划线开头

### SkillContext 注入（推荐）

技能函数可声明 `context` 参数获取统一接口：

```python
def my_function(context, param1: str) -> str:
    # context.work_directory — 当前工作目录
    # context.log_info("消息")     — 日志
    # context.file_operation(...)  — 文件操作
    # context.require_confirmation(...) — 用户确认
    return "结果"
```

未声明 `context` 的函数保持向后兼容。

---

## 工具命名规则

- **Skill**: `skill_<技能名>_<函数名>` → 例：`skill_calculator_calculate`
- **Plugin**: `plugin_<插件名>_<函数名>`
- **MCP**: `<服务器名>_<工具名>` → 例：`filesystem_read_file`

## user_output 精简显示

工具可通过返回 `user_output` 字段简化终端输出：

```python
return {
    "success": True,
    "result": value,
    "user_output": {"label": "标签", "content": "内容"}
}
```

返回 `user_output` 时，冗长的工具调用/结果区块自动隐藏，仅显示一行简约标签。

## 命令参考

| 命令 | 说明 |
|------|------|
| `/tools` | 查看所有可用工具 |
| `/skills` | 管理技能启用/禁用 |
| `/toggle` | 切换单个工具启用状态 |

命令前缀默认为 `/`，可通过 `/set` 修改。

## 故障排除

| 问题 | 排查方向 |
|------|----------|
| 技能未加载 | 检查 `skills/` 目录下文件夹结构和 `skill_info` 定义 |
| 工具调用失败 | 检查工具名称格式、参数是否符合 JSON Schema |
| MCP 连接失败 | 确认 MCP 服务器运行状态和连接参数，查看日志 |

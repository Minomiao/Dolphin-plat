# Skills 目录说明

本目录包含 Dolphin 的所有技能（Skills）。

## 目录结构

每个技能都有自己独立的文件夹，包含以下文件：

```
skills/
├── calculator/           # 计算器技能
│   └── skill.py          # 技能实现文件
├── file_manager/         # 文件管理器技能
│   └── skill.py
├── file_reader/          # 文件阅读器技能
│   └── skill.py
├── powershell_executor/  # PowerShell 执行器技能
│   └── skill.py
├── random_generator/     # 随机数生成器技能
│   └── skill.py
└── web_search/          # 网络搜索技能
    └── skill.py
```

## 创建新技能

### 1. 创建技能文件夹

在 `skills/` 目录下创建一个新的文件夹，例如 `my_skill/`

### 2. 创建 skill.py 文件

在技能文件夹中创建 `skill.py` 文件，包含技能的实现。

所有技能函数可以通过声明 `context` 参数来获取统一的程序能力接口（`SkillContext`），无需手动 import 内部模块：

```python
from typing import Dict, Any

skill_info = {
    "name": "my_skill",
    "description": "我的自定义技能",
    "functions": {
        "my_function": {
            "description": "函数描述",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "参数1"},
                },
                "required": ["param1"]
            }
        }
    }
}

def my_function(context, param1: str) -> Dict[str, Any]:
    # context.work_directory — 当前工作目录
    # context.logger — 日志对象
    # context.log_info(msg) / log_warning(msg) / log_error(msg)
    # context.file_operation("create_file", file_path=..., content=...)
    # context.require_confirmation(message=..., action=...)
    # context.backup_manager — 备份管理器
    # context.execute_script(script, timeout, wait_time) — PowerShell 执行
    context.log_info(f"my_function called with {param1}")
    return {"success": True, "result": param1}
```

### SkillContext 提供的能力

| 方法/属性 | 说明 |
|---|---|
| `context.work_directory` | 当前工作目录绝对路径 |
| `context.logger` | 日志对象 |
| `context.log_info(msg)` | 写入 info 日志 |
| `context.log_warning(msg)` | 写入 warning 日志 |
| `context.log_error(msg)` | 写入 error 日志 |
| `context.resolve_path(path)` | 相对路径 → 绝对路径 |
| `context.is_path_allowed(path)` | 检查路径是否在允许范围内 |
| `context.file_operation(op, **kw)` | 通过 request_manager 执行文件操作 |
| `context.require_confirmation(msg, action, **kw)` | 请求用户确认 |
| `context.require_user_input(prompt, default)` | 请求用户输入 |
| `context.backup_manager` | 备份管理器（仅 file_manager） |
| `context.execute_script(script, timeout, wait_time)` | 执行 PowerShell 脚本（异步） |
| `context.check_script(command_id, wait_time)` | 查询后台命令状态 |
| `context.kill_command(command_id)` | 强制终止后台命令 |

**向后兼容**：如果函数不声明 `context` 参数，则按旧的 `func(**arguments)` 方式调用（与之前行为一致）。

## 工具命名规则

工具名称格式为：`skill_<技能名>_<函数名>`

例如：
- `skill_calculator_calculate` - 计算器技能的计算函数
- `skill_file_reader_read_file` - 文件阅读器技能的读取函数
- `skill_file_manager_create_file` - 文件管理器技能的创建文件函数

## 现有技能

### 1. calculator（计算器）
提供基本的数学计算功能：
- `calculate` - 使用 sympy 求值数学表达式
- `get_current_time` - 获取当前时间

### 2. file_reader（文件阅读器）
提供文件搜索、目录结构查看和文件阅读功能：
- `get_work_directory` - 获取当前工作目录
- `search_files` - 在指定目录下搜索文件（支持文件名和内容搜索）
- `list_directory` - 列出目录结构（树形结构显示）
- `read_file` - 读取文件内容（每次最多 1000 行，支持分页）

**安全特性：**
- 所有文件操作限制在工作目录内，通过 dpc 机制校验
- 跳过大于 10MB 的文件
- 内置路径越界检查

### 3. file_manager（文件管理器）
提供文件创建、修改和删除功能：
- `set_work_directory` - 临时切换工作目录（子目录，支持 `..`，越界回退）
- `create_file` - 创建文件并写入内容
- `modify_file` - 修改文件内容（字符串查找替换）
- `delete_file` - 删除文件（需用户确认）

**安全特性：**
- 所有文件操作限制在工作目录内
- 限制文件大小（最大 10MB）、行数（最大 1100 行）
- 删除文件需用户确认
- 自动去重行号标记
- 修改文件采用三级匹配策略（精确 → 去空白 → 95% 模糊）

### 4. powershell_executor（PowerShell 执行器）
提供 PowerShell 脚本异步执行功能：
- `run_script(script, timeout, wait_time)` — 异步运行脚本，wait_time 后返回（未完成附 command_id）
- `check_script(command_id, wait_time)` — 轮询后台命令状态和输出
- `kill_command(command_id)` — 强制终止后台命令

**安全特性：**
- 危险脚本检测（DANGEROUS_PATTERNS 正则匹配）
- 危险脚本需用户确认后才能执行
- 限制脚本长度（最大 10000 字符）
- 限制输出长度（最大 50000 字符 / 500 行）
- 超时后命令继续后台运行，通过 atexit/signal 兜底清理

### 5. random_generator（随机数生成器）
提供各种随机数生成功能：
- `random_int` - 生成指定范围内的随机整数
- `random_float` - 生成指定范围内的随机浮点数
- `random_choice` - 从列表中随机选择一个元素
- `random_password` - 生成随机密码

### 6. web_search（网络搜索）
提供网络搜索功能：
- `search` - 使用 DuckDuckGo 搜索网络信息

## 注意事项

1. 每个技能文件夹必须包含 `skill.py` 文件
2. `skill.py` 必须定义 `skill_info` 字典
3. 函数参数必须与 JSON Schema 兼容
4. 如需获取程序能力，声明 `context` 参数即可，无需 import 内部模块
5. 技能会在程序启动时自动加载
6. 不需要创建 `__init__.py` 文件

## 更多信息

详细的使用说明请参考 [SKILL_OPERATION_GUIDE.md](SKILL_OPERATION_GUIDE.md)

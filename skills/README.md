# Skills 目录说明

本目录包含 QuickAI 的所有技能（Skills）。

## 目录结构

每个技能都有自己独立的文件夹，包含以下文件：

```
skills/
├── __pycache__/           # Python 缓存目录
├── calculator/           # 计算器技能
│   └── skill.py          # 技能实现文件
├── random_generator/     # 随机数生成器技能
│   └── skill.py
└── web_search/          # 网络搜索技能
    └── skill.py
```

## 创建新技能

### 1. 创建技能文件夹

在 `skills/` 目录下创建一个新的文件夹，例如 `my_skill/`

### 2. 创建 skill.py 文件

在技能文件夹中创建 `skill.py` 文件，包含技能的实现：

```python
import datetime

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

**注意：** 不需要创建 `__init__.py` 文件，技能管理器会自动加载 `skill.py` 文件。

## 技能命名规则

- 技能文件夹名称即为技能名称
- 只能包含小写字母、数字和下划线
- 不能以数字或下划线开头
- 建议使用有意义的名称，如 `calculator`、`web_search` 等

## 工具命名规则

工具名称格式为：`skill_<技能名>_<函数名>`

例如：
- `skill_calculator_add` - 计算器技能的加法函数
- `skill_web_search_search` - 网络搜索技能的搜索函数
- `skill_random_generator_random_int` - 随机数生成器技能的随机整数函数

## 现有技能

### 1. calculator（计算器）
提供基本的数学计算功能：
- `add` - 加法运算
- `subtract` - 减法运算
- `multiply` - 乘法运算
- `divide` - 除法运算
- `get_current_time` - 获取当前时间

### 2. file_reader（文件阅读器）
提供文件搜索、目录结构查看和文件阅读功能：
- `get_work_directory` - 获取当前工作目录
- `set_work_directory` - 设置工作目录（所有文件操作将限制在此目录内）
- `set_confirmation_required` - 设置是否需要用户确认（启用后，操作工作目录外的文件需要确认）
- `search_files` - 在指定目录下搜索文件（支持文件名和内容搜索）
- `list_directory` - 列出目录结构（树形结构显示）
- `read_file` - 读取文件内容

**安全特性：**
- 所有文件操作默认限制在工作目录内（默认为当前目录 `.`）
- 可以通过 `set_work_directory` 修改工作目录
- 可以通过 `set_confirmation_required` 启用确认机制
- 当启用确认机制时，操作工作目录外的文件会提示用户确认
- 确认操作由程序执行，而非 AI 自动执行

**功能特点：**
- 支持按文件名搜索
- 支持在文件内容中搜索关键词
- 支持按文件扩展名过滤
- 支持树形结构显示目录
- 支持设置最大递归深度
- 支持显示/隐藏隐藏文件

### 3. file_manager（文件管理器）
提供文件创建、修改和删除功能：
- `get_work_directory` - 获取当前工作目录
- `set_work_directory` - 设置工作目录（所有文件操作将限制在此目录内）
- `set_confirmation_required` - 设置是否需要用户确认（启用后，操作工作目录外的文件需要确认）
- `create_file` - 创建文件并写入内容（AI 可以决定文件名和后缀）
- `modify_file` - 修改文件内容（需要提供原有内容和修改后的内容）
- `delete_file` - 删除文件（需要用户确认）
- `confirm_delete_file` - 确认删除文件（在用户确认后调用）

**安全特性：**
- 所有文件操作默认限制在工作目录内（默认为当前目录 `.`）
- 可以通过 `set_work_directory` 修改工作目录
- 可以通过 `set_confirmation_required` 启用确认机制
- 当启用确认机制时，操作工作目录外的文件会提示用户确认
- 确认操作由程序执行，而非 AI 自动执行
- 限制文件大小（最大 10MB）
- 修改文件时验证原有内容，防止并发修改冲突
- 删除文件时需要用户确认

**功能特点：**
- AI 可以自动决定文件名和后缀
- 自动创建不存在的父目录
- 支持自定义文件编码（默认为 UTF-8）
- 返回文件大小和行数统计
- 修改文件时验证原有内容，确保修改的是正确的版本
  - 删除文件前显示文件大小，让用户确认

### 4. powershell_executor（PowerShell 执行器）
提供 PowerShell 脚本执行功能：
- `set_confirmation_required` - 设置是否需要用户确认（启用后，运行脚本前需要用户确认）
- `set_timeout` - 设置脚本执行的超时时间（秒）
- `run_script` - 请求运行 PowerShell 脚本（显示脚本内容，请求用户确认）
- `confirm_run_script` - 确认运行 PowerShell 脚本（在用户确认后调用）

**安全特性：**
- 运行脚本前必须用户确认
- 限制脚本长度（最大 10000 字符）
- 限制输出长度（最大 50000 字符）
- 设置超时时间（默认 30 秒）
- 确认操作由程序执行，而非 AI 自动执行

**功能特点：**
- 显示脚本预览（前 500 字符）
- 显示脚本长度
- 捕获标准输出和错误输出
- 输出过长时自动截断
- 返回脚本执行结果和返回码

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
4. 确保技能文件没有语法错误
5. 技能会在程序启动时自动加载
6. 不需要创建 `__init__.py` 文件

## 更多信息

详细的使用说明请参考 [MCP_SKILL_GUIDE.md](../MCP_SKILL_GUIDE.md)

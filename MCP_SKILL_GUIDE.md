# QuickAI MCP 和 Skill 使用说明

## 概述

QuickAI 现在支持 MCP (Model Context Protocol) 和自定义 Skill 功能，让 AI 能够使用各种工具来增强其能力。

## 功能特性

### 1. Skill 系统
- 自动加载 `skills/` 目录下的所有技能文件
- 每个技能可以包含多个可调用的函数
- 支持同步和异步函数
- AI 可以根据需要自动调用这些函数

### 2. MCP 支持
- 支持连接到 MCP 服务器
- 可以使用 MCP 提供的工具
- 支持多个 MCP 服务器同时连接

### 3. 工具调用
- AI 可以自动决定何时使用工具
- 支持流式和非流式对话
- 显示工具调用的详细信息

## 内置技能

### 1. 计算器技能 (calculator)
提供基本的数学计算功能：
- `add`: 加法运算
- `subtract`: 减法运算
- `multiply`: 乘法运算
- `divide`: 除法运算
- `get_current_time`: 获取当前时间

### 2. 网络搜索技能 (web_search)
搜索网络信息：
- `search`: 使用 DuckDuckGo 搜索网络

## 使用方法

### 命令

在 QuickAI 中可以使用以下命令：

- `.tools` - 查看所有可用工具
- `.skills` - 查看所有可用技能
- `.toggle` - 切换工具启用/禁用状态

### 示例对话

```
您: 5 + 3 等于多少？
工具调用:
  - skill_calculator_add
    参数: {"a": 5, "b": 3}
  结果: 8
QuickAI: 5 + 3 = 8
```

```
您: 现在几点了？
工具调用:
  - skill_calculator_get_current_time
    参数: {}
  结果: 2026-02-17 23:30:00
QuickAI: 现在是 2026-02-17 23:30:00
```

## 创建自定义技能

### 技能文件夹结构

每个技能都应该有自己的独立文件夹，结构如下：

```
skills/
├── my_skill/
│   ├── __init__.py
│   └── skill.py
├── calculator/
│   ├── __init__.py
│   └── skill.py
└── web_search/
    ├── __init__.py
    └── skill.py
```

### 技能文件内容

在技能文件夹中创建 `skill.py` 文件：

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
                    "param1": {"type": "string", "description": "参数1描述"},
                    "param2": {"type": "number", "description": "参数2描述"}
                },
                "required": ["param1"]
            }
        }
    }
}

def my_function(param1: str, param2: float = 0.0) -> str:
    return f"结果: {param1}, {param2}"
```

在技能文件夹中创建 `__init__.py` 文件：

```python
from .skill import skill_info
```

### 技能文件要求

1. 每个技能必须有自己的独立文件夹
2. 文件夹名称即为技能名称
3. 文件夹中必须包含 `skill.py` 和 `__init__.py` 文件
4. `skill.py` 必须定义 `skill_info` 字典
5. `skill_info` 必须包含：
   - `name`: 技能名称
   - `description`: 技能描述
   - `functions`: 函数字典
6. 每个函数必须在 `skill_info['functions']` 中定义
7. 实际的函数必须在 `skill.py` 中定义
8. 函数参数类型应该与 `parameters` 定义匹配

## 工具命名规则

- Skill 工具: `skill_<技能名>_<函数名>`
  - 例如: `skill_calculator_add`
- MCP 工具: `<服务器名>_<工具名>`
  - 例如: `filesystem_read_file`

## 配置

### 启用/禁用工具

使用 `.toggle` 命令可以切换工具的启用状态。

### 代码中配置

```python
from modules import chat

chat_instance = chat.QuickAIChat(
    model="deepseek-chat",
    enable_tools=True  # 启用工具
)
```

## 注意事项

1. 工具名称只能包含字母、数字、下划线和连字符
2. 技能文件名不能以下划线开头
3. 函数参数必须与 JSON Schema 兼容
4. 确保技能文件中的函数没有语法错误
5. MCP 服务器需要单独配置和启动

## 故障排除

### 技能未加载
- 检查技能文件是否在 `skills/` 目录下
- 检查 `skill_info` 是否正确定义
- 检查函数是否与定义匹配

### 工具调用失败
- 检查工具名称是否正确
- 检查参数是否符合要求
- 查看错误信息获取详细原因

### MCP 连接失败
- 确保 MCP 服务器正在运行
- 检查连接参数是否正确
- 查看错误日志获取详细信息

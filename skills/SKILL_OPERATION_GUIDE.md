# Skill 操作参考文档

## 概述

本文档详细说明 Skill 如何使用 `SkillContext` 统一接口进行文件操作、备份、确认和 PowerShell 执行。

## SkillContext 接口

`SkillContext` 是程序注入到 skill 函数的统一上下文对象。在函数签名中声明 `context` 参数即可获取所有程序能力，无需手动 import 内部模块。

### 获取 context

```python
def my_skill_fn(context, param1: str) -> Dict[str, Any]:
    wd = context.work_directory
    context.log_info(f"working in {wd}")
    ...
```

### 完整能力清单

| 方法/属性 | 说明 |
|---|---|
| `context.work_directory` | 当前工作目录绝对路径 |
| `context.logger` | 日志对象 |
| `context.log_info(msg)` | info 日志 |
| `context.log_warning(msg)` | warning 日志 |
| `context.log_error(msg)` | error 日志 |
| `context.resolve_path(path)` | 相对路径 → 绝对路径 |
| `context.is_path_allowed(path)` | 检查路径是否在允许范围内 |
| `context.file_operation(op, **kw)` | 执行文件操作（create/modify/delete） |
| `context.require_confirmation(msg, action, **kw)` | 请求用户确认 |
| `context.require_user_input(prompt, default)` | 请求用户输入 |
| `context.backup_manager` | 备份管理器 |
| `context.execute_script(script, timeout, wait_time)` | 执行 PowerShell 脚本 |
| `context.check_script(command_id, wait_time)` | 查询后台命令 |
| `context.kill_command(command_id)` | 终止后台命令 |

### 向后兼容

不声明 `context` 参数的函数按旧方式 `func(**arguments)` 调用。

## 确认机制

### 发式确认

通过 `context.require_confirmation` 请求用户确认：

```python
def delete_file(context, file_path: str) -> Dict[str, Any]:
    if not should_delete_directly:
        return context.require_confirmation(
            message=f"确认删除文件: {file_path}",
            action="delete_file",
            file_path=file_path,
        )

    # 执行删除
    result = context.file_operation("delete_file", file_path=file_path)
    result["user_output"] = {"label": "File Change", "content": f"--{file_path} Delet"}
    return result
```

### 主程序处理

`SkillManager` 通过 `context.require_confirmation` 调用 `request_manager.create_skill_confirmation()`，主程序检测到后显示确认提示，用户确认后重新调用 skill 函数。

## 文件操作

### 创建文件

```python
def create_file(context, file_path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
    result = context.file_operation(
        "create_file",
        file_path=file_path,
        content=content,
        encoding=encoding,
    )
    # context.file_operation 已自动填充 work_directory
    if result.get("success"):
        result["user_output"] = {"label": "File Change", "content": f"{Path(file_path).name} +{result.get('line_count', 0)}"}
    return result
```

### 修改文件

```python
def modify_file(context, file_path: str, old_str: str, new_str: str, encoding: str = "utf-8") -> Dict[str, Any]:
    result = context.file_operation(
        "modify_file",
        file_path=file_path,
        old_str=old_str,
        new_str=new_str,
        encoding=encoding,
    )
    if result.get("success"):
        result["user_output"] = {"label": "File Change", "content": f"{Path(file_path).name}"}
    return result
```

### 删除文件

```python
def delete_file(context, file_path: str, confirmed: bool = False) -> Dict[str, Any]:
    if not confirmed:
        return context.require_confirmation(
            message=f"确认删除文件: {file_path}",
            action="delete_file",
            file_path=file_path,
        )
    result = context.file_operation("delete_file", file_path=file_path)
    result["user_output"] = {"label": "File Change", "content": f"--{Path(file_path).name} Delet"}
    return result
```

## PowerShell 执行

```python
def run_command(context, script: str, timeout: int = 30, wait_time: int = 10) -> Dict[str, Any]:
    context.log_info(f"执行脚本: {len(script)} 字符")

    # 危险脚本确认
    if is_dangerous(script):
        return context.require_confirmation(
            message=f"确认执行脚本: {script[:500]}",
            action="run_script",
            script=script,
            timeout=timeout,
            wait_time=wait_time,
        )

    # 安全脚本自动执行，返回 auto_execute 标记
    return {
        "auto_execute": True,
        "action": "run_script",
        "script": script,
        "timeout": timeout,
        "wait_time": wait_time,
    }


async def check_status(context, command_id: str, wait_time: int = 10) -> Dict[str, Any]:
    result = await context.check_script(command_id, wait_time)
    result["user_output"] = {"label": "Read", "content": f"--{command_id}"}
    return result


def stop_command(context, command_id: str) -> Dict[str, Any]:
    result = context.kill_command(command_id)
    result["user_output"] = {"label": "Stop", "content": f"--{command_id}"}
    return result
```

## 备份管理

`context.file_operation()` 内部已集成备份管理，文件操作前自动备份，skill 无需手动调用 backup_manager。

如需手动操作：

```python
def my_operation(context):
    if context.backup_manager:
        context.backup_manager.backup_file(file_path, context.work_directory, action="modify")
        context.backup_manager.record_change(action="modify", file_path=file_path, work_dir=context.work_directory)
```

## 确认机制的最佳实践

1. **命中即确认**：删除、危险命令、工作目录外操作
2. **清晰明确**：确认消息包含操作内容和影响
3. **使用 `user_output`**：提供紧凑的终端显示

## 旧式与 context 式对比

| | 旧式 | context 式 |
|---|---|---|
| 获取工作目录 | `get_work_dir()` 自实现 | `context.work_directory` |
| 日志 | `get_logger()` via request_manager | `context.log_info(...)` |
| 文件操作 | `req_mgr.create_file_operation_request()` + `handle_request()` | `context.file_operation("create_file", ...)` |
| 确认 | `self-code` 或 `rm.create_skill_confirmation()` | `context.require_confirmation(...)` |
| PowerShell | `from modules.functions import powershell_manager` | `context.execute_script(...)` |
| 模块导入 | `sys.path.insert` + import | 零 import |

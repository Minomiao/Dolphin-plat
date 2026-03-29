# Skill 操作参考文档

## 概述

本文档详细说明 Skill 如何向主程序发出确认申请，以及如何调用备份管理器进行文件备份的完整流程。

## 确认操作流程

### 1. Skill 发起确认申请

当 Skill 需要用户确认才能执行操作时，应返回特定格式的结果，标记该操作需要确认。

### 2. 主程序处理确认

主程序检测到确认申请后，向用户显示确认提示，获取用户的确认或取消输入。

### 3. 执行确认后的操作

用户确认后，主程序重新调用 Skill 执行实际操作。

## 确认申请格式

### 基本格式

```python
{
    "requires_confirmation": True,  # 必须字段：标记需要确认
    "message": "确认操作的详细信息"  # 必须字段：显示给用户的确认信息
}
```

### 可选字段

```python
{
    "requires_confirmation": True,
    "message": "确认操作的详细信息",
    "confirmed": False,  # 可选：标记操作是否已经确认
    "additional_data": {  # 可选：其他业务相关数据
        "key": "value"
    }
}
```

## 代码示例

### 示例 1：文件删除确认

**Skill 端代码**：

```python
def delete_file(file_path: str) -> Dict[str, Any]:
    """删除文件"""
    # 检查是否需要确认
    if CONFIRMATION_REQUIRED and not is_in_work_dir(file_path):
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        return {
            "requires_confirmation": True,
            "message": f"确认删除文件: {file_path} (大小: {file_size} 字节)"
        }
    
    # 直接执行删除操作
    try:
        os.remove(file_path)
        return {
            "success": True,
            "message": f"文件删除成功: {file_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"删除文件失败: {e}"
        }
```

### 示例 2：工作目录外文件操作确认

**Skill 端代码**：

```python
def read_file(file_path: str) -> Dict[str, Any]:
    """读取文件"""
    # 检查是否需要确认
    if CONFIRMATION_REQUIRED and not is_in_work_dir(file_path):
        return {
            "requires_confirmation": True,
            "message": f"确认读取工作目录外的文件: {file_path}"
        }
    
    # 直接执行读取操作
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {
            "success": True,
            "content": content,
            "message": f"文件读取成功: {file_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"读取文件失败: {e}"
        }
```

## 主程序处理流程

### 确认处理代码

**modules/chat.py** 中的处理逻辑：

```python
# 处理工具调用结果
if result_dict.get("requires_confirmation"):
    # 检查是否已经处理过确认
    if not result_dict.get("confirmed"):
        print(f"\n⚠️  需要确认:")
        # 显示确认信息
        print(f"  {result_dict.get('message', '此操作需要确认')}")
        # 获取用户输入
        confirm = input("\n是否确认此操作? (y/n): ").lower()
        if confirm != 'y':
            # 取消操作
            log.info(f"用户取消操作: {tool_name}")
            print("操作已取消")
            tool_response = {
                "role": "tool",
                "name": tool_name,
                "content": json.dumps({
                    "success": False,
                    "message": "操作已取消"
                }, ensure_ascii=False)
            }
            tool_responses.append(tool_response)
        else:
            # 确认操作，重新调用 Skill
            log.info(f"用户确认操作: {tool_name}")
            print("操作已确认")
            # 重新执行工具调用
            # ...
```

## 确认机制的实践

### 1. 何时需要确认

- **操作工作目录外的文件**：防止意外修改系统文件
- **删除操作**：防止意外删除重要文件
- **执行脚本**：防止执行恶意代码
- **网络操作**：防止未授权的网络访问
- **其他危险操作**：可能造成系统影响的操作

### 2. 确认信息的编写

- **清晰明确**：准确描述操作内容和影响
- **包含必要信息**：如文件路径、大小、操作类型等
- **简洁明了**：避免过长的确认信息
- **使用一致的格式**：保持确认信息的风格一致

### 3. 实现建议

- **使用常量**：定义 `CONFIRMATION_REQUIRED` 常量控制确认机制
- **统一检查**：创建 `is_in_work_dir()` 函数检查文件是否在工作目录内
- **异常处理**：妥善处理确认过程中的异常情况
- **日志记录**：记录确认操作的详细信息

## 确认机制的配置

### 启用/禁用确认机制

Skill 应提供 `set_confirmation_required` 函数来启用或禁用确认机制：

```python
def set_confirmation_required(required: bool) -> Dict[str, Any]:
    """设置是否需要用户确认"""
    global CONFIRMATION_REQUIRED
    CONFIRMATION_REQUIRED = required
    return {
        "success": True,
        "confirmation_required": CONFIRMATION_REQUIRED,
        "message": f"确认机制已{'启用' if CONFIRMATION_REQUIRED else '禁用'}"
    }
```

## 常见问题

### 1. 确认后如何重新执行操作？

主程序会在用户确认后，使用相同的参数重新调用 Skill 函数。Skill 应检查 `confirmed` 字段或直接执行操作。

### 2. Web 版本如何处理确认？

Web 版本不支持交互式确认，会显示提示信息并建议用户使用命令行版本或确保操作在工作目录内。

### 3. 如何处理批量操作的确认？

对于批量操作，应在开始前进行统一确认，或为每个操作单独确认，取决于操作的风险程度。

## 示例：完整的确认流程

1. **用户请求**：删除文件 `C:\important\data.txt`
2. **Skill 响应**：返回确认申请
   ```python
   {
       "requires_confirmation": True,
       "message": "确认删除文件: C:\important\data.txt (大小: 1024 字节)"
   }
   ```
3. **主程序**：显示确认提示
   ```
   ⚠️  需要确认:
     确认删除文件: C:\important\data.txt (大小: 1024 字节)
   
   是否确认此操作? (y/n): 
   ```
4. **用户输入**：`y`
5. **主程序**：重新调用 Skill 执行删除
6. **Skill**：执行删除操作并返回结果
   ```python
   {
       "success": True,
       "message": "文件删除成功: C:\important\data.txt"
   }
   ```

## 备份管理器调用

### 概述

备份管理器用于在文件操作前创建备份，确保操作可以被撤销。Skill 应在执行文件操作前调用备份管理器进行备份。

### 备份管理器初始化

Skill 应在模块顶部初始化备份管理器：

```python
from modules import backup_manager

backup_mgr = backup_manager
```

### 调用时机

Skill 应在以下操作前调用备份管理器：
- **创建文件**：记录创建操作
- **修改文件**：备份原始文件
- **删除文件**：备份要删除的文件

### 调用格式

#### 1. 备份文件

```python
# 创建操作
backup_path = backup_mgr.backup_file(file_path, work_dir, action="create")

# 修改操作
backup_path = backup_mgr.backup_file(file_path, work_dir, action="modify")

# 删除操作
backup_path = backup_mgr.backup_file(file_path, work_dir, action="delete")
```

**参数说明**：
- `file_path`：文件路径
- `work_dir`：工作目录
- `action`：操作类型（"create"、"modify"、"delete"）

**返回值**：
- 成功：返回备份文件路径
- 失败：返回 None

#### 2. 记录更改

```python
backup_mgr.record_change(
    action="create",  # 操作类型
    file_path=file_path,  # 文件路径
    work_dir=work_dir  # 工作目录
)
```

**参数说明**：
- `action`：操作类型（"create"、"modify"、"delete"）
- `file_path`：文件路径
- `work_dir`：工作目录（可选）

### 完整示例

#### 文件创建示例

```python
def create_file(file_path: str, content: str, work_dir: str = "workplace") -> Dict[str, Any]:
    """创建文件"""
    # 调用备份管理器记录创建操作
    backup_path = backup_mgr.backup_file(file_path, work_dir, action="create")
    
    try:
        # 执行文件创建
        full_path = Path(work_dir) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 记录更改
        backup_mgr.record_change(
            action="create",
            file_path=file_path,
            work_dir=work_dir
        )
        
        return {
            "success": True,
            "message": f"文件创建成功: {file_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"创建文件失败: {e}"
        }
```

#### 文件修改示例

```python
def modify_file(file_path: str, content: str, work_dir: str = "workplace") -> Dict[str, Any]:
    """修改文件"""
    # 调用备份管理器备份原始文件
    backup_path = backup_mgr.backup_file(file_path, work_dir, action="modify")
    
    try:
        # 执行文件修改
        full_path = Path(work_dir) / file_path
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 记录更改
        backup_mgr.record_change(
            action="modify",
            file_path=file_path,
            work_dir=work_dir
        )
        
        return {
            "success": True,
            "message": f"文件修改成功: {file_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"修改文件失败: {e}"
        }
```

#### 文件删除示例

```python
def delete_file(file_path: str, work_dir: str = "workplace") -> Dict[str, Any]:
    """删除文件"""
    # 调用备份管理器备份要删除的文件
    backup_path = backup_mgr.backup_file(file_path, work_dir, action="delete")
    
    try:
        # 执行文件删除
        full_path = Path(work_dir) / file_path
        if full_path.exists():
            full_path.unlink()
        
        # 记录更改
        backup_mgr.record_change(
            action="delete",
            file_path=file_path,
            work_dir=work_dir
        )
        
        return {
            "success": True,
            "message": f"文件删除成功: {file_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"删除文件失败: {e}"
        }
```

### 备份管理流程

1. **Skill 调用备份**：在执行文件操作前调用 `backup_file`
2. **执行文件操作**：执行实际的文件创建、修改或删除
3. **记录更改**：调用 `record_change` 记录操作
4. **用户选择**：用户可以选择应用或撤销更改
5. **应用/撤销**：系统执行应用或撤销操作

### 注意事项

1. **必须调用**：所有文件操作都应调用备份管理器
2. **正确的操作类型**：确保传递正确的 `action` 参数
3. **异常处理**：妥善处理备份过程中的异常
4. **日志记录**：备份管理器会自动记录备份操作

## 总结

确认机制和备份机制是保障系统安全的重要组成部分。Skill 开发者应：

1. **遵循确认申请格式**：使用统一的确认申请格式
2. **调用备份管理器**：在文件操作前进行备份
3. **实现安全操作**：确保操作的安全性和可追溯性
4. **提供清晰的用户反馈**：向用户提供明确的操作状态信息

通过遵循本文档的规范，Skill 可以实现安全、可靠的文件操作，同时为用户提供完整的操作控制和恢复能力。
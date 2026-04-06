# 用户输入插件 (user_input)

## 功能描述

用户输入插件允许 AI 在不打断对话的前提下，向用户获取必要的确认信息或输入。该插件提供了两种主要功能：

1. **request_user_input**: 向用户请求输入信息，支持不同的输入类型和验证
2. **confirm_action**: 向用户确认一个操作是否执行

## 安装方法

1. 将插件压缩包放入 `plugins` 目录
2. 系统会自动加载插件

## 使用示例

### 请求用户输入

```python
# 示例：请求用户输入姓名
result = await plugin_user_input_request_user_input({
    "prompt": "请输入您的姓名：",
    "input_type": "text",
    "default_value": "匿名"
})
```

### 确认操作

```python
# 示例：确认是否执行删除操作
result = await plugin_user_input_confirm_action({
    "action": "删除当前文件",
    "default": false
})
```

## 技术实现

插件通过返回特殊结构的响应，指示主程序需要向用户提问或确认。主程序需要实现相应的接收和处理逻辑，以显示提示并获取用户输入。

## 注意事项

- 主程序需要实现对 `user_input_request` 和 `confirmation_request` 类型响应的处理
- 插件本身不直接与用户交互，而是通过主程序进行
- 输入验证需要在主程序中实现

## 版本历史

- v1.0.0: 初始版本，提供基本的用户输入和确认功能
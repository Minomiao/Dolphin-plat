# Dolphin

Dolphin 是一个实验性的 AI 聊天助手项目，旨在通过技能（Skills）系统扩展 AI 的能力，使 DeepSeek 等模型变得更加有用。

## 主要特点

- **技能系统**：通过可插拔的技能模块扩展 AI 功能
- **工具调用**：支持 AI 调用各种工具完成任务
- **多模型支持**：支持 DeepSeek、GPT 等多种 AI 模型
- **对话管理**：支持创建、保存、加载多个对话
- **灵活配置**：可自定义 API 密钥、模型、工作目录等

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

首次运行时，程序会引导你配置：
- API 密钥
- 选择模型（deepseek-chat、deepseek-coder、deepseek-reasoner 等）
- 工作目录

### 运行

```bash
python main.py
```

## 技能系统

QuickAI 的核心是技能系统，通过技能可以扩展 AI 的能力。

### 内置技能

- **calculator** - 数学计算
- **file_reader** - 文件读取和搜索
- **file_manager** - 文件创建、修改、删除
- **powershell_executor** - PowerShell 脚本执行
- **random_generator** - 随机数生成
- **web_search** - 网络搜索

### 创建新技能

在 `skills/` 目录下创建新文件夹，包含 `skill.py` 文件即可。详细说明请参考 [skills/README.md](skills/README.md)

## 命令

- `/help` - 显示帮助信息
- `/set` - 进入设置模式
- `/clear` - 清空历史记录
- `/new` - 创建新对话
- `/load` - 加载对话
- `/save_as` - 保存对话
- `/list` - 列出所有对话
- `/tools` - 显示可用工具
- `/skills` - 显示可用技能
- `/toggle` - 切换工具启用状态
- `/skill` - 技能管理
- `/quit` - 退出程序

## 项目目的

本项目主要用于实验和探索如何通过技能系统扩展 AI 的能力，使 DeepSeek 等模型能够完成更多实际任务。

## 许可证

MIT License

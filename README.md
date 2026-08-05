# dolphincode

基于大语言模型的代码智能体（Code Agent），通过技能（Skills）和插件（Plugins）系统扩展 AI 能力，支持工具调用、对话管理、文件操作和用户交互。

***

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行

```bash
python main.py
```

首次运行自动创建 `workplace/` 工作目录、`date/config.json` 和 `date/.env`。按提示配置 API 密钥和模型即可开始使用。

### 配置文件

| 文件                 | 内容            | 管理方式                    |
| ------------------ | ------------- | ----------------------- |
| `date/.env`        | API 密钥、工作目录   | `/model`、`/workdir` 命令 |
| `date/config.json` | 模型、命令前缀、技能开关等 | `/set` 命令               |

旧版 `config.json` 中的敏感数据会自动迁移到 `.env` 并清除。

***

## 支持的模型

| 模型                | 说明    |
| ----------------- | ----- |
| deepseek-v4-flash | 快速响应  |
| deepseek-v4-pro   | 高质量输出 |

已废弃模型启动时会显示警告及剩余天数，可通过 `/model` 切换。

***

## 命令列表

| 命令                      | 说明                  |
| ----------------------- | ------------------- |
| `/help`                 | 显示帮助信息              |
| `/set`                  | 设置模式（Token 数、命令前缀等） |
| `/back`                 | 返回上一级界面             |
| `/model`                | 切换模型和配置 API 密钥      |
| `/language`             | 选择显示语言（支持 40 种）     |
| `/workdir [path]`       | 打开/切换工作目录           |
| `/clear`                | 清空对话历史              |
| `/new [name]`           | 创建新对话               |
| `/load [name]`          | 加载已保存的对话            |
| `/list`                 | 列出所有已保存对话           |
| `/tools`                | 查看可用工具列表            |
| `/skills`               | 管理技能启用/禁用           |
| `/toggle`               | 切换工具启用/禁用           |
| `/showthinking on\|off` | 显示/隐藏思考过程           |
| `/effort [fine\|normal\|high]` | 设置 AI 思考深度，无参数显示当前 |
| `/changes`              | 处理待应用的备份变更         |
| `/quit`                 | 退出程序                |

所有命令共用可配置的前缀（默认 `/`），通过 `/set` 修改。

### 思考深度

通过 `/effort` 命令调整 AI 的工作模式，影响系统提示词中的行为约束：

| 级别 | 命令 | 说明 |
| --- | --- | --- |
| **精简** | `/effort fine` | 只修改与任务直接相关内容，审视必要性和最小改动方案，优先复用现有功能 |
| **标准** | `/effort normal` | 不确定时向用户询问，使用 `plugin_user_input_request_user_input` 工具 |
| **深度** | `/effort high` | 全面考虑每个细节，不确定时询问，完成后审视逻辑正确性和边界情况 |

默认 `fine`，切换后持久化到 `config.json`，启动时自动恢复。

### 多语言

通过 `/language` 命令选择界面语言，支持 40 种语言（含文言文、喵喵语）。翻译表内置于代码中，首次运行会同步到 `date/language/{code}.json`，可直接编辑文件自定义文案。

***

## 内置技能

位于 `skills/` 目录，共 6 个：

| 技能                       | 功能                     | 工具                                                                  |
| ------------------------ | ---------------------- | ------------------------------------------------------------------- |
| **calculator**           | 数学表达式求值、获取时间           | `calculate`, `get_current_time`                                     |
| **file\_reader**         | 文件搜索、目录浏览、内容阅读         | `get_work_directory`, `search_files`, `list_directory`, `read_file` |
| **file\_manager**        | 文件创建、修改、删除、切换目录        | `set_work_directory`, `create_file`, `modify_file`, `delete_file`   |
| **powershell\_executor** | PowerShell 脚本异步执行（需确认） | `run_script`, `check_script`, `kill_command`                        |
| **random\_generator**    | 随机数、随机选择、密码生成          | `random_int`, `random_float`, `random_choice`, `random_password`    |
| **web\_search**          | Bing 网络搜索 (jieba 关键字相关性过滤) | `search`, `fetch`                                                |

### 安全机制

- **确认保护**：`delete_file` 和 `run_script` 执行前需用户 y/n 确认
- **DPC 文件保护**：`.dpc` 文件控制目录访问权限，保护程序数据不被 AI 读取
- **工作目录隔离**：AI 操作限制在配置的工作目录内，支持子目录切换
- **文件备份**：修改前自动备份到 `date/backup/`，退出时可选择应用/还原

***

## 插件系统

插件以 ZIP 格式存放在 `plugins/` 目录，启动时自动加载。需包含 `manifest.json` 声明技能信息和入口点。

## 许可证

MIT License

### 首次启动：Embedding 模型下载

web_search 技能首次使用时，程序会自动从 hf-mirror 下载 BAAI/bge-small-zh-v1.5 语义向量模型（约 95MB），并自动转换为 ONNX 格式以加速推理。模型存储在 `models/` 目录，下载过程有 Rich 进度条提示。整个过程仅在首次启动时执行一次。

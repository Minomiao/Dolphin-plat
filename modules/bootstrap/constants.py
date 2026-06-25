"""
项目全局固定常量。
所有模块级固定变量集中在此管理，各模块通过 from modules.bootstrap import constants 导入。
"""

# ===== 文件操作限制 =====
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
# MAX_LINE_COUNT 采用 100 行冗余设计：对外声明 1000 行，实际限制 1100 行
# 冗余用于避免创建文件再追加内容时行数统计误差导致的拒绝
MAX_LINE_COUNT = 1100
MAX_FILES_TO_READ = 1000
MAX_SEARCH_RESULTS = 500
MAX_FILES_TO_SEARCH_IN_CONTENT = 100

# ===== PowerShell 执行限制 =====
MAX_SCRIPT_LENGTH = 10000
MAX_OUTPUT_LENGTH = 50000
MAX_OUTPUT_LINES = 500
DEFAULT_TIMEOUT = 30
DEFAULT_WAIT_TIME = 10

# ===== PowerShell 缓存管理 =====
# 缓存有效期（秒）：命令完成后保留多久供 AI 轮询
COMMAND_CACHE_TTL_SECONDS = 3600  # 1小时
# 持久化缓存目录：位于 date 目录下，受 DPC 保护
COMMAND_CACHE_PERSIST_DIR = "command_cache"
# 持久化缓存清理时间（秒）：超过此时间未读取则删除
COMMAND_CACHE_PERSIST_TTL_SECONDS = 86400  # 24小时
# 最大并发缓存数量（超过时转储到持久化）
MAX_COMMAND_CACHE_SIZE = 20

DANGEROUS_PATTERNS = [
    # ===== 文件系统破坏 =====
    r'\bremove-item\b', r'\bremove-itemproperty\b',
    r'\brm\s', r'\bdel\s', r'\bdel\b', r'\brd\s', r'\brmdir\b',
    r'\bclear-content\b', r'\bclear-item\b',
    r'\bformat-volume\b', r'\bclear-disk\b', r'\binitialize-disk\b',
    r'\brename-item\b.*[-/].*path.*(?:system32|windows|boot|etc)\b',
    r'\bmove-item\b.*[-/].*destination.*(?:system32|windows|boot)\b',
    r'\bformat\s+[a-z]:', r'\bdiskpart\b',

    # ===== 进程/服务控制 =====
    r'\bstop-process\b', r'\btaskkill\b', r'\bstop-service\b',
    r'\bstart-process\b.*[-/].*(?:hidden|windowstyle\s+hidden)',

    # ===== 系统状态变更 =====
    r'\brestart-computer\b', r'\bstop-computer\b', r'\bshutdown\b',
    r'\bset-executionpolicy\b', r'\bdisable-psremoting\b', r'\benable-psremoting\b',
    r'\bset-netfirewallrule\b', r'\bset-netfirewallprofile\b',
    r'\bbcdedit\b', r'\bnetsh\b.*(?:firewall|interface|winsock)',

    # ===== 注册表修改 =====
    r'\breg\s+(add|delete|import|load|unload)\b',
    r'\bset-itemproperty\b.*(?:registry|hklm|hkcu|hkcr|hkey)',
    r'\bnew-itemproperty\b.*(?:registry|hklm|hkcu|hkcr|hkey)',
    r'\bregsvr32\b',

    # ===== 用户/权限操作 =====
    r'\bnew-localuser\b', r'\bremove-localuser\b', r'\bset-localuser\b',
    r'\badd-localgroupmember\b', r'\badd-adgroupmember\b',
    r'\bnet\s+(user|localgroup|group)\b',
    r'\bicacls\b', r'\btakeown\b', r'\battrib\b.*[+-]h',

    # ===== 计划任务/持久化 =====
    r'\bschtasks\b', r'\bnew-scheduledtask\b', r'\bregister-scheduledtask\b',
    r'\bwmic\b.*(?:startup|create\s+process)',
    r'\bsc\s+(create|delete|config|stop)',

    # ===== 代码执行/下载执行 =====
    r'\binvoke-expression\b', r'\biex\b',
    r'\binvoke-(?:webrequest|restmethod|wrmethod)\b.*\|.*\b(?:invoke-expression|iex)\b',
    r'\bwget\b.*\|.*\b(?:invoke-expression|iex|sh|bash|cmd)\b',
    r'\bcurl\b.*\|.*\b(?:invoke-expression|iex|sh|bash|cmd)\b',
    r'\bnew-object\b.*\b(?:net\.webclient|system\.net\.webclient)\b',
    r'\bnew-object\b.*\b(?:net\.sockets\.tcpclient|system\.net\.sockets)\b',
    r'\bdownloadstring\b', r'\bdownloadfile\b', r'\bdownloaddata\b',
    r'\bstart-bits transfer\b', r'\bbitsadmin\b',
    r'\bmshta\b', r'\bcertutil\b.*[-/](?:decode|encode|urlcache)',
    r'\brundll32\b',
    r'\bcscript\b', r'\bwscript\b',

    # ===== 编码/混淆执行 =====
    r'[-/](?:enc|encodedcommand|ec|e)\s+\S{20,}',
    r'\[system\.text\.encoding\].*frombase64',
    r'\bfrombase64string\b.*\binvoke-expression\b',
    r'\bfrombase64string\b.*\biex\b',
    r'\bfrombase64string\b.*\bstart-process\b',
]

# ===== 上下文窗口告警阈值 =====
WARN_THRESHOLD = 0.70   # 70%: 提醒用户
HIGH_THRESHOLD = 0.85   # 85%: 建议清理
CRITICAL_THRESHOLD = 0.95  # 95%: 强烈建议清理

# ===== DPC 对话控制文件 =====
DPC_FILENAME = ".dpc"
FILE_ATTRIBUTE_HIDDEN = 0x2

# ===== 对话恢复：文件工具集 =====
FILE_AUTOCOMPLETE_TOOLS = {"create_file", "write_file", "read_file", "modify_file", "delete_file"}

# ===== 模型注册表 =====
MODEL_REGISTRY = {
    "deepseek-v4-flash": {
        "name": "deepseek-v4-flash",
        "description": "DeepSeek V4 Flash",
        "context_window": 1000000,
        "deprecated": False,
    },
    "deepseek-v4-pro": {
        "name": "deepseek-v4-pro",
        "description": "DeepSeek V4 Pro",
        "context_window": 1000000,
        "deprecated": False,
    },
    "deepseek-chat": {
        "name": "deepseek-chat",
        "description": "DeepSeek Chat (已废弃)",
        "context_window": 128000,
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
    "deepseek-reasoner": {
        "name": "deepseek-reasoner",
        "description": "DeepSeek Reasoner(已废弃)",
        "context_window": 128000,
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
    "deepseek-coder": {
        "name": "deepseek-coder",
        "description": "DeepSeek Coder (已废弃)",
        "context_window": 128000,
        "deprecated": True,
        "deprecation_date": "2026-07-24",
        "replacement": "deepseek-v4-flash",
    },
}

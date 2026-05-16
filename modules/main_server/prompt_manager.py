import os
import json
from modules.logger import get_logger

log = get_logger("Dolphin.prompt_manager")

DATE_DIR = "date"
PROMPT_DIR = os.path.join(DATE_DIR, "prompts")
PROMPT_FILE = os.path.join(PROMPT_DIR, "system_prompts.json")

class PromptManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PromptManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """初始化提示词管理器"""
        # 创建提示词目录
        if not os.path.exists(PROMPT_DIR):
            os.makedirs(PROMPT_DIR)
            log.info(f"创建提示词目录: {PROMPT_DIR}")
        
        # 初始化默认提示词
        if not os.path.exists(PROMPT_FILE):
            self._create_default_prompts()
        
        # 加载提示词
        self.prompts = self._load_prompts()
        log.info(f"提示词管理器初始化完成，加载了 {len(self.prompts)} 个提示词")
    
    def _create_default_prompts(self):
        """创建默认提示词"""
        default_prompts = {
            "system": "你是一个AI助手。当用户要求完成任务时，必须确保完成所有必要的步骤，不要中途停止。重要限制：每次只能调用一个工具（skill），等待工具返回结果后，再决定是否需要调用下一个工具。不要同时调用多个工具。重要：在每次回答结束时，必须至少给出一个正常的输出（除了思考过程和工具调用之外的内容），让用户知道发生了什么。始终以完整的回答结束对话。重要：你的所有输出都将显示在终端中，因此请使用纯文本格式输出，不要使用Markdown格式（如 **粗体**、*斜体*、# 标题、- 列表、`代码块`、```代码围栏```、表格、> 引用等），使用自然语言和空格缩进来表达结构和层级。不要输出表情符号（如 emoji）。",
            "file_operation": "你可以帮助用户创建、修改和删除文件。所有文件操作都在当前工作目录下进行，可以使用子文件夹路径。",
            "work_directory": "当前工作目录：{work_directory}。所有文件操作都在此目录下进行。如果需要切换工作目录，请使用 file_manager 技能的 set_work_directory 函数。",
            "directory_structure": "当前工作目录的文件结构：\n{directory_structure}"
        }
        
        with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_prompts, f, ensure_ascii=False, indent=2)
        
        log.info(f"创建默认提示词文件: {PROMPT_FILE}")
    
    def _load_prompts(self):
        """加载提示词"""
        try:
            with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
            return prompts
        except Exception as e:
            log.error(f"加载提示词失败: {e}")
            return {}
    
    def get_prompt(self, prompt_key, **kwargs):
        """获取提示词"""
        prompt = self.prompts.get(prompt_key, "")
        if prompt and kwargs:
            try:
                prompt = prompt.format(**kwargs)
            except Exception as e:
                log.error(f"格式化提示词失败: {e}")
        return prompt
    
    def set_prompt(self, prompt_key, prompt_content):
        """设置提示词"""
        self.prompts[prompt_key] = prompt_content
        self._save_prompts()
        log.info(f"更新提示词: {prompt_key}")
    
    def _save_prompts(self):
        """保存提示词"""
        try:
            with open(PROMPT_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, ensure_ascii=False, indent=2)
            log.debug(f"保存提示词到: {PROMPT_FILE}")
        except Exception as e:
            log.error(f"保存提示词失败: {e}")
    
    def handle_request(self, request):
        """处理提示词请求"""
        request_type = request.get("type")
        if request_type == "get_prompt":
            prompt_key = request.get("prompt_key")
            if not prompt_key:
                return {"error": "缺少 prompt_key"}
            
            # 获取格式化参数
            kwargs = request.get("kwargs", {})
            prompt = self.get_prompt(prompt_key, **kwargs)
            
            return {
                "success": True,
                "prompt": prompt,
                "prompt_key": prompt_key
            }
        elif request_type == "set_prompt":
            prompt_key = request.get("prompt_key")
            prompt_content = request.get("prompt_content")
            if not prompt_key or prompt_content is None:
                return {"error": "缺少 prompt_key 或 prompt_content"}
            
            self.set_prompt(prompt_key, prompt_content)
            return {
                "success": True,
                "prompt_key": prompt_key
            }
        else:
            return {"error": "未知的请求类型"}

def get_prompt_manager():
    """获取提示词管理器实例"""
    return PromptManager()
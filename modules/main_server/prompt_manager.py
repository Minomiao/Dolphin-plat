import os
import json
from modules.logger import get_logger
from modules import bootstrap as app_paths

log = get_logger("Dolphin.prompt_manager")

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
        if not os.path.exists(app_paths.PROMPT_DIR):
            os.makedirs(app_paths.PROMPT_DIR)
            log.info(f"创建提示词目录: {app_paths.PROMPT_DIR}")
        
        # 初始化默认提示词
        if not os.path.exists(app_paths.PROMPT_FILE):
            self._create_default_prompts()
        
        # 加载提示词
        self.prompts = self._load_prompts()
        log.info(f"提示词管理器初始化完成，加载了 {len(self.prompts)} 个提示词")
    
    def _create_default_prompts(self):
        """创建默认提示词"""
        default_prompts = {
            "system": [
                "1. 角色定位：你是一个AI助手。当用户要求完成任务时，必须确保完成所有必要的步骤，不能中途停止。",
                "",
                "2. 工具调用限制：每次只能调用一个工具（skill），等待工具返回结果后，再决定是否需要调用下一个工具，不能同时调用多个工具。",
                "",
                "3. 输出格式要求：",
                "   - 每次回答结束时，必须至少给出一个正常的输出（除了思考过程和工具调用之外的内容），让用户知道发生了什么",
                "   - 始终以完整的回答结束对话",
                "   - 所有输出显示在终端中，使用纯文本格式表达",
                "   - 不能使用Markdown格式（如粗体、斜体、标题、列表、代码块、代码围栏、表格、引用等）",
                "   - 使用自然语言和空格缩进来表达结构和层级",
                "   - 不能输出表情符号（emoji）"
            ],
            "work_directory": [
                "4. 工作目录：",
                "   - 当前工作目录：{work_directory}",
                "   - 所有文件操作都在此目录下进行，可以使用子文件夹路径",
                "   - 如果需要切换工作目录，使用 file_manager 技能的 set_work_directory 函数",
                "   - 切换后的工作目录仅在当前对话有效"
            ],
            "directory_structure": [
                "   - 当前工作目录的文件结构：",
                "{directory_structure}"
            ]
        }

        with open(app_paths.PROMPT_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_prompts, f, ensure_ascii=False, indent=2)

        log.info(f"创建默认提示词文件: {app_paths.PROMPT_FILE}")

    def _load_prompts(self):
        """加载提示词，将数组格式的行合并为字符串"""
        try:
            with open(app_paths.PROMPT_FILE, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
            for key, value in prompts.items():
                if isinstance(value, list):
                    prompts[key] = "\n".join(value)
            return prompts
        except Exception as e:
            log.error(f"加载提示词失败: {e}")
            return {}
    
    def get_prompt(self, prompt_key, **kwargs):
        """获取单个提示词，支持 format 占位符替换"""
        prompt = self.prompts.get(prompt_key, "")
        if prompt and kwargs:
            try:
                prompt = prompt.format(**kwargs)
            except Exception as e:
                log.error(f"格式化提示词失败: {e}")
        return prompt

    # 努力程度提示词（动态注入，不持久化到 JSON）
    EFFORT_PROMPTS = {
        "fine": (
            "当前工作模式：精简。\n"
            "   - 只修改与任务直接相关的内容，不做额外改动\n"
            "   - 在每次修改前，审视：这个改动是否必要？能否以更少的代码完成？能否复用现有功能？能否使用系统已有的工具或方法？\n"
            "   - 完成后，确认修改范围没有超出任务要求"
        ),
        "medium": (
            "当前工作模式：标准。\n"
            "   - 如果遇到问题或任何不确定的情况，必须向用户询问确认，不要自行猜测\n"
            "   - 询问用户时，使用 plugin_user_input_request_user_input 工具"
        ),
        "high": (
            "当前工作模式：深度。\n"
            "   - 全面且完整地考虑每一个细节，不留遗漏\n"
            "   - 遇到任何不确定的情况，必须向用户询问确认\n"
            "   - 询问用户时，使用 plugin_user_input_request_user_input 工具\n"
            "   - 完成后仔细审视自己的工作，检查逻辑正确性、边界情况和潜在问题"
        ),
    }

    def compose_system_prompt(self, **kwargs):
        """组合完整的系统提示词 (system + effort + work_directory + directory_structure)"""
        effort_level = kwargs.pop("effort_level", "fine")
        effort_prompt = self.EFFORT_PROMPTS.get(effort_level, "")

        parts = [
            self.get_prompt("system"),
            self.get_prompt("work_directory", **kwargs),
            self.get_prompt("directory_structure", **kwargs),
            effort_prompt,
        ]
        return "\n\n".join(p for p in parts if p)

    def set_prompt(self, prompt_key, prompt_content):
        """设置提示词并持久化"""
        self.prompts[prompt_key] = prompt_content
        self._save_prompts()
        log.info(f"更新提示词: {prompt_key}")

    def _save_prompts(self):
        """保存提示词到 JSON 文件，拆分为数组格式提高可读性"""
        try:
            data = {}
            for key, value in self.prompts.items():
                data[key] = value.split("\n") if isinstance(value, str) else value
            with open(app_paths.PROMPT_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            log.debug(f"保存提示词到: {app_paths.PROMPT_FILE}")
        except Exception as e:
            log.error(f"保存提示词失败: {e}")

    def handle_request(self, request):
        """处理提示词请求，支持 prompt_request / get_prompt / set_prompt 三种类型"""
        request_type = request.get("type")

        if request_type == "prompt_request":
            # 来自 request_manager 的提示词拼接请求
            prompt_key = request.get("prompt_key")
            kwargs = request.get("kwargs", {})

            if prompt_key == "system":
                prompt = self.compose_system_prompt(**kwargs)
            else:
                prompt = self.get_prompt(prompt_key, **kwargs)

            return {
                "success": True,
                "prompt": prompt,
                "prompt_key": prompt_key
            }

        elif request_type == "get_prompt":
            prompt_key = request.get("prompt_key")
            if not prompt_key:
                return {"error": "缺少 prompt_key"}
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
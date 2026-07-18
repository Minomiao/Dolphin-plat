"""
技能加载器基类。
提供 SkillManager 和 PluginSkillLoader 共用的工具注册、参数校验、调用分发等通用逻辑。
"""
import inspect
import asyncio
import traceback
from typing import Dict, List, Any, Optional

from modules.logger import get_logger

log = get_logger("Dolphin.base_loader")


class BaseSkillLoader:
    """技能加载器基类。

    子类需实现：
        - _tool_prefix(): 工具名前缀，如 "skill_" 或 "plugin_"
        - _config_section(): 配置中启用/禁用的键名，如 "skills" 或 "plugins"
        - _load_skills(): 加载技能并填充 self.skills / self.failed_skills
    """

    def __init__(self):
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.failed_skills: Dict[str, str] = {}
        self._current_work_dir: Optional[str] = None

    # ===== 子类必须实现的抽象接口 =====

    def _tool_prefix(self) -> str:
        """返回工具名前缀（如 "skill_" 或 "plugin_"）。"""
        raise NotImplementedError

    def _config_section(self) -> str:
        """返回配置中启用/禁用的键名（如 "skills" 或 "plugins"）。"""
        raise NotImplementedError

    def _load_skills(self):
        """加载技能并填充 self.skills / self.failed_skills。"""
        raise NotImplementedError

    # ===== 通用逻辑 =====

    def set_work_dir(self, work_dir: str):
        """设置当前工作目录，供 SkillContext 注入使用。"""
        self._current_work_dir = work_dir

    def _get_default_work_dir(self) -> str:
        try:
            from modules.main_server import config
            return config.load_config().get('work_directory', 'workplace')
        except Exception as e:
            log.warning(f"获取默认工作目录失败: {e}")
            return 'workplace'

    def _resolve_skill_name(self, tool_name: str) -> Optional[tuple]:
        """从工具名解析出 (skill_name, func_name)。

        工具名格式为 {prefix}{skill_name}_{func_name}，其中 skill_name 可能包含下划线。
        """
        prefix = self._tool_prefix()
        if not tool_name.startswith(prefix):
            return None

        rest = tool_name[len(prefix):]
        parts = rest.split("_")
        if len(parts) < 2:
            return None

        for i in range(1, len(parts) + 1):
            possible_skill = "_".join(parts[:i])
            if possible_skill in self.skills:
                func_name = "_".join(parts[i:])
                return possible_skill, func_name
        return None

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """返回当前启用技能的所有工具定义。"""
        from modules.main_server import config
        config_section = config.load_config().get(self._config_section(), {})

        tools = []
        for skill_name, skill_info in self.skills.items():
            if not config_section.get(skill_name, True):
                continue

            if 'functions' in skill_info:
                for func_name, func_info in skill_info['functions'].items():
                    if 'callable' in func_info:
                        tools.append({
                            "type": "function",
                            "function": {
                                "name": f"{self._tool_prefix()}{skill_name}_{func_name}",
                                "description": func_info.get('description', ''),
                                "parameters": func_info.get('parameters', {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                })
                            }
                        })
        return tools

    def get_tool_names(self) -> List[str]:
        """返回所有工具名（不受启用状态过滤）。"""
        names = []
        for skill_name, skill_info in self.skills.items():
            if 'functions' in skill_info:
                for func_name in skill_info['functions'].keys():
                    names.append(f"{self._tool_prefix()}{skill_name}_{func_name}")
        return names

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用技能工具。"""
        log.info(f"调用技能工具: {tool_name}, 参数: {arguments}")
        prefix = self._tool_prefix()
        if not tool_name.startswith(prefix):
            log.error(f"工具名称格式错误: {tool_name}")
            raise ValueError(f"工具名称格式错误: {tool_name}")

        resolved = self._resolve_skill_name(tool_name)
        if resolved is None:
            log.error(f"找不到对应的技能: {tool_name}")
            raise ValueError(f"找不到对应的技能: {tool_name}")

        skill_name, func_name = resolved
        skill_info = self.skills[skill_name]

        if 'functions' not in skill_info or func_name not in skill_info['functions']:
            log.error(f"函数 {func_name} 在技能 {skill_name} 中不存在")
            raise ValueError(f"函数 {func_name} 在技能 {skill_name} 中不存在")

        func_info = skill_info['functions'][func_name]
        if 'callable' not in func_info:
            log.error(f"函数 {func_name} 不可调用")
            raise ValueError(f"函数 {func_name} 不可调用")

        # 检查必需参数
        required_params = []
        if 'parameters' in func_info and 'required' in func_info['parameters']:
            required_params = func_info['parameters']['required']

        missing_params = [p for p in required_params if p not in arguments]
        if missing_params:
            error_msg = f"缺少必需参数: {', '.join(missing_params)}"
            log.error(f"技能工具执行失败: {tool_name}, {error_msg}")
            return {"error": error_msg, "missing_parameters": missing_params}

        func = func_info['callable']
        try:
            sig = inspect.signature(func)
            if 'context' in sig.parameters:
                from .skill_context import create_default_context
                ctx = create_default_context(self._current_work_dir or self._get_default_work_dir())
                result = await asyncio.to_thread(func, context=ctx, **arguments)
            else:
                result = await asyncio.to_thread(func, **arguments)

            if asyncio.iscoroutine(result):
                result = await result

            log.debug(f"技能工具执行结果: {result}")
            return result
        except TypeError as e:
            log.error(f"技能工具 {tool_name} 参数类型错误: {e}\n{traceback.format_exc()}")
            return {"error": "参数类型错误，请检查调用参数格式"}
        except ValueError as e:
            log.error(f"技能工具 {tool_name} 参数值错误: {e}\n{traceback.format_exc()}")
            return {"error": "参数值错误，请检查调用参数"}
        except KeyError as e:
            log.error(f"技能工具 {tool_name} 缺少必需键: {e}\n{traceback.format_exc()}")
            return {"error": "缺少必需参数"}
        except ImportError as e:
            log.error(f"技能工具 {tool_name} 依赖加载失败: {e}\n{traceback.format_exc()}")
            return {"error": "工具所需依赖加载失败"}
        except Exception as e:
            log.error(f"技能工具执行失败: {tool_name}, 错误: {e}")
            log.debug(f"错误详情:\n{traceback.format_exc()}")
            return {"error": "工具执行过程中发生内部错误"}

    def list_failed_skills(self) -> Dict[str, str]:
        return self.failed_skills.copy()

    def reload_skills(self) -> Dict[str, Any]:
        """重新加载所有技能。"""
        self.skills.clear()
        self.failed_skills.clear()
        self._load_skills()
        return {
            "success": True,
            "loaded_count": len(self.skills),
            "failed_count": len(self.failed_skills),
            "failed_skills": list(self.failed_skills.keys())
        }

import os
import json
import importlib.util
from typing import Dict, List, Any, Callable, Optional
from pathlib import Path
from modules import logger

log = logger.get_logger("QuickAI.skill_manager")


class SkillManager:
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(exist_ok=True)
        self.skills: Dict[str, Dict[str, Any]] = {}
        self._load_skills()
        log.debug(f"初始化 SkillManager, 加载 {len(self.skills)} 个技能")
    
    def _load_skills(self):
        if not self.skills_dir.exists():
            log.debug("技能目录不存在")
            return
        
        for skill_folder in self.skills_dir.iterdir():
            if not skill_folder.is_dir() or skill_folder.name.startswith("_"):
                continue
            
            try:
                self._load_skill_folder(skill_folder)
            except Exception as e:
                log.error(f"加载技能 {skill_folder.name} 失败: {e}")
                print(f"加载技能 {skill_folder.name} 失败: {e}")
    
    def _load_skill_folder(self, skill_folder: Path):
        log.debug(f"加载技能文件夹: {skill_folder.name}")
        skill_file = skill_folder / "skill.py"
        init_file = skill_folder / "__init__.py"
        
        if not skill_file.exists():
            log.warning(f"技能文件不存在: {skill_file}")
            return
        
        spec = importlib.util.spec_from_file_location(
            f"skills.{skill_folder.name}.skill",
            skill_file
        )
        if spec is None or spec.loader is None:
            log.error(f"无法加载技能模块: {skill_folder.name}")
            return
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if hasattr(module, 'skill_info'):
            skill_info = module.skill_info
            
            if 'name' not in skill_info:
                skill_info['name'] = skill_folder.name
            
            if 'functions' in skill_info:
                for func_name, func_info in skill_info['functions'].items():
                    if hasattr(module, func_name):
                        func_info['callable'] = getattr(module, func_name)
            
            self.skills[skill_info['name']] = skill_info
            log.debug(f"技能加载成功: {skill_info['name']}")
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        tools = []
        from modules import config
        skills_config = config.load_config().get('skills', {})
        
        for skill_name, skill_info in self.skills.items():
            if not skills_config.get(skill_name, True):
                continue
                
            if 'functions' in skill_info:
                for func_name, func_info in skill_info['functions'].items():
                    if 'callable' in func_info:
                        tools.append({
                            "type": "function",
                            "function": {
                                "name": f"skill_{skill_name}_{func_name}",
                                "description": func_info.get('description', ''),
                                "parameters": func_info.get('parameters', {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                })
                            }
                        })
        return tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        log.info(f"调用技能工具: {tool_name}, 参数: {arguments}")
        if not tool_name.startswith("skill_"):
            log.error(f"工具名称格式错误: {tool_name}")
            raise ValueError(f"工具名称格式错误: {tool_name}")
        
        parts = tool_name.split("_")
        if len(parts) < 3:
            log.error(f"工具名称格式错误: {tool_name}")
            raise ValueError(f"工具名称格式错误: {tool_name}")
        
        skill_name = None
        func_name = None
        
        for i in range(1, len(parts)):
            possible_skill_name = "_".join(parts[1:i+1])
            if possible_skill_name in self.skills:
                skill_name = possible_skill_name
                func_name = "_".join(parts[i+1:])
                break
        
        if skill_name is None:
            log.error(f"找不到对应的技能: {tool_name}")
            raise ValueError(f"找不到对应的技能: {tool_name}")
        
        if skill_name not in self.skills:
            log.error(f"技能 {skill_name} 不存在")
            raise ValueError(f"技能 {skill_name} 不存在")
        
        skill_info = self.skills[skill_name]
        
        if 'functions' not in skill_info or func_name not in skill_info['functions']:
            log.error(f"函数 {func_name} 在技能 {skill_name} 中不存在")
            raise ValueError(f"函数 {func_name} 在技能 {skill_name} 中不存在")
        
        func_info = skill_info['functions'][func_name]
        
        if 'callable' not in func_info:
            log.error(f"函数 {func_name} 不可调用")
            raise ValueError(f"函数 {func_name} 不可调用")
        
        func = func_info['callable']
        
        try:
            result = func(**arguments)
            
            if asyncio.iscoroutine(result):
                result = await result
            
            log.debug(f"技能工具执行结果: {str(result)[:200]}{'...' if len(str(result)) > 200 else ''}")
            return result
        except Exception as e:
            log.error(f"技能工具执行失败: {tool_name}, 错误: {str(e)}")
            return {"error": str(e)}
    
    def get_tool_names(self) -> List[str]:
        names = []
        for skill_name, skill_info in self.skills.items():
            if 'functions' in skill_info:
                for func_name in skill_info['functions'].keys():
                    names.append(f"skill_{skill_name}_{func_name}")
        return names
    
    def list_skills(self) -> List[Dict[str, Any]]:
        from modules import config
        skills_config = config.load_config().get('skills', {})
        return [
            {
                "name": skill_name,
                "description": skill_info.get('description', ''),
                "functions": list(skill_info.get('functions', {}).keys()),
                "enabled": skills_config.get(skill_name, True)
            }
            for skill_name, skill_info in self.skills.items()
        ]
    
    def toggle_skill(self, skill_name: str, enabled: bool) -> Dict[str, Any]:
        from modules import config
        if skill_name not in self.skills:
            return {"error": f"技能不存在: {skill_name}"}
        
        current_config = config.load_config()
        if 'skills' not in current_config:
            current_config['skills'] = {}
        
        current_config['skills'][skill_name] = enabled
        config.save_config(current_config)
        
        return {
            "success": True,
            "skill": skill_name,
            "enabled": enabled,
            "message": f"技能 '{skill_name}' 已{'启用' if enabled else '禁用'}"
        }


import asyncio


_skill_manager = None


def get_skill_manager() -> SkillManager:
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager

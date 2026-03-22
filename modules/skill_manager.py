import os
import json
import importlib.util
import traceback
from typing import Dict, List, Any, Callable, Optional
from pathlib import Path
from modules import logger

log = logger.get_logger("Dolphin.skill_manager")


class SkillManager:
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.failed_skills: Dict[str, str] = {}
        self._load_skills()
        log.info(f"SkillManager 初始化完成: {len(self.skills)} 个技能加载成功, {len(self.failed_skills)} 个失败")
        if self.failed_skills:
            log.warning(f"加载失败的技能: {list(self.failed_skills.keys())}")
    
    def _load_skills(self):
        if not self.skills_dir.exists():
            log.info(f"技能目录不存在，创建目录: {self.skills_dir}")
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            return
        
        for skill_folder in self.skills_dir.iterdir():
            if not skill_folder.is_dir() or skill_folder.name.startswith("_"):
                continue
            
            try:
                self._load_skill_folder(skill_folder)
            except Exception as e:
                error_msg = f"{str(e)}"
                self.failed_skills[skill_folder.name] = error_msg
                log.error(f"加载技能 {skill_folder.name} 失败: {error_msg}")
                log.debug(f"错误详情:\n{traceback.format_exc()}")
    
    def _load_skill_folder(self, skill_folder: Path):
        log.debug(f"加载技能文件夹: {skill_folder.name}")
        skill_file = skill_folder / "skill.py"
        
        if not skill_file.exists():
            log.debug(f"跳过 {skill_folder.name}: 没有 skill.py 文件")
            return
        
        spec = importlib.util.spec_from_file_location(
            f"skills.{skill_folder.name}.skill",
            skill_file
        )
        if spec is None or spec.loader is None:
            log.warning(f"无法创建模块规范: {skill_folder.name}")
            return
        
        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            log.error(f"执行技能模块失败 {skill_folder.name}: {e}")
            raise
        
        if not hasattr(module, 'skill_info'):
            log.warning(f"技能 {skill_folder.name} 没有 skill_info 定义")
            return
        
        skill_info = module.skill_info
        
        if 'name' not in skill_info:
            skill_info['name'] = skill_folder.name
        
        if 'functions' in skill_info:
            for func_name, func_info in skill_info['functions'].items():
                if hasattr(module, func_name):
                    func_info['callable'] = getattr(module, func_name)
                else:
                    log.warning(f"技能 {skill_info['name']} 的函数 {func_name} 未找到")
        
        self.skills[skill_info['name']] = skill_info
        log.info(f"技能加载成功: {skill_info['name']}")
    
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
        
        # 检查必需参数
        required_params = []
        if 'parameters' in func_info and 'required' in func_info['parameters']:
            required_params = func_info['parameters']['required']
        
        # 检查是否缺少必需参数
        missing_params = []
        for param in required_params:
            if param not in arguments:
                missing_params.append(param)
        
        if missing_params:
            error_msg = f"缺少必需参数: {', '.join(missing_params)}"
            log.error(f"技能工具执行失败: {tool_name}, {error_msg}")
            return {"error": error_msg, "missing_parameters": missing_params}
        
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
    
    def list_failed_skills(self) -> Dict[str, str]:
        return self.failed_skills.copy()
    
    def reload_skills(self) -> Dict[str, Any]:
        self.skills.clear()
        self.failed_skills.clear()
        self._load_skills()
        return {
            "success": True,
            "loaded_count": len(self.skills),
            "failed_count": len(self.failed_skills),
            "failed_skills": list(self.failed_skills.keys())
        }
    
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

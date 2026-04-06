import os
import json
import importlib.util
import traceback
import zipfile
import tempfile
from typing import Dict, List, Any, Callable, Optional
from pathlib import Path
from modules import logger

log = logger.get_logger("Dolphin.plugin_skill_loader")


class PluginSkillLoader:
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.failed_skills: Dict[str, str] = {}
        log.info(f"PluginSkillLoader 初始化，插件目录: {self.plugins_dir}")
        self._load_skills()
        log.info(f"PluginSkillLoader 初始化完成: {len(self.skills)} 个插件技能加载成功, {len(self.failed_skills)} 个失败")
        if self.failed_skills:
            log.warning(f"加载失败的插件技能: {list(self.failed_skills.keys())}")
            for skill_name, error in self.failed_skills.items():
                log.warning(f"  - {skill_name}: {error}")
    
    def _load_skills(self):
        if not self.plugins_dir.exists():
            log.info(f"插件目录不存在，创建目录: {self.plugins_dir}")
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            return
        
        for zip_file in self.plugins_dir.iterdir():
            if not zip_file.is_file() or not zip_file.name.endswith('.zip'):
                continue
            
            try:
                self._load_skill_from_zip(zip_file)
            except Exception as e:
                error_msg = f"{str(e)}"
                self.failed_skills[zip_file.name] = error_msg
                log.error(f"加载插件技能压缩包 {zip_file.name} 失败: {error_msg}")
                log.debug(f"错误详情:\n{traceback.format_exc()}")
    
    def _load_skill_from_zip(self, zip_file: Path):
        log.debug(f"加载插件技能压缩包: {zip_file.name}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(temp_dir)
            
            temp_path = Path(temp_dir)
            
            # 首先尝试读取 manifest.json
            manifest_file = temp_path / 'manifest.json'
            if manifest_file.exists():
                try:
                    self._load_skill_with_manifest(temp_path, manifest_file, zip_file.name)
                    return
                except Exception as e:
                    log.warning(f"使用 manifest.json 加载失败，尝试旧方式: {e}")
            
            # 如果没有 manifest.json 或加载失败，使用旧的方式
            for root, dirs, files in os.walk(temp_path):
                if 'skill.py' in files:
                    skill_file = Path(root) / 'skill.py'
                    skill_folder_name = Path(root).name
                    
                    try:
                        self._load_skill_file(skill_file, skill_folder_name)
                    except Exception as e:
                        log.error(f"执行插件技能模块失败 {skill_folder_name}: {e}")
                        raise
                    break
    
    def _load_skill_with_manifest(self, temp_path: Path, manifest_file: Path, zip_name: str):
        """使用 manifest.json 加载技能"""
        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"manifest.json 格式错误: {e}")
        
        # 验证 manifest 结构
        if 'main' not in manifest:
            raise ValueError("manifest.json 缺少 'main' 字段")
        
        main_config = manifest['main']
        entry_point = main_config.get('entry_point', 'skill/skill.py')
        
        # 定位 skill.py 文件
        skill_file = temp_path / entry_point
        if not skill_file.exists():
            raise ValueError(f"入口文件不存在: {entry_point}")
        
        # 从 manifest 中获取技能信息
        skill_info_manifest = manifest.get('skill_info', {})
        skill_name = skill_info_manifest.get('name', Path(zip_name).stem)
        skill_version = skill_info_manifest.get('version', '1.0.0')
        
        # 加载技能文件
        self._load_skill_file(skill_file, skill_name, skill_version, skill_info_manifest)
    
    def _load_skill_file(self, skill_file: Path, skill_name: str, skill_version: str = '1.0.0', skill_info_from_manifest: dict = None):
        spec = importlib.util.spec_from_file_location(
            f"plugins.{skill_name}.skill",
            skill_file
        )
        if spec is None or spec.loader is None:
            log.warning(f"无法创建模块规范: {skill_name}")
            return
        
        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            log.error(f"执行插件技能模块失败 {skill_name}: {e}")
            raise
        
        # 优先使用从 manifest 加载的技能信息
        if skill_info_from_manifest:
            skill_info = skill_info_from_manifest
            log.info(f"从 manifest.json 加载技能信息: {skill_name}")
        elif hasattr(module, 'skill_info'):
            skill_info = module.skill_info
            log.info(f"从模块加载技能信息: {skill_name}")
        else:
            log.warning(f"插件技能 {skill_name} 没有 skill_info 定义")
            return
        
        if 'name' not in skill_info:
            skill_info['name'] = skill_name
        
        # 添加版本信息
        if 'version' not in skill_info:
            skill_info['version'] = skill_version
        
        if 'functions' in skill_info:
            for func_name, func_info in skill_info['functions'].items():
                if hasattr(module, func_name):
                    func_info['callable'] = getattr(module, func_name)
                else:
                    log.warning(f"插件技能 {skill_info['name']} 的函数 {func_name} 未找到")
        
        self.skills[skill_info['name']] = skill_info
        log.info(f"插件技能加载成功: {skill_info['name']} (版本: {skill_info['version']})")
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        tools = []
        from modules import config
        plugins_config = config.load_config().get('plugins', {})
        
        for skill_name, skill_info in self.skills.items():
            if not plugins_config.get(skill_name, True):
                continue
                
            if 'functions' in skill_info:
                for func_name, func_info in skill_info['functions'].items():
                    if 'callable' in func_info:
                        tools.append({
                            "type": "function",
                            "function": {
                                "name": f"plugin_{skill_name}_{func_name}",
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
        log.info(f"调用插件技能工具: {tool_name}, 参数: {arguments}")
        if not tool_name.startswith("plugin_"):
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
            # 检查是否有 "plugin-" 前缀
            if possible_skill_name.startswith("plugin-"):
                possible_skill_name = possible_skill_name[8:]
            if possible_skill_name in self.skills:
                skill_name = possible_skill_name
                func_name = "_".join(parts[i+1:])
                break
        
        if skill_name is None:
            log.error(f"找不到对应的插件技能: {tool_name}")
            raise ValueError(f"找不到对应的插件技能: {tool_name}")
        
        if skill_name not in self.skills:
            log.error(f"插件技能 {skill_name} 不存在")
            raise ValueError(f"插件技能 {skill_name} 不存在")
        
        skill_info = self.skills[skill_name]
        
        if 'functions' not in skill_info or func_name not in skill_info['functions']:
            log.error(f"函数 {func_name} 在插件技能 {skill_name} 中不存在")
            raise ValueError(f"函数 {func_name} 在插件技能 {skill_name} 中不存在")
        
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
            log.error(f"插件技能工具执行失败: {tool_name}, {error_msg}")
            return {"error": error_msg, "missing_parameters": missing_params}
        
        try:
            result = func(**arguments)
            
            if asyncio.iscoroutine(result):
                result = await result
            
            log.debug(f"插件技能工具执行结果: {result}")
            return result
        except Exception as e:
            log.error(f"插件技能工具执行失败: {tool_name}, 错误: {str(e)}")
            return {"error": str(e)}
    
    def get_tool_names(self) -> List[str]:
        names = []
        for skill_name, skill_info in self.skills.items():
            if 'functions' in skill_info:
                for func_name in skill_info['functions'].keys():
                    names.append(f"plugin_{skill_name}_{func_name}")
        return names
    
    def list_skills(self) -> List[Dict[str, Any]]:
        from modules import config
        plugins_config = config.load_config().get('plugins', {})
        return [
            {
                "name": f"plugin-{skill_name}",
                "description": skill_info.get('description', ''),
                "version": skill_info.get('version', '1.0.0'),
                "functions": list(skill_info.get('functions', {}).keys()),
                "enabled": plugins_config.get(skill_name, True)
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
        
        # 移除 "plugin-" 前缀
        if skill_name.startswith("plugin-"):
            original_skill_name = skill_name[8:]
        else:
            original_skill_name = skill_name
        
        if original_skill_name not in self.skills:
            return {"error": f"插件技能不存在: {skill_name}"}
        
        current_config = config.load_config()
        if 'plugins' not in current_config:
            current_config['plugins'] = {}
        
        current_config['plugins'][original_skill_name] = enabled
        config.save_config(current_config)
        
        return {
            "success": True,
            "skill": skill_name,
            "enabled": enabled,
            "message": f"插件技能 '{skill_name}' 已{'启用' if enabled else '禁用'}"
        }


import asyncio


_plugin_skill_loader = None


def get_plugin_skill_loader() -> PluginSkillLoader:
    global _plugin_skill_loader
    if _plugin_skill_loader is None:
        _plugin_skill_loader = PluginSkillLoader()
    return _plugin_skill_loader
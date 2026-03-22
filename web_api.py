from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from modules import config
from modules import commands as cmd
from modules.chat import QuickAIChat
from modules import logger
import json

log = logger.setup_logger("Dolphin-Web")

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

chat_instance = None

def _complete_incomplete_tool_calls(messages, reason="对话被截断"):
    """补完不完整的 tool_calls 消息，让 AI 知道对话被截断"""
    result = list(messages)
    i = 0
    while i < len(result):
        msg = result[i]
        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
            tool_call_ids = {tc.get('id') for tc in msg.get('tool_calls', [])}
            responded_ids = set()
            for j in range(i + 1, len(result)):
                if result[j].get('role') == 'tool':
                    if result[j].get('tool_call_id') in tool_call_ids:
                        responded_ids.add(result[j].get('tool_call_id'))
            
            missing_ids = tool_call_ids - responded_ids
            if missing_ids:
                for tc_id in missing_ids:
                    result.append({
                        "tool_call_id": tc_id,
                        "role": "tool",
                        "content": json.dumps({"error": f"操作未完成: {reason}", "reason": reason}, ensure_ascii=False)
                    })
        i += 1
    return result

def init_chat():
    global chat_instance
    current_config = config.load_config()
    print(f"加载配置: api_key={current_config.get('api_key', '')[:10]}..., base_url={current_config.get('base_url')}")
    chat_instance = QuickAIChat(
        model=current_config.get('model', 'deepseek-chat'),
        max_tokens=current_config.get('max_tokens', 8192)
    )
    log.info("Chat instance initialized")

@app.route('/api/config', methods=['GET'])
def get_config():
    current_config = config.load_config()
    all_skills = {}
    skills_list = chat_instance.skill_mgr.list_skills()
    for skill in skills_list:
        skill_name = skill['name']
        all_skills[skill_name] = current_config.get('skills', {}).get(skill_name, True)
    
    return jsonify({
        'model': current_config.get('model', 'deepseek-chat'),
        'max_tokens': current_config.get('max_tokens', 8192),
        'work_directory': current_config.get('work_directory', 'workplace'),
        'base_url': current_config.get('base_url', 'https://api.deepseek.com'),
        'reasoning': current_config.get('reasoning', False),
        'skills': all_skills
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    current_config = config.load_config()
    
    if 'model' in data:
        current_config['model'] = data['model']
    if 'max_tokens' in data:
        current_config['max_tokens'] = data['max_tokens']
    if 'work_directory' in data:
        current_config['work_directory'] = data['work_directory']
    if 'base_url' in data:
        current_config['base_url'] = data['base_url']
    if 'reasoning' in data:
        current_config['reasoning'] = data['reasoning']
    if 'skills' in data:
        current_config['skills'] = data['skills']
    
    config.save_config(current_config)
    init_chat()
    
    return jsonify({'status': 'ok', 'message': '配置已更新', 'config': current_config})

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    user_input = data.get('message', '').strip()
    
    if not user_input:
        return jsonify({'error': '消息不能为空'}), 400
    
    log.info(f"收到消息: {user_input[:50]}...")
    
    def generate():
        if user_input == cmd.get_command('clear'):
            chat_instance.messages = []
            log.info("历史记录已清空")
            yield f"data: {json.dumps({'type': 'system', 'content': '历史记录已清空'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        elif user_input == cmd.get_command('help'):
            commands_config = cmd.load_commands()
            cmd_list = commands_config.get("commands", {})
            help_text = "=== 命令帮助 ===\n"
            for cmd_key, cmd_info in cmd_list.items():
                cmd_input = cmd_info.get("input", "")
                cmd_description = cmd_info.get("description", "")
                help_text += f"{cmd_input:<12} - {cmd_description}\n"
            help_text += "\n输入任何其他内容将发送给AI"
            yield f"data: {json.dumps({'type': 'system', 'content': help_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        elif user_input == cmd.get_command('tools'):
            tools = chat_instance.list_available_tools() if hasattr(chat_instance, 'list_available_tools') else []
            if tools:
                tools_text = "=== 可用工具 ===\n"
                for tool in tools:
                    tools_text += f"  - {tool['name']}\n"
                    tools_text += f"    {tool['description']}\n"
            else:
                tools_text = "没有可用的工具"
            yield f"data: {json.dumps({'type': 'system', 'content': tools_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        elif user_input == cmd.get_command('skills'):
            skills = chat_instance.skill_mgr.list_skills()
            if skills:
                skills_text = "=== 可用技能 ===\n"
                for skill in skills:
                    status = "启用" if skill.get('enabled', True) else "禁用"
                    skills_text += f"  - {skill['name']} [{status}]\n"
                    skills_text += f"    {skill['description']}\n"
            else:
                skills_text = "没有可用的技能"
            yield f"data: {json.dumps({'type': 'system', 'content': skills_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        elif user_input == cmd.get_command('toggle'):
            current_status = chat_instance.enable_tools
            new_status = not current_status
            chat_instance.enable_tool(new_status)
            status_text = "启用" if new_status else "禁用"
            yield f"data: {json.dumps({'type': 'system', 'content': f'工具已{status_text}'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        elif user_input == cmd.get_command('set'):
            current_config = config.load_config()
            set_text = "=== 设置模式 ===\n"
            set_text += f"当前配置:\n"
            set_text += f"模型: {current_config.get('model', 'deepseek-chat')}\n"
            set_text += f"工作目录: {current_config.get('work_directory', 'workplace')}\n"
            set_text += f"最大Token数: {current_config.get('max_tokens', 8192)}\n"
            set_text += "\nWeb版本暂不支持交互式设置，请直接修改配置文件。"
            yield f"data: {json.dumps({'type': 'system', 'content': set_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return
        
        try:
            system_message = "你是一个AI助手。当用户要求完成任务时，必须确保完成所有必要的步骤，不要中途停止。重要限制：每次只能调用一个工具（skill），等待工具返回结果后，再决定是否需要调用下一个工具。不要同时调用多个工具。重要：在每次回答结束时，必须至少给出一个正常的输出（除了思考过程和工具调用之外的内容），让用户知道发生了什么。始终以完整的回答结束对话。"
            kwargs = {
                "model": chat_instance.model,
                "messages": [{"role": "system", "content": system_message}] + chat_instance.messages + [{"role": "user", "content": user_input}],
                "temperature": chat_instance.temperature,
                "max_tokens": chat_instance.max_tokens,
                "stream": True
            }
            
            if chat_instance.tools:
                kwargs["tools"] = chat_instance.tools
            
            max_iterations = 10
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                log.info(f"开始流式响应 (迭代 {iteration}/{max_iterations}): model={chat_instance.model}, messages={len(kwargs['messages'])}")
                stream = chat_instance.client.chat.completions.create(**kwargs)
                full_response = ""
                full_reasoning = ""
                chunk_count = 0
                tool_calls_buffer = {}
                reasoning_started = False
                response_started = False
                has_tool_calls = False
                
                for chunk in stream:
                    chunk_count += 1
                    delta = chunk.choices[0].delta
                    if chunk_count <= 3:
                        log.info(f"Chunk {chunk_count}: delta={delta}")
                    
                    content = None
                    if hasattr(delta, 'content') and delta.content:
                        content = delta.content
                    elif hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        content = delta.reasoning_content
                    
                    if content:
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                            if not reasoning_started:
                                reasoning_started = True
                            full_reasoning += content
                        else:
                            full_response += content
                            response_started = True
                        if chunk_count <= 3:
                            log.debug(f"发送 chunk {chunk_count}: {content[:20]}...")
                        yield f"data: {json.dumps({'type': 'assistant', 'content': content}, ensure_ascii=False)}\n\n"
                    
                    if delta.tool_calls:
                        has_tool_calls = True
                        for tc in delta.tool_calls:
                            if tc.index not in tool_calls_buffer:
                                tool_calls_buffer[tc.index] = {
                                    "id": tc.id,
                                    "type": tc.type,
                                    "function": {
                                        "name": tc.function.name if tc.function.name else "",
                                        "arguments": tc.function.arguments if tc.function.arguments else ""
                                    }
                                }
                            else:
                                if tc.function.name:
                                    tool_calls_buffer[tc.index]["function"]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_buffer[tc.index]["function"]["arguments"] += tc.function.arguments
                
                log.info(f"流式响应完成: 共 {chunk_count} 个 chunk, 总长度 {len(full_response)}, 工具调用={has_tool_calls}")
                
                if has_tool_calls and tool_calls_buffer:
                    tool_calls = list(tool_calls_buffer.values())
                    log.info(f"检测到 {len(tool_calls)} 个工具调用")
                    
                    chat_instance.add_message("user", user_input)
                    chat_instance.add_message("assistant", full_response or "", tool_calls, reasoning_content=full_reasoning)
                    
                    yield f"data: {json.dumps({'type': 'system', 'content': f'\n\n工具调用 ({len(tool_calls)}):'}, ensure_ascii=False)}\n\n"
                    
                    needs_confirmation = False
                    for tc in tool_calls:
                        tool_name = tc['function']['name']
                        tool_call_id = tc['id']
                        try:
                            arguments = json.loads(tc['function']['arguments'])
                        except:
                            arguments = {}
                        
                        yield f"data: {json.dumps({'type': 'system', 'content': f'\n  执行: {tool_name}'}, ensure_ascii=False)}\n\n"
                        
                        result = chat_instance._execute_tool_sync(tool_name, arguments)
                        
                        if isinstance(result, dict):
                            if result.get('requires_confirmation'):
                                needs_confirmation = True
                                yield f"data: {json.dumps({'type': 'system', 'content': f'  ⚠️ 需要确认: {result.get("message", "")}'}, ensure_ascii=False)}\n\n"
                                yield f"data: {json.dumps({'type': 'system', 'content': '  [Web版本不支持交互式确认，请使用命令行版本或修改文件路径到工作目录内]'}, ensure_ascii=False)}\n\n"
                            elif result.get('success'):
                                yield f"data: {json.dumps({'type': 'system', 'content': f'  ✓ 成功: {result.get("message", "")}'}, ensure_ascii=False)}\n\n"
                            elif 'error' in result:
                                yield f"data: {json.dumps({'type': 'error', 'content': f'  ✗ 错误: {result["error"]}'}, ensure_ascii=False)}\n\n"
                        
                        tool_content = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
                        chat_instance.messages.append({
                            "tool_call_id": tool_call_id,
                            "role": "tool",
                            "content": tool_content
                        })
                    
                    if needs_confirmation:
                        yield f"data: {json.dumps({'type': 'system', 'content': '\n[操作需要确认，对话已暂停。请使用命令行版本进行此操作，或确保文件路径在工作目录内。]'}, ensure_ascii=False)}\n\n"
                        chat_instance.messages = _complete_incomplete_tool_calls(chat_instance.messages, "操作需要用户确认，但Web版本不支持交互式确认")
                        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                        break
                    
                    kwargs["messages"] = [{"role": "system", "content": system_message}] + chat_instance.messages
                    continue
                else:
                    chat_instance.add_message("user", user_input)
                    chat_instance.add_message("assistant", full_response, reasoning_content=full_reasoning)
                    break
            
            if iteration >= max_iterations:
                yield f"data: {json.dumps({'type': 'system', 'content': '\n[已达到最大对话轮数限制(10轮)，对话已结束]'}, ensure_ascii=False)}\n\n"
                chat_instance.messages = _complete_incomplete_tool_calls(chat_instance.messages, "已达到最大对话轮数限制(10轮)")
            
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"聊天错误: {str(e)}")
            print(error_trace)
            log.error(f"聊天错误: {str(e)}")
            log.error(error_trace)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
    
    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/api/commands', methods=['GET'])
def get_commands():
    commands_config = cmd.load_commands()
    return jsonify(commands_config.get('commands', {}))

@app.route('/api/tools', methods=['GET'])
def get_tools():
    tools = chat_instance.skill_mgr.get_all_tools() if chat_instance else []
    return jsonify(tools)

@app.route('/api/skills', methods=['GET'])
def get_skills():
    skills = chat_instance.skill_mgr.list_skills() if chat_instance else []
    return jsonify(skills)

@app.route('/api/clear', methods=['POST'])
def clear_conversation():
    chat_instance.messages = []
    log.info("对话已清空")
    return jsonify({'status': 'ok', 'message': '对话已清空'})

@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    init_chat()
    app.run(host='0.0.0.0', port=5000, debug=True)

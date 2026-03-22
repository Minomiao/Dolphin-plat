import os
import json
from dotenv import load_dotenv
from openai import OpenAI

CONFIG_FILE = "config.json"
COMMANDS_FILE = "commands.json"
DATE_DIR = "date"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "api_key": os.getenv("QUICKAI_API_KEY", ""),
        "base_url": os.getenv("QUICKAI_BASE_URL", "https://api.deepseek.com"),
        "model": "deepseek-chat"
    }

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_commands():
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "commands": {
            "set": {
                "input": ".set",
                "description": "进入设置模式"
            },
            "back": {
                "input": ".back",
                "description": "返回 (在设置模式中使用)"
            },
            "help": {
                "input": ".help",
                "description": "显示此帮助信息"
            },
            "quit": {
                "input": ".quit",
                "description": "退出程序"
            },
            "clear": {
                "input": ".clear",
                "description": "清空对话历史"
            },
            "new": {
                "input": ".new",
                "description": "开启新对话"
            },
            "load": {
                "input": ".load",
                "description": "加载旧对话"
            },
            "save_as": {
                "input": ".save as",
                "description": "保存对话"
            },
            "list": {
                "input": ".list",
                "description": "查看所有对话"
            }
        }
    }

def save_commands(commands):
    with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(commands, f, ensure_ascii=False, indent=2)

def get_command(cmd_key):
    commands = load_commands()
    cmd_list = commands.get("commands", {})
    if cmd_key in cmd_list:
        return cmd_list[cmd_key].get("input", f".{cmd_key}")
    return f".{cmd_key}"

def get_command_description(cmd_key):
    commands = load_commands()
    cmd_list = commands.get("commands", {})
    if cmd_key in cmd_list:
        return cmd_list[cmd_key].get("description", "")
    return ""

config = load_config()
commands = load_commands()
client = OpenAI(
    api_key=config.get("api_key"),
    base_url=config.get("base_url", "https://api.deepseek.com")
)

class DolphinChat:
    def __init__(self, model="deepseek-chat", temperature=0.7, max_tokens=2000):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.messages = []
    
    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})
    
    def chat(self, user_input):
        self.add_message("user", user_input)
        response = client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        assistant_message = response.choices[0].message.content
        self.add_message("assistant", assistant_message)
        return assistant_message
    
    def chat_stream(self, user_input):
        self.add_message("user", user_input)
        stream = client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True
        )
        full_response = ""
        print("Dolphin: ", end="", flush=True)
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_response += content
        print()
        self.add_message("assistant", full_response)
        return full_response
    
    def clear_history(self):
        self.messages = []
    
    def save_conversation(self, name):
        if not os.path.exists(DATE_DIR):
            os.makedirs(DATE_DIR)
        filepath = os.path.join(DATE_DIR, f"{name}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)
    
    def load_conversation(self, name):
        filepath = os.path.join(DATE_DIR, f"{name}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                self.messages = json.load(f)
            return True
        return False
    
    def list_conversations(self):
        if not os.path.exists(DATE_DIR):
            return []
        conversations = []
        for filename in os.listdir(DATE_DIR):
            if filename.endswith('.json'):
                conversations.append(filename[:-5])
        return conversations

def settings_mode():
    global config, client, chat, commands
    print("\n=== 设置模式 ===")
    print(f"输入 '{get_command('back')}' 返回主界面")
    print("当前配置:")
    print(f"API密钥: {'***' if config.get('api_key') else '未设置'}")
    print(f"模型: {config.get('model', 'deepseek-chat')}")
    print("\n输入新的配置 (留空保持当前值):")
    
    new_api_key = input("API密钥: ")
    if new_api_key == get_command('back'):
        print("返回主界面")
        return
    new_api_key = new_api_key or config.get('api_key')
    
    print("\n可用模型:")
    print("1. deepseek-chat")
    print("2. deepseek-coder")
    print("3. gpt-3.5-turbo")
    print("4. gpt-4")
    print("5. 自定义模型")
    
    model_choice = input("\n请选择模型 (1-5): ")
    if model_choice == get_command('back'):
        print("返回主界面")
        return
    
    model_map = {
        "1": "deepseek-chat",
        "2": "deepseek-coder",
        "3": "gpt-3.5-turbo",
        "4": "gpt-4"
    }
    
    if model_choice in model_map:
        new_model = model_map[model_choice]
    elif model_choice == "5":
        new_model = input("请输入自定义模型名称: ")
        if new_model == get_command('back'):
            print("返回主界面")
            return
        new_model = new_model or config.get('model', 'deepseek-chat')
    else:
        print("无效选择，保持当前模型")
        new_model = config.get('model', 'deepseek-chat')
    
    print("\n是否要修改命令配置? (y/n)")
    modify_commands = input().lower()
    if modify_commands == 'y':
        for cmd_key in cmd_list.keys():
            current_input = cmd_list[cmd_key].get('input', '')
            new_input = input(f"{cmd_key} 命令输入 (当前: {current_input}): ")
            if new_input == get_command('back'):
                print("返回主界面")
                return
            if new_input:
                commands["commands"][cmd_key]["input"] = new_input
    
    config['api_key'] = new_api_key
    config['model'] = new_model
    
    save_config(config)
    save_commands(commands)
    print("\n配置已保存")
    
    global client
    client = OpenAI(
        api_key=config.get("api_key"),
        base_url=config.get("base_url")
    )
    chat = DolphinChat(model=config.get('model'))
    print("客户端已更新")

def show_help():
    commands = load_commands()
    cmd_list = commands.get("commands", {})
    
    print("\n=== 命令帮助 ===")
    for cmd_key, cmd_info in cmd_list.items():
        cmd_input = cmd_info.get("input", "")
        cmd_description = cmd_info.get("description", "")
        print(f"{cmd_input:<12} - {cmd_description}")
    print("\n输入任何其他内容将发送给AI")

if __name__ == "__main__":
    chat = DolphinChat(model=config.get('model', 'deepseek-chat'))
    current_conversation = "main"
    
    print("Dolphin 聊天助手")
    print(f"输入 '{get_command('help')}' 获取命令帮助")
    print("=" * 50)
    
    while True:
        user_input = input("\n您: ")
        
        if user_input == get_command('quit'):
            print("再见!")
            break
        elif user_input == get_command('clear'):
            chat.clear_history()
            print("历史记录已清空")
            continue
        elif user_input == get_command('set'):
            settings_mode()
            continue
        elif user_input == get_command('help'):
            show_help()
            continue
        elif user_input == get_command('new'):
            new_name = input("请输入新对话名称: ")
            if new_name:
                if current_conversation == "main" and chat.messages:
                    save_choice = input("是否保存当前main对话? (y/n): ").lower()
                    if save_choice == 'y':
                        save_name = input("请输入保存名称: ") or current_conversation
                        chat.save_conversation(save_name)
                        print(f"对话已保存为: {save_name}")
                chat.clear_history()
                current_conversation = new_name
                print(f"已切换到新对话: {new_name}")
            continue
        elif user_input == get_command('load'):
            load_name = input("请输入要加载的对话名称: ")
            if load_name:
                if chat.load_conversation(load_name):
                    current_conversation = load_name
                    print(f"已加载对话: {load_name}")
                else:
                    print(f"对话 '{load_name}' 不存在")
            continue
        elif user_input == get_command('save_as'):
            save_name = input("请输入保存名称: ")
            if save_name:
                chat.save_conversation(save_name)
                print(f"对话已保存为: {save_name}")
                if current_conversation == "main":
                    chat.clear_history()
                    print("main对话已清空")
                else:
                    current_conversation = "main"
                    print("已切换到main对话")
            continue
        elif user_input == get_command('list'):
            conversations = chat.list_conversations()
            if conversations:
                print("\n=== 所有对话 ===")
                for conv in conversations:
                    print(f"  - {conv}")
            else:
                print("没有找到任何对话")
            continue
        
        chat.chat_stream(user_input)

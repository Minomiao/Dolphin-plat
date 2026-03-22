import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("QUICKAI_API_KEY"),
    base_url=os.getenv("QUICKAI_BASE_URL", "https://api.deepseek.com")
)

def chat_with_dolphin(prompt, model="deepseek-chat", temperature=0.7, max_tokens=2000):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def chat_with_history(messages, model="deepseek-chat", temperature=0.7, max_tokens=2000):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    user_input = input("请输入您的问题: ")
    response = chat_with_dolphin(user_input)
    print(f"\nDolphin 回复:\n{response}")

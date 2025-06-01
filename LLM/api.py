import os
from openai import OpenAI
from dotenv import load_dotenv

class TongYiAPI:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # 使用阿里云通义千问的配置
        self.model = os.getenv("model_name", "qwen-plus")  # 默认使用qwen-plus模型
        self.api_key = os.getenv("api_key")  # 使用阿里云API Key
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        
        if not self.api_key:
            raise ValueError("请设置DASHSCOPE_API_KEY环境变量")
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def chat(self, prompt, content, max_token=1024, temperature=0.7, response_format="json_object"):
        """
        使用通义千问API进行对话，支持JSON格式输出
        :param prompt: 系统提示词
        :param content: 用户输入内容
        :param max_token: 最大输出token数
        :param temperature: 温度参数，控制输出的随机性
        :param response_format: 响应格式，可选 "json_object" 或 None
        :return: 模型响应内容
        """
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ]
        
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_token,
            "temperature": temperature,
            "stream": False
        }
        
        if response_format == "json_object":
            params["response_format"] = {"type": "json_object"}
            
        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content
    
    def chat_without_json(self, prompt, content, max_token=1024, temperature=0.7):
        """
        使用通义千问API进行对话，返回普通文本格式
        :param prompt: 系统提示词
        :param content: 用户输入内容
        :param max_token: 最大输出token数
        :param temperature: 温度参数，控制输出的随机性
        :return: 模型响应内容
        """
        return self.chat(prompt, content, max_token, temperature, response_format=None)

if __name__ == "__main__":
    api = TongYiAPI()
    # 测试普通对话
    response = api.chat_without_json(
        "你是一个专业的小说创作者",
        "完成一篇关于明朝赤脚医生救死扶伤的小说"
    )
    print("普通对话响应:", response)
    
    # 测试JSON格式对话
    json_response = api.chat(
        "你是一个JSON格式的助手",
        "给我一个包含标题和内容的小说大纲",
    )
    print("JSON格式响应:", json_response)
    
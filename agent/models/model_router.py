import os

os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import warnings

warnings.filterwarnings('ignore')

import re
import json
import logging
from typing import List, Dict, Any
from datetime import datetime

import instructor
from agent.schemas.travel_plan import FinalTravelPlan
from openai import OpenAI  # 使用官方的OpenAI客户端
import google.generativeai as genai  # 使用官方的Gemini客户端

logging.getLogger('google.generativeai').setLevel(logging.ERROR)


class ModelRouter:
    def __init__(self):
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 配置完整路径
        config_path = os.path.join(current_dir, "..", "config", "model_config.json")
        self.config_path = os.path.abspath(config_path)

        with open(self.config_path) as f:
            self.config = json.load(f)

        self.model_instances = {
            "gpt4o": self._init_openai_model("gpt4o"),
            "gpt-5-chat": self._init_openai_model("gpt-5-chat"),
            "gpt4o-mini": self._init_openai_model("gpt4o-mini"),
            "claude-sonnet-4-5-20250929": self._init_openai_model("claude-sonnet-4-5-20250929"),
            "gemini-2.0-flash": self._init_gemini("gemini-2.0-flash"),
            "deepseek-chat": self._init_openai_compatible("deepseek-chat"),
            "qwen3-8b": self._init_qwen("qwen3-8b"),
            "open-mistral-7b": self._init_openai_compatible("open-mistral-7b")
        }

    # ===================== 动态添加自定义模型 =====================
    def add_custom_model(self, model_key: str, model_type: str, cfg: dict):
        """
        动态添加自定义模型
        :param model_key: 模型名称（用户自定义）
        :param model_type: 类型：openai / qwen / gemini
        :param cfg: 配置：api_key, base_url, model_name, temperature, max_tokens
        """
        if model_type == "openai":
            fn = self._build_openai_call(cfg)
        elif model_type == "qwen":
            fn = self._build_qwen_call(cfg)
        elif model_type == "gemini":
            fn = self._build_gemini_call(cfg)
        else:
            raise ValueError("不支持的模型类型：openai / qwen / gemini")

        self.model_instances[model_key] = fn

    # 动态构造模型调用函数
    def _build_openai_call(self, cfg):
        def call(messages):
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg.get("base_url", ""))
            response = client.chat.completions.create(
                model=cfg["model_name"], messages=messages,
                temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
            self._save_token_usage(cfg["model_name"], response.usage.dict() if hasattr(response, 'usage') else {})
            return response.choices[0].message.content

        return call

    def _build_qwen_call(self, cfg):
        def call(messages):
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg.get("base_url", ""))
            response = client.chat.completions.create(
                model=cfg["model_name"], messages=messages,
                extra_body={"enable_thinking": False}, stream=False,
                temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
            self._save_token_usage(cfg["model_name"], response.usage.dict() if hasattr(response, 'usage') else {})
            return response.choices[0].message.content

        return call

    def _build_gemini_call(self, cfg):
        def call(messages):
            client = OpenAI(api_key=cfg["api_key"], base_url=cfg.get("base_url", ""))
            response = client.chat.completions.create(
                model=cfg["model_name"], messages=messages,
                temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
            self._save_token_usage(cfg["model_name"], response.usage.dict() if hasattr(response, 'usage') else {})
            return response.choices[0].message.content

        return call

    def _save_token_usage(self, model_name: str, usage_data: dict, filename_suffix: str = None):
        """保存token使用情况到JSON文件"""
        try:
            # 创建token目录
            token_dir = os.path.join("agent", "token_usage")
            os.makedirs(token_dir, exist_ok=True)

            # 生成文件名
            filename = f"{model_name}_tokens.json"
            file_path = os.path.join(token_dir, filename)

            # 准备保存的数据
            token_data = {
                "model": model_name,
                "query_uid": filename_suffix,
                "timestamp": datetime.now().isoformat(),
                "usage": usage_data,
                "total_tokens": usage_data.get("total_tokens", 0),
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0)
            }

            # 保存到文件
            if os.path.exists(file_path):
                # 读取现有数据
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                # 如果现有数据不是列表，则将其转换为列表
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
                # 追加新的数据
                existing_data.append(token_data)
                # 保存到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, ensure_ascii=False, indent=2)
            else:
                # 保存到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump([token_data], f, ensure_ascii=False, indent=2)

            print(f"💾 Token使用情况已保存到: {file_path}")
            return file_path

        except Exception as e:
            print(f"❌ 保存token使用情况失败: {e}")
            return None

    def _extract_query_uid(self, messages: List[Dict[str, str]]) -> str:
        """从消息中提取查询ID"""
        try:
            if messages and len(messages) > 0:
                # 查找用户消息中的query_uid
                user_content = messages[-1].get("content", "")
                uid_match = re.search(r'"uid":\s*"([^"]+)"', user_content)
                if uid_match:
                    return uid_match.group(1)

                # 如果没有找到，尝试从系统消息中查找
                system_content = messages[0].get("content", "")
                uid_match = re.search(r'"query_uid":\s*"([^"]+)"', system_content)
                if uid_match:
                    return uid_match.group(1)
        except Exception:
            pass
        return ""

    def _init_openai_model(self, model_key: str):
        """初始化OpenAI官方模型"""
        cfg = self.config[model_key]

        def openai_call(messages: List[Dict[str, str]]) -> str:
            try:
                client = OpenAI(
                    api_key=cfg["api_key"],
                    base_url=cfg.get("api_base", "https://api.openai.com/v1")
                )

                response = client.chat.completions.create(
                    model=cfg["model_name"],
                    messages=messages,
                    max_tokens=cfg["max_tokens"],
                    temperature=cfg["temperature"],
                    stream=False
                )

                # 调试：打印完整响应
                print("✅ 原始响应:", response)

                # 保存token使用情况
                if hasattr(response, 'usage') and response.usage:
                    usage_data = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }

                    query_uid = self._extract_query_uid(messages)
                    self._save_token_usage(cfg["model_name"], usage_data, query_uid)

                    print(
                        f"📊 Token使用: 总{response.usage.total_tokens}"
                        f" (输入{response.usage.prompt_tokens} + 输出{response.usage.completion_tokens})")

                return response.choices[0].message.content
            except Exception as e:
                print(f"❌ {model_key} 调用失败: {e}")
                return ""

        return openai_call

    def _init_openai_compatible(self, model_key: str):
        """初始化OpenAI兼容的模型（DeepSeek, Qwen, Mistral）"""
        cfg = self.config[model_key]

        def openai_compatible_call(messages: List[Dict[str, str]]) -> str:
            try:
                client = OpenAI(
                    api_key=cfg["api_key"],
                    base_url=cfg.get("api_base", cfg.get("base_url", ""))  # 使用配置中的api_base
                )

                response = client.chat.completions.create(
                    model=cfg["model_name"],
                    messages=messages,
                    max_tokens=cfg["max_tokens"],
                    temperature=cfg["temperature"]
                )

                # 调试：打印完整响应
                print("✅ 原始响应:", response)

                # 保存token使用情况
                if hasattr(response, 'usage') and response.usage:
                    usage_data = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "prompt_cache_hit_tokens": getattr(response.usage, 'prompt_cache_hit_tokens', 0),
                        "prompt_cache_miss_tokens": getattr(response.usage, 'prompt_cache_miss_tokens', 0)
                    }

                    query_uid = self._extract_query_uid(messages)
                    self._save_token_usage(cfg["model_name"], usage_data, query_uid)

                    print(
                        f"📊 Token使用: 总{response.usage.total_tokens} "
                        f"(输入{response.usage.prompt_tokens} + 输出{response.usage.completion_tokens})")

                return response.choices[0].message.content
            except Exception as e:
                print(f"❌ {model_key} 调用失败: {e}")
                return ""

        return openai_compatible_call

    def _init_qwen(self, model_key: str):
        """初始化OpenAI兼容的模型（DeepSeek, Qwen, Mistral）"""
        cfg = self.config[model_key]

        def qwen_call(messages: List[Dict[str, str]]) -> str:
            try:
                client = OpenAI(
                    api_key=cfg["api_key"],
                    base_url=cfg.get("api_base", cfg.get("base_url", ""))  # 使用配置中的api_base
                )

                response = client.chat.completions.create(
                    model=cfg["model_name"],
                    messages=messages,
                    extra_body={"enable_thinking": False},
                    stream=False,
                    max_tokens=cfg["max_tokens"],
                )

                # 调试：打印完整响应
                print("✅ 原始响应:", response)

                # 保存token使用情况
                if hasattr(response, 'usage') and response.usage:
                    usage_data = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                        "prompt_cache_hit_tokens": getattr(response.usage, 'prompt_cache_hit_tokens', 0),
                        "prompt_cache_miss_tokens": getattr(response.usage, 'prompt_cache_miss_tokens', 0)
                    }

                    query_uid = self._extract_query_uid(messages)
                    self._save_token_usage(cfg["model_name"], usage_data, query_uid)

                    print(
                        f"📊 Token使用: 总{response.usage.total_tokens} "
                        f"(输入{response.usage.prompt_tokens} + 输出{response.usage.completion_tokens})")

                return response.choices[0].message.content
            except Exception as e:
                print(f"❌ {model_key} 调用失败: {e}")
                return ""

        return qwen_call

    def _init_gemini(self, model_key: str):
        """初始化Gemini模型"""
        cfg = self.config[model_key]

        def gemini_call(messages: List[Dict[str, str]]) -> str:
            try:
                client = OpenAI(
                    api_key=cfg["api_key"],
                    base_url=cfg.get("api_base", "https://api.openai.com/v1")
                )

                response = client.chat.completions.create(
                    model=cfg["model_name"],
                    messages=messages,
                    max_tokens=cfg["max_tokens"],
                    temperature=cfg["temperature"],
                    stream=False
                )

                # 调试：打印完整响应
                print("✅ 原始响应:", response)

                # 保存token使用情况
                if hasattr(response, 'usage') and response.usage:
                    usage_data = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }

                    query_uid = self._extract_query_uid(messages)
                    self._save_token_usage(cfg["model_name"], usage_data, query_uid)

                    print(
                        f"📊 Token使用: 总{response.usage.total_tokens}"
                        f" (输入{response.usage.prompt_tokens} + 输出{response.usage.completion_tokens})")

                return response.choices[0].message.content
            except Exception as e:
                print(f"❌ {model_key} 调用失败: {e}")
                return ""

        return gemini_call

    def generate_response(self, model_name: str, messages: List[Dict[str, str]]) -> str:
        """调用指定模型生成响应"""
        if model_name not in self.model_instances:
            raise ValueError(f"Model {model_name} not found. Available models: {list(self.model_instances.keys())}")

        print(f"🤖 调用模型: {model_name}")
        response = self.model_instances[model_name](messages)

        return response

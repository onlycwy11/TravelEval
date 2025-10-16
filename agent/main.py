import os
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import warnings
warnings.filterwarnings('ignore')

import json
import sys
import traceback

from models.model_router import ModelRouter
from core.utils.data_loader import DataLoader
from core.utils.output_handler import OutputHandler
from core.utils.plan_extractors import PlanExtractor
from strategies.direct import DirectPromptingStrategy
from strategies.zero_shot_cot import ZeroShotCoTStrategy
from strategies.react_reflection import ReActReflectionStrategy

def main(file_name):
    # 1. 加载配置
    with open("config/path_config.json") as f:
        output_dir = json.load(f)["output_dir"]

    # 2. 初始化数据加载器
    data_loader = DataLoader()
    base_path = os.path.join(os.path.dirname(
        os.path.dirname(__file__)), 'environment', 'database', 'intercity_transport')
    file_path = os.path.join(os.path.dirname(
        os.path.dirname(__file__)), 'environment', 'data', 'queries', file_name)

    # 3. 加载用户提问
    user_queries = data_loader.load_simplified_user_queries(file_path)

    # 4. 初始化模型路由器
    model_router = ModelRouter()

    # 5. 初始化所有策略
    strategies = [
        DirectPromptingStrategy(),
        # ZeroShotCoTStrategy(),
        # ReActReflectionStrategy()
    ]

    # 6. 遍历所有用户提问
    for uid, query in user_queries.items():
        station_constraints = PlanExtractor._extract_routes_from_file(
            base_path, query["start_city"], query["target_city"])
        print(query)

        # 7. 遍历所有策略
        for strategy in strategies:
            # 8. 生成系统提示和用户提问
            system_prompt = strategy.get_system_prompt(station_constraints)
            user_query = {
                "uid": uid,
                "nature_language": query["nature_language"]
            }
            user_prompt = strategy.get_user_prompt(user_query)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 6. 遍历所有模型生成方案
            for model_name in ["qwen3-8b"]:
            # for model_name in ["gpt4o_mini", "deepseek-chat", "gpt4o", "qwen3-8b"]:
                try:
                    raw_response = model_router.generate_response(model_name, messages)
                    if raw_response.startswith("```json") and raw_response.endswith("```"):
                        json_content = raw_response.strip("```json").strip("```").strip()
                        try:
                            # 解析 JSON 内容
                            response = json.loads(json_content)
                            print(response)
                        except json.JSONDecodeError as e:
                            print(f"❌ 解析 JSON 响应失败: {e}")
                    elif isinstance(raw_response, str):
                        try:
                            response = json.loads(raw_response)
                        except json.JSONDecodeError:
                            # 处理 JSON 解析错误
                            raise ValueError("Invalid JSON response from model")
                    else:
                        response = raw_response
                    # print("here")

                    # 7. 解析并保存结构化数据
                    travel_plan = OutputHandler.parse_response(
                        response, os.path.join(os.path.dirname(os.path.dirname(__file__)), output_dir), model_name, strategy.strategy_name)
                    saved_path = OutputHandler.save_to_file(
                        travel_plan, os.path.join(os.path.dirname(os.path.dirname(__file__)), output_dir), model_name, strategy.strategy_name)

                    print(f"Successfully saved plan from {model_name} to {saved_path}")
                except Exception as e:
                    print(f"Error with {model_name}: {e}")


if __name__ == "__main__":
    for file_name in ['medium-1.json', 'hard.json', 'progressive.json']:
        main(file_name)
import os
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import warnings
warnings.filterwarnings('ignore')

import json
import sys
import traceback

import re
import mail
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
        ZeroShotCoTStrategy(),
        ReActReflectionStrategy()
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
            for model_name in ["deepseek-chat"]:
            # for model_name in ["gpt4o_mini", "deepseek-chat", "gpt4o", "qwen3-8b", "open-mistral-7b"]:
                try:
                    raw_response = model_router.generate_response(model_name, messages)
                    reasoning_part, response = OutputHandler.process_raw_response(raw_response)
                    OutputHandler.save_results(
                        reasoning_part, response, uid, output_dir, model_name, strategy.strategy_name)

                    if strategy.strategy_name == 'ReAct&Reflection':
                        print("Reflection!")
                        strategy = ReActReflectionStrategy()
                        system_prompt = strategy.get_reflection_prompt(response)
                        messages = [
                            {"role": "system", "content": system_prompt}
                        ]

                        raw_response = model_router.generate_response(model_name, messages)
                        reasoning_part, response = OutputHandler.process_raw_response(raw_response)
                        OutputHandler.save_results(
                            reasoning_part, response, uid, output_dir, model_name, strategy.strategy_name)

                except Exception as e:
                    print(f"Error with {model_name}: {e}")


if __name__ == "__main__":
    # for file_name in ['easy.json', 'medium.json', 'hard.json', 'progressive.json']:
    for file_name in ['test.json']:
        main(file_name)
    mail.sendMail('您的程序已经运行完成！')

    # base_path = os.path.join(os.path.dirname(
    #     os.path.dirname(__file__)), 'environment', 'database', 'intercity_transport')
    #
    # city = {
    #     "北京",
    #     "上海",
    #     "广州",
    #     "深圳",
    #     "杭州",
    #     "南京",
    #     "成都",
    #     "重庆",
    #     "武汉",
    #     "苏州"
    # }
    #
    # stations = set()
    # for start_city in city:
    #     for end_city in city:
    #         if start_city != end_city:
    #             station_constraints = PlanExtractor._extract_routes_from_file(
    #                 base_path, start_city, end_city)
    #             stations.update(station_constraints)
    # print(stations)
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, Tuple
from agent.schemas.travel_plan import FinalTravelPlan  # 导入Pydantic模型


class OutputHandler:
    @staticmethod
    def process_raw_response(raw_response: str) -> Tuple[str, dict]:
        """处理原始响应，提取推理过程和JSON部分"""
        reasoning_part = ""
        json_part = ""

        if "```json" in raw_response:
            split_pos = raw_response.find("```json")
            reasoning_part = raw_response[:split_pos].strip()

            json_block = re.search(r"```json(.*?)```", raw_response[split_pos:], re.DOTALL)
            if json_block:
                json_part = json_block.group(1).strip()
        else:
            json_part = raw_response.strip()

        # 解析JSON
        response = None
        if json_part:
            try:
                response = json.loads(json_part)
            except json.JSONDecodeError:
                try:
                    json_part = json_part.replace("'", '"')  # 修复单引号问题
                    response = json.loads(json_part)
                except json.JSONDecodeError as e:
                    raise ValueError(f"JSON解析失败: {e}")

        return reasoning_part, response

    @staticmethod
    def save_results(
            reasoning_part: str,
            response: dict,
            uid: str,
            output_dir: str,
            model_name: str,
            strategy_name: str
    ) -> str:
        """保存推理过程和旅行计划"""
        if reasoning_part:
            saved_reasoning_path = OutputHandler.save_reasoning_to_json(
                uid, reasoning_part,
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), output_dir, "reasoning_part"),
                model_name, strategy_name
            )
            print(f"Successfully saved reasoning part to {saved_reasoning_path}")

        travel_plan = OutputHandler.parse_response(
            response,
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), output_dir),
            model_name, strategy_name
        )
        saved_path = OutputHandler.save_to_file(
            travel_plan,
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), output_dir, "raw"),
            model_name, strategy_name
        )
        print(f"Successfully saved plan from {model_name} to {saved_path}")
        return saved_path

    @staticmethod
    def parse_response(response: Dict[str, Any], output_dir: str, model_name: str, strategy_name: str) -> FinalTravelPlan:
        """将AI响应解析为结构化数据"""
        try:
            # AI返回的是一个字典
            plan = FinalTravelPlan(**response)
            # print("there")
            # print(plan)

            return plan
        except Exception as e:
            # 解析失败时，将原始 response 包装成 plan 的结构（兼容 save_to_file_fail）
            wrapped_response = {
                "_raw_response": response,  # 标记原始数据
                "_error": str(e),  # 记录错误信息
            }

            # 调用原生的 save_to_file_fail
            filename = OutputHandler.save_to_file_fail(
                plan=wrapped_response,  # 传入包装后的数据
                output_dir=output_dir,
                model_name=model_name,
                strategy_name=strategy_name
            )

            # 抛出异常，提示用户查看保存的文件
            error_msg = (
                f"Failed to parse response: {e}\n"
                # f"💾 Raw response saved to: {os.path.join(output_dir, filename)}"
            )
            raise ValueError(error_msg)

    @staticmethod
    def save_reasoning_to_json(query_uid: str, reasoning_part: str, output_dir: str, model_name: str,
                               strategy_name: str):
        """
        将用户提问的 ID 和推理过程存储到 JSON 文件中。

        Args:
            query_uid (str): 用户提问的唯一 ID（如 "T0001"）。
            reasoning_part (str): 推理过程文本（`'''json` 之前的部分）。
            output_dir (str): 存储路径
            model_name (str): 模型名
            strategy_name (str): 策略名
        """

        # 0. 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 1. 读取已有数据（如果文件存在）
        records = {}
        file_name = f"{model_name}_{strategy_name}_reasoning_records.json"
        json_file = os.path.join(output_dir, file_name)
        if os.path.exists(json_file):
            with open(json_file, "r", encoding="utf-8") as f:
                try:
                    records = json.load(f)
                except json.JSONDecodeError:
                    records = {}  # 如果文件损坏，则初始化为空字典

        # 2. 追加新数据
        records[query_uid] = reasoning_part

        # 3. 保存回 JSON 文件
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

        return file_name

    @staticmethod
    def save_to_file(plan: FinalTravelPlan, output_dir: str, model_name: str, strategy_name: str):
        """保存结构化方案到文件"""
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)

            # 生成文件名
            filename = f"plans_{model_name}_{strategy_name}.json"
            filepath = os.path.join(output_dir, filename)

            # 准备保存的数据
            plan_data = plan.dict()

            # 检查文件是否存在
            if os.path.exists(filepath):
                # 读取现有数据
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                # 如果现有数据不是列表，则将其转换为列表
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
                # 追加新的数据
                existing_data.append(plan_data)
            else:
                # 初始化为列表
                existing_data = [plan_data]

            # 保存到文件
            with open(filepath, "w", encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            print(f"💾 结构化方案已保存到: {filepath}")
            return filename

        except Exception as e:
            print(f"❌ 保存结构化方案失败: {e}")
            return ''

    @staticmethod
    def save_to_file_fail(plan: Dict[str, Any], output_dir: str, model_name: str, strategy_name: str):
        """保存结构化方案到文件"""
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)

            # 生成文件名
            filename = f"fail_plans_{model_name}_{strategy_name}.json"
            filepath = os.path.join(output_dir, filename)

            # 准备保存的数据
            plan_data = plan

            # 检查文件是否存在
            if os.path.exists(filepath):
                # 读取现有数据
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                # 如果现有数据不是列表，则将其转换为列表
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
                # 追加新的数据
                existing_data.append(plan_data)
            else:
                # 初始化为列表
                existing_data = [plan_data]

            # 保存到文件
            with open(filepath, "w", encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            print(f"💾 非结构化问题方案已保存到: {filepath}")
            return filename

        except Exception as e:
            print(f"❌ 保存非结构化问题方案失败: {e}")
            return ''

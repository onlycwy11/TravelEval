import json
import os
from datetime import datetime
from agent.schemas.travel_plan import FinalTravelPlan  # 导入Pydantic模型
from core.utils.poi_matcher import POIMatcher


class OutputHandler:
    @staticmethod
    def parse_response(response: str) -> FinalTravelPlan:
        """将AI响应解析为结构化数据"""
        try:
            # AI返回的是JSON字符串（需在Prompt中强制）
            data = json.loads(response)
            plan = FinalTravelPlan(**data)

            # 匹配POI
            matcher = POIMatcher()
            plan = matcher.match_pois(plan)

            return plan
        except Exception as e:
            raise ValueError(f"Failed to parse response: {e}")

    @staticmethod
    def save_to_file(plan: FinalTravelPlan, output_dir: str, model_name: str, strategy_name: str):
        """保存结构化方案到文件"""
        os.makedirs(output_dir, exist_ok=True)
        filename = f"plans_{model_name}_{strategy_name}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(plan.dict(), f, ensure_ascii=False, indent=2)

        return filename
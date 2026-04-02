from typing import Dict, List, Any
from core.metrics.utility import UtilityMetrics
from core.utils.plan_extractors import PlanExtractor


class EconomyMetrics:
    """经济维度评估指标"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.config = config_manager.get_metric_config('utility')
        self.utility = UtilityMetrics(config_manager)
        self.extractors = PlanExtractor()

    def calculate_all(self, user_query: Dict[str, Any], enhanced_plan: Dict[str, Any],
                      sandbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算经济维度所有指标
        """
        metrics = {}

        ai_plan = enhanced_plan['original_plan']

        print("economy！")

        # 费用分布合理性
        metrics['cost_distribution'] = self.extractors._calculate_actual_cost(ai_plan)

        # 预算效率指数
        metrics['budget_efficiency'] = self._calculate_budget_efficiency(user_query, ai_plan, sandbox_data)

        return metrics

    def _calculate_budget_efficiency(self, user_query: Dict[str, Any],
                                     ai_plan: Dict[str, Any],
                                     sandbox_data: Dict[str, Any]) -> float:
        daily_attractions = {}

        raw_daily_attractions = self.extractors._extract_daily_attractions(ai_plan)

        for day_number in sorted(raw_daily_attractions.keys()):
            if day_number is None:
                continue
            attraction_sequence = []
            day_attractions = raw_daily_attractions[day_number]
            for attraction in day_attractions:
                if attraction['type'] == 'attraction':
                    attraction_sequence.append(attraction['name'])
            daily_attractions[day_number] = attraction_sequence

        travel_experience = self.utility._calculate_experience_value(daily_attractions, sandbox_data, user_query)
        actual_costs = self.extractors._calculate_actual_cost(ai_plan)
        budget_used = 0
        for category in actual_costs:
            actual_value = actual_costs[category]
            budget_used += actual_value

        return travel_experience / budget_used * 1000

    def _calculate_score(self, metrics: Dict[str, Any]) -> float:
        """计算经济维度综合得分"""
        return 90.0  # 示例值

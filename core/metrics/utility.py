from typing import Dict, List, Any
from core.utils.plan_extractors import PlanExtractor


class UtilityMetrics:
    """收益维度评估指标"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.config = config_manager.get_metric_config('utility')
        self.categories = config_manager.get_categories_config()
        self.waiting = config_manager.get_waiting_time()
        self.target_density_map = self.config.get('target_attraction_density_map', {})
        self.extractors = PlanExtractor()

    def calculate_all(self, user_query: Dict[str, Any], enhanced_plan: Dict[str, Any],
                      sandbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算收益维度所有指标

        Args:
            user_query: 用户提问数据
            enhanced_plan: 增强的规划方案数据（包含提取的信息）
            sandbox_data: 沙盒数据

        Returns:
            包含所有指标值和综合得分的字典
        """
        metrics = {}

        # 获取提取的数据
        ai_plan = enhanced_plan['original_plan']
        extracted_data = enhanced_plan['extracted_data']
        raw_daily_attractions = extracted_data['daily_attractions']

        daily_attractions = {}
        n = 0

        for day_number in sorted(raw_daily_attractions.keys()):
            if day_number is None:
                continue
            attraction_sequence = []
            day_attractions = raw_daily_attractions[day_number]
            for attraction in day_attractions:
                if attraction['type'] == 'attraction':
                    attraction_sequence.append(attraction['name'])
                    n = n + 1
            daily_attractions[day_number] = attraction_sequence

        experience_value = self._calculate_experience_value(
            daily_attractions, sandbox_data, user_query
        )

        # 规划行程总时间
        time = 24 * self.extractors._calculate_total_travel_time(
            ai_plan['summary'], ai_plan['intercity_transport']['transport_type'])
        # 高质量景点体验值（High-Quality Attraction Experience Value）
        hae_value = self._calculate_hai(raw_daily_attractions, user_query, sandbox_data)

        # 景点质量效能
        metrics['aqe'] = hae_value / time

        # 旅行体验收益（平均价值）
        metrics['profit'] = experience_value / n

        # 体验多样性
        metrics['diversity'] = self._calculate_diversity(daily_attractions, sandbox_data)

        # 景点密度评分
        metrics['ads'] = self._calculate_ads(daily_attractions, user_query)

        # 计算综合得分
        # metrics['score'] = self._calculate_score(metrics)

        return metrics

    def _calculate_diversity(self, daily_attractions: Dict[int, List[Dict]],
                             sandbox_data: Dict[str, Any]) -> float:
        """
        计算体验多样性指数 (EDI)
        """
        # 提取所有景点类型
        all_experiences = []
        attractions_df = sandbox_data.get('attractions')

        if attractions_df is None or attractions_df.empty:
            return 0.0

        # 创建景点名称到类型的映射
        attraction_type_map = {}
        for _, row in attractions_df.iterrows():
            types = row['type'].strip('{}').split(';')
            attraction_type_map[row['name']] = types

        # 收集所有景点的类型（多标签格式）
        for day_attractions in daily_attractions.values():
            for attraction in day_attractions:
                if attraction in attraction_type_map:
                    attraction_types = attraction_type_map[attraction]
                    all_experiences.append(attraction_types)

        if not all_experiences:
            return 0.0

        # print(all_experiences)

        # 获取 attractions 的长度
        n_attractions = len(self.categories['attractions'])

        # 计算体验多样性指数
        return self.extractors._calculate_edi(all_experiences, n_attractions)

    def _calculate_hai(self, daily_schedules: Dict[int, List[Dict]],
                       user_query: Dict[str, Any],
                       sandbox_data: Dict[str, Any]) -> float:
        """
        计算高质量景点指数
        """
        total_quality_time = 0.0

        attractions_df = sandbox_data.get('attractions')
        if attractions_df is None or attractions_df.empty:
            return 0.0

        # 创建景点名称到评分的映射
        attraction_quality_map = {}
        for _, row in attractions_df.iterrows():
            attraction_quality_map[row['name']] = row.get('star', 3.0)

        # 计算质量加权时间和总时间
        for day_number, day_attractions in daily_schedules.items():
            for attraction in day_attractions:
                if attraction['type'] == 'attraction':
                    attraction_name = attraction['name']
                    day_type = self.extractors._get_date_type(user_query.get('dates'), day_number)
                    effective_duration = self.extractors._calculate_effective_time(
                        attraction, day_type, attraction.get('type'), self.waiting)
                    quality_score = attraction_quality_map.get(attraction_name, 3.0)
                    total_quality_time += quality_score * effective_duration

        return total_quality_time

    def _calculate_ads(self, daily_attractions: Dict[int, List[Dict]],
                       user_query: Dict[str, Any]) -> float:
        """
        计算景点密度评分
        """
        if not daily_attractions:
            return 0.0

        # 计算实际每日平均景点数
        total_attractions = sum(len(attractions) for attractions in daily_attractions.values())
        actual_daily_density = total_attractions / len(daily_attractions)

        # 获取目标景点密度
        travel_style = self.extractors._determine_travel_style(user_query)  # 默认"普通"
        target_density = self.target_density_map.get(travel_style, 3.54)  # 默认3.54

        # 计算密度评分
        if target_density == 0:
            return 0.0

        density_ratio = actual_daily_density / target_density
        ads = density_ratio

        return ads

    def _calculate_experience_value(self, daily_attractions: Dict[int, List[Dict]],
                                    sandbox_data: Dict[str, Any],
                                    user_query: Dict[str, Any]) -> float:
        """
        计算旅行体验价值
        """
        total_value = 0.0
        attractions_df = sandbox_data.get('attractions')

        if attractions_df is None or attractions_df.empty:
            return 0.0

        # 创建景点名称到信息的映射
        attraction_info_map = {}
        for _, row in attractions_df.iterrows():
            attraction_info_map[row['name']] = {
                'star': row.get('star', 3.0),
                'type': row.get('type', '其他')
            }

        # 获取用户偏好
        user_preferences = self.extractors._extract_user_preferences(user_query)

        # 计算每个景点的价值
        for day_attractions in daily_attractions.values():
            for attraction in day_attractions:
                if attraction in attraction_info_map:
                    attraction_info = attraction_info_map[attraction]
                    base_quality = attraction_info['star']
                    preference_match = self.extractors._calculate_preference_match(
                        attraction_info['type'], user_preferences
                    )
                    attraction_value = base_quality * preference_match
                    total_value += attraction_value

        return total_value

    def _calculate_budget_efficiency(self, ai_plan: Dict[str, Any],
                                     total_experience_value: float) -> float:
        """
        计算预算效率指数
        """
        summary = ai_plan.get('summary', {})
        total_cost = float(summary.get('calculated_total_cost', 0) or 0)

        if total_cost <= 0:
            return 0.0

        efficiency = total_experience_value / total_cost
        normalized_efficiency = min(1.0, efficiency / 10.0)

        return normalized_efficiency

    def _calculate_score(self, metrics: Dict[str, Any]) -> float:
        """
        计算收益维度综合得分
        """
        weights = {
            'diversity': 0.25,
            'haei': 0.25,
            'ads': 0.20,
            'total_experience_value': 0.15,
            'budget_efficiency': 0.15
        }

        # 归一化各指标值
        normalized_metrics = {}
        normalized_metrics['diversity'] = metrics['diversity']
        normalized_metrics['aqe'] = min(1.0, metrics['aqe'] / 4.0)
        normalized_metrics['ads'] = metrics['ads']
        normalized_metrics['profit'] = min(1.0, metrics['profit'] / 100.0)

        # 计算加权得分
        total_score = 0.0
        total_weight = 0.0

        for metric_name, weight in weights.items():
            if metric_name in normalized_metrics:
                total_score += normalized_metrics[metric_name] * weight
                total_weight += weight

        final_score = (total_score / total_weight) * 100 if total_weight > 0 else 0
        return round(final_score, 2)

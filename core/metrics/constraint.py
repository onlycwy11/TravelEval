from typing import Dict, List, Any
from core.utils.plan_extractors import PlanExtractor


class ConstraintMetrics:
    """约束维度评估指标"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.config = config_manager.get_metric_config('constraint')
        self.config_waiting = config_manager.get_waiting_time()
        self.extractors = PlanExtractor()

    def calculate_all(self, user_query: Dict[str, Any], enhanced_plan: Dict[str, Any],
                      sandbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算约束维度所有指标

        Args:
            user_query: 用户提问数据
            enhanced_plan: 增强的规划方案数据
            sandbox_data: 沙盒数据

        Returns:
            包含所有指标值和综合得分的字典
        """
        metrics = {}

        extracted_data = enhanced_plan['extracted_data']
        daily_schedules = extracted_data['daily_schedules']
        original_plan = enhanced_plan['original_plan']

        # 预算满足度
        metrics['budget_satisfaction'] = self._calculate_budget_satisfaction(original_plan)

        # 时间准合度
        metrics['time_compliance'] = self._calculate_time_compliance(original_plan, user_query)

        # 人数适应性
        metrics['people_adaptability'] = self._calculate_people_adaptability(original_plan, user_query)

        # 住宿满足度
        metrics['accommodation_satisfaction'] = self._calculate_accommodation_satisfaction(
            original_plan, user_query, sandbox_data
        )

        # 交通满足度
        metrics['transportation_satisfaction'] = self._calculate_transportation_satisfaction(
            original_plan, user_query
        )

        # 饮食偏好满足度
        metrics['diet_preference_satisfaction'] = self._calculate_diet_preference_satisfaction(
            daily_schedules, user_query, sandbox_data
        )

        # 游览时间满足度
        metrics['travel_time_satisfaction'] = self._calculate_travel_time_satisfaction(
            daily_schedules, user_query, sandbox_data
        )

        # 计算综合得分
        # metrics['score'] = self._calculate_score(metrics)

        return metrics

    def _calculate_budget_satisfaction(self, ai_plan: Dict[str, Any]) -> int:
        """
        计算预算满足度

        Args:
            ai_plan: AI规划方案

        Returns:
            预算满足度 (0-1)
        """
        actual_costs = self.extractors._calculate_actual_cost(ai_plan)
        actual_cost = 0
        for category in actual_costs:
            actual_value = actual_costs[category]
            actual_cost += actual_value

        summary = ai_plan.get('summary', {})
        total_budget = float(summary.get('total_budget', 0) or 0)
        is_within_budget = summary.get('is_within_budget', False)

        if is_within_budget:
            if total_budget == 0 or actual_cost <= total_budget:
                return 1  # 预算为0，无法判断
            else:
                return 0
        else:
            return 0

    def _calculate_time_compliance(self, ai_plan: Dict[str, Any], user_query: Dict[str, Any]) -> int:
        """
        计算时间准合度

        Args:
            ai_plan: AI规划方案
            user_query: 用户提问

        Returns:
            时间准合度 (0-1)
        """
        summary = ai_plan.get('summary', {})
        planned_days = summary.get('total_days', 0)
        user_days = user_query.get('days', 0)

        if user_days == 0:
            return 1  # 用户未指定天数

        if planned_days == user_days:
            return 1
        else:
            return 0

    def _calculate_people_adaptability(self, ai_plan: Dict[str, Any], user_query: Dict[str, Any]) -> int:
        """
        计算人数适应性

        Args:
            ai_plan: AI规划方案
            user_query: 用户提问

        Returns:
            人数适应性 (0-1)
        """
        summary = ai_plan.get('summary', {})
        planned_people = summary.get('total_travelers', 0)
        actual_people = user_query.get('people_number', 0)

        if actual_people == 0:
            return 1  # 用户未指定人数
        elif planned_people != actual_people:
            return 0

        room_type = {"单人房": 1, "大床房": 2, "双人房": 2, "家庭房": 3}

        # 1. 提取交通人数偏差
        for transport in ai_plan["intercity_transport"]["transport_type"]:
            details = transport.get('details')
            planned_people = float(details.get('number'))
            if planned_people < actual_people:
                return 0

        # 2. 提取住宿人数偏差
        planned_people = 0
        for accommodation in ai_plan["accommodation"]["room_type"]:
            types = accommodation.get('type')
            matched_type = next((key for key in room_type if key in types), None)
            type_number = room_type.get(matched_type, 0)
            planned_people += float(accommodation.get('quantity')) * type_number
        if planned_people < actual_people:
            return 0

        # 3. 遍历每日计划，计算其他人数偏差
        for day_plan in ai_plan["daily_plans"]:
            for activity in day_plan["activities"]:
                if "details" not in activity or activity["details"] is None:
                    continue

                ticket_number = activity["details"].get("ticket_number", 0)
                if ticket_number and ticket_number < actual_people:
                    return 0

                load_limit = activity["details"].get("load_limit")
                car_number = activity["details"].get("car_number")

                if load_limit is not None and car_number is not None:
                    seat_number = float(load_limit) - 1
                    car_number = float(car_number)
                    if seat_number and car_number and seat_number * car_number < actual_people:
                        return 0

            # 处理每日结束点的交通成本（如返回酒店的地铁）
            ending_point = day_plan.get("ending_point", {})
            if ending_point and "details" in ending_point and ending_point["details"] is not None:
                load_limit = ending_point["details"].get("load_limit")
                car_number = ending_point["details"].get("car_number")

                if load_limit is not None and car_number is not None:
                    seat_number = float(load_limit) - 1
                    car_number = float(car_number)
                    if seat_number and car_number and seat_number * car_number < actual_people:
                        return 0

        return 1

    def _calculate_accommodation_satisfaction(self, ai_plan: Dict[str, Any],
                                              user_query: Dict[str, Any],
                                              sandbox_data: Dict[str, Any]) -> int:
        """
        计算住宿满足度

        Args:
            ai_plan: 每日行程安排
            user_query: 用户提问

        Returns:
            住宿满足度 (0-1)
        """
        user_preferences = user_query.get('accommodations', {})
        preferences = user_preferences.get('preferences', [])
        constraints = user_preferences.get('constraints', [])
        total_day = ai_plan.get('summary').get('total_days', 0)
        name = ai_plan.get('accommodation').get('hotel_name', '')

        night = 0
        night_index = 0
        for accommodation in ai_plan['accommodation'].get('room_type'):
            night += int(accommodation.get('nights', 0))
            night_index += 1
        night = night / night_index
        if night != (total_day - 1):
            return 0

        accommodations_df = sandbox_data.get('accommodations')
        if accommodations_df is None or accommodations_df.empty:
            return 0  # 无法验证

        types = ''
        for _, row in accommodations_df.iterrows():
            if row['name'] == name:
                types = row.get('featurehoteltype', '')
                break

        if not preferences:
            if constraints:
                is_preferred = types not in constraints
            else:
                return 1
        else:
            is_preferred = types in preferences

        return int(is_preferred)

    def _calculate_transportation_satisfaction(self, ai_plan: Dict[str, Any],
                                               user_query: Dict[str, Any]) -> int:
        """
        计算交通满足度

        Args:
            ai_plan: AI规划方案
            user_query: 用户提问

        Returns:
            交通满足度 (0-1)
        """
        user_transportation = user_query.get('transportation', {})
        preferences = user_transportation.get('preferences', [])
        constraints = user_transportation.get('constraints', [])

        if not preferences and not constraints:
            return 1  # 用户无交通要求

        intercity_transports = ai_plan.get('intercity_transport', [])

        is_preferred = 0
        for transport in intercity_transports.get('transport_type'):
            types = transport.get('transportation_to')
            if preferences:
                is_preferred = types in preferences
                if is_preferred:
                    is_preferred = types not in constraints
                else:
                    return 0
            else:
                is_preferred = types not in constraints

        return int(is_preferred)

    def _calculate_diet_preference_satisfaction(self, daily_schedules: Dict[int, List[Dict]],
                                                user_query: Dict[str, Any],
                                                sandbox_data: Dict[str, Any]) -> int:
        """
        计算饮食偏好满足度

        Args:
            daily_schedules: 每日行程安排
            user_query: 用户提问

        Returns:
            饮食偏好满足度 (0-1)
        """
        user_diet = user_query.get('diet', {})
        preferences = user_diet.get('preferences', [])
        constraints = user_diet.get('constraints', [])

        restaurants_df = sandbox_data.get('restaurants')
        if restaurants_df is None or restaurants_df.empty:
            return 0  # 无法验证

        types = ''
        for day_number, activities in daily_schedules.items():
            meal_activities = [act for act in activities if act and act.get('type') == 'meal']

            for activity in meal_activities:
                name = activity.get('location_name')
                for _, row in restaurants_df.iterrows():
                    if row['name'] == name:
                        types = row.get('cuisine', '其他')
                        break

                if preferences:
                    is_preferred = types in preferences
                    if is_preferred:
                        preferences = [item for item in preferences if item != types]
                else:
                    is_preferred = types not in constraints
                    if not is_preferred:
                        return 0

        if not preferences:
            return 1
        else:
            return 0

    def _calculate_travel_time_satisfaction(self, daily_schedules: Dict[int, List[Dict]],
                                            user_query: Dict[str, Any],
                                            sandbox_data: Dict[str, Any]) -> int:
        attractions_df = sandbox_data.get('attractions')
        if attractions_df is None or attractions_df.empty:
            return 1  # 无法验证开放时间

        effective_hours_map = {}
        for _, row in attractions_df.iterrows():
            types_str = row.get('type')
            effective_hours_map[row['name']] = {
                'recommendmintime': row.get('recommendmintime', '0'),
                'recommendmaxtime': row.get('recommendmaxtime', '0'),
                'type': {t.strip() for t in types_str.strip("{}").split(";")}
            }

        for day_number, activities in daily_schedules.items():
            for activity in activities:
                if activity.get('type', '') == 'attraction':
                    name = activity.get('location_name', '')

                    if name in effective_hours_map:
                        day_type = self.extractors._get_date_type(user_query.get('dates'), day_number)
                        effective_hours = self.extractors._calculate_effective_time(
                            activity, day_type, effective_hours_map[name].get('type'), self.config_waiting)
                        if effective_hours < effective_hours_map[name].get('recommendmintime') or \
                                effective_hours > effective_hours_map[name].get('recommendmaxtime'):
                            # print(name)
                            return 0

        return 1

    def _calculate_score(self, metrics: Dict[str, Any]) -> float:
        """
        计算约束维度综合得分 (0-100)

        Args:
            metrics: 各指标值

        Returns:
            综合得分
        """
        # 指标权重配置
        weights = {
            'budget_satisfaction': 0.15,  # 预算满足度
            'time_compliance': 0.15,  # 时间准合度
            'people_adaptability': 0.15,  # 人数适应性
            'accommodation_satisfaction': 0.15,  # 住宿满足度
            'transportation_satisfaction': 0.15,  # 交通满足度
            'diet_preference_satisfaction': 0.10,  # 饮食偏好满足度
            'travel_time_satisfaction': 0.15
        }

        # 约束维度指标值本身就是满足度（0-1）
        normalized_metrics = metrics.copy()

        # 计算加权得分
        total_score = 0.0
        total_weight = 0.0

        for metric_name, weight in weights.items():
            if metric_name in normalized_metrics:
                total_score += normalized_metrics[metric_name] * weight
                total_weight += weight

        # 转换为0-100分制
        final_score = (total_score / total_weight) * 100 if total_weight > 0 else 0

        return round(final_score, 2)

import os
from typing import Dict, List, Any
from core.utils.plan_extractors import PlanExtractor
from core.utils.geo_calculator import GeoCalculator
from core.utils.data_loader import DataLoader


class AccuracyMetrics:
    """准确维度评估指标"""

    def __init__(self, config_manager, poi_file: str = "poi.json"):
        self.config_manager = config_manager
        self.config = config_manager.get_metric_config('accuracy')
        self.apis = config_manager.get_apis_config()
        self.poi_file = poi_file
        self.geo_calculator = GeoCalculator()
        self.extractors = PlanExtractor()
        self.data_loader = DataLoader()
        self.base_path = os.path.join(self.data_loader.base_path, 'poi')

    def calculate_all(self, user_query: Dict[str, Any], enhanced_plan: Dict[str, Any],
                      sandbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算准确维度所有指标

        Args:
            user_query: 用户提问数据
            enhanced_plan: 增强的规划方案数据
            sandbox_data: 沙盒数据

        Returns:
            包含所有指标值和综合得分的字典
        """
        metrics = {}

        extracted_data = enhanced_plan['extracted_data']
        daily_attractions = extracted_data['daily_attractions']
        attraction_sequence = extracted_data['attraction_sequence']
        daily_schedules = extracted_data['daily_schedules']
        plan_summary = extracted_data['plan_summary']
        original_plan = enhanced_plan['original_plan']

        city = self.data_loader._city_to_pinyin(plan_summary['destination'])
        poi_file_path = os.path.join(self.base_path, city, self.poi_file)
        self.geo_calculator.set_gaode_api_key(self.apis['gaode_api_key'])

        attractions_sequence = []
        for day_number in sorted(attraction_sequence.keys()):
            for attraction in attraction_sequence[day_number]:
                attractions_sequence.append(attraction)

        # print(attractions_sequence)

        coordinate = self.geo_calculator.get_poi_coordinates(poi_file_path, attractions_sequence)
        # print(coordinate)
        sandbox_data_intercity = self.data_loader.load_intercity_transport(plan_summary.get('departure'),
                                                                           plan_summary.get('destination'))

        # 费用计算偏差率
        metrics['cost_deviation_rate'] = self._calculate_cost_deviation_rate(original_plan)

        # 虚构景点检出率
        metrics['fictitious_attraction_rate'] = self._calculate_fictitious_attraction_rate(
            daily_attractions, coordinate
        )

        # 开放时间硬性违规
        metrics['opening_hours_violations'] = self._calculate_opening_hours_violations(
            daily_schedules, sandbox_data
        )

        # 交通链路断裂数
        metrics['transportation_breaks'] = self._calculate_transportation_breaks(daily_attractions, coordinate, plan_summary.get('destination'))

        # 城际规划偏差
        metrics['intercity_planning_deviation'] = self._calculate_intercity_planning_deviation(
            original_plan, sandbox_data_intercity
        )

        # 人数准确率
        metrics['people_accuracy'] = self._calculate_people_accuracy(original_plan, user_query)

        # 计算综合得分
        # metrics['score'] = self._calculate_score(metrics)

        # print(metrics)

        return metrics

    def _calculate_cost_deviation_rate(self, ai_plan: Dict[str, Any]) -> float:
        """
        Args:
        ai_plan: AI规划方案，包含 summary 和 cost_breakdown

        Returns:
            费用偏差率 (0-1)，表示总偏差程度
        """
        # 初始化实际成本字典
        actual_costs = self.extractors._calculate_actual_cost(ai_plan)

        # 对比AI计算的分项成本与实际成本
        ai_costs = ai_plan["cost_breakdown"]
        discrepancy = 0
        actual_cost = 0

        for category in actual_costs:
            ai_value = float(ai_costs.get(category, 0))
            actual_value = actual_costs[category]
            discrepancy += abs(actual_value - ai_value)
            # print(actual_value)
            actual_cost += actual_value

        return discrepancy / actual_cost

    def _calculate_fictitious_attraction_rate(self, daily_attractions: Dict[int, List[Dict]],
                                              coordinate: Dict[str, Any]) -> float:
        """
        计算虚构景点检出率

        Args:
            daily_attractions: 每日景点字典
            coordinate (dict): 真实景点坐标字典，格式如 {'景点A': (lat, lng), ...}

        Returns:
            虚构景点比例 (0-1)
        """
        if not daily_attractions or not coordinate:
            return 1.0

        total_attractions = 0
        fictitious_count = 0
        real_attractions = set(coordinate.keys())  # 真实景点名称集合

        # 检查每个景点是否真实存在
        for day_attractions in daily_attractions.values():
            for attraction in day_attractions:
                attraction_name = attraction['name']
                total_attractions += 1

                if attraction_name not in real_attractions:
                    print(attraction_name)
                    fictitious_count += 1

        if total_attractions == 0:
            return 0.0

        return fictitious_count / total_attractions

    def _calculate_opening_hours_violations(self, daily_attractions: Dict[int, List[Dict]],
                                            sandbox_data: Dict[str, Any]) -> float:
        """
        计算开放时间硬性违规

        Args:
            daily_attractions: 每日景点字典
            sandbox_data: 沙盒数据

        Returns:
            违规比例 (0-1)
        """
        total_attractions = 0
        violation_count = 0

        attractions_df = sandbox_data.get('attractions')
        if attractions_df is None or attractions_df.empty:
            return 1.0  # 无法验证开放时间

        # 创建景点名称到开放时间的映射
        opening_hours_map = {}
        for _, row in attractions_df.iterrows():
            opening_hours_map[row['name']] = {
                'opentime': row.get('opentime', '09:00'),
                'endtime': row.get('endtime', '17:00')
            }

        # 检查每个景点的访问时间是否在开放时间内
        for day_attractions in daily_attractions.values():
            for attraction in day_attractions:
                attraction_name = attraction['location_name']
                visit_time = attraction['start_time']  # 使用开始时间作为访问时间

                if attraction_name in opening_hours_map:
                    total_attractions += 1
                    hours_info = opening_hours_map[attraction_name]

                    if not self._is_within_opening_hours(visit_time, hours_info):
                        violation_count += 1

        if total_attractions == 0:
            return 0.0

        return violation_count / total_attractions

    def _is_within_opening_hours(self, visit_time: str, hours_info: Dict[str, str]) -> bool:
        """
        检查访问时间是否在开放时间内

        Args:
            visit_time: 访问时间 (HH:MM)
            hours_info: 开放时间信息

        Returns:
            是否在开放时间内
        """
        try:
            visit_h, visit_m = map(int, visit_time.split(':'))
            open_h, open_m = map(int, hours_info['opentime'].split(':'))
            end_h, end_m = map(int, hours_info['endtime'].split(':'))

            visit_minutes = visit_h * 60 + visit_m
            open_minutes = open_h * 60 + open_m
            end_minutes = end_h * 60 + end_m

            return open_minutes <= visit_minutes <= end_minutes

        except (ValueError, AttributeError, KeyError):
            return True  # 如果时间格式错误，假设在开放时间内

    def _calculate_transportation_breaks(self, daily_schedules: Dict[int, List[Dict]], coordinate: Dict, city: str) -> float:
        """
        计算交通链路断裂数

        Args:
            daily_schedules: 每日行程安排

        Returns:
            交通断裂比例 (0-1)
        """
        total_transitions = 0
        break_count = 0

        for day_number, activities in daily_schedules.items():
            if len(activities) < 2:
                continue

            for i in range(len(activities) - 1):
                current_activity = activities[i]
                next_activity = activities[i + 1]

                # 检查是否需要交通转移
                if self._requires_transportation(current_activity, next_activity):
                    total_transitions += 1

                    # 检查是否有合理的交通时间
                    if not self.geo_calculator.check_public_transport_availability(current_activity, next_activity,
                                                                                   coordinate, city):
                        break_count += 1
                        print(break_count)

        if total_transitions == 0:
            return 0.0

        return break_count / total_transitions

    def _requires_transportation(self, activity1: Dict[str, Any], activity2: Dict[str, Any]) -> bool:
        """
        检查两个活动之间是否需要交通转移

        Args:
            activity1: 第一个活动
            activity2: 第二个活动

        Returns:
            是否需要交通
        """
        location1 = activity1.get('location_name', '')
        location2 = activity2.get('location_name', '')

        # 如果地点名称不同，认为需要交通
        return location1 != location2 and location1 and location2

    def _calculate_intercity_planning_deviation(self, ai_plan: Dict[str, Any],
                                                sandbox_data: Dict[str, Any]) -> float:
        """
        计算城际规划偏差

        Args:
            ai_plan: AI规划方案
            sandbox_data: 沙盒数据

        Returns:
            城际规划偏差率 (0-1)
        """
        intercity_transport = ai_plan.get('intercity_transport', {})
        transport_types = intercity_transport.get('transport_type', [])

        # 如果没有城际交通数据，认为偏差严重（返回 1.0）
        if not transport_types:
            return 1.0

        delta = 0
        actual = 0
        start = transport_types[-1].get('location_name')
        end = transport_types[0].get('location_name')
        for transport in transport_types:
            plan_time = self.extractors._calculate_activity_duration(transport)
            actual_time = self.extractors._extract_intercity_time(transport, start, end, sandbox_data)
            if not actual_time:
                return 1.0
            # print(plan_time, actual_time)
            delta = delta + abs(plan_time - actual_time)
            actual = actual + actual_time
            # print(actual)
            # print(plan_time)

        return delta / actual  # 完全匹配则偏差为 0

    def _calculate_people_accuracy(self, ai_plan: Dict[str, Any], user_query: Dict[str, Any]) -> float:
        """
        计算人数准确率

        Args:
            plan_summary: AI规划方案 Summary 部分
            user_query: 用户提问

        Returns:
            人数准确率 (0-1)
        """
        room_type = {"单人房": 1, "大床房": 2, "双人房": 2, "家庭房": 3}

        deviation_people = 0
        planned_people = 0
        actual_people = user_query.get('people_number', 0)

        if actual_people == 0:
            return 1.0  # 用户未指定人数，认为准确

        # 1. 提取交通人数偏差
        for transport in ai_plan["intercity_transport"]["transport_type"]:
            details = transport.get('details')
            planned_people += float(details.get('number'))
        deviation_people += abs(planned_people / 2 - actual_people)

        # 2. 提取住宿人数偏差
        for accommodation in ai_plan["accommodation"]["room_type"]:
            types= accommodation.get('type')
            matched_type = next((key for key in room_type if key in types), None)
            type_number = room_type.get(matched_type, 0)
            planned_people += float(accommodation.get('quantity')) * type_number
        deviation_people += abs(planned_people - actual_people)

        # 3. 遍历每日计划，计算其他人数偏差
        n1 = 0
        n2 = 0
        planned_people1 = 0
        for day_plan in ai_plan["daily_plans"]:
            for activity in day_plan["activities"]:
                ticket_number = activity["details"].get("ticket_number", 0)
                if ticket_number:
                    planned_people += abs(ticket_number - actual_people)
                    n1 += 1
                seat_number = float(activity["details"].get("load_limit", 0)) - 1
                car_number = float(activity["details"].get("car_number", 0))
                if seat_number or car_number:
                    planned_people1 += abs(seat_number * car_number - actual_people)
                    n2 += 1

            # 处理每日结束点的交通成本（如返回酒店的地铁）
            ending_point = day_plan.get("ending_point", {})
            if ending_point:
                seat_number = float(ending_point["details"].get("load_limit", 0)) - 1
                car_number = float(ending_point["details"].get("car_number", 0))
                if seat_number or car_number:
                    planned_people1 += abs(seat_number * car_number - actual_people)
                    n2 += 1
        if n1 and n2:
            deviation_people += (planned_people / n1 + planned_people1 / n2)

        deviation = deviation_people / actual_people
        accuracy = 1.0 - min(1.0, deviation)

        return accuracy

    def _calculate_score(self, metrics: Dict[str, Any]) -> float:
        """
        计算准确维度综合得分 (0-100)

        Args:
            metrics: 各指标值

        Returns:
            综合得分
        """
        # 指标权重配置
        weights = {
            'cost_deviation_rate': 0.25,  # 费用计算偏差率
            'fictitious_attraction_rate': 0.20,  # 虚构景点检出率
            'opening_hours_violations': 0.20,  # 开放时间违规
            'transportation_breaks': 0.15,  # 交通链路断裂
            'intercity_planning_deviation': 0.10,  # 城际规划偏差
            'people_accuracy': 0.10  # 人数准确率
        }

        # 归一化各指标值（准确维度指标值越小越好，需要转换为得分）
        normalized_metrics = {}

        # 费用偏差率：偏差越小得分越高
        normalized_metrics['cost_deviation_rate'] = 1.0 - metrics['cost_deviation_rate']

        # 虚构景点率：虚构越少得分越高
        normalized_metrics['fictitious_attraction_rate'] = 1.0 - metrics['fictitious_attraction_rate']

        # 开放时间违规：违规越少得分越高
        normalized_metrics['opening_hours_violations'] = 1.0 - metrics['opening_hours_violations']

        # 交通断裂：断裂越少得分越高
        normalized_metrics['transportation_breaks'] = 1.0 - metrics['transportation_breaks']

        # 城际规划偏差：偏差越小得分越高
        normalized_metrics['intercity_planning_deviation'] = 1.0 - metrics['intercity_planning_deviation']

        # 人数准确率：准确率本身就是得分
        normalized_metrics['people_accuracy'] = metrics['people_accuracy']

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

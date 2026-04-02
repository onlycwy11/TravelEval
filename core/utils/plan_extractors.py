import math
import json
import os
from typing import Dict, List, Set, Any
from collections import Counter
from datetime import datetime, timedelta


class PlanExtractor:
    @staticmethod
    def _extract_accommodation_pois(ai_plan: Dict[str, Any]) -> Set:
        special_pois = set()

        daily_plans = ai_plan.get('daily_plans', [])
        for day_plan in daily_plans:
            for activity in day_plan.get('activities', []):
                if activity.get('type') in ['accommodation_check_in', 'accommodation_check_out', 'accommodation']:
                    special_pois.add(activity.get('location_name'))
        return special_pois

    @staticmethod
    def _extract_daily_attractions(ai_plan: Dict[str, Any],
                                   need_start_end: bool = True) -> Dict[int, List[Dict[str, Any]]]:
        """
        从AI规划方案中提取每日景点列表，并在景点序列中加入每日起点和终点
        （此处实则是提取 POI，提取景点只需简单修改即可）

        Args:
            ai_plan: AI生成的规划方案

        Returns:
            每日景点字典 {day_number: [attraction_info1, attraction_info2, ...]}
        """
        daily_attractions = {}

        # 注意：现在ai_plan直接就是规划方案内容，没有外层的query_uid
        daily_plans = ai_plan.get('daily_plans', [])

        for day_plan in daily_plans:
            day_number = day_plan.get('day')
            if day_number is None:
                continue

            day_attractions = []

            # 添加起点信息
            if need_start_end:
                starting_point = day_plan.get('starting_point')
                if starting_point:
                    day_attractions.append({
                        'name': starting_point,
                        'type': 'starting_point',
                        'start_time': '00:00',  # 起点没有具体开始时间，可以设置为00:00
                        'end_time': '00:00',  # 起点没有具体结束时间，可以设置为00:00
                        'cost': 0,
                        'duration': 0,
                        'transportation': '',
                        'activity_data': {
                            'description': '起点',
                            'location_name': starting_point
                        }
                    })

            # 遍历当天的活动
            # for activity in day_plan.get('activities', []):
            #     if activity.get('type') == 'attraction':
            #         attraction_info = {
            #             'name': activity.get('location_name'),
            #             'start_time': activity.get('start_time'),
            #             'end_time': activity.get('end_time'),
            #             'cost': float(activity.get('cost', 0) or 0),
            #             'duration': self._calculate_activity_duration(activity),
            #             'activity_data': activity  # 保留完整的活动数据
            #         }
            #
            #         # 只添加有名称的景点
            #         if attraction_info['name']:
            #             day_attractions.append(attraction_info)
            for activity in day_plan.get('activities', []):
                attraction_info = {
                    'name': activity.get('location_name'),
                    'type': activity.get('type'),
                    'start_time': activity.get('start_time'),
                    'end_time': activity.get('end_time'),
                    'cost': float(activity.get('cost', 0) or 0),
                    'duration': PlanExtractor._calculate_activity_duration(activity),
                    'transportation': activity.get('transportation_to'),
                    'activity_data': activity  # 保留完整的活动数据
                }

                # 只添加有名称的景点
                if attraction_info['name']:
                    day_attractions.append(attraction_info)

            # 添加终点信息
            if need_start_end:
                ending_point = day_plan.get('ending_point')
                if ending_point:
                    # 如果ending_point是一个字典，直接使用其内容
                    if isinstance(ending_point, dict):
                        day_attractions.append({
                            'name': ending_point.get('location_name', ''),
                            'type': ending_point.get('type'),
                            'start_time': ending_point.get('start_time', '23:59'),
                            # 使用ending_point中的start_time，如果没有则默认为23:59
                            'end_time': ending_point.get('end_time', '23:59'),  # 使用ending_point中的end_time，如果没有则默认为23:59
                            'cost': ending_point.get('cost', 0),
                            'duration': 0,  # 终点没有具体持续时间，可以设置为0
                            'transportation': ending_point.get('transportation_to', ''),
                            'activity_data': {
                                'type': ending_point.get('type', 'ending_point'),
                                'description': ending_point.get('description', '终点'),
                                'location_name': ending_point.get('location_name', '')
                            }
                        })
                    else:
                        day_attractions.append({
                            'name': 'ending_point',
                            'type': 'ending_point',
                            'start_time': '23:59',  # 终点没有具体开始时间，可以设置为23:59
                            'end_time': '23:59',  # 终点没有具体结束时间，可以设置为23:59
                            'cost': 0,
                            'duration': 0,
                            'transportation': '',
                            'activity_data': {
                                'description': '终点',
                                'location_name': ending_point
                            }
                        })

            daily_attractions[day_number] = day_attractions

        return daily_attractions

    @staticmethod
    def _extract_attraction_sequence(ai_plan: Dict[str, Any], need_start_end: bool = True) -> Dict[int, list[Any]]:
        """
        提取整个行程的景点访问顺序

        Args:
            ai_plan: AI生成的规划方案

        Returns:
            景点名称列表，按访问顺序排列
        """
        attractions_sequence = {}
        daily_attractions = PlanExtractor._extract_daily_attractions(ai_plan, need_start_end)

        # 按天数顺序提取景点
        for day_number in sorted(daily_attractions.keys()):
            attraction_sequence = []
            day_attractions = daily_attractions[day_number]
            for attraction in day_attractions:
                attraction_sequence.append(attraction['name'])
            attractions_sequence[day_number] = attraction_sequence

        return attractions_sequence

    @staticmethod
    def _calculate_activity_duration(activity: Dict[str, Any]) -> float:
        """
        计算活动持续时间（小时）

        Args:
            activity: 活动数据

        Returns:
            持续时间（小时）
        """
        try:
            start_time = activity.get('start_time', '00:00')
            end_time = activity.get('end_time', '00:00')

            start_h, start_m = map(int, start_time.split(':'))
            end_h, end_m = map(int, end_time.split(':'))

            if start_h > end_h:
                duration = (end_h + 24 - start_h) + (end_m - start_m) / 60.0
            else:
                duration = (end_h - start_h) + (end_m - start_m) / 60.0

            return max(0, duration)

        except (ValueError, AttributeError):
            return 0.0

    @staticmethod
    def _extract_intercity_time(transport: Dict[str, Any], sandbox_data: Dict[str, Any]) -> float:
        """
        从沙盒数据中提取指定交通方式和编号的城际交通持续时间。

        Args:
            transport: 交通类型（如 'train' 或 'airplane'）。
            sandbox_data: 包含交通数据的字典。

        Returns:
            匹配的持续时间（小时），如果未找到则返回 None。
        """
        transport_type = transport.get('transportation_to')
        # print(transport_type)
        if transport_type == '飞机':
            type = 'airplane'
        elif transport_type in ['高铁', '动车', '快速', '特快', '直达特快']:
            type = 'train'
        else:
            return 1.0

        transport_list = sandbox_data[type]
        closest_flight = None
        min_diff = float('inf')

        start_time = transport['start_time']
        end_time = transport['end_time']
        end = transport['location_name']

        for flight in transport_list:
            if flight.get('To').startswith(end[:2]):
                if flight.get('TrainType') and transport_type not in ['高铁', '动车']:
                    if flight.get('TrainType') in ['高铁', '动车']:
                        continue
                diff = PlanExtractor._get_time_difference(start_time, end_time, flight['BeginTime'], flight['EndTime'])
                if diff < min_diff:
                    min_diff = diff
                    closest_flight = flight
                    # print(closest_flight)

        # print(closest_flight)
        if closest_flight:
            return closest_flight.get('Duration')
        else:
            return 0.0

    @staticmethod
    def _get_time_difference(start1: str, end1: str, start2: str, end2: str) -> float:
        """计算两个时间范围的差异（以小时为单位）"""

        def parse_time(time_str: str) -> datetime:
            """将时间字符串解析为datetime对象"""
            return datetime.strptime(time_str, "%H:%M")

        start1_dt = parse_time(start1)
        end1_dt = parse_time(end1)
        start2_dt = parse_time(start2)
        end2_dt = parse_time(end2)

        if end1_dt < start1_dt:
            end1_dt += timedelta(hours=24)

        diff_start = abs((start1_dt - start2_dt).total_seconds() / 60)
        diff_end = abs((end1_dt - end2_dt).total_seconds() / 60)

        return diff_start + diff_end

    @staticmethod
    def _extract_daily_schedules(ai_plan: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
        """
        提取每日完整行程安排（包含所有活动类型）

        Args:
            ai_plan: AI生成的规划方案

        Returns:
            每日行程字典 {day_number: [activity1, activity2, ...]}
        """
        daily_schedules = {}

        daily_plans = ai_plan.get('daily_plans', [])

        for day_plan in daily_plans:
            day_number = day_plan.get('day')
            if day_number is None:
                continue

            # 复制当天的所有活动
            daily_schedules[day_number] = day_plan.get('activities', [])

        return daily_schedules

    @staticmethod
    def _extract_cost_breakdown(ai_plan: Dict[str, Any]) -> Dict[str, float]:
        """
        提取费用分解信息

        Args:
            ai_plan: AI生成的规划方案

        Returns:
            费用分解字典
        """
        # 注意：你的规划方案中没有cost_breakdown字段，需要从summary中获取
        summary = ai_plan.get('summary', {})
        breakdown = ai_plan.get('cost_breakdown', {})
        cost_breakdown = {
            "attractions": breakdown.get('attractions'),
            "intercity_transportation": breakdown.get('intercity_transportation'),
            "intracity_transportation": breakdown.get('intracity_transportation'),
            "accommodation": breakdown.get('accommodation'),
            "meals": breakdown.get('meals'),
            "other": breakdown.get('other'),
            "total": breakdown.get('total'),
            'is_within_budget': summary.get('is_within_budget', False)
        }
        return cost_breakdown

    @staticmethod
    def _extract_plan_summary(ai_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取规划方案概要信息

        Args:
            ai_plan: AI生成的规划方案

        Returns:
            概要信息字典
        """
        return ai_plan.get('summary', {})

    @staticmethod
    def _extract_user_preferences(user_query: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        提取用户偏好

        Args:
            user_query: 用户提问数据

        Returns:
            用户偏好字典
        """
        preferences = {
            'attraction_types': [],
            'constraints': []
        }

        # 提取景点偏好
        attractions = user_query.get('attractions', {})
        preferences['attraction_types'] = attractions.get('preferences', [])
        preferences['constraints'] = attractions.get('constraints', [])

        return preferences

    @staticmethod
    def _calculate_preference_match(attraction_type: str,
                                    user_preferences: Dict[str, List[str]]) -> float:
        """
        计算景点类型与用户偏好的匹配度

        Args:
            attraction_type: 景点类型
            user_preferences: 用户偏好

        Returns:
            匹配度 (0-1)
        """
        preferred_types = user_preferences.get('attraction_types', [])
        constrained_types = user_preferences.get('constraints', [])

        # 计算匹配到偏好的数量
        n = sum(1 for preferred_type in preferred_types if preferred_type in attraction_type)

        # 计算匹配到拒绝列表的数量
        m = sum(1 for constrained_type in constrained_types if constrained_type in attraction_type)

        # 如果匹配到拒绝列表，返回 0.0
        if m > 0:
            if n > 0:
                return (1 + n) / (1 + m)
            return 0.0

        # 如果匹配到偏好列表，返回 1 + n
        if n > 0:
            return 1 + n

        # 默认匹配度
        return 1.0

    @staticmethod
    def _calculate_edi(experiences: List[List[str]], n_types: int) -> float:
        """
        计算体验多样性指数

        Args:
            experiences: 体验类型列表 [['历史','文化'], ['自然'], ...]

        Returns:
            EDI值 (0-1)
        """
        # 初始化类型得分字典
        type_scores = Counter()

        # 计算每个类型的得分
        for exp_list in experiences:
            n = len(exp_list)
            if n == 0:
                continue
            for exp_type in exp_list:
                type_scores[exp_type] += 1 / n

        print(type_scores)

        # 计算总得分（用于概率计算）
        total_score = sum(type_scores.values())
        if total_score == 0:
            return 0.0

        # 计算各类型概率
        probabilities = {t: score / total_score for t, score in type_scores.items()}

        print(probabilities)

        # 计算香农指数
        shannon_h = 0.0
        for p in probabilities.values():
            if p > 0:
                shannon_h -= p * math.log2(p)

        # 计算标准化EDI
        max_entropy = math.log2(n_types) if n_types > 0 else 0
        edi = shannon_h / max_entropy if max_entropy > 0 else 0

        return edi

    @staticmethod
    def _determine_travel_style(user_query):
        """
        根据优先级返回单一 travel_style
        优先级：特种兵式 > 慢旅游 > 亲子家庭游 > 普通
        """
        people = user_query.get('people_composition', {})
        has_family = people.get('children', 0) > 0 or people.get('seniors', 0) > 0

        rhythm = user_query.get('rhythm', {})
        preferences = rhythm.get('preferences', [])

        # 按优先级检查
        if "特种兵式" in preferences:
            return "特种兵"
        elif "慢游" in preferences:
            return "慢游"
        elif has_family:
            return "亲子"
        else:
            return "普通"

    @staticmethod
    def _calculate_total_travel_time(summary, intercity_transport):
        if not intercity_transport:
            start_time = "8:00"
            end_time = "22:00"
        else:
            # 提取第一天城际交通的开始时间和最后一天城际交通的结束时间
            start_time = intercity_transport[0]['start_time']
            end_time = intercity_transport[-1]['end_time']

        # 将时间转换为小时数
        start_hour = int(start_time.split(':')[0]) + int(
            start_time.split(':')[1]) / 60
        end_hour = int(end_time.split(':')[0]) + int(end_time.split(':')[1]) / 60

        # 计算总时间（天数）
        total_hours = end_hour - start_hour
        total_days = total_hours / 24 + int(summary['total_days']) - 1

        return total_days

    @staticmethod
    def _calculate_actual_cost(ai_plan: Dict[str, Any]) -> Dict:
        # 初始化实际成本字典
        actual_costs = {
            "attractions": 0,
            "intercity_transportation": 0,
            "intracity_transportation": 0,
            "accommodation": 0,
            "meals": 0,
            "other": 0
        }

        summary = ai_plan.get('summary', {})
        total_travelers = summary.get('total_travelers')

        # 1. 提取城际交通成本
        cost = 0
        details = None
        for transport in ai_plan["intercity_transport"]["transport_type"]:
            details = transport.get('details')
            cost = cost + float(details.get('price')) * float(details.get('number'))
        actual_costs["intercity_transportation"] = cost
        if details is None:
            details = {
                "price": float("inf")
            }

        # 2. 提取住宿成本
        cost = 0
        for accommodation in ai_plan["accommodation"]["room_type"]:
            cost = cost + float(accommodation.get('quantity')) * float(accommodation.get('price_per_night')) \
                   * float(accommodation.get('nights'))
        actual_costs["accommodation"] = cost

        # 3. 遍历每日计划，计算其他成本
        for day_plan in ai_plan["daily_plans"]:
            for activity in day_plan["activities"]:
                if "details" not in activity or activity["details"] is None:
                    cost = float(activity.get("cost", 0))
                else:
                    price = float(activity["details"].get("ticket_price", 0) or 0.0)
                    number = int(activity["details"].get("ticket_number", 0) or 0)
                    if price:
                        if number:
                            cost = price * number
                        else:
                            cost = price * total_travelers
                    else:
                        cost = float(activity.get("cost", 0))
                transport_cost = float(activity.get("transportation_cost", 0))

                # 景点成本
                if activity["type"] == "attraction":
                    actual_costs["attractions"] += cost

                # 餐饮成本
                elif activity["type"] == "meal":
                    actual_costs["meals"] += cost

                elif activity["type"] in [
                    "intercity_transport", "accommodation", "accommodation_check_in", "accommodation_check_out", "intracity_transport"
                ]:
                    pass

                else:
                    actual_costs["other"] += cost

                # 市内交通成本（所有活动的交通费用，包括步行/地铁等）
                if transport_cost < details.get('price'):
                    actual_costs["intracity_transportation"] += transport_cost

            # 处理每日结束点的交通成本（如返回酒店的地铁）
            ending_point = day_plan.get("ending_point", {})
            if ending_point:
                if float(ending_point.get("transportation_cost", 0)) < details.get('price'):
                    actual_costs["intracity_transportation"] += float(ending_point.get("transportation_cost", 0))

        return actual_costs

    @staticmethod
    def _calculate_effective_time(activity: Dict[str, Any], date_type: str, types: str, config) -> float:
        B_category = config["B_category"]
        K_date = config["K_date"]
        K_time = config["K_time"]

        start_time = activity.get('start_time', '00:00')
        time_slot = PlanExtractor._get_time_slot(start_time)

        B = 0
        for category in types:
            B = B_category.get(category, 0)
            if B:
                break

        K_d = K_date.get(date_type, 1.0)
        K_t = K_time.get(time_slot, 1.0)

        T_est = B * K_d * K_t / 60
        duration = PlanExtractor._calculate_activity_duration(activity)

        return duration - T_est

    @staticmethod
    def _get_date_type(date_range: str, day_number: int):
        start_date_str = date_range.split("to")[0].strip()
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        date = start_date + timedelta(days=int(day_number) - 1)

        month = date.month
        day = date.day
        weekday = date.weekday()  # 0 是周一，6 是周日

        if (month == 10 and 1 <= day <= 7) or (month == 1 and 1 <= day <= 3) or (month == 5 and 1 <= day <= 5):
            return "Golden Week"
        elif weekday in [5, 6]:  # 周六或周日+
            return "Weekend"
        elif (month == 7 or month == 8) or (month == 1 and 15 <= day <= 31) or (month == 2 and 1 <= day <= 15):
            return "Vacation"
        # elif (month == 4 and 29 <= day <= 30) or (month == 5 and 1 <= day <= 4) or (month == 9 and 19 <= day <= 21) or (
        # month == 10 and 1 <= day <= 7):
        # return "Short Holiday"
        elif (month == 12 and 24 <= day <= 25) or (month == 2 and 14 <= day <= 15) or (
                month == 4 and 4 <= day <= 5) or (month == 5 and 1 <= day <= 4) or (
                month == 6 and day == 1) or (month == 9 and day == 10):
            return "Peak Season"
        else:
            return "Weekday"

    @staticmethod
    def _get_time_slot(start_time):
        start_hour, start_minute = map(int, start_time.split(":"))
        start_minutes = start_hour * 60 + start_minute

        time_slots = {
            "08:00-10:00": (8 * 60, 10 * 60),
            "10:00-12:00": (10 * 60, 12 * 60),
            "12:00-16:00": (12 * 60, 16 * 60),
            "16:00-20:00": (16 * 60, 20 * 60),
            "20:00-close": (20 * 60, 24 * 60)
        }

        for slot, (start, end) in time_slots.items():
            if start <= start_minutes < end:
                return slot
        return None

    @staticmethod
    def _extract_routes_from_file(base_path: str, from_city: str, to_city: str) -> Set[str]:
        """
        从指定的JSON文件中提取出发地和目的地数据，并将匹配的机场名也加入到结果中。

        Args:
            base_path (str): 基础路径
            from_city (str): 出发城市
            to_city (str): 目的城市

        Returns:
            Set[str]: 包含出发地、目的地及其匹配机场的集合
        """

        file_path = os.path.join(base_path, 'train', f'from_{from_city}_to_{to_city}.json')

        airports = {
            "南京禄口国际机场",
            "武汉天河国际机场",
            "杭州萧山国际机场",
            "成都天府国际机场",
            "成都双流国际机场",
            "重庆江北国际机场",
            "广州白云国际机场",
            "深圳宝安国际机场",
            "北京大兴国际机场",
            "北京首都国际机场",
            "上海浦东国际机场",
            "上海虹桥国际机场"
        }

        routes = set()

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)

                for item in data:
                    from_location = item.get('From')
                    to_location = item.get('To')

                    # 添加出发地和目的地
                    routes.add(from_location)
                    routes.add(to_location)

            # 检查出发地和目的地是否与机场名的前两个字匹配
            for airport in airports:
                if airport.startswith(from_city):
                    routes.add(airport)
                if airport.startswith(to_city):
                    routes.add(airport)

        except FileNotFoundError:
            print(f"文件未找到: {file_path}")
        except json.JSONDecodeError:
            print(f"文件格式错误: {file_path}")
        except Exception as e:
            print(f"发生错误: {e}")

        return routes

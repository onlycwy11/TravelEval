import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, time


class DataValidators:
    """数据验证器"""

    @staticmethod
    def validate_user_query(query: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证用户提问数据的完整性"""
        errors = []
        required_fields = ['uid', 'start_city', 'target_city', 'days', 'people_number', "people_composition",
                           'budget', 'dates', 'nature_language', 'nature_language_en']

        for field in required_fields:
            if field not in query:
                errors.append(f"缺少必填字段: {field}")

        tag = query.get('tag', 'easy').lower()

        # 验证数据类型
        if 'days' in query and not isinstance(query['days'], int):
            errors.append("days字段应为整数")

        if 'people_number' in query and not isinstance(query['people_number'], int):
            errors.append("people_number字段应为整数")

        if 'budget' in query and not isinstance(query['budget'], (int, float)):
            errors.append("budget字段应为数字")

        if tag == 'medium':
            n = 0
            for category in ['transportation', 'accommodations', 'diet', 'attractions', 'rhythm']:
                if category in query and 'preferences' in query.get(category, {}):
                    n += 1
            if not n:
                errors.append(f"medium难度下{category}字段需要包含preferences")
        elif tag == 'hard':
            m, n = 0, 0
            for category in ['transportation', 'accommodations', 'diet', 'attractions', 'rhythm']:
                if category in query:
                    cat_data = query[category]
                    if 'preferences' in cat_data:
                        m += 1
                    if 'constraints' in cat_data:
                        n += 1
            if not m or not n:
                errors.append(f"hard难度下{category}字段需要包含preferences")
                errors.append(f"hard难度下{category}字段需要包含constraints")

        return len(errors) == 0, errors

    @staticmethod
    def validate_ai_plan(plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证AI规划方案的完整性"""
        errors = []

        if 'query_uid' not in plan:
            errors.append("缺少query_uid字段")
            return False, errors

        if 'itinerary' not in plan:
            errors.append("缺少itinerary字段")
            return False, errors

        itinerary = plan['itinerary']

        # 验证概要信息
        if 'summary' not in itinerary:
            errors.append("缺少summary字段")
        else:
            summary = itinerary['summary']
            summary_fields = ['total_days', 'total_travelers', 'total_budget', 'calculated_total_cost']
            for field in summary_fields:
                if field not in summary:
                    errors.append(f"summary中缺少字段: {field}")

        # 验证住宿信息
        if 'accommodation' not in itinerary:
            errors.append("缺少accommodation字段")
        else:
            accommodation = itinerary['accommodation']
            accommodation_fields = ['hotel_name', 'room_type', 'total_cost']
            for field in accommodation_fields:
                if field not in accommodation:
                    errors.append(f"accommodation中缺少字段: {field}")

            # 验证房间类型信息
            if 'room_type' in accommodation and isinstance(accommodation['room_type'], list):
                for room in accommodation['room_type']:
                    room_fields = ['type', 'quantity', 'price_per_night', 'nights']
                    for field in room_fields:
                        if field not in room:
                            errors.append(f"room_type中缺少字段: {field}")

        # 验证城际交通
        if 'intercity_transport' not in itinerary:
            errors.append("缺少intercity_transport字段")
        else:
            transport = itinerary['intercity_transport']
            if 'total_cost' not in transport:
                errors.append("intercity_transport中缺少total_cost字段")
            if 'transport_type' not in transport:
                errors.append("intercity_transport中缺少transport_type字段")
            elif isinstance(transport['transport_type'], list):
                for t in transport['transport_type']:
                    transport_fields = ['description', 'start_time', 'end_time', 'location_name',
                                        'cost', 'transportation_to', 'transportation_cost']
                    for field in transport_fields:
                        if field not in t:
                            errors.append(f"transport_type中缺少字段: {field}")

                    # 验证详情字段
                    if 'details' in t:
                        t_fields = ['transport_number', 'price', 'number']
                        for field in t_fields:
                            if field not in t['details']:
                                errors.append(f"transport_details中缺少字段: {field}")

        # 验证每日计划
        if 'daily_plans' not in itinerary:
            errors.append("缺少daily_plans字段")
        else:
            daily_plans = itinerary['daily_plans']
            if not isinstance(daily_plans, list):
                errors.append("daily_plans应为列表")
            else:
                for i, day_plan in enumerate(daily_plans):
                    day_errors = DataValidators._validate_daily_plan(day_plan, i)
                    errors.extend(day_errors)

        # 验证费用明细
        if 'cost_breakdown' not in itinerary:
            errors.append("缺少cost_breakdown字段")
        else:
            cost_breakdown = itinerary['cost_breakdown']
            cost_fields = ['attractions', 'intercity_transportation', 'intracity_transportation',
                                     'accommodation', 'meals', 'other', 'total']
            for field in cost_fields:
                if field not in cost_breakdown:
                    errors.append(f"cost_breakdown中缺少字段: {field}")

        return len(errors) == 0, errors

    @staticmethod
    def _validate_daily_plan(day_plan: Dict[str, Any], day_index: int) -> List[str]:
        """验证单日计划"""
        errors = []

        required_fields = ['day', 'date', 'activities']
        for field in required_fields:
            if field not in day_plan:
                errors.append(f"第{day_index + 1}天计划缺少字段: {field}")

        # 验证起始点和结束点
        if 'starting_point' not in day_plan:
            errors.append(f"第{day_index + 1}天计划缺少starting_point字段")

        if 'ending_point' not in day_plan:
            errors.append(f"第{day_index + 1}天计划缺少ending_point字段")
        else:
            ending_point = day_plan['ending_point']
            ending_fields = ['type', 'description', 'start_time', 'end_time', 'location_name',
                             'cost', 'transportation_to', 'transportation_cost']
            for field in ending_fields:
                if field not in ending_point:
                    errors.append(f"第{day_index + 1}天计划的ending_point中缺少字段: {field}")

            if '打车' in ending_point['transportation_to'] or '包车' in ending_point['transportation_to']:
                if 'details' in ending_point:
                    d_fields = ['load_limit', 'car_number']
                    for field in d_fields:
                        if field not in ending_point['details']:
                            errors.append(f"第{day_index + 1}天计划的ending_point details中缺少字段: {field}")
                else:
                    errors.append(f"第{day_index + 1}天计划的ending_point中缺少details字段")

        if 'activities' in day_plan:
            activities = day_plan['activities']
            if not isinstance(activities, list):
                errors.append(f"第{day_index + 1}天的activities应为列表")
            else:
                for j, activity in enumerate(activities):
                    activity_errors = DataValidators._validate_activity(activity, day_index, j)
                    errors.extend(activity_errors)

        return errors

    @staticmethod
    def _validate_activity(activity: Dict[str, Any], day_index: int, activity_index: int) -> List[str]:
        """验证单个活动"""
        errors = []

        required_fields = ['type', 'description', 'start_time', 'end_time', 'location_name', 'cost']
        for field in required_fields:
            if field not in activity:
                errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动缺少字段: {field}")

        # 验证特定类型活动的额外字段
        if activity['type'] == 'attractions' and 'details' not in activity:
            errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动(景点)缺少details字段")
        elif activity['type'] == 'attractions' and 'details' in activity:
            attraction_fields = ['ticket_type', 'ticket_price', 'ticket_number']
            for field in attraction_fields:
                if field not in activity['details']:
                    errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动(景点)的details中缺少字段: {field}")

        if activity['type'] == 'meal' and 'details' not in activity:
            errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动(用餐)缺少details字段")
        elif activity['type'] == 'meal' and 'details' in activity and 'cuisine' not in activity['details']:
            errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动(用餐)的details中缺少cuisine字段")

        # 验证活动的额外字段
        if '打车' in activity['transportation_to'] or '包车' in activity['transportation_to']:
            if 'details' in activity:
                d_fields = ['load_limit', 'car_number']
                for field in d_fields:
                    if field not in activity['details']:
                        errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动的details中缺少字段: {field}")
            else:
                errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动中缺少details字段")

        # 验证时间格式
        if 'start_time' in activity and 'end_time' in activity:
            if not DataValidators._validate_time_format(activity['start_time']):
                errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动start_time格式错误")
            if not DataValidators._validate_time_format(activity['end_time']):
                errors.append(f"第{day_index + 1}天第{activity_index + 1}个活动end_time格式错误")

        # 验证交通方式
        if 'transportation_to' not in activity:
            errors.append(
                f"第{day_index + 1}天第{activity_index + 1}个活动缺少transportation_to")
        elif 'transportation_to' in activity and 'transportation_cost' not in activity:
            errors.append(
                f"第{day_index + 1}天第{activity_index + 1}个活动有transportation_to但缺少transportation_cost")

        return errors

    @staticmethod
    def _validate_time_format(time_str: str) -> bool:
        """验证时间格式 HH:MM"""
        time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
        return bool(time_pattern.match(time_str))


class BusinessValidators:
    """业务逻辑验证器"""

    @staticmethod
    def validate_budget_constraint(plan_cost: float, user_budget: float) -> bool:
        """验证预算约束"""
        return plan_cost <= user_budget

    @staticmethod
    def validate_time_sequence(activities: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """验证活动时间顺序"""
        errors = []

        for i in range(len(activities) - 1):
            current_end = activities[i]['end_time']
            next_start = activities[i + 1]['start_time']

            if current_end > next_start:
                errors.append(f"活动{i + 1}结束时间({current_end})晚于活动{i + 2}开始时间({next_start})")

        return len(errors) == 0, errors

    @staticmethod
    def validate_opening_hours(attraction_name: str, visit_time: str, opening_hours: Dict[str, str]) -> bool:
        """验证景点开放时间"""
        if 'opentime' not in opening_hours or 'endtime' not in opening_hours:
            return False

        visit_dt = datetime.strptime(visit_time, '%H:%M').time()
        open_dt = datetime.strptime(opening_hours['opentime'], '%H:%M').time()
        close_dt = datetime.strptime(opening_hours['endtime'], '%H:%M').time()

        return open_dt <= visit_dt <= close_dt

    @staticmethod
    def validate_transport_feasibility(departure_time: str, arrival_time: str,
                                       transport_schedule: Dict[str, Any]) -> bool:
        """验证交通可行性"""
        try:
            dep_dt = datetime.strptime(departure_time, '%H:%M').time()
            arr_dt = datetime.strptime(arrival_time, '%H:%M').time()
            schedule_dep = datetime.strptime(transport_schedule['BeginTime'], '%H:%M').time()
            schedule_arr = datetime.strptime(transport_schedule['EndTime'], '%H:%M').time()

            # 验证出发时间不早于班次时间，到达时间不晚于班次时间
            return (dep_dt >= schedule_dep and arr_dt <= schedule_arr)

        except (ValueError, KeyError):
            return False
from typing import Dict, List, Any
from core.utils.plan_extractors import PlanExtractor


class TimeMetrics:
    """时间维度评估指标"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.config = config_manager.get_metric_config('time')
        self.config_waiting = config_manager.get_waiting_time()
        self.extractors = PlanExtractor()

    def calculate_all(self, user_query: Dict[str, Any], enhanced_plan: Dict[str, Any],
                      sandbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算时间维度所有指标
        """
        metrics = {}

        original_plan = enhanced_plan['original_plan']
        extracted_data = enhanced_plan['extracted_data']
        daily_schedules = extracted_data['daily_schedules']

        metrics['tour_ratio'] = self._calculate_tour_ratio(daily_schedules, user_query, sandbox_data)
        metrics['daily_time_utilization'] = self._calculate_daily_time_utilization(
            original_plan, metrics['tour_ratio'])
        metrics['overall_time_utilization'] = self._calculate_overall_time_utilization(
            original_plan, metrics['tour_ratio'])

        # metrics['score'] = self._calculate_score(metrics)

        return metrics

    def _calculate_tour_ratio(self, daily_schedules: Dict[int, List[Dict]],
                              user_query: Dict[str, Any],
                              sandbox_data: Dict[str, Any]) -> Dict:
        """
        计算游览比重
        """
        attractions_df = sandbox_data.get('attractions')
        if attractions_df is None or attractions_df.empty:
            return {}

        effective_hours_map = {}
        for _, row in attractions_df.iterrows():
            types_str = row.get('type')
            effective_hours_map[row['name']] = {
                'recommendmintime': row.get('recommendmintime', '0'),
                'recommendmaxtime': row.get('recommendmaxtime', '0'),
                'type': {t.strip() for t in types_str.strip("{}").split(";")}
            }

        tours_ratio = {}
        for day_number, activities in daily_schedules.items():
            for activity in activities:
                if activity.get('type', '') == 'attraction':
                    name = activity.get('location_name', '')

                    if name in effective_hours_map:
                        day_type = self.extractors._get_date_type(user_query.get('dates'), day_number)
                        effective_hours = self.extractors._calculate_effective_time(
                            activity, day_type, effective_hours_map[name].get('type'), self.config_waiting)
                        if effective_hours < effective_hours_map[name].get('recommendmintime'):
                            tour_ratio = 0.0
                        else:
                            duration = self.extractors._calculate_activity_duration(activity)
                            tour_ratio = effective_hours / duration
                        tours_ratio[name] = tour_ratio

        return  tours_ratio

    def _calculate_daily_time_utilization(self, ai_plan: Dict[str, Any], tours_ratio: Dict) -> Dict[int, float]:
        """
        计算单日时间利用率
        """
        daily_utilization = {}
        total_day = ai_plan.get('summary').get('total_days')
        transport = ai_plan.get('intercity_transport').get('transport_type')

        for day_plan in ai_plan.get('daily_plans'):
            day_number = day_plan.get('day')
            start_time = day_plan.get('activities')[0].get('start_time')
            if day_number == 1:
                start_time = transport[0].get('start_time')
            end_time = day_plan.get('ending_point').get('end_time')
            if day_number == total_day:
                end_time = transport[1].get('end_time')

            start_hour = int(start_time.split(':')[0]) + int(
                start_time.split(':')[1]) / 60
            end_hour = int(end_time.split(':')[0]) + int(
                end_time.split(':')[1]) / 60

            tour_ratio = 0
            for activity in day_plan.get('activities'):
                name = activity.get('location_name')
                types = activity.get('type')
                if name in tours_ratio.keys() and types == 'attraction':
                    duration = self.extractors._calculate_activity_duration(activity)
                    tour_ratio += tours_ratio[name] * duration

            utilization = tour_ratio / (end_hour - start_hour)

            daily_utilization[day_number] = utilization

        return daily_utilization

    def _calculate_overall_time_utilization(self, ai_plan: Dict[str, Any], tours_ratio: Dict) -> float:
        """
        计算整体旅游时间利用率
        """
        if not tours_ratio:
            return 0.0

        time = 24 * self.extractors._calculate_total_travel_time(
            ai_plan['summary'], ai_plan['intercity_transport']['transport_type'])

        tour_ratio = 0
        for day_plan in ai_plan.get('daily_plans'):
            for activity in day_plan.get('activities'):
                name = activity.get('location_name')
                types = activity.get('type')
                if name in tours_ratio.keys() and types == 'attraction':
                    tour_ratio += tours_ratio[name]

        total_utilization = tour_ratio / time

        return total_utilization

    def _calculate_score(self, metrics: Dict[str, Any]) -> float:
        """
        计算时间维度综合得分
        """
        weights = {
            'tour_ratio': 0.34,
            'overall_time_utilization': 0.33,
            'daily_time_utilization': 0.33
        }

        normalized_metrics = {
            'tour_ratio': metrics['tour_ratio'],
            'overall_time_utilization': metrics['overall_time_utilization'],
            'daily_time_utilization': metrics['daily_time_utilization']
        }

        total_score = 0.0
        total_weight = 0.0

        for metric_name, weight in weights.items():
            if metric_name in normalized_metrics:
                total_score += normalized_metrics[metric_name] * weight
                total_weight += weight

        final_score = (total_score / total_weight) * 100 if total_weight > 0 else 0
        return round(final_score, 2)

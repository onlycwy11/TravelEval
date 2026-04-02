from typing import Dict, Set, Any, Tuple
import numpy as np
import os
from core.utils.data_loader import DataLoader
from core.utils.geo_calculator import GeoCalculator
from core.utils.plan_extractors import PlanExtractor


class SpaceMetrics:
    """空间维度评估指标"""

    def __init__(self, config_manager, poi_file: str = "poi.json"):
        self.config_manager = config_manager
        self.config = config_manager.get_metric_config('space')
        self.apis = config_manager.get_apis_config()
        self.poi_file = poi_file
        self.geo_calculator = GeoCalculator()
        self.data_loader = DataLoader()
        self.base_path = os.path.join(self.data_loader.base_path, 'poi')

    def calculate_all(self, user_query: Dict[str, Any], enhanced_plan: Dict[str, Any],
                      sandbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算所有空间维度指标"""
        results = {}
        metrics = {}

        # 获取提取的数据
        ai_plan = enhanced_plan['original_plan']

        self.geo_calculator.set_gaode_api_key(self.apis['gaode_api_key'])

        city = self.data_loader._city_to_pinyin(PlanExtractor._extract_plan_summary(ai_plan)['destination'])
        poi_file_path = os.path.join(self.base_path, city, self.poi_file)

        attractions_sequence_by_day_1 = PlanExtractor._extract_attraction_sequence(ai_plan)
        attractions_sequence_by_day_2 = PlanExtractor._extract_attraction_sequence(ai_plan, False)
        special_pois = PlanExtractor._extract_accommodation_pois(ai_plan)

        # 景点顺序合理性
        # 路线惩罚 (Route Penalty)
        route_penalty = self.calculate_RP(attractions_sequence_by_day_1, poi_file_path)
        results['RP'] = sum(route_penalty.values()) / len(route_penalty) if route_penalty else 0.0
        print("RP!")
        # 跨日空间错配度 (Cross-Day Spatial Misalignment)
        results['CSM'] = self.calculate_CSM(attractions_sequence_by_day_2, poi_file_path, special_pois)

        # 计算空间维度综合得分
        # results['score'] = self._calculate_space_score(results)

        return results

    def calculate_RP(self, attractions_sequence_by_day: Dict, poi_file_path: str) -> Dict:
        """计算景点顺序合理性 (使用你提供的GTR代码)"""
        try:
            routes_penalty = {}

            if not os.path.exists(poi_file_path):
                print(f"文件不存在: {poi_file_path}")
            else:
                for day_number in sorted(attractions_sequence_by_day.keys()):
                    print(f"提取第 {day_number} 天的景点访问序列...")
                    raw_attractions_sequence = attractions_sequence_by_day[day_number]
                    coordinates = self.geo_calculator.get_poi_coordinates(poi_file_path, raw_attractions_sequence)

                    attractions_sequence = [attraction for attraction in raw_attractions_sequence if attraction in coordinates.keys()]
                    # print(coordinates)
                    # print(attractions_sequence)

                    actual_distances = self.geo_calculator.calculate_segment_distance(attractions_sequence, coordinates, "driving")

                    route_penalty = self.geo_calculator.calculate_route_penalty(
                        attractions_sequence,
                        actual_distances,
                        coordinates,
                        optimal_route_method="dp"
                    )

                    print(f"Route Penalty (RP): {route_penalty}")
                    print("-" * 50)

                    routes_penalty[day_number] = route_penalty

            return routes_penalty  # 转换为得分形式

        except Exception as e:
            print(f"Route Penalty 计算错误: {e}")
            return {}

    def calculate_CSM(self, attractions_sequence_by_day: Dict, poi_file_path: str, special_pois: Set) -> Dict:
        """计算跨日空间适配指数"""
        try:
            all_attractions = set()
            for day_number in sorted(attractions_sequence_by_day.keys()):
                attractions_sequence = attractions_sequence_by_day[day_number]
                all_attractions.update(attractions_sequence)

            trip_plan_coordinates = self.geo_calculator.get_poi_coordinates(poi_file_path, list(all_attractions))

            for day_number in sorted(attractions_sequence_by_day.keys()):
                attractions_sequence = attractions_sequence_by_day[day_number]
                new_attractions_sequence = [attraction for attraction in attractions_sequence if attraction in trip_plan_coordinates.keys()]
                attractions_sequence_by_day[day_number] = new_attractions_sequence

            result = self.geo_calculator.calculate_cross_day_misalignment(attractions_sequence_by_day, trip_plan_coordinates, special_pois)
            csm_values = result['csm_values']
            problem_spots = result['problem_spots']

            # print(result)
            print(f"景点MisFit值: {csm_values}")
            if problem_spots:
                print("\n需优化的景点:")
                for spot in problem_spots:
                    print(f"- {spot['attraction']} (第{spot['current_day']}天): MisFit={spot['misfit']:.2f}")
                    print(f"  建议移至第{spot['recommended_day']}天，可减少{spot['improvement']}通勤成本")

            # 使用90%和95%分位数
            p90 = np.percentile(csm_values, 90)
            p95 = np.percentile(csm_values, 95)
            print(f"90%分位数(P90): {p90:.2f}")
            print(f"95%分位数(P95): {p95:.2f}")

            return {
                # 'misfit_value': csm_values,
                # 'problem_spots': problem_spots,
                'P90': p90,
                'P95': p95
            }

        except Exception as e:
            print(f"CSM 计算错误: {e}")
            return {}  # 最差情况

    def _calculate_space_score(self, results: Dict[str, float]) -> float:
        """计算空间维度综合得分"""
        RP_score = max(0, 1 - results.get('RP', 1))
        CSM_score = max(0, 1 - min(results.get('CSM', 1), 1))

        return (RP_score * 0.6 + CSM_score * 0.4) * 100
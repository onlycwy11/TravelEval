import json
import os
from typing import Optional
from pydantic import ValidationError
from agent.schemas.travel_plan import (
    FinalTravelPlan,
    Accommodation,
    DailyPlan,
    DailyActivity,
    DailyEndingPoint,
    TransportType,
    ItineraryContent
)


class POIMatcher:
    def __init__(self, city_pinyin):
        # 加载POI数据库路径
        db_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', 'environment', 'database', 'poi', city_pinyin, 'poi.json'
        )
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                self.poi_db = json.load(f)
        except FileNotFoundError:
            self.poi_db = []
            print(f"Warning: POI database not found at {db_path}")
        except json.JSONDecodeError:
            self.poi_db = []
            print(f"Warning: Invalid JSON format in POI database at {db_path}")

    def match_pois(self, plan: FinalTravelPlan) -> FinalTravelPlan:
        """匹配旅行计划中的POI与数据库中的POI"""
        try:
            # 处理每日计划中的POI
            if plan.itinerary.daily_plans:
                for day_plan in plan.itinerary.daily_plans:
                    # 处理每日活动中的POI
                    for activity in day_plan.activities:
                        if hasattr(activity, 'location_name') and activity.location_name:
                            matched_poi = self._find_best_match(activity.location_name)
                            if matched_poi:
                                # 更新活动信息
                                activity.location_name = matched_poi

                    # 处理终点POI
                    matched_ending = self._match_activity_poi(day_plan.ending_point)
                    # 更新终点信息
                    day_plan.ending_point = matched_ending

            # 处理城际交通中的POI
            if plan.itinerary.accommodation:
                accommodation = plan.itinerary.accommodation
                matched_accommodation = self._match_accommodation_poi(accommodation)
                plan.itinerary.accommodation = matched_accommodation

            return plan
        except ValidationError as e:
            print(f"Validation error during POI matching: {e}")
            return plan

    def _match_activity_poi(self, activity: DailyActivity) -> Optional[DailyActivity]:
        """匹配活动中的POI（如景点、餐饮、酒店）"""

        # 示例：假设我们有一个地点名称需要匹配
        if hasattr(activity, 'location_name') and activity.location_name:
            matched_poi = self._find_best_match(activity.location_name)
            if matched_poi:
                # 更新活动信息
                activity.location_name = matched_poi
        return activity

    def _match_accommodation_poi(self, accommodation: Accommodation) -> Optional[Accommodation]:
        """匹配活动中的POI（如景点、餐饮、酒店）"""

        # 示例：假设我们有一个地点名称需要匹配
        if hasattr(accommodation, 'hotel_name') and accommodation.hotel_name:
            matched_poi = self._find_best_match(accommodation.hotel_name)
            if matched_poi:
                # 更新酒店信息
                accommodation.hotel_name = matched_poi
        return accommodation


    def _find_best_match(self, name: str) -> str:
        """在数据库中查找最佳匹配的POI"""
        if not self.poi_db:
            return ''

        # 简单实现：精确匹配名称
        for db_poi in self.poi_db:
            if db_poi.get('name') == name:
                return db_poi.get('name')

        # 可以添加模糊匹配逻辑
        # 例如：计算相似度，返回最接近的匹配

        return ''


def creat_plan():
    return {
        "query_uid": "T0001",
        "itinerary": {
            "summary": {
                'total_days': 3,
                'total_travelers': 2,
                'departure': "北京",
                'destination': "上海",
                'total_budget': 3400,
                'calculated_total_cost': 3300,
                'is_within_budget': True
            },
            "accommodation": {
                "hotel_name": "上海静安瑞吉酒店",
                "room_type": [
                    {
                        "type": "大床房",
                        "quantity": 1,
                        "price_per_night": 800,
                        "nights": 2
                    }
                ],
                "total_cost": 1600
            },
            "intercity_transport": {
                "transport_type": [
                    {
                        "description": "乘坐高铁从北京前往上海",
                        "start_time": "07:00",
                        "end_time": "12:00",
                        "location_name": "上海虹桥站",
                        "cost": 693.75,
                        "transportation_to": "高铁",
                        "transportation_cost": "693.75",
                        "details": {
                            "transport_number": "G101",
                            "price": 693.75,
                            "number": 2
                        }
                    },
                    {
                        "description": "乘坐高铁返回北京",
                        "start_time": "15:00",
                        "end_time": "21:00",
                        "location_name": "北京南站",
                        "cost": "693.75",
                        "transportation_to": "高铁",
                        "transportation_cost": "693.75",
                        "details": {
                            "transport_number": "G20",
                            "price": 693.75,
                            "number": 2
                        }
                    }
                ],
                "total_cost": 1387.50
            },
            "daily_plans": [
                {
                    "day": 1,
                    "date": "2024-11-15",
                    "starting_point": "上海虹桥站",
                    "ending_point": {
                        "type": "accommodation",
                        "description": "从南京路返回酒店",
                        "start_time": "21:30",
                        "end_time": "22:00",
                        "location_name": "上海静安瑞吉酒店",
                        "cost": 0,
                        "transportation_to": "地铁",
                        "transportation_cost": 5,
                        "details": {
                            "line": "2号线"
                        }
                    },
                    "activities": [
                        {
                            "type": "accommodation_check_in",
                            "description": "入住酒店，放下行李，稍作休息",
                            "start_time": "13:00",
                            "end_time": "14:00",
                            "location_name": "上海静安瑞吉酒店",
                            "cost": "800",
                            "transportation_to": "地铁",
                            "transportation_cost": "10",
                            "details": {
                                "room_type": "豪华大床房"
                            }
                        },
                        {
                            "type": "attraction",
                            "description": "游览外滩，欣赏黄浦江两岸风光",
                            "start_time": "14:30",
                            "end_time": "17:00",
                            "location_name": "外滩",
                            "cost": "0",
                            "transportation_to": "步行",
                            "transportation_cost": "0",
                            "details": {}
                        },
                        {
                            "type": "meal",
                            "description": "在外滩附近享用晚餐，品尝上海本帮菜",
                            "start_time": "17:30",
                            "end_time": "19:00",
                            "location_name": "老正兴菜馆(福州路店)",
                            "cost": "300",
                            "transportation_to": "步行",
                            "transportation_cost": "0",
                            "details": {
                                "cuisine": "上海本帮菜"
                            }
                        },
                        {
                            "type": "attraction",
                            "description": "游览南京路步行街，体验上海的繁华商业",
                            "start_time": "19:30",
                            "end_time": "21:30",
                            "location_name": "南京路步行街",
                            "cost": "0",
                            "transportation_to": "地铁",
                            "transportation_cost": "5",
                            "details": {}
                        }
                    ]
                },
                {
                    "day": 2,
                    "date": "2024-11-16",
                    "starting_point": "上海静安瑞吉酒店",
                    "ending_point": {
                        "type": "accommodation",
                        "description": "从迪士尼返回酒店",
                        "start_time": "19:00",
                        "end_time": "20:00",
                        "location_name": "上海静安瑞吉酒店",
                        "cost": "0",
                        "transportation_to": "地铁",
                        "transportation_cost": "10",
                        "details": {
                            "line": "11号线"
                        }
                    },
                    "activities": [
                        {
                            "type": "attraction",
                            "description": "参观上海迪士尼乐园，享受一天的欢乐时光",
                            "start_time": "08:30",
                            "end_time": "19:00",
                            "location_name": "上海迪士尼度假区",
                            "cost": "1000",
                            "transportation_to": "地铁",
                            "transportation_cost": "10",
                            "details": {
                                "ticket_type": "一日票"
                            }
                        },
                        {
                            "type": "meal",
                            "description": "在迪士尼乐园内餐厅享用午餐和晚餐",
                            "start_time": "12:00",
                            "end_time": "19:00",
                            "location_name": "上海迪士尼度假区",
                            "cost": "400",
                            "transportation_to": "园内步行",
                            "transportation_cost": "0",
                            "details": {
                                "cuisine": "国际美食"
                            }
                        }
                    ]
                },
                {
                    "day": 3,
                    "date": "2024-11-17",
                    "starting_point": "上海静安瑞吉酒店",
                    "ending_point": {
                        "type": "transport_to_station",
                        "description": "从酒店前往上海虹桥站",
                        "start_time": "14:00",
                        "end_time": "14:30",
                        "location_name": "上海虹桥站",
                        "cost": "10",
                        "transportation_to": "地铁",
                        "transportation_cost": "10",
                        "details": {
                            "line": "2/10/17号线"
                        }
                    },
                    "activities": [
                        {
                            "type": "attraction",
                            "description": "游览东方明珠塔，俯瞰上海全景",
                            "start_time": "09:00",
                            "end_time": "11:00",
                            "location_name": "东方明珠",
                            "cost": "300",
                            "transportation_to": "地铁",
                            "transportation_cost": "5",
                            "details": {
                                "ticket_type": "观光票"
                            }
                        },
                        {
                            "type": "meal",
                            "description": "在东方明珠附近的餐厅享用午餐",
                            "start_time": "11:30",
                            "end_time": "13:00",
                            "location_name": "上海中心J酒店·锦上田舍 Kinnjyou Inaka",
                            "cost": "400",
                            "transportation_to": "步行",
                            "transportation_cost": "0",
                            "details": {
                                "cuisine": "日式料理"
                            }
                        },
                        {
                            "type": "accommodation_check_out",
                            "description": "办理酒店退房手续",
                            "start_time": "13:30",
                            "end_time": "14:00",
                            "location_name": "上海静安瑞吉酒店",
                            "cost": "0",
                            "transportation_to": "步行",
                            "transportation_cost": "0",
                            "details": {}
                        }
                    ]
                }
            ],
            "cost_breakdown": {
            "attractions": "1300",
            "intercity_transportation": "1387.50",
            "intracity_transportation": "30",
            "accommodation": "800",
            "meals": "1100",
            "other": "0",
            "total": "3300"
        }
        }
    }

if __name__ == "__main__":
    plan = creat_plan()
    matcher = POIMatcher('shanghai')

    plan_new = matcher.match_pois(plan)
    print(plan_new)
import copy
import os
import sys
import json
import mail
import math
import time
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from threading import Lock
from typing import List, Dict, Tuple, Optional, Any
from collections import ChainMap
import requests  # 用于调用高德API
from pypinyin import pinyin, Style
from sklearn.cluster import KMeans
from core.utils.plan_extractors import PlanExtractor
from core.utils.config import ConfigManager
from core.utils.data_loader import DataLoader
from core.utils.geo_calculator import GeoCalculator

# 获取当前文件的绝对路径
current_file = os.path.abspath(__file__)
DATA_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
CACHE_FILE = os.path.join(DATA_BASE_DIR, "core", "geo_cache.json")
print(CACHE_FILE)

config_manager = ConfigManager()
target_density_map = config_manager.get_metric_config('utility').get('target_attraction_density')
print(target_density_map)
min_density = min(target_density_map.values())

APIs = config_manager.get_apis_config()

special_city_pair = {
    frozenset({"上海", "广州"}),
    frozenset({"上海", "成都"}),
    frozenset({"上海", "深圳"}),
    frozenset({"上海", "重庆"}),
    frozenset({"北京", "广州"}),
    frozenset({"北京", "成都"}),
    frozenset({"北京", "深圳"}),
    frozenset({"北京", "重庆"}),
    frozenset({"南京", "广州"}),
    frozenset({"南京", "成都"}),
    frozenset({"南京", "深圳"}),
    frozenset({"南京", "重庆"}),
    frozenset({"广州", "成都"}),
    frozenset({"广州", "杭州"}),
    frozenset({"广州", "苏州"}),
    frozenset({"广州", "重庆"}),
    frozenset({"成都", "杭州"}),
    frozenset({"成都", "武汉"}),
    frozenset({"成都", "深圳"}),
    frozenset({"成都", "苏州"}),
    frozenset({"杭州", "深圳"}),
    frozenset({"杭州", "重庆"}),
    frozenset({"深圳", "苏州"}),
    frozenset({"深圳", "重庆"}),
    frozenset({"苏州", "重庆"}),
}

all_stations = {
    "train": {
        '广州增城站', '武汉武昌站', '苏州园区站', '成都西站', '广州新塘站', '成都南站', '广州站', '深圳福田站',
        '广州南站', '南京南站', '深圳北站', '杭州南站', '北京丰台站', '北京西站', '杭州站', '南京站', '武汉站',
        '重庆江北机场站', '重庆东站', '苏州盛泽站', '深圳站', '苏州南站', '北京清河站', '广州东站', '上海金山北站',
        '苏州常熟站', '苏州北站', '武汉汉口站', '上海站', '杭州东站', '重庆沙坪坝站', '杭州西站', '苏州站',
        '重庆北站', '广州白云站', '北京南站', '深圳东站', '重庆西站', '广州北站', '苏州张家港站', '北京站',
        '上海练塘站', '苏州太仓站', '成都东站', '苏州新区站', '南京仙林站', '成都犀浦站', '北京大兴站', '上海南站',
        '北京亦庄站', '上海西站', '苏州太仓南站', '上海虹桥站', '上海松江站'
    },
    # {
    #     '北京西站', '重庆西站', '杭州西站', '北京南站', '南京南站', '苏州站',
    #     '苏州南站', '成都西站', '深圳北站', '广州白云站', '上海虹桥站', '南京站',
    #     '深圳机场北站', '广州东站', '广州站', '重庆北站', '北京丰台站', '上海站',
    #     '杭州东站', '深圳坪山站', '杭州站', '武汉站', '广州北站', '北京站',
    #     '苏州新区站', '成都南站', '广州南站', '深圳站', '上海南站', '深圳机场站',
    #     '上海西站', '苏州北站', '深圳东站', '杭州南站', '成都东站', '苏州园区站'
    # },
    "airplane": {
        '南京禄口国际机场', '广州白云国际机场', '上海浦东国际机场', '成都天府国际机场',
        '北京首都国际机场', '重庆江北国际机场', '成都双流国际机场', '深圳宝安国际机场',
        '上海虹桥国际机场', '武汉天河国际机场', '杭州萧山国际机场', '北京大兴国际机场',
    }
}

# 每日花销范围（除城际交通）和 对应的可接受餐饮比例
daily_costs_range = {
    "经济": (100, 500, 25),
    "中等": (500, 100, 50),
    "高端": (1000, 5000, 100)
}


class TravelPlanner:
    def __init__(self, user_query: Dict, cache_file="travel_time_cache.json"):
        """
        初始化旅行规划器
        :param user_query: 用户输入字典，包含预算、人数、偏好、天数等
        """
        self.data_loader = DataLoader()
        self.geo_calculator = GeoCalculator(CACHE_FILE)
        self.apis = APIs
        self.geo_calculator.set_gaode_api_key(self.apis['gaode_api_key'])

        self.user_query = user_query
        self.uid = user_query["uid"]
        self.start_city = user_query["start_city"]
        self.target_city = user_query["target_city"]
        self.budget = user_query["budget"]
        self.num_people = user_query["people_number"]
        self.people_composition = user_query["people_composition"]

        self.preferences = {
            "attraction_preferences": user_query["attractions"].get("preferences", []),
            "attraction_constraints": user_query["attractions"].get("constraints", []),
            "accommodation_preferences": user_query["accommodations"].get("preferences", []),
            "accommodation_constraints": user_query["accommodations"].get("constraints", []),
            "transportation_preferences": user_query["transportation"].get("preferences", []),
            "transportation_constraints": user_query["transportation"].get("constraints", []),
            "restaurant_preferences": user_query["diet"].get("preferences", []),
            "restaurant_constraints": user_query["diet"].get("constraints", []),
            "rhythm_preferences": user_query["rhythm"].get("preferences", []),
            "rhythm_constraints": user_query["rhythm"].get("constraints", [])
        }
        self.travel_days = user_query["days"]

        # single_room,king_room,double_bed,family_room
        self.accommodation_type = self.extract_room_num()
        # print(self.accommodation_type)

        city_pair = frozenset({self.start_city, self.target_city})
        if city_pair in special_city_pair:
            self.long_intercity = True
        else:
            self.long_intercity = False

        travel_style = PlanExtractor._determine_travel_style(user_query)  # 默认"普通"
        target_density = target_density_map.get(travel_style, 3.54)  # 默认3.54
        print(target_density)
        if target_density > 5:
            target_density -= 1

        if self.long_intercity and self.travel_days > 2:
            self.total_attractions_needed = target_density * (self.travel_days - 2)  # 首日末日涉及城际交通，而城际交通时间较长
        elif target_density > 4:
            self.total_attractions_needed = target_density * (self.travel_days - 1)  # 默认首日和末日只有半天可供游玩
        else:
            self.total_attractions_needed = target_density * self.travel_days  # 默认每日2个景点

        target_city_pinyin = self._chinese_to_pinyin(self.target_city)
        start_city_pinyin = self._chinese_to_pinyin(self.start_city)
        # 加载数据
        sandbox = self.data_loader.load_sandbox_data(self.target_city)
        self.attractions = sandbox["attractions"]
        self.accommodations = sandbox["accommodations"]
        self.restaurants = sandbox["restaurants"]
        self.pois = sandbox["poi_coordinates"]
        self.intercity = self.data_loader.load_intercity_transport(self.start_city, self.target_city)

        self.cache_file = cache_file
        self.cache = {}  # 内存缓存
        self.cache_lock = Lock()  # 多线程安全锁（可选）
        self._load_cache()  # 启动时加载缓存文件

    def extract_room_num(self):
        accommodation_type = {
            "single_room": 0,
            "two_bed": 0,
            "family_room": 0
        }
        if self.num_people == 1:
            accommodation_type["single_room"] = 1
        elif self.num_people == 2:
            accommodation_type["two_bed"] = 1
        else:
            adults = self.people_composition["adults"]
            children = self.people_composition["children"]
            seniors = self.people_composition["seniors"]

            if children == 0:
                two_bed = self.num_people // 2
                accommodation_type["two_bed"] = two_bed
                accommodation_type["single_room"] = self.num_people - two_bed * 2
            elif children == 1:
                accommodation_type["family_room"] = 1
                two_bed = (self.num_people - 3) // 2
                accommodation_type["two_bed"] = two_bed
                accommodation_type["single_room"] = self.num_people - 3 - two_bed * 2
            elif children == 2:
                adult_people = adults + seniors
                if adult_people == 1:
                    accommodation_type["family_room"] = 1
                elif adult_people == 2:
                    accommodation_type["two_bed"] = 2
                else:
                    family_room = self.num_people // 3
                    accommodation_type["family_room"] = family_room
                    two_bed = (self.num_people - family_room * 3) // 2
                    accommodation_type["two_bed"] = two_bed
            else:
                if self.num_people == 4:
                    accommodation_type["two_bed"] = 2
                else:
                    family_room = self.num_people // 3
                    accommodation_type["family_room"] = family_room
                    two_bed = (self.num_people - family_room * 3) // 2
                    accommodation_type["two_bed"] = two_bed

        return accommodation_type

    def _chinese_to_pinyin(self, city_name: str) -> str:
        """将中文城市名转换为拼音"""
        pinyin_list = pinyin(city_name, style=Style.NORMAL)
        return ''.join([item[0] for item in pinyin_list]).lower()

    def str_to_float(self, time_str: str) -> float:
        hours, minutes = map(int, time_str.split(":"))
        total_minutes = hours * 60 + minutes
        return total_minutes / 60

    def extract_poi_names(self, attractions: list) -> list:
        """
        从 attractions 数据列表中提取所有景点名称
        :param attractions: 景点数据列表，每个元素是一个字典，包含 'name' 字段
        :return: 景点名称列表
        """
        return [
            attraction.get("name") for attraction in attractions
            if isinstance(attraction, dict) and "name" in attraction
        ]

    def extract_attractions_details(self, attraction_name: str):
        for attraction in self.attractions.to_dict("records"):
            if attraction_name == attraction["name"]:
                return attraction

        return {}

    def extract_restaurant_details(self, restaurant_name: str):
        for restaurant in self.restaurants.to_dict("records"):
            if restaurant_name == restaurant["name"]:
                return restaurant

        return {}

    def extract_min_intercity_cost(self):
        min_cost = float('inf')
        for value in self.intercity.values():
            for intercity_dict in value:
                cost = intercity_dict['Cost']
                if cost is not None and cost < min_cost:
                    min_cost = cost
        return min_cost

    def get_poi_coordinates(self, poi_names: List[str]) -> Dict[str, Tuple[float, float]]:
        """
        从 self.pois（列表格式）查询指定景点的坐标
        :param poi_names: 要查询的 POI 名称列表
        :return: 字典 { "景点名": [lat, lng], ... }
        """
        coordinates = {}
        for poi in self.pois:  # self.pois 是列表，如 [{'name': '北京站', 'position': [lat, lng]}, ...]
            if isinstance(poi, dict) and "name" in poi and "position" in poi:
                if poi["name"] in poi_names:
                    position = poi["position"]
                    if isinstance(position, list) and len(position) == 2:
                        coordinates[poi["name"]] = tuple(position)  # 直接存储 [lat, lng]
                        # 如果已经找到所有需要的坐标，提前退出循环
                        if len(coordinates) == len(poi_names):
                            break

        return coordinates

    def _filter_attractions_by_preference(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        根据用户偏好筛选景点
        :return: (偏好匹配景点, 无偏好备选景点)
        """
        max_price = max(
            (self.budget - self.extract_min_intercity_cost() * 2 * self.num_people
             ) / self.total_attractions_needed / self.num_people, 0.0
        )
        filter_by_price = self.attractions[self.attractions["price"] <= max_price]
        preferred = filter_by_price.copy()

        # 匹配任意一个 pref 就保留
        if self.preferences["attraction_preferences"]:
            # 初始化为全 False（默认不匹配）
            mask_pref = pd.Series(False, index=preferred.index)
            for pref in self.preferences["attraction_preferences"]:
                mask_pref = mask_pref | preferred["type"].str.contains(pref, na=False)
            preferred = preferred[mask_pref]

        # 匹配任意一个 const 就删除
        if self.preferences["attraction_constraints"]:
            mask_const = pd.Series(False, index=preferred.index)
            for const in self.preferences["attraction_constraints"]:
                mask_const = mask_const | preferred["type"].str.contains(const, na=False)
            preferred = preferred[~mask_const]

        # 备选景点（排除已选中的偏好景点）
        backup = filter_by_price[~filter_by_price["id"].isin(preferred["id"])]

        if not len(backup):
            backup, preferred = preferred, backup

        print(len(preferred))
        print(len(backup))

        # 使用star列而不是rating列（根据你的数据）
        return preferred.sort_values("star", ascending=False), backup.sort_values("star", ascending=False)

    def _filter_accommodations_by_preference(self) -> pd.DataFrame:
        """
        根据用户偏好筛选酒店
        :return: 偏好匹配酒店
        """
        preferred = self.accommodations.copy()

        # 匹配任意一个 pref 就保留
        if self.preferences["accommodation_preferences"]:
            # 初始化为全 False（默认不匹配）
            mask_pref = pd.Series(False, index=preferred.index)
            for pref in self.preferences["accommodation_preferences"]:
                mask_name = preferred["name"].str.contains(pref, na=False, case=False)
                mask_featurehoteltype = preferred["featurehoteltype"].str.contains(pref, na=False, case=False)
                mask_pref = mask_pref | mask_name | mask_featurehoteltype
            preferred = preferred[mask_pref]

        # 匹配任意一个 const 就删除
        if self.preferences["accommodation_constraints"]:
            mask_const = pd.Series(False, index=preferred.index)
            for const in self.preferences["accommodation_constraints"]:
                mask_name = preferred["name"].str.contains(const, na=False, case=False)
                mask_featurehoteltype = preferred["featurehoteltype"].str.contains(const, na=False, case=False)
                mask_const = mask_const | mask_name | mask_featurehoteltype
            preferred = preferred[~mask_const]

        print("匹配偏好的酒店：")
        print(len(preferred))

        return preferred

    def _filter_restaurants_by_preference(self) -> pd.DataFrame:
        """
        根据用户偏好筛选餐馆
        :return: 偏好匹配餐馆
        """
        preferred = self.restaurants.copy()

        # 匹配任意一个 pref 就保留
        if self.preferences["restaurant_preferences"]:
            # 初始化为全 False（默认不匹配）
            mask_pref = pd.Series(False, index=preferred.index)
            for pref in self.preferences["restaurant_preferences"]:
                mask_name = preferred["name"].str.contains(pref, na=False, case=False)
                mask_cuisine = preferred["cuisine"].str.contains(pref, na=False, case=False)
                mask_recommendedfood = preferred["recommendedfood"].str.contains(pref, na=False, case=False)
                mask_pref = mask_pref | mask_name | mask_cuisine | mask_recommendedfood
            preferred = preferred[mask_pref]

        # 匹配任意一个 const 就删除
        if self.preferences["attraction_constraints"]:
            mask_const = pd.Series(False, index=preferred.index)
            for const in self.preferences["attraction_constraints"]:
                mask_name = preferred["name"].str.contains(const, na=False, case=False)
                mask_cuisine = preferred["cuisine"].str.contains(const, na=False, case=False)
                mask_const = mask_const | mask_name | mask_cuisine
            preferred = preferred[~mask_const]

        print("匹配偏好的餐馆：")
        print(len(preferred))

        return preferred.sort_values("price", ascending=True)

    def _filter_restaurants_by_constraints(self) -> pd.DataFrame:
        """
        根据用户偏好筛选餐馆 - 2
        :return: 偏好匹配餐馆
        """
        preferred = self.restaurants.copy()

        # 匹配任意一个 const 就删除
        if self.preferences["attraction_constraints"]:
            mask_const = pd.Series(False, index=preferred.index)
            for const in self.preferences["attraction_constraints"]:
                mask_name = preferred["name"].str.contains(const, na=False, case=False)
                mask_cuisine = preferred["cuisine"].str.contains(const, na=False, case=False)
                mask_const = mask_const | mask_name | mask_cuisine
            preferred = preferred[~mask_const]

        print("匹配限制的餐馆：")
        print(len(preferred))

        return preferred.sort_values("price", ascending=True)

    def _filter_stations_by_preference(self) -> List:
        # intercity_type = []
        if self.preferences["transportation_preferences"]:
            if '高铁' in self.preferences["transportation_preferences"]:
                intercity_type = ["train"]
            elif '飞机' in self.preferences["transportation_preferences"]:
                intercity_type = ["airplane"]
            else:
                intercity_type = ["train", "airplane"]
        else:
            intercity_type = ["train", "airplane"]

        if self.preferences["transportation_constraints"]:
            if '高铁' in self.preferences["transportation_constraints"] and 'train' in intercity_type:
                intercity_type.remove("train")
            elif '飞机' in self.preferences["transportation_constraints"] and 'airplane' in intercity_type:
                intercity_type.remove("airplane")

        if self.start_city == '苏州' or self.target_city == '苏州':
            intercity_type = ["train"]

        filter_stations = []
        if intercity_type:
            for transport in intercity_type:
                for station in all_stations[transport]:
                    if station.startswith(self.target_city):
                        filter_stations.append(station)

        return filter_stations

    def _select_candidate_attractions(self) -> List[Dict]:
        """
        步骤(1): 筛选候选景点
        :return: 候选景点列表（含偏好匹配和无偏好备选）
        """
        preferred, backup = self._filter_attractions_by_preference()

        # 计算需要的偏好景点和备选景点数量
        num_preferred = min(len(preferred), int(self.total_attractions_needed // 2))  # 整数除法，向下取整
        num_backup = round(self.total_attractions_needed - num_preferred)  # 四舍五入

        print("备选景点数量：")
        print(num_preferred, num_backup)

        # 选择景点
        selected_preferred = preferred.head(num_preferred)
        selected_backup = backup.head(num_backup)

        # 将合并后的 DataFrame 转换成字典列表
        return pd.concat([selected_preferred, selected_backup]).to_dict("records")

    def _cluster_attractions(self, attractions: List[Dict]) -> Dict[int, List[Dict | str]]:
        """
        步骤(2): 集群分类（简化版：按地理位置聚类）
        聚类需确保簇的景点数量均衡：
        - 最大簇的景点数 ≤ 每日景点密度 * 2
        否则调整簇分配
        :return: 字典 {cluster_id: [attraction1, attraction2...]}
        """
        # 使用K-Means进行聚类
        if not attractions:
            return {}

        # 准备数据
        coords = np.array([[a["lon"], a["lat"]] for a in attractions])

        # 确定聚类数量 (旅行天数，确保每天有景点可去)
        if self.long_intercity:
            n_clusters = min(len(attractions), self.travel_days - 1)
        else:
            n_clusters = min(len(attractions), self.travel_days)
        target_density = max(self.total_attractions_needed / self.travel_days, min_density)

        # 聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(coords)

        # 组织初始簇
        clusters = {}
        for i in range(n_clusters):
            clusters[i] = [attractions[j]["name"] for j in range(len(attractions)) if labels[j] == i]

        print(clusters)

        # 检查均衡性
        cluster_sizes = [len(clusters[i]) for i in clusters]
        max_size = max(cluster_sizes)

        # 条件：最大簇的景点数 ≤ target_density * 2
        condition = (max_size <= target_density * 2)

        if condition or self.travel_days == 2:
            return clusters
        else:
            return self._adjust_imbalanced_clusters(clusters, attractions, int(target_density * 2))

    def _adjust_imbalanced_clusters(
            self,
            clusters: Dict[int, List[Dict | str]],
            attractions: List[Dict],
            max_allowed_per_cluster: int,
    ) -> Dict[int, List[Dict | str]]:
        """
        调整不均衡的簇：
        1. 找出景点数过多的簇（> max_allowed_per_cluster）。
        2. 对每个过大簇中的景点，找到距离它最近的正常“非原簇”中心，并分配到该簇。
        3. 重复直到所有簇满足大小条件。
        """
        # 初始分配：用KMeans重新聚类（保持簇数量不变）
        coords = np.array([[a["lon"], a["lat"]] for a in attractions])
        kmeans = KMeans(n_clusters=len(clusters), random_state=42, n_init=10)
        labels = kmeans.fit_predict(coords)

        if max_allowed_per_cluster > 8:
            max_allowed_per_cluster = 8
        print("最大允许簇容量：")
        print(max_allowed_per_cluster)

        # 初始化簇字典
        cluster_dict = {i: [] for i in clusters}
        for i, attraction in enumerate(attractions):
            cluster_dict[labels[i]].append(attraction)

        # 计算每个簇的中心（经纬度均值）
        cluster_centers = {}
        for cluster_id in cluster_dict:
            points = np.array([[a["lon"], a["lat"]] for a in cluster_dict[cluster_id]])
            if len(points) > 0:
                cluster_centers[cluster_id] = np.mean(points, axis=0)
            else:
                cluster_centers[cluster_id] = np.array([0.0, 0.0])  # 避免空簇

        # 调整不均衡的簇
        while True:
            cluster_sizes = [len(cluster_dict[i]) for i in cluster_dict]
            max_size = max(cluster_sizes)

            # 检查是否满足条件
            if max_size <= max_allowed_per_cluster:
                break

            # 找出所有过大的簇
            overloaded_clusters = [
                cluster_id for cluster_id in cluster_dict
                if len(cluster_dict[cluster_id]) > max_allowed_per_cluster
            ]

            if not overloaded_clusters:
                break

            # 对每个过大簇，尝试分配景点到最近的簇
            for cluster_id in overloaded_clusters:
                print(f"过大簇：{cluster_id}")
                while len(cluster_dict[cluster_id]) > max_allowed_per_cluster:
                    # print(len(cluster_dict[cluster_id]))
                    # 获取当前簇的所有景点
                    attractions_in_cluster = cluster_dict[cluster_id].copy()
                    if not attractions_in_cluster:
                        break

                    # 找到距离其他簇中心最近的景点
                    min_distance = float("inf")
                    best_attraction = None
                    best_target_cluster = None

                    for attraction in attractions_in_cluster:
                        attraction_coord = np.array([attraction["lon"], attraction["lat"]])
                        # print(attraction_coord)

                        # 计算该景点到所有其他簇中心的距离
                        distances = {}
                        for target_cluster_id in cluster_centers:
                            # 不能分配回原簇 或 任意过大簇
                            if target_cluster_id not in overloaded_clusters \
                                    and len(cluster_dict[target_cluster_id]) < max_allowed_per_cluster:
                                # # 计算欧式距离
                                # dist = np.linalg.norm(attraction_coord - cluster_centers[target_cluster_id])
                                # 计算大圆距离
                                dist = self.geo_calculator.haversine_distance(
                                    attraction_coord[1],
                                    attraction_coord[0],
                                    cluster_centers[target_cluster_id][1],
                                    cluster_centers[target_cluster_id][0]
                                )
                                distances[target_cluster_id] = dist

                        # 找到最近的簇
                        if distances:
                            # get 方法，等价于 key=lambda x: distances[x]，对每个簇ID x，返回它的距离
                            closest_cluster = min(distances, key=distances.get)
                            closest_dist = distances[closest_cluster]

                            # 记录全局最优（距离最近的景点分配）
                            if closest_dist < min_distance:
                                min_distance = closest_dist
                                best_attraction = attraction
                                best_target_cluster = closest_cluster

                    # 执行分配
                    if best_attraction and best_target_cluster is not None:
                        cluster_dict[cluster_id].remove(best_attraction)
                        cluster_dict[best_target_cluster].append(best_attraction)
                        # 更新目标簇的中心（近似：重新计算均值）
                        new_points = np.array([[a["lon"], a["lat"]] for a in cluster_dict[best_target_cluster]])
                        cluster_centers[best_target_cluster] = np.mean(new_points, axis=0)
                    else:
                        break

        new_cluster_dict = {}
        for cluster_id, attractions in cluster_dict.items():
            new_cluster_dict[cluster_id] = [attraction["name"] for attraction in attractions]

        return new_cluster_dict

    def get_clusters_with_recommended_time(
            self, clusters: Dict, attractions_list: List[Dict]) -> Tuple[List, int, int | None]:
        """
        修正版：获取集群大小和推荐时间信息

        Args:
            clusters: 集群字典 {cluster_id: [景点名列表]}
            attractions_list: 景点详细数据列表

        Returns:
            (cluster_sizes_with_time, smallest_cluster, second_smallest_cluster)
            cluster_sizes_with_time: [(大小, 平均推荐时间, cluster_id), ...]
            smallest_cluster: 最小集群ID
            second_smallest_cluster: 次小集群ID（考虑游览时间）
        """
        # 创建景点名到详细信息的映射
        attraction_map = {attr['name']: attr for attr in attractions_list}

        # 计算每个集群的大小和平均推荐时间
        cluster_info = []

        for cluster_id, attraction_names in clusters.items():
            size = len(attraction_names)
            avg_recommended_time = 0

            if size > 0:
                total_time = 0
                valid_attractions = 0

                for name in attraction_names:
                    if name in attraction_map:
                        attr = attraction_map[name]
                        # 计算推荐时间的平均值
                        min_time = attr.get('recommendmintime', 1.0)  # 默认1小时
                        max_time = attr.get('recommendmaxtime', 2.0)  # 默认2小时
                        avg_time = (min_time + max_time) / 2
                        total_time += avg_time
                        valid_attractions += 1

                if valid_attractions > 0:
                    avg_recommended_time = total_time / valid_attractions

            cluster_info.append({
                'cluster_id': cluster_id,
                'size': size,
                'avg_time': avg_recommended_time
            })

        # 首先按大小排序，然后按平均游览时间排序
        # 先找到最小的大小值
        min_size = min(info['size'] for info in cluster_info)

        # 找到所有最小大小的集群
        min_size_clusters = [info for info in cluster_info if info['size'] == min_size]

        # 如果有多个最小集群，按平均游览时间排序，选择时间最短的
        if len(min_size_clusters) > 1:
            min_size_clusters.sort(key=lambda x: x['avg_time'])
            # 最小的集群就是第一个
            smallest_cluster = min_size_clusters[0]['cluster_id']
            # 次小的集群就是第二个
            second_smallest_cluster = min_size_clusters[1]['cluster_id']

        else:
            # 最小的集群就是第一个
            smallest_cluster = min_size_clusters[0]['cluster_id']

            # 找到次小集群
            # 首先获取比最小大小大的集群
            larger_clusters = [info for info in cluster_info if info['size'] > min_size]

            if not larger_clusters:
                # 如果没有更大的集群，说明所有集群大小相同
                # 理论上不会存在
                second_smallest_cluster = None
                if len(min_size_clusters) > 1:
                    # 选择平均游览时间第二短的作为次小
                    second_smallest_cluster = min_size_clusters[1]['cluster_id']
            else:
                # 找到次小的大小值
                second_min_size = min(info['size'] for info in larger_clusters)

                # 找到所有次小大小的集群
                second_min_clusters = [info for info in larger_clusters if info['size'] == second_min_size]

                # 如果有多个次小集群，按平均游览时间排序，选择时间最短的
                if len(second_min_clusters) > 1:
                    second_min_clusters.sort(key=lambda x: x['avg_time'])

                second_smallest_cluster = second_min_clusters[0]['cluster_id']

        # 准备返回的格式
        cluster_sizes_with_time = [
            (info['size'], info['avg_time'], info['cluster_id'])
            for info in cluster_info
        ]
        # print(f"次小：{second_smallest_cluster}")

        return cluster_sizes_with_time, smallest_cluster, second_smallest_cluster

    def assign_clusters_to_days(self, clusters: Dict[int, List[Dict | str]], attractions_list: List[Dict]) -> Dict[
        int, int]:
        """
        将集群分配到具体的旅行天数

        Returns:
            字典 {集群ID: 旅行第几天}
        """
        cluster_days = {}

        # 获取最小和次小集群
        if clusters:
            cluster_info, smallest_cluster, second_smallest_cluster = self.get_clusters_with_recommended_time(
                clusters, attractions_list
            )

            cluster_info.sort(key=lambda x: (x[0], x[1]))  # 先按大小，再按时间'

            cluster_sizes = []
            for info in cluster_info:
                size, avg_time, cluster_id = info
                cluster_sizes.append((size, cluster_id))
                print(f"集群：{cluster_id}，预计游览时间：{size * avg_time}")

            # 验证前提条件
            if len(cluster_sizes) > self.travel_days:
                raise ValueError(f"集群数量({len(cluster_sizes)})超过了旅行天数({self.travel_days})")

        else:
            return {}

        if self.long_intercity:
            # 长途城际旅行模式，第一天无集群（作为交通/调整日）
            # 最小集群安排在最后一天
            # 其他集群随机安排

            # 将最小集群安排在最后一天
            cluster_days[smallest_cluster] = self.travel_days

            if len(cluster_sizes) > 1:
                # 所有可用天数（从第2天开始，到倒数第二天结束）
                # 参考：available_days = [2, 3, 4, 5, 6, 7]
                available_days = list(range(2, self.travel_days))  # 第2天到倒数第2天

                # 随机安排其他集群
                remaining_clusters = [cid for size, cid in cluster_sizes[1:]]

                # 确保有足够的天数
                if len(remaining_clusters) > len(available_days):
                    raise ValueError(f"剩余集群数量({len(remaining_clusters)})超过可用天数({len(available_days)})")

                random.shuffle(available_days)
                for cluster_id, day in zip(remaining_clusters, available_days):
                    cluster_days[cluster_id] = day

        else:
            # 短途旅行模式，最小集群安排在第一天
            # 次小集群最后一天
            # 其他集群随机安排

            # 最小集群第一天
            cluster_days[smallest_cluster] = 1

            # 次小集群最后一天
            if second_smallest_cluster is not None:
                cluster_days[second_smallest_cluster] = self.travel_days

            if len(cluster_sizes) > 2:
                # 剩余天数和集群，排除第1天和最后一天
                remaining_days = list(range(2, self.travel_days))

                remaining_clusters = [cid for size, cid in cluster_sizes[2:]]

                # 确保有足够的天数
                if len(remaining_clusters) > len(remaining_days):
                    raise ValueError(f"剩余集群数量({len(remaining_clusters)})超过可用天数({len(remaining_days)})")

                # 随机安排
                random.shuffle(remaining_days)
                for cluster_id, day in zip(remaining_clusters, remaining_days):
                    cluster_days[cluster_id] = day

        return cluster_days

    def extract_daily_attractions(
            self, clusters: Dict[int, List[Dict | str]], cluster_days: Dict[int, int], coordinates: Dict[str, Tuple]):
        """
        确定每日最佳访问顺序
        :param clusters: 集群
        :param cluster_days: 集群对应的天数
        :return: 每日景点
        """
        # 反转映射：第几天 -> [集群ID列表]
        days_to_clusters = {}
        for cluster_id, day in cluster_days.items():
            days_to_clusters[day] = cluster_id

        daily_attractions = {}
        for day in range(1, self.travel_days + 1):
            if day in days_to_clusters:
                cluster_id = days_to_clusters[day]
                # 获取当天所有景点
                all_attractions = clusters[cluster_id]

                # optimal_order, optimal_total_distance = self.calculate_optimal_route(  # _ 是 Python 的惯例，表示忽略不关心的返回值。
                #     list(order),  # 所有景点
                #     coordinates,
                #     method=optimal_route_method,
                #     travel_mode="driving",  # 统一使用驾车距离
                # )
                # print(coordinates)
                optimized_order, _ = self.geo_calculator.calculate_optimal_route(
                    all_attractions,
                    coordinates,
                    travel_mode="driving"
                )

                daily_attractions[day] = optimized_order
            else:
                daily_attractions[day] = []

        return daily_attractions

    def _select_stations(self, attrations: List[str], coordinates: Dict[str, Tuple[float, float]], flag: int):
        """
            0：去程
            1：回程
        """
        index_map = {
            0: "To",
            1: "From"
        }

        points = np.array([coordinates[name] for name in attrations])
        centroid = np.mean(points, axis=0)

        raw_stations = self._filter_stations_by_preference()
        stations = set()
        for station in raw_stations:
            for value in self.intercity.values():
                for intercity_dict in value:
                    if intercity_dict[index_map[flag]] == station:
                        stations.add(station)
                        break
                    else:
                        continue

        stations = list(stations)

        # 找离集群中心最近的车站
        min_dist = float("inf")
        optimal_station = ""
        stations_coord = self.get_poi_coordinates(stations)
        for station in stations:
            dist = self.geo_calculator.haversine_distance(
                stations_coord[station][0],
                stations_coord[station][1],
                centroid[0],
                centroid[1]
            )

            if dist < min_dist:
                min_dist = dist
                optimal_station = station

        return optimal_station

    def _select_intercity(self, station1, station2, attractions_day1, attractions_dayn, attractions_list):
        """
        步骤(6): 规划城际交通（根据偏好选择）
        """
        # 去程
        if station1.endswith("机场"):
            optional_intercity = self.intercity["airplane"]
        else:
            optional_intercity = self.intercity["train"]

        if len(attractions_day1) == 0:
            latest_time = 24.00
        else:
            _, close_time = self.start_close_time(attractions_day1, attractions_list)
            latest_time = close_time - len(attractions_day1) * 1.5

        min_cost = float('inf')
        min_start_info = None
        for intercity_info in optional_intercity:
            if not self.long_intercity and (intercity_info["Duration"] > 9 or self.str_to_float(
                    intercity_info["EndTime"]) > 6):
                continue
            if intercity_info["To"] == station1:
                arrived_time = self.str_to_float(intercity_info["EndTime"])
                cost = intercity_info["Cost"]
                if cost is None:
                    continue
                if latest_time > arrived_time and min_cost > cost:
                    min_cost = cost
                    min_start_info = intercity_info

        if min_start_info is None:
            print("没有满足时间要求的出发城际行程！")
            end_time = float('inf')
            for intercity_info in optional_intercity:
                if intercity_info["To"] == station1:
                    arrived_time = self.str_to_float(intercity_info["EndTime"])
                    if arrived_time < end_time:
                        end_time = arrived_time
                        min_start_info = intercity_info

        # 返程
        if station2.endswith("机场"):
            optional_intercity = self.intercity["airplane"]
        else:
            optional_intercity = self.intercity["train"]

        if len(attractions_dayn) == 0:
            earliest_time = 0.00
        else:
            start_time, _ = self.start_close_time(attractions_dayn, attractions_list)
            earliest_time = start_time + len(attractions_dayn) * 1.5

        min_cost = float('inf')
        min_end_info = None
        for intercity_info in optional_intercity:
            if intercity_info["From"] == station2:
                begin_time = self.str_to_float(intercity_info["BeginTime"])
                cost = intercity_info["Cost"]
                if cost is None:
                    continue
                if earliest_time < begin_time and min_cost > cost:
                    min_cost = cost
                    min_end_info = intercity_info

        if min_end_info is None:
            print("没有满足时间要求的返程城际行程！")
            start_time = 0.0
            for intercity_info in optional_intercity:
                if intercity_info["From"] == station2:
                    begin_time = self.str_to_float(intercity_info["BeginTime"])
                    if begin_time > start_time:
                        start_time = begin_time
                        min_end_info = intercity_info

        return min_start_info, min_end_info

    def start_close_time(self, attractions, attractions_list):
        start_time = 24.00
        close_time = 0.00
        for info in attractions_list:
            if info["name"] in attractions:
                opentime = self.str_to_float(info["opentime"])
                endtime = self.str_to_float(info["endtime"])
                if opentime < start_time:
                    start_time = opentime

                if endtime > close_time:
                    close_time = endtime

        return start_time, close_time

    def float_to_time(self, float_time):
        hours = int(float_time)
        minutes = int(round((float_time - hours) * 60))

        return f"{hours}:{minutes:02d}"

    def _select_accommodation(
            self, budget: float, nights: int, attrations: List[str], coordinates: Dict[str, Tuple[float, float]]
    ) -> Tuple[Dict, List]:
        """
        步骤(3): 选择酒店（价格区间内最近）
        """
        if budget / nights < 10:
            print("预算严重不足！")
            budget = 10 * nights

        points = np.array([coordinates[name] for name in attrations])
        centroid = np.mean(points, axis=0)

        accommodations = self._filter_accommodations_by_preference().to_dict("records")

        min_dist = float('inf')
        accommodation_info = None
        final_room_type = []
        # 筛选价格区间内的酒店
        for accommodation in accommodations:
            single_room_price = accommodation["single_room_price"]
            single_room_stock = accommodation["single_room_stock"]
            king_room_price = accommodation["king_room_price"]
            king_room_stock = accommodation["king_room_stock"]
            double_bed_price = accommodation["double_bed_price"]
            double_bed_stock = accommodation["double_bed_stock"]
            family_room_price = accommodation["family_room_price"]
            family_room_stock = accommodation["family_room_stock"]

            # print(single_room_stock, king_room_stock, double_bed_stock, family_room_stock)
            # print(single_room_price)

            # print(self.accommodation_type)
            has_enough_room = True
            has_enough_king_room = True
            if single_room_stock < self.accommodation_type["single_room"]:
                has_enough_room = False
            elif king_room_stock < self.accommodation_type["two_bed"]:
                has_enough_king_room = False
            elif king_room_stock + double_bed_stock < self.accommodation_type["two_bed"]:
                has_enough_room = False
            elif family_room_stock < self.accommodation_type["family_room"]:
                has_enough_room = False

            if not has_enough_room:
                # print("没有足够的房间库存！")
                continue

            costs = single_room_price * self.accommodation_type[
                "single_room"] + king_room_price * min(king_room_stock, self.accommodation_type[
                "two_bed"]) + double_bed_price * max(self.accommodation_type[
                                                         "two_bed"] - king_room_stock, 0) + family_room_price * \
                    self.accommodation_type["family_room"]
            # print(costs)
            if costs < (budget / nights):
                dist = self.geo_calculator.haversine_distance(
                    accommodation["lat"],
                    accommodation["lon"],
                    centroid[0],
                    centroid[1]
                )

                if dist < min_dist:
                    min_dist = dist
                    accommodation_info = accommodation

                    room_type = []
                    if self.accommodation_type["single_room"]:
                        room_type.append({
                            "type": "单人房",
                            "quantity": self.accommodation_type["single_room"],
                            "price_per_night": single_room_price,
                            "nights": nights
                        })
                    if self.accommodation_type["two_bed"]:
                        if not has_enough_king_room:
                            if king_room_stock:
                                room_type.append({
                                    "type": "大床房",
                                    "quantity": king_room_stock,
                                    "price_per_night": king_room_price,
                                    "nights": nights
                                })

                            room_type.append({
                                "type": "双人房",
                                "quantity": self.accommodation_type["two_bed"] - king_room_stock,
                                "price_per_night": double_bed_price,
                                "nights": nights
                            })

                        else:
                            room_type.append({
                                "type": "大床房",
                                "quantity": self.accommodation_type["two_bed"],
                                "price_per_night": king_room_price,
                                "nights": nights
                            })
                    if self.accommodation_type["family_room"]:
                        room_type.append({
                            "type": "家庭房",
                            "quantity": self.accommodation_type["family_room"],
                            "price_per_night": family_room_price,
                            "nights": nights
                        })

                    final_room_type = room_type

        min_dist = 5.0
        while not accommodation_info:
            i = 1
            min_costs = float('inf')
            while i <= 500 and not accommodation_info:
                accommodations = self.accommodations.to_dict("records")
                for accommodation in accommodations:
                    single_room_price = accommodation["single_room_price"]
                    single_room_stock = accommodation["single_room_stock"]
                    king_room_price = accommodation["king_room_price"]
                    king_room_stock = accommodation["king_room_stock"]
                    double_bed_price = accommodation["double_bed_price"]
                    double_bed_stock = accommodation["double_bed_stock"]
                    family_room_price = accommodation["family_room_price"]
                    family_room_stock = accommodation["family_room_stock"]

                    # print(self.accommodation_type)
                    has_enough_room = True
                    has_enough_king_room = True
                    if single_room_stock < self.accommodation_type["single_room"]:
                        has_enough_room = False
                    elif king_room_stock < self.accommodation_type["two_bed"]:
                        has_enough_king_room = False
                    elif king_room_stock + double_bed_stock < self.accommodation_type["two_bed"]:
                        has_enough_room = False
                    elif family_room_stock < self.accommodation_type["family_room"]:
                        has_enough_room = False

                    if not has_enough_room:
                        # print("没有足够的房间库存！")
                        continue

                    costs = single_room_price * self.accommodation_type[
                        "single_room"] + king_room_price * min(king_room_stock, self.accommodation_type[
                        "two_bed"]) + double_bed_price * max(self.accommodation_type[
                                                                 "two_bed"] - king_room_stock, 0) + family_room_price * \
                            self.accommodation_type["family_room"]
                    if costs < (budget / nights) * i:
                        dist = self.geo_calculator.haversine_distance(
                            accommodation["lat"],
                            accommodation["lon"],
                            centroid[0],
                            centroid[1]
                        )

                        if dist < min_dist and costs < min_costs:
                            min_costs = costs
                            accommodation_info = accommodation

                            room_type = []
                            if self.accommodation_type["single_room"]:
                                room_type.append({
                                    "type": "单人房",
                                    "quantity": self.accommodation_type["single_room"],
                                    "price_per_night": single_room_price,
                                    "nights": nights
                                })
                            if self.accommodation_type["two_bed"]:
                                if not has_enough_king_room:
                                    if king_room_stock:
                                        room_type.append({
                                            "type": "大床房",
                                            "quantity": king_room_stock,
                                            "price_per_night": king_room_price,
                                            "nights": nights
                                        })

                                    room_type.append({
                                        "type": "双人房",
                                        "quantity": self.accommodation_type["two_bed"] - king_room_stock,
                                        "price_per_night": double_bed_price,
                                        "nights": nights
                                    })

                                else:
                                    room_type.append({
                                        "type": "大床房",
                                        "quantity": self.accommodation_type["two_bed"],
                                        "price_per_night": king_room_price,
                                        "nights": nights
                                    })
                            if self.accommodation_type["family_room"]:
                                room_type.append({
                                    "type": "家庭房",
                                    "quantity": self.accommodation_type["family_room"],
                                    "price_per_night": family_room_price,
                                    "nights": nights
                                })

                            final_room_type = room_type
                i += 0.5
            if not accommodation_info:
                print(f"价格范围内找不到 {min_dist} 公里内的酒店！")
            min_dist += 1.0

        return accommodation_info, final_room_type

    def _select_restaurants(
            self, budget: float, daily_attractions: Dict[int, List],
            coordinates: Dict[str, Tuple], intercity_info: Tuple[Any, Any]
    ) -> Tuple[Dict, float]:
        """
        步骤(5): 选择餐饮（偏好 + 价格区间内最近）
        """
        station_1 = intercity_info[0]["To"]
        station_2 = intercity_info[1]["From"]
        intercity1_start = intercity_info[0]["BeginTime"]
        intercity1_end = intercity_info[0]["EndTime"]

        if self.str_to_float(
                intercity1_start) > self.str_to_float(intercity1_end) or intercity_info[0]["Duration"] > 24:
            next_day = True
        else:
            next_day = False

        original_restaurants_list = self._filter_restaurants_by_constraints().to_dict("records")
        total_restaurants_list = [
            restaurant for restaurant in original_restaurants_list if restaurant["price"] < budget]
        # print(restaurants_list)
        preferred_restaurants_list = self._filter_restaurants_by_preference().to_dict("records")

        start_info = intercity_info[0]
        end_info = intercity_info[1]
        daily_restaurants = {}
        selected_restaurant_ids = set()  # 记录已经选过的餐厅ID

        for day, day_attractions in daily_attractions.items():
            num = len(day_attractions)
            daily_restaurants[day] = {}

            min_dist_1 = float('inf')
            min_dist_2 = float('inf')
            second_dist_1 = float('inf')
            second_dist_2 = float('inf')
            lunch = ("", None, "")
            dinner = ("", None, "")
            candidate_lunch = None
            candidate_dinner = None
            restaurants_list = [r for r in total_restaurants_list if r["id"] not in selected_restaurant_ids]
            for restaurant in restaurants_list:
                if day == 1:
                    arrived_time = self.str_to_float(start_info["EndTime"])
                    arrived_time = max(arrived_time, 8.0)
                    if arrived_time > 18 or next_day:
                        break
                    if arrived_time < 12:
                        # 午餐
                        before_lunch = min(num, round((12 - arrived_time) / 2))
                        if num == 1:
                            prev_attraction = station_1
                            next_attraction = day_attractions[0]
                        elif num == 0:
                            prev_attraction = station_1
                            next_attraction = station_1
                        else:
                            prev_attraction = day_attractions[before_lunch - 1] if before_lunch >= 1 else start_info[
                                "To"]
                            next_attraction = day_attractions[before_lunch] if len(
                                day_attractions) > before_lunch else prev_attraction

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_1:
                            second_dist_1 = min_dist_1
                            min_dist_1 = dist_1 + dist_2
                            candidate_lunch = lunch[1]
                            lunch = (prev_attraction, restaurant, next_attraction)

                        # 晚餐
                        before_dinner = round((18 - arrived_time - 1) / 2)
                        if num == 1:
                            prev_attraction = day_attractions[0]
                            next_attraction = day_attractions[0]
                        elif num == 0:
                            prev_attraction = station_1
                            next_attraction = station_1
                        else:
                            prev_attraction = day_attractions[before_dinner - 1] if len(
                                day_attractions) >= before_dinner else day_attractions[-1]
                            next_attraction = day_attractions[before_dinner] if len(
                                day_attractions) >= before_dinner + 1 else day_attractions[-1]

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_2:
                            second_dist_2 = min_dist_2
                            min_dist_2 = dist_1 + dist_2
                            candidate_dinner = dinner[1]
                            dinner = (prev_attraction, restaurant, next_attraction)
                    else:
                        before_dinner = round((18 - arrived_time) / 2)
                        if before_dinner <= 1 and num > 3:
                            before_dinner = round(18 - arrived_time)

                        if num == 1 and before_dinner:
                            prev_attraction = day_attractions[0]
                            next_attraction = day_attractions[0]
                        elif num == 1 and not before_dinner:
                            prev_attraction = station_1
                            next_attraction = day_attractions[0]
                        elif num == 0:
                            prev_attraction = station_1
                            next_attraction = station_1
                        else:
                            prev_attraction = day_attractions[before_dinner - 1] if len(
                                day_attractions) >= before_dinner else day_attractions[-1]
                            next_attraction = day_attractions[before_dinner] if len(
                                day_attractions) > before_dinner else day_attractions[-1]

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_2:
                            second_dist_2 = min_dist_2
                            min_dist_2 = dist_1 + dist_2
                            candidate_dinner = dinner[1]
                            dinner = (prev_attraction, restaurant, next_attraction)
                elif day == self.travel_days:
                    end_time = self.str_to_float(end_info["BeginTime"])
                    if end_time < 12:
                        break
                    elif end_time < 18:
                        # 午餐
                        if num == 1:
                            prev_attraction = day_attractions[0]
                            next_attraction = station_2
                        else:
                            enough_time = round((end_time - 13) / 2) if end_time > 13 else 0
                            enough_time = min(num, enough_time)
                            if enough_time:
                                prev_attraction = day_attractions[len(day_attractions) - enough_time - 1]
                                next_attraction = day_attractions[len(day_attractions) - enough_time]
                            else:
                                prev_attraction = day_attractions[-1]
                                next_attraction = station_2

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_1:
                            second_dist_1 = min_dist_1
                            min_dist_1 = dist_1 + dist_2
                            candidate_lunch = lunch[1]
                            lunch = (prev_attraction, restaurant, next_attraction)
                    else:
                        before_lunch = round(len(day_attractions) / 2)
                        if num == 1:
                            prev_attraction = day_attractions[0]
                            next_attraction = day_attractions[0]
                        else:
                            prev_attraction = day_attractions[before_lunch - 1]
                            next_attraction = day_attractions[before_lunch]

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_1:
                            second_dist_1 = min_dist_1
                            min_dist_1 = dist_1 + dist_2
                            candidate_lunch = lunch[1]
                            lunch = (prev_attraction, restaurant, next_attraction)

                        prev_attraction = day_attractions[-1]
                        next_attraction = station_2

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_2:
                            second_dist_2 = min_dist_2
                            min_dist_2 = dist_1 + dist_2
                            candidate_dinner = dinner[1]
                            dinner = (prev_attraction, restaurant, next_attraction)
                else:
                    start_time, end_time = self.start_close_time(day_attractions, self.attractions.to_dict("records"))
                    if end_time < 18:
                        before_lunch = round(len(day_attractions) / 2)
                        if num == 1:
                            prev_attraction = day_attractions[0]
                            next_attraction = day_attractions[0]
                        else:
                            prev_attraction = day_attractions[before_lunch - 1]
                            next_attraction = day_attractions[before_lunch]

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_1:
                            second_dist_1 = min_dist_1
                            min_dist_1 = dist_1 + dist_2
                            candidate_lunch = lunch[1]
                            lunch = (prev_attraction, restaurant, next_attraction)

                        prev_attraction = day_attractions[-1]
                        next_attraction = day_attractions[-1]

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_2:
                            second_dist_2 = min_dist_2
                            min_dist_2 = dist_1 + dist_2
                            candidate_dinner = dinner[1]
                            dinner = (prev_attraction, restaurant, next_attraction)
                    else:
                        before_lunch = round(len(day_attractions) / 3)
                        before_dinner = round(len(day_attractions) / 3 * 2)
                        if num == 1:
                            prev_attraction = day_attractions[0]
                            next_attraction = day_attractions[0]
                        elif num == 2:
                            prev_attraction = day_attractions[0]
                            next_attraction = day_attractions[1]
                        else:
                            prev_attraction = day_attractions[before_lunch - 1]
                            next_attraction = day_attractions[before_lunch]

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_1:
                            second_dist_1 = min_dist_1
                            min_dist_1 = dist_1 + dist_2
                            candidate_lunch = lunch[1]
                            lunch = (prev_attraction, restaurant, next_attraction)

                        if num < 3:
                            prev_attraction = day_attractions[-1]
                            next_attraction = day_attractions[-1]
                        else:
                            prev_attraction = day_attractions[before_dinner - 1]
                            next_attraction = day_attractions[before_dinner]

                        dist_1 = self.geo_calculator.haversine_distance(
                            coordinates[prev_attraction][0],
                            coordinates[prev_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )
                        dist_2 = self.geo_calculator.haversine_distance(
                            coordinates[next_attraction][0],
                            coordinates[next_attraction][1],
                            restaurant["lat"],
                            restaurant["lon"]
                        )

                        if dist_1 + dist_2 < min_dist_2:
                            second_dist_2 = min_dist_2
                            min_dist_2 = dist_1 + dist_2
                            candidate_dinner = dinner[1]
                            dinner = (prev_attraction, restaurant, next_attraction)

            if lunch[1] and dinner[1] and lunch[1]["id"] == dinner[1]["id"]:
                if min_dist_1 + second_dist_2 <= min_dist_2 + second_dist_1:
                    daily_restaurants[day]["lunch"] = lunch
                    dinner_new = (dinner[0], candidate_dinner, dinner[2])
                    daily_restaurants[day]["dinner"] = dinner_new
                else:
                    daily_restaurants[day]["dinner"] = dinner
                    lunch_new = (lunch[0], candidate_lunch, lunch[2])
                    daily_restaurants[day]["lunch"] = lunch_new
            else:
                if lunch[1]:
                    daily_restaurants[day]["lunch"] = lunch
                    selected_restaurant_ids.add(lunch[1]["id"])
                if dinner[1]:
                    daily_restaurants[day]["dinner"] = dinner
                    selected_restaurant_ids.add(dinner[1]["id"])

        print(daily_restaurants)

        preferred_type = self.preferences["restaurant_preferences"]
        select_preferred_type = preferred_type.copy()
        dists_matrix = {}

        for day_restaurants in daily_restaurants.values():
            for meal in ["lunch", "dinner"]:
                if meal in day_restaurants:
                    restaurant = day_restaurants[meal][1]
                    if restaurant and restaurant["cuisine"] in select_preferred_type:
                        select_preferred_type = [item for item in select_preferred_type if
                                                 item != restaurant["cuisine"]]

        restaurants_costs = 0.0
        i = 0
        for day_restaurants in daily_restaurants.values():
            for meal in ["lunch", "dinner"]:
                if meal in day_restaurants:
                    restaurant = day_restaurants[meal][1]
                    restaurants_costs += restaurant["price"] if restaurant else 0.0
                    i += 1

        if select_preferred_type not in [None, []]:
            print(select_preferred_type)
            delta = (budget * i - restaurants_costs) / len(select_preferred_type)
            print(delta)

            filter_restaurants_list_preferred = [
                restaurant for restaurant in preferred_restaurants_list
                if restaurant["price"] <= budget + delta and restaurant["id"] not in selected_restaurant_ids
            ]
            # print(filter_restaurants_list_preferred)

            # 二分图最小权匹配问题
            remained_type_list = []
            for unselected_type in select_preferred_type:
                dists_matrix[unselected_type] = []
                for day_restaurants in daily_restaurants.values():
                    for meal in ["lunch", "dinner"]:
                        if meal in day_restaurants:
                            restaurant = day_restaurants[meal][1]
                            if not restaurant:
                                continue
                            min_dist = float('inf')
                            chosen = None
                            skip = False
                            for preferred_restaurant in filter_restaurants_list_preferred:
                                if preferred_restaurant["cuisine"] == unselected_type:
                                    if restaurant["cuisine"] in preferred_type:
                                        # print(restaurant["cuisine"])
                                        # dist = float('inf')
                                        skip = True
                                        break
                                    else:
                                        dist = self.geo_calculator.haversine_distance(
                                            preferred_restaurant["lat"],
                                            preferred_restaurant["lon"],
                                            restaurant["lat"],
                                            restaurant["lon"]
                                        )
                                        # print(dist)

                                        if dist < min_dist:
                                            min_dist = dist
                                            chosen = preferred_restaurant

                            if not skip:
                                dists_matrix[unselected_type].append(
                                    (restaurant, chosen, min_dist)
                                )

                if not dists_matrix[unselected_type]:
                    remained_type_list.append(unselected_type)

            if remained_type_list:
                filter_restaurants_list_preferred = [
                    restaurant for restaurant in preferred_restaurants_list
                    if restaurant["cuisine"] in remained_type_list and restaurant["id"] not in selected_restaurant_ids
                ]

                for unselected_type in remained_type_list:
                    dists_matrix[unselected_type] = []
                    for day_restaurants in daily_restaurants.values():
                        for meal in ["lunch", "dinner"]:
                            if meal in day_restaurants:
                                restaurant = day_restaurants[meal][1]
                                if not restaurant:
                                    continue
                                min_dist = float('inf')
                                chosen = None
                                for preferred_restaurant in filter_restaurants_list_preferred:
                                    if preferred_restaurant["cuisine"] == unselected_type:
                                        dist = self.geo_calculator.haversine_distance(
                                            preferred_restaurant["lat"],
                                            preferred_restaurant["lon"],
                                            restaurant["lat"],
                                            restaurant["lon"]
                                        )
                                        # print(dist)

                                        if dist < min_dist:
                                            min_dist = dist
                                            chosen = preferred_restaurant

                                dists_matrix[unselected_type].append(
                                    (restaurant, chosen, min_dist)
                                )

            dists_list = []
            for dists in dists_matrix.values():
                dists_list.append(dists)
            # print(dists_list)
            best_replacement, min_total_weight = self.find_min_weight_replacement(dists_list)

            if best_replacement:
                # print(best_replacement)
                for replace in best_replacement:
                    for key, day_restaurants in daily_restaurants.items():
                        for meal in ["lunch", "dinner"]:
                            if meal in day_restaurants:
                                restaurant = day_restaurants[meal][1]
                                if restaurant and restaurant["id"] == replace[0]["id"]:
                                    original_tuple = daily_restaurants[key][meal]
                                    new_tuple = (original_tuple[0], replace[1], original_tuple[2])
                                    daily_restaurants[key][meal] = new_tuple

        restaurants_costs = 0.0
        for day_restaurants in daily_restaurants.values():
            for meal in ["lunch", "dinner"]:
                if meal in day_restaurants:
                    restaurant = day_restaurants[meal][1]
                    restaurants_costs += restaurant["price"] if restaurant else 0.0

        return daily_restaurants, restaurants_costs

    def find_min_weight_replacement(self, distance_lists):
        n = len(distance_lists)
        min_total_weight = sys.maxsize
        best_replacement = None

        # 用于记录已经选过的 special_hotel_id，避免重复
        used_special_hotels = set()

        def backtrack(index, current_replacement, current_weight):
            nonlocal min_total_weight, best_replacement

            if index == n:
                if current_weight < min_total_weight:
                    min_total_weight = current_weight
                    best_replacement = current_replacement.copy()
                return

            # 遍历当前距离列表的所有可能选择
            for original, special, weight in distance_lists[index]:
                if not special:
                    continue
                special_id = special["id"]
                if special_id not in used_special_hotels:
                    used_special_hotels.add(special_id)
                    current_replacement.append((original, special, weight))
                    backtrack(index + 1, current_replacement, current_weight + weight)
                    current_replacement.pop()
                    used_special_hotels.remove(special_id)

        backtrack(0, [], 0)
        return best_replacement, min_total_weight

    def _load_cache(self):
        """从文件加载缓存"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r", encoding="utf-8") as f:
                try:
                    self.cache = json.load(f)
                except json.JSONDecodeError:
                    self.cache = {}  # 如果文件损坏，清空缓存

    def _save_cache(self):
        """保存缓存到文件"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=4)

    def _make_cache_key(self, origin, destination):
        """生成缓存键，确保origin和destination是元组（不可变）"""
        return str((
            (float(origin[0]), float(origin[1])),  # origin (lat, lng)
            (float(destination[0]), float(destination[1]))  # destination (lat, lng)
        ))

    def get_travel_time(self, origin, destination, city):
        """调用高德地图API获取交通时间和费用（带缓存）"""
        # 1. 检查缓存
        cache_key = self._make_cache_key(origin, destination)
        with self.cache_lock:  # 如果多线程调用，加锁保护缓存
            if cache_key in self.cache:
                return self.cache[cache_key]

        # 2. 缓存未命中，调用API
        time.sleep(self.geo_calculator.rate_limit_delay)
        url = "https://restapi.amap.com/v5/direction/transit/integrated"
        params = {
            "key": self.geo_calculator.gaode_api_key,
            "origin": f"{origin[1]},{origin[0]}",
            "destination": f"{destination[1]},{destination[0]}",
            "city1": self.geo_calculator.city_code_converter(city),
            "city2": self.geo_calculator.city_code_converter(city),
            "strategy": 0,  # 最快路线
            "output": "json",
            "extensions": "base",
            "show_fields": "cost"
        }

        try:
            response = requests.get(url, params=params).json()
            # print(response)
            if response["status"] == "1":
                if response["route"]["transits"]:
                    # 取第一条推荐路线
                    transit = response["route"]["transits"][0]
                    duration = float(transit["cost"]["duration"]) / 60 if transit["cost"]["duration"] else 0.0  # 转换为分钟
                    cost = float(transit["cost"]["transit_fee"]) if transit["cost"]["transit_fee"] else 0.0
                    result = {
                        "time": duration,
                        "cost": cost,
                        "details": {
                            "line": transit["segments"][0]["bus"]["buslines"][0]["name"] if "bus" in
                                                                                            transit["segments"][
                                                                                                0] else "地铁"
                        }
                    }
                else:
                    result = {"time": 1.0, "cost": 0.0, "details": {"line": "步行"}}
            else:
                print("高德API返回错误:", response.get("info", "未知错误"))
                result = {"time": 5.0, "cost": 3.0, "details": {"line": "4号线"}}
        except Exception as e:
            print(f"高德API调用失败: {e}")
            # 失败时返回默认值
            result = {"time": 5.0, "cost": 3.0, "details": {"line": "4号线"}}

        # 3. 存入内存缓存 + 文件缓存
        with self.cache_lock:
            self.cache[cache_key] = result
            self._save_cache()  # 每次更新缓存都写入文件（可优化为批量写入）

        return result

    def clear_cache(self):
        """清空缓存（内存 + 文件）"""
        with self.cache_lock:
            self.cache.clear()
            self._save_cache()

    def get_attraction_time_range(self, poi_name):
        """获取景点的推荐访问时间范围"""
        if poi_name in self.attractions:
            recommendmintime = self.attractions[poi_name].get("recommendmintime", 0.5)
            recommendmaxtime = self.attractions[poi_name].get("recommendmaxtime", 2.0)
            return (recommendmintime, recommendmaxtime)

        return (0.5, 2.0)  # 默认时间

    def create_daily_pois(
            self,
            daily_attractions: Dict[int, List],
            daily_restaurants: Dict[int, Dict],
    ):
        daily_pois = {}
        for day, day_attractions in daily_attractions.items():
            day_restaurants = daily_restaurants.get(day, {})
            day_pois = copy.deepcopy(day_attractions)

            for meal_type in ["lunch", "dinner"]:
                if meal_type in day_restaurants:
                    prev_poi, restaurant, next_poi = day_restaurants[meal_type]

                    # 检查前后景点是否在当日列表中
                    prev_in_list = prev_poi in day_attractions
                    next_in_list = next_poi in day_attractions

                    # 餐厅名称（用于插入）
                    if restaurant:
                        restaurant_name = restaurant['name']
                    else:
                        continue

                    # 确定插入位置
                    if not prev_in_list:
                        day_pois.insert(0, restaurant_name)
                    elif not next_in_list:
                        day_pois.append(restaurant_name)
                    elif prev_poi == next_poi:
                        # 前后相同：插入到该景点后面
                        prev_index = day_pois.index(prev_poi)
                        day_pois.insert(prev_index + 1, restaurant_name)
                    else:
                        prev_index = day_pois.index(prev_poi)
                        next_index = day_pois.index(next_poi)
                        if prev_index == next_index - 1:
                            day_pois.insert(prev_index + 1, restaurant_name)
                        else:
                            print("前后景点不连续，存在数据问题！理论上不应出现！")
                            day_pois.insert(prev_index + 1, restaurant_name)

            daily_pois[day] = day_pois

        return daily_pois

    def create_daily_activities(
            self,
            day: int,
            day_pois: List,
            day_attractions: List,
            accommodation: Dict,
            station: str,
            start_time: float,
            finish_time: float,
            coordinates: Dict[str, Tuple[float, float]]
    ):
        """确定每日的活动安排"""
        activities = []
        num = len(day_pois)
        accommodation_coord = (accommodation["lat"], accommodation["lon"])
        if num > 6:
            urgent = True
            end_hour = 22
        elif (day == 1 or day == self.travel_days) and num > 3:
            urgent = True
            end_hour = 22
        else:
            urgent = False
            if num <= 3:
                end_hour = 18
            else:
                end_hour = 22

        transports_info = {}
        total_transport_time = 0.0

        if day == 1:
            # 第一天根据到达时间确定
            if day_pois:
                first_attraction = day_pois[0]
                transport_info = self.get_travel_time(
                    coordinates[station], coordinates[first_attraction], self.target_city)
                transports_info[0] = transport_info
                transport_time = transport_info["time"]
                total_transport_time += transport_time
                begin_hour = max(8.0, start_time + transport_time / 60)

                open, close = self.start_close_time(day_attractions, self.attractions.to_dict("records"))
                if urgent:
                    all_day = max(close, end_hour) - min(open, begin_hour)
                else:
                    all_day = min(close, end_hour) - max(open, begin_hour)
            else:
                return activities, start_time
        elif day == self.travel_days:
            first_attraction = day_pois[0]
            transport_info = self.get_travel_time(
                accommodation_coord, coordinates[first_attraction], self.target_city)
            transports_info[0] = transport_info
            transport_time = transport_info["time"]
            total_transport_time += transport_time
            begin_hour = min(8.0, start_time + transport_time / 60)

            open, close = self.start_close_time(day_attractions, self.attractions.to_dict("records"))
            if urgent:
                all_day = finish_time - min(open, begin_hour)
            else:
                all_day = finish_time - max(open, begin_hour)
        else:
            first_attraction = day_pois[0]
            transport_info = self.get_travel_time(
                accommodation_coord, coordinates[first_attraction], self.target_city)
            transports_info[0] = transport_info
            transport_time = transport_info["time"]
            total_transport_time += transport_time
            begin_hour = min(8.0, start_time + transport_time / 60)

            open, close = self.start_close_time(day_attractions, self.attractions.to_dict("records"))
            if urgent:
                all_day = max(close, end_hour) - max(begin_hour, open)
            else:
                all_day = min(close, end_hour) - min(begin_hour, open)

        for index in range(len(day_pois) - 1):
            coord_1 = coordinates[day_pois[index]]
            coord_2 = coordinates[day_pois[index + 1]]

            transport_info = self.get_travel_time(
                coord_1, coord_2, self.target_city
            )
            transports_info[index + 1] = transport_info
            total_transport_time += transport_info["time"]
            print(f'transport_time: {transport_info["time"]}')
        print(f"all_day: {all_day}")
        avg_duration = (all_day - total_transport_time / 60 + transport_time / 60) / num
        print(f"avg: {avg_duration}")
        end = 0
        for i in range(len(day_pois)):
            poi = day_pois[i]
            poi_is_attraction = poi in day_attractions
            details_dict = self.extract_attractions_details(
                poi) if poi_is_attraction else self.extract_restaurant_details(poi)
            transport_info = transports_info[i]
            trans_time = transports_info[i]['time']
            activity_type = "attraction" if poi_is_attraction else "meal"
            description = f"参观{poi}" if poi_is_attraction else f"品尝{poi}"
            s, e = self.get_attraction_time_range(poi)
            print(s, e)
            duration = min(e, avg_duration)
            duration = max(s, duration)
            if poi == day_pois[0]:
                start = begin_hour
            else:
                start = end + trans_time / 60
            end = start + duration if poi_is_attraction else start + 1
            print(f"start:{start}, end:{end}")
            cost = details_dict["price"] * self.num_people
            details = {
                "transport_time": f"{trans_time}",
                "line": transport_info["details"]["line"],
                "ticket_type": "成人票" if details_dict["price"] else "免费",
                "ticket_price": details_dict["price"],  # 实际价格
                "ticket_number": self.num_people
            } if poi_is_attraction else {
                "transport_time": f"{trans_time}",
                "line": transport_info["details"]["line"],
                "cuisine": details_dict["recommendedfood"],
            }

            activity = {
                "type": activity_type,
                "description": description,
                "start_time": self.float_to_time(start),  # 实际应根据时间安排动态计算
                "end_time": self.float_to_time(end),  # 实际应根据时间安排动态计算
                "location_name": poi,
                "cost": cost,  # 景点门票价格应从数据库获取
                "transportation_to": "地铁" if transport_info["details"]["line"] == "地铁" else "公交",
                "transportation_cost": transport_info["cost"] * self.num_people,
                "details": details
            }

            activities.append(activity)

        return activities, end

    def generate_travel_plan(
            self,
            daily_attractions: Dict[int, List],
            daily_restaurants: Dict[int, Dict],
            accommodation_info: Tuple[Dict, List],
            intercity_info: Tuple[Dict, Dict],
            coordinates: Dict[str, Tuple[float, float]]
    ):
        """
        生成标准JSON格式的旅行规划

        参数:
            user_input: 用户查询字典
            daily_attractions: 每日景点列表 {day: [poi1, poi2,...]}
            daily_restaurants: 每日餐饮计划 {day: [(prev_poi, restaurant, next_poi),...]}
            accommodation_info: 酒店信息字典
            intercity_info: 城际交通信息字典

        返回:
            标准旅行规划JSON
        """
        # 解析日期范围
        start_date, end_date = self.user_query["dates"].split(" to ")
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        total_days = (end_date - start_date).days + 1

        station_1 = intercity_info[0]["To"]
        station_2 = intercity_info[1]["From"]

        accommodation, accommodation_type = accommodation_info
        accommodation_costs = 0.0
        for room_type in accommodation_type:
            accommodation_costs += room_type["quantity"] * room_type["price_per_night"] * room_type["nights"]

        intercity_info_0_cost = intercity_info[0]["Cost"] if intercity_info[0][
            "Cost"] else self.extract_min_intercity_cost()
        intercity_info_1_cost = intercity_info[1]["Cost"] if intercity_info[1][
            "Cost"] else self.extract_min_intercity_cost()

        # 初始化规划结构
        plan = {
            "query_uid": self.uid,
            "itinerary": {
                "summary": {
                    "total_days": total_days,
                    "total_travelers": self.num_people,
                    "departure": self.start_city,
                    "destination": self.target_city,
                    "total_budget": self.budget,
                    "calculated_total_cost": 0,  # 后续计算
                    "is_within_budget": True  # 后续验证
                },
                "accommodation": {
                    "hotel_name": accommodation["name"],
                    "room_type": accommodation_type,
                    "total_cost": accommodation_costs
                },
                "intercity_transport": {
                    "transport_type": [{
                        "description": f"{intercity_info[0]['From']}出发前往{intercity_info[0]['To']}",
                        "start_time": intercity_info[0]["BeginTime"],
                        "end_time": intercity_info[0]["EndTime"],
                        "location_name": intercity_info[0]["To"],
                        "cost": intercity_info[0]["Cost"] * self.num_people if intercity_info[
                            0]["Cost"] else self.extract_min_intercity_cost() * self.num_people,
                        "transportation_to": "飞机" if "FlightID" in intercity_info[
                            0] else intercity_info[0]["TrainType"],
                        "transportation_cost": intercity_info[0]["Cost"] * self.num_people if intercity_info[
                            0]["Cost"] else self.extract_min_intercity_cost() * self.num_people,
                        "details": {
                            "transport_number": intercity_info[0][
                                "FlightID"] if "FlightID" in intercity_info[0] else intercity_info[0]["TrainID"],
                            "price": intercity_info[0]["Cost"] if intercity_info[
                                0]["Cost"] else self.extract_min_intercity_cost(),
                            "number": self.num_people
                        }
                    }, {
                        "description": f"{intercity_info[1]['From']}返回{intercity_info[1]['To']}",
                        "start_time": intercity_info[1]["BeginTime"],
                        "end_time": intercity_info[1]["EndTime"],
                        "location_name": intercity_info[1]["To"],
                        "cost": intercity_info[1]["Cost"] * self.num_people if intercity_info[
                            1]["Cost"] else self.extract_min_intercity_cost() * self.num_people,
                        "transportation_to": "飞机" if "FlightID" in intercity_info[
                            1] else intercity_info[1]["TrainType"],
                        "transportation_cost": intercity_info[1]["Cost"] * self.num_people if intercity_info[
                            1]["Cost"] else self.extract_min_intercity_cost() * self.num_people,
                        "details": {
                            "transport_number": intercity_info[1][
                                "FlightID"] if "FlightID" in intercity_info[1] else intercity_info[1]["TrainID"],
                            "price": intercity_info[1]["Cost"] if intercity_info[
                                1]["Cost"] else self.extract_min_intercity_cost(),
                            "number": self.num_people
                        }
                    }],
                    "total_cost": (
                                          (
                                              intercity_info[0]["Cost"] if intercity_info[0][
                                                  "Cost"] else self.extract_min_intercity_cost()
                                          ) + (
                                              intercity_info[1]["Cost"] if intercity_info[1][
                                                  "Cost"] else self.extract_min_intercity_cost()
                                          )
                                  ) * self.num_people
                },
                "daily_plans": [],
                "cost_breakdown": {
                    "attractions": 0,
                    "intercity_transportation": (
                                                        (
                                                            intercity_info[0]["Cost"] if intercity_info[0][
                                                                "Cost"] else self.extract_min_intercity_cost()
                                                        ) + (
                                                            intercity_info[1]["Cost"] if intercity_info[1][
                                                                "Cost"] else self.extract_min_intercity_cost()
                                                        )
                                                ) * self.num_people,
                    "intracity_transportation": 0,
                    "accommodation": accommodation_costs,
                    "meals": 0,
                    "other": 0,
                    "total": 0
                }
            }
        }

        daily_pois = self.create_daily_pois(daily_attractions, daily_restaurants)
        print(daily_pois)
        new_coordinates = coordinates.copy()
        for day, day_pois in daily_pois.items():
            add_coords = self.get_poi_coordinates(day_pois)
            new_coordinates = dict(ChainMap(add_coords, new_coordinates))

        # 生成每日计划
        current_date = start_date
        for day in range(1, total_days + 1):
            day_attractions = daily_attractions[day]
            day_pois = daily_pois[day]
            # 确定当天开始时间
            if day == 1:
                # 实际为到达时间
                arrived_time = datetime.strptime(intercity_info[0]["EndTime"], "%H:%M").time()
                start_time = arrived_time.hour + arrived_time.minute / 60
                finish_time = 23.99
            elif day == self.travel_days:
                # 实际为返程时间
                arrived_time = datetime.strptime(intercity_info[0]["BeginTime"], "%H:%M").time()
                start_time = 8.00
                finish_time = arrived_time.hour + arrived_time.minute / 60
            else:
                start_time = 8.00
                finish_time = 23.59
            if len(day_pois) >= 6:
                start_time = 6.00
            activities, ending_point_time = self.create_daily_activities(
                day, day_pois, day_attractions, accommodation, station_1, start_time, finish_time, new_coordinates
            )
            if day == self.travel_days:
                transport_info = self.get_travel_time(
                    new_coordinates[day_pois[-1]], new_coordinates[station_2], self.target_city
                )
            elif len(day_pois) > 0:
                transport_info = self.get_travel_time(
                    new_coordinates[day_pois[-1]], (accommodation["lat"], accommodation["lon"]), self.target_city
                )
            else:
                transport_info = self.get_travel_time(
                    new_coordinates[station_1], (accommodation["lat"], accommodation["lon"]), self.target_city
                )

            cost = transport_info["cost"]
            float_start = ending_point_time + transport_info["time"] / 60
            if float_start > 24:
                float_start -= 24
            start = self.float_to_time(float_start)
            end = self.float_to_time(round(float_start + 1)) if float_start < 8 else "23:59"

            day_plan = {
                "day": day,
                "date": current_date.strftime("%Y-%m-%d"),
                "starting_point": intercity_info[0]["From"] if day == 1 else accommodation["name"],
                "ending_point": {
                    "type": "accommodation" if day < total_days else "intercity_transport",
                    "description": "返回酒店休息" if day < total_days else f"前往{intercity_info[1]['From']}乘坐{'飞机' if 'FlightID' in intercity_info[1] else intercity_info[1]['TrainType']}返回{self.start_city}",
                    "start_time": start,
                    "end_time": end if day < total_days else intercity_info[1]["BeginTime"],
                    "location_name": accommodation["name"] if day < total_days else intercity_info[1]["From"],
                    "cost": 0,
                    "transportation_to": "地铁" if transport_info["details"]["line"] == "地铁" else "公交",
                    "transportation_cost": cost * self.num_people,
                    "details": {
                        "transport_time": str(transport_info["time"]),
                        "line": transport_info["details"]["line"]
                    }
                },
                "activities": activities
            }

            for activity in activities:
                cost = float(activity.get("cost", 0))
                transport_cost = float(activity.get("transportation_cost", 0))

                # 景点成本
                if activity["type"] == "attraction":
                    plan["itinerary"]["cost_breakdown"]["attractions"] += cost

                # 餐饮成本
                elif activity["type"] == "meal":
                    plan["itinerary"]["cost_breakdown"]["meals"] += cost

                elif activity["type"] in [
                    "intercity_transport", "accommodation", "accommodation_check_in", "accommodation_check_out", "intracity_transport"
                ]:
                    pass

                else:
                    plan["itinerary"]["cost_breakdown"]["other"] += cost

                # 市内交通成本（所有活动的交通费用，包括步行/地铁等）
                if transport_cost < intercity_info_0_cost and transport_cost < intercity_info_1_cost:
                    plan["itinerary"]["cost_breakdown"]["intracity_transportation"] += transport_cost

                # 处理每日结束点的交通成本（如返回酒店的地铁）

            ending_point = day_plan.get("ending_point", {})
            if ending_point and float(
                    ending_point.get("transportation_cost", 0)) < intercity_info_0_cost and float(
                ending_point.get("transportation_cost", 0)) < intercity_info_1_cost:
                plan["itinerary"]["cost_breakdown"]["intracity_transportation"] += float(
                    ending_point.get("transportation_cost", 0))

            plan["itinerary"]["daily_plans"].append(day_plan)
            current_date += timedelta(days=1)

        # 计算总费用
        total_cost = (plan["itinerary"]["accommodation"]["total_cost"] +
                      plan["itinerary"]["intercity_transport"]["total_cost"] +
                      plan["itinerary"]["cost_breakdown"]["attractions"] +
                      plan["itinerary"]["cost_breakdown"]["meals"] +
                      plan["itinerary"]["cost_breakdown"]["intracity_transportation"])

        plan["itinerary"]["summary"]["calculated_total_cost"] = total_cost
        plan["itinerary"]["summary"]["is_within_budget"] = total_cost <= self.budget
        plan["itinerary"]["cost_breakdown"]["total"] = total_cost

        return plan

    def generate_plan(self):
        """生成完整旅行计划"""
        # 步骤(1): 筛选候选景点
        attractions_list = self._select_candidate_attractions()
        restaurants_list = self._filter_restaurants_by_preference().to_dict("records")

        attractions = self.extract_poi_names(attractions_list)
        coordinates = self.get_poi_coordinates(attractions)

        # print(coordinates)
        # 步骤(2): 集群分类
        clusters = self._cluster_attractions(attractions_list)
        print(clusters)

        # 分配每日集群
        cluster_days = self.assign_clusters_to_days(clusters, attractions_list)
        print(cluster_days)

        # 生成每日计划
        daily_attractions = self.extract_daily_attractions(clusters, cluster_days, coordinates)
        print(daily_attractions)

        attractions_to_accommodations = []
        # 提取第 2 ~ n-1 天的首尾景点，第 n 天的第一个景点
        for i in range(2, self.travel_days + 1):
            attractions_to_accommodations.append(daily_attractions[i][0])
            if i != self.travel_days:
                attractions_to_accommodations.append(daily_attractions[i][-1])
        print(attractions_to_accommodations)

        if daily_attractions[1]:
            attractions_to_stations = daily_attractions[1]
        else:
            attractions_to_stations = attractions_to_accommodations

        station_1 = self._select_stations(attractions_to_stations, coordinates, 0)
        print(station_1)
        attractions_to_stations = []
        attractions_to_stations.append(daily_attractions[self.travel_days][-1])
        station_2 = self._select_stations(attractions_to_stations, coordinates, 1)
        print(station_2)
        added_coord = self.get_poi_coordinates([station_1, station_2])
        # 新增车站经纬度坐标
        merged_coord = dict(ChainMap(coordinates, added_coord))

        # 步骤(6): 城际交通（示例：第一天和最后一天的车站）
        intercity_info = self._select_intercity(
            station_1, station_2, daily_attractions[1], daily_attractions[self.travel_days], attractions_list)
        print(intercity_info)

        intercity_costs = 0.0
        for info in intercity_info:
            if info["Cost"]:
                intercity_costs += info["Cost"]
        daily_budget = (self.budget / self.num_people - intercity_costs) / self.travel_days

        attractions_costs = 0.0
        for atttraction in attractions_list:
            # print(atttraction["price"])
            attractions_costs += atttraction["price"]

        # 一天两顿饭，共 n 天
        percentage = 100
        for cost_range in daily_costs_range.values():
            if cost_range[0] <= daily_budget <= cost_range[1]:
                percentage = cost_range[2]
                print(percentage)
        n = int(len(restaurants_list) * percentage / 100)
        predicted_restaurants_costs = float(np.mean(list(item["price"] for item in restaurants_list[:n])))

        # 步骤(5): 插入餐饮
        restaurants, restaurants_costs = self._select_restaurants(
            predicted_restaurants_costs, daily_attractions, merged_coord, intercity_info
        )

        print(restaurants)

        segments = 0
        for day_attractions in daily_attractions.values():
            segments += (len(day_attractions) + 3)  # 计算行程段数，包括 去餐馆2 和 回酒店1
        predicted_intracity_costs = segments * 5

        # 酒店总预算
        budget_for_accommodations = self.budget - (
                intercity_costs + attractions_costs + restaurants_costs + predicted_intracity_costs
        ) * self.num_people
        print(intercity_costs, attractions_costs, restaurants_costs, predicted_intracity_costs)

        # 步骤(3): 选择酒店
        print(budget_for_accommodations)
        accommodation_info = self._select_accommodation(
            budget_for_accommodations, self.travel_days - 1, attractions_to_accommodations, coordinates)

        accommodation, accommodation_type = accommodation_info
        print(accommodation, accommodation_type)

        accommodation_costs = 0.0
        for room_type in accommodation_type:
            accommodation_costs += room_type["quantity"] * room_type["price_per_night"] * room_type["nights"]

        print(daily_attractions)

        # daily_pois = planner.create_daily_pois(daily_attractions, restaurants)
        # print(daily_pois)

        # 生成最终JSON
        travel_plan = self.generate_travel_plan(
            daily_attractions, restaurants, accommodation_info, intercity_info, merged_coord
        )

        print("生成的旅行计划：")
        print(travel_plan)

        # 保存到指定路径（例如: "./data/output/travel_plan.json"）
        save_path = os.path.join(DATA_BASE_DIR, "environment", "data", "plans", "plans_our-method_matched.json")
        planner.save_travel_plan_to_json(travel_plan, save_path)

        # return travel_plan

    def save_travel_plan_to_json(self, travel_plan, file_path):
        """
        将旅行计划追加并保存到指定路径的 JSON 文件
        :param travel_plan: 要保存的数据（dict/list）
        :param file_path: 文件路径，如 "output/travel_plan.json"
        """
        try:
            # 1. 确保目录存在（自动创建多级目录）
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 2. 如果文件已存在，读取旧数据
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)  # 假设文件存储的是 list
            else:
                existing_data = []  # 初始化为空列表

            # 3. 合并新数据（假设 travel_plan 是 dict，追加到 list）
            if isinstance(existing_data, list):
                existing_data.append(travel_plan)
            else:
                raise ValueError("JSON 文件格式错误，期望是 list 类型")

            # 4. 重新写入合并后的数据
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=4)

            print(f"✅ 成功追加数据到: {os.path.abspath(file_path)}")
            return True
        except Exception as e:
            print(f"❌ 保存失败: {str(e)}")
            return False


if __name__ == '__main__':
    data_loader = DataLoader()
    for query_file in ['easy.json', 'medium.json', 'hard.json', 'progressive.json']:
        file_path = os.path.join(DATA_BASE_DIR, 'environment', 'data', 'queries', query_file)
        user_queries = data_loader.load_user_queries(file_path)

        for key, user_query in user_queries.items():
            # 生成计划
            print(f"{key}: {user_query['nature_language']}")
            planner = TravelPlanner(user_query)
            planner.generate_plan()
        mail.sendMail(f'您的提问 {query_file} 已经运行完成！')
    #
    # user_query = {
    #   "uid": "T0001",
    #   "tag": "easy",
    #   "start_city": "北京",
    #   "target_city": "上海",
    #   "days": 3,
    #   "people_number": 2,
    #   "people_composition": {
    #     "adults": 2,
    #     "children": 0,
    #     "seniors": 0
    #   },
    #   "budget": 3400,
    #   "dates": "2024-11-15 to 2024-11-17",
    #   "transportation": {},
    #   "accommodations": {},
    #   "diet": {},
    #   "attractions": {},
    #   "rhythm": {},
    #   "nature_language": "我们两个人想从北京去上海玩3天，预算3400元。",
    #   "nature_language_en": "We two people want to travel from Beijing to Shanghai for 3 days with a budget of 3400 RMB."
    # }
    # {
    #   "uid": "T0023",
    #   "tag": "easy",
    #   "start_city": "南京",
    #   "target_city": "成都",
    #   "days": 3,
    #   "people_number": 4,
    #   "people_composition": {
    #     "adults": 2,
    #     "children": 0,
    #     "seniors": 2
    #   },
    #   "budget": 6000,
    #   "dates": "2024-11-26 to 2024-11-28",
    #   "transportation": {},
    #   "accommodations": {},
    #   "diet": {},
    #   "attractions": {},
    #   "rhythm": {},
    #   "nature_language": "我们四个人（2大2老）想从南京去成都玩3天，预算6000元。",
    #   "nature_language_en": "We four people (2 adults, 2 seniors) want to travel from Nanjing to Chengdu for 3 days with a budget of 6000 RMB."
    # }
    # {
    #   "uid": "T0004",
    #   "tag": "easy",
    #   "start_city": "深圳",
    #   "target_city": "南京",
    #   "days": 2,
    #   "people_number": 4,
    #   "people_composition": {
    #     "adults": 2,
    #     "children": 2,
    #     "seniors": 0
    #   },
    #   "budget": 5200,
    #   "dates": "2024-11-08 to 2024-11-09",
    #   "transportation": {},
    #   "accommodations": {},
    #   "diet": {},
    #   "attractions": {},
    #   "rhythm": {},
    #   "nature_language": "我们一家四口（2大2小）想从深圳去南京玩2天，预算5200元。",
    #   "nature_language_en": "Our family of four (2 adults, 2 children) wants to travel from Shenzhen to Nanjing for 2 days with a budget of 5200 RMB."
    # }

    # planner = TravelPlanner(user_query)
    # planner.generate_plan()

    # 示例用户输入
    # user_input_example = {
    #     "uid": "T1002",
    #     "tag": "hard",
    #     "start_city": "广州",
    #     "target_city": "北京",
    #     "days": 7,
    #     "people_number": 1,
    #     "people_composition": {
    #         "adults": 1,
    #         "children": 0,
    #         "seniors": 0
    #     },
    #     "budget": 3500,
    #     "dates": "2024-12-09 to 2024-12-15",
    #     "transportation": {"preferences": ["飞机"], "constraints": ["骑行"]},
    #     "accommodations": {"preferences": [], "constraints": ["管家服务", "SPA", "民宿"]},
    #     "diet": {"preferences": ["北京菜", "烧烤", "小吃"], "constraints": ["粤菜"]},
    #     "attractions": {"preferences": ["历史古迹", "博物馆/纪念馆"], "constraints": ["现代景观"]},
    #     "rhythm": {"preferences": ["特种兵式"], "constraints": []},
    #     "nature_language": "我一个人12月中旬从广州到北京玩7天，预算3500元，坐飞机不要骑行，住宿不要管家服务、SPA和民宿，吃北京菜烧烤小吃不要粤菜，看历史古迹博物馆不看现代景观，特种兵式游玩。",
    #     "nature_language_en": "I'm traveling alone from Guangzhou to Beijing for 7 days in mid-December with a budget of 3500 RMB, flying not cycling, accommodation without butler service, SPA or guesthouses, eat Beijing cuisine, BBQ and snacks not Cantonese food, visit historical sites and museums not modern attractions, in an intensive travel style."
    # }
    # user_input_example = {
    #     "uid": "T0606",
    #     "tag": "hard",
    #     "start_city": "杭州",
    #     "target_city": "北京",
    #     "days": 4,
    #     "people_number": 2,
    #     "people_composition": {
    #         "adults": 1,
    #         "children": 0,
    #         "seniors": 1
    #     },
    #     "budget": 2400,
    #     "dates": "2025-01-05 to 2025-01-08",
    #     "transportation": {
    #         "preferences": ["高铁"],
    #         "constraints": []
    #     },
    #     "accommodations": {
    #         "preferences": [],
    #         "constraints": ["温泉", "桑拿"]
    #     },
    #     "diet": {
    #         "preferences": ["北京菜", "茶馆/茶室"],
    #         "constraints": ["烧烤"]
    #     },
    #     "attractions": {
    #         "preferences": ["历史古迹", "园林"],
    #         "constraints": []
    #     },
    #     "rhythm": {
    #         "preferences": ["慢游"],
    #         "constraints": []
    #     },
    #     "nature_language": "我带老人从杭州坐高铁去北京玩4天，预算2400元，住宿不要温泉桑拿，想吃北京菜去茶馆但不吃烧烤，慢游历史古迹和园林。",
    #     "nature_language_en": "I want to take an elderly person from Hangzhou to Beijing by high-speed rail for 4 days with a budget of 2400 RMB, accommodation without hot springs and sauna, want to try Beijing cuisine and teahouses but no barbecue, slowly visit historical sites and gardens."
    # }

    # 生成计划
    # planner = TravelPlanner(user_input_example)
    # travel_plan = planner.generate_plan()
    # print(planner.attractions)

    # print(planner.preferences)
    # print(planner.total_attractions_needed / planner.travel_days)

    # attractions_list = self._select_candidate_attractions()
    # # print(attractions_list)
    # # accommodations_list = planner._filter_accommodations_by_preference().to_dict("records")
    # restaurants_list = self._filter_restaurants_by_preference().to_dict("records")
    # # print(accommodations_list)
    # # print(restaurants_list)
    #
    # attractions = self.extract_poi_names(attractions_list)
    # coordinates = self.get_poi_coordinates(attractions)
    # # print(coordinates)
    #
    # clusters = self._cluster_attractions(attractions_list)
    # print(clusters)
    #
    # cluster_days = self.assign_clusters_to_days(clusters, attractions_list)
    # print(cluster_days)
    #
    # daily_attractions = self.extract_daily_attractions(clusters, cluster_days)
    # print(daily_attractions)
    #
    # attractions_to_accommodations = []
    # # 提取第 2 ~ n-1 天的首尾景点，第 n 天的第一个景点
    # for i in range(2, self.travel_days + 1):
    #     attractions_to_accommodations.append(daily_attractions[i][0])
    #     if i != self.travel_days:
    #         attractions_to_accommodations.append(daily_attractions[i][-1])
    # print(attractions_to_accommodations)
    #
    # if daily_attractions[1]:
    #     attractions_to_stations = daily_attractions[1]
    # else:
    #     attractions_to_stations = attractions_to_accommodations
    #
    # station_1 = self._select_stations(attractions_to_stations, coordinates)
    # print(station_1)
    # attractions_to_stations = []
    # attractions_to_stations.append(daily_attractions[self.travel_days][-1])
    # station_2 = self._select_stations(attractions_to_stations, coordinates)
    # print(station_2)
    # added_coord = self.get_poi_coordinates([station_1, station_2])
    # # 新增车站经纬度坐标
    # merged_coord = dict(ChainMap(coordinates, added_coord))
    #
    # intercity_info = self._select_intercity(
    #     station_1, station_2, daily_attractions[1], daily_attractions[self.travel_days], attractions_list)
    # print(intercity_info)
    #
    # intercity_costs = 0.0
    # for info in intercity_info:
    #     intercity_costs += info["Cost"]
    # daily_budget = (self.budget / self.num_people - intercity_costs) / self.travel_days
    #
    # attractions_costs = 0.0
    # for atttraction in attractions_list:
    #     # print(atttraction["price"])
    #     attractions_costs += atttraction["price"]
    #
    # # 一天两顿饭，共 n 天
    # percentage = 100
    # for cost_range in daily_costs_range.values():
    #     if cost_range[0] <= daily_budget <= cost_range[1]:
    #         percentage = cost_range[2]
    #         print(percentage)
    # n = int(len(restaurants_list) * percentage / 100)
    # predicted_restaurants_costs = float(np.mean(list(item["price"] for item in restaurants_list[:n])))
    #
    # restaurants, restaurants_costs = self._select_restaurants(
    #     predicted_restaurants_costs, daily_attractions, merged_coord, intercity_info
    # )
    #
    # print(restaurants)
    #
    # segments = 0
    # for day_attractions in daily_attractions.values():
    #     segments += (len(day_attractions) + 3)  # 计算行程段数，包括 去餐馆2 和 回酒店1
    # predicted_intracity_costs = segments * 5
    #
    # # 酒店总预算
    # budget_for_accommodations = self.budget - (
    #         intercity_costs + attractions_costs + restaurants_costs + predicted_intracity_costs
    # ) * self.num_people
    # print(intercity_costs, attractions_costs, restaurants_costs, predicted_intracity_costs)
    #
    # print(budget_for_accommodations)
    # accommodation_info = self._select_accommodation(
    #     budget_for_accommodations, self.travel_days - 1, attractions_to_accommodations, coordinates)
    #
    # accommodation, accommodation_type = accommodation_info
    # print(accommodation, accommodation_type)
    #
    # accommodation_costs = 0.0
    # for room_type in accommodation_type:
    #     accommodation_costs += room_type["quantity"] * room_type["price_per_night"] * room_type["nights"]
    #
    # print(daily_attractions)
    #
    # # daily_pois = planner.create_daily_pois(daily_attractions, restaurants)
    # # print(daily_pois)
    #
    # travel_plan = self.generate_travel_plan(
    #     daily_attractions, restaurants, accommodation_info, intercity_info, merged_coord
    # )

    # travel_plan = planner.generate_plan()

    # 输出JSON
    # print(json.dumps(travel_plan, indent=2, ensure_ascii=False))

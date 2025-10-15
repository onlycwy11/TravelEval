import math
import requests
import time
import json
import os
import numpy as np
from typing import Dict, List, Set, Tuple, Optional
from geopy.distance import geodesic
from itertools import permutations


class GeoCalculator:
    """
    地理计算工具类，处理距离计算、坐标转换等地理相关操作
    """

    def __init__(self, cache_file: str = "geo_cache.json"):
        self.cache_file = cache_file
        self.gaode_api_key = None  # 外部配置
        self.rate_limit_delay = 0.5

    def set_gaode_api_key(self, api_key: str):
        """设置高德API密钥"""
        self.gaode_api_key = api_key

    def get_poi_coordinates(self, file_path, poi_names: List) -> Dict[str, Tuple[float, float]]:
        """
        从 JSON 文件中读取指定 POI 列表的坐标
        :param file_path: JSON 文件路径
        :param poi_names: 要查询的 POI 名称列表
        :return: 包含指定 POI 坐标的字典
        """
        coordinates = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)  # 直接解析整个 JSON 文件
                for poi in data:
                    # 检查 poi 是否是字典，并且包含 name 和 position
                    if isinstance(poi, dict) and "name" in poi and "position" in poi:
                        if poi["name"] in poi_names:
                            position = poi["position"]
                            # 检查 position 是否是包含 2 个数字的列表
                            if isinstance(position, list) and len(position) == 2:
                                coordinates[poi["name"]] = tuple(position)
                                # 如果已经找到所有需要的坐标，提前退出循环
                                if len(coordinates) == len(poi_names):
                                    break
        except Exception as e:
            print(f"读取文件出错: {e}")
        return coordinates

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        使用哈弗辛公式计算两个地理坐标点之间的大圆距离

        Args:
            lat1, lon1: 第一个点的纬度和经度
            lat2, lon2: 第二个点的纬度和经度

        Returns:
            两点之间的大圆距离（单位：公里）
        """
        # 地球半径（公里）
        R = 6371.0

        # 将角度转换为弧度
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # 计算纬度和经度的差值
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        # 哈弗辛公式计算
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    def geodesic_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        使用测地线距离计算两点距离（更高精度）

        Args:
            coord1: 第一个点的坐标 (纬度, 经度)
            coord2: 第二个点的坐标 (纬度, 经度)

        Returns:
            两点之间的测地线距离（单位：公里）
        """
        return geodesic(coord1, coord2).kilometers

    def great_circle_dist(self, attraction1: str, attraction2: str, coordinates: Dict[str, Tuple[float, float]]):
        """
        计算两个景点之间的大圆距离
        :param attraction1: 第一个景点名称
        :param attraction2: 第二个景点名称
        :param coordinates: 包含景点坐标的字典
        :return: 两点之间的大圆距离（单位：公里）
        """
        coord1 = coordinates.get(attraction1)
        coord2 = coordinates.get(attraction2)

        if coord1 and coord2:
            return self.haversine_distance(coord1[0], coord1[1], coord2[0], coord2[1])
        else:
            print(f"未找到 {attraction1} or {attraction2} 的坐标")
            return None

    def calculate_bearing(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        计算两点之间的方位角（从正北方向顺时针到路径方向的角度）

        Args:
            coord1: 起点坐标 (纬度, 经度)
            coord2: 终点坐标 (纬度, 经度)

        Returns:
            方位角（度，0-360）
        """
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

        # 计算经度差
        dlon = lon2 - lon1

        # 计算x和y
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

        # 计算初始方位角（弧度）
        initial_bearing = math.atan2(x, y)

        # 转换为角度并调整到0-360度
        initial_bearing = math.degrees(initial_bearing)
        bearing = (initial_bearing + 360) % 360

        return bearing

    def calculate_segment_distance(self,
                                   attractions_order: List[str],
                                   attraction_coords: Dict[str, Tuple[float, float]],
                                   transport_type: str = "walking") -> Optional[Dict[Tuple[str, str], float]]:
        """
        计算多段路径的总距离（通过高德API），并返回相邻景点对及其距离

        支持交通方式：
        - driving: 驾车
        - walking: 步行
        - bicycling: 骑行（自行车）
        - electrobike: 骑行（电动车）
        - transit: 公交（含地铁）

        Args:
            attractions_order: 景点访问顺序列表，如 ["景点A", "景点B", "景点C"]
            attraction_coords: 景点坐标字典，格式为 {"景点名": (纬度, 经度)}
            transport_type: 交通方式

        Returns:
            dict: 包含相邻景点对及其实际距离的字典，格式为 {("景点A", "景点B"): 距离(公里)}
            如果计算失败则返回None
        """
        if len(attractions_order) < 2:
            return {}

        if not self.gaode_api_key:
            raise ValueError("未配置高德API密钥")

        actual_distances = {}

        for i in range(len(attractions_order) - 1):
            start = attractions_order[i]
            end = attractions_order[i + 1]
            segment = (start, end)

            try:
                # 检查坐标是否存在
                if start not in attraction_coords or end not in attraction_coords:
                    print(f"警告: 缺少景点坐标 - {segment}")
                    continue

                start_coord = attraction_coords[start]
                end_coord = attraction_coords[end]

                # 计算距离
                distance = self._call_gaode_api_with_cache(start_coord, end_coord, transport_type)
                if distance is not None:
                    actual_distances[segment] = distance
                else:
                    print(f"警告: 无法计算路线 - {segment}")

            except Exception as e:
                print(f"未知错误: {segment} - {str(e)}")

        return actual_distances

    def _call_gaode_api_with_cache(self, origin: Tuple[float, float],
                                   destination: Tuple[float, float],
                                   transport_type: str) -> Optional[float]:
        """调用高德路径规划API"""
        # 高德API坐标顺序是 (lon, lat)
        cache_key = f"{transport_type}_{origin}_to_{destination}"
        cache = self._load_cache()

        # 1. 检查缓存
        if cache_key in cache:
            # print("cache!")
            return cache[cache_key]

        # 2. 限流：每次请求间隔 0.5 秒（高德默认 3次/秒）
        time.sleep(self.rate_limit_delay)

        # 3. 调用高德API
        if transport_type in ["driving", "walking", "bicycling", "electrobike"]:
            url = f"https://restapi.amap.com/v5/direction/{transport_type}"
        elif transport_type == "transit":
            url = f"https://restapi.amap.com/v5/direction/driving"
        else:
            print("交通方式错误！")
            return None
        # print(url)

        params = {
            "key": self.gaode_api_key,
            "origin": f"{origin[1]},{origin[0]}",  # 经度,纬度
            "destination": f"{destination[1]},{destination[0]}",
            "output": "json",
            "extensions": "base"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data["status"] == "1" and data["route"]["paths"]:
                distance_meters = int(data["route"]["paths"][0]["distance"])
                distance_km = round(distance_meters / 1000, 2)
                # 写入缓存
                cache[cache_key] = distance_km
                self._save_cache(cache)
                return distance_km  # 转换为公里

            else:
                print(f"高德API错误: {data.get('info', '未知错误')}")
                return None
        except Exception as e:
            print(f"高德API请求失败: {e}")
            return None

    def is_closed_loop(self, order: List[str]) -> bool:
        """检查路线是否闭环（首尾相同）"""
        return len(order) > 1 and order[0] == order[-1]

    def calculate_optimal_route(
            self,
            attractions: List[str],
            coordinates: Dict[str, Tuple[float, float]],
            travel_mode: str = "walking",
            method: str = "dp",  # 可选 "dp"（动态规划）或 "brute"（暴力搜索）
            # return_to_start: bool = False  # 新增参数：是否返回起点
    ) -> Tuple[List[str], float]:
        """
        计算最优路线顺序和总距离（支持动态规划或暴力搜索）

        参数:
            attractions: 景点名称列表
            coordinates: 景点经纬度坐标字典 {景点名: (纬度, 经度)}
            travel_mode: 交通方式 (walking/transit/driving/bicycling)
            method: 计算方法 ("dp" 或 "brute")

        返回:
            (最优路线顺序, 最优总距离)
        """
        n = len(attractions)
        if n == 0:
            return [], 0.0
        if n == 1:
            return attractions, 0.0

        # 固定起点和终点
        start, end = attractions[0], attractions[-1]
        middle_attractions = attractions[1:-1]  # 中间景点
        m = len(middle_attractions)  # 中间景点数量

        # 构建距离矩阵
        distance_matrix = {}
        for i in range(n):
            for j in range(n):
                if i != j:
                    loc1, loc2 = attractions[i], attractions[j]
                    start_coord = coordinates[loc1]
                    end_coord = coordinates[loc2]
                    dist = self._call_gaode_api_with_cache(start_coord, end_coord, travel_mode)
                    # print(dist)
                    if dist is None:
                        raise ValueError(f"Failed to compute distance from {loc1} to {loc2}")
                    distance_matrix[(loc1, loc2)] = dist

        # 动态规划方法（适用于 n <= 20）
        if method == "dp" and n <= 20:
            loc_to_idx = {loc: i for i, loc in enumerate(attractions)}
            idx_to_loc = {i: loc for i, loc in enumerate(attractions)}

            # DP 表：dp[mask][i] = min_distance
            dp = [[float('inf')] * n for _ in range(1 << n)]
            parent = [[-1] * n for _ in range(1 << n)]  # 记录路径

            # 初始化：从起点出发
            start_idx = loc_to_idx[start]
            end_idx = loc_to_idx[end]
            dp[1 << start_idx][start_idx] = 0

            for mask in range(1 << n):
                for i in range(n):
                    if dp[mask][i] == float('inf'):
                        continue

                    # 尝试访问所有未访问的景点 j
                    for j in range(n):
                        if mask & (1 << j):
                            continue

                        # 不能直接从起点跳到终点（除非没有中间景点）
                        if (mask == (1 << start_idx)) and (j == end_idx) and (m > 0):
                            continue

                        new_mask = mask | (1 << j)
                        loc_i, loc_j = attractions[i], attractions[j]
                        dist = distance_matrix[(loc_i, loc_j)]
                        new_dist = dp[mask][i] + dist

                        if new_dist < dp[new_mask][j]:
                            dp[new_mask][j] = new_dist
                            parent[new_mask][j] = i

            # 最终状态：所有景点被访问，且位于终点
            full_mask = (1 << n) - 1
            min_distance = dp[full_mask][end_idx]

            # 回溯路径
            path = []
            if min_distance != float('inf'):
                # 从终点开始回溯
                current_mask = full_mask
                current_node = end_idx
                path.append(end)

                while current_node != start_idx:
                    prev_node = parent[current_mask][current_node]
                    if prev_node == -1:
                        break  # 路径重建失败

                    path.append(idx_to_loc[prev_node])
                    # 移除当前节点
                    current_mask ^= (1 << current_node)
                    current_node = prev_node

                path.reverse()

            return path, min_distance

        # 暴力搜索方法（适用于 n <= 10）
        else:
            min_distance = float('inf')
            print("brute")
            best_order = None
            start = attractions[0]  # 固定起点
            end = attractions[-1]  # 固定终点
            other_attractions = attractions[1:-1]

            # 只对其他景点进行全排列
            for perm in permutations(other_attractions):
                # 构建完整路径：起点 + 其他景点的排列 + 终点
                full_path = (start,) + perm + (end,)
                dist = 0

                # 计算路径距离
                for i in range(len(full_path) - 1):
                    dist += distance_matrix[(full_path[i], full_path[i + 1])]

                if dist < min_distance:
                    min_distance = dist
                    best_order = full_path
            return list(best_order), min_distance

    def calculate_route_penalty(
            self,
            order: List[str],
            actual_distances: Dict[Tuple[str, str], float],  # 实际交通距离矩阵
            coordinates: Dict[str, Tuple[float, float]],
            optimal_route_method: str = "brute"  # 最优路线计算方法
    ) -> float:
        """
        计算路线绕路程度 (Route Penalty)

        参数:
            order: 实际访问顺序列表
            actual_distances: 实际交通距离矩阵 {(起点, 终点): 距离}
            coordinates: 景点坐标字典 {景点名: (纬度, 经度)}
            optimal_route_method: 最优路线计算方法 ("dp" 或 "brute")

        返回:
            Route Penalty 值 (实际距离/最优距离)
        """
        # 1. 计算实际路线总距离
        actual_total_distance = 0
        for i in range(len(order) - 1):
            s1, s2 = order[i], order[i + 1]
            # 优先使用实际交通距离，如果没有则使用大圆距离
            if (s1, s2) in actual_distances:
                actual_total_distance += actual_distances[(s1, s2)]
            elif (s2, s1) in actual_distances:
                actual_total_distance += actual_distances[(s2, s1)]
            else:
                actual_total_distance += self.great_circle_dist(s1, s2, coordinates)

        # 2. 计算最优路线总距离
        optimal_order, optimal_total_distance = self.calculate_optimal_route(  # _ 是 Python 的惯例，表示忽略不关心的返回值。
            list(order),  # 所有景点
            coordinates,
            method=optimal_route_method,
            travel_mode="walking",  # 统一使用步行距离
        )  # 我们只需要距离，不需要顺序，用 _ 占位

        # print(optimal_order)
        # topological_penalty = calculate_topology_penalty(optimal_order, coordinates) / 180
        # print(topological_penalty)

        # 4. 计算Route Penalty
        if optimal_total_distance == 0:
            return float('inf')  # 避免除以零
        route_penalty = actual_total_distance / optimal_total_distance - 1

        # 5. 可视化路线（可选）
        # map_center = list(coordinates.values())[0]
        # travel_map = folium.Map(location=map_center, zoom_start=12, tiles='OpenStreetMap')
        #
        # # 添加实际路线
        # for i in range(len(order) - 1):
        #     s1, s2 = order[i], order[i + 1]
        #     folium.PolyLine(
        #         locations=[coordinates[s1], coordinates[s2]],
        #         color='blue',
        #         weight=5,
        #         opacity=0.5,
        #         # tooltip=f"{s1} → {s2}: {actual_distances.get((s1, s2), great_circle_dist(s1, s2, coordinates)):.2f}km"
        #     ).add_to(travel_map)
        #
        # for i in range(len(optimal_order) - 1):
        #     s1, s2 = optimal_order[i], optimal_order[i + 1]
        #     folium.PolyLine(
        #         locations=[coordinates[s1], coordinates[s2]],
        #         color='red',
        #         weight=5,
        #         opacity=0.5,
        #         # tooltip="TEST Popup"
        #         # tooltip=f"{s1} → {s2}: {actual_distances.get((s1, s2), great_circle_dist(s1, s2, coordinates)):.2f}km"
        #     ).add_to(travel_map)
        #
        # # 添加景点标记
        # for place, coord in coordinates.items():
        #     folium.Marker(location=coord, popup=place).add_to(travel_map)
        #
        # travel_map.save('travel_map.html')

        return route_penalty

    def calculate_cross_day_misalignment(self, attractions: Dict, coordinates: Dict, special_pois: Set) -> Dict:
        """计算跨日空间错配度"""
        csm_values = []
        problem_spots = []

        # 创建距离矩阵，为所有景点对预计算距离
        distance_matrix = {}
        all_attractions = list(coordinates.keys())  # 获取所有景点名称
        n = len(all_attractions)
        for i in range(n):
            loc1 = all_attractions[i]
            distance_matrix[(loc1, loc1)] = 0.0
            for j in range(i + 1, n):
                loc2 = all_attractions[j]
                start_coord = coordinates[loc1]
                end_coord = coordinates[loc2]
                dist = self._call_gaode_api_with_cache(start_coord, end_coord, "walking")
                # print(dist)
                if dist is None:
                    raise ValueError(f"Failed to compute distance from {loc1} to {loc2}")
                distance_matrix[(loc1, loc2)] = dist
                distance_matrix[(loc2, loc1)] = dist  # 此处考虑距离对称

        # print(distance_matrix)

        # 遍历每一天
        for day, attractions_sequence in attractions.items():
            # 遍历当天每一个景点
            for current_attraction in attractions_sequence:
                if current_attraction in special_pois:
                    continue

                # 计算到当日其他景点的平均距离（分子）
                same_day_distances = []
                for other_attractions in attractions_sequence:
                    if other_attractions == current_attraction:
                        continue  # 跳过自身

                    # 从矩阵中获取距离
                    dist = distance_matrix[(current_attraction, other_attractions)]
                    same_day_distances.append(dist)

                if not same_day_distances:
                    avg_same_day = 0.0
                else:
                    avg_same_day = np.mean(same_day_distances)

                # 计算到其他日期景点的最小平均距离（分母）
                other_days_data = []  # 存储 (other_day, avg_distance) 对
                for other_day, other_attractions in attractions.items():
                    if other_day == day or not other_attractions:
                        continue  # 跳过当天和空日期

                    distances_to_other_day = []
                    for attraction in other_attractions:
                        dist = distance_matrix[(current_attraction, attraction)]
                        distances_to_other_day.append(dist)

                    if distances_to_other_day:  # 确保非空
                        avg_dist = np.mean(distances_to_other_day)  # 使用 NumPy库计算算术平均值
                        other_days_data.append((other_day, avg_dist))  # 记录日期和对应的平均距离

                # 如果找不到其他有效日期
                if not other_days_data:
                    min_avg_other_days = 0.0
                else:
                    min_avg_other_days = min(avg for _, avg in other_days_data)

                if min_avg_other_days > 0:
                    mis_fit_value = avg_same_day / min_avg_other_days
                    csm_values.append(mis_fit_value)

                    if mis_fit_value > 1.0:
                        optimal_day = next(day for day, avg in other_days_data if avg == min_avg_other_days)
                        avg_dists = sorted([dist for _, dist in other_days_data])
                        second_min_avg_dist = avg_dists[1] if len(avg_dists) > 1 else None
                        if second_min_avg_dist > avg_same_day:
                            second_min_avg_dist = avg_same_day

                        problem_spots.append({
                            'attraction': current_attraction,
                            'current_day': day,
                            'misfit': mis_fit_value,
                            'recommended_day': optimal_day,
                            'improvement': f"{(mis_fit_value - min_avg_other_days / second_min_avg_dist) * 100:.1f}%"
                        })

        return {
            'csm_values': csm_values,
            'problem_spots': problem_spots
        }

    def check_public_transport_availability(self, current_activity: Dict, next_activity: Dict, coordinate: Dict,
                                            city: str) -> bool:
        """
        使用高德地图API检查指定时间的公共交通方案是否可行
        """
        start_time = current_activity['end_time']
        if start_time == '00:00':
            hours, minutes = map(int, next_activity['start_time'].split(':'))
            # 减去30分钟
            minutes -= 30
            if minutes < 0:
                minutes += 60
                hours -= 1
            # 处理小时为负数的情况（如00:00减30分钟）
            if hours < 0:
                hours = 23  # 假设跨天，设置为前一天的23:30（根据需求调整）
            start_time = f"{hours:02d}:{minutes:02d}"

        origin = coordinate[current_activity['location_name']]
        destination = coordinate[next_activity['location_name']]
        city_code = self.city_code_converter(city)

        cache_key = f"'transit'_{origin}_to_{destination}_{start_time}_"
        cache = self._load_cache()

        # 1. 检查缓存
        if cache_key in cache:
            # print("cache!")
            return cache[cache_key]

        # 2. 限流：每次请求间隔 0.5 秒（高德默认 3次/秒）
        time.sleep(self.rate_limit_delay)

        # 3. 调用高德API
        params = {
            "key": self.gaode_api_key,
            "origin": f"{origin[1]},{origin[0]}",  # 经度,纬度
            "destination": f"{destination[1]},{destination[0]}",
            "city1": city_code,
            "city2": city_code,
            "time": start_time,
            "output": "json",
            "extensions": "base"
        }
        # 构造请求高德地图 API 的 URL
        url = f"https://restapi.amap.com/v5/direction/transit/integrated?"

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data["status"] == "1" and data["route"]["transits"]:
                distance_meters = int(data["route"]["transits"][0]["distance"])
                distance_km = round(distance_meters / 1000, 2)
                # 写入缓存
                cache[cache_key] = distance_km
                self._save_cache(cache)
                return True
        except Exception as e:
            print(f"高德API请求失败: {e}")
            return False

    def find_nearest_poi(self, target_coord: Tuple[float, float],
                         poi_list: List[Dict], max_distance: float = 10.0) -> Optional[Dict]:
        """
        查找最近的POI点

        Args:
            target_coord: 目标坐标
            poi_list: POI列表，每个POI应包含'lat'和'lon'字段
            max_distance: 最大搜索距离（公里）

        Returns:
            最近的POI信息，如果没有找到则返回None
        """
        nearest_poi = None
        min_distance = float('inf')

        for poi in poi_list:
            if 'lat' in poi and 'lon' in poi:
                poi_coord = (poi['lat'], poi['lon'])
                distance = self.geodesic_distance(target_coord, poi_coord)

                if distance < min_distance and distance <= max_distance:
                    min_distance = distance
                    nearest_poi = poi
                    nearest_poi['distance'] = distance

        return nearest_poi

    def calculate_travel_time(self, distance_km: float, transport_type: str = "car") -> float:
        """
        估算旅行时间

        Args:
            distance_km: 距离（公里）
            transport_type: 交通方式 ("walk", "bike", "car", "subway")

        Returns:
            估算的旅行时间（分钟）
        """
        # 平均速度（公里/小时）
        speed_map = {
            "walk": 5.0,  # 步行
            "bike": 15.0,  # 自行车
            "car": 30.0,  # 城市驾驶
            "subway": 35.0,  # 地铁（包含等待时间）
        }

        speed = speed_map.get(transport_type, 30.0)

        # 计算时间（小时转换为分钟）
        time_hours = distance_km / speed
        time_minutes = time_hours * 60

        # 增加缓冲时间（根据交通方式）
        buffer_map = {
            "walk": 0,  # 步行不需要额外缓冲
            "bike": 2,  # 自行车找停车位
            "car": 5,  # 汽车找停车位
            "subway": 10,  # 地铁等待和换乘时间
        }

        time_minutes += buffer_map.get(transport_type, 5)

        return time_minutes

    def city_code_converter(self, query: str) -> str:
        # 城市编码对照表
        city_dict = {
            '北京': '010', '010': '北京',
            '广州': '020', '020': '广州',
            '上海': '021', '021': '上海',
            '重庆': '023', '023': '重庆',
            '南京': '025', '025': '南京',
            '武汉': '027', '027': '武汉',
            '成都': '028', '028': '成都',
            '苏州': '0512', '0512': '苏州',
            '杭州': '0571', '0571': '杭州',
            '深圳': '0755', '0755': '深圳'
        }

        return city_dict.get(query, "未找到匹配的城市/编码")

    def _load_cache(self) -> Dict:
        """加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self, cache):
        """保存缓存"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except:
            pass

# def test_geo_calculator():
#     """测试 GeoCalculator 类的功能"""
#     print("开始测试 GeoCalculator...")
#
#     # 初始化计算器（使用测试API密钥）
#     calculator = GeoCalculator("test_geo_cache.json")
#     calculator.set_gaode_api_key(api_key)  # 使用全局定义的api_key
#
#     # 测试数据 - 北京几个知名景点坐标 (纬度, 经度)
#     test_coords = {
#         "天安门": (39.90872, 116.39748),
#         "故宫": (39.91806, 116.39703),
#         "颐和园": (39.99941, 116.27415),
#         "天坛": (39.88217, 116.40659),
#         "北海公园": (39.92558, 116.39361)
#     }
#
#     # 测试1: 正常路线计算（驾车）
#     print("\n测试1: 正常路线计算（驾车）")
#     route1 = ["天安门", "故宫", "北海公园"]
#     result1 = calculator.calculate_segment_distance(route1, test_coords, "driving")
#     print(f"路线: {route1}")
#     print(f"结果: {result1}")
#     assert isinstance(result1, dict), "结果应该是字典"
#     assert len(result1) == 2, "应该有两段距离"
#     assert all(dist > 0 for dist in result1.values()), "所有距离应该大于0"
#
#     # 测试2: 正常路线计算（步行）
#     print("\n测试2: 正常路线计算（步行）")
#     route2 = ["天安门", "故宫"]
#     result2 = calculator.calculate_segment_distance(route2, test_coords, "walking")
#     print(f"路线: {route2}")
#     print(f"结果: {result2}")
#     assert isinstance(result2, dict), "结果应该是字典"
#     assert len(result2) == 1, "应该有一段距离"
#     assert all(dist > 0 for dist in result2.values()), "所有距离应该大于0"
#
#     # 测试3: 无效景点（缺少坐标）
#     print("\n测试3: 无效景点（缺少坐标）")
#     route3 = ["天安门", "不存在的景点", "颐和园"]
#     result3 = calculator.calculate_segment_distance(route3, test_coords, "driving")
#     print(f"路线: {route3}")
#     print(f"结果: {result3}")
#     assert isinstance(result3, dict), "结果应该是字典"
#     assert ("天安门", "不存在的景点") not in result3, "不应该包含无效路段的距离"
#     assert ("不存在的景点", "颐和园") not in result3, "不应该包含无效路段的距离"
#
#     # 测试4: 单景点路线
#     print("\n测试4: 单景点路线")
#     route4 = ["天坛"]
#     result4 = calculator.calculate_segment_distance(route4, test_coords, "driving")
#     print(f"路线: {route4}")
#     print(f"结果: {result4}")
#     assert isinstance(result4, dict), "结果应该是字典"
#     assert len(result4) == 0, "单景点路线应该返回空字典"
#
#     # 测试5: 空路线
#     print("\n测试5: 空路线")
#     route5 = []
#     result5 = calculator.calculate_segment_distance(route5, test_coords, "driving")
#     print(f"路线: {route5}")
#     print(f"结果: {result5}")
#     assert isinstance(result5, dict), "结果应该是字典"
#     assert len(result5) == 0, "空路线应该返回空字典"
#
#     # 测试6: 公交路线计算
#     print("\n测试6: 公交路线计算")
#     route6 = ["天坛", "颐和园"]
#     result6 = calculator.calculate_segment_distance(route6, test_coords, "transit")
#     print(f"路线: {route6}")
#     print(f"结果: {result6}")
#     assert isinstance(result6, dict), "结果应该是字典"
#     assert len(result6) == 1, "应该有一段距离"
#     assert all(dist > 0 for dist in result6.values()), "所有距离应该大于0"
#
#     # 测试7: 正常路线计算（自行车）
#     print("\n测试7: 正常路线计算（自行车）")
#     route7 = ["天安门", "故宫"]
#     result7 = calculator.calculate_segment_distance(route2, test_coords, "bicycling")
#     print(f"路线: {route2}")
#     print(f"结果: {result2}")
#     assert isinstance(result2, dict), "结果应该是字典"
#     assert len(result2) == 1, "应该有一段距离"
#     assert all(dist > 0 for dist in result2.values()), "所有距离应该大于0"
#
#     # 测试8: 正常路线计算（电动车）
#     print("\n测试8: 正常路线计算（电动车）")
#     route8 = ["天安门", "故宫"]
#     result8 = calculator.calculate_segment_distance(route2, test_coords, "electrobike")
#     print(f"路线: {route2}")
#     print(f"结果: {result2}")
#     assert isinstance(result2, dict), "结果应该是字典"
#     assert len(result2) == 1, "应该有一段距离"
#     assert all(dist > 0 for dist in result2.values()), "所有距离应该大于0"
#
#     print("\n所有测试完成！")

# def test_calculate_optimal_route():
#     """测试 calculate_optimal_route 函数"""
#     print("开始测试 calculate_optimal_route...")
#
#     # 初始化 GeoCalculator 并设置高德 API 密钥（测试时可用模拟数据替代）
#     geo_calc = GeoCalculator(cache_file="test2_geo_cache.json")
#     geo_calc.set_gaode_api_key(api_key)  # 使用你的高德 API 密钥
#
#     # 模拟景点坐标（北京部分景点）
#     attractions = ["天安门", "故宫", "颐和园", "北海公园", "圆明园", "天坛"]
#     coordinates = {
#         "天安门": (39.9075, 116.3972),
#         "故宫": (39.9150, 116.3975),
#         "颐和园": (39.9995, 116.2755),
#         "天坛": (39.8821, 116.4150),
#         "北海公园": (39.9258, 116.3952),
#         "圆明园": (40.0085, 116.2972)
#     }
#
#     try:
#         # 测试动态规划方法
#         print("\n测试动态规划方法 (DP)...")
#         dp_route, dp_distance = geo_calc.calculate_optimal_route(
#             attractions=attractions,
#             coordinates=coordinates,
#             travel_mode="walking",
#             method="dp"
#         )
#         print(f"动态规划最优路线: {dp_route}")
#         print(f"动态规划总距离: {dp_distance:.2f} 公里")
#
#         # 测试暴力搜索方法
#         print("\n测试暴力搜索方法 (Brute Force)...")
#         brute_route, brute_distance = geo_calc.calculate_optimal_route(
#             attractions=attractions,  # 减少景点数量以避免暴力搜索过慢
#             coordinates=coordinates,
#             travel_mode="walking",
#             method="brute"
#         )
#         print(f"暴力搜索最优路线: {brute_route}")
#         print(f"暴力搜索总距离: {brute_distance:.2f} 公里")
#
#         # 验证结果是否一致（对于小规模数据）
#         if dp_route == brute_route and math.isclose(dp_distance, brute_distance, rel_tol=1e-2):
#             print("\n验证通过：DP 和 Brute Force 结果一致！")
#         else:
#             print("\n警告：DP 和 Brute Force 结果不一致！")
#             print(f"DP 路径: {dp_route}, 距离: {dp_distance}")
#             print(f"Brute 路径: {brute_route}, 距离: {brute_distance}")
#
#         # 验证路径合理性：检查是否固定起点和终点
#         assert dp_route[0] == attractions[0], "起点不是天安门！"
#         assert dp_route[-1] == attractions[-1], "终点不是鸟巢！"
#         print("路径合理性验证通过：起点和终点固定正确。")
#
#     except Exception as e:
#         print(f"计算过程中发生错误: {e}")

# 运行测试
# if __name__ == "__main__":
# test_geo_calculator()
# test_calculate_optimal_route()

import json
import pandas as pd
import os
from typing import Dict, List, Any, Optional
from collections import defaultdict


class DataLoader:
    def __init__(self, base_path: str = None):
        """
        初始化数据加载器

        Args:
            base_path: 数据库基础路径，默认为项目根目录下的 environment/database
        """
        if base_path is None:
            # 默认路径：假设从项目根目录开始
            self.base_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'environment', 'database')
        else:
            self.base_path = base_path

        print(f"数据加载器初始化，基础路径: {self.base_path}")

    def load_simplified_user_queries(self, file_path: str) -> Dict[str, Dict]:
        """
        加载用户提问数据，返回 {query_uid: nature_language} 格式

        Args:
            file_path: 用户提问文件路径

        Returns:
            用户提问字典，key为query_uid，value为nature_language
        """
        queries_dict = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 处理不同的数据结构
            if 'queries' in data:
                # A组数据格式
                print("检测到A组数据格式 (queries)")
                for query in data['queries']:
                    queries_dict[query['uid']] = {
                        'nature_language': query.get('nature_language', ''),
                        'start_city': query.get('start_city'),
                        'target_city': query.get('target_city')
                    }
            elif 'query_groups' in data:
                # B组数据格式
                print("检测到B组数据格式 (query_groups)")
                for query_group in data['query_groups']:
                    for queries in query_group:
                        for query in queries:
                            queries_dict[query['uid']] = {
                                'nature_language': query.get('nature_language', ''),
                                'start_city': query.get('start_city'),
                                'target_city': query.get('target_city')
                            }

            print(f"成功加载用户提问数据，共 {len(queries_dict)} 个提问")
            return queries_dict
        except Exception as e:
            print(f"加载用户提问数据时发生错误: {e}")
            return {}

    def load_user_queries(self, file_path: str) -> Dict[str, Any]:
        """
        加载用户提问数据，返回 {query_uid: query_data} 格式

        Args:
            file_path: 用户提问文件路径

        Returns:
            用户提问字典，key为query_uid
        """
        queries_dict = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 处理不同的数据结构
            if 'queries' in data:
                # A组数据格式
                print("检测到A组数据格式 (queries)")
                for query in data['queries']:
                    queries_dict[query['uid']] = query
            elif 'query_groups' in data:
                # B组数据格式
                print("检测到B组数据格式 (query_groups)")
                for query_group in data['query_groups']:
                    for query in query_group:
                        queries_dict[query['uid']] = query

            print(f"成功加载用户提问数据，共 {len(queries_dict)} 个提问")
            return queries_dict

        except Exception as e:
            print(f"加载用户提问数据失败: {e}")
            return {}

    def load_ai_plans(self, file_path: str) -> Dict[str, Any]:
        """
        加载AI规划方案
        
        Args:
            fi: 规划方案文件名（不需要扩展名）
            
        Returns:
            包含规划方案数据的字典
        """
        ai_plans_dict = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 遍历数据，构建query_uid和itinerary的映射
            for plan in data:
                query_uid = plan.get('query_uid')
                itinerary = plan.get('itinerary')
                if query_uid and itinerary:
                    ai_plans_dict[query_uid] = itinerary
            print(f"成功加载AI规划方案，共 {len(ai_plans_dict)} 个方案")
            return ai_plans_dict
        except Exception as e:
            print(f"加载AI规划方案失败: {e}")
            return {}

    def process_plans_and_queries(self, plans_dict: Dict[str, Any], queries_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理规划方案和对应的用户提问

        Args:
            plans_dict: 规划方案字典，key为query_uid，value为对应的itinerary
            queries_dict: 用户提问字典，key为query_uid，value为对应的用户提问

        Returns:
            包含规划方案和对应用户提问的字典
        """
        result = {}
        for query_uid, itinerary in plans_dict.items():
            # 从用户提问字典中查找对应的用户提问
            user_query = queries_dict.get(query_uid)
            if user_query:
                # 如果找到对应的用户提问，将规划方案和用户提问一起存储
                result[query_uid] = {
                    'itinerary': itinerary,
                    'user_query': user_query
                }
            else:
                print(f"警告：未找到query_uid为{query_uid}的用户提问，跳过该规划方案。")
        return result

    def load_sandbox_data(self, city: str) -> Dict[str, Any]:
        """加载沙盒数据（景点、住宿、交通等）"""
        sandbox_data = {}
        city_pinyin = self._city_to_pinyin(city)

        print(f"正在加载 {city}({city_pinyin}) 的沙盒数据...")

        # 加载景点数据
        attractions_path = os.path.join(self.base_path, 'attractions', city_pinyin, 'attractions.csv')
        if os.path.exists(attractions_path):
            try:
                sandbox_data['attractions'] = pd.read_csv(attractions_path)
                print(f"  景点数据: 加载成功，共 {len(sandbox_data['attractions'])} 个景点")
            except Exception as e:
                print(f"  景点数据: 加载失败 - {e}")
                sandbox_data['attractions'] = pd.DataFrame()
        else:
            print(f"  景点数据: 文件不存在 - {attractions_path}")
            sandbox_data['attractions'] = pd.DataFrame()

        # 加载住宿数据
        accommodations_path = os.path.join(self.base_path, 'accommodations', city_pinyin, 'accommodations.csv')
        if os.path.exists(accommodations_path):
            try:
                sandbox_data['accommodations'] = pd.read_csv(accommodations_path)
                print(f"  住宿数据: 加载成功，共 {len(sandbox_data['accommodations'])} 个住宿")
            except Exception as e:
                print(f"  住宿数据: 加载失败 - {e}")
                sandbox_data['accommodations'] = pd.DataFrame()
        else:
            print(f"  住宿数据: 文件不存在 - {accommodations_path}")
            sandbox_data['accommodations'] = pd.DataFrame()

        # 加载餐厅数据
        restaurants_path = os.path.join(self.base_path, 'restaurants', city_pinyin, f'restaurants_{city_pinyin}.csv')
        if os.path.exists(restaurants_path):
            try:
                sandbox_data['restaurants'] = pd.read_csv(restaurants_path)
                print(f"  餐厅数据: 加载成功，共 {len(sandbox_data['restaurants'])} 个餐厅")
            except Exception as e:
                print(f"  餐厅数据: 加载失败 - {e}")
                sandbox_data['restaurants'] = pd.DataFrame()
        else:
            print(f"  餐厅数据: 文件不存在 - {restaurants_path}")
            sandbox_data['restaurants'] = pd.DataFrame()

        # 加载POI坐标数据
        poi_path = os.path.join(self.base_path, 'poi', city_pinyin, 'poi.json')
        if os.path.exists(poi_path):
            try:
                with open(poi_path, 'r', encoding='utf-8') as f:
                    sandbox_data['poi_coordinates'] = json.load(f)
                print(f"  POI坐标: 加载成功，共 {len(sandbox_data['poi_coordinates'])} 个POI")
            except Exception as e:
                print(f"  POI坐标: 加载失败 - {e}")
                sandbox_data['poi_coordinates'] = []
        else:
            print(f"  POI坐标: 文件不存在 - {poi_path}")
            sandbox_data['poi_coordinates'] = []

        return sandbox_data

    def load_intercity_transport(self, from_city: str, to_city: str, transport_type: str = 'all') -> Dict[str, Any]:
        """
        加载城际交通数据

        Args:
            from_city: 出发城市
            to_city: 到达城市
            transport_type: 'train', 'airplane', 或 'all'
        """
        transport_data = {}

        print(f"正在加载 {from_city} - {to_city} 的城际交通数据...")

        # 加载火车数据
        if transport_type in ['train', 'all']:
            train_path_1 = os.path.join(self.base_path, 'intercity_transport', 'train',
                                      f'from_{from_city}_to_{to_city}.json')
            train_path_2 = os.path.join(self.base_path, 'intercity_transport', 'train',
                                        f'from_{to_city}_to_{from_city}.json')
            if os.path.exists(train_path_1) and os.path.exists(train_path_2):
                try:
                    with open(train_path_1, 'r', encoding='utf-8') as f:
                        data1 = json.load(f)

                    with open(train_path_2, 'r', encoding='utf-8') as f:
                        data2 = json.load(f)

                    transport_data['train'] = data1 + data2
                    print(f"  火车数据: 加载成功，共 {len(transport_data['train'])} 个车次")
                except Exception as e:
                    print(f"  火车数据: 加载失败 - {e}")
                    transport_data['train'] = []
            else:
                print(f"  火车数据: 文件不存在 - {train_path_1} or {train_path_2}")
                transport_data['train'] = []

        # 加载飞机数据
        if transport_type in ['airplane', 'all']:
            airplane_path = os.path.join(self.base_path, 'intercity_transport', 'airplane.jsonl')
            if os.path.exists(airplane_path):
                try:
                    transport_data['airplane'] = self._load_airplane_data(airplane_path, from_city, to_city)
                    print(f"  飞机数据: 加载成功，共 {len(transport_data['airplane'])} 个航班")
                except Exception as e:
                    print(f"  飞机数据: 加载失败 - {e}")
                    transport_data['airplane'] = []
            else:
                print(f"  飞机数据: 文件不存在 - {airplane_path}")
                transport_data['airplane'] = []

        return transport_data

    def _load_airplane_data(self, file_path: str, from_prefix: str, to_prefix: str) -> List[Dict]:
        """从jsonl文件加载特定城市间的飞机数据"""
        flights = []

        print(f"  匹配规则: {from_prefix}* - {to_prefix}*")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            flight_data = json.loads(line)
                            from_airport = flight_data.get('From', '')
                            to_airport = flight_data.get('To', '')

                            # 检查机场名称是否以城市前缀开头
                            if (from_airport.startswith(from_prefix) and to_airport.startswith(to_prefix)) \
                                    or (to_airport.startswith(from_prefix) and from_airport.startswith(to_prefix)):
                                flights.append(flight_data)

                        except json.JSONDecodeError as e:
                            print(f"    第{line_num}行JSON解析错误: {e}")
                            continue

        except Exception as e:
            print(f"解析飞机数据失败: {e}")

        return flights

    def _match_city(self, location: str, city_chinese: str, city_pinyin: str) -> bool:
        """检查地点是否匹配城市（支持中文和拼音匹配）"""
        location_lower = location.lower()
        return (city_chinese in location or
                city_pinyin in location_lower or
                city_chinese in location_lower)

    def _city_to_pinyin(self, city: str) -> str:
        """城市名转拼音（简化版，实际使用时可以集成pypinyin）"""
        pinyin_map = {
            '北京': 'beijing', '上海': 'shanghai', '广州': 'guangzhou',
            '深圳': 'shenzhen', '杭州': 'hangzhou', '成都': 'chengdu',
            '南京': 'nanjing', '武汉': 'wuhan', '苏州': 'suzhou', '重庆': 'chongqing'
        }
        return pinyin_map.get(city, city.lower())

    def _count_queries(self, data: Dict) -> int:
        """统计查询数量"""
        count = 0
        if 'queries' in data:
            for group in data['queries']:
                count += len(group)
        elif 'query_groups' in data:
            for group in data['query_groups']:
                count += len(group)
        return count

    def get_available_cities(self) -> List[str]:
        """获取可用的城市列表"""
        attractions_dir = os.path.join(self.base_path, 'attractions')
        if os.path.exists(attractions_dir):
            return [d for d in os.listdir(attractions_dir) if os.path.isdir(os.path.join(attractions_dir, d))]
        return []


# test_data_loader.py
def test_data_loader():
    # """测试数据加载器的所有方法"""
    loader = DataLoader()

    # # 1. 测试用户提问数据加载
    # print("=== 测试用户提问数据加载 ===")
    # a_group_user_queries = loader.load_user_queries(
    #     os.path.join(loader.base_path, "../data/queries/easy.json")  # 替换为实际路径
    # )
    # print(f"用户提问数据: {a_group_user_queries if a_group_user_queries else '加载失败'}")

    # b_group_user_queries = loader.load_user_queries(
    #     os.path.join(loader.base_path, "../data/queries/progressive.json")  # 替换为实际路径
    # )
    # print(f"用户提问数据: {b_group_user_queries if b_group_user_queries else '加载失败'}")

    # # 2. 测试 AI 方案数据加载
    # print("\n=== 测试 AI 方案数据加载 ===")
    # ai_plans = loader.load_ai_plans(
    #     os.path.join(loader.base_path, "../data/plans/test_plan.json")  # 替换为实际路径
    # )
    # print(f"AI 方案数据: {ai_plans if ai_plans else '加载失败'}")

    # # 3. 处理规划方案和对应的用户提问
    # plan_to_query = loader.process_plans_and_queries(ai_plans, a_group_user_queries)
    # print("处理结果：")
    # for query_uid, data in plan_to_query.items():
    #     print(f"Query UID: {query_uid}")
    #     print(f"  Itinerary: {data['itinerary']}")
    #     print(f"  User Query: {data['user_query']}")

    # # 4. 测试沙盒数据加载
    # print("\n=== 测试沙盒数据加载 ===")
    # sandbox_data = loader.load_sandbox_data('北京')
    # # print(sandbox_data.get('attractions'))
    # print(f"北京景点数量: {len(sandbox_data.get('attractions', []))}")
    # print(f"北京住宿数量: {len(sandbox_data.get('accommodations', []))}")
    # print(f"北京餐厅数量: {len(sandbox_data.get('restaurants', []))}")
    # print(f"北京 POI 数量: {len(sandbox_data.get('poi_coordinates', []))}")

    # # 5. 测试城际交通数据加载
    print("\n=== 测试城际交通数据加载 ===")
    transport_data = loader.load_intercity_transport('北京', '上海', 'all')
    print(transport_data)
    print(f"北京→上海 火车车次: {len(transport_data.get('train', []))}")
    print(f"北京→上海 飞机航班: {len(transport_data.get('airplane', []))}")

    # # 6. 测试可用城市列表
    # print("\n=== 测试可用城市列表 ===")
    # cities = loader.get_available_cities()
    # print(f"可用城市: {cities}")


# test_airplane_loading.py
# def test_airplane_loading():
#     """专门测试飞机数据加载"""
#     loader = DataLoader()
#
#     # 测试不同城市组合
#     test_routes = [
#         ('北京', '上海'),
#         ('上海', '北京'),
#         ('广州', '深圳'),
#         ('杭州', '成都')
#     ]
#
#     for from_city, to_city in test_routes:
#         print(f"\n=== 测试 {from_city} → {to_city} ===")
#         transport_data = loader.load_intercity_transport(from_city, to_city, 'airplane')
#
#         if transport_data['airplane']:
#             print(f"找到 {len(transport_data['airplane'])} 个航班:")
#             for i, flight in enumerate(transport_data['airplane'][:3]):  # 只显示前3个
#                 print(f"  {i + 1}. {flight['FlightID']}: {flight['From']} → {flight['To']} "
#                       f"({flight['BeginTime']}-{flight['EndTime']}) ￥{flight['Cost']}")
#         else:
#             print("未找到匹配的航班")


if __name__ == "__main__":
    # test_airplane_loading()
    test_data_loader()

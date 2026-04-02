import json
import os
import re
import glob
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from fuzzywuzzy import fuzz, process
from collections import defaultdict


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("poi_processor.log"),  # 输出到文件
        logging.StreamHandler()  # 输出到终端
    ]
)
logger = logging.getLogger(__name__)


class POIBatchProcessor:
    def __init__(self, poi_base_path: str, min_score: int = 75):
        """
        POI批量处理器
        :param poi_base_path: POI数据库基础路径
        :param min_score: 最小匹配分数阈值
        """
        logger.info(f"初始化 POIBatchProcessor，poi_base_path={poi_base_path}, min_score={min_score}")

        self.poi_base_path = poi_base_path
        self.min_score = min_score
        self.city_poi_names = {}  # 城市 -> POI名称列表
        self.city_name_indices = {}  # 城市 -> 名称到完整数据的映射
        self.loaded_cities = set()

        # 补充数据库 - 车站和机场
        self.stations = {
            '广州增城站', '武汉武昌站', '成都天府国际机场', '苏州园区站', '成都西站', '上海虹桥国际机场',
            '广州新塘站', '成都南站', '广州站', '深圳福田站', '广州南站', '南京南站', '深圳北站', '杭州南站',
            '杭州萧山国际机场', '北京丰台站', '北京西站', '杭州站', '南京站', '武汉站', '重庆江北机场站',
            '重庆东站', '苏州盛泽站', '深圳站', '深圳宝安国际机场', '苏州南站', '广州白云国际机场', '北京清河站',
            '广州东站', '上海金山北站', '北京大兴国际机场', '苏州常熟站', '苏州北站', '武汉汉口站', '重庆江北国际机场',
            '武汉天河国际机场', '上海站', '杭州东站', '重庆沙坪坝站', '杭州西站', '苏州站', '北京首都国际机场',
            '重庆北站', '南京禄口国际机场', '广州白云站', '北京南站', '深圳东站', '重庆西站', '广州北站', '苏州张家港站',
            '北京站', '上海浦东国际机场', '上海练塘站', '苏州太仓站', '成都东站', '苏州新区站', '南京仙林站', '成都犀浦站',
            '北京大兴站', '上海南站', '北京亦庄站', '上海西站', '苏州太仓南站', '上海虹桥站', '成都双流国际机场', '上海松江站'
        }
        # {
        #     '北京西站', '重庆西站', '杭州西站', '北京南站', '南京南站', '南京禄口国际机场', '苏州站',
        #     '苏州南站', '广州白云国际机场', '成都西站', '深圳北站', '广州白云站', '上海虹桥站', '南京站',
        #     '上海浦东国际机场', '成都天府国际机场', '深圳机场北站', '广州东站', '北京首都国际机场', '广州站',
        #     '重庆北站', '北京丰台站', '上海站', '杭州东站', '重庆江北国际机场', '成都双流国际机场', '深圳坪山站',
        #     '杭州站', '武汉站', '深圳宝安国际机场', '广州北站', '北京站', '苏州新区站', '成都南站', '广州南站',
        #     '深圳站', '上海南站', '上海虹桥国际机场', '武汉天河国际机场', '深圳机场站', '上海西站', '苏州北站',
        #     '杭州萧山国际机场', '深圳东站', '杭州南站', '北京大兴国际机场', '成都东站', '苏州园区站'
        # }

        # 匹配缓存：原始名称 -> 匹配结果
        self.match_cache = {}

        # 扫描可用城市
        self.available_cities = self._scan_available_cities()
        logger.info(f"[FILE] 发现 {len(self.available_cities)} 个可用城市")

    def _scan_available_cities(self) -> List[str]:
        """扫描可用的城市目录"""
        poi_pattern = os.path.join(self.poi_base_path, "*", "poi.json")
        city_poi_files = glob.glob(poi_pattern)
        return [os.path.basename(os.path.dirname(f)) for f in city_poi_files]

    def _load_city_data(self, city_name: str):
        """按需加载城市POI数据"""
        if city_name in self.loaded_cities:
            return

        poi_file = os.path.join(self.poi_base_path, city_name, "poi.json")
        added_subway_file = os.path.join(self.poi_base_path, "../transportation", "subways.json")
        if not os.path.exists(poi_file) or not os.path.exists(added_subway_file):
            return

        try:
            with open(poi_file, 'r', encoding='utf-8') as f:
                poi_data = json.load(f)

            # 只提取POI名称和必要信息
            poi_names = []
            name_to_data = {}

            for poi in poi_data:
                name = poi.get('name', '').strip()
                if name:
                    poi_names.append(name)
                    name_to_data[name] = {
                        'name': name,
                        # 'position': poi.get('position'),
                        'city': city_name
                    }

            self.city_poi_names[city_name] = poi_names
            self.city_name_indices[city_name] = name_to_data

        except Exception as e:
            logger.error(f"[FAIL] 加载 {city_name} 失败: {e}")

        try:
            with open(added_subway_file, 'r', encoding='utf-8') as f:
                subway_data = json.load(f)

            # 提取地铁站名称
            subway_stations = []
            for line in subway_data.get(city_name, []):
                for station in line.get('stations', []):
                    station_name = station.get('name', '').strip()
                    if station_name:
                        subway_stations.append(station_name)

            # 将地铁站名称添加到 POI 名称列表中
            self.city_poi_names[city_name].extend(subway_stations)

            logger.info(f"[DATABASE] 加载 {city_name} 地铁站: {len(subway_stations)} 个")

        except Exception as e:
            logger.error(f"[FAIL] 加载 {city_name} 地铁站数据失败: {e}")

        self.loaded_cities.add(city_name)
        logger.info(f"[DATABASE] 加载 {city_name}: {len(self.city_poi_names[city_name])} 个POI")

    def _city_name_to_directory_name(self, chinese_city_name: str) -> str:
        """中文城市名转目录名"""
        city_mapping = {
            '北京': 'beijing', '上海': 'shanghai', '广州': 'guangzhou',
            '深圳': 'shenzhen', '杭州': 'hangzhou', '南京': 'nanjing',
            '成都': 'chengdu', '重庆': 'chongqing', '武汉': 'wuhan',
            '苏州': 'suzhou'
        }
        return city_mapping.get(chinese_city_name, chinese_city_name.lower())

    def _clean_poi_name(self, name: str) -> str:
        """清理POI名称"""
        if not name:
            return ""
        cleaned = re.sub(r'^(前往|从|出发|返回|抵达|参观|游览|在)\s*', '', name.strip())
        cleaned = re.split(r'[/、]', cleaned)[0].strip()
        return cleaned

    def _match_poi(self, search_name: str, target_city: str) -> Dict:
        """匹配单个POI - 增强版本"""
        cache_key = f"{search_name}_{target_city}"
        if cache_key in self.match_cache:
            return self.match_cache[cache_key]

        clean_name = self._clean_poi_name(search_name)
        if not clean_name:
            result = {'match_score': 0, 'matched_name': None}
            self.match_cache[cache_key] = result
            return result

        # 按需加载城市数据
        self._load_city_data(target_city)

        if target_city not in self.city_poi_names:
            result = {'match_score': 0, 'matched_name': None}
            self.match_cache[cache_key] = result
            return result

        city_poi_names = self.city_poi_names[target_city]
        city_index = self.city_name_indices[target_city]

        # 1. 精确匹配
        if clean_name in city_index:
            result = {'match_score': 100, 'matched_name': clean_name}
            self.match_cache[cache_key] = result
            return result

        # 2. 如果主数据库匹配失败，尝试补充数据库
        station_match = self._match_in_stations(clean_name)
        if station_match:
            best_match = station_match
            best_score = 100  # 车站匹配给较高分数
            result = {'match_score': best_score, 'matched_name': best_match}
            self.match_cache[cache_key] = result
            return result

        # 3. 标准化匹配 - 新增：处理括号和店铺名称变体
        normalized_matches = self._normalized_match(clean_name, city_poi_names, city_index)
        if normalized_matches:
            result = normalized_matches
            self.match_cache[cache_key] = result
            return result

        # 4. 模糊匹配
        matches = process.extract(clean_name, city_poi_names, limit=10, scorer=fuzz.token_sort_ratio)

        best_match = None
        best_score = 0

        for match in matches:
            # 兼容不同版本的返回格式
            if len(match) == 3:
                matched_name, score, _ = match
            else:
                matched_name, score = match

            if score > best_score:
                best_match = matched_name
                best_score = score

        # 5. 部分匹配 - 修复：处理包含关系的POI名称
        partial_matches = []
        for poi_name in city_poi_names:
            # 检查相互包含关系
            if clean_name in poi_name or poi_name in clean_name:
                similarity = fuzz.partial_ratio(clean_name, poi_name)
                partial_matches.append((poi_name, similarity))

        if partial_matches:
            best_partial_name, best_partial_score = max(partial_matches, key=lambda x: x[1])
            if best_partial_score > best_score:
                best_match = best_partial_name
                best_score = best_partial_score

        # 6. 关键词提取匹配 - 新增：处理"迪士尼乐园内餐厅"这类复杂名称
        keyword_matches = self._keyword_based_match(clean_name, city_poi_names, city_index)
        if keyword_matches:
            keyword_name, keyword_score = keyword_matches
            if keyword_score > best_score:
                best_match = keyword_name
                best_score = keyword_score

        # 7. 处理"商圈"、"附近"等后缀
        if best_score < 60 and ("商圈" in clean_name or "附近" in clean_name):
            base_name = clean_name.replace("商圈", "").replace("附近", "").strip()
            if base_name in city_index:
                best_match = base_name
                best_score = 80

        result = {'match_score': best_score, 'matched_name': best_match} if best_match and best_score >= 50 else {
            'match_score': 0, 'matched_name': None}
        self.match_cache[cache_key] = result
        return result

    def _normalized_match(self, search_name: str, city_poi_names: List[str], city_index: Dict) -> Dict:
        """
        标准化匹配 - 处理括号、店铺名称变体等
        例如："全聚德烤鸭店(前门店)" -> "北京全聚德(前门店)"
        """
        # 提取核心品牌名称和分店信息
        core_name, branch_info = self._extract_branch_info(search_name)

        if not core_name:
            return None

        # 在数据库中找到所有包含核心品牌名称的POI
        candidate_pois = []
        for poi_name in city_poi_names:
            if core_name in poi_name:
                candidate_pois.append(poi_name)

        if not candidate_pois:
            return None

        # 如果有分店信息，优先匹配分店
        if branch_info:
            # 精确分店匹配
            for poi_name in candidate_pois:
                poi_core, poi_branch = self._extract_branch_info(poi_name)
                if poi_branch and branch_info in poi_branch:
                    return {'match_score': 95, 'matched_name': poi_name}

            # 模糊分店匹配
            for poi_name in candidate_pois:
                poi_core, poi_branch = self._extract_branch_info(poi_name)
                if poi_branch and fuzz.partial_ratio(branch_info, poi_branch) >= 80:
                    return {'match_score': 85, 'matched_name': poi_name}

        # 如果没有分店信息或分店匹配失败，选择第一个候选（通常是总店或最知名的分店）
        if candidate_pois:
            return {'match_score': 80, 'matched_name': candidate_pois[0]}

        return None

    def _extract_branch_info(self, poi_name: str) -> tuple:
        """
        提取品牌核心名称和分店信息
        返回: (核心名称, 分店信息)
        """
        # 常见的品牌前缀（城市名）
        city_prefixes = ['北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '重庆', '武汉', '苏州']

        # 移除城市前缀
        clean_name = poi_name
        for prefix in city_prefixes:
            if poi_name.startswith(prefix):
                clean_name = poi_name[len(prefix):]
                break

        # 提取括号内的分店信息
        branch_match = re.search(r'[（(]([^）)]+)[）)]', clean_name)
        branch_info = branch_match.group(1) if branch_match else None

        # 提取核心品牌名称（移除括号和分店信息）
        if branch_match:
            core_name = clean_name[:branch_match.start()].strip()
        else:
            core_name = clean_name.strip()

        # 移除常见的描述性词汇
        descriptors = ['烤鸭店', '烤鸭', '餐厅', '饭店', '酒家', '大酒店']
        for desc in descriptors:
            core_name = core_name.replace(desc, '').strip()

        return core_name, branch_info

    def _match_in_stations(self, search_name: str) -> str:
        """在补充数据库中匹配POI名称"""
        clean_name = self._clean_poi_name(search_name)

        # 精确匹配
        if clean_name in self.stations:
            return clean_name

        # 尝试添加城市前缀进行匹配（如果提供了可能的城市列表）
        possible_cities = {
            "北京",
            "上海",
            "广州",
            "深圳",
            "杭州",
            "苏州",
            "南京",
            "武汉",
            "重庆",
            "成都"
        }
        for city in possible_cities:
            # 构造带城市前缀的名称（如 "北京亦庄站"）
            city_prefixed_name = f"{city}{clean_name}"
            if city_prefixed_name in self.stations:
                return city_prefixed_name

        # 模糊匹配
        matches = process.extract(clean_name, list(self.stations), limit=3, scorer=fuzz.token_sort_ratio)
        for match in matches:
            if len(match) == 3:
                matched_name, score, _ = match
            else:
                matched_name, score = match

            # print(score)

            if score >= 80:  # 车站匹配要求更高的分数
                return matched_name

        return ""

    def _keyword_based_match(self, search_name: str, city_poi_names: List[str], city_index: Dict) -> tuple:
        """
        基于关键词的匹配 - 处理复杂POI名称
        例如："迪士尼乐园内餐厅" -> "上海迪士尼度假区"
        """
        # 定义关键词映射规则
        keyword_rules = [
            # (搜索关键词, 目标POI关键词, 基础分数)
            (['迪士尼', '迪斯尼'], ['迪士尼'], 85),
            (['外滩'], ['外滩'], 90),
            (['东方明珠'], ['东方明珠'], 90),
            (['城隍庙'], ['城隍庙'], 85),
            (['豫园'], ['豫园'], 85),
            (['陆家嘴'], ['陆家嘴'], 85),
            (['新天地'], ['新天地'], 85),
            (['田子坊'], ['田子坊'], 85),
            (['朱家角'], ['朱家角'], 85),
            (['南京路'], ['南京路'], 80),
            (['徐家汇'], ['徐家汇'], 80),
            (['静安寺'], ['静安寺'], 80),
            (['全聚德'], ['全聚德'], 85),
            (['海底捞'], ['海底捞'], 85),
            (['肯德基', 'KFC'], ['肯德基'], 80),
            (['麦当劳', 'McDonald'], ['麦当劳'], 80),
            (['星巴克', 'Starbucks'], ['星巴克'], 80),
        ]

        best_keyword_match = None
        best_keyword_score = 0

        for search_keywords, target_keywords, base_score in keyword_rules:
            # 检查搜索名称是否包含关键词
            has_search_keyword = any(keyword in search_name for keyword in search_keywords)

            if has_search_keyword:
                # 在POI名称中寻找包含目标关键词的项
                for poi_name in city_poi_names:
                    has_target_keyword = any(keyword in poi_name for keyword in target_keywords)

                    if has_target_keyword:
                        # 计算额外相似度
                        extra_similarity = fuzz.partial_ratio(search_name, poi_name)
                        total_score = min(base_score + (extra_similarity * 0.1), 95)

                        if total_score > best_keyword_score:
                            best_keyword_match = poi_name
                            best_keyword_score = total_score

        # 通用关键词匹配：提取主要地名进行匹配
        if not best_keyword_match:
            # 移除常见修饰词，提取核心地名
            modifiers = ['内', '的', '里', '中', '上', '附近', '周边', '旁边', '一侧']
            core_name = search_name
            for modifier in modifiers:
                core_name = core_name.replace(modifier, ' ')

            # 分割并取最长的部分作为核心关键词
            parts = [part.strip() for part in core_name.split() if len(part.strip()) > 1]
            if parts:
                core_keyword = max(parts, key=len)

                # 在POI名称中寻找包含核心关键词的项
                for poi_name in city_poi_names:
                    if core_keyword in poi_name:
                        similarity = fuzz.partial_ratio(search_name, poi_name)
                        if similarity > best_keyword_score:
                            best_keyword_match = poi_name
                            best_keyword_score = max(similarity, 75)

        if best_keyword_match and best_keyword_score >= 70:
            return best_keyword_match, best_keyword_score

        return None

    def process_batch_files(self, input_pattern: str):
        """
        批量处理文件
        :param input_pattern: 输入文件模式，如 "*.json" 或 "itineraries/*.json"
        """
        input_files = glob.glob(input_pattern)
        logger.info(f"[INFO] 找到 {len(input_files)} 个待处理文件")

        for input_file in input_files:
            if input_file.endswith('_matched.json'):
                continue

            logger.info(f"\n{'=' * 50}")
            logger.info(f"处理文件: {input_file}")
            logger.info(f"{'=' * 50}")

            self.process_single_file(input_file)

    def process_single_file(self, input_file: str):
        """处理单个文件"""
        # 读取原文件
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"[FAIL] 读取文件失败: {e}")
            return

        # 处理数据
        processed_data = []
        total_stats = {'total_pois': 0, 'matched_pois': 0, 'unique_pois': 0, 'cache_hits': 0}
        all_failed_pois = set()  # 收集所有行程的失败POI

        for item in data:
            # 清空缓存，为每个行程创建新的缓存
            self.match_cache = {}
            processed_item, stats, failed_pois = self._process_single_itinerary(item)
            processed_data.append(processed_item)
            total_stats['total_pois'] += stats['total_pois']
            total_stats['matched_pois'] += stats['matched_pois']
            total_stats['unique_pois'] += stats['unique_pois']
            total_stats['cache_hits'] += stats['cache_hits']
            all_failed_pois.update(failed_pois)

        # 生成新文件名
        file_name_only = os.path.basename(input_file)
        base_name = os.path.splitext(file_name_only)[0]
        parent_dir = os.path.dirname(os.path.dirname(input_file))
        output_file = os.path.join(parent_dir, f"{base_name}_matched.json")

        # 保存新文件
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(processed_data, f, ensure_ascii=False, indent=2)

            logger.info(f"\n[SUMMARY] 总体匹配统计:")
            logger.info(f"   总POI引用次数: {total_stats['total_pois']}")
            logger.info(f"   唯一POI数量: {total_stats['unique_pois']}")
            logger.info(f"   匹配成功: {total_stats['matched_pois']}")
            logger.info(f"   缓存命中: {total_stats['cache_hits']} 次")
            logger.info(f"   匹配率: {(total_stats['matched_pois'] / total_stats['total_pois'] * 100):.1f}%")

            # # 输出总体失败POI列表
            # if all_failed_pois:
            #     logger.info(f"\n[FAIL] 文件总体匹配失败的POI ({len(all_failed_pois)} 个):")
            #     for i, poi in enumerate(sorted(all_failed_pois), 1):
            #         logger.info(f"   {i:2d}. {poi}")

            logger.info(f"[SUCCESS] 已保存: {output_file}")

        except Exception as e:
            logger.error(f"[FAIL] 保存文件失败: {e}")

    def _process_single_itinerary(self, itinerary_item: Dict):
        """处理单个行程"""
        query_uid = itinerary_item.get('query_uid', 'Unknown')
        itinerary_data = itinerary_item.get('itinerary', {})

        logger.info(f"\n[INFO] 处理行程: {query_uid}")

        # 获取目的地城市
        summary = itinerary_data.get('summary', {})
        destination = summary.get('destination', '')
        target_city = self._city_name_to_directory_name(destination)
        logger.info(f"[TARGET] 目的地: {destination} -> {target_city}")

        # 创建行程副本
        processed_itinerary = json.loads(json.dumps(itinerary_data))

        # 替换POI名称并统计
        stats, failed_pois = self._replace_poi_names(processed_itinerary, target_city)

        return {
            'query_uid': query_uid,
            'itinerary': processed_itinerary
        }, stats, failed_pois

    def _replace_poi_names(self, itinerary_data: Dict, target_city: str) -> tuple[dict[str, int], set[Any]]:
        """替换行程中的POI名称并返回统计信息"""
        stats = {'total_pois': 0, 'matched_pois': 0, 'unique_pois': 0, 'cache_hits': 0}
        processed_pois = set()  # 记录已处理的唯一POI
        failed_pois = set()  # 记录匹配失败的POI名称

        def process_field(field_value, field_type, field_desc):
            if not field_value or not isinstance(field_value, str):
                return field_value

            stats['total_pois'] += 1

            # 检查是否已经处理过这个POI
            cache_key = f"{field_value}_{target_city}"
            if cache_key in self.match_cache:
                stats['cache_hits'] += 1
                match_result = self.match_cache[cache_key]
                if match_result['matched_name'] and match_result['match_score'] >= self.min_score:
                    stats['matched_pois'] += 1
                    logger.info(f"  [SUCCESS] {field_desc}: {field_value} -> {match_result['matched_name']} (缓存)")
                    return match_result['matched_name']
                else:
                    logger.info(f"  [FAIL] {field_desc}: {field_value} (缓存未匹配)")
                    # 记录匹配失败
                    if field_value not in processed_pois:
                        failed_pois.add(field_value)
                    return field_value

            # 新POI，进行匹配
            if field_value not in processed_pois:
                processed_pois.add(field_value)
                stats['unique_pois'] += 1

                match_result = self._match_poi(field_value, target_city)

                if match_result['matched_name'] and match_result['match_score'] >= self.min_score:
                    stats['matched_pois'] += 1
                    logger.info(
                        f"  [SUCCESS] {field_desc}: {field_value} -> {match_result['matched_name']} ({match_result['match_score']}分)")
                    return match_result['matched_name']
                else:
                    logger.info(f"  [FAIL] {field_desc}: {field_value} (未匹配)")
                    # 记录匹配失败
                    failed_pois.add(field_value)
                    return field_value
            else:
                # 这个POI已经处理过，但不在缓存中（理论上不会发生）
                return field_value

        # 处理住宿
        accommodation = itinerary_data.get('accommodation', {})
        if accommodation.get('hotel_name'):
            accommodation['hotel_name'] = process_field(
                accommodation['hotel_name'], 'accommodation', '住宿'
            )

        # 处理交通
        transport = itinerary_data.get('intercity_transport', {})
        for i, transport_item in enumerate(transport.get('transport_type', [])):
            if transport_item.get('location_name'):
                transport_item['location_name'] = process_field(
                    transport_item['location_name'], 'transport', f'交通{i + 1}'
                )

        # 处理每日计划
        daily_plans = itinerary_data.get('daily_plans', [])
        for day_plan in daily_plans:
            # 起始点
            if day_plan.get('starting_point'):
                day_plan['starting_point'] = process_field(
                    day_plan['starting_point'], 'daily_plan', f'Day{day_plan.get("day", "?")}起始点'
                )

            # 结束点
            ending_point = day_plan.get('ending_point', {})
            if isinstance(ending_point, dict) and ending_point.get('location_name'):
                ending_point['location_name'] = process_field(
                    ending_point['location_name'], 'daily_plan', f'Day{day_plan.get("day", "?")}结束点'
                )

            # 活动
            for j, activity in enumerate(day_plan.get('activities', [])):
                if activity.get('location_name'):
                    activity['location_name'] = process_field(
                        activity['location_name'], 'activity', f'Day{day_plan.get("day", "?")}活动{j + 1}'
                    )

        # 输出匹配失败的POI列表
        if failed_pois:
            logger.info(f"\n[FAIL] 匹配失败的POI列表 ({len(failed_pois)} 个):")
            for i, poi in enumerate(sorted(failed_pois), 1):
                logger.info(f"   {i:2d}. {poi}")
        else:
            logger.info(f"\n[SUCCESS] 所有POI都匹配成功！")

        return stats, failed_pois


def main():
    """主函数"""
    # 配置参数
    POI_BASE_PATH = "../../environment/database/poi"  # POI数据库路径
    PLANS_BASE_PATH = "../../environment/data/plans/raw"  # 行程文件路径
    MIN_SCORE = 60  # 最小匹配分数

    file_name = {
        # "added_plans_gpt4o_Zero-shot CoT.json"
        # "added_plans_deepseek-chat_Direct Prompting.json",
        # "added_plans_deepseek-chat_Zero-shot CoT.json",
        # "added_plans_gemini-2.0-flash_Direct Prompting.json",
        # "added_plans_qwen3-8b_Direct Prompting.json",
        # "added_plans_gpt4o-mini_Direct Prompting.json",
        # "added_plans_gpt4o-mini_ReAct&Reflection.json",
        # "added_plans_gpt4o-mini_Zero-shot CoT.json",
        # "added_plans_gpt4o_Direct Prompting.json",
        # "plans_claude-sonnet-4-5-20250929_Direct Prompting.json",
        # "plans_gpt-5-chat_Direct Prompting.json",
        # "plans_deepseek-chat_Direct Prompting.json",
        # "plans_gpt4o_Direct Prompting.json",
        # "plans_gpt4o-mini_Direct Prompting.json",
        # "plans_gpt4o-mini_ReAct&Reflection.json",
        # "plans_qwen3-8b_Direct Prompting.json",
        "plans_gemini-2.0-flash_Direct Prompting.json"
        # "new_plans.json",
        # "plans_deepseek-chat_Zero-shot CoT.json",
        # "plans_gpt4o-mini_Zero-shot CoT.json",
        # "plans_gpt4o_Zero-shot CoT.json"
    }

    for INPUT_PATTERN in file_name:
        # 创建处理器
        processor = POIBatchProcessor(poi_base_path=POI_BASE_PATH, min_score=MIN_SCORE)

        input_pattern = os.path.join(PLANS_BASE_PATH, INPUT_PATTERN)

        # 批量处理文件
        processor.process_batch_files(input_pattern)

    # test_cases = [
    #     "迪士尼乐园内餐厅",  # → "上海迪士尼度假区"
    #     "外滩附近的酒店",  # → "外滩"
    #     "南京路商圈",  # → "南京路步行街"
    #     "东方明珠塔下",  # → "东方明珠广播电视塔"
    #     "城隍庙小吃街",  # → "城隍庙"
    #     "陆家嘴金融中心",  # → "陆家嘴"
    #     "全聚德",
    #     "上海虹桥",
    #     "上海虹桥火车站"
    # ]
    #
    # processor = POIBatchProcessor(poi_base_path=POI_BASE_PATH, min_score=MIN_SCORE)
    # for case in test_cases:
    #     result = processor._match_poi(case, "beijing")
    #     print(f"{case} -> {result['matched_name']} (分数: {result['match_score']})")


if __name__ == "__main__":
    main()

    # import sys
    #
    #
    # def find_min_weight_replacement(original_hotels, distance_lists):
    #     n = len(distance_lists)
    #     min_total_weight = sys.maxsize
    #     best_replacement = None
    #
    #     # 用于记录已经选过的 special_hotel_id，避免重复
    #     used_special_hotels = set()
    #
    #     def backtrack(index, current_replacement, current_weight):
    #         nonlocal min_total_weight, best_replacement
    #
    #         if index == n:
    #             if current_weight < min_total_weight:
    #                 min_total_weight = current_weight
    #                 best_replacement = current_replacement.copy()
    #             return
    #
    #         # 遍历当前距离列表的所有可能选择
    #         for original_id, special_id, weight in distance_lists[index]:
    #             if special_id not in used_special_hotels:
    #                 used_special_hotels.add(special_id)
    #                 current_replacement.append((original_id, special_id, weight))
    #                 backtrack(index + 1, current_replacement, current_weight + weight)
    #                 current_replacement.pop()
    #                 used_special_hotels.remove(special_id)
    #
    #     backtrack(0, [], 0)
    #     return best_replacement, min_total_weight
    #
    #
    # # 示例数据
    # original_hotels = ["H1", "H2", "H3"]
    # distance_lists = [
    #     [("H1", "S1", 10), ("H2", "S2", 20), ("H3", "S3", 30)],  # 距离列表 1
    #     [("H1", "S4", 5), ("H2", "S5", 15), ("H3", "S6", 25)],  # 距离列表 2
    #     [("H1", "S7", 8), ("H2", "S8", 18), ("H3", "S9", 28)],  # 距离列表 3
    # ]
    #
    # best_replacement, min_weight = find_min_weight_replacement(original_hotels, distance_lists)
    # print("最佳替换方案:", best_replacement)
    # print("最小总权值:", min_weight)
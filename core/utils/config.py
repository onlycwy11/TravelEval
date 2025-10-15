import os
import yaml
from typing import Dict, Any, Optional


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径，默认为项目根目录下的 config/metrics_config.yaml
        """
        if config_path is None:
            self.config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config', 'metrics_config.yaml'
            )
        else:
            self.config_path = config_path

        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = self._get_default_config()

        if not os.path.exists(self.config_path):
            print(f"配置文件不存在: {self.config_path}，使用默认配置")
            return default_config

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}

            # 合并配置（用户配置覆盖默认配置）
            merged_config = self._merge_configs(default_config, user_config)
            print(f"成功加载配置文件: {self.config_path}")
            return merged_config

        except Exception as e:
            print(f"加载配置文件失败: {e}，使用默认配置")
            return default_config

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'data_paths': {
                'database_root': 'environment/database',
                'queries_dir': 'data/queries',
                'plans_dir': 'data/plans',
                'results_dir': 'results'
            },
            'metrics': {
                'accuracy': {
                    'cost_deviation_threshold': 0.1,  # 费用偏差率阈值
                    'fictitious_attraction_penalty': 1.0,
                    'opening_hours_violation_penalty': 1.0
                },
                'constraint': {
                    'budget_tolerance': 0.05,  # 预算容忍度
                    'time_tolerance_minutes': 30
                },
                'time': {
                    'min_attraction_time_minutes': 30,
                    'max_attraction_time_minutes': 240,
                    'recommended_daily_hours': 8
                },
                'space': {
                    'gtr_alpha': 0.5,
                    'gtr_beta': 0.5,
                    'cdsfi_percentiles': [90, 95]
                },
                'economy': {
                    'cost_categories': ['attractions', 'intercity_transportation',
                                        'intracity_transportation', 'accommodation',
                                        'meals', 'other']
                },
                'utility': {
                    'diversity_normalization': True,
                    'min_attraction_quality': 3.0,
                    'target_attraction_density': {  # 改为字典，按节奏分类
                        '慢游': 2.00,
                        '普通': 3.54,
                        '亲子': 2.75,
                        '特种兵': 6.00
                    }
                }
            },
            'evaluation': {
                'max_workers': 4,
                'timeout_seconds': 300,
                'log_level': 'INFO'
            },
            'apis': {
                'gaode_api_key': '56335e8ed2298117890c03dcbd1728a0',
                'gaode_base_url': 'https://restapi.amap.com/v5/direction/walking',
                'request_timeout': 10,
                'rate_limit_delay': 0.5
            },
            'categories': {
                'accommodations': [
                    "管家服务", "桑拿", "家庭房", "SPA", "行政酒廊", "泳池", "智能客控", "免费停车", "山景房", "茶室",
                    "停车场", "自营亲子房", "窗外好景", "日光浴场", "机器人服务", "Boss推荐", "网红泳池", "动人夜景",
                    "私人泳池", "江河景房", "棋牌室", "私汤房", "充电桩", "酒店公寓", "影音房", "亲子主题房", "空气净化器",
                    "多功能厅", "民宿", "智能马桶", "情侣房", "儿童俱乐部", "健身室", "24小时前台", "儿童乐园", "湖景房",
                    "温泉", "拍照出片", "洗衣房", "设计师酒店", "会议厅", "四合院", "套房", "桌球室", "洗衣服务", "行李寄存",
                    "提前入园", "美食酒店", "温泉泡汤", "电竞房", "空调", "商务中心", "穿梭机场班车", "洗衣机", "小而美", "别墅",
                    "湖畔美居", "中式庭院", "历史名宅", "园林建筑", "钓鱼", "客栈", "特色住宿", "自营影音房", "电竞酒店", "老洋房",
                    "厨房", "海景房", "迷人海景", "农家乐", "自营舒睡房", "位置超好", "儿童泳池", "宠物友好"
                ],
                'diet': [
                    "小吃", "面包甜点", "快餐简餐", "烧烤", "茶馆/茶室", "素食", "咖啡店", "粤菜", "湖北菜", "日本料理",
                    "韩国料理", "清真菜", "西餐", "火锅", "本帮菜", "江浙菜", "川菜", "西北菜", "东南亚菜", "新疆菜",
                    "其他中餐", "创意菜", "湘菜", "北京菜", "农家菜", "台湾菜", "海鲜", "客家菜", "酒吧/酒馆", "东北菜",
                    "其他", "自助餐", "融合菜", "云南菜", "徽菜", "鲁菜", "西藏菜", "中东料理", "闽菜", "海南菜",
                    "拉美料理", "亚洲菜"
                ],
                'attractions': [
                    "网红打卡点", "沉浸式体验", "夜经济热点", "亲子友好", "小众秘境", "城市地标", "美食目的地",
                    "节庆限定", "非遗体验", "宠物特色", "历史古迹", "博物馆/纪念馆", "自然风光", "人文景观",
                    "大学校园", "美术馆/艺术馆", "红色景点", "游乐园/体育娱乐", "图书馆", "园林", "其它",
                    "文化旅游区", "公园", "商业街区"
                ],
                'rhythm': [
                    "慢游", "特种兵式", "亲子家庭游", "普通"
                ]
            },
            'waiting_time': {
                "B_category": {
                    "人文景观": 3.0,
                    "园林": 3.0,
                    "自然风光": 3.5,
                    "历史古迹": 4.0,
                    "游乐园/体育娱乐": 6.0,
                    "博物馆/纪念馆": 10.0
                },
                "K_date": {
                    "Golden Week": 10.06,
                    "Weekend": 7.55,
                    "Peak Season": 4.63,
                    "Short Holiday": 4.39,
                    "Vacation": 3.94,
                    "Weekday": 1.00
                },
                "K_time": {
                    "08:00-10:00": 0.85,
                    "10:00-12:00": 0.90,
                    "12:00-16:00": 1.10,
                    "16:00-20:00": 1.10,
                    "20:00-close": 0.70
                }
            }
        }

    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """递归合并配置字典"""
        merged = default.copy()

        for key, value in user.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value

        return merged

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        current = self._config

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default

        return current

    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        current = self._config

        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def save_config(self, file_path: Optional[str] = None):
        """保存配置到文件"""
        save_path = file_path or self.config_path

        # 确保目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True, indent=2)
            print(f"配置已保存到: {save_path}")
        except Exception as e:
            print(f"保存配置失败: {e}")

    def get_metric_config(self, metric_name: str) -> Dict[str, Any]:
        """获取指定指标的配置"""
        return self.get(f'metrics.{metric_name}', {})

    def get_apis_config(self) -> Dict[str, Any]:
        return self.get('apis', {})

    def get_categories_config(self) -> Dict[str, Any]:
        return self.get('categories', {})

    def get_waiting_time(self) -> Dict[str, Any]:
        return self.get('waiting_time', {})

    def get_data_path(self, path_type: str) -> str:
        """获取数据路径"""
        relative_path = self.get(f'data_paths.{path_type}')
        if relative_path:
            return os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                relative_path
            )
        return ''

    def reload(self):
        """重新加载配置"""
        self._config = self._load_config()

    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config.copy()
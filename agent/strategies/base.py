from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set
from agent.schemas.travel_plan import FinalTravelPlan


class BaseStrategy(ABC):
    """策略基类"""

    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name

    @abstractmethod
    def get_system_prompt(self, station_constraints: Set) -> str:
        """获取系统提示词"""
        pass

    @abstractmethod
    def get_user_prompt(self, user_query: Dict) -> str:
        """获取用户提示词"""
        pass

    def create_messages(self, user_query: Dict, station_constraints: Set) -> list:
        """创建消息列表"""
        system_content = self.get_system_prompt(station_constraints)
        user_content = self.get_user_prompt(user_query)

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
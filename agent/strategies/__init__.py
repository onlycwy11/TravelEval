from .base import BaseStrategy
from .direct import DirectPromptingStrategy
from .zero_shot_cot import ZeroShotCoTStrategy
from .react_reflection import ReActReflexionStrategy


class StrategyFactory:
    """策略工厂类"""

    @staticmethod
    def create_strategy(strategy_name: str, **kwargs) -> BaseStrategy:
        """
        创建策略实例

        Args:
            strategy_name: 策略名称
            **kwargs: 策略特定参数

        Returns:
            策略实例
        """
        strategies = {
            "Direct Prompting": DirectPromptingStrategy,
            "Zero-shot CoT": ZeroShotCoTStrategy,
            "ReAct&Reflexion": ReActReflexionStrategy
        }

        if strategy_name not in strategies:
            raise ValueError(f"不支持的策略: {strategy_name}")

        strategy_class = strategies[strategy_name]
        return strategy_class(**kwargs)


__all__ = [
    'BaseStrategy',
    'DirectPromptingStrategy',
    'ZeroShotCoTStrategy',
    'ReActReflexionStrategy',
    'StrategyFactory'
]
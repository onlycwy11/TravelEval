import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from .metrics.accuracy import AccuracyMetrics
from .metrics.constraint import ConstraintMetrics
from .metrics.time import TimeMetrics
from .metrics.space import SpaceMetrics
from .metrics.economy import EconomyMetrics
from .metrics.utility import UtilityMetrics
from .utils.config import ConfigManager
from .utils.validators import DataValidators
from .utils.plan_extractors import PlanExtractor


class TravelPlanEvaluator:
    """
    AI旅行规划评估器
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化评估器

        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        self.config_manager = ConfigManager()
        if config:
            for key, value in config.items():
                self.config_manager.set(key, value)

        # 初始化各维度评估器
        self.metrics = {
            'accuracy': AccuracyMetrics(self.config_manager),
            'constraint': ConstraintMetrics(self.config_manager),
            'time': TimeMetrics(self.config_manager),
            'space': SpaceMetrics(self.config_manager),
            'economy': EconomyMetrics(self.config_manager),
            'utility': UtilityMetrics(self.config_manager)
        }

        self.validators = DataValidators()

        print("TravelPlanEvaluator 初始化完成")

    def evaluate_single_plan(self,
                             user_query: Dict[str, Any],
                             ai_plan: Dict[str, Any],
                             sandbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估单个规划方案

        Args:
            user_query: 用户提问数据
            ai_plan: AI生成的规划方案
            sandbox_data: 沙盒数据（景点、交通等真实数据）

        Returns:
            评估结果字典
        """
        start_time = time.time()

        # 验证输入数据
        is_valid_query, query_errors = self.validators.validate_user_query(user_query)
        is_valid_plan, plan_errors = self.validators.validate_ai_plan(ai_plan)

        if not is_valid_query or not is_valid_plan:
            return {
                'query_id': user_query.get('uid', 'unknown'),
                'evaluation_time': datetime.now().isoformat(),
                'status': 'error',
                'errors': {
                    'query_errors': query_errors,
                    'plan_errors': plan_errors
                },
                'overall_score': 0,
                'dimension_scores': {},
                'detailed_metrics': {}
            }

        # 提取规划方案的关键信息（供各维度指标使用）
        try:
            daily_attractions = PlanExtractor._extract_daily_attractions(ai_plan)
            attraction_sequence = PlanExtractor._extract_attraction_sequence(ai_plan)
            daily_schedules = PlanExtractor._extract_daily_schedules(ai_plan)
            cost_breakdown = PlanExtractor._extract_cost_breakdown(ai_plan)
            plan_summary = PlanExtractor._extract_plan_summary(ai_plan)

            # 创建增强的规划数据
            enhanced_plan = {
                'original_plan': ai_plan,
                'extracted_data': {
                    'daily_attractions': daily_attractions,
                    'attraction_sequence': attraction_sequence,
                    'daily_schedules': daily_schedules,
                    'cost_breakdown': cost_breakdown,
                    'plan_summary': plan_summary
                }
            }

        except Exception as e:
            print(f"提取规划方案信息失败: {e}")
            return {
                'query_id': user_query.get('uid', 'unknown'),
                'plan_id': ai_plan.get('query_uid', 'unknown'),
                'evaluation_time': datetime.now().isoformat(),
                'status': 'error',
                'error': f"提取规划方案信息失败: {e}",
                'overall_score': 0,
                'dimension_scores': {},
                'detailed_metrics': {}
            }

        # 执行各维度评估
        results = {
            'query_id': user_query.get('uid'),
            'evaluation_time': datetime.now().isoformat(),
            'status': 'success',
            'dimension_scores': {},
            'detailed_metrics': {},
            'extraction_info': {
                'total_days': len(daily_attractions),
                'total_attractions': len(attraction_sequence),
                'daily_attraction_counts': {day: len(atts) for day, atts in daily_attractions.items()}
            },
            'validation': {
                'query_valid': is_valid_query,
                'plan_valid': is_valid_plan
            }
        }

        try:
            # 并行或顺序执行各维度评估
            for dimension, metric_calculator in self.metrics.items():
                dimension_start = time.time()

                dimension_results = metric_calculator.calculate_all(
                    user_query, enhanced_plan, sandbox_data
                )

                # results['dimension_scores'][dimension] = dimension_results.get('score', 0)
                results['detailed_metrics'][dimension] = dimension_results
                results['detailed_metrics'][dimension]['calculation_time'] = time.time() - dimension_start

            # 计算综合得分（简单平均，权重在具体指标内部处理）
            # results['overall_score'] = self._calculate_overall_score(results['dimension_scores'])

            # 添加评估元数据
            results['evaluation_metadata'] = {
                'total_calculation_time': time.time() - start_time,
                'config_version': '1.0'
            }

        except Exception as e:
            results['status'] = 'error'
            results['error'] = str(e)
            results['overall_score'] = 0
            print(f"评估过程中发生错误: {e}")

        return results

    def evaluate_batch(self,
                       queries: Dict[str, Any],
                       plans: Dict[str, Dict[str, Any]],
                       sandbox_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量评估多个规划方案

        Args:
            queries: 用户提问列表
            plans: AI方案字典 {query_id: plan}
            sandbox_data: 沙盒数据

        Returns:
            批量评估结果
        """
        batch_results = {
            'batch_id': f"batch_{int(time.time())}",
            'evaluation_time': datetime.now().isoformat(),
            'total_queries': len(queries),
            'evaluated_plans': 0,
            'results': {},
            'summary_stats': {}
        }

        successful_evaluations = 0
        total_score = 0
        dimension_totals = {dim: 0 for dim in self.metrics.keys()}

        # for query in queries:
        #     query_id = query.get('uid')
        #     if query_id in plans:
        for query_id, itinerary in plans.items():
            # 从用户提问字典中查找对应的用户提问
            user_query = queries.get(query_id)
            if user_query:
                plan_result = self.evaluate_single_plan(user_query, itinerary, sandbox_data)
                batch_results['results'][query_id] = plan_result

                if plan_result['status'] == 'success':
                    successful_evaluations += 1
                    # total_score += plan_result['overall_score']

                    # 累加各维度分数
                    # for dim, score in plan_result['dimension_scores'].items():
                    #     dimension_totals[dim] += score

        # 计算统计信息
        batch_results['evaluated_plans'] = successful_evaluations
        if successful_evaluations > 0:
            batch_results['summary_stats'] = {
                'successful_evaluations': successful_evaluations,
                # 'average_dimension_scores': {
                #     dim: score / successful_evaluations
                #     for dim, score in dimension_totals.items()
                # },
                'success_rate': successful_evaluations / len(queries)
            }

        return batch_results

    def _calculate_overall_score(self, dimension_scores: Dict[str, float]) -> float:
        """
        计算综合得分

        Args:
            dimension_scores: 各维度得分字典

        Returns:
            综合得分 (0-100)
        """
        if not dimension_scores:
            return 0.0

        # 简单平均，具体权重在各维度内部处理
        total_score = sum(dimension_scores.values())
        return total_score / len(dimension_scores)

    def get_evaluation_report(self, results: Dict[str, Any]) -> str:
        """
        生成评估报告

        Args:
            results: 评估结果

        Returns:
            格式化报告字符串
        """
        if results['status'] != 'success':
            return f"评估失败: {results.get('error', '未知错误')}"

        report = []
        report.append("=" * 60)
        report.append("AI旅行规划评估报告")
        report.append("=" * 60)
        report.append(f"查询ID: {results['query_id']}")
        report.append(f"评估时间: {results['evaluation_time']}")
        report.append(f"综合得分: {results['overall_score']:.2f}/100")
        report.append("")
        report.append("各维度得分:")

        for dimension, score in results['dimension_scores'].items():
            report.append(f"  {dimension.upper():<12}: {score:.2f}/100")

        report.append("")
        report.append("详细指标:")

        for dimension, metrics in results['detailed_metrics'].items():
            report.append(f"  {dimension.upper()}:")
            for metric, value in metrics.items():
                if metric not in ['score', 'calculation_time']:
                    if isinstance(value, (int, float)):
                        report.append(f"    {metric}: {value:.4f}")
                    else:
                        report.append(f"    {metric}: {value}")

        return "\n".join(report)

    def save_results(self, results: Dict[str, Any], file_path: str):
        """
        保存评估结果到文件

        Args:
            results: 评估结果
            file_path: 文件路径
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"评估结果已保存到: {file_path}")
        except Exception as e:
            print(f"保存结果失败: {e}")
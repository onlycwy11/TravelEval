import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from core.metrics.accuracy import AccuracyMetrics
from core.metrics.constraint import ConstraintMetrics
from core.metrics.time import TimeMetrics
from core.metrics.space import SpaceMetrics
from core.metrics.economy import EconomyMetrics
from core.metrics.utility import UtilityMetrics
from core.utils.config import ConfigManager
from core.utils.data_loader import DataLoader
from core.utils.validators import DataValidators
from core.utils.plan_extractors import PlanExtractor
from core.utils.result_writer import ExcelResultWriter


class TravelPlanEvaluator:
    """
    AI旅行规划评估器
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, excel_output_path: str = "evaluation_results.xlsx"):
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

        self.data_loader = DataLoader()
        self.validators = DataValidators()

        # 初始化Excel写入器
        self.excel_writer = ExcelResultWriter(excel_output_path)

        print("TravelPlanEvaluator 初始化完成")

    def evaluate_single_plan(self,
                             user_query: Dict[str, Any],
                             ai_plan: Dict[str, Any],
                             sandbox_data: Dict[str, Any],
                             save_to_excel: bool = True) -> Dict[str, Any]:
        """
        评估单个规划方案

        Args:
            user_query: 用户提问数据
            ai_plan: AI生成的规划方案
            sandbox_data: 沙盒数据（景点、交通等真实数据）
            save_to_excel: 保存方式

        Returns:
            评估结果字典
        """
        start_time = time.time()

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
            result = {
                'query_id': user_query.get('uid', 'unknown'),
                'evaluation_time': datetime.now().isoformat(),
                'status': 'error',
                'error': f"提取规划方案信息失败: {e}",
                # 'overall_score': 0,
                # 'dimension_scores': {},
                'detailed_metrics': {}
            }
            if save_to_excel:
                self.excel_writer.add_evaluation_result(result)
                self.excel_writer.save_to_excel()
            return result

        # 执行各维度评估
        results = {
            'query_id': user_query.get('uid'),
            'evaluation_time': datetime.now().isoformat(),
            'status': 'success',
            'error': "",
            # 'dimension_scores': {},
            'detailed_metrics': {},
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
            # results['overall_score'] = 0
            print(f"评估过程中发生错误: {e}")

        # 保存到Excel
        if save_to_excel:
            self.excel_writer.all_results = []
            self.excel_writer.add_evaluation_result(results)
            self.excel_writer.save_to_excel()

        return results

    def evaluate_batch(self,
                       queries: Dict[str, Any],
                       plans: Dict[str, Dict[str, Any]],
                       batch_save_to_excel: bool = False) -> Dict[str, Any]:
        """
        批量评估多个规划方案

        Args:
            queries: 用户提问列表
            plans: AI方案字典 {query_id: plan}
            sandbox_data: 沙盒数据
            batch_save_to_excel: 保存方式

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
            # if query_id not in ["T0219", "T0855", "T0908", "T0957", "T0641", "G32-1", "G32-2", "G32-3", "T0555"]:
            #     continue
            # if query_id[0] == 'G' or int(query_id[1:]) <= 450:
            #     continue
            # if query_id not in ["T0410"]:
            #     continue

            user_query = queries.get(query_id)
            count = 1
            while not user_query and count <= 3:
                schema = f"_scheme{count}"
                query_id = query_id.replace(schema, "")
                user_query = queries.get(query_id)
                count += 1

            if user_query:
                sandbox_data = self.data_loader.load_sandbox_data(itinerary.get('summary').get('destination'))
                plan_result = self.evaluate_single_plan(user_query, itinerary, sandbox_data, not batch_save_to_excel)

                if query_id in batch_results['results']:
                    count = 1
                    new_query_id = f"{query_id}_scheme{count}"
                    while new_query_id in batch_results['results']:
                        count += 1
                        new_query_id = f"{query_id}_scheme{count}"
                    # 更新plan_result中的query_id
                    # plan_result['query_id'] = new_query_id
                    batch_results['results'][new_query_id] = plan_result
                    print(new_query_id)
                else:
                    batch_results['results'][query_id] = plan_result
                # batch_results['results'][query_id] = plan_result

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
                'success_rate': successful_evaluations / len(plans)
            }

        # 批量保存到Excel
        if batch_save_to_excel:
            self.excel_writer.all_results = []
            for query_id, result in batch_results['results'].items():
                self.excel_writer.add_evaluation_result(result)
            self.excel_writer.save_to_excel()

        return batch_results

    def save_results_to_excel(self):
        """手动保存结果到Excel"""
        self.excel_writer.save_to_excel()

    def get_excel_stats(self) -> Dict[str, Any]:
        """获取Excel统计信息"""
        return {
            'total_records': len(self.excel_writer.all_results),
            'excel_path': self.excel_writer.excel_path,
            'success_count': sum(1 for r in self.excel_writer.all_results if r.get('status') == 'success')
        }

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

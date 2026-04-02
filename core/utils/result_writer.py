import pandas as pd
import os
from typing import Dict, List, Any
from datetime import datetime


class ExcelResultWriter:
    def __init__(self, excel_path: str):
        """
        初始化Excel写入器

        Args:
            excel_path: Excel文件路径
        """
        self.excel_path = excel_path
        self.column_headers = []  # 存储所有列名
        self.all_results = []  # 存储所有评估结果

        # 如果文件不存在，创建空的DataFrame
        if not os.path.exists(excel_path):
            self._initialize_excel_file()

    def _initialize_excel_file(self):
        """初始化Excel文件"""
        df = pd.DataFrame()
        df.to_excel(self.excel_path, index=False)
        print(f"✅ 已创建Excel文件: {self.excel_path}")

    def _flatten_dict(self, nested_dict: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """
        将嵌套字典展平为一维字典

        Args:
            nested_dict: 嵌套字典
            parent_key: 父级键名
            sep: 分隔符

        Returns:
            展平后的字典
        """
        items = []
        for k, v in nested_dict.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k

            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # 处理列表，将列表转换为字符串或展开
                if all(isinstance(item, dict) for item in v):
                    # 如果列表元素都是字典，展开处理
                    for i, item in enumerate(v):
                        items.extend(self._flatten_dict(item, f"{new_key}_{i}", sep=sep).items())
                else:
                    # 否则转换为字符串
                    items.append((new_key, str(v)))
            else:
                items.append((new_key, v))

        return dict(items)

    def _extract_all_columns(self, results: List[Dict]):
        """
        从所有结果中提取所有可能的列名

        Args:
            results: 评估结果列表
        """
        all_columns = set()

        for result in results:
            flattened = self._flatten_dict(result)
            all_columns.update(flattened.keys())

        # 按照特定的顺序排列列名
        ordered_columns = []

        # 首先添加基本信息
        basic_columns = ['query_id', 'evaluation_time', 'status']
        for col in basic_columns:
            if col in all_columns:
                ordered_columns.append(col)
                all_columns.remove(col)

        # 然后按维度添加
        dimensions = ['accuracy', 'constraint', 'time', 'space', 'economy', 'utility']
        for dim in dimensions:
            dim_columns = [col for col in all_columns if
                           col.startswith(f"{dim}_") or col.startswith(f"detailed_metrics_{dim}")]
            for col in sorted(dim_columns):
                ordered_columns.append(col)
                all_columns.remove(col)

        # 添加剩余的列
        ordered_columns.extend(sorted(all_columns))

        self.column_headers = ordered_columns

    def add_evaluation_result(self, evaluation_result: Dict):
        """
        添加单次评估结果

        Args:
            evaluation_result: 评估结果字典
        """
        # 确保query_id存在
        if 'query_id' not in evaluation_result:
            evaluation_result['query_id'] = f"query_{len(self.all_results)}"

        # 添加时间戳
        if 'evaluation_time' not in evaluation_result:
            evaluation_result['evaluation_time'] = datetime.now().isoformat()

        self.all_results.append(evaluation_result)

        # 更新列头
        self._extract_all_columns(self.all_results)

        print(f"✅ 已添加评估结果: {evaluation_result['query_id']}")

    def add_batch_results(self, batch_results: Dict):
        """
        添加批量评估结果

        Args:
            batch_results: 批量评估结果
        """
        if 'results' in batch_results:
            for query_id, result in batch_results['results'].items():
                # 确保每个结果都有query_id
                result['query_id'] = query_id
                self.add_evaluation_result(result)
        else:
            print("❌ 批量结果格式错误，缺少'results'字段")

    def save_to_excel(self):
        """
        将结果保存到Excel文件
        """
        if not self.all_results:
            print("❌ 没有评估结果可保存")
            return

        try:
            # 检查文件是否存在且不为空
            if os.path.exists(self.excel_path) and os.path.getsize(self.excel_path) > 0:
                # 读取现有数据
                existing_df = pd.read_excel(self.excel_path)
                # print(existing_df)
            else:
                # 创建新的 DataFrame
                existing_df = pd.DataFrame(columns=self.column_headers)

            # 创建新数据的 DataFrame
            rows = []
            for result in self.all_results:
                flattened = self._flatten_dict(result)
                row = {col: flattened.get(col, '') for col in self.column_headers}
                rows.append(row)
            # print(rows)

            new_df = pd.DataFrame(rows, columns=self.column_headers)

            # 在合并之前，排除空列或全为 NA 的列
            existing_df = existing_df.dropna(axis=1, how='all')
            new_df = new_df.dropna(axis=1, how='all')

            # 合并现有数据和新数据
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)

            # 保存到Excel
            combined_df.to_excel(self.excel_path, index=False)

            print(f"✅ 评估结果已保存到: {self.excel_path}")
            print(f"📊 总计 {len(combined_df)} 条评估记录")
            print(f"📋 列数: {len(self.column_headers)}")

            # 显示前几列的信息
            if len(self.column_headers) > 0:
                print(f"📝 前10个列名: {self.column_headers[:10]}")

        except Exception as e:
            print(f"❌ 保存Excel文件失败: {e}")

    def get_current_stats(self) -> Dict:
        """
        获取当前统计信息

        Returns:
            统计信息字典
        """
        return {
            'total_records': len(self.all_results),
            'total_columns': len(self.column_headers),
            'excel_path': self.excel_path,
            'success_count': sum(1 for r in self.all_results if r.get('status') == 'success'),
            'error_count': sum(1 for r in self.all_results if r.get('status') == 'error')
        }


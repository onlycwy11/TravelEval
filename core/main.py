import os
from evaluator import TravelPlanEvaluator
from core.utils.result_writer import ExcelResultWriter
from core.utils.data_loader import DataLoader


def main():
    user_queries = {}
    data_loader = DataLoader()
    base_path = os.path.dirname(os.path.dirname(__file__))

    # excel_output_path = os.path.join(base_path, 'environment', 'data', 'results', 'test.xlsx')
    # # 初始化评估器（指定Excel文件路径）
    # evaluator = TravelPlanEvaluator(excel_output_path=excel_output_path)
    # user_query = create_test_query()
    # ai_plan = create_test_plan()
    # sandbox_data = data_loader.load_sandbox_data(ai_plan.get('summary').get('destination'))

    # 单条评估（自动保存到Excel）
    # result = evaluator.evaluate_single_plan(user_query, ai_plan, sandbox_data)
    # print(result)

    # user_queries = {}
    for file_name in ['easy.json', 'medium.json', 'hard.json', 'progressive.json']:
        user_queries = {}
        file_path = os.path.join(base_path, 'environment', 'data', 'queries', file_name)
        return_value = data_loader.load_user_queries(file_path)
        user_queries.update(return_value)

        plan_file_names = [
            # "new_plans_matched.json",
            # "plans_gemini-2.0-flash_Direct Prompting_matched.json",
            # "plans_deepseek-chat_Direct Prompting_matched.json",
            # "plans_deepseek-chat_Zero-shot CoT_matched.json",
            # "plans_gpt4o_Direct Prompting_matched.json",
            # "plans_gpt4o_Zero-shot CoT_matched.json",
            # "plans_gpt4o-mini_Direct Prompting_matched.json",
            # "plans_gpt4o-mini_Zero-shot CoT_matched.json",
            # "plans_gpt4o-mini_ReAct&Reflection_matched.json",
            # "plans_qwen3-8b_Direct Prompting_matched.json",
            # "plans_gpt-5-chat_Direct Prompting_matched.json",
            # "plans_claude-sonnet-4-5-20250929_Direct Prompting_matched.json",
            # "added_plans_deepseek-chat_Direct Prompting_matched.json",
            # "added_plans_deepseek-chat_Zero-shot CoT_matched.json",
            # "added_plans_gemini-2.0-flash_Direct Prompting_matched.json",
            # "added_plans_qwen3-8b_Direct Prompting_matched.json",
            # "added_plans_gpt4o_Zero-shot CoT_matched.json",
            # "added_plans_gpt4o_Direct Prompting_matched.json",
            # "added_plans_gpt4o-mini_Direct Prompting_matched.json",
            # "added_plans_gpt4o-mini_Zero-shot CoT_matched.json",
            # "added_plans_gpt4o-mini_ReAct&Reflection_matched.json"
            # "test_plan.json"
            # "plans_our-method_matched.json",
            # "plans_our-method-strict_matched.json",
            "plans_our-method-strict-1_matched.json"
        ]

        for file_name in plan_file_names:
            file_path = os.path.join(base_path, 'environment', 'data', 'plans', file_name)
            ai_plans = data_loader.load_ai_plans(file_path)

            # 提取文件名中的基本部分（去掉扩展名）
            base_name = os.path.splitext(file_name)[0]
            # 构造新的文件名
            new_file_name = f"{base_name}_test.xlsx"
            excel_output_path = os.path.join(base_path, 'environment', 'data', 'results', new_file_name)
            evaluator = TravelPlanEvaluator(excel_output_path=excel_output_path)
            # 批量评估（自动保存到Excel）
            batch_results = evaluator.evaluate_batch(user_queries, ai_plans)

            print("=" * 10)
            print(batch_results["summary_stats"])
            print("=" * 10)

            # 手动保存（如果需要）
            # evaluator.save_results_to_excel()

            # 查看统计
            stats = evaluator.get_excel_stats()
            print(stats)


# 使用示例
if __name__ == "__main__":
    main()
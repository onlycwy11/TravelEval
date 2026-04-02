import sys
import os
import re
import glob
import yaml
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.main import main as original_main
from agent.strategies.direct import DirectPromptingStrategy
from agent.strategies.zero_shot_cot import ZeroShotCoTStrategy
from agent.strategies.react_reflection import ReActReflexionStrategy
from agent.models.model_router import ModelRouter

from core.evaluator import TravelPlanEvaluator
from core.utils.data_loader import DataLoader
from core.utils.poi_matcher import POIBatchProcessor
from core.utils.config import ConfigManager

# ==============================
# 内置模型列表
# ==============================
BUILTIN_MODELS = [
    "gpt4o",
    "gpt-5-chat",
    "gpt4o-mini",
    "claude-sonnet-4-5-20250929",
    "gemini-2.0-flash",
    "deepseek-chat",
    "qwen3-8b"
]


# ==========================
# 生成配置文件
# ==========================
def generate_config_if_missing():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(root_dir, "config")
    config_path = os.path.join(config_dir, "metrics_config.yaml")

    # 如果配置已存在，直接返回
    if os.path.exists(config_path):
        print(f"✅ Config already exists: {config_path}")
        return

    # 不存在 → 创建配置目录
    os.makedirs(config_dir, exist_ok=True)

    print("\n==========================================")
    print("⚙️  First run: Please input GAODE API Key")
    print("==========================================")

    # 让用户输入 API KEY
    gaode_api_key = input("Please input your Gaode API Key: ").strip()
    while not gaode_api_key:
        gaode_api_key = input("API Key cannot be empty! Re-input: ").strip()

    # ============== 加载默认配置 ==============
    default_config = ConfigManager()._get_default_config()

    # ============== 只修改高德API ==============
    default_config["apis"]["gaode_api_key"] = gaode_api_key

    # ============== 保存配置文件 ==============
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, indent=2)

    print(f"\n✅ Config file created: {config_path}")
    print(f"✅ Gaode API Key saved: {gaode_api_key}\n")


# ==============================
# 选择策略
# ==============================
def choose_strategies():
    # print("\n===== 选择策略 =====")
    print("\n===== Select Strategies =====")
    print("1. DirectPrompting")
    print("2. ZeroShotCoT")
    print("3. ReAct&Reflexion")
    print("4. All Strategies")
    while True:
        c = input("Input number (1-4): ").strip()
        if c == "1": return [DirectPromptingStrategy()]
        if c == "2": return [ZeroShotCoTStrategy()]
        if c == "3": return [ReActReflexionStrategy()]
        if c == "4": return [DirectPromptingStrategy(), ZeroShotCoTStrategy(), ReActReflexionStrategy()]
        print("Invalid input!")


# ==============================
# 选择模型：支持 内置 / all / 自定义（输入信息）
# ==============================
def choose_models(model_router: ModelRouter):
    print("\n===== Select Models =====")
    for i, m in enumerate(BUILTIN_MODELS, 1):
        print(f"{i}. {m}")
    print(f"{len(BUILTIN_MODELS) + 1}. All Built-in Models")  # 所有内置模型
    print(f"{len(BUILTIN_MODELS) + 2}. [Custom Model]")  # 【自定义模型】

    total = len(BUILTIN_MODELS)
    while True:
        choice = input(f"Input (1~{total + 2}): ").strip()
        if not choice.isdigit():
            print("Please Input a number")
            continue

        c = int(choice)
        if 1 <= c <= total:
            return [BUILTIN_MODELS[c - 1]]

        elif c == total + 1:
            return BUILTIN_MODELS.copy()

        elif c == total + 2:
            # ========== 【核心】用户输入自定义模型信息 ==========
            print("\n===== Please Input Custom Model Information =====")
            model_key = input("Model Name (custom): ").strip()
            model_type = input("Model Type (openai/qwen/gemini): ").strip()
            api_key = input("API Key: ").strip()
            base_url = input("Base URL: ").strip()
            model_name = input("Actual Model Name: ").strip()
            temperature = float(input("Temperature (default 0.7): ") or 0.7)
            max_tokens = int(input("Max Tokens(default 4096): ") or 4096)

            # 动态加入模型
            model_router.add_custom_model(model_key, model_type, {
                "api_key": api_key,
                "base_url": base_url,
                "model_name": model_name,
                "temperature": temperature,
                "max_tokens": max_tokens
            })
            return [model_key]


def auto_run_poi_clean():
    print("\n==================================================")
    print("Start automatic POI name standardization cleaning...")
    print("====================================================")

    # 跨平台路径（Windows / Ubuntu 通用）
    root_dir = os.path.dirname(os.path.abspath(__file__))
    poi_base_path = os.path.join(root_dir, "environment", "database", "poi")
    plans_raw_path = os.path.join(root_dir, "environment", "data", "plans", "raw")

    # 初始化清洗器
    processor = POIBatchProcessor(poi_base_path=poi_base_path, min_score=60)

    # 自动清洗刚刚生成的所有计划文件
    all_plan_files = glob.glob(os.path.join(plans_raw_path, "*.json"))

    for file_path in all_plan_files:
        print(f"\nCleaning：{os.path.basename(file_path)}")
        processor.process_single_file(file_path)

    print("\n✅ POI cleaning is complete! Generated _matched.json file\n")


# ==========================
# 【自动评估】清洗后的文件
# ==========================
def auto_run_evaluation():
    print("\n=============================================")
    print("Start automatic evaluation of travel plans...")
    print("=============================================")

    root_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = root_dir

    # 1. 加载所有查询文件
    user_queries = {}
    data_loader = DataLoader()

    for query_file in ['easy.json', 'medium.json', 'hard.json', 'progressive.json']:
        file_path = os.path.join(base_path, 'environment', 'data', 'queries', query_file)
        user_queries.update(data_loader.load_user_queries(file_path))

    # 2. 评估 plans/ 目录下 所有以 _matched.json 结尾的文件
    plans_dir = os.path.join(base_path, 'environment', 'data', 'plans')
    plan_files = glob.glob(os.path.join(plans_dir, "*_matched.json"))

    for file_path in plan_files:
        file_name = os.path.basename(file_path)
        print(f"\nEvaluating：{file_name}")

        # 加载计划
        ai_plans = data_loader.load_ai_plans(file_path)

        # 生成对应的 Excel 路径
        base_name = os.path.splitext(file_name)[0]
        excel_name = f"{base_name}.xlsx"
        excel_output_path = os.path.join(base_path, 'environment', 'data', 'results', excel_name)

        # 评估
        evaluator = TravelPlanEvaluator(excel_output_path=excel_output_path)
        batch_results = evaluator.evaluate_batch(user_queries, ai_plans)

        print("✅ Evaluation complete!")
        print(batch_results["summary_stats"])

    print("\n🎉 All evaluations are finished! Excel saved in /results folder!\n")


def calculate_means_simple(input_file, output_file):
    """
    输出：所有均值 + 样本统计
    """
    # 读取Excel
    df = pd.read_excel(input_file)
    results = {}

    # --------------------- 筛选规则 ---------------------
    def is_t0001_t0200_gxx1(query_id):
        if isinstance(query_id, str):
            if re.match(r'T0[0-1][0-9][0-9]|T0200', query_id) and 1 <= int(query_id[1:5]) <= 200:
                return True
            if re.match(r'G\d+-1', query_id):
                return True
        return False

    def is_t0201_t0600_gxx2(query_id):
        if isinstance(query_id, str):
            if re.match(r'T0[2-5][0-9][0-9]|T0600', query_id) and 201 <= int(query_id[1:5]) <= 600:
                return True
            if re.match(r'G\d+-2', query_id):
                return True
        return False

    def is_t0601_t1000_gxx3(query_id):
        if isinstance(query_id, str):
            if re.match(r'T0[6-9][0-9][0-9]|T1000', query_id) and 601 <= int(query_id[1:5]) <= 1000:
                return True
            if re.match(r'G\d+-3', query_id):
                return True
        return False

    def is_gxx1(query_id):
        return isinstance(query_id, str) and bool(re.match(r'G\d+-1', query_id))

    def is_gxx2(query_id):
        return isinstance(query_id, str) and bool(re.match(r'G\d+-2', query_id))

    def is_gxx3(query_id):
        return isinstance(query_id, str) and bool(re.match(r'G\d+-3', query_id))

    # --------------------- 计算全部数据 ---------------------
    results['所有数据'] = df.mean(numeric_only=True)

    mask1 = df['query_id'].apply(is_t0001_t0200_gxx1)
    mask2 = df['query_id'].apply(is_t0201_t0600_gxx2)
    mask3 = df['query_id'].apply(is_t0601_t1000_gxx3)
    mask4 = df['query_id'].apply(is_gxx1)
    mask5 = df['query_id'].apply(is_gxx2)
    mask6 = df['query_id'].apply(is_gxx3)

    results['T0001-T0200_Gxx-1'] = df[mask1].mean(numeric_only=True)
    results['T0201-T0600_Gxx-2'] = df[mask2].mean(numeric_only=True)
    results['T0601-T1000_Gxx-3'] = df[mask3].mean(numeric_only=True)
    results['Gxx-1'] = df[mask4].mean(numeric_only=True)
    results['Gxx-2'] = df[mask5].mean(numeric_only=True)
    results['Gxx-3'] = df[mask6].mean(numeric_only=True)

    result_df = pd.DataFrame(results)

    # --------------------- 保存到 Excel ---------------------
    with pd.ExcelWriter(output_file) as writer:
        result_df.to_excel(writer, sheet_name='全数据均值结果', index=True)

        # 样本数量
        summary_data = {
            '范围': [
                '所有数据', 'T0001-T0200_Gxx-1', 'T0201-T0600_Gxx-2',
                'T0601-T1000_Gxx-3', 'Gxx-1', 'Gxx-2', 'Gxx-3'
            ],
            '样本数量': [
                len(df), len(df[mask1]), len(df[mask2]), len(df[mask3]),
                len(df[mask4]), len(df[mask5]), len(df[mask6])
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='样本数量统计', index=False)

    print(f"✅ 分析完成！已保存：{output_file}")
    return result_df


def auto_run_final_analysis():
    print("\n===========================================")
    print("Start final analysis of evaluation results...")
    print("=============================================")

    root_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(root_dir, "environment", "data", "results")

    analysis_dir = os.path.join(results_dir, "analysis")
    # 自动创建文件夹（不存在就创建）
    os.makedirs(analysis_dir, exist_ok=True)

    # 获取所有刚刚生成的 xlsx
    excel_files = glob.glob(os.path.join(results_dir, "*.xlsx"))

    for file_path in excel_files:
        file_name = os.path.basename(file_path)

        # # 跳过已经分析过的
        # if "_analysis_results" in file_name:
        #     continue

        print(f"\nAnalyzing：{file_name}")

        base_name = os.path.splitext(file_name)[0]
        output_file = os.path.join(analysis_dir, f"{base_name}_analysis_results.xlsx")

        # 执行分析
        calculate_means_simple(file_path, output_file)

    print("\n🎉 All analysis completed! Excel generated in /results/analysis folder!")


# ==============================
# 运行入口
# ==============================
if __name__ == "__main__":
    # 0. 生成配置文件
    generate_config_if_missing()
    model_router = ModelRouter()
    strategies = choose_strategies()
    models = choose_models(model_router)

    print("\nRunning...")
    print(f"Models: {models}")
    print(f"Strategies: {len(strategies)} of them")

    # 1. 生成计划
    for f in ['test.json']:
        original_main(f, models, strategies)

    # 2. 清洗 POI
    auto_run_poi_clean()

    # 3. 自动评估
    auto_run_evaluation()

    # 4. 分析数据
    auto_run_final_analysis()

    print("\n🎉 Full Process Completed!")

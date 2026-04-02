
<h1 align="center">TravelEval: A Benchmarking Framework for Evaluating<br>LLM-Powered Travel Planning Agents</h1>

![Task](https://img.shields.io/badge/Task-Travel_Planning-blue)
![Eval](https://img.shields.io/badge/Eval-Multi--Dimensional-blue)
![Agents](https://img.shields.io/badge/Agents-LLM_Strategies-blue)
![Models](https://img.shields.io/badge/Models-Multi--Backend-green)

Official codebase for the TravelEval benchmark.

---

## ✨ Highlights

- **All-in-One Pipeline**: One command → itinerary generation → POI standardization → evaluation → analysis.
- **Multiple Prompt Strategies**: Direct, Zero-shot CoT, ReAct/Reflexion.
- **Multi-Model Support**: DeepSeek, GPT, Qwen, Gemini, Claude, etc.
- **Comprehensive Evaluation**: six-dimensional automated scoring over realistic travel constraints.
- **Auto Analysis**: Automatic result aggregation & Excel output.

---

## Project Structure

```text
agent/
  main.py                  # Generated engine
  config/
  models/ 
  strategies/
  schemas/

config/                    # Global configuration (metrics, API keys)     

core/
  evaluator.py             # Evaluation engine
  metrics/                 # Six-dimensional evaluation metrics
  utils/

environment/
  data/
    queries/               # User queries
    plans/                 # LLM_generated plans
    results/
  database/                # Sandbox
  
run.py                     # One-click main entry (generation + cleaning + evaluation + analysis)
```

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Data Preparation

The sandbox database and query files are organized as:

```text
environment/
  database/
    attractions/{city}/attractions.csv
    accommodations/{city}/accommodations.csv
    restaurants/{city}/restaurants_{city}.csv
    poi/{city}/poi.json
    intercity_transport/
      train/from_{A}_to_{B}.json
      airplane.jsonl

  data/
    queries/*.json
```

---

## ⚙️ Configuration

Before running, you only need to **obtain a Gaode Map API Key** (required for geographic calculations).
The system will automatically prompt you to enter the key on the first run, and save it to the configuration file for subsequent use.

---

## ▶️ One-Click Running (Full Pipeline)

Everything in ONE command:
```bash
python run.py
```

This script will automatically:
- Ask for Gaode API key (first run only)
- Generate travel plans using selected LLMs & strategies
- Standardize POI names
- Run six-dimensional evaluation
- Generate analysis reports & Excel summaries

No separate agent/evaluation steps needed!

---

## 📊 Supported Strategies

- Direct Prompting
- Zero-Shot CoT
- ReAct & Reflexion

---

## 📈 Evaluation Metrics

Six dimensions are implemented in TravelEval.

- **Accuracy**: Evaluate the authenticity of information and the reliability of calculations.
- **Compliance**: Evaluate whether the LLM travel planning system can meet the specific demands and references of users.
- **Temporality**: Evaluate the efficiency and rationality of time utilization in travel planning.
- **Spatiality**: Evaluate the rationality of attraction distribution and travel route in the itinerary.
- **Economy**: Evaluate cost structure and budget efficiency of the travel plan.
- **Utility**: Evaluate the tourist experience value of the travel plan.

---

## 🧾 Output Format

All outputs are automatically saved:

- Raw plans: 
```text 
environment/data/plans/raw/
```
- Standardized plans: 
```text
environment/data/plans/
```
- Evaluation scores: 
```text
environment/data/results/
```
- Analysis reports: 
```text
environment/data/results/analysis/
```


---

## ✉️ Contact

If you have any problems, please contact 
[only-chen@foxmail.com](mailto:only-chen@foxmail.com).



---

## 📌 Citation

If you find this work useful in your research, please cite our paper (currently under review).

The full citation will be updated once the paper is accepted and published.

---

## 📄 License

TODO: Add license information.

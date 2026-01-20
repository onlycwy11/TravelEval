
<h1 align="center">TravelEval: A Benchmarking Framework for Evaluating<br>LLM-Powered Travel Planning Agents</h1>

![Task](https://img.shields.io/badge/Task-Travel_Planning-blue)
![Eval](https://img.shields.io/badge/Eval-Multi--Dimensional-blue)
![Agents](https://img.shields.io/badge/Agents-LLM_Strategies-blue)
![Models](https://img.shields.io/badge/Models-Multi--Backend-green)

Official codebase for the TravelEval benchmark.

---

## ✨ Highlights

- **Agent side**: LLM-based itinerary generation with multiple prompting strategies.
- **Evaluator side**: Multi-dimensional scoring over realistic travel constraints.
- **Sandbox data**: POIs, restaurants, accommodations, and intercity transport.


---

## Project Structure

```text
agent/
  main.py                  # 添加简要描述
  config/                  # TODO
  models/                  # TODO
  strategies/              # TODO
  schemas/                 # TODO
  token_usage/             # TODO

core/
  evaluator.py             # TODO
  metrics/                 # TODO
  utils/                   # TODO

environment/
  data/
    queries/               # TODO
    plans/                 # TODO
```

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Data Preparation

Sandbox database and query files are expected under the following structure:

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
    plans/*.json
```

TODO: 数据集下载链接

---

## Configuration

- agent/config/model_config.json: TODO
- agent/config/path_config.json: TODO
- config/metrics_config.yaml (optional): TODO

---

## ▶️ Running (Agent)

TODO

---

## 📊 Evaluation (Evaluator)

```python
相关代码
```

TODO: 补充evaluation实现细节；输出格式/样例

---

## 📈 Metrics Overview

Six dimensions are implemented in TravelEval. 各维度简述

- **Accuracy**: TODO
- **Constraint**: TODO
- **Time**: TODO
- **Space**: TODO
- **Economy**: TODO
- **Utility**: TODO

---

## 🧾 Schema & Output Format

Schema definition lives in agent/schemas/travel_plan.py.

TODO: Provide output example and strict JSON requirements.


---

## ✉️ Contact

If you have any problems, please contact 
[123](mailto:123),



---

## 📌 Citation

TODO: Add citation.

---

## 📄 License

TODO: Add license information.

#!/usr/bin/env python
"""
RAGAS evaluation: Week 1 vs Week 2 answers on the 5-question eval set.

Usage (from project root):
    python eval/run_ragas.py

Requires DEEPSEEK_API_KEY in .env and a built index under storage/.
Outputs:
    eval/week3_ragas/week1_ragas.json
    eval/week3_ragas/week2_ragas.json
    eval/week3_ragas/comparison.md
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

EVAL_DIR = PROJECT_ROOT / "eval"
OUTPUT_DIR = EVAL_DIR / "week3_ragas"

METRIC_NAMES = ("faithfulness", "answer_relevancy", "context_precision")

# 加载JSON文件
def _load_json(name: str) -> list[dict]:
    return json.loads((EVAL_DIR / name).read_text(encoding="utf-8"))

# 去除引用附录
def _strip_citation_appendix(answer: str) -> str:
    if "---" in answer and "引用来源" in answer:
        return answer.split("---")[0].strip()
    return answer.strip()

# 加载索引
def _load_index():
    from llama_index.core import Settings, StorageContext, load_index_from_storage

    from app.config import PERSIST_DIR
    from app.retrieval.embedder import get_embed_model
    from app.state import app_state

    Settings.llm = None

    embed_name = (PERSIST_DIR / "embed_model.txt").read_text(encoding="utf-8").strip()
    app_state.selected_embed_model_name = embed_name

    metadata_path = PERSIST_DIR / "document_metadata.json"
    if metadata_path.exists():
        app_state.document_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    embed_model = get_embed_model(embed_name)
    storage_context = StorageContext.from_defaults(persist_dir=str(PERSIST_DIR))
    vector_index = load_index_from_storage(storage_context=storage_context, embed_model=embed_model)
    return vector_index, embed_model, embed_name

# 检索上下文
def _retrieve_contexts(question: str, vector_index, embed_model, embed_name: str) -> list[str]:
    from app.retrieval.pipeline import retrieve_context

    _, nodes = retrieve_context(question, vector_index, embed_model, embed_name)
    return [node.get_content() for node in nodes]

# 构建样本
def _build_samples(
    questions: list[dict],
    results_by_id: dict[str, dict],
    contexts_by_id: dict[str, list[str]],
) -> list[dict]:
    samples = []
    for item in questions:
        qid = item["id"]
        result = results_by_id.get(qid)
        if result is None:
            print(f"[警告] 缺少 {qid} 的结果，跳过")
            continue
        contexts = contexts_by_id.get(qid, [])
        if not contexts:
            print(f"[警告] {qid} 未检索到 context，跳过")
            continue
        samples.append(
            {
                "id": qid,
                "question": item["question"],
                "answer": _strip_citation_appendix(result["actual_answer"]),
                "contexts": contexts,
                "ground_truth": item["expected_answer"],
            }
        )
    return samples

# 创建RAGAS LLM
def _create_ragas_llm():
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置，RAGAS 需要 LLM 评判")

    llm = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
        temperature=0,
        max_tokens=1024,
    )
    return LangchainLLMWrapper(llm)

# 创建RAGAS embeddings
def _create_ragas_embeddings():
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    from app.config import MODELS_DIR
    from app.retrieval.model_loader import resolve_local_model_path

    model_path = resolve_local_model_path("BAAI/bge-small-en-v1.5")
    hf = HuggingFaceEmbeddings(
        model_name=model_path,
        cache_folder=str(MODELS_DIR),
        model_kwargs={"device": "cpu"},
    )
    return LangchainEmbeddingsWrapper(hf)

# 运行RAGAS评估
def _run_ragas_eval(samples: list[dict], label: str) -> dict:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    print(f"\n[RAGAS] 评估 {label}（{len(samples)} 题）...")

    dataset = Dataset.from_dict(
        {
            "question": [s["question"] for s in samples],
            "answer": [s["answer"] for s in samples],
            "contexts": [s["contexts"] for s in samples],
            "ground_truth": [s["ground_truth"] for s in samples],
        }
    )

    llm = _create_ragas_llm()
    embeddings = _create_ragas_embeddings()

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=llm,
        embeddings=embeddings,
        column_map={
            "user_input": "question",
            "response": "answer",
            "retrieved_contexts": "contexts",
            "reference": "ground_truth",
        },
        raise_exceptions=False,
    )

    df = result.to_pandas()
    per_question = []
    for index, sample in enumerate(samples):
        row = df.iloc[index]
        per_question.append(
            {
                "id": sample["id"],
                "question": sample["question"],
                "faithfulness": _safe_float(row.get("faithfulness")),
                "answer_relevancy": _safe_float(row.get("answer_relevancy")),
                "context_precision": _safe_float(row.get("context_precision")),
            }
        )

    summary = {
        metric: round(
            sum(q[metric] for q in per_question if q[metric] is not None)
            / max(1, sum(1 for q in per_question if q[metric] is not None)),
            4,
        )
        for metric in METRIC_NAMES
    }

    return {
        "label": label,
        "evaluated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sample_count": len(samples),
        "summary": summary,
        "per_question": per_question,
    }

# 安全转换为浮点数
def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        import math

        f = float(value)
        return None if math.isnan(f) else round(f, 4)
    except (TypeError, ValueError):
        return None

# 加载人工通过结果
def _load_manual_pass(results: list[dict]) -> dict[str, str]:
    out = {}
    for row in results:
        if row.get("pass"):
            out[row["id"]] = "通过"
        elif row.get("partial_pass"):
            out[row["id"]] = "部分通过"
        else:
            out[row["id"]] = "未通过"
    return out

# 格式化对比MD
def _format_comparison_md(
    week1_ragas: dict,
    week2_ragas: dict,
    week1_manual: dict[str, str],
    week2_manual: dict[str, str],
) -> str:
    lines = [
        "# Week 1 vs Week 2 RAGAS 对比",
        "",
        f"评估时间：{week2_ragas.get('evaluated_at', 'N/A')}",
        "",
        "## 总体指标（5 题平均）",
        "",
        "| 指标 | Week 1 | Week 2 | 变化 |",
        "|------|--------|--------|------|",
    ]

    for metric in METRIC_NAMES:
        w1 = week1_ragas["summary"].get(metric)
        w2 = week2_ragas["summary"].get(metric)
        if w1 is not None and w2 is not None:
            delta = w2 - w1
            sign = "+" if delta >= 0 else ""
            lines.append(f"| {metric} | {w1:.4f} | {w2:.4f} | {sign}{delta:.4f} |")
        else:
            lines.append(f"| {metric} | {w1} | {w2} | — |")

    lines.extend(
        [
            "",
            "## 逐题 RAGAS + 人工判分",
            "",
            "| ID | 问题 | W1 Faith | W2 Faith | W1 CtxPrec | W2 CtxPrec | W1 Rel | W2 Rel | 人工 W1 | 人工 W2 |",
            "|----|------|----------|----------|------------|------------|--------|--------|---------|---------|",
        ]
    )

    w1_by_id = {q["id"]: q for q in week1_ragas["per_question"]}
    w2_by_id = {q["id"]: q for q in week2_ragas["per_question"]}

    for qid in sorted(w1_by_id.keys()):
        q1 = w1_by_id[qid]
        q2 = w2_by_id.get(qid, {})
        short_q = q1["question"][:18] + "…" if len(q1["question"]) > 18 else q1["question"]
        lines.append(
            f"| {qid} | {short_q} | "
            f"{_fmt(q1.get('faithfulness'))} | {_fmt(q2.get('faithfulness'))} | "
            f"{_fmt(q1.get('context_precision'))} | {_fmt(q2.get('context_precision'))} | "
            f"{_fmt(q1.get('answer_relevancy'))} | {_fmt(q2.get('answer_relevancy'))} | "
            f"{week1_manual.get(qid, '—')} | {week2_manual.get(qid, '—')} |"
        )

    lines.extend(
        [
            "",
            "## 指标说明",
            "",
            "- **faithfulness**：回答是否被检索 context 支持（越高越少幻觉）",
            "- **context_precision**：检索片段与参考答案的相关度",
            "- **answer_relevancy**：回答与问题的相关度",
            "",
            "> Context 为评估时重新检索（同一索引与配置），Week 1/2 共用；差异来自 `actual_answer`。",
        ]
    )
    return "\n".join(lines) + "\n"

# 格式化值
def _fmt(value) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"

# 主函数
def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("错误: 请先在 .env 中设置 DEEPSEEK_API_KEY")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    questions = _load_json("questions.json")
    week1_results = _load_json("week1_results.json")
    week2_results = _load_json("week2_results.json")

    results_w1 = {r["id"]: r for r in week1_results}
    results_w2 = {r["id"]: r for r in week2_results}

    print("[RAGAS] 加载索引...")
    vector_index, embed_model, embed_name = _load_index()

    contexts_by_id: dict[str, list[str]] = {}
    for item in questions:
        qid = item["id"]
        print(f"[RAGAS] 检索 context: {qid} {item['question'][:30]}...")
        contexts_by_id[qid] = _retrieve_contexts(item["question"], vector_index, embed_model, embed_name)
        print(f"  -> {len(contexts_by_id[qid])} chunks")

    samples_w1 = _build_samples(questions, results_w1, contexts_by_id)
    samples_w2 = _build_samples(questions, results_w2, contexts_by_id)

    week1_ragas = _run_ragas_eval(samples_w1, "week1-hybrid-rerank-semantic-chunk")
    week2_ragas = _run_ragas_eval(samples_w2, "week2-router-citations-refusal")

    (OUTPUT_DIR / "week1_ragas.json").write_text(
        json.dumps(week1_ragas, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "week2_ragas.json").write_text(
        json.dumps(week2_ragas, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    comparison_md = _format_comparison_md(
        week1_ragas,
        week2_ragas,
        _load_manual_pass(week1_results),
        _load_manual_pass(week2_results),
    )
    (OUTPUT_DIR / "comparison.md").write_text(comparison_md, encoding="utf-8")

    print("\n[RAGAS] 完成")
    print(f"  Week1 summary: {week1_ragas['summary']}")
    print(f"  Week2 summary: {week2_ragas['summary']}")
    print(f"  对比报告: {OUTPUT_DIR / 'comparison.md'}")


if __name__ == "__main__":
    main()

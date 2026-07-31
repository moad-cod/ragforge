import os
import json
import time
import requests
from datasets import Dataset
from dotenv import load_dotenv
from ragas import evaluate
from ragas.metrics import (
    faithfulness, answer_relevancy,
    context_precision, context_recall,
)
from ragas.run_config import RunConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

load_dotenv()

# ── Gemini 1.5 Flash — free, fast, real LLM judge ──
gemini_llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
))

local_embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
))

QUERY_URL = "http://localhost:8000/rag/query"
TEST_SET_PATH = "tests/fixtures/test_set.json"
VERSIONS = ["v1", "v2", "v3"]

RUN_CONFIG = RunConfig(
    max_workers=1,
    timeout=60,
    max_retries=3,
)


# ── Retrieval metrics ──
def chunk_is_relevant(chunk: str, relevant_chunk: str) -> bool:
    chunk_lower = chunk.lower().strip()
    relevant_lower = relevant_chunk.lower().strip()
    if relevant_lower in chunk_lower:
        return True
    if chunk_lower in relevant_lower:
        return True
    words = [w for w in relevant_lower.split() if len(w) > 3]
    if not words:
        return False
    hits = sum(1 for w in words if w in chunk_lower)
    return hits / len(words) >= 0.7

def recall_at_k(retrieved, relevant_chunk, k):
    return 1.0 if any(chunk_is_relevant(c, relevant_chunk) for c in retrieved[:k]) else 0.0

def mrr(retrieved, relevant_chunk):
    for i, chunk in enumerate(retrieved):
        if chunk_is_relevant(chunk, relevant_chunk):
            return 1.0 / (i + 1)
    return 0.0

def precision_at_k(retrieved, relevant_chunk, k):
    hits = sum(1 for c in retrieved[:k] if chunk_is_relevant(c, relevant_chunk))
    return hits / k


# ── Call RAG API ──
def run_pipeline(question: str, version: str) -> dict:
    response = requests.post(
        QUERY_URL,
        params={"version": version},
        json={"question": question},
    )
    data = response.json()
    return {
        "answer": data["answer"],
        "contexts": data["retrieved_chunks"],
    }


# ── Evaluate one version ──
def evaluate_version(test_set: list, version: str) -> dict:
    print(f"\n{'='*40}")
    print(f" Evaluating {version}")
    print(f"{'='*40}")

    questions, answers, contexts, ground_truths = [], [], [], []
    mrr_scores, recall_5, recall_20, precision_5 = [], [], [], []

    for item in test_set:
        print(f"  → {item['question']}")
        result = run_pipeline(item["question"], version)
        retrieved = result["contexts"]
        relevant  = item["relevant_chunk"]

        mrr_scores.append(mrr(retrieved, relevant))
        recall_5.append(recall_at_k(retrieved, relevant, k=5))
        recall_20.append(recall_at_k(retrieved, relevant, k=20))
        precision_5.append(precision_at_k(retrieved, relevant, k=5))

        questions.append(item["question"])
        answers.append(result["answer"])
        contexts.append(retrieved)
        ground_truths.append(item["ground_truth"])

        time.sleep(0.3)

    # ── RAGAS with Gemini as judge ──
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    print(f"\n  Running RAGAS with Gemini for {version}...")
    ragas_results = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=gemini_llm,
        embeddings=local_embeddings,
        run_config=RUN_CONFIG,
    )

    def avg(lst): return round(sum(lst) / len(lst), 3)

    return {
        "version": version,
        "retrieval_metrics": {
            "MRR":         avg(mrr_scores),
            "Recall@5":    avg(recall_5),
            "Recall@20":   avg(recall_20),
            "Precision@5": avg(precision_5),
        },
        "generation_metrics": ragas_results.to_pandas().mean(numeric_only=True).to_dict(),
    }


# ── Main ──
def main():
    with open(TEST_SET_PATH) as f:
        test_set = json.load(f)

    os.makedirs("artifacts/test-results", exist_ok=True)
    all_results = []
    for version in VERSIONS:
        result = evaluate_version(test_set, version)
        all_results.append(result)

        with open(f"artifacts/test-results/results_{version}.json", "w") as f:
            json.dump(result, f, indent=2)
        print(f"  ✓ Saved artifacts/test-results/results_{version}.json")

    # ── Comparison table ──
    print("\n\n===== FINAL COMPARISON =====\n")
    print(f"{'Metric':<22} {'v1 (paragraph)':>15} {'v2 (proposition)':>17} {'v3 (sentence)':>14}")
    print("-" * 70)

    print("\n-- Retrieval --")
    for m in ["MRR", "Recall@5", "Recall@20", "Precision@5"]:
        scores = [r["retrieval_metrics"][m] for r in all_results]
        best = max(scores)
        row = f"{m:<22}"
        for s in scores:
            row += f" {s:>14}" + (" ◄" if s == best else "  ")
        print(row)

    print("\n-- Generation (Gemini LLM judge) --")
    for m in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        scores = [r["generation_metrics"].get(m, 0) for r in all_results]
        best = max(scores)
        row = f"{m:<22}"
        for s in scores:
            row += f" {s:>14.3f}" + (" ◄" if s == best else "  ")
        print(row)

    print("\n◄ = best score for that metric")


if __name__ == "__main__":
    main()

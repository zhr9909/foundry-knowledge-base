#!/usr/bin/env python3
"""eval_retrieval.py - RAG Retrieval Evaluation Pipeline"""

import json, os, sys, time, re
import eval_db
import eval_db
from pathlib import Path

CONFIG = {
    "host": "127.0.0.1", "port": 15432,
    "dbname": "foundry_kb", "user": "findmyjob",
    "password": "findmyjob_dev_password",
}

def hit_rate(results_by_query, k=5):
    hits = 0
    for qid, data in results_by_query.items():
        expected = set(data["expected_ids"])
        retrieved = [r["chunk_id"] for r in data["results"][:k]]
        if expected & set(retrieved):
            hits += 1
    return hits / len(results_by_query) if results_by_query else 0

def mrr(results_by_query, k=10):
    total = 0.0
    for qid, data in results_by_query.items():
        expected = set(data["expected_ids"])
        for rank, r in enumerate(data["results"][:k], 1):
            if r["chunk_id"] in expected:
                total += 1.0 / rank
                break
    return total / len(results_by_query) if results_by_query else 0

def precision_at_k(results_by_query, k=5):
    total = 0.0
    for qid, data in results_by_query.items():
        expected = set(data["expected_ids"])
        retrieved = [r["chunk_id"] for r in data["results"][:k]]
        relevant = len(expected & set(retrieved))
        total += relevant / k
    return total / len(results_by_query) if results_by_query else 0

def generate_test_queries(source_id=None, n=50, min_text_length=80):
    import psycopg2
    conn = psycopg2.connect(**CONFIG)
    cur = conn.cursor()
    where = "WHERE source_id = %s" if source_id else "WHERE 1=1"
    params = [source_id] if source_id else []
    cur.execute(f"""
        SELECT chunk_id, page, content_text, source_id
        FROM chunks
        {where}
        AND chunk_type = 'page_text'
        AND LENGTH(content_text) > %s
        ORDER BY RANDOM()
        LIMIT %s
    """, params + [min_text_length, n * 3])
    candidates = cur.fetchall()
    conn.close()
    queries = []
    for row in candidates:
        chunk_id, page, text, sid = row
        alloys = re.findall(r'\b\d{4,5}[-A-Za-z0-9]*\b', text)
        properties = re.findall(r'\b(strength|tensile|fatigue|hardness|corrosion|thermal|conductivity)\b', text, re.I)
        if alloys:
            prop_str = " ".join(properties[:2]) if properties else ""
            query = f"{alloys[0]} {prop_str}".strip()
        else:
            lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 15]
            query = lines[0][:80] if lines else text[:80]
        if len(query) > 10:
            queries.append({"query": query, "expected_chunk_ids": [chunk_id], "page": page, "source_id": sid})
        if len(queries) >= n:
            break
    return queries

def evaluate(queries, top_k=10, hybrid=True):
    from search import search
    results_by_query = {}
    print(f"\nEvaluating {len(queries)} queries...")
    for i, q in enumerate(queries):
        start = time.time()
        result = search(q["query"], top_k=top_k, hybrid=hybrid)
        elapsed = (time.time() - start) * 1000
        results_by_query[f"q{i+1}"] = {
            "query": q["query"], "expected_ids": q["expected_chunk_ids"],
            "results": result.get("results", []), "latency_ms": elapsed,
        }
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(queries)}]")
    metrics = {
        "hit_rate_5": hit_rate(results_by_query, 5),
        "hit_rate_10": hit_rate(results_by_query, 10),
        "mrr": mrr(results_by_query, 10),
        "precision_5": precision_at_k(results_by_query, 5),
        "avg_latency_ms": sum(d["latency_ms"] for d in results_by_query.values()) / len(results_by_query),
        "total_queries": len(queries),
    }
    return metrics, results_by_query

def print_report(metrics):
    print("\n" + "=" * 50)
    print("RETRIEVAL EVALUATION REPORT")
    print("=" * 50)
    print(f"  Total queries:     {metrics['total_queries']}")
    print(f"  Hit Rate@5:        {metrics['hit_rate_5']:.3f}")
    print(f"  Hit Rate@10:       {metrics['hit_rate_10']:.3f}")
    print(f"  MRR:               {metrics['mrr']:.3f}")
    print(f"  Precision@5:       {metrics['precision_5']:.3f}")
    print(f"  Avg Latency:       {metrics['avg_latency_ms']:.0f} ms")
    print("=" * 50)

def save_results(metrics, results_by_query, queries):
    import datetime
    out_dir = Path(__file__).resolve().parent.parent / "eval_results"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {"timestamp": ts, "config": {"top_k": 10, "hybrid": True}, "metrics": metrics}
    with open(out_dir / f"report_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    detail = {"timestamp": ts, "config": {"top_k": 10, "hybrid": True}, "metrics": metrics, "queries": []}
    for i, q in enumerate(queries):
        r = results_by_query.get(f"q{i+1}", {})
        detail["queries"].append({
            "query": q["query"], "expected": q["expected_chunk_ids"],
            "top_results": [{"chunk_id": r2["chunk_id"], "page": r2.get("page"), "score": r2.get("score")}
                           for r2 in r.get("results", [])[:5]],
            "latency_ms": r.get("latency_ms", 0),
        })
    with open(out_dir / f"detail_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(detail, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_dir}")
    print(f"  report_{ts}.json / detail_{ts}.json")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAG Retrieval Evaluation")
    parser.add_argument("--n-queries", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--source-id", type=int)
    parser.add_argument("--queries", help="JSON file with manual queries")
    args = parser.parse_args()
    print("=== RAG Retrieval Evaluation ===")
    if args.queries:
        with open(args.queries, "r", encoding="utf-8") as f:
            queries = json.load(f)
        print(f"Loaded {len(queries)} queries from {args.queries}")
    else:
        print(f"Generating {args.n_queries} test queries from chunks...")
        queries = generate_test_queries(source_id=args.source_id, n=args.n_queries)
        print(f"Generated {len(queries)} queries")
    metrics, results_by_query = evaluate(queries, top_k=args.top_k)
    print_report(metrics)
    save_results(metrics, results_by_query, queries)
    try:
        dsn = os.path.basename(args.queries).replace(".json", "") if args.queries else "auto"
        rid = eval_db.save_run(dsn, {"top_k": args.top_k, "hybrid": True}, metrics, metrics["total_queries"], metrics["avg_latency_ms"])
        rlist = []
        for i, q in enumerate(queries):
            r = results_by_query.get("q" + str(i+1), {})
            rf = 0
            for ri, rr in enumerate(r.get("results", [])[:10], 1):
                if rr["chunk_id"] in set(q.get("expected_chunk_ids", [])):
                    rf = ri
                    break
            rlist.append({"query": q["query"], "expected_ids": q.get("expected_chunk_ids", []), "rank_found": rf, "top_score": r["results"][0].get("score", 0) if r.get("results") else 0, "latency_ms": r.get("latency_ms", 0), "hit": rf > 0})
        eval_db.save_results(rid, rlist)
        print("   DB: run #%d saved" % rid)
    except Exception as ex:
        print("   DB save: %s" % ex)
    print("\nDone!")

if __name__ == "__main__":
    main()

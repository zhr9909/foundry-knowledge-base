#!/usr/bin/env python3
"""eval_full_pipeline.py - Eval through full pipeline (rewrite → search → rerank)"""

import json, sys, os, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import eval_db

CONFIG = {
    "host": "127.0.0.1", "port": 15432,
    "dbname": "foundry_kb", "user": "findmyjob",
    "password": "findmyjob_dev_password",
}

def hit_rate(results_by_query, k=5):
    hits = 0
    for qid, data in results_by_query.items():
        expected = set(data["expected_ids"])
        retrieved = [r["chunk_id"] for r in data["context"][:k]]
        if expected & set(retrieved):
            hits += 1
    return hits / len(results_by_query) if results_by_query else 0

def mrr(results_by_query, k=10):
    total = 0.0
    for qid, data in results_by_query.items():
        expected = set(data["expected_ids"])
        for rank, r in enumerate(data["context"][:k], 1):
            if r["chunk_id"] in expected:
                total += 1.0 / rank
                break
    return total / len(results_by_query) if results_by_query else 0

def precision_at_k(results_by_query, k=5):
    total = 0.0
    for qid, data in results_by_query.items():
        expected = set(data["expected_ids"])
        retrieved = [r["chunk_id"] for r in data["context"][:k]]
        relevant = len(expected & set(retrieved))
        total += relevant / k
    return total / len(results_by_query) if results_by_query else 0

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=30)
    args = parser.parse_args()

    print("=== Full Pipeline Eval (rewrite → search_parallel → select_context) ===")
    print(f"Queries: {args.queries}, top_k={args.top_k}, candidate_pool={args.candidate_k}")

    # Import from agent.py
    print("\nLoading agent modules...")
    from agent import rewrite_query, search_parallel, select_context

    # Load test set
    with open(args.queries, "r", encoding="utf-8") as f:
        test_queries = json.load(f)
    print(f"Loaded {len(test_queries)} test queries")

    results_by_query = {}
    total_start = time.time()

    for i, q in enumerate(test_queries):
        query = q.get("query", "")
        expected_ids = q.get("expected_chunk_ids", [])
        q_start = time.time()

        # Step 1: Rewrite query (Chinese → English sub-queries)
        try:
            rw = rewrite_query(query, history=None)
            sub_queries = rw.get("search_queries", [query])
        except Exception as e:
            print(f"  Rewrite failed: {e}")
            sub_queries = [query]

        # Step 2: Parallel search
        try:
            candidates = search_parallel(sub_queries, section=None, top_k=args.candidate_k)
        except Exception as e:
            print(f"  Search failed: {e}")
            candidates = []

        # Step 3: Select context (includes boost_keywords + reranker)
        try:
            original_query = " ".join(sub_queries)
            ctx = select_context(candidates, top_k=args.top_k,
                                 original_query=original_query,
                                 search_query=sub_queries[0] if sub_queries else query)
        except Exception as e:
            print(f"  Select_context failed: {e}")
            ctx = []

        elapsed = int((time.time() - q_start) * 1000)
        results_by_query[f"q{i+1}"] = {
            "query": query,
            "expected_ids": expected_ids,
            "context": ctx,
            "sub_queries": sub_queries,
            "latency_ms": elapsed,
        }

        if (i + 1) % 10 == 0:
            elapsed_total = int(time.time() - total_start)
            rate = (i + 1) / elapsed_total * 1000 if elapsed_total > 0 else 0
            print(f"  [{i+1}/{len(test_queries)}] ({rate:.1f} q/s)")

    # Compute metrics
    metrics = {
        "hit_rate_5": hit_rate(results_by_query, 5),
        "hit_rate_10": hit_rate(results_by_query, 10),
        "mrr": mrr(results_by_query, 10),
        "precision_5": precision_at_k(results_by_query, 5),
        "avg_latency_ms": sum(d["latency_ms"] for d in results_by_query.values()) / len(results_by_query),
        "total_queries": len(test_queries),
    }

    # Print report
    print("\n" + "=" * 50)
    print("FULL PIPELINE EVALUATION REPORT")
    print("=" * 50)
    print(f"  Total queries:     {metrics['total_queries']}")
    print(f"  Hit Rate@5:        {metrics['hit_rate_5']:.3f}")
    print(f"  Hit Rate@10:       {metrics['hit_rate_10']:.3f}")
    print(f"  MRR:               {metrics['mrr']:.3f}")
    print(f"  Precision@5:       {metrics['precision_5']:.3f}")
    print(f"  Avg Latency:       {metrics['avg_latency_ms']:.0f} ms")
    print("=" * 50)

    # Save results
    ts = time.strftime("%Y%m%d_%H%M%S")
    report = {"timestamp": ts, "config": {"top_k": args.top_k, "candidate_k": args.candidate_k},
              "metrics": metrics}
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "eval_results", f"full_pipeline_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to: {out_path}")

    # Save to DB
    try:
        dsn = os.path.basename(args.queries).replace(".json", "")
        rid = eval_db.save_run(dsn + "_full_pipeline", {"top_k": args.top_k, "candidate_k": args.candidate_k},
                              metrics, metrics["total_queries"], metrics["avg_latency_ms"])
        rlist = []
        for i, q in enumerate(test_queries):
            r = results_by_query.get(f"q{i+1}", {})
            rf = 0
            for ri, rr in enumerate(r.get("context", [])[:10], 1):
                if rr.get("chunk_id") in set(q.get("expected_chunk_ids", [])):
                    rf = ri
                    break
            rlist.append({"query": q.get("query", ""), "expected_ids": q.get("expected_chunk_ids", []),
                         "rank_found": rf, "top_score": r["context"][0].get("score", 0) if r.get("context") else 0,
                         "latency_ms": r.get("latency_ms", 0), "hit": rf > 0})
        eval_db.save_results(rid, rlist)
        print(f"   DB: run #{rid} saved")
    except Exception as ex:
        print(f"   DB save: {ex}")

    print("\nDone!")

if __name__ == "__main__":
    main()

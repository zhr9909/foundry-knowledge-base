import psycopg2, json, sys

CONFIG = {"host": "127.0.0.1", "port": 15432, "dbname": "foundry_kb", "user": "findmyjob", "password": "findmyjob_dev_password"}

def get_conn():
    return psycopg2.connect(**CONFIG)

def save_queries(dataset_name, queries):
    conn = get_conn()
    cur = conn.cursor()
    count = 0
    for q in queries:
        cur.execute("INSERT INTO eval_queries (dataset_name, query, expected_chunk_ids, page, source_id, all_queries, summary, keywords) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (dataset_name, q.get("query"), q.get("expected_chunk_ids", []), q.get("page"), q.get("source_id"), q.get("all_queries", []), q.get("summary"), q.get("keywords", [])))
        count += 1
    conn.commit()
    conn.close()
    return count

def save_run(dataset_name, config, metrics, query_count, avg_latency_ms):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO eval_runs (dataset_name, config, metrics, query_count, avg_latency_ms) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (dataset_name, json.dumps(config), json.dumps(metrics), query_count, avg_latency_ms))
    run_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return run_id

def save_results(run_id, results_list):
    conn = get_conn()
    cur = conn.cursor()
    for r in results_list:
        cur.execute("INSERT INTO eval_results (run_id, query, expected_chunk_ids, rank_found, top_score, latency_ms, hit) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (run_id, r.get("query"), r.get("expected_ids", []), r.get("rank_found", 0), r.get("top_score", 0), r.get("latency_ms", 0), r.get("hit", False)))
    conn.commit()
    conn.close()

def load_queries(dataset_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, query, expected_chunk_ids, page, source_id FROM eval_queries WHERE dataset_name = %s", (dataset_name,))
    rows = cur.fetchall()
    conn.close()
    return [{"query_id": r[0], "query": r[1], "expected_chunk_ids": r[2], "page": r[3], "source_id": r[4]} for r in rows]

def list_recent_runs(limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, dataset_name, metrics, query_count, avg_latency_ms, created_at FROM eval_runs ORDER BY created_at DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def print_runs_table(runs):
    print(f"\n{'ID':<5} {'Dataset':<20} {'Hit@5':<8} {'MRR':<8} {'P@5':<8} {'Latency':<10} {'Queries':<8} {'Date'}")
    print("-" * 80)
    for r in runs:
        m = r[2] if r[2] else {}
        print(f"{r[0]:<5} {str(r[1]):<20} {m.get('hit_rate_5', 0):<8.3f} {m.get('mrr', 0):<8.3f} {m.get('precision_5', 0):<8.3f} {str(r[4] or 0)+'ms':<10} {r[3]:<8} {str(r[5])[:19]}")

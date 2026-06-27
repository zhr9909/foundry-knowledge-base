#!/usr/bin/env python3
"""generate_eval_dataset.py - Generate high-quality eval queries using LLM"""

import json, sys, time, re
import httpx, psycopg2
import eval_db

CONFIG = {"host": "127.0.0.1", "port": 15432, "dbname": "foundry_kb", "user": "findmyjob", "password": "findmyjob_dev_password"}
LLM_API = "http://127.0.0.1:15721/v1"
LLM_KEY = "PROXY_MANAGED"
LLM_MODEL = "deepseek-v4-flash"

SYS_PROMPT = """\u4f60\u662f\u6750\u6599\u5de5\u7a0b\u9886\u57df\u7684\u641c\u7d22\u67e5\u8be2\u4e13\u5bb6\u3002
\u7ed9\u5b9a\u4e00\u6bb5ASM\u624b\u518c\u7684\u6280\u672f\u6587\u672c\uff0c\u4f60\u9700\u8981\uff1a
1. \u63d0\u53d6\u5173\u952e\u6280\u672f\u5b9e\u4f53\uff08\u5408\u91d1\u724c\u53f7\u3001\u6027\u80fd\u6307\u6807\u3001\u6570\u503c\u3001\u6d4b\u8bd5\u6761\u4ef6\uff09
2. \u751f\u62102-3\u6761\u771f\u5b9e\u7684\u641c\u7d22\u67e5\u8be2\uff0c\u8981\u6c42\uff1a
   - \u4e2d\u82f1\u6587\u7686\u53ef
   - \u50cf\u4e00\u4f4d\u5de5\u7a0b\u5e08\u771f\u7684\u4f1a\u641c\u7684\u95ee\u9898
   - \u5305\u542b\u5408\u91d1\u724c\u53f7\u3001\u6027\u80fd\u540d\u79f0\u7b49\u5173\u952e\u4fe1\u606f
   - \u6bcf\u6761\u67e5\u8be2\u5e94\u8be5\u80fd\u591f\u552f\u4e00\u5730\u53ec\u56de\u8fd9\u6bb5\u6587\u672c

\u4e25\u683c\u6309\u4ee5\u4e0bJSON\u683c\u5f0f\u8f93\u51fa\uff0c\u4e0d\u8981\u6709\u5176\u4ed6\u5185\u5bb9\uff1a
{"summary": "\u4e00\u53e5\u8bdd\u6982\u62ec", "keywords": ["\u5173\u952e1","\u5173\u952e2"], "queries": ["\u67e5\u8be21","\u67e5\u8be22"]}"""

def call_llm(messages, max_tokens=1024, timeout=45):
    for attempt in range(2):
        try:
            resp = httpx.post(LLM_API + "/chat/completions",
                headers={"Authorization": "Bearer " + LLM_KEY, "Content-Type": "application/json"},
                json={"model": LLM_MODEL, "messages": messages, "max_tokens": max_tokens}, timeout=timeout)
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 0:
                time.sleep(1)
                continue
            raise e

def generate_for_chunk(chunk_id, page, text, source_name='Unknown'):
    text_preview = text[:600]
    prompt = SYS_PROMPT.replace("{source_name}", source_name)
    messages = [{"role": "system", "content": prompt},
                {"role": "user", "content": "\u6587\u672c\uff08page " + str(page) + "\uff09:\n" + text_preview}]
    try:
        result = call_llm(messages)
        match = re.search(r'\{[\s\S]*\}', result)
        if match:
            data = json.loads(match.group())
            return data.get("queries", []), data.get("summary", ""), data.get("keywords", [])
    except Exception as e:
        print("  LLM error: " + str(e), file=sys.stderr)
    return [], "", []

def sample_chunks(source_id=None, n=50, min_len=200, max_len=3000):
    conn = psycopg2.connect(**CONFIG)
    cur = conn.cursor()
    where_clause = "WHERE source_id = %s" if source_id else "WHERE 1=1"
    params = [source_id] if source_id else []
    sql = "SELECT c.chunk_id, c.page, c.content_text, c.source_id, COALESCE(ds.title, %s) FROM chunks c LEFT JOIN document_sources ds ON ds.id = c.source_id " + where_clause + " AND chunk_type = 'page_text' AND LENGTH(content_text) > %s AND LENGTH(content_text) < %s ORDER BY RANDOM() LIMIT %s"
    cur.execute(sql, ['Unknown'] + params + [min_len, max_len, n])
    rows = cur.fetchall()
    conn.close()
    return [{"chunk_id": r[0], "page": r[1], "text": r[2], "source_id": r[3], "source_title": r[4]} for r in rows]

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--source-id", type=int)
    parser.add_argument("--dataset-name", default="llm_v1", help="Dataset name for DB storage")
    parser.add_argument("--output", default="eval_results/llm_generated_queries.json")
    args = parser.parse_args()
    print("=== Generate Eval Dataset (" + str(args.n) + " queries) ===")
    print("1. Sampling chunks...")
    chunks = sample_chunks(source_id=args.source_id, n=args.n)
    print("   Sampled " + str(len(chunks)) + " chunks")
    print("2. Generating queries via LLM...")
    dataset = []
    for i, chunk in enumerate(chunks):
        queries, summary, keywords = generate_for_chunk(chunk["chunk_id"], chunk["page"], chunk["text"], chunk.get("source_title", "Unknown"))
        if queries:
            dataset.append({"query": queries[0], "expected_chunk_ids": [chunk["chunk_id"]],
                "page": chunk["page"], "source_id": chunk["source_id"],
                "all_queries": queries, "summary": summary, "keywords": keywords})
        status = str(len(queries)) + " queries"
        if queries: status += " (first: " + queries[0][:50] + "...)"
        else: status += " (SKIPPED)"
        try:
            print("   [" + str(i+1) + "/" + str(len(chunks)) + "] page=" + str(chunk["page"]) + " -> " + status)
        except:
            print("   [" + str(i+1) + "/" + str(len(chunks)) + "] page=" + str(chunk["page"]) + " -> [encoding error]")
        time.sleep(0.1)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    print("\nDone! " + str(len(dataset)) + " queries saved to " + args.output)
    total_variants = sum(len(d.get("all_queries", [])) for d in dataset)
    print("   Total query variants: " + str(total_variants))
    try:
        import eval_db as _edb
        n = _edb.save_queries(args.dataset_name or "unknown", dataset)
        print("   DB: saved " + str(n) + " queries")
    except Exception as ex:
        print("   DB save: " + str(ex))

if __name__ == "__main__":
    main()

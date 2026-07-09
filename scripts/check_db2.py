import psycopg2
conn = psycopg2.connect(host="127.0.0.1", port=15432, dbname="foundry_kb", user="findmyjob", password="findmyjob_dev_password")
cur = conn.cursor()
cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'conversations')")
e1 = cur.fetchone()[0]
cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'conversation_messages')")
e2 = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM conversations")
cnt = cur.fetchone()[0]
conn.close()
print("conversations table:", e1)
print("conversation_messages table:", e2)
print("conversations count:", cnt)

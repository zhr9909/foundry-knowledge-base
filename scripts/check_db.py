import os, psycopg2

try:
    conn = psycopg2.connect(host="127.0.0.1", port=15432, dbname="foundry_kb", user="findmyjob", password="findmyjob_dev_password")
    cur = conn.cursor()
    
    # Check if conversations table exists
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'conversations')")
    exists = cur.fetchone()[0]
    print("conversations table exists:", exists)
    
    # Check if conversation_messages table exists
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'conversation_messages')")
    exists2 = cur.fetchone()[0]
    print("conversation_messages table exists:", exists2)
    
    # Check users table
    cur.execute("SELECT count(*) FROM users")
    users = cur.fetchone()[0]
    print("Users count:", users)
    
    cur.close()
    conn.close()
except Exception as e:
    print("Database error:", e)

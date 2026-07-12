#!/usr/bin/env python3
"""Authentication handler for Foundry KB - JWT + bcrypt + email verification"""
import os, json, secrets, smtplib, ssl, base64, time, re, random, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pathlib import Path

# Load .env file if present (must happen before os.environ.get() calls)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        with open(_env_path, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass


# === Config ===
SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 72
EMAIL_VERIFY_EXPIRE_HOURS = 24

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:8000")

_db_config = {
    "host": "127.0.0.1", "port": 15432,
    "dbname": "foundry_kb", "user": "findmyjob",
    "password": "findmyjob_dev_password"
}

def _get_conn():
    import psycopg2
    return psycopg2.connect(**_db_config)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_session_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + ACCESS_TOKEN_EXPIRE_HOURS * 3600
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        return None

_security = HTTPBearer(auto_error=False)

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security)):
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None:
        return None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, email, username, email_verified, created_at, last_login FROM users WHERE id = %s AND is_active = TRUE", (int(payload["sub"]),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {
                "id": row[0], "email": row[1], "username": row[2],
                "email_verified": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
                "last_login": row[5].isoformat() if row[5] else None
            }
    except:
        pass
    return None

def require_user(user: Optional[dict] = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user

def create_user(email: str, username: str, password: str) -> dict:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        pwd_hash = hash_password(password)
        cur.execute("INSERT INTO users (email, username, password_hash) VALUES (%s, %s, %s) RETURNING id, email, username, created_at",
            (email.lower().strip(), username.strip(), pwd_hash))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "email": row[1], "username": row[2], "created_at": row[3].isoformat() if row[3] else None}
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "该邮箱已被注册")
        raise HTTPException(500, f"注册失败: {str(e)}")
    finally:
        cur.close()
        conn.close()

def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email, username, password_hash, email_verified, created_at FROM users WHERE email = %s AND is_active = TRUE", (email.lower().strip(),))
        row = cur.fetchone()
        if not row:
            return None
        if not verify_password(password, row[3]):
            return None
        cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (row[0],))
        conn.commit()
        return {"id": row[0], "email": row[1], "username": row[2], "email_verified": row[4], "created_at": row[5].isoformat() if row[5] else None}
    finally:
        cur.close()
        conn.close()

def create_verification_code(user_id: int) -> str:
    code = str(random.randint(100000, 999999))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO verification_tokens (user_id, token, type, expires_at) VALUES (%s, %s, 'email_code', %s)",
            (user_id, code, expires_at))
        conn.commit()
        return code
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Code gen failed: {e}")
    finally:
        cur.close()
        conn.close()

def verify_code(email: str, code: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT u.id, vt.id FROM users u JOIN verification_tokens vt ON vt.user_id = u.id WHERE u.email = %s AND vt.token = %s AND vt.type = 'email_code' AND vt.used = FALSE AND vt.expires_at > NOW() ORDER BY vt.created_at DESC LIMIT 1",
            (email.lower().strip(), code))
        row = cur.fetchone()
        if not row:
            return False
        cur.execute("UPDATE verification_tokens SET used = TRUE WHERE id = %s", (row[1],))
        cur.execute("UPDATE users SET email_verified = TRUE WHERE id = %s", (row[0],))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def create_verification_token(user_id: int, token_type: str = "email_verify", expires_hours: int = EMAIL_VERIFY_EXPIRE_HOURS) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO verification_tokens (user_id, token, type, expires_at) VALUES (%s, %s, %s, %s)", (user_id, token, token_type, expires_at))
        conn.commit()
        return token
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"Token creation failed: {str(e)}")
    finally:
        cur.close()
        conn.close()

def verify_email_token(token: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, user_id FROM verification_tokens WHERE token = %s AND type = 'email_verify' AND used = FALSE AND expires_at > NOW()", (token,))
        row = cur.fetchone()
        if not row:
            return False
        cur.execute("UPDATE verification_tokens SET used = TRUE WHERE id = %s", (row[0],))
        cur.execute("UPDATE users SET email_verified = TRUE WHERE id = %s", (row[1],))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

def get_verification_email_html(code: str, username: str) -> str:
    return f"""<!DOCTYPE html><html><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#f5f5f7;padding:20px"><div style="max-width:420px;margin:auto;background:white;border-radius:16px;padding:32px;box-shadow:0 4px 24px rgba(0,0,0,0.08)"><div style="text-align:center"><div style="font-size:32px;margin-bottom:16px">🏭</div><h2 style="color:#1d1d1f;font-size:20px;margin:0 0 8px">欢迎注册铸造知识库</h2><p style="color:#6b6b70;font-size:14px;margin:0 0 24px">你好，{username}，请输入以下验证码完成注册</p><div style="background:#f5f5f7;border-radius:12px;padding:20px;margin:0 0 20px"><div style="font-size:36px;font-weight:700;letter-spacing:12px;color:#1d1d1f;font-family:monospace">{code}</div></div><p style="color:#8e8e93;font-size:12px;margin:0">此验证码15分钟内有效</p></div></div></body></html>"""

def send_verification_email(email: str, token: str, username: str):
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[Auth] SMTP未配置。验证码: {token}")
        return
    html = get_verification_email_html(token, username)
    subject_b64 = base64.b64encode('您的验证码 - 铸造知识库'.encode()).decode()
    msg = f"From: {SMTP_FROM}\r\nTo: {email}\r\nSubject: =?utf-8?B?{subject_b64}?=\r\nMIME-Version: 1.0\r\nContent-Type: text/html; charset=utf-8\r\n\r\n{html}"
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls(context=ctx)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, email, msg.encode())
        print(f"[Auth] 验证码已发送至 {email}")
    except Exception as e:
        print(f"[Auth] 邮件发送失败: {e}")

def send_verification_code(email: str, code: str, username: str):
    send_verification_email(email, code, username)

def init_auth_db():
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL, password_hash TEXT NOT NULL,
            email_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_login TIMESTAMPTZ, is_active BOOLEAN DEFAULT TRUE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS verification_tokens (
            id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id),
            token TEXT NOT NULL, type TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(), used BOOLEAN DEFAULT FALSE)""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_verif_token ON verification_tokens(token)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_verif_user ON verification_tokens(user_id)")
        cur.execute("""CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            title TEXT DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS conversation_messages (
            id SERIAL PRIMARY KEY,
            conversation_id INT REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL DEFAULT '未命名项目',
            customer_name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS project_artifacts (
            id SERIAL PRIMARY KEY,
            project_id INT REFERENCES projects(id) ON DELETE CASCADE,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            artifact_type TEXT NOT NULL DEFAULT 'qa',
            title TEXT NOT NULL DEFAULT '未命名产物',
            content TEXT NOT NULL DEFAULT '',
            structured_data JSONB DEFAULT '{}',
            citations JSONB DEFAULT '[]',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS project_id INT")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_project ON conversations(project_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON conversation_messages(conversation_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_project_user ON projects(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_artifact_project ON project_artifacts(project_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_artifact_user ON project_artifacts(user_id)")
        cur.execute("""CREATE TABLE IF NOT EXISTS knowledge_sources (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'standard_manual',
            owner_user_id INT,
            organization_id INT,
            visibility TEXT NOT NULL DEFAULT 'public',
            description TEXT DEFAULT '',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS evidence_cards (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            project_id INT REFERENCES projects(id) ON DELETE CASCADE,
            knowledge_source_id INT REFERENCES knowledge_sources(id),
            document_id INT,
            artifact_id INT REFERENCES project_artifacts(id) ON DELETE SET NULL,
            title TEXT NOT NULL DEFAULT '未命名证据',
            evidence_type TEXT NOT NULL DEFAULT 'general',
            page INT,
            section TEXT DEFAULT '',
            quote TEXT NOT NULL DEFAULT '',
            summary TEXT DEFAULT '',
            tags JSONB DEFAULT '[]',
            reliability TEXT DEFAULT 'medium',
            note TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            usable_in_report BOOLEAN DEFAULT FALSE,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS engineering_documents (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            project_id INT REFERENCES projects(id) ON DELETE CASCADE,
            artifact_id INT REFERENCES project_artifacts(id) ON DELETE SET NULL,
            title TEXT NOT NULL DEFAULT '未命名工程文档',
            original_filename TEXT NOT NULL DEFAULT '',
            document_kind TEXT NOT NULL DEFAULT 'engineering_case',
            source_type TEXT NOT NULL DEFAULT 'current_project',
            storage_backend TEXT NOT NULL DEFAULT 'local',
            bucket TEXT NOT NULL DEFAULT '',
            object_key TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            mime_type TEXT DEFAULT '',
            file_size BIGINT DEFAULT 0,
            parse_status TEXT DEFAULT 'pending',
            extracted_text TEXT DEFAULT '',
            structured_data JSONB DEFAULT '{}',
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW())""")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_sources_name_type_unique ON knowledge_sources(name, source_type)")
        cur.execute("""INSERT INTO knowledge_sources (name, source_type, visibility, description, metadata)
            VALUES ('ASM Handbook Vol.2', 'standard_manual', 'public', '当前系统默认标准手册知识源', '{"source": "asm_handbook_vol_2"}')
            ON CONFLICT DO NOTHING""")
        cur.execute("ALTER TABLE document_sources ADD COLUMN IF NOT EXISTS knowledge_source_id INT")
        cur.execute("ALTER TABLE document_sources ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'standard_manual'")
        cur.execute("ALTER TABLE document_sources ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'public'")
        cur.execute("ALTER TABLE document_sources ADD COLUMN IF NOT EXISTS organization_id INT")
        cur.execute("ALTER TABLE document_sources ADD COLUMN IF NOT EXISTS owner_user_id INT")
        cur.execute("ALTER TABLE document_sources ADD COLUMN IF NOT EXISTS domain_tags JSONB DEFAULT '[]'")
        cur.execute("ALTER TABLE document_sources ADD COLUMN IF NOT EXISTS confidentiality TEXT DEFAULT 'public'")
        cur.execute("ALTER TABLE document_sources ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'standard_manual'")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS document_id INT")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'public'")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS organization_id INT")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS owner_user_id INT")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS project_id INT")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS domain_tags JSONB DEFAULT '[]'")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS confidentiality TEXT DEFAULT 'public'")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS evidence_level TEXT DEFAULT 'standard'")
        cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content_text)) STORED")
        cur.execute("ALTER TABLE evidence_cards ADD COLUMN IF NOT EXISTS note TEXT DEFAULT ''")
        cur.execute("ALTER TABLE evidence_cards ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft'")
        cur.execute("ALTER TABLE evidence_cards ADD COLUMN IF NOT EXISTS usable_in_report BOOLEAN DEFAULT FALSE")
        cur.execute("""UPDATE document_sources
            SET source_type = COALESCE(NULLIF(source_type, ''), 'standard_manual'),
                visibility = COALESCE(NULLIF(visibility, ''), 'public'),
                confidentiality = COALESCE(NULLIF(confidentiality, ''), 'public')""")
        cur.execute("""UPDATE document_sources
            SET knowledge_source_id = (
                SELECT id FROM knowledge_sources
                WHERE name = 'ASM Handbook Vol.2' AND source_type = 'standard_manual'
                ORDER BY id LIMIT 1
            )
            WHERE knowledge_source_id IS NULL AND source_type = 'standard_manual'""")
        cur.execute("""UPDATE chunks
            SET source_type = COALESCE(NULLIF(source_type, ''), 'standard_manual'),
                visibility = COALESCE(NULLIF(visibility, ''), 'public'),
                confidentiality = COALESCE(NULLIF(confidentiality, ''), 'public'),
                evidence_level = COALESCE(NULLIF(evidence_level, ''), 'standard')""")
        cur.execute("""UPDATE chunks c
            SET document_id = c.source_id
            WHERE c.document_id IS NULL""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_sources_type ON knowledge_sources(source_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_document_sources_type ON document_sources(source_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source_type ON chunks(source_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_visibility ON chunks(visibility)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_fts ON chunks USING GIN (fts)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_evidence_project ON evidence_cards(project_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence_cards(evidence_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_evidence_status ON evidence_cards(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_engineering_documents_project ON engineering_documents(project_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_engineering_documents_hash ON engineering_documents(content_hash)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_engineering_documents_status ON engineering_documents(parse_status)")
        conn.commit()
        print("[Auth] 数据库表已就绪")
    except Exception as e:
        print(f"[Auth] 数据库初始化失败: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# === Google OAuth ===
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/google/callback")

def get_google_auth_url() -> str:
    params = urllib.parse.urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

def exchange_google_code(code: str) -> Optional[dict]:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    data = urllib.parse.urlencode({
        "code": code, "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code"
    }).encode()
    try:
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        print(f"[Auth] Google token exchange failed: {e}")
        return None

def get_google_user_info(access_token: str) -> Optional[dict]:
    try:
        req = urllib.request.Request("https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"})
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        print(f"[Auth] Google user info failed: {e}")
        return None

def google_login(code: str) -> Optional[dict]:
    tokens = exchange_google_code(code)
    if not tokens:
        return None
    info = get_google_user_info(tokens.get("access_token", ""))
    if not info or not info.get("email"):
        return None
    email = info["email"]
    name = info.get("name", "") or email.split("@")[0]
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, email, username, email_verified, created_at FROM users WHERE email = %s", (email.lower().strip(),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"id": row[0], "email": row[1], "username": row[2], "email_verified": row[3],
                    "created_at": row[4].isoformat() if row[4] else None}
    except:
        pass
    # New user via Google
    random_pwd = secrets.token_hex(16)
    return create_user(email, name, random_pwd)
def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

# ==================== Conversation History CRUD ====================
def _get_conn2():
    import psycopg2
    return psycopg2.connect(host="127.0.0.1", port=15432, dbname="foundry_kb", user="findmyjob", password="findmyjob_dev_password")

def _valid_project_id(cur, user_id, project_id):
    if not project_id:
        return None
    try:
        pid = int(project_id)
    except (TypeError, ValueError):
        return None
    cur.execute("SELECT id FROM projects WHERE id = %s AND user_id = %s", (pid, user_id))
    return pid if cur.fetchone() else None

def create_conversation(user_id, title="", project_id=None):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        pid = _valid_project_id(cur, user_id, project_id)
        cur.execute(
            "INSERT INTO conversations (user_id, title, project_id) VALUES (%s, %s, %s) RETURNING id, created_at",
            (user_id, title, pid),
        )
        r = cur.fetchone()
        conn.commit()
        return {"id": r[0], "title": title, "project_id": pid, "created_at": r[1].isoformat()}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"创建会话失败: {e}")
    finally:
        conn.close()

def list_conversations(user_id):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, created_at, updated_at, project_id FROM conversations WHERE user_id = %s ORDER BY updated_at DESC", (user_id,))
        return [{"id": r[0], "title": r[1], "created_at": r[2].isoformat(), "updated_at": r[3].isoformat(), "project_id": r[4]} for r in cur.fetchall()]
    finally:
        conn.close()

def get_conv_messages(conv_id, user_id):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, title, project_id FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
        conv = cur.fetchone()
        if not conv:
            return None
        cur.execute("SELECT id, role, content, metadata, created_at FROM conversation_messages WHERE conversation_id = %s ORDER BY id", (conv_id,))
        msgs = [{"id": r[0], "role": r[1], "content": r[2], "metadata": r[3], "created_at": r[4].isoformat()} for r in cur.fetchall()]
        return {"id": conv[0], "title": conv[1], "project_id": conv[2], "messages": msgs}
    finally:
        conn.close()

def save_message(conv_id, role, content, metadata=None):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO conversation_messages (conversation_id, role, content, metadata) VALUES (%s, %s, %s, %s) RETURNING id, created_at",
            (conv_id, role, content, json.dumps(metadata or {})))
        r = cur.fetchone()
        cur.execute("UPDATE conversations SET updated_at = NOW() WHERE id = %s", (conv_id,))
        conn.commit()
        return {"id": r[0], "created_at": r[1].isoformat()}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"保存消息失败: {e}")
    finally:
        conn.close()

def delete_conversation(conv_id, user_id):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def update_conv_title(conv_id, user_id, title):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE conversations SET title = %s, updated_at = NOW() WHERE id = %s AND user_id = %s", (title, conv_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

# ==================== Project Workspace CRUD ====================
def _normalize_project_name(name):
    name = (name or "").strip()
    return name[:80] if name else "未命名项目"

def _serialize_json(value, fallback):
    if value is None:
        value = fallback
    return json.dumps(value, ensure_ascii=False)

def _row_to_project(row):
    return {
        "id": row[0],
        "name": row[1],
        "customer_name": row[2] or "",
        "description": row[3] or "",
        "status": row[4] or "active",
        "created_at": row[5].isoformat() if row[5] else None,
        "updated_at": row[6].isoformat() if row[6] else None,
        "artifact_count": row[7] if len(row) > 7 else 0,
        "conversation_count": row[8] if len(row) > 8 else 0,
    }

def _row_to_artifact(row):
    return {
        "id": row[0],
        "project_id": row[1],
        "type": row[2],
        "title": row[3],
        "content": row[4],
        "structured_data": row[5] or {},
        "citations": row[6] or [],
        "metadata": row[7] or {},
        "created_at": row[8].isoformat() if row[8] else None,
        "updated_at": row[9].isoformat() if row[9] else None,
    }

def _row_to_evidence_card(row):
    return {
        "id": row[0],
        "project_id": row[1],
        "knowledge_source_id": row[2],
        "document_id": row[3],
        "artifact_id": row[4],
        "title": row[5],
        "evidence_type": row[6],
        "page": row[7],
        "section": row[8] or "",
        "quote": row[9] or "",
        "summary": row[10] or "",
        "tags": row[11] or [],
        "reliability": row[12] or "medium",
        "note": row[13] or "",
        "status": row[14] or "draft",
        "usable_in_report": bool(row[15]),
        "metadata": row[16] or {},
        "created_at": row[17].isoformat() if row[17] else None,
        "updated_at": row[18].isoformat() if row[18] else None,
    }

def _row_to_engineering_document(row):
    return {
        "id": row[0],
        "project_id": row[1],
        "artifact_id": row[2],
        "title": row[3],
        "original_filename": row[4],
        "document_kind": row[5],
        "source_type": row[6],
        "storage_backend": row[7],
        "bucket": row[8],
        "object_key": row[9],
        "content_hash": row[10],
        "mime_type": row[11] or "",
        "file_size": row[12] or 0,
        "parse_status": row[13] or "pending",
        "extracted_text": row[14] or "",
        "structured_data": row[15] or {},
        "metadata": row[16] or {},
        "created_at": row[17].isoformat() if row[17] else None,
        "updated_at": row[18].isoformat() if row[18] else None,
    }

def create_project(user_id, name="", customer_name="", description=""):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO projects (user_id, name, customer_name, description)
               VALUES (%s, %s, %s, %s)
               RETURNING id, name, customer_name, description, status, created_at, updated_at, 0, 0""",
            (user_id, _normalize_project_name(name), (customer_name or "").strip(), (description or "").strip()),
        )
        row = cur.fetchone()
        conn.commit()
        return _row_to_project(row)
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"创建项目失败: {e}")
    finally:
        conn.close()

def list_projects(user_id):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT p.id, p.name, p.customer_name, p.description, p.status, p.created_at, p.updated_at,
                      COUNT(DISTINCT a.id)::int AS artifact_count,
                      COUNT(DISTINCT c.id)::int AS conversation_count
               FROM projects p
               LEFT JOIN project_artifacts a ON a.project_id = p.id
               LEFT JOIN conversations c ON c.project_id = p.id
               WHERE p.user_id = %s
               GROUP BY p.id
               ORDER BY p.updated_at DESC""",
            (user_id,),
        )
        return [_row_to_project(r) for r in cur.fetchall()]
    finally:
        conn.close()

def get_project(project_id, user_id):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT p.id, p.name, p.customer_name, p.description, p.status, p.created_at, p.updated_at,
                      COUNT(DISTINCT a.id)::int AS artifact_count,
                      COUNT(DISTINCT c.id)::int AS conversation_count
               FROM projects p
               LEFT JOIN project_artifacts a ON a.project_id = p.id
               LEFT JOIN conversations c ON c.project_id = p.id
               WHERE p.id = %s AND p.user_id = %s
               GROUP BY p.id""",
            (project_id, user_id),
        )
        project_row = cur.fetchone()
        if not project_row:
            return None
        cur.execute(
            """SELECT id, project_id, artifact_type, title, content, structured_data, citations, metadata, created_at, updated_at
               FROM project_artifacts
               WHERE project_id = %s AND user_id = %s
               ORDER BY created_at DESC, id DESC""",
            (project_id, user_id),
        )
        project = _row_to_project(project_row)
        project["artifacts"] = [_row_to_artifact(r) for r in cur.fetchall()]
        cur.execute(
            """SELECT id, title, created_at, updated_at
               FROM conversations
               WHERE project_id = %s AND user_id = %s
               ORDER BY updated_at DESC""",
            (project_id, user_id),
        )
        project["conversations"] = [
            {"id": r[0], "title": r[1], "created_at": r[2].isoformat(), "updated_at": r[3].isoformat(), "project_id": project_id}
            for r in cur.fetchall()
        ]
        project["evidence_cards"] = list_evidence_cards(user_id, project_id, cur=cur)
        project["engineering_documents"] = list_engineering_documents(user_id, project_id, cur=cur)
        return project
    finally:
        conn.close()

def update_project(user_id, project_id, name=None, customer_name=None, description=None, status=None):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
        if not cur.fetchone():
            return None
        updates = []
        values = []
        if name is not None:
            updates.append("name = %s")
            values.append(_normalize_project_name(name))
        if customer_name is not None:
            updates.append("customer_name = %s")
            values.append((customer_name or "").strip())
        if description is not None:
            updates.append("description = %s")
            values.append((description or "").strip())
        if status is not None:
            updates.append("status = %s")
            values.append((status or "active").strip() or "active")
        if not updates:
            return get_project(project_id, user_id)
        updates.append("updated_at = NOW()")
        values.extend([project_id, user_id])
        cur.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = %s AND user_id = %s", values)
        conn.commit()
        return get_project(project_id, user_id)
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"更新项目失败: {e}")
    finally:
        conn.close()

def save_project_artifact(user_id, project_id, artifact_type, title, content, structured_data=None, citations=None, metadata=None):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
        if not cur.fetchone():
            raise HTTPException(404, "项目不存在")
        clean_title = (title or "").strip()[:120] or "未命名产物"
        clean_type = (artifact_type or "qa").strip()[:40] or "qa"
        cur.execute(
            """INSERT INTO project_artifacts
               (project_id, user_id, artifact_type, title, content, structured_data, citations, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id, project_id, artifact_type, title, content, structured_data, citations, metadata, created_at, updated_at""",
            (
                project_id,
                user_id,
                clean_type,
                clean_title,
                content or "",
                _serialize_json(structured_data, {}),
                _serialize_json(citations, []),
                _serialize_json(metadata, {}),
            ),
        )
        row = cur.fetchone()
        cur.execute("UPDATE projects SET updated_at = NOW() WHERE id = %s", (project_id,))
        conn.commit()
        return _row_to_artifact(row)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"保存项目产物失败: {e}")
    finally:
        conn.close()

def list_evidence_cards(user_id, project_id, cur=None):
    own_conn = None
    try:
        if cur is None:
            own_conn = _get_conn2()
            cur = own_conn.cursor()
        cur.execute(
            """SELECT id, project_id, knowledge_source_id, document_id, artifact_id, title, evidence_type,
                      page, section, quote, summary, tags, reliability, note, status, usable_in_report,
                      metadata, created_at, updated_at
               FROM evidence_cards
               WHERE project_id = %s AND user_id = %s
               ORDER BY usable_in_report DESC, updated_at DESC, id DESC""",
            (project_id, user_id),
        )
        return [_row_to_evidence_card(row) for row in cur.fetchall()]
    finally:
        if own_conn is not None:
            own_conn.close()

def _clean_evidence_payload(data):
    data = data or {}
    tags = data.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    reliability = (data.get("reliability") or "medium").strip()
    if reliability not in ("high", "medium", "low"):
        reliability = "medium"
    status = (data.get("status") or "draft").strip()
    if status not in ("draft", "confirmed", "archived"):
        status = "draft"
    page = data.get("page")
    try:
        page = int(page) if page not in (None, "") else None
    except (TypeError, ValueError):
        page = None
    document_id = data.get("document_id") or data.get("source_id") or data.get("sourceId")
    try:
        document_id = int(document_id) if document_id not in (None, "") else None
    except (TypeError, ValueError):
        document_id = None
    artifact_id = data.get("artifact_id") or data.get("artifactId")
    try:
        artifact_id = int(artifact_id) if artifact_id not in (None, "") else None
    except (TypeError, ValueError):
        artifact_id = None
    title = (data.get("title") or "").strip()
    quote = (data.get("quote") or data.get("text") or "").strip()
    if not title:
        title = (quote[:48] + "...") if len(quote) > 48 else (quote or "未命名证据")
    return {
        "title": title[:120],
        "evidence_type": (data.get("evidence_type") or data.get("type") or "general").strip()[:40] or "general",
        "page": page,
        "section": (data.get("section") or "").strip()[:160],
        "quote": quote,
        "summary": (data.get("summary") or "").strip(),
        "tags": tags,
        "reliability": reliability,
        "note": (data.get("note") or "").strip(),
        "status": status,
        "usable_in_report": bool(data.get("usable_in_report")),
        "metadata": metadata,
        "document_id": document_id,
        "artifact_id": artifact_id,
    }

def create_evidence_card(user_id, project_id, data):
    payload = _clean_evidence_payload(data)
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
        if not cur.fetchone():
            raise HTTPException(404, "项目不存在")
        if payload["artifact_id"]:
            cur.execute(
                "SELECT id FROM project_artifacts WHERE id = %s AND project_id = %s AND user_id = %s",
                (payload["artifact_id"], project_id, user_id),
            )
            if not cur.fetchone():
                payload["artifact_id"] = None
        cur.execute(
            """INSERT INTO evidence_cards
               (user_id, project_id, document_id, artifact_id, title, evidence_type, page, section,
                quote, summary, tags, reliability, note, status, usable_in_report, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id, project_id, knowledge_source_id, document_id, artifact_id, title, evidence_type,
                         page, section, quote, summary, tags, reliability, note, status, usable_in_report,
                         metadata, created_at, updated_at""",
            (
                user_id,
                project_id,
                payload["document_id"],
                payload["artifact_id"],
                payload["title"],
                payload["evidence_type"],
                payload["page"],
                payload["section"],
                payload["quote"],
                payload["summary"],
                _serialize_json(payload["tags"], []),
                payload["reliability"],
                payload["note"],
                payload["status"],
                payload["usable_in_report"],
                _serialize_json(payload["metadata"], {}),
            ),
        )
        row = cur.fetchone()
        cur.execute("UPDATE projects SET updated_at = NOW() WHERE id = %s", (project_id,))
        conn.commit()
        return _row_to_evidence_card(row)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"保存证据卡失败: {e}")
    finally:
        conn.close()

def update_evidence_card(user_id, project_id, evidence_id, data):
    payload = _clean_evidence_payload(data)
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM evidence_cards WHERE id = %s AND project_id = %s AND user_id = %s",
            (evidence_id, project_id, user_id),
        )
        if not cur.fetchone():
            return None
        cur.execute(
            """UPDATE evidence_cards
               SET title = %s, evidence_type = %s, page = %s, section = %s, quote = %s, summary = %s,
                   tags = %s, reliability = %s, note = %s, status = %s, usable_in_report = %s,
                   metadata = %s, document_id = %s, artifact_id = %s, updated_at = NOW()
               WHERE id = %s AND project_id = %s AND user_id = %s
               RETURNING id, project_id, knowledge_source_id, document_id, artifact_id, title, evidence_type,
                         page, section, quote, summary, tags, reliability, note, status, usable_in_report,
                         metadata, created_at, updated_at""",
            (
                payload["title"],
                payload["evidence_type"],
                payload["page"],
                payload["section"],
                payload["quote"],
                payload["summary"],
                _serialize_json(payload["tags"], []),
                payload["reliability"],
                payload["note"],
                payload["status"],
                payload["usable_in_report"],
                _serialize_json(payload["metadata"], {}),
                payload["document_id"],
                payload["artifact_id"],
                evidence_id,
                project_id,
                user_id,
            ),
        )
        row = cur.fetchone()
        cur.execute("UPDATE projects SET updated_at = NOW() WHERE id = %s", (project_id,))
        conn.commit()
        return _row_to_evidence_card(row)
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"更新证据卡失败: {e}")
    finally:
        conn.close()

def delete_evidence_card(user_id, project_id, evidence_id):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM evidence_cards WHERE id = %s AND project_id = %s AND user_id = %s",
            (evidence_id, project_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def list_engineering_documents(user_id, project_id, cur=None):
    own_conn = None
    try:
        if cur is None:
            own_conn = _get_conn2()
            cur = own_conn.cursor()
        cur.execute(
            """SELECT id, project_id, artifact_id, title, original_filename, document_kind, source_type,
                      storage_backend, bucket, object_key, content_hash, mime_type, file_size, parse_status,
                      extracted_text, structured_data, metadata, created_at, updated_at
               FROM engineering_documents
               WHERE project_id = %s AND user_id = %s
               ORDER BY created_at DESC, id DESC""",
            (project_id, user_id),
        )
        return [_row_to_engineering_document(row) for row in cur.fetchall()]
    finally:
        if own_conn is not None:
            own_conn.close()

def create_engineering_document(
    user_id,
    project_id,
    title,
    original_filename,
    document_kind,
    source_type,
    storage_info,
    content_hash,
    mime_type,
    file_size,
    parse_status,
    extracted_text,
    structured_data=None,
    metadata=None,
    artifact_id=None,
):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
        if not cur.fetchone():
            raise HTTPException(404, "项目不存在")
        clean_kind = (document_kind or "engineering_case").strip()[:50] or "engineering_case"
        clean_source_type = (source_type or "current_project").strip()[:50] or "current_project"
        cur.execute(
            """INSERT INTO engineering_documents
               (user_id, project_id, artifact_id, title, original_filename, document_kind, source_type,
                storage_backend, bucket, object_key, content_hash, mime_type, file_size, parse_status,
                extracted_text, structured_data, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id, project_id, artifact_id, title, original_filename, document_kind, source_type,
                         storage_backend, bucket, object_key, content_hash, mime_type, file_size, parse_status,
                         extracted_text, structured_data, metadata, created_at, updated_at""",
            (
                user_id,
                project_id,
                artifact_id,
                (title or original_filename or "未命名工程文档").strip()[:160],
                (original_filename or "").strip()[:240],
                clean_kind,
                clean_source_type,
                storage_info.get("storage_backend") or "local",
                storage_info.get("bucket") or "",
                storage_info.get("object_key") or "",
                content_hash,
                mime_type or "",
                int(file_size or 0),
                parse_status or "pending",
                extracted_text or "",
                _serialize_json(structured_data, {}),
                _serialize_json(metadata, {}),
            ),
        )
        row = cur.fetchone()
        cur.execute("UPDATE projects SET updated_at = NOW() WHERE id = %s", (project_id,))
        conn.commit()
        return _row_to_engineering_document(row)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"保存工程文档失败: {e}")
    finally:
        conn.close()

def attach_artifact_to_engineering_document(user_id, project_id, document_id, artifact_id):
    conn = _get_conn2()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE engineering_documents
               SET artifact_id = %s, updated_at = NOW()
               WHERE id = %s AND project_id = %s AND user_id = %s
               RETURNING id, project_id, artifact_id, title, original_filename, document_kind, source_type,
                         storage_backend, bucket, object_key, content_hash, mime_type, file_size, parse_status,
                         extracted_text, structured_data, metadata, created_at, updated_at""",
            (artifact_id, document_id, project_id, user_id),
        )
        row = cur.fetchone()
        conn.commit()
        return _row_to_engineering_document(row) if row else None
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, f"关联工程文档产物失败: {e}")
    finally:
        conn.close()

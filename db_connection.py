import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# ── SSH tunnel singleton ──
_tunnel = None

def _ensure_tunnel():
    """Start an SSH tunnel if DB_MODE=tunnel and return (host, port) to connect to."""
    global _tunnel
    db_mode = os.getenv('DB_MODE', 'direct').lower()

    if db_mode != 'tunnel':
        return os.getenv('DB_HOST'), int(os.getenv('DB_PORT', '5432'))

    if _tunnel is not None and _tunnel.is_active:
        return '127.0.0.1', _tunnel.local_bind_port

    from sshtunnel import SSHTunnelForwarder

    _tunnel = SSHTunnelForwarder(
        (os.getenv('SSH_HOST'), 22),
        ssh_username=os.getenv('SSH_USER', 'ec2-user'),
        ssh_pkey=os.getenv('SSH_KEY_PATH'),
        remote_bind_address=(
            os.getenv('SSH_REMOTE_DB_HOST', os.getenv('DB_HOST')),
            int(os.getenv('SSH_REMOTE_DB_PORT', '5432')),
        ),
    )
    _tunnel.start()
    return '127.0.0.1', _tunnel.local_bind_port


def get_db_connection():
    """Create and return a database connection."""
    try:
        host, port = _ensure_tunnel()
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        return conn
    except Exception as e:
        raise Exception(f"Failed to connect to database: {str(e)}")

def execute_query(query, params=None):
    """Execute a query and return results as a list of dictionaries."""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
    except Exception as e:
        raise Exception(f"Query execution failed: {str(e)}")
    finally:
        if conn:
            conn.close()

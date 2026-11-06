"""
NoticeShield - Database Management Module
Handles SQLite connection, schema migrations, and queries for notices, admins, and verification logs.
"""

import sqlite3
import json
import os
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'notices.db')

def get_db_connection(db_path=DB_PATH):
    """Returns a connection to the SQLite database with row dictionary factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    """Hashes a password with SHA-256 and a standard salt for demo admin login."""
    salt = "neuroforge_noticeshield_salt_2026"
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()

def init_db(db_path=DB_PATH):
    """Initializes the database schema and default admin account if not existing."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Table 1: Admins
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table 2: Notices
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notice_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            department TEXT NOT NULL,
            notice_date TEXT NOT NULL,
            event_date TEXT NOT NULL,
            venue TEXT NOT NULL,
            description TEXT NOT NULL,
            issuer TEXT NOT NULL,
            canonical_data TEXT NOT NULL,
            digital_signature TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            pdf_path TEXT,
            qr_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table 3: Verification Logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notice_id TEXT,
            verification_status TEXT NOT NULL,
            result_details TEXT,
            verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Insert default administrator if none exists
    cursor.execute("SELECT id FROM admins WHERE username = 'admin'")
    if not cursor.fetchone():
        default_pwd_hash = hash_password("admin123")
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ('admin', default_pwd_hash)
        )

    conn.commit()
    conn.close()

def verify_admin(username: str, password: str, db_path=DB_PATH) -> bool:
    """Verifies admin login credentials."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM admins WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row and row['password_hash'] == hash_password(password):
        return True
    return False

def save_notice(notice_dict: dict, db_path=DB_PATH) -> bool:
    """Saves or updates a notice in the database."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO notices (
                notice_id, title, department, notice_date, event_date,
                venue, description, issuer, canonical_data, digital_signature,
                status, pdf_path, qr_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            notice_dict['notice_id'],
            notice_dict['title'],
            notice_dict['department'],
            notice_dict['notice_date'],
            notice_dict['event_date'],
            notice_dict['venue'],
            notice_dict['description'],
            notice_dict['issuer'],
            notice_dict['canonical_data'],
            notice_dict['digital_signature'],
            notice_dict.get('status', 'active'),
            notice_dict.get('pdf_path', ''),
            notice_dict.get('qr_path', '')
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_notice_by_id(notice_id: str, db_path=DB_PATH):
    """Retrieves a notice by its unique notice_id."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notices WHERE notice_id = ?", (notice_id.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_notices(db_path=DB_PATH):
    """Returns all registered notices ordered by creation time descending."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notices ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def revoke_notice(notice_id: str, db_path=DB_PATH) -> bool:
    """Marks a notice as revoked."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE notices SET status = 'revoked' WHERE notice_id = ?", (notice_id.strip(),))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def reactivate_notice(notice_id: str, db_path=DB_PATH) -> bool:
    """Reactivates a revoked notice."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE notices SET status = 'active' WHERE notice_id = ?", (notice_id.strip(),))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed

def log_verification(notice_id: str, status: str, details: dict, db_path=DB_PATH):
    """Records a verification attempt in verification_logs."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO verification_logs (notice_id, verification_status, result_details)
        VALUES (?, ?, ?)
    ''', (notice_id, status, json.dumps(details)))
    conn.commit()
    conn.close()

def get_verification_logs(limit=25, db_path=DB_PATH):
    """Retrieves recent verification logs."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM verification_logs ORDER BY verified_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    logs = []
    for r in rows:
        item = dict(r)
        try:
            item['details_parsed'] = json.loads(item['result_details'])
        except Exception:
            item['details_parsed'] = {}
        logs.append(item)
    return logs

def get_dashboard_stats(db_path=DB_PATH):
    """Computes analytics counts for the admin dashboard."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM notices")
    total_notices = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM notices WHERE status = 'revoked'")
    revoked_notices = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM verification_logs WHERE verification_status = 'VERIFIED'")
    verified_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM verification_logs WHERE verification_status = 'MODIFIED'")
    modified_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM verification_logs WHERE verification_status IN ('UNVERIFIED', 'INVALID_SIGNATURE')")
    unverified_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM verification_logs")
    total_verifications = cursor.fetchone()[0]

    conn.close()

    return {
        'total_notices': total_notices,
        'active_notices': total_notices - revoked_notices,
        'revoked_notices': revoked_notices,
        'verified_count': verified_count,
        'modified_count': modified_count,
        'unverified_count': unverified_count,
        'total_verifications': total_verifications
    }

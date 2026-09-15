# -*- coding: utf-8 -*-
# session_store.py -- minimal, dependency-free per-session store for the
# local/LAN-only private-server auth tier (mitm_serve.py).
#
# Scope note (Phase 1 of 07_ros_legacy_approach/PRIVATE_SERVER_ADAPTATION_PLAN.md
# section 14): this is throwaway/test infra for a LOCAL test server, not
# production-grade. No sqlite dependency exists anywhere else in this project
# (checked: no `import sqlite3` under mitm/ or elsewhere in the repo), so per
# the task's own instruction this uses a minimal JSON-file-backed store
# instead of adding a new dependency.
#
# Security note: session ids here are cryptographically random (uuid4, backed
# by os.urandom) but are NOT derived from any password/credential, and this
# store is not designed to resist a hostile actor -- it only needs to be
# unique per local test login, per the plan's own scoping (PRIVATE_SERVER_
# ADAPTATION_PLAN.md section 6, point 1).
import json
import os
import threading
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_PATH = os.path.join(HERE, 'session_store.json')

_lock = threading.RLock()

# Default session lifetime for a LAN test server (process-lifetime testing
# is the common case, but an expiry is still recorded per the task's
# session-store field requirements).
DEFAULT_TTL_SECONDS = 6 * 60 * 60  # 6 hours


def _short(session_id):
    """Short prefix for safe logging -- never log the full session id."""
    if not session_id:
        return '<none>'
    return session_id[:8]


def _load():
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        # Corrupt/partial file -- treat as empty rather than crash the
        # auth server; this is throwaway local test infra.
        return {}


def _save(data):
    tmp_path = STORE_PATH + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp_path, STORE_PATH)


def create_session(player_id, source='guest_login', ttl_seconds=DEFAULT_TTL_SECONDS):
    """Mint a brand-new, cryptographically random session id for player_id.

    Uses uuid.uuid4() (backed by os.urandom -- CSPRNG, not derived from any
    password) formatted as a plain hex string prefixed 'sess_' so it drops
    into the existing sdk_token/user string fields the client already
    parses (06_notes/LOCAL_SESSION_CONTRACT.md) without changing their
    expected type (opaque string token, not a strict UUID-canonical form).
    """
    session_id = 'sess_' + uuid.uuid4().hex
    now = time.time()
    record = {
        'session_id': session_id,
        'player_id': player_id,
        'created_at': now,
        'expires_at': now + ttl_seconds,
        'source': source,
    }
    with _lock:
        data = _load()
        data[session_id] = record
        _save(data)
    return record


def get_session(session_id):
    """Return the session record dict, or None if unknown."""
    if not session_id:
        return None
    with _lock:
        data = _load()
        return data.get(session_id)


def validate_session(session_id):
    """Return True if session_id exists and has not expired."""
    record = get_session(session_id)
    if record is None:
        return False
    return time.time() < record.get('expires_at', 0)


def expire_session(session_id):
    """Immediately mark a session expired (idempotent)."""
    with _lock:
        data = _load()
        record = data.get(session_id)
        if record is None:
            return False
        record['expires_at'] = 0
        _save(data)
        return True


def all_sessions():
    """Debug/testing helper: return the full in-store dict (session_id ->
    record). Not used by the HTTP handlers themselves."""
    with _lock:
        return _load()

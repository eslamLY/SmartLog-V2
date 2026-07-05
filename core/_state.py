"""
core/_state.py — Shared process-wide state for lifecycle synchronisation.

This module must NOT import any other core/ module to avoid circular
imports at application factory time.
"""
import threading

# Signalled when the background DB-init thread completes
# (see core/__init__.py _init_db_background).
db_ready_event = threading.Event()

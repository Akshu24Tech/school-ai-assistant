import os
import tempfile

# config requires a key on import, and the memory/audit dbs should land somewhere
# disposable during tests — set all of that before any app code loads.
os.environ.setdefault("GEMINI_API_KEY", "test-key")

_tmp = tempfile.mkdtemp(prefix="school-erp-test-")
os.environ.setdefault("MEMORY_DB", os.path.join(_tmp, "memory.db"))
os.environ.setdefault("AUDIT_DB", os.path.join(_tmp, "audit.db"))

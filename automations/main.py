"""
Cloud Functions entrypoint.

GCF looks for the entry_point function in main.py at the source root.
This re-exports from the kavik-intake handler.
"""

from kavik_intake.handler import handle_intake  # noqa: F401 — GCF entrypoint

# If adding more pipelines later, import and route here:
# from acme_lead_response.handler import handle_lead  # noqa: F401

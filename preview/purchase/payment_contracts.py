"""Configured identity checks for local synthetic evidence, never Stripe access."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class FixtureBinding:
    account: str = "TEST_ONLY_ACCOUNT"
    environment: str = "TEST_ONLY_SANDBOX"

    def __post_init__(self):
        if any(not isinstance(v, str) or not re.fullmatch(r"TEST_ONLY_[A-Z0-9_]{1,80}", v)
               for v in (self.account, self.environment)):
            raise ValueError("SYNTHETIC_BINDING_REQUIRED")


DEFAULT_BINDING = FixtureBinding()


def snapshot_matches(snapshot, order_id, session_id, binding=DEFAULT_BINDING):
    """Match against trusted configuration/order, not two event-supplied values.

    Final paid timestamps and immutable payment identity are checked separately
    by the model. A valid association alone does not establish successful payment.
    """
    return (isinstance(snapshot, dict)
            and snapshot.get("account") == binding.account
            and snapshot.get("environment") == binding.environment
            and snapshot.get("mode") == "LOCAL_FAKE_ONLY"
            and snapshot.get("livemode") is False
            and snapshot.get("id") == session_id
            and snapshot.get("order_id") == order_id
            and isinstance(snapshot.get("status"), str)
            and isinstance(snapshot.get("payment_status"), str)
            and (snapshot.get("status"), snapshot.get("payment_status")) in {
                ("open", "unpaid"), ("expired", "unpaid"), ("complete", "processing"),
                ("complete", "failed"), ("complete", "paid")}
            and type(snapshot.get("amount_total")) is int and snapshot["amount_total"] == 14900
            and snapshot.get("currency") == "usd"
            and type(snapshot.get("quantity")) is int and snapshot["quantity"] == 1
            and type(snapshot.get("tax_cents")) is int and snapshot["tax_cents"] == 0
            and snapshot.get("product") == "WORKFLOW_BLUEPRINT")

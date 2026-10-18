"""Offline webhook-boundary contracts using TEST_ONLY signatures and fake IDs.

This is deliberately NOT a Stripe webhook endpoint or production verifier. It
accepts only explicit synthetic envelopes, a TEST_ONLY key and local fake
sessions. A future authorized integration must use the official provider SDK
and verify its actual event format/account/environment before dispatch.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import json
import re

from .model import FakeProvider
from .payment_contracts import DEFAULT_BINDING, FixtureBinding

MAX_BODY_BYTES = 16 * 1024
TOLERANCE_SECONDS = 300
EVENT_TYPES = frozenset({"checkout.session.completed",
                         "checkout.session.async_payment_succeeded",
                         "checkout.session.async_payment_failed",
                         "checkout.session.expired"})


class FixtureEventError(ValueError):
    """Static error code only: never include a body, signature or key."""


@dataclass(frozen=True)
class VerifiedFixtureEvent:
    event_id: str
    event_type: str
    session_id: str


def verify_fixture_event(raw_body, signature_header, fixture_key, now, binding=DEFAULT_BINDING):
    if type(binding) is not FixtureBinding:
        raise FixtureEventError("CONFIGURED_SYNTHETIC_BINDING_REQUIRED")
    if not isinstance(raw_body, bytes) or not 1 <= len(raw_body) <= MAX_BODY_BYTES:
        raise FixtureEventError("FIXTURE_BODY_INVALID")
    if not isinstance(fixture_key, bytes) or not fixture_key.startswith(b"TEST_ONLY_") or not 32 <= len(fixture_key) <= 128:
        raise FixtureEventError("TEST_ONLY_KEY_REQUIRED")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise FixtureEventError("EXPLICIT_AWARE_CLOCK_REQUIRED")
    if not isinstance(signature_header, str) or len(signature_header) > 2048:
        raise FixtureEventError("FIXTURE_SIGNATURE_INVALID")
    timestamps, signatures = [], []
    for part in signature_header.split(","):
        pair = part.strip().split("=", 1)
        if len(pair) != 2 or pair[0] not in {"t", "v1", "v0"}:
            raise FixtureEventError("FIXTURE_SIGNATURE_INVALID")
        if pair[0] == "t":
            timestamps.append(pair[1])
        elif pair[0] == "v1":
            signatures.append(pair[1])
    if len(timestamps) != 1 or not re.fullmatch(r"[0-9]{10,12}", timestamps[0]) or not 1 <= len(signatures) <= 10:
        raise FixtureEventError("FIXTURE_SIGNATURE_INVALID")
    if any(not re.fullmatch(r"[0-9a-fA-F]{64}", item) for item in signatures):
        raise FixtureEventError("FIXTURE_SIGNATURE_INVALID")
    if abs(now.timestamp() - int(timestamps[0])) > TOLERANCE_SECONDS:
        raise FixtureEventError("FIXTURE_TIMESTAMP_OUTSIDE_TOLERANCE")
    expected = hmac.new(fixture_key, timestamps[0].encode("ascii") + b"." + raw_body, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, item.lower()) for item in signatures):
        raise FixtureEventError("FIXTURE_SIGNATURE_MISMATCH")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise FixtureEventError("FIXTURE_JSON_INVALID")
            result[key] = value
        return result

    def invalid_constant(_):
        raise FixtureEventError("FIXTURE_JSON_INVALID")

    try:
        event = json.loads(raw_body, object_pairs_hook=unique, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise FixtureEventError("FIXTURE_JSON_INVALID") from None
    if not isinstance(event, dict) or set(event) != {"id", "type", "livemode", "fixture", "account", "environment", "data"}:
        raise FixtureEventError("FIXTURE_ENVELOPE_INVALID")
    if event["fixture"] is not True or event["livemode"] is not False:
        raise FixtureEventError("SYNTHETIC_NONLIVE_EVENT_REQUIRED")
    if event["account"] != binding.account or event["environment"] != binding.environment:
        raise FixtureEventError("FIXTURE_ACCOUNT_ENVIRONMENT_MISMATCH")
    if not isinstance(event["id"], str) or not re.fullmatch(r"fixture_evt_[A-Za-z0-9_]{1,80}", event["id"]):
        raise FixtureEventError("FIXTURE_EVENT_ID_INVALID")
    if not isinstance(event["type"], str) or event["type"] not in EVENT_TYPES:
        raise FixtureEventError("FIXTURE_EVENT_TYPE_UNSUPPORTED")
    data = event["data"]
    if not isinstance(data, dict) or set(data) != {"object"} or not isinstance(data["object"], dict) or set(data["object"]) != {"id"}:
        raise FixtureEventError("FIXTURE_OBJECT_INVALID")
    session_id = data["object"]["id"]
    if not isinstance(session_id, str) or not re.fullmatch(r"fake_cs_ord_[0-9a-f]{32}_[1-9][0-9]*", session_id):
        raise FixtureEventError("LOCAL_FAKE_SESSION_REQUIRED")
    return VerifiedFixtureEvent(event["id"], event["type"], session_id)


def apply_fixture_event(store, raw_body, signature_header, fixture_key, now):
    if type(store.provider) is not FakeProvider:
        raise FixtureEventError("LOCAL_FAKE_PROVIDER_REQUIRED")
    event = verify_fixture_event(raw_body, signature_header, fixture_key, now)
    # The verified label is only a wake-up, never proof of payment. Re-read the
    # local provider and let the existing transaction/unique constraints decide.
    return store.event(event.event_id, event.session_id)

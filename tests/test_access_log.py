import unittest

from app.presentation.middleware.access_log import _is_sensitive_query_key
from app.presentation.middleware.request_context import (
    _safe_request_id,
    _safe_trace_id,
    _trace_id_from_traceparent,
)


class AccessLogTests(unittest.TestCase):
    def test_sensitive_query_key_variants_are_redacted(self) -> None:
        for key in (
            "access_token",
            "client_secret",
            "refresh-token",
            "id_token",
            "password_confirmation",
            "authorization_code",
        ):
            self.assertTrue(_is_sensitive_query_key(key), key)

    def test_regular_query_key_is_not_redacted(self) -> None:
        self.assertFalse(_is_sensitive_query_key("page"))

    def test_request_id_rejects_untrusted_values(self) -> None:
        self.assertEqual(_safe_request_id("req_123"), "req_123")
        self.assertNotEqual(_safe_request_id("bad\nrequest"), "bad\nrequest")
        self.assertNotEqual(_safe_request_id("x" * 129), "x" * 129)

    def test_trace_id_requires_w3c_hex_format(self) -> None:
        trace_id = "0123456789abcdef0123456789abcdef"
        self.assertEqual(_safe_trace_id(trace_id.upper()), trace_id)
        self.assertIsNone(_safe_trace_id("0" * 32))
        self.assertIsNone(_safe_trace_id("not-a-trace-id"))

    def test_traceparent_requires_supported_valid_format(self) -> None:
        trace_id = "0123456789abcdef0123456789abcdef"
        self.assertEqual(
            _trace_id_from_traceparent(f"00-{trace_id}-0123456789abcdef-01"),
            trace_id,
        )
        self.assertIsNone(_trace_id_from_traceparent(f"01-{trace_id}-0123456789abcdef-01"))

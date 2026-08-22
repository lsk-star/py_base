import json
import unittest

from pybase.presentation.responses import error_response, success_response


class ApiResponseTests(unittest.TestCase):
    def test_success_response_keeps_null_data_and_omits_disabled_trace_id(self) -> None:
        response = success_response()
        payload = json.loads(response.body)

        self.assertIsNone(payload["data"])
        self.assertNotIn("trace_id", payload)

    def test_error_response_keeps_null_data_and_omits_disabled_trace_id(self) -> None:
        response = error_response("BAD_REQUEST", "错误", status_code=400)
        payload = json.loads(response.body)

        self.assertFalse(payload["success"])
        self.assertIsNone(payload["data"])
        self.assertNotIn("trace_id", payload)


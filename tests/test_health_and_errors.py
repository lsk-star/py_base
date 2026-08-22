import json
from http import HTTPStatus
from types import SimpleNamespace
import unittest

from pybase.contracts.lifecycle import ReadinessStatus
from pybase.core.errors import ErrorCode
from pybase.modules.health.router import readiness
from pybase.presentation.exception_handlers import error_code_for_http_status


class FakeRegistry:
    def __init__(self, checks: list[ReadinessStatus]) -> None:
        self._checks = checks

    async def readiness(self) -> list[ReadinessStatus]:
        return self._checks


class HealthAndErrorTests(unittest.IsolatedAsyncioTestCase):
    async def test_not_ready_returns_failure_envelope(self) -> None:
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    components=FakeRegistry([ReadinessStatus("database", False, "数据库暂不可用")])
                )
            )
        )

        response = await readiness(request)
        payload = json.loads(response.body)

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], ErrorCode.DEPENDENCY_UNAVAILABLE)
        self.assertEqual(payload["data"]["status"], "not_ready")

    async def test_ready_returns_success_envelope(self) -> None:
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    components=FakeRegistry([ReadinessStatus("database", True)])
                )
            )
        )

        response = await readiness(request)
        payload = json.loads(response.body)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["code"], "SUCCESS")


class HttpErrorCodeTests(unittest.TestCase):
    def test_http_statuses_map_to_matching_error_codes(self) -> None:
        self.assertEqual(error_code_for_http_status(401), ErrorCode.UNAUTHORIZED)
        self.assertEqual(error_code_for_http_status(403), ErrorCode.FORBIDDEN)
        self.assertEqual(error_code_for_http_status(404), ErrorCode.NOT_FOUND)
        self.assertEqual(error_code_for_http_status(409), ErrorCode.CONFLICT)
        self.assertEqual(error_code_for_http_status(429), ErrorCode.TOO_MANY_REQUESTS)

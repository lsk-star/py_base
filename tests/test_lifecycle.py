import unittest

from pybase.contracts.lifecycle import ComponentRegistry, ReadinessStatus


class FakeComponent:
    def __init__(
        self,
        name: str,
        *,
        start_error: Exception | None = None,
        stop_error: Exception | None = None,
        readiness_error: Exception | None = None,
    ) -> None:
        self.name = name
        self.start_error = start_error
        self.stop_error = stop_error
        self.readiness_error = readiness_error
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        if self.start_error:
            raise self.start_error
        self.started = True

    async def stop(self) -> None:
        self.stopped = True
        if self.stop_error:
            raise self.stop_error

    async def readiness(self) -> ReadinessStatus:
        if self.readiness_error:
            raise self.readiness_error
        return ReadinessStatus(self.name, True)


class ComponentRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_continues_after_component_failure(self) -> None:
        registry = ComponentRegistry()
        first = FakeComponent("first")
        failing = FakeComponent("failing", stop_error=RuntimeError("close failed"))
        registry.add(first)
        registry.add(failing)

        with self.assertRaises(ExceptionGroup):
            await registry.stop()

        self.assertTrue(failing.stopped)
        self.assertTrue(first.stopped)

    async def test_readiness_converts_component_error_to_not_ready_status(self) -> None:
        registry = ComponentRegistry()
        registry.add(FakeComponent("healthy"))
        registry.add(FakeComponent("broken", readiness_error=RuntimeError("unavailable")))

        statuses = await registry.readiness()

        self.assertEqual(statuses[0], ReadinessStatus("healthy", True))
        self.assertEqual(statuses[1], ReadinessStatus("broken", False, "就绪检查失败"))

    async def test_start_cleans_up_previously_started_components(self) -> None:
        registry = ComponentRegistry()
        started = FakeComponent("started")
        failing = FakeComponent("failing", start_error=RuntimeError("start failed"))
        registry.add(started)
        registry.add(failing)

        with self.assertRaisesRegex(RuntimeError, "start failed"):
            await registry.start()

        self.assertTrue(started.stopped)

    async def test_get_returns_component_by_concrete_type(self) -> None:
        registry = ComponentRegistry()
        component = FakeComponent("database")
        registry.add(component)

        result = registry.get(FakeComponent)

        self.assertIs(result, component)

    async def test_get_raises_when_component_is_not_registered(self) -> None:
        registry = ComponentRegistry()

        with self.assertRaisesRegex(LookupError, "FakeComponent"):
            registry.get(FakeComponent)

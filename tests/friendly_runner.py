"""User-friendly unittest runner for the Fly-in test suite."""

import sys
import unittest
from collections.abc import Sequence
from types import TracebackType
from typing import Any, ClassVar


SEPARATOR = "-" * 30
TestError = (
    tuple[type[BaseException], BaseException, TracebackType]
    | tuple[None, None, None]
)


class FriendlyTestResult(unittest.TextTestResult):
    """Print each test with the code area and behavior under test."""

    CODE_TARGETS: ClassVar[dict[str, tuple[str, ...]]] = {
        "test_parser": ("src/parser.py :: MapParser",),
        "tests.test_parser": ("src/parser.py :: MapParser",),
        "test_drone": (
            "src/drone.py :: Drone",
            "src/fly_in.py :: Simulation.configure/next_turn",
        ),
        "tests.test_drone": (
            "src/drone.py :: Drone",
            "src/fly_in.py :: Simulation.configure/next_turn",
        ),
        "test_simulation": (
            "src/fly_in.py :: Simulation",
            "src/ZoneHub.py :: Zone/Connection",
        ),
        "tests.test_simulation": (
            "src/fly_in.py :: Simulation",
            "src/ZoneHub.py :: Zone/Connection",
        ),
        "test_benchmarks": (
            "src/fly_in.py :: Simulation scheduler",
            "maps/ :: Subject 1.6 benchmark maps",
        ),
        "tests.test_benchmarks": (
            "src/fly_in.py :: Simulation scheduler",
            "maps/ :: Subject 1.6 benchmark maps",
        ),
        "test_visualization": (
            "src/visualization.py :: BrowserSimulation/SvgMapRenderer",
        ),
        "tests.test_visualization": (
            "src/visualization.py :: BrowserSimulation/SvgMapRenderer",
        ),
        "test_web_app": ("src/web_app.py :: Fullscreen viewport",),
        "tests.test_web_app": ("src/web_app.py :: Fullscreen viewport",),
    }

    def startTest(self, test: unittest.case.TestCase) -> None:
        """Print a readable header before each individual test."""
        super().startTest(test)
        test_id = test.id()
        module_name = test.__class__.__module__
        class_name = test.__class__.__name__
        method_name = test._testMethodName
        description = test.shortDescription() or self._humanize(method_name)
        targets = self.CODE_TARGETS.get(module_name, (module_name,))

        self.stream.writeln()
        self.stream.writeln(SEPARATOR)
        self.stream.writeln("PARTE DO CODIGO TESTADA")
        for target in targets:
            self.stream.writeln(f"  {target}")
        self.stream.writeln()
        self.stream.writeln("ARQUIVO/CLASSE DE TESTE")
        self.stream.writeln(f"  {module_name}.{class_name}")
        self.stream.writeln()
        self.stream.writeln("TESTE ESPECIFICO")
        self.stream.writeln(f"  {test_id}")
        self.stream.writeln(f"  {description}")
        self.stream.writeln()
        self.stream.write("RESULTADO: ")
        self.stream.flush()

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        """Print a friendly success status."""
        super().addSuccess(test)
        self.stream.writeln("OK")

    def addFailure(
        self,
        test: unittest.case.TestCase,
        err: TestError,
    ) -> None:
        """Print a friendly failure status."""
        super().addFailure(test, err)
        self.stream.writeln("FALHOU")

    def addError(
        self,
        test: unittest.case.TestCase,
        err: TestError,
    ) -> None:
        """Print a friendly error status."""
        super().addError(test, err)
        self.stream.writeln("ERRO")

    def addSkip(
        self,
        test: unittest.case.TestCase,
        reason: str,
    ) -> None:
        """Print a friendly skipped status."""
        super().addSkip(test, reason)
        self.stream.writeln(f"PULADO ({reason})")

    @staticmethod
    def _humanize(method_name: str) -> str:
        """Convert a unittest method name into readable text."""
        return method_name.removeprefix("test_").replace("_", " ").capitalize()


def friendly_result_factory(*args: Any, **kwargs: Any) -> FriendlyTestResult:
    """Build the custom result class with unittest's internal arguments."""
    return FriendlyTestResult(*args, **kwargs)


def main(arguments: Sequence[str] | None = None) -> int:
    """Discover and run all tests with readable output."""
    if arguments is None:
        arguments = sys.argv[1:]

    start_directory = arguments[0] if arguments else "tests"
    suite = unittest.defaultTestLoader.discover(start_directory)
    runner = unittest.TextTestRunner(
        resultclass=friendly_result_factory,
        verbosity=0,
    )
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

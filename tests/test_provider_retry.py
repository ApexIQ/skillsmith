import os
import tempfile
import unittest
import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from skillsmith.commands.providers import (
    GitHubTopicsProvider,
    ProviderSearchError,
    HuggingFaceProvider,
    OrgRegistryProvider,
    SkillCandidate,
    discover_skills_with_diagnostics,
)


class _StubProvider:
    source_name = "skills.sh"

    def __init__(self, side_effect):
        self._side_effect = side_effect
        self.calls = 0

    def search(self, query: str, limit: int = 10):
        self.calls += 1
        value = self._side_effect(self.calls)
        if isinstance(value, Exception):
            raise value
        return value


class ProviderRetryTests(unittest.TestCase):
    @contextmanager
    def project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            previous = Path.cwd()
            os.chdir(cwd)
            try:
                yield cwd
            finally:
                os.chdir(previous)

    def test_discovery_retries_network_errors_and_succeeds(self):
        candidate = SkillCandidate(
            name="python-packaging",
            description="Packaging workflow",
            source="skills.sh",
            install_ref="org/repo@python-packaging",
            trust_score=70,
        )
        provider = _StubProvider(
            lambda call: requests.RequestException("temporary network error")
            if call < 3
            else [candidate]
        )
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.providers.build_provider_registry",
            return_value={"skills.sh": provider},
        ), mock.patch("skillsmith.commands.providers.time.sleep", return_value=None):
            results, errors = discover_skills_with_diagnostics("python packaging", cwd, source="skills.sh", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "python-packaging")
        self.assertEqual(errors, [])
        telemetry = getattr(discover_skills_with_diagnostics, "_last_telemetry", [])
        self.assertEqual(len(telemetry), 1)
        self.assertEqual(telemetry[0]["provider"], "skills.sh")
        self.assertEqual(telemetry[0]["status"], "ok")
        self.assertEqual(telemetry[0]["attempts"], 3)

    def test_discovery_reports_error_after_retry_exhaustion(self):
        provider = _StubProvider(lambda call: requests.RequestException(f"network down {call}"))
        with self.project_dir() as cwd, mock.patch(
            "skillsmith.commands.providers.build_provider_registry",
            return_value={"skills.sh": provider},
        ), mock.patch("skillsmith.commands.providers.time.sleep", return_value=None):
            results, errors = discover_skills_with_diagnostics("python packaging", cwd, source="skills.sh", limit=5)

        self.assertEqual(results, [])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ProviderSearchError)
        self.assertEqual(errors[0].attempts, 3)
        self.assertEqual(errors[0].error_type, "network")
        telemetry = getattr(discover_skills_with_diagnostics, "_last_telemetry", [])
        self.assertEqual(len(telemetry), 1)
        self.assertEqual(telemetry[0]["status"], "error")
        self.assertEqual(telemetry[0]["attempts"], 3)
        self.assertEqual(telemetry[0]["error_type"], "network")

    def test_huggingface_network_errors_retry_through_diagnostics(self):
        provider = HuggingFaceProvider()
        cwd = Path.cwd() / ".tmp-tests" / "provider-retry-huggingface-network"
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            with mock.patch(
                "skillsmith.commands.providers.build_provider_registry",
                return_value={"huggingface": provider},
            ), mock.patch("skillsmith.commands.providers.requests.get", side_effect=requests.RequestException("temporary outage")), mock.patch(
                "skillsmith.commands.providers.time.sleep", return_value=None
            ):
                results, errors = discover_skills_with_diagnostics("python packaging", cwd, source="huggingface", limit=5)

            self.assertEqual(results, [])
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ProviderSearchError)
            self.assertEqual(errors[0].source, "huggingface")
            self.assertEqual(errors[0].attempts, 3)
            self.assertEqual(errors[0].error_type, "network")
            telemetry = getattr(discover_skills_with_diagnostics, "_last_telemetry", [])
            self.assertEqual(len(telemetry), 1)
            self.assertEqual(telemetry[0]["provider"], "huggingface")
            self.assertEqual(telemetry[0]["status"], "error")
            self.assertEqual(telemetry[0]["attempts"], 3)
            self.assertEqual(telemetry[0]["error_type"], "network")
        finally:
            shutil.rmtree(cwd, ignore_errors=True)

    def test_huggingface_payload_errors_map_through_diagnostics(self):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("bad payload")
        provider = HuggingFaceProvider()

        cwd = Path.cwd() / ".tmp-tests" / "provider-retry-huggingface-payload"
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            with mock.patch(
                "skillsmith.commands.providers.build_provider_registry",
                return_value={"huggingface": provider},
            ), mock.patch("skillsmith.commands.providers.requests.get", return_value=response):
                results, errors = discover_skills_with_diagnostics("python packaging", cwd, source="huggingface", limit=5)

            self.assertEqual(results, [])
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ProviderSearchError)
            self.assertEqual(errors[0].source, "huggingface")
            self.assertEqual(errors[0].attempts, 1)
            self.assertEqual(errors[0].error_type, "payload")
            telemetry = getattr(discover_skills_with_diagnostics, "_last_telemetry", [])
            self.assertEqual(len(telemetry), 1)
            self.assertEqual(telemetry[0]["provider"], "huggingface")
            self.assertEqual(telemetry[0]["status"], "error")
            self.assertEqual(telemetry[0]["attempts"], 1)
            self.assertEqual(telemetry[0]["error_type"], "payload")
        finally:
            shutil.rmtree(cwd, ignore_errors=True)

    def test_github_topics_payload_errors_map_through_diagnostics(self):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("bad payload")
        provider = GitHubTopicsProvider()

        cwd = Path.cwd() / ".tmp-tests" / "provider-retry-github-topics-payload"
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            with mock.patch(
                "skillsmith.commands.providers.build_provider_registry",
                return_value={"github-topics": provider},
            ), mock.patch("skillsmith.commands.providers.requests.get", return_value=response):
                results, errors = discover_skills_with_diagnostics("python packaging", cwd, source="github-topics", limit=5)

            self.assertEqual(results, [])
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ProviderSearchError)
            self.assertEqual(errors[0].source, "github-topics")
            self.assertEqual(errors[0].attempts, 1)
            self.assertEqual(errors[0].error_type, "payload")
            telemetry = getattr(discover_skills_with_diagnostics, "_last_telemetry", [])
            self.assertEqual(len(telemetry), 1)
            self.assertEqual(telemetry[0]["provider"], "github-topics")
            self.assertEqual(telemetry[0]["status"], "error")
            self.assertEqual(telemetry[0]["attempts"], 1)
            self.assertEqual(telemetry[0]["error_type"], "payload")
        finally:
            shutil.rmtree(cwd, ignore_errors=True)

    def test_org_registry_payload_errors_map_through_diagnostics(self):
        with self.project_dir() as cwd:
            registry_dir = cwd / ".agent" / "registry"
            registry_dir.mkdir(parents=True, exist_ok=True)
            (registry_dir / "skills.json").write_text("{not json", encoding="utf-8")

            provider = OrgRegistryProvider()
            with mock.patch(
                "skillsmith.commands.providers.build_provider_registry",
                return_value={"org-registry": provider},
            ):
                results, errors = discover_skills_with_diagnostics("python packaging", cwd, source="org-registry", limit=5)

            self.assertEqual(results, [])
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ProviderSearchError)
            self.assertEqual(errors[0].source, "org-registry")
            self.assertEqual(errors[0].attempts, 1)
            self.assertEqual(errors[0].error_type, "payload")
            telemetry = getattr(discover_skills_with_diagnostics, "_last_telemetry", [])
            self.assertEqual(len(telemetry), 1)
            self.assertEqual(telemetry[0]["provider"], "org-registry")
            self.assertEqual(telemetry[0]["status"], "error")
            self.assertEqual(telemetry[0]["attempts"], 1)
            self.assertEqual(telemetry[0]["error_type"], "payload")


if __name__ == "__main__":
    unittest.main()

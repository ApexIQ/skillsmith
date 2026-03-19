from __future__ import annotations

import datetime
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import time
from typing import Protocol

import requests
import yaml

from . import load_catalog
from .lockfile import (
    _normalize_publisher_key_rotation,
    _normalize_publisher_keys,
    _normalize_publisher_public_keys,
    _publisher_signature_algorithms,
    _publisher_signature_mode,
    _publisher_signature_scheme_mode,
)

PROVIDER_SOURCE_ORDER = ["local", "skills.sh", "huggingface", "github-topics", "org-registry"]


def _tokenize(text: str) -> set[str]:
    return {token for token in re.sub(r"[^a-z0-9 ]", " ", text.lower()).split() if token}


def _safe_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _unique_text_values(*values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        for item in _safe_list(value):
            text = str(item).strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            result.append(text)
    return result


def _first_text(*values) -> str:
    items = _unique_text_values(*values)
    return items[0] if items else ""


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalized_text_set(value) -> set[str]:
    return {text.strip().lower() for text in _safe_list(value) if str(text).strip()}


def _normalized_license_token(value: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "", str(value).strip().lower())


def _normalized_tags(item: dict) -> list[str]:
    return _unique_text_values(item.get("tags"), item.get("topics"))


def _normalized_license(item: dict) -> str:
    return _first_text(
        item.get("license"),
        item.get("license_name"),
        item.get("spdx_license"),
        item.get("spdx_license_id"),
        item.get("license_type"),
    )


def _normalized_maintainer(item: dict) -> str:
    return _first_text(
        item.get("maintainer"),
        item.get("maintainers"),
        item.get("author"),
        item.get("authors"),
        item.get("owner"),
        item.get("organization"),
        item.get("org"),
        item.get("team"),
    )


def _metadata_timestamp_signal(metadata: dict) -> tuple[str, str]:
    freshness_source = str(metadata.get("freshness_source") or metadata.get("_freshness_source") or "").strip()
    if freshness_source:
        value = metadata.get(freshness_source)
        if value is not None:
            text = str(value).strip()
            if text:
                return text, freshness_source

    for key in (
        "updated_at",
        "updatedAt",
        "modified_at",
        "modifiedAt",
        "last_modified",
        "lastModified",
        "last_updated",
        "lastUpdated",
        "published_at",
        "publishedAt",
        "created_at",
        "createdAt",
    ):
        value = metadata.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text, key
    return "", ""


def _normalized_provider_metadata(item: dict) -> dict:
    normalized = dict(item)
    tags = _normalized_tags(item)
    if tags:
        normalized["tags"] = tags
        normalized.setdefault("topics", tags)

    license_value = _normalized_license(item)
    if license_value:
        normalized["license"] = license_value

    maintainer_value = _normalized_maintainer(item)
    if maintainer_value:
        normalized["maintainer"] = maintainer_value

    timestamp_value, timestamp_source = _metadata_timestamp_signal(item)
    if timestamp_value:
        normalized["updated_at"] = timestamp_value
        normalized["freshness_source"] = timestamp_source
        if timestamp_source.lower() in {"created_at", "createdat"} and not normalized.get("created_at"):
            normalized["created_at"] = timestamp_value

    return normalized


def _profile_terms(profile: dict | None = None) -> set[str]:
    profile = profile or {}
    values = []
    values.extend(_safe_list(profile.get("languages")))
    values.extend(_safe_list(profile.get("frameworks")))
    values.extend(_safe_list(profile.get("priorities")))
    values.extend(_safe_list(profile.get("target_tools")))
    values.extend(_safe_list(profile.get("build_commands")))
    values.extend(_safe_list(profile.get("test_commands")))
    values.extend(_safe_list(profile.get("trusted_skill_sources")))
    values.append(str(profile.get("app_type", "")))
    values.append(str(profile.get("deployment_target", "")))
    return _tokenize(" ".join(values))


def _candidate_terms(candidate: "SkillCandidate") -> set[str]:
    haystack = " ".join(
        [
            candidate.name,
            candidate.description,
            " ".join(candidate.tags),
            candidate.category,
            " ".join(candidate.compatibility),
            " ".join(f"{key} {value}" for key, value in candidate.metadata.items() if isinstance(value, str)),
        ]
    )
    return _tokenize(haystack)


def _profile_bonus(candidate: "SkillCandidate", profile: dict | None = None) -> int:
    profile = profile or {}
    candidate_tokens = _candidate_terms(candidate)
    bonus = 0

    app_type = str(profile.get("app_type", "")).lower()
    priorities = {item.lower() for item in _safe_list(profile.get("priorities"))}
    target_tools = {item.lower() for item in _safe_list(profile.get("target_tools"))}
    frameworks = {item.lower() for item in _safe_list(profile.get("frameworks"))}
    languages = {item.lower() for item in _safe_list(profile.get("languages"))}

    if app_type == "library" and {"package", "packaging", "publish", "release", "library"} & candidate_tokens:
        bonus += 45
    if app_type == "api-service" and {"api", "backend", "service"} & candidate_tokens:
        bonus += 35
    if app_type == "web-app" and {"frontend", "ui", "web", "browser"} & candidate_tokens:
        bonus += 35
    if app_type == "fullstack-app" and {"fullstack", "frontend", "backend", "web", "api"} & candidate_tokens:
        bonus += 45
    if app_type == "cli-tool" and {"cli", "terminal", "command"} & candidate_tokens:
        bonus += 35

    if "testability" in priorities and {"test", "testing", "pytest", "unit", "integration"} & candidate_tokens:
        bonus += 20
    if "verification" in priorities and {"review", "audit", "lint", "validation"} & candidate_tokens:
        bonus += 15
    if "automation" in priorities and {"workflow", "automation", "ci", "pipeline"} & candidate_tokens:
        bonus += 20
    if "speed" in priorities and {"performance", "shipping", "iteration", "delivery"} & candidate_tokens:
        bonus += 10

    if frameworks & candidate_tokens:
        bonus += len(frameworks & candidate_tokens) * 12
    if languages & candidate_tokens:
        bonus += len(languages & candidate_tokens) * 8
    if target_tools & candidate_tokens:
        bonus += len(target_tools & candidate_tokens) * 14
    if target_tools & {item.lower() for item in candidate.compatibility}:
        bonus += len(target_tools & {item.lower() for item in candidate.compatibility}) * 20

    return bonus


def curated_pack_label(profile: dict | None = None) -> str:
    profile = profile or {}
    app_type = str(profile.get("app_type", "project")).lower() or "project"
    framework_text = "-".join(item.lower() for item in _safe_list(profile.get("frameworks"))[:2])
    if framework_text:
        return f"{app_type}:{framework_text}"
    return app_type


def _source_reliability_bonus(candidate: "SkillCandidate") -> int:
    source = candidate.source.lower()
    bonus_map = {
        "local": 15,
        "skills.sh": 8,
        "huggingface": 7,
        "github-topics": 6,
        "org-registry": 12,
        "github": 5,
    }
    bonus = bonus_map.get(source, 0)
    if candidate.metadata.get("verified") or candidate.metadata.get("official"):
        bonus += 10
    return bonus


def _metadata_trust_bonus(candidate: "SkillCandidate") -> int:
    metadata = candidate.metadata or {}
    bonus = 0
    license_value = _normalized_license(metadata)
    if license_value:
        bonus += 2
        if license_value.lower() in {"mit", "apache-2.0", "apache 2.0", "bsd-3-clause", "bsd-2-clause", "isc", "unlicense", "mpl-2.0"}:
            bonus += 1

    maintainer_value = _normalized_maintainer(metadata)
    if maintainer_value:
        bonus += 2

    return bonus


def _metadata_freshness_score(metadata: dict) -> int:
    timestamp_value, _ = _metadata_timestamp_signal(metadata)
    return _freshness_from_timestamp(timestamp_value)


def _freshness_from_timestamp(value: str | None) -> int:
    if not value:
        return 0
    try:
        normalized = value.replace("Z", "+00:00")
        timestamp = datetime.datetime.fromisoformat(normalized)
        now = datetime.datetime.now(datetime.timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
        age_days = (now - timestamp).days
        if age_days <= 30:
            return 12
        if age_days <= 90:
            return 8
        if age_days <= 180:
            return 4
    except Exception:
        return 0
    return 0


def explain_candidate(candidate: "SkillCandidate", query: str, profile: dict | None = None) -> dict:
    profile = profile or {}
    query_tokens = _tokenize(query)
    candidate_tokens = _candidate_terms(candidate)
    matched_query = sorted(query_tokens & candidate_tokens)
    matched_profile = sorted(_profile_terms(profile) & candidate_tokens)
    source_bonus = _source_reliability_bonus(candidate)
    profile_bonus = _profile_bonus(candidate, profile)
    metadata_bonus = _metadata_trust_bonus(candidate)
    freshness_value, freshness_source = _metadata_timestamp_signal(candidate.metadata)
    license_value = _normalized_license(candidate.metadata)
    maintainer_value = _normalized_maintainer(candidate.metadata)

    reasons = []
    if candidate.metadata.get("starter_pack"):
        reasons.append(f"starter pack:{candidate.metadata.get('starter_pack_label', 'default')}")
    if matched_query:
        reasons.append(f"query:{', '.join(matched_query[:3])}")
    if matched_profile:
        reasons.append(f"profile:{', '.join(matched_profile[:3])}")
    if license_value:
        reasons.append(f"license:{license_value}")
    if maintainer_value:
        reasons.append(f"maintainer:{maintainer_value}")
    if candidate.compatibility:
        reasons.append(f"compat:{', '.join(candidate.compatibility[:2])}")
    if candidate.freshness_score:
        freshness_label = freshness_source or "metadata"
        reasons.append(f"freshness:{freshness_label}")
        reasons.append(f"freshness:+{candidate.freshness_score}")
    if source_bonus:
        reasons.append(f"source:+{source_bonus}")
    if profile_bonus:
        reasons.append(f"profile_bonus:+{profile_bonus}")
    if metadata_bonus:
        reasons.append(f"metadata_bonus:+{metadata_bonus}")
    if not reasons:
        reasons.append("general match")

    return {
        "reasons": reasons,
        "matched_query": matched_query,
        "matched_profile": matched_profile,
        "source_bonus": source_bonus,
        "profile_bonus": profile_bonus,
        "metadata_bonus": metadata_bonus,
        "freshness_source": freshness_source,
        "license": license_value,
        "maintainer": maintainer_value,
    }


@dataclass
class SkillCandidate:
    name: str
    description: str
    source: str
    version: str = "0.0.0"
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    install_ref: str = ""
    trust_score: int = 50
    popularity_score: int = 0
    freshness_score: int = 0
    compatibility: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class SkillProvider(Protocol):
    source_name: str

    def search(self, query: str, limit: int = 10) -> list[SkillCandidate]:
        ...


class DiscoveryError(Exception):
    """Base class for discovery-related failures."""


class UnknownProviderError(DiscoveryError):
    def __init__(self, source: str, available_sources: list[str]):
        self.source = source
        self.available_sources = available_sources
        options = ", ".join(available_sources)
        super().__init__(f"Unknown discovery source '{source}'. Available sources: {options}")


@dataclass
class ProviderSearchError(DiscoveryError):
    source: str
    message: str
    attempts: int = 1
    elapsed_ms: int = 0
    error_type: str = "unknown"

    def __str__(self) -> str:
        return (
            f"[{self.source}] {self.message} "
            f"(type={self.error_type}, attempts={self.attempts}, elapsed_ms={self.elapsed_ms})"
        )


def get_profile(cwd: Path) -> dict:
    profile_path = cwd / ".agent" / "project_profile.yaml"
    if not profile_path.exists():
        return {}
    return yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}


def candidate_install_url(candidate: SkillCandidate) -> str:
    possible_fields = [
        candidate.metadata.get("install_url"),
        candidate.metadata.get("github_url"),
        candidate.metadata.get("repo_url"),
        candidate.metadata.get("url"),
        candidate.install_ref,
    ]
    for value in possible_fields:
        if isinstance(value, str) and value.startswith("http"):
            return value
    return ""


def install_policy_for_profile(profile: dict | None = None) -> dict:
    profile = profile or {}
    allow_remote = bool(profile.get("allow_remote_skills", False))
    configured_sources = _safe_list(profile.get("trusted_skill_sources"))
    configured_domains = _safe_list(profile.get("allowed_remote_domains"))
    if configured_sources:
        allowed_sources = {source.strip().lower() for source in configured_sources if source}
    elif allow_remote:
        allowed_sources = set(PROVIDER_SOURCE_ORDER)
    else:
        allowed_sources = {"local"}

    blocked_sources = _normalized_text_set(profile.get("blocked_skill_sources"))
    allowed_domains = {item.strip().lower() for item in configured_domains if str(item).strip()}
    if not allowed_domains:
        allowed_domains = {"github.com", "skills.sh"}
    min_remote_trust = _safe_int(profile.get("min_remote_trust_score", 65), 65)
    min_remote_freshness = _safe_int(profile.get("min_remote_freshness_score", 0), 0)
    require_pinned_github_refs = bool(profile.get("require_pinned_github_refs", True))
    trusted_publisher_keys = _normalize_publisher_keys(profile.get("trusted_publisher_keys"))
    trusted_publisher_public_keys = _normalize_publisher_public_keys(profile.get("trusted_publisher_public_keys"))
    publisher_verification_mode = _publisher_signature_mode(profile.get("publisher_verification_mode"))
    publisher_signature_scheme_mode = _publisher_signature_scheme_mode(profile.get("publisher_signature_scheme_mode"))
    publisher_signature_algorithms = _publisher_signature_algorithms(profile.get("publisher_signature_algorithms"))
    publisher_key_rotation = _normalize_publisher_key_rotation(profile.get("publisher_key_rotation"))
    required_remote_licenses = {
        token
        for token in (_normalized_license_token(item) for item in _safe_list(profile.get("required_remote_licenses")))
        if token
    }
    return {
        "allow_remote_skills": allow_remote,
        "allowed_sources": allowed_sources,
        "allowed_remote_domains": allowed_domains,
        "blocked_skill_sources": blocked_sources,
        "min_remote_trust_score": min_remote_trust,
        "min_remote_freshness_score": min_remote_freshness,
        "require_pinned_github_refs": require_pinned_github_refs,
        "trusted_publisher_keys": trusted_publisher_keys,
        "trusted_publisher_key_ids": list(trusted_publisher_keys.keys()),
        "trusted_publisher_public_keys": trusted_publisher_public_keys,
        "trusted_publisher_public_key_ids": list(trusted_publisher_public_keys.keys()),
        "publisher_verification_mode": publisher_verification_mode,
        "publisher_signature_scheme_mode": publisher_signature_scheme_mode,
        "publisher_signature_algorithms": publisher_signature_algorithms,
        "publisher_key_rotation": publisher_key_rotation,
        "required_remote_licenses": required_remote_licenses,
    }


def candidate_allowed(candidate: SkillCandidate, profile: dict | None = None) -> tuple[bool, str]:
    policy = install_policy_for_profile(profile)
    source = candidate.source.lower()
    if source in {"local", "org-registry"}:
        return True, ""
    if source in policy["blocked_skill_sources"]:
        return False, f"source '{candidate.source}' is blocked by blocked_skill_sources"
    if not policy["allow_remote_skills"]:
        return False, "remote installs are disabled by .agent/project_profile.yaml"
    if source not in policy["allowed_sources"]:
        return False, f"source '{candidate.source}' is not in trusted_skill_sources"
    if candidate.trust_score < policy["min_remote_trust_score"]:
        return False, f"trust score {candidate.trust_score} is below min_remote_trust_score {policy['min_remote_trust_score']}"
    if candidate.freshness_score < policy["min_remote_freshness_score"]:
        return False, (
            f"freshness score {candidate.freshness_score} is below "
            f"min_remote_freshness_score {policy['min_remote_freshness_score']}"
        )
    required_licenses = policy["required_remote_licenses"]
    if required_licenses:
        license_value = _normalized_license(candidate.metadata)
        if _normalized_license_token(license_value) not in required_licenses:
            required_values = ", ".join(_safe_list(profile.get("required_remote_licenses")))
            return False, f"license '{license_value}' is not in required_remote_licenses [{required_values}]"
    return True, ""


def rank_candidates(candidates: list[SkillCandidate], query: str, profile: dict | None = None) -> list[SkillCandidate]:
    profile = profile or {}
    query_tokens = _tokenize(query)
    profile_tokens = _profile_terms(profile)

    def score(candidate: SkillCandidate) -> tuple[int, str]:
        tokens = _candidate_terms(candidate)
        query_score = len(query_tokens & tokens) * 30
        profile_score = len(profile_tokens & tokens) * 15
        recommendation_bonus = _profile_bonus(candidate, profile)
        source_score = candidate.trust_score + _source_reliability_bonus(candidate)
        metadata_bonus = _metadata_trust_bonus(candidate)
        popularity_score = candidate.popularity_score
        freshness_score = candidate.freshness_score
        total = query_score + profile_score + recommendation_bonus + source_score + metadata_bonus + popularity_score + freshness_score
        return total, candidate.name

    return sorted(candidates, key=score, reverse=True)


def _catalog_items() -> list[dict]:
    catalog = load_catalog()
    if not catalog:
        return []
    skills = catalog if isinstance(catalog, list) else catalog.get("skills", {}).values()
    return list(skills)


def _candidate_from_catalog_item(item: dict, source: str = "local", trust_score: int = 90) -> SkillCandidate:
    normalized = _normalized_provider_metadata(item)
    popularity_source = normalized.get("popularity_score", normalized.get("installs", 0))
    return SkillCandidate(
        name=str(normalized.get("name", "unknown")),
        description=str(normalized.get("description", "")),
        source=source,
        version=str(normalized.get("version", "0.0.0")),
        category=str(normalized.get("category", "general")),
        tags=_normalized_tags(normalized),
        install_ref=str(normalized.get("name", "")),
        trust_score=trust_score,
        popularity_score=min(_safe_int(popularity_source) // 10, 15),
        freshness_score=_metadata_freshness_score(normalized),
        compatibility=_safe_list(normalized.get("compatibility") or normalized.get("installed_on")),
        metadata=normalized,
    )


def _coerce_payload_items(payload, preferred_keys: tuple[str, ...] = ()) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in preferred_keys + ("skills", "items", "results", "spaces", "models", "datasets", "data", "hits"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _coerce_payload_items(value, preferred_keys=())
            if nested:
                return nested

    if any(key in payload for key in ("name", "id", "title", "repo_id", "modelId", "space_id")):
        return [payload]

    return []


def _flatten_owner_and_license(item: dict) -> dict:
    merged = dict(item)

    owner = merged.get("owner")
    if isinstance(owner, dict):
        owner_value = _first_text(owner.get("login"), owner.get("name"), owner.get("id"))
        if owner_value:
            merged["owner"] = owner_value
            merged.setdefault("maintainer", owner_value)

    license_value = merged.get("license")
    if isinstance(license_value, dict):
        merged["license"] = _first_text(license_value.get("spdx_id"), license_value.get("name"), license_value.get("key"))

    return merged


def curated_pack_names(profile: dict | None = None) -> list[str]:
    profile = profile or {}
    app_type = str(profile.get("app_type", "")).lower()
    frameworks = {item.lower() for item in _safe_list(profile.get("frameworks"))}
    languages = {item.lower() for item in _safe_list(profile.get("languages"))}
    package_manager = str(profile.get("package_manager", "")).lower()

    names = [
        "agentic_workflow",
        "software_architecture",
        "verification_before_completion",
    ]

    if app_type == "library":
        names.extend(["python_packaging", "python_testing_patterns", "test_driven_development"])
    if app_type == "api-service":
        names.extend(["api_design_principles", "backend-testing", "fastapi-best-practices"])
    if app_type == "web-app":
        names.extend(["react_best_practices", "frontend-testing", "web_design_guidelines"])
    if app_type == "fullstack-app":
        names.extend(["full_stack_orchestration_full_stack_feature", "nextjs_best_practices", "backend-testing", "frontend-testing"])
    if app_type == "cli-tool":
        names.extend(["bash_defensive_patterns", "uv_package_manager", "python_patterns"])

    if "python" in languages:
        names.extend(["python_patterns", "python_pro"])
    if "typescript" in languages:
        names.extend(["typescript_pro"])
    if "fastapi" in frameworks:
        names.extend(["fastapi-best-practices", "fastapi_pro"])
    if "next" in frameworks:
        names.extend(["nextjs_best_practices"])
    if "react" in frameworks:
        names.extend(["react_best_practices", "react_patterns"])
    if package_manager == "uv":
        names.append("uv_package_manager")

    deduped = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


def curated_pack_candidates(profile: dict | None = None, limit: int = 5) -> list[SkillCandidate]:
    items = _catalog_items()
    if not items:
        return []
    requested = curated_pack_names(profile)
    by_name = {str(item.get("name", "")): item for item in items}
    results = []
    pack_label = curated_pack_label(profile)
    for name in requested:
        item = by_name.get(name)
        if not item:
            continue
        candidate = _candidate_from_catalog_item(item, source="local", trust_score=95)
        candidate.metadata = {**candidate.metadata, "starter_pack": True, "starter_pack_label": pack_label}
        results.append(candidate)
        if len(results) >= limit:
            break
    return results


def merge_recommendations(primary: list[SkillCandidate], secondary: list[SkillCandidate], limit: int) -> list[SkillCandidate]:
    merged = []
    seen: set[tuple[str, str]] = set()
    for candidate in primary + secondary:
        key = (candidate.source, candidate.name)
        if key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
        if len(merged) >= limit:
            break
    return merged


class LocalCatalogProvider:
    source_name = "local"

    def search(self, query: str, limit: int = 10) -> list[SkillCandidate]:
        catalog = load_catalog()
        if not catalog:
            return []
        skills = catalog if isinstance(catalog, list) else catalog.get("skills", {}).values()
        query_tokens = _tokenize(query)
        candidates: list[SkillCandidate] = []
        for item in skills:
            normalized = _normalized_provider_metadata(item)
            text = " ".join(
                [
                    str(normalized.get("name", "")),
                    str(normalized.get("description", "")),
                    " ".join(_normalized_tags(normalized)),
                    str(normalized.get("category", "")),
                ]
            )
            if query_tokens and not (_tokenize(text) & query_tokens):
                continue
            candidates.append(
                _candidate_from_catalog_item(
                    {**item, "source": item.get("source", "bundled")},
                    source="local",
                    trust_score=90,
                )
            )
        return candidates[:limit]


class SkillsShProvider:
    source_name = "skills.sh"
    api_url = "https://skills.sh/api/skills"

    def search(self, query: str, limit: int = 10) -> list[SkillCandidate]:
        response = requests.get(self.api_url, params={"q": query, "limit": limit}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        items = _coerce_payload_items(payload, ("skills",))
        candidates: list[SkillCandidate] = []
        for item in items[:limit]:
            normalized = _normalized_provider_metadata(item)
            owner = str(item.get("owner", item.get("org", "")))
            repo = str(item.get("repo", item.get("repository", "")))
            skill_name = str(normalized.get("skill", normalized.get("name", "unknown")))
            install_ref = normalized.get("install_ref") or normalized.get("install") or f"{owner}/{repo}@{skill_name}".strip("@")
            freshness_value = _metadata_freshness_score(normalized)
            popularity_source = normalized.get("weekly_installs", normalized.get("installs", normalized.get("popularity_score", 0)))
            try:
                popularity_score = min(int(popularity_source) // 10, 15)
            except (TypeError, ValueError):
                popularity_score = 0
            candidates.append(
                SkillCandidate(
                    name=skill_name,
                    description=str(normalized.get("description", "")),
                    source="skills.sh",
                    version=str(normalized.get("version", "0.0.0")),
                    category=str(normalized.get("category", "general")),
                    tags=_normalized_tags(normalized),
                    install_ref=str(install_ref),
                    trust_score=70,
                    popularity_score=popularity_score,
                    freshness_score=freshness_value,
                    compatibility=_safe_list(normalized.get("installed_on")),
                    metadata=normalized,
                )
            )
        return candidates


class HuggingFaceProvider:
    source_name = "huggingface"
    api_url = "https://huggingface.co/api/spaces"

    def search(self, query: str, limit: int = 10) -> list[SkillCandidate]:
        response = requests.get(
            self.api_url,
            params={"search": query, "limit": limit, "full": 1},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        items = _coerce_payload_items(payload, ("spaces", "items", "results", "hits", "data"))
        candidates: list[SkillCandidate] = []
        for item in items[:limit]:
            merged = dict(item)
            card_data = item.get("cardData")
            if isinstance(card_data, dict):
                for key, value in card_data.items():
                    merged.setdefault(key, value)
            normalized = _normalized_provider_metadata(merged)
            repo_id = _first_text(
                normalized.get("id"),
                normalized.get("repo_id"),
                normalized.get("repoId"),
                normalized.get("space_id"),
                normalized.get("name"),
                normalized.get("title"),
            )
            description = _first_text(
                normalized.get("description"),
                normalized.get("summary"),
                normalized.get("card_description"),
                normalized.get("short_description"),
            )
            category = _first_text(
                normalized.get("pipeline_tag"),
                normalized.get("space_sdk"),
                normalized.get("sdk"),
                normalized.get("library_name"),
                normalized.get("type"),
            ) or "space"
            popularity_source = normalized.get("likes", normalized.get("downloads", normalized.get("popularity_score", 0)))
            candidates.append(
                SkillCandidate(
                    name=repo_id or _first_text(normalized.get("title"), normalized.get("name"), normalized.get("id")),
                    description=description,
                    source="huggingface",
                    version=str(normalized.get("sha", normalized.get("lastModified", normalized.get("createdAt", "0.0.0")))),
                    category=category,
                    tags=_normalized_tags(normalized),
                    install_ref=repo_id or _first_text(normalized.get("title"), normalized.get("name")),
                    trust_score=68,
                    popularity_score=min(_safe_int(popularity_source) // 10, 15),
                    freshness_score=_metadata_freshness_score(normalized),
                    compatibility=_safe_list(normalized.get("sdk") or normalized.get("space_sdk") or normalized.get("library_name")),
                    metadata=normalized,
                )
            )
        return candidates


class GitHubTopicsProvider:
    source_name = "github-topics"
    api_url = "https://api.github.com/search/repositories"

    def search(self, query: str, limit: int = 10) -> list[SkillCandidate]:
        github_query = " ".join(part for part in [query.strip(), "topic:skills"] if part).strip() or "topic:skills"
        response = requests.get(
            self.api_url,
            params={"q": github_query, "per_page": limit, "sort": "stars", "order": "desc"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        items = _coerce_payload_items(payload, ("items",))
        candidates: list[SkillCandidate] = []
        for item in items[:limit]:
            merged = _flatten_owner_and_license(item)
            html_url = _first_text(merged.get("html_url"), merged.get("url"), merged.get("homepage"))
            if html_url:
                merged.setdefault("url", html_url)
                merged.setdefault("github_url", html_url)
            normalized = _normalized_provider_metadata(merged)
            name = _first_text(
                normalized.get("full_name"),
                normalized.get("name"),
                normalized.get("repo_id"),
                normalized.get("id"),
            )
            description = _first_text(normalized.get("description"), normalized.get("summary"))
            category = _first_text(normalized.get("language"), normalized.get("topic")) or "repository"
            stars = normalized.get("stargazers_count", normalized.get("stars", normalized.get("watchers_count", 0)))
            candidates.append(
                SkillCandidate(
                    name=name or _first_text(normalized.get("html_url"), normalized.get("url")),
                    description=description,
                    source="github-topics",
                    version=str(normalized.get("sha", normalized.get("updated_at", "0.0.0"))),
                    category=category,
                    tags=_normalized_tags(normalized),
                    install_ref=html_url or _first_text(normalized.get("full_name"), normalized.get("name")),
                    trust_score=72,
                    popularity_score=min(_safe_int(stars) // 10, 15),
                    freshness_score=_metadata_freshness_score(normalized),
                    compatibility=_safe_list(normalized.get("language")),
                    metadata=normalized,
                )
            )
        return candidates


class OrgRegistryProvider:
    source_name = "org-registry"

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else Path.cwd()

    @property
    def registry_path(self) -> Path:
        return self.root / ".agent" / "registry" / "skills.json"

    def search(self, query: str, limit: int = 10) -> list[SkillCandidate]:
        registry_path = self.registry_path
        if not registry_path.exists():
            return []

        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid org registry payload: {exc}") from exc

        items = _coerce_payload_items(payload, ("skills", "items", "results"))
        query_tokens = _tokenize(query)
        candidates: list[SkillCandidate] = []
        for item in items:
            merged = _flatten_owner_and_license(item)
            normalized = _normalized_provider_metadata(merged)
            text = " ".join(
                [
                    str(normalized.get("name", "")),
                    str(normalized.get("description", "")),
                    " ".join(_normalized_tags(normalized)),
                    str(normalized.get("category", "")),
                ]
            )
            if query_tokens and not (_tokenize(text) & query_tokens):
                continue

            name = _first_text(
                normalized.get("name"),
                normalized.get("title"),
                normalized.get("slug"),
                normalized.get("skill"),
                normalized.get("id"),
            )
            install_ref = _first_text(
                normalized.get("install_url"),
                normalized.get("github_url"),
                normalized.get("url"),
                normalized.get("repo_url"),
                normalized.get("path"),
                normalized.get("name"),
            )
            popularity_source = normalized.get("installs", normalized.get("popularity_score", normalized.get("downloads", 0)))
            candidates.append(
                SkillCandidate(
                    name=name or "unknown",
                    description=_first_text(normalized.get("description"), normalized.get("summary"), normalized.get("notes")),
                    source="org-registry",
                    version=str(normalized.get("version", normalized.get("updated_at", "0.0.0"))),
                    category=_first_text(normalized.get("category"), normalized.get("team"), normalized.get("namespace")) or "registry",
                    tags=_normalized_tags(normalized),
                    install_ref=install_ref,
                    trust_score=_safe_int(normalized.get("trust_score"), 84),
                    popularity_score=min(_safe_int(popularity_source) // 10, 15),
                    freshness_score=_metadata_freshness_score(normalized),
                    compatibility=_safe_list(normalized.get("installed_on") or normalized.get("compatibility") or normalized.get("target_tools")),
                    metadata=normalized,
                )
            )
            if len(candidates) >= limit:
                break
        return candidates


def build_provider_registry(root: Path | None = None) -> dict[str, SkillProvider]:
    return {
        "local": LocalCatalogProvider(),
        "skills.sh": SkillsShProvider(),
        "huggingface": HuggingFaceProvider(),
        "github-topics": GitHubTopicsProvider(),
        "org-registry": OrgRegistryProvider(root),
    }


def _resolve_providers(source: str, providers: dict[str, SkillProvider]) -> list[SkillProvider]:
    if source == "all":
        return list(providers.values())
    provider = providers.get(source)
    if provider is None:
        raise UnknownProviderError(source, sorted(providers.keys()))
    return [provider]


def discover_skills_with_diagnostics(
    query: str,
    cwd: Path,
    source: str = "all",
    limit: int = 10,
) -> tuple[list[SkillCandidate], list[ProviderSearchError]]:
    max_attempts = 3
    base_backoff_seconds = 0.05
    providers = build_provider_registry(cwd)
    profile = get_profile(cwd)
    selected = _resolve_providers(source, providers)
    candidates: list[SkillCandidate] = []
    errors: list[ProviderSearchError] = []
    telemetry: list[dict] = []
    for provider in selected:
        start = time.perf_counter()
        attempts = 0
        last_exception: Exception | None = None
        success = False
        error_type = ""
        while attempts < max_attempts:
            attempts += 1
            try:
                results = provider.search(query, limit=limit)
                candidates.extend(results)
                success = True
                break
            except requests.RequestException as exc:
                last_exception = exc
                error_type = "network"
                if attempts < max_attempts:
                    time.sleep(base_backoff_seconds * (2 ** (attempts - 1)))
                    continue
            except ValueError as exc:
                last_exception = exc
                error_type = "payload"
                break
            except Exception as exc:
                last_exception = exc
                error_type = "unexpected"
                break

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        telemetry.append(
            {
                "provider": provider.source_name,
                "status": "ok" if success else "error",
                "attempts": attempts,
                "elapsed_ms": elapsed_ms,
                "error_type": error_type,
            }
        )
        if success:
            continue

        assert last_exception is not None
        if error_type == "network":
            errors.append(
                ProviderSearchError(
                    provider.source_name,
                    f"network error: {last_exception}",
                    attempts=attempts,
                    elapsed_ms=elapsed_ms,
                    error_type=error_type,
                )
            )
        elif error_type == "payload":
            errors.append(
                ProviderSearchError(
                    provider.source_name,
                    f"invalid provider payload: {last_exception}",
                    attempts=attempts,
                    elapsed_ms=elapsed_ms,
                    error_type=error_type,
                )
            )
        else:
            errors.append(
                ProviderSearchError(
                    provider.source_name,
                    f"unexpected provider error: {last_exception}",
                    attempts=attempts,
                    elapsed_ms=elapsed_ms,
                    error_type=error_type or "unexpected",
                )
            )
    ranked = rank_candidates(candidates, query, profile)
    telemetry_path = cwd / ".agent" / "evals" / "provider_telemetry.jsonl"
    telemetry_path.parent.mkdir(parents=True, exist_ok=True)
    with telemetry_path.open("a", encoding="utf-8") as handle:
        for item in telemetry:
            line = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                **item,
            }
            handle.write(json.dumps(line, ensure_ascii=True) + "\n")
    setattr(discover_skills_with_diagnostics, "_last_telemetry", telemetry)
    return ranked[:limit], errors


def discover_skills(query: str, cwd: Path, source: str = "all", limit: int = 10) -> list[SkillCandidate]:
    results, _ = discover_skills_with_diagnostics(query, cwd, source=source, limit=limit)
    return results


def recommend_skills_for_profile(profile: dict, cwd: Path, limit: int = 5) -> list[SkillCandidate]:
    source = "all" if profile.get("allow_remote_skills") else "local"
    query_parts = []
    query_parts.extend(_safe_list(profile.get("app_type")))
    query_parts.extend(_safe_list(profile.get("languages")))
    query_parts.extend(_safe_list(profile.get("frameworks")))
    query_parts.extend(_safe_list(profile.get("priorities")))
    query_parts.extend(_safe_list(profile.get("target_tools")))
    query_parts.extend(_safe_list(profile.get("build_commands")))
    query_parts.extend(_safe_list(profile.get("test_commands")))
    query = " ".join(part for part in query_parts if part and part != "unknown")
    if not query.strip():
        query = str(profile.get("app_type", "project"))
    curated = curated_pack_candidates(profile, limit=limit)
    discovered = discover_skills(query, cwd, source=source, limit=limit)
    ranked_curated = rank_candidates(curated, query, profile)
    ranked_discovered = rank_candidates(discovered, query, profile)
    return merge_recommendations(ranked_curated, ranked_discovered, limit=limit)


def explain_recommendations_for_profile(profile: dict, cwd: Path, limit: int = 5) -> list[tuple[SkillCandidate, dict]]:
    recommendations = recommend_skills_for_profile(profile, cwd, limit=limit)
    query_parts = []
    query_parts.extend(_safe_list(profile.get("app_type")))
    query_parts.extend(_safe_list(profile.get("languages")))
    query_parts.extend(_safe_list(profile.get("frameworks")))
    query_parts.extend(_safe_list(profile.get("priorities")))
    query_parts.extend(_safe_list(profile.get("target_tools")))
    query_parts.extend(_safe_list(profile.get("build_commands")))
    query_parts.extend(_safe_list(profile.get("test_commands")))
    query = " ".join(part for part in query_parts if part and part != "unknown") or str(profile.get("app_type", "project"))
    return [(candidate, explain_candidate(candidate, query, profile)) for candidate in recommendations]

"""Política de acesso do broker (ACL): privilégio mínimo, verificado como código.

O arquivo infra/mosquitto/acl é a política real do Mosquitto. Estes testes o leem e conferem,
tópico a tópico, quem pode ler e quem pode escrever, inclusive tudo o que NÃO pode.
"""

from pathlib import Path

import pytest

MOSQUITTO = Path(__file__).resolve().parents[2] / "infra" / "mosquitto"
DEVICES = ["cam-sim-01", "act-sim-01"]
ROLES = ["backend", "camera", "actuator"]
SUFFIXES = [
    "detections",
    "status",
    "commands",
    "actuator/state",
    "actuator/events",
    "actuator/other",
    "actuator",
    "other",
]
CAN_READ = {
    "backend": ["detections", "status", "actuator/state", "actuator/events"],
    "camera": [],
    "actuator": ["commands"],
}
CAN_WRITE = {
    "backend": ["commands"],
    "camera": ["detections", "status"],
    "actuator": ["actuator/state", "actuator/events"],
}
WILDCARD_AND_FOREIGN_TOPICS = [
    "#",
    "+/#",
    "pigeondome/#",
    "pigeondome/v1/#",
    "pigeondome/v1/+/#",
    "pigeondome/v1/+/+",
    "pigeondome/v2/cam-sim-01/detections",
    "$SYS/broker/uptime",
    "other/topic",
]

Rule = tuple[str, str]  # (nível de acesso, padrão de tópico)


def parse_acl(text: str) -> dict[str, list[Rule]]:
    rules: dict[str, list[Rule]] = {}
    user: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        keyword, _, rest = line.partition(" ")
        if keyword == "user":
            user = rest.strip()
            rules.setdefault(user, [])
        elif keyword == "topic" and user is not None:
            access, _, pattern = rest.strip().partition(" ")
            if access not in ("read", "write", "readwrite"):
                raise ValueError(f"regra sem nível de acesso explícito no ACL: {line!r}")
            rules[user].append((access, pattern.strip()))
        else:
            raise ValueError(f"linha inesperada no ACL: {line!r}")
    return rules


def topic_matches(pattern: str, topic: str) -> bool:
    pattern_levels = pattern.split("/")
    topic_levels = topic.split("/")
    for index, level in enumerate(pattern_levels):
        if level == "#":
            return True
        if index >= len(topic_levels):
            return False
        if level != "+" and level != topic_levels[index]:
            return False
    return len(pattern_levels) == len(topic_levels)


def allows(acl: dict[str, list[Rule]], user: str, access: str, topic: str) -> bool:
    return any(
        granted in (access, "readwrite") and topic_matches(pattern, topic)
        for granted, pattern in acl.get(user, [])
    )


@pytest.fixture(scope="module")
def acl() -> dict[str, list[Rule]]:
    return parse_acl((MOSQUITTO / "acl").read_text("utf-8"))


@pytest.mark.parametrize("access", ["read", "write"])
@pytest.mark.parametrize("role", ROLES)
def test_each_role_has_exactly_the_permissions_it_needs(
    acl: dict[str, list[Rule]], role: str, access: str
) -> None:
    allowed = CAN_READ[role] if access == "read" else CAN_WRITE[role]
    for device in DEVICES:
        for suffix in SUFFIXES:
            topic = f"pigeondome/v1/{device}/{suffix}"
            expected = suffix in allowed
            assert allows(acl, role, access, topic) == expected, f"{role} {access} {topic}"


def test_no_role_can_touch_wildcards_other_versions_or_foreign_topics(
    acl: dict[str, list[Rule]],
) -> None:
    for role in ROLES:
        for access in ("read", "write"):
            for topic in WILDCARD_AND_FOREIGN_TOPICS:
                assert not allows(acl, role, access, topic), f"{role} {access} {topic}"


def test_rules_stay_in_the_project_namespace_without_wildcards_or_readwrite(
    acl: dict[str, list[Rule]],
) -> None:
    for role, rules in acl.items():
        assert rules, f"{role} sem regras"
        for access, pattern in rules:
            assert access in ("read", "write"), f"{role}: {access} {pattern}"
            assert pattern.startswith("pigeondome/v1/+/"), f"{role}: {pattern}"
            assert "#" not in pattern, f"{role}: {pattern}"


def test_only_the_three_known_roles_exist(acl: dict[str, list[Rule]]) -> None:
    assert set(acl) == set(ROLES)


def test_unknown_users_have_no_access(acl: dict[str, list[Rule]]) -> None:
    for access in ("read", "write"):
        assert not allows(acl, "intruder", access, "pigeondome/v1/cam-sim-01/detections")


def test_broker_config_requires_authentication_and_loads_the_acl() -> None:
    text = (MOSQUITTO / "mosquitto.conf").read_text("utf-8")
    lines = {line.strip() for line in text.splitlines()}
    assert "allow_anonymous false" in lines
    assert "acl_file /mosquitto/config/acl" in lines
    assert "password_file /mosquitto/config/passwd" in lines


@pytest.mark.parametrize(
    "text",
    ["topic read a/b", "user x\ntopic a/b", "user x\nfoo bar"],
    ids=["topic_without_user", "topic_without_access_level", "unknown_keyword"],
)
def test_parser_rejects_ambiguous_or_unexpected_lines(text: str) -> None:
    with pytest.raises(ValueError, match="ACL"):
        parse_acl(text)


def test_topic_matching_follows_the_mqtt_rules() -> None:
    assert topic_matches("a/+/c", "a/b/c")
    assert not topic_matches("a/+/c", "a/b/c/d")
    assert not topic_matches("a/+/c", "a/b")
    assert topic_matches("a/#", "a/b/c")
    assert not topic_matches("a/b", "a/c")

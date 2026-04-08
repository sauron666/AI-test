"""Smoke tests — make sure the package imports and core wiring works."""
from __future__ import annotations


def test_import_main():
    from backend import main  # noqa: F401


def test_settings_load():
    from backend.settings import get_settings
    s = get_settings()
    assert s.sauron_port > 0
    assert s.executor_workdir


def test_kali_catalog_loads():
    from backend.tools.kali_catalog import get_catalog
    cat = get_catalog()
    tools = cat.all()
    assert len(tools) > 20  # we ship dozens of tools out of the box
    names = {t.name for t in tools}
    for must in {"nmap", "nuclei", "sqlmap", "ffuf", "kerbrute"}:
        assert must in names, f"missing core tool: {must}"


def test_pentest_profiles_load():
    from backend.pentest.registry import list_playbooks
    pbs = list_playbooks()
    keys = {p.key for p in pbs}
    for must in {"web_application", "api", "mobile", "infrastructure",
                 "network", "active_directory", "llm_ai", "red_team"}:
        assert must in keys


def test_banned_command_filter():
    from backend.utils.security import is_command_banned
    assert is_command_banned("rm -rf /")
    assert is_command_banned("dd if=/dev/zero of=/dev/sda")
    assert not is_command_banned("nmap -sV 10.0.0.1")


def test_llm_router_does_not_crash():
    from backend.llm.router import get_router
    r = get_router()
    # `available_providers` should never raise even with no keys.
    assert isinstance(r.available_providers(), list)

import json
import shutil
from pathlib import Path

import pytest

from careerloop import cli
from careerloop import home as H

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo"

WEB = """name = "web"
[categories]
protocols = ["http", "https", "http/2", "tls", "dns", "websockets"]
api = ["rest", "json", "graphql", "openapi"]
security = ["oauth", "cors", "csrf", "rate limiting"]
ops = ["caching", "cdn", "load balancing", "observability", "docker"]
data = ["sql", "postgresql"]
"""


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    monkeypatch.setenv("CAREERLOOP_TODAY", "2030-03-20")
    monkeypatch.delenv("CAREERLOOP_HOME", raising=False)


@pytest.fixture
def home(tmp_path):
    """A minimal initialised HOME with the web pack and an empty facts sheet."""
    h = tmp_path / "home"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text("## Held\n")
    return h


@pytest.fixture
def cfg(home):
    return H.load_config(home)


@pytest.fixture
def demo(tmp_path):
    h = tmp_path / "demo"
    shutil.copytree(DEMO, h)
    return h


def run(h, *argv, capsys=None):
    code = cli.main(["--home", str(h), *argv])
    out = capsys.readouterr() if capsys else None
    return code, out


def rows(h, topic):
    p = Path(h) / "topics" / topic / "log.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

import importlib.util
from pathlib import Path

CONF = Path(__file__).resolve().parents[1] / "gunicorn.conf.py"


def load_conf():
    spec = importlib.util.spec_from_file_location("gunicorn_conf", CONF)
    conf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conf)
    return conf


def test_django_boots_once(monkeypatch):
    # a free instance has a tenth of a core and Django takes ~14 s to boot on it
    monkeypatch.setenv("PORT", "9123")
    conf = load_conf()
    assert conf.preload_app is True
    assert conf.workers == 1
    assert conf.bind == "0.0.0.0:9123"


def test_prepares_the_database_then_closes_it_before_forking(monkeypatch):
    conf = load_conf()
    calls = []
    monkeypatch.setattr(conf, "call_command", lambda name: calls.append(name))
    monkeypatch.setattr(conf.connections, "close_all", lambda: calls.append("close_all"))
    conf.on_starting(server=None)
    # a connection opened in the master would be shared by the forked worker
    assert calls == ["prepare_db", "close_all"]

"""A listening port is insufficient evidence that an owned capture child started."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def capture_module(monkeypatch):
    root = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "capture_review_demo", root / "scripts/capture_review_demo.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readiness_refuses_exited_child_before_contacting_other_listener(monkeypatch):
    module = capture_module(monkeypatch)
    monkeypatch.setattr(
        module,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("Exited child cannot own a listener"),
    )
    with pytest.raises(RuntimeError, match="exited"):
        module.ready("http://unused", SimpleNamespace(poll=lambda: 1), "our-instance")


@pytest.mark.parametrize(
    "response_nonce,accept", [("other-instance", False), ("our-instance", True)]
)
def test_readiness_requires_this_capture_instance(monkeypatch, response_nonce, accept):
    module = capture_module(monkeypatch)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return ('{"capture_instance":"' + response_nonce + '"}').encode()

    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: Response())
    child = SimpleNamespace(poll=lambda: None)
    if accept:
        module.ready("http://unused", child, "our-instance")
    else:
        with pytest.raises(ValueError, match="instance"):
            module.ready("http://unused", child, "our-instance")


def test_https_readiness_checks_owned_nonce_and_tls_context(monkeypatch):
    import ssl

    module = capture_module(monkeypatch)
    received = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self):
            return b'{"capture_instance":"ours"}'

    def response(_url, **kwargs):
        received.append(kwargs["context"])
        return Response()

    monkeypatch.setattr(module, "urlopen", response)
    context = ssl._create_unverified_context()
    module.ready(
        "https://127.0.0.1:8443/capture_identity",
        SimpleNamespace(poll=lambda: None),
        "ours",
        context=context,
    )
    assert received == [context]


def test_live_capture_identity_is_served_before_the_flutter_static_mount(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    root = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "serve_live_capture", root / "scripts/serve_live_flutter_capture.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("Static app index")
    app = module.capture_app(tmp_path / "intake", web, "owned-capture")
    with TestClient(app) as client:
        response = client.get("/capture_identity")
        assert response.status_code == 200
        assert response.json() == {"capture_instance": "owned-capture"}
        assert client.get("/").text == "Static app index"

"""REST publication is append-only, serialized, and reconciles ambiguous outcomes."""

import hashlib

import httpx
import pytest
from test_annotation_samples import canonical_batch as canonical_batch
from test_publication_package import exported, manifest_sha

from weedz.batches.package import validate_package
from weedz.batches.publication import publish


class Service:
    def __init__(self):
        self.tasks = {}
        self.predictions = {}
        self.requests = []
        self.imported = []
        self.timeout_import = False
        self.accept_import = True
        self.timeout_prediction = False
        self.annotations = {"human": [{"value": "untouched"}]}

    def index(self):
        return self.tasks.copy()

    def handle(self, request):
        import json

        self.requests.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path.endswith("/import"):
            rows = json.loads(request.content)
            self.imported.extend(rows)
            if self.accept_import:
                for row in rows:
                    key = row["meta"]["external_id"]
                    self.tasks[key] = {"id": len(self.tasks) + 1, "data": row["data"]}
                    self.predictions[self.tasks[key]["id"]] = row.get("predictions", [])
            if self.timeout_import:
                raise httpx.ReadTimeout("Ambiguous response", request=request)
            return httpx.Response(201, json={"task_ids": [v["id"] for v in self.tasks.values()]})
        if request.method == "POST" and request.url.path.endswith("/import/predictions"):
            return self.append_predictions(request)
        if request.method == "GET" and request.url.path.startswith("/api/tasks/"):
            task_id = int(request.url.path.strip("/").split("/")[-1])
            return httpx.Response(200, json={"predictions": self.predictions[task_id]})
        pytest.fail(f"Unexpected request: {request.method} {request.url.path}")

    def append_predictions(self, request):
        import json

        for row in json.loads(request.content):
            self.predictions[row["task"]].append(
                {
                    "model_version": row["model_version"],
                    "result": row["result"],
                }
            )
        if self.timeout_prediction:
            raise httpx.ReadTimeout("Ambiguous prediction response", request=request)
        return httpx.Response(201, json={"created": 1})


def run(service, package, tmp_path, heartbeat=lambda: None):
    with httpx.Client(
        base_url="http://127.0.0.1:8068", transport=httpx.MockTransport(service.handle)
    ) as client:
        return publish(
            package,
            1,
            client,
            service.index,
            tmp_path / "images",
            tmp_path / "state",
            tmp_path / "import.lock",
            heartbeat=heartbeat,
        )


def test_repeated_publication_creates_no_duplicate_tasks_or_human_writes(canonical_batch, tmp_path):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    service = Service()
    first = run(service, package, tmp_path)
    assert first["tasks"] == 1
    run(service, package, tmp_path)
    assert sum(method == "POST" for method, _ in service.requests) == 1
    assert service.annotations == {"human": [{"value": "untouched"}]}
    image = next((tmp_path / "images").rglob("*.png"))
    assert hashlib.sha256(image.read_bytes()).hexdigest() == image.stem


def test_accepted_import_timeout_reconciles_without_a_second_post(canonical_batch, tmp_path):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    service = Service()
    service.timeout_import = True
    run(service, package, tmp_path)
    run(service, package, tmp_path)
    assert sum(method == "POST" for method, _ in service.requests) == 1


def test_unresolved_import_timeout_never_blindly_resubmits(canonical_batch, tmp_path):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    service = Service()
    service.timeout_import, service.accept_import = True, False
    with pytest.raises(RuntimeError, match="uncertain"):
        run(service, package, tmp_path)
    with pytest.raises(RuntimeError, match="uncertain"):
        run(service, package, tmp_path)
    assert sum(method == "POST" for method, _ in service.requests) == 1


def test_mutated_in_memory_task_cannot_write_annotations(canonical_batch, tmp_path):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    package.tasks[0]["annotations"] = [{"result": []}]
    service = Service()
    run(service, package, tmp_path)
    assert all("annotations" not in task for task in service.imported)


def test_missing_prediction_uses_bulk_endpoint_and_reconciles_timeout(canonical_batch, tmp_path):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    service = Service()
    run(service, package, tmp_path)
    service.predictions[1] = []
    service.timeout_prediction = True
    run(service, package, tmp_path)
    run(service, package, tmp_path)
    assert service.requests.count(("POST", "/api/projects/1/import/predictions")) == 1
    assert len(service.tasks) == 1 and len(service.predictions[1]) == 1
    assert service.annotations == {"human": [{"value": "untouched"}]}


def test_same_version_conflict_never_changes_existing_results(canonical_batch, tmp_path):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    service = Service()
    run(service, package, tmp_path)
    service.predictions[1][0]["result"] = [{"type": "human-independent-old-result"}]
    before = len(service.requests)
    with pytest.raises(ValueError, match="conflicting"):
        run(service, package, tmp_path)
    assert all(method == "GET" for method, _ in service.requests[before:])
    assert service.predictions[1][0]["result"] == [{"type": "human-independent-old-result"}]


def test_publication_heartbeats_between_task_reads_and_reconciliation(canonical_batch, tmp_path):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    service = Service()
    run(service, package, tmp_path)
    service.predictions[1] = []
    pulses, observed = [], []
    original = service.handle

    def handle(request):
        if request.method == "GET":
            observed.append(len(pulses))
        return original(request)

    service.handle = handle
    run(service, package, tmp_path, heartbeat=lambda: pulses.append(1))
    assert len(observed) >= 3
    assert len(set(observed)) == len(observed)
    assert min(observed) >= 5  # Package files/tasks have already pulsed before REST reconciliation.


def test_existing_image_is_resealed_before_any_rest_write(canonical_batch, tmp_path, monkeypatch):
    import weedz.batches.publication as publication

    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    destination = tmp_path / "images"
    for name, reference in package.images.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((package.root / reference["path"]).read_bytes())
    service = Service()

    def interrupted_barrier(path):
        raise OSError("Interrupted image directory barrier")

    monkeypatch.setattr(publication, "sync_directory", interrupted_barrier)
    with pytest.raises(OSError, match="directory barrier"):
        run(service, package, tmp_path)
    assert service.requests == []


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ConnectTimeout])
def test_definite_connection_failure_releases_only_its_new_intents(
    canonical_batch, tmp_path, failure
):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    service = Service()
    original = service.handle

    def offline(request):
        if request.method == "POST":
            raise failure("No connection established", request=request)
        return original(request)

    service.handle = offline
    with pytest.raises(failure):
        run(service, package, tmp_path)
    service.handle = original
    run(service, package, tmp_path)
    assert len(service.tasks) == 1

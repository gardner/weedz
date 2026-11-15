"""Run explicit canonical batch task queues against the existing Temporal service."""

import argparse
import asyncio
import hashlib
import json
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.worker import Worker

from weedz.batches.activities import BatchActivities
from weedz.batches.contract import batch_request
from weedz.batches.publisher_runtime import publisher_from_config
from weedz.batches.receipts import write_receipt
from weedz.batches.runtime import prepare_config, registry_from_config
from weedz.batches.workflow import (
    CLASSIFICATION,
    CONTROL,
    PUBLICATION,
    SEGMENTATION,
    BatchAnnotationWorkflow,
)
from weedz.segmentation.sam3_image import Sam3Config

ROLES = {
    "publication": (PUBLICATION, ("batch_publish_v1",)),
    "control": (CONTROL, ("batch_validate_v1", "batch_package_v1")),
    "segmentation": (SEGMENTATION, ("batch_segment_v1",)),
    "classification": (
        CLASSIFICATION,
        ("batch_classify_frame_v1", "batch_classify_tiles_v1", "batch_classify_regions_v1"),
    ),
}


async def worker(args, config):
    selected = args.roles.split(",")
    if not selected or any(role not in ROLES for role in selected):
        raise ValueError(
            "Choose explicit control, segmentation, classification or publication roles"
        )
    client = await Client.connect(args.address, namespace=args.namespace)
    publisher = None
    if "publication" in selected:
        if args.publication_config is None:
            raise ValueError("The publication role requires explicit sole-writer configuration")
        publisher = publisher_from_config(
            json.loads(args.publication_config.read_text(encoding="utf-8"))
        )
    activities = BatchActivities(
        Path(config["artifact_root"]), registry_from_config(config), publisher
    )
    stopped = asyncio.Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(name, stopped.set)
    with ThreadPoolExecutor(max_workers=len(selected) + 1) as executor:
        async with AsyncExitStack() as stack:
            for role in selected:
                queue, names = ROLES[role]
                await stack.enter_async_context(
                    Worker(
                        client,
                        task_queue=queue,
                        workflows=[BatchAnnotationWorkflow] if role == "control" else [],
                        activities=[getattr(activities, name) for name in names],
                        activity_executor=executor,
                        max_concurrent_activities=1,
                    )
                )
            print(json.dumps({"status": "polling", "roles": selected}), flush=True)
            await stopped.wait()


async def submit(args):
    request = batch_request(json.loads(args.request.read_text(encoding="utf-8")))
    client = await Client.connect(args.address, namespace=args.namespace)
    handle = await client.start_workflow(
        BatchAnnotationWorkflow.run,
        request,
        id=args.workflow_id,
        task_queue=CONTROL,
        id_reuse_policy=(
            WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
            if args.retry_failed
            else WorkflowIDReusePolicy.REJECT_DUPLICATE
        ),
    )
    print(json.dumps({"workflow_id": handle.id}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", default="127.0.0.1:7258")
    parser.add_argument("--namespace", default="weedz-hosted")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--root", type=Path, required=True)
    prepare.add_argument("--sam-checkpoint", type=Path, required=True)
    prepare.add_argument("--classifier-checkpoint", type=Path, required=True)
    prepare.add_argument("--labels", type=Path, required=True)
    prepare.add_argument("--device", default="cuda:0")
    prepare.add_argument("--proposer", choices=["sam2", "sam3"], default="sam2")
    prepare.add_argument("--prompts", nargs="+", default=["plant", "flower"])
    prepare.add_argument("--concept-threshold", type=float, default=0.5)
    serve = commands.add_parser("worker")
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument("--roles", required=True)
    serve.add_argument("--publication-config", type=Path)
    start = commands.add_parser("submit")
    start.add_argument("--request", type=Path, required=True)
    start.add_argument("--workflow-id", required=True)
    start.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        config = prepare_config(
            args.root,
            args.sam_checkpoint,
            args.classifier_checkpoint,
            args.labels,
            args.device,
            proposer_kind=args.proposer,
            sam3_config=Sam3Config(
                prompts=tuple(args.prompts), concept_threshold=args.concept_threshold
            ),
        )
        digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        print(
            json.dumps(
                write_receipt(
                    args.root,
                    f"temporal-config/{digest}.json",
                    config,
                )
            )
        )
    elif args.command == "worker":
        asyncio.run(worker(args, json.loads(args.config.read_text(encoding="utf-8"))))
    else:
        asyncio.run(submit(args))


if __name__ == "__main__":
    main()

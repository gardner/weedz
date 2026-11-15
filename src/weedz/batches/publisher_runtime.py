"""The explicitly configured publication role, sharing the operator's existing writer lock."""

from pathlib import Path

from temporalio import activity

from weedz.batches.label_client import LabelStudioClient, task_index
from weedz.batches.package import Package
from weedz.batches.publication import publish


def publisher_from_config(config: dict):
    project = config["project_id"]
    if type(project) is not int or project <= 0:
        raise ValueError("Publication configuration requires an allowed project ID")

    def publish_package(package: Package, requested_project: int) -> dict:
        if requested_project != project:
            raise ValueError("This publication worker is restricted to its configured project")
        keys = [task["meta"]["external_id"] for task in package.tasks]
        with LabelStudioClient(config["api_url"], Path(config["token_file"])) as client:
            client.refresh()
            return publish(
                package,
                project,
                client,
                lambda: task_index(Path(config["database"]), project, keys),
                Path(config["images"]),
                Path(config["state"]),
                Path(config["lock"]),
                heartbeat=lambda: activity.heartbeat("publishing verified machine predictions"),
                legacy_allowlist=config.get("legacy_identity_allowlist"),
            )

    return publish_package

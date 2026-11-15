"""Deterministic orchestration: all network, disk and model work is in activities."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class DiscoveryWorkflow:
    @workflow.run
    async def run(self, spec: dict) -> dict:
        payload = {"run_id": workflow.info().workflow_id, "spec": spec}
        retry = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=3)
        names = ["collect_photos", "screen_photos", "export_run"]
        if spec.get("segmentation") == "sam2.1-tiny-v1" and workflow.patched("sam21-stages-v1"):
            names = [
                "collect_photos",
                "segment_photos_v1",
                "screen_photos",
                "score_region_views_v1",
                "export_run",
            ]
        last_result: dict = {}
        try:
            for name in names:
                last_result = await workflow.execute_activity(
                    name,
                    payload,
                    start_to_close_timeout=timedelta(minutes=30),
                    heartbeat_timeout=timedelta(minutes=2),
                    retry_policy=retry,
                    result_type=dict,
                )
        except Exception as error:
            await workflow.execute_activity(
                "fail_run",
                {"run_id": payload["run_id"], "error": str(error)},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry,
            )
            raise
        result = {"run_id": payload["run_id"], "status": "completed"}
        if "segment_photos_v1" in names:
            result["pipeline_outcome"] = last_result.get("pipeline_outcome", "unknown")
        return result

"""One bounded canonical batch; retries reuse validated immutable stage artifacts."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from weedz.batches.contract import artifact, batch_request

CONTROL = "weedz-batch-control-v1"
SEGMENTATION = "weedz-batch-segmentation-v1"
CLASSIFICATION = "weedz-batch-classification-v1"
PUBLICATION = "weedz-batch-publication-v1"


@workflow.defn(failure_exception_types=[ValueError])
class BatchAnnotationWorkflow:
    @workflow.run
    async def run(self, request: dict) -> dict:
        request = batch_request(request)
        stages = [("batch_validate_v1", CONTROL), ("batch_segment_v1", SEGMENTATION)]
        stages.extend(
            (f"batch_classify_{variant}_v1", CLASSIFICATION)
            for variant in ("frame", "tiles", "regions")
            if variant in request["variants"]
        )
        stages.extend([("batch_package_v1", CONTROL), ("batch_publish_v1", PUBLICATION)])
        completed: dict[str, dict[str, str]] = {}
        result: dict[str, str] = {}
        for name, queue in stages:
            result = artifact(
                await workflow.execute_activity(
                    name,
                    {"request": request, "completed": completed},
                    task_queue=queue,
                    start_to_close_timeout=timedelta(hours=2),
                    heartbeat_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=5), maximum_attempts=3
                    ),
                    result_type=dict,
                )
            )
            completed[name] = result
        return result

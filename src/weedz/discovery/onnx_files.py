"""Find external ONNX tensors, including tensors in nested control-flow graphs."""

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from onnx import AttributeProto, GraphProto, TensorProto


def _attribute_tensors(attribute: "AttributeProto") -> Iterator["TensorProto"]:
    if attribute.HasField("t"):
        yield attribute.t
    yield from attribute.tensors
    if attribute.HasField("sparse_tensor"):
        yield attribute.sparse_tensor.values
        yield attribute.sparse_tensor.indices
    for sparse in attribute.sparse_tensors:
        yield sparse.values
        yield sparse.indices
    if attribute.HasField("g"):
        yield from _graph_tensors(attribute.g)
    for graph in attribute.graphs:
        yield from _graph_tensors(graph)


def _graph_tensors(graph: "GraphProto") -> Iterator["TensorProto"]:
    yield from graph.initializer
    for sparse in graph.sparse_initializer:
        yield sparse.values
        yield sparse.indices
    for node in graph.node:
        for attribute in node.attribute:
            yield from _attribute_tensors(attribute)


def references_external_data(path: Path) -> bool:
    """Inspect graph bytes without loading any of their external tensor data."""
    import onnx
    from onnx.external_data_helper import uses_external_data

    model = onnx.load(str(path), load_external_data=False)
    return any(uses_external_data(tensor) for tensor in _graph_tensors(model.graph))

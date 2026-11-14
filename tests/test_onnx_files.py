"""All serialized tensor containers must be self-contained before recording a tower hash."""

from pathlib import Path

import pytest
from onnx import ModelProto, TensorProto, helper
from test_compare_optimised import script


def model_with_tensor(weight: TensorProto, container: str) -> ModelProto:
    constant = helper.make_node("Constant", [], ["embedding"], value=weight)
    nested = helper.make_graph([constant], "nested", [], [])
    function = helper.make_function(
        "weedz", "Tower", [], ["embedding"], [], [helper.make_opsetid("", 18)]
    )
    if container == "constant":
        function.node.append(constant)
    elif container == "nested":
        function.node.append(
            helper.make_node("If", ["condition"], ["embedding"], then_branch=nested)
        )
    elif container == "default":
        function.attribute_proto.append(helper.make_attribute("weights", weight))
    graph = helper.make_graph([], "main", [], [])
    model = helper.make_model(graph, functions=[function])
    if container == "training":
        model.training_info.add().algorithm.CopyFrom(nested)
    return model


@pytest.mark.parametrize("container", ["constant", "nested", "default", "training"])
def test_external_tensors_outside_the_main_graph_cannot_ship(
    tmp_path: Path, container: str
) -> None:
    for external in (True, False):
        weight = helper.make_tensor("weight", TensorProto.FLOAT, [1], [1.0])
        if external:
            weight.ClearField("float_data")
            weight.data_location = TensorProto.EXTERNAL
            weight.external_data.add(key="location", value="elsewhere.bin")
        path = tmp_path / f"tower-{external}.onnx"
        path.write_bytes(model_with_tensor(weight, container).SerializeToString())
        assert (script.artefact_sha256(path) is None) == external

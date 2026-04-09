from pybi.semanticmodel import SemanticModelDefinition
from pybi.serialization import deserialize, serialize


def test_bench_core_json_serialize_realistic(benchmark, semantic_model_realistic) -> None:
    benchmark(serialize, semantic_model_realistic.definition)


def test_bench_core_json_deserialize_realistic(benchmark, semantic_model_realistic) -> None:
    payload = serialize(semantic_model_realistic.definition)
    benchmark(deserialize, SemanticModelDefinition, payload)


def test_bench_core_json_roundtrip_realistic(benchmark, semantic_model_realistic) -> None:
    payload = serialize(semantic_model_realistic.definition)

    def run() -> None:
        model = deserialize(SemanticModelDefinition, payload)
        serialize(model)

    benchmark(run)


def test_bench_core_json_serialize_worst_case(benchmark, semantic_model_worst_case) -> None:
    benchmark(serialize, semantic_model_worst_case.definition)


def test_bench_core_json_deserialize_worst_case(benchmark, semantic_model_worst_case) -> None:
    payload = serialize(semantic_model_worst_case.definition)
    benchmark(deserialize, SemanticModelDefinition, payload)

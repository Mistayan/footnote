"""Exercise HelixDB's isolated embedded Windows runtime without telemetry."""
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench/work/storage/helix-python"))
os.environ["HELIX_TELEMETRY_LEVEL"] = "off"
from helixdb import Client, InMemory, PropertyValue, VectorDistanceMetric, g, read_batch, write_batch  # noqa: E402


def main():
    client = Client.embedded(InMemory("footnote-vector-fixture"))
    try:
        index = write_batch().var_as("index", g().create_vector_index_nodes(
            "Item", "embedding", 2, VectorDistanceMetric.EUCLIDEAN)).returning(["index"]).to_query_request()
        receipt = client.query(index)
        print("index:", receipt, flush=True)
        operation_id = receipt["index"]["operation_id"]
        status_query = read_batch().var_as("status", g().get_index_operation(operation_id)).returning(["status"]).to_query_request()
        for _ in range(100):
            status = client.query(status_query)["status"]
            if status.get("status") == "succeeded":
                break
            if status.get("status") in ("blocked", "aborted"):
                raise RuntimeError(f"Index operation failed: {status}")
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Index operation did not finish: {status}")
        for name, vector in (("one", [1.0, 0.0]), ("two", [0.8, 0.6]), ("three", [0.0, 1.0])):
            batch = write_batch().var_as("item", g().add_n("Item", {
                "name": name, "embedding": PropertyValue.f32_array(vector)})).returning(["item"]).to_query_request()
            print("insert:", client.query(batch), flush=True)
        query = read_batch().var_as("hits", g().vector_search_nodes("Item", "embedding", [1.0, 0.0], 3)
                                    .value_map(["name", "$id", "$distance"])).returning(["hits"]).to_query_request()
        result = client.query(query)
        print("search:", result, flush=True)
        if [item.get("name") for item in result.get("hits", [])] != ["one", "two", "three"]:
            raise RuntimeError("Unexpected vector search order")
    finally:
        client.close()


if __name__ == "__main__":
    main()

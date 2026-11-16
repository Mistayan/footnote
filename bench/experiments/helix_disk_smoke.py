"""Verify a disposable embedded Helix disk database survives a clean reopen."""
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench/work/storage/helix-python"))
os.environ["HELIX_TELEMETRY_LEVEL"] = "off"
from helixdb import Client, Disk, PropertyValue, VectorDistanceMetric, g, read_batch, write_batch  # noqa: E402


def main():
    directory = ROOT / "bench/work/storage/helixdb-3.7.0/disk-fixture"
    directory.mkdir(exist_ok=False)
    source = Disk(str(directory), "footnote-fixture")
    client = Client.embedded(source)
    try:
        batch = write_batch()
        for name, vector in (("one", [1.0, 0.0]), ("two", [0.8, 0.6]), ("three", [0.0, 1.0])):
            batch = batch.var_as(name, g().add_n("Item", {"name": name, "embedding": PropertyValue.f32_array(vector)}))
        client.query(batch.returning(["one", "two", "three"]).to_query_request())
        index = write_batch().var_as("index", g().create_vector_index_nodes(
            "Item", "embedding", 2, VectorDistanceMetric.EUCLIDEAN)).returning(["index"]).to_query_request()
        operation = client.query(index)["index"]["operation_id"]
        status_query = read_batch().var_as("status", g().get_index_operation(operation)).returning(["status"]).to_query_request()
        for _ in range(150):
            status = client.query(status_query)["status"]
            if status.get("status") == "succeeded":
                break
            if status.get("status") in ("blocked", "aborted"):
                raise RuntimeError(f"Index failed: {status}")
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Index timed out: {status}")
    finally:
        client.close()
    reader = Client.embedded_reader(source)
    try:
        query = read_batch().var_as("hits", g().vector_search_nodes("Item", "embedding", [1.0, 0.0], 3)
                                    .value_map(["name", "$distance"])).returning(["hits"]).to_query_request()
        result = reader.query(query)
        names = [hit["name"] for hit in result["hits"]]
        if names != ["one", "two", "three"]:
            raise RuntimeError(f"Unexpected reopened rankings: {result}")
        print(f"Helix embedded disk reopen: vector order {names}", flush=True)
    finally:
        reader.close()


if __name__ == "__main__":
    main()

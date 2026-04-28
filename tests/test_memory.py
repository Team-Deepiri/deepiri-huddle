from huddle.memory import MemoryStore


def test_memory_store_roundtrip(tmp_path) -> None:
    path = tmp_path / "mem.jsonl"
    store = MemoryStore(str(path))
    store.append("user", "hello")
    store.append("assistant", "hi")
    entries = store.latest(limit=10)
    assert len(entries) == 2
    assert entries[0].role == "user"
    assert entries[1].content == "hi"


from winbot import store


class FakeClient:
    def __init__(self):
        self.calls = []

    def query_vectors(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "vectors": [
                {"distance": 0.9, "metadata": {"page": 2, "text": "low"}},
                {"distance": 0.1, "metadata": {"page": 1, "text": "high"}},
                {"distance": 0.5, "metadata": {"page": 3, "text": "mid"}},
            ]
        }


def use_fake(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(store, "_client", fake)
    monkeypatch.setattr(store, "embed", lambda text: [0.0])
    return fake


def test_no_doc_id_means_no_filter(monkeypatch):
    fake = use_fake(monkeypatch)
    store.retrieve("question")
    assert "filter" not in fake.calls[0]


def test_doc_id_adds_a_filter(monkeypatch):
    fake = use_fake(monkeypatch)
    store.retrieve("question", doc_id="report")
    assert fake.calls[0]["filter"] == {"doc_id": "report"}


def test_results_are_sorted_best_first_and_limited(monkeypatch):
    use_fake(monkeypatch)
    results = store.retrieve("question", top_k=2)
    assert [r["text"] for r in results] == ["high", "mid"]
    assert results[0]["similarity"] == 0.9


def test_over_fetches_from_the_index(monkeypatch):
    fake = use_fake(monkeypatch)
    store.retrieve("question", top_k=3)
    assert fake.calls[0]["topK"] == store.config.FETCH_K
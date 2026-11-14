import math

import pytest
from src.embeddings import MyEmbedder

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def emb():
    return MyEmbedder("BAAI/bge-m3")


def cos(a, b):
    return sum(x * y for x, y in zip(a, b))  # vectors are L2-normalised


def test_dimensions_1024(emb):
    assert emb.dimensions == 1024
    assert len(emb.embed_query("đái tháo đường")) == 1024


def test_one_vector_per_text_in_order(emb):
    texts = ["Glucose huyết tương lúc đói", "Thời tiết hôm nay nắng đẹp", "Insulin tác dụng nhanh"]
    vecs = emb.embed_documents(texts)
    assert len(vecs) == 3
    assert all(abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-3 for v in vecs)
    singles = [emb.embed_documents([t])[0] for t in texts]
    for v, s in zip(vecs, singles):
        assert cos(v, s) > 0.999            # same text -> same vector, so order is kept


def test_related_closer_than_unrelated(emb):
    q = emb.embed_query("tiêu chuẩn chẩn đoán đái tháo đường")
    related, unrelated = emb.embed_documents([
        "Chẩn đoán đái tháo đường khi glucose huyết tương lúc đói >= 7,0 mmol/L.",
        "Hôm nay trời nắng đẹp, nhiệt độ khoảng 30 độ C.",
    ])
    assert cos(q, related) > cos(q, unrelated)


def test_model_failure_raises():
    with pytest.raises(RuntimeError):
        MyEmbedder("khong-ton-tai/model-gia-12345")

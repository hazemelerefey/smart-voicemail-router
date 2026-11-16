import random
import sys
import types

import numpy as np
import pytest

from infra.seeds import run_over_seeds, set_global_seed, summarize, summarize_metrics


def draw():
    return random.random(), float(np.random.rand())


def test_same_seed_gives_same_numbers():
    set_global_seed(42)
    a = draw()
    set_global_seed(42)
    b = draw()
    assert a == b


def test_different_seeds_give_different_numbers():
    set_global_seed(42)
    a = draw()
    set_global_seed(1337)
    b = draw()
    assert a != b


@pytest.mark.parametrize("bad", [-1, 1.5, "42", None, True])
def test_bad_seed_raises(bad):
    with pytest.raises(ValueError, match="seed"):
        set_global_seed(bad)


def test_torch_is_seeded_when_installed():
    calls = []
    fake = types.SimpleNamespace(
        manual_seed=lambda s: calls.append(("cpu", s)),
        cuda=types.SimpleNamespace(
            is_available=lambda: True,
            manual_seed_all=lambda s: calls.append(("cuda", s)),
        ),
    )
    previous = sys.modules.get("torch")
    sys.modules["torch"] = fake
    try:
        set_global_seed(7)
    finally:
        if previous is None:
            del sys.modules["torch"]
        else:
            sys.modules["torch"] = previous
    assert calls == [("cpu", 7), ("cuda", 7)]


def test_run_over_seeds_runs_in_order_and_is_repeatable():
    seeds = [42, 1337, 2023, 7, 99]
    first = run_over_seeds(lambda s: draw(), seeds)
    second = run_over_seeds(lambda s: draw(), seeds)
    assert [r["seed"] for r in first] == seeds
    assert first == second


def test_run_over_seeds_passes_the_seed_to_fn():
    records = run_over_seeds(lambda s: s * 2, [42, 7])
    assert records == [{"seed": 42, "result": 84}, {"seed": 7, "result": 14}]


def test_run_over_seeds_rejects_duplicates_and_empty():
    with pytest.raises(ValueError, match="duplicates"):
        run_over_seeds(lambda s: s, [42, 42])
    with pytest.raises(ValueError, match="empty"):
        run_over_seeds(lambda s: s, [])


def test_summarize_sample_std():
    out = summarize([1, 2, 3, 4, 5], ddof=1)
    assert out["mean"] == pytest.approx(3.0)
    assert out["std"] == pytest.approx(1.5811388300841898)
    assert out["ddof"] == 1
    assert out["n"] == 5


def test_summarize_population_std():
    out = summarize([1, 2, 3, 4, 5], ddof=0)
    assert out["std"] == pytest.approx(1.4142135623730951)
    assert out["ddof"] == 0


def test_summarize_rejects_bad_input():
    with pytest.raises(ValueError, match="more than"):
        summarize([0.5], ddof=1)
    with pytest.raises(ValueError, match="finite"):
        summarize([0.5, float("nan")])
    with pytest.raises(ValueError, match="finite"):
        summarize([0.5, None])
    with pytest.raises(ValueError, match="ddof"):
        summarize([0.5, 0.6], ddof=2)


def test_summarize_metrics_per_field():
    per_seed = [
        {"a_macro_f1": 0.5, "b_macro_f1": 0.7},
        {"a_macro_f1": 0.6, "b_macro_f1": 0.9},
    ]
    out = summarize_metrics(per_seed, ddof=1)
    assert out["a_macro_f1"]["mean"] == pytest.approx(0.55)
    assert out["b_macro_f1"]["mean"] == pytest.approx(0.8)
    assert out["a_macro_f1"]["ddof"] == 1


def test_summarize_metrics_rejects_mismatched_metrics():
    with pytest.raises(ValueError, match="different metrics"):
        summarize_metrics([{"a": 0.5}, {"b": 0.6}])
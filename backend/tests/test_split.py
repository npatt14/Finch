from eval.schema import BenchItem
from eval.split import split_items


def _item(i, cite):
    return BenchItem(
        id=f"i{i}", klass="clean_verbatim", citation=cite, brief_text="text",
        expected_verdict="verified", expected_flag=False,
    )


def test_split_is_deterministic_and_disjoint():
    items = [_item(i, f"c{i % 10}") for i in range(40)]
    dev1, hold1 = split_items(items)
    dev2, hold2 = split_items(items)
    assert [i.id for i in dev1] == [i.id for i in dev2]
    assert [i.id for i in hold1] == [i.id for i in hold2]
    assert {i.id for i in dev1}.isdisjoint({i.id for i in hold1})
    assert len(dev1) + len(hold1) == 40


def test_split_never_shares_a_seed_case_across_sides():
    items = [_item(i, f"c{i % 10}") for i in range(40)]
    dev, hold = split_items(items)
    assert {i.citation for i in dev}.isdisjoint({i.citation for i in hold})


def test_holdout_fraction_roughly_respected():
    items = [_item(i, f"c{i}") for i in range(100)]
    dev, hold = split_items(items, holdout_fraction=0.3)
    assert 20 <= len(hold) <= 40

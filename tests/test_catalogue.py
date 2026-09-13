from intelligence_os.catalogue import filter_candidates, parse_awesomedata_readme


def test_parse_awesomedata_candidates() -> None:
    text = """
Economics
---------

* |OK_ICON| `Example Dataset - useful data <https://example.com/data>`_ [`Meta <https://example.com/meta.yml>`_]
* |FIXME_ICON| `Broken Dataset <https://example.com/broken>`_
"""

    candidates = parse_awesomedata_readme(text)

    assert len(candidates) == 2
    assert candidates[0].category == "Economics"
    assert candidates[0].healthy is True
    assert candidates[1].healthy is False


def test_filter_candidates_defaults_to_healthy() -> None:
    text = """
Economics
---------
* |OK_ICON| `Good <https://example.com/good>`_
* |FIXME_ICON| `Bad <https://example.com/bad>`_
"""

    candidates = filter_candidates(parse_awesomedata_readme(text))

    assert [candidate.title for candidate in candidates] == ["Good"]

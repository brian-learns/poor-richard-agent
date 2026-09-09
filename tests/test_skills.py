"""Offline tests for PoorRichardSkill: deterministic search/get over the almanack.

All tests run with the network blocked (tests/conftest.py). Most use the real
bundled almanack data (high-value integration); one monkeypatches the wrapped
``poor_richard.search`` to assert the exact SearchHit mapping in isolation.
"""

import asyncio

import poor_richard
import pytest

from poor_richard_agent.models import SearchHit
from poor_richard_agent.skills import PoorRichardSkill


def test_search_maps_hits_to_searchhit():
    hits = asyncio.run(PoorRichardSkill().search("ISO 3166 France", top=3))
    assert isinstance(hits, list) and hits
    assert all(isinstance(h, SearchHit) for h in hits)
    top = hits[0]
    assert top.card_id == "pycountry"
    assert top.pypi == "pycountry"
    assert top.import_name == "pycountry"
    # the matched golden question is flattened onto the hit as plain strings
    assert top.question == "ISO 3166-1 alpha-3 for France?"
    assert top.expected == "France"
    # scores are ranked, best first
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_search_respects_top():
    hits = asyncio.run(PoorRichardSkill().search("ISO 3166 France", top=1))
    assert [h.card_id for h in hits] == ["pycountry"]


def test_search_no_match_returns_empty():
    hits = asyncio.run(PoorRichardSkill().search("zzz qqq xyzzy flurble", top=3))
    assert hits == []


def test_search_flattens_matched_question(monkeypatch):
    # control the wrapped function to assert the exact mapping, including the
    # question=None / expected=None case when a card has no matching golden question
    score, card, question = 0.9, poor_richard.get("pycountry"), None
    monkeypatch.setattr(poor_richard, "search", lambda query, top=3: [(score, card, question)])
    hits = asyncio.run(PoorRichardSkill().search("anything"))
    assert len(hits) == 1
    assert hits[0].score == 0.9
    assert hits[0].card_id == "pycountry"
    assert hits[0].question is None
    assert hits[0].expected is None


def test_get_returns_reference_card():
    card = asyncio.run(PoorRichardSkill().get("pycountry"))
    assert isinstance(card, poor_richard.ReferenceCard)
    assert card.id == "pycountry"
    assert len(card.questions) >= 1
    assert all(hasattr(q, "expected") for q in card.questions)


def test_get_unknown_id_raises():
    with pytest.raises(KeyError):
        asyncio.run(PoorRichardSkill().get("does-not-exist"))

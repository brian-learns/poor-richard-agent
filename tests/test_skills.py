"""Offline tests for PoorRichardSkill: deterministic search/get over the almanack.

All tests run with the network blocked (tests/conftest.py). Most use the real
bundled almanack data (high-value integration); the rest monkeypatch the
wrapped ``poor_richard.search`` to assert the SearchHit mapping in isolation.
"""

import asyncio

import poor_richard
import pytest

from poor_richard_agent.models import CardDetail, SearchHit
from poor_richard_agent.skills import PoorRichardSkill


def test_search_maps_hits_to_searchhit():
    # cross-check against the almanack's own data (not hardcoded golden values,
    # which live in poor-richard and can change) — this test is about the mapping
    query = "ISO 3166 France"
    hits = asyncio.run(PoorRichardSkill().search(query, top=3))
    raw = poor_richard.search(query, top=3)
    assert len(hits) == len(raw)
    assert all(isinstance(h, SearchHit) for h in hits)
    for hit, (score, card, question) in zip(hits, raw):
        assert hit.score == score
        assert hit.card_id == card.id
        assert hit.pypi == card.pypi
        assert hit.import_name == card.import_name
        if question is None:
            assert hit.question is None and hit.expected is None
        else:
            assert hit.question == question.question
            assert hit.expected == question.expected
    assert hits[0].card_id == "pycountry"
    # scores are ranked, best first
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


def test_search_respects_top():
    hits = asyncio.run(PoorRichardSkill().search("ISO 3166 France", top=1))
    assert [h.card_id for h in hits] == ["pycountry"]


def test_search_no_match_returns_empty(monkeypatch):
    # empty pass-through is this layer's contract; whether a given query
    # matches is poor-richard's business (tested in its own suite)
    monkeypatch.setattr(poor_richard, "search", lambda query, top=3: [])
    assert asyncio.run(PoorRichardSkill().search("zzz qqq xyzzy flurble", top=3)) == []


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


def test_get_returns_card_detail():
    card = asyncio.run(PoorRichardSkill().get("pycountry"))
    raw = poor_richard.get("pycountry")
    assert isinstance(card, CardDetail)
    # field names the model can rely on (card_id is consistent with SearchHit)
    assert card.card_id == raw.id
    assert card.pypi == raw.pypi
    assert card.import_name == raw.import_name
    assert len(card.questions) == len(raw.questions)
    for cq, rq in zip(card.questions, raw.questions):
        assert cq.question == rq.question
        assert cq.expected == rq.expected
    assert isinstance(card.notes, str)
    assert isinstance(card.example, str)


def test_get_unknown_id_raises():
    with pytest.raises(KeyError):
        asyncio.run(PoorRichardSkill().get("does-not-exist"))

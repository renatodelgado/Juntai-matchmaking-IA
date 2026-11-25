from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.supervised.behavior import BehaviorSnapshot, DiscoveryEvent, behavior_features, capture_behavior_snapshot

T = datetime(2026, 6, 1, tzinfo=timezone.utc)
I = UUID('11111111-1111-4111-8111-111111111111')
S = UUID('22222222-2222-4222-8222-222222222222')
OTHER = UUID('33333333-3333-4333-8333-333333333333')


def event(n, when, kind='perfil_aberto', **kwargs):
    return DiscoveryEvent(id=UUID(int=n), investidor_id=I, startup_id=S,
                          tipo=kind, ocorrido_em=when, **kwargs)


def calculate(events, since=T - timedelta(days=90)):
    return behavior_features(events, investor_id=I, startup_id=S, decision_at=T, history_complete_since=since)


def test_only_prior_events_for_pair_in_window_and_deduplication():
    first = event(1, T - timedelta(days=90))
    other = event(7, T - timedelta(days=1)).model_copy(update={'startup_id': OTHER})
    events = [first, first, event(2, T - timedelta(days=91)), event(3, T),
              event(4, T + timedelta(seconds=1)), event(5, T - timedelta(seconds=1), 'tempo_perfil', segundos=30),
              event(6, T - timedelta(days=1), 'salvou'), other]
    assert calculate(events) == {'historico_completo_90d': True, 'aberturas': 1,
        'visitas_temporizadas': 1, 'segundos_perfil': 30, 'salvamentos': 1, 'remocoes': 0}


def test_incomplete_history_is_unknown_not_zero():
    result = calculate([], T - timedelta(days=89))
    assert result['historico_completo_90d'] is False
    assert all(v is None for k, v in result.items() if k != 'historico_completo_90d')
    assert calculate([], None) == result
    assert calculate([])['aberturas'] == 0


def test_invalid_and_conflicting_events_are_rejected():
    with pytest.raises(ValidationError):
        event(1, T, 'tempo_perfil', segundos=9)
    with pytest.raises(ValidationError):
        event(1, T, 'salvou', segundos=10)
    with pytest.raises(ValueError, match='divergente'):
        calculate([event(1, T), event(1, T - timedelta(days=1))])


def test_requires_timezone_for_decision_and_coverage():
    with pytest.raises(ValueError, match='timezone'):
        behavior_features([], investor_id=I, startup_id=S, decision_at=datetime(2026, 1, 1), history_complete_since=None)
    with pytest.raises(ValueError, match='timezone'):
        calculate([], datetime(2026, 1, 1))


def test_snapshot_round_trip_preserves_decision_and_captured_values():
    events = [event(1, T - timedelta(seconds=1)), event(2, T)]
    snapshot = capture_behavior_snapshot(events, investor_id=I, startup_id=S, decision_at=T,
                                         history_complete_since=T - timedelta(days=90))
    assert snapshot.versao == 'behavior-v1'
    assert snapshot.decisao_em == T and snapshot.aberturas == 1
    assert BehaviorSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    events.append(event(3, T - timedelta(seconds=2)))
    assert snapshot.aberturas == 1


def test_snapshot_rejects_inconsistent_coverage_and_values():
    snapshot = capture_behavior_snapshot([], investor_id=I, startup_id=S, decision_at=T,
                                         history_complete_since=None)
    data = snapshot.model_dump()
    data['aberturas'] = 0
    with pytest.raises(ValidationError):
        BehaviorSnapshot.model_validate(data)
    data = snapshot.model_dump()
    data['historico_completo_90d'] = True
    with pytest.raises(ValidationError):
        BehaviorSnapshot.model_validate(data)

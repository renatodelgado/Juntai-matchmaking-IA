from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.supervised.behavior_dataset import build_behavior_dataset
from app.supervised.training.behavior_evaluation import evaluate_behavior
from test_behavior_dataset import BASE


def synthetic_data(n=500):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows, events = [], []
    for i in range(n):
        date = start + timedelta(days=i * 2)
        row = deepcopy(BASE)
        investor, startup = str(UUID(int=1000+i)), str(UUID(int=10000+i))
        row.update(id=str(UUID(int=20000+i)), investidor_id=investor, startup_id=startup,
                   ocorrido_em=date.isoformat(), origem_dados='sintetica')
        row['snapshot_perfis']['investidor']['id'] = investor
        row['snapshot_perfis']['startup']['id'] = startup
        row['snapshot_perfis']['investidor']['ticketMaximo'] = 50000 + (i % 9) * 1000
        row['snapshot_comportamental'] = {
            'versao': 'behavior-v1', 'investidor_id': investor, 'startup_id': startup,
            'decisao_em': (date - timedelta(seconds=1)).isoformat(),
            'historico_completo_desde': (date - timedelta(days=100)).isoformat(),
            'historico_completo_90d': True, 'aberturas': i % 2,
            'visitas_temporizadas': 0, 'segundos_perfil': 0, 'salvamentos': 0, 'remocoes': 0,
        }
        rows.append(row)
        if i % 2:
            events.append({'id': str(UUID(int=30000+i)), 'investidor_id': investor, 'startup_id': startup,
                           'tipo_evento': 'interesse_demonstrado', 'ocorrido_em': (date+timedelta(days=1)).isoformat()})
    cutoff = start + timedelta(days=n * 2 + 30)
    return build_behavior_dataset(rows, interactions=events, cutoff=cutoff, origin='sintetica',
                                  history_complete=True, complete_until=cutoff)


def test_paired_temporal_experiment_on_synthetic_data():
    result = evaluate_behavior(synthetic_data())
    assert result['modelos']['base']['metricas']['test']['n'] == result['modelos']['comportamental']['metricas']['test']['n']
    assert result['modelos']['comportamental']['metricas']['test']['roc_auc'] > result['modelos']['base']['metricas']['test']['roc_auc']
    assert 'behavior::aberturas' in result['modelos']['comportamental']['colunas_selecionadas']
    assert not any(k.startswith('behavior::') for k in result['modelos']['base']['colunas_selecionadas'])
    assert result['cobertura']['test']['historico_completo'] == result['split']['test']['n']
    assert result['temporal']['embargo_days'] == 30


def test_no_examples_rejected():
    data = synthetic_data(2)
    with pytest.raises(ValueError):
        evaluate_behavior(data)

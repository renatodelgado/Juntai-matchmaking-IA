import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.supervised.behavior_dataset import StoredBehaviorExposure, build_behavior_dataset, paired_training_records

BASE = json.loads((Path(__file__).parent / 'fixtures/stored-supervised-exposure.json').read_text(encoding='utf-8'))
T = datetime.fromisoformat(BASE['ocorrido_em'].replace('Z', '+00:00'))


def stored():
    row = deepcopy(BASE)
    row['snapshot_comportamental'] = {
        'versao': 'behavior-v1', 'investidor_id': row['investidor_id'], 'startup_id': row['startup_id'],
        'decisao_em': (T - timedelta(seconds=1)).isoformat(),
        'historico_completo_desde': (T - timedelta(days=100)).isoformat(),
        'historico_completo_90d': True, 'aberturas': 2, 'visitas_temporizadas': 1,
        'segundos_perfil': 30, 'salvamentos': 1, 'remocoes': 0,
    }
    return row


def dataset(rows, events=None):
    return build_behavior_dataset(rows, interactions=events or [], cutoff=T + timedelta(days=40),
                                  origin='sintetica', history_complete=True,
                                  complete_until=T + timedelta(days=40))


def test_snapshot_and_future_interest_remain_separate():
    row = stored()
    interest = {'id': 'interest', 'investidor_id': row['investidor_id'], 'startup_id': row['startup_id'],
                'ocorrido_em': T + timedelta(days=1), 'tipo_evento': 'interesse_demonstrado',
                'metadados': {'aberturas': 999}}
    out = dataset([row], [interest]).registros[0]
    assert out.base.rotulo.target == 1
    assert out.features_comportamentais.aberturas == 2
    assert out.versao_features_comportamentais == 'behavior-v1'
    assert out.base.metadados['versao_features'] == 'profiles-rules-v1'
    assert out.decisao_em == row['snapshot_comportamental']['decisao_em']
    assert 'aberturas' not in out.base.features.numericas


def test_missing_and_incomplete_snapshot_are_distinct():
    missing = dataset([BASE]).registros[0]
    assert missing.decisao_em is None
    assert missing.features_comportamentais.historico_completo_90d is None
    row = stored()
    behavior = row['snapshot_comportamental']
    behavior.update(historico_completo_desde=None, historico_completo_90d=False,
                    aberturas=None, visitas_temporizadas=None, segundos_perfil=None, salvamentos=None, remocoes=None)
    incomplete = dataset([row]).registros[0]
    assert incomplete.features_comportamentais.historico_completo_90d is False
    assert incomplete.features_comportamentais.aberturas is None


@pytest.mark.parametrize('mutation', [
    lambda r: r['snapshot_comportamental'].update(startup_id='33333333-3333-4333-8333-333333333333'),
    lambda r: r['snapshot_comportamental'].update(decisao_em=(T + timedelta(seconds=1)).isoformat()),
    lambda r: r['snapshot_comportamental'].update(aberturas=None),
    lambda r: r.update(origem_recomendacao='rules'),
    lambda r: r['snapshot_comportamental'].update(target=1),
])
def test_invalid_snapshot_rejected(mutation):
    row = stored()
    mutation(row)
    with pytest.raises((ValueError, ValidationError)):
        dataset([row])


def test_first_exposure_selected_without_using_later_snapshot():
    first = stored()
    second = deepcopy(first)
    second['id'] = str(UUID(int=555))
    second['ocorrido_em'] = (T + timedelta(days=1)).isoformat()
    second['snapshot_comportamental']['decisao_em'] = T.isoformat()
    second['snapshot_comportamental']['aberturas'] = 99
    result = dataset([second, first])
    assert len(result.registros) == 1
    assert result.registros[0].features_comportamentais.aberturas == 2
    assert 'multiplas_exposicoes' in [q.codigo for q in result.qualidade]


def test_duplicate_and_mixed_origins_rejected():
    row = stored()
    with pytest.raises(ValueError, match='duplicada'):
        dataset([row, row])
    row['origem_dados'] = 'real'
    with pytest.raises(ValueError, match='Origem'):
        dataset([row])


def test_contract_accepts_legacy_export_without_column():
    assert StoredBehaviorExposure.model_validate(BASE).snapshot_comportamental is None


def test_paired_records_use_same_labels_and_keep_identifiers_out_of_features():
    item = paired_training_records(dataset([stored()]))[0]
    assert item['target'] == 0
    assert item['comportamental']['behavior::aberturas'] == 2
    assert {k: v for k, v in item['comportamental'].items() if not k.startswith('behavior::')} == item['baseline']
    assert not {'target', 't0', 'exposicao_id'} & item['baseline'].keys()
    assert not {'target', 't0', 'exposicao_id'} & item['comportamental'].keys()


def test_censored_rows_are_excluded_from_training_records():
    data = build_behavior_dataset([stored()], interactions=[], cutoff=T + timedelta(days=1),
                                  origin='sintetica', history_complete=True,
                                  complete_until=T + timedelta(days=1))
    assert data.registros[0].base.rotulo.target is None
    assert paired_training_records(data) == []

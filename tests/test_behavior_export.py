from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.supervised.behavior_export import read_export
from test_behavior_dataset import stored

FIELDS = ['id','investidor_id','startup_id','ocorrido_em','origem_recomendacao','posicao_ranking',
          'versao_recomendador','snapshot_perfis','versao_contrato','semantica','origem_dados','snapshot_comportamental']


class Cursor:
    def __init__(self, row, readonly=True, column=True):
        self.row, self.readonly, self.column = row, readonly, column
        self.index = -1
        self.description = []
        self.queries = []

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, args=None):
        self.index += 1
        self.queries.append((sql, args))
        if self.index == 3:
            self.description = [type('Column', (), {'name': name}) for name in FIELDS]
        if self.index == 4:
            self.description = [type('Column', (), {'name': name}) for name in ['id','investidor_id','startup_id','tipo_evento','ocorrido_em']]
    def fetchone(self):
        if self.index == 0: return ('on' if self.readonly else 'off',)
        if self.index == 1: return (datetime(2026, 3, 1, tzinfo=timezone.utc), 'test', 'exposicoes_startups')
        if self.index == 2: return (self.column,)
        raise AssertionError(self.index)
    def fetchall(self):
        return [tuple(self.row[k] for k in FIELDS)] if self.index == 3 and self.row else []


class Connection:
    def __init__(self, cursor): self.cur = cursor
    def cursor(self): return self.cur


def test_export_validates_snapshot_and_never_claims_completeness():
    row = stored(); row['origem_dados'] = 'real'
    cursor = Cursor(row)
    result, database = read_export(Connection(cursor))
    assert database == 'test' and result['historico_completo'] is False
    assert result['exposicoes'][0]['snapshot_comportamental']['aberturas'] == 2
    assert result['interacoes'] == []
    assert 'JOIN pairs' in cursor.queries[3][0] and "origem_dados='real'" in cursor.queries[3][0]


def test_rejects_writable_connection_or_missing_migration():
    with pytest.raises(ValueError, match='somente de leitura'):
        read_export(Connection(Cursor(None, readonly=False)))
    with pytest.raises(ValueError, match='Migration'):
        read_export(Connection(Cursor(None, column=False)))


def test_invalid_snapshot_fails_export():
    row = deepcopy(stored()); row['snapshot_comportamental']['startup_id'] = '33333333-3333-4333-8333-333333333333'
    with pytest.raises(ValueError):
        read_export(Connection(Cursor(row)))

"""Exporta snapshots confirmados e interesses relacionados em leitura consistente."""

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.supervised.behavior_dataset import StoredBehaviorExposure
from app.supervised.schemas import Interaction
from app.supervised.synthetic.source import connection

ROOT = Path(__file__).resolve().parents[2] / 'data' / 'behavior'


def encode(value):
    if isinstance(value, (datetime, date, UUID, Decimal)):
        return str(value)
    raise TypeError(f'Tipo não serializável: {type(value).__name__}')


def read_export(conn):
    """Transação REPEATABLE READ somente leitura; não declara completude histórica."""
    with conn.cursor() as cur:
        cur.execute('SHOW transaction_read_only')
        if cur.fetchone()[0] != 'on':
            raise ValueError('Conexão precisa ser somente de leitura')
        cur.execute("SELECT transaction_timestamp(), current_database(), to_regclass('public.exposicoes_startups')")
        cutoff, database, table = cur.fetchone()
        if table is None:
            raise ValueError('Tabela de exposições ausente')
        cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='exposicoes_startups' AND column_name='snapshot_comportamental')")
        if not cur.fetchone()[0]:
            raise ValueError('Migration de snapshot comportamental ainda não aplicada')
        cur.execute('''WITH pairs AS (
            SELECT DISTINCT investidor_id, startup_id FROM public.exposicoes_startups
            WHERE snapshot_comportamental IS NOT NULL AND ocorrido_em <= %s AND origem_dados='real'
          ) SELECT e.id,e.investidor_id,e.startup_id,e.ocorrido_em,e.origem_recomendacao,
            e.posicao_ranking,e.versao_recomendador,e.snapshot_perfis,e.versao_contrato,e.semantica,
            e.origem_dados,e.snapshot_comportamental
          FROM public.exposicoes_startups e JOIN pairs p USING (investidor_id,startup_id)
          WHERE e.ocorrido_em <= %s AND e.origem_dados='real' ORDER BY e.ocorrido_em,e.id''', (cutoff, cutoff))
        columns = [item.name for item in cur.description]
        exposures = [StoredBehaviorExposure.model_validate(dict(zip(columns, row))).model_dump(mode='json') for row in cur.fetchall()]
        cur.execute('''WITH pairs AS (
            SELECT DISTINCT investidor_id, startup_id FROM public.exposicoes_startups
            WHERE snapshot_comportamental IS NOT NULL AND ocorrido_em <= %s AND origem_dados='real'
          ) SELECT f.id::text, f.investidor_id, f.startup_id, f.tipo_evento::text, f.ocorrido_em
          FROM public.funil_interacoes f JOIN pairs p USING (investidor_id,startup_id)
          WHERE f.tipo_evento='interesse_demonstrado' AND f.ocorrido_em <= %s ORDER BY f.ocorrido_em,f.id''', (cutoff, cutoff))
        columns = [item.name for item in cur.description]
        interactions = [Interaction.model_validate(dict(zip(columns, row))).model_dump(mode='json') for row in cur.fetchall()]
        return {'versao': 'behavior-export-v1', 'origem_dados': 'real', 'data_corte': cutoff.isoformat(),
                'historico_completo': False, 'completo_ate': None, 'exposicoes': exposures, 'interacoes': interactions}, database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Novo arquivo .json dentro de data/behavior/')
    args = parser.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to(ROOT.resolve()) or target.suffix != '.json':
        parser.error('Destino deve ser arquivo .json dentro de data/behavior/')
    target.parent.mkdir(parents=True, exist_ok=True)
    with connection(args.env_file) as conn:
        payload, database = read_export(conn)
    content = (json.dumps(payload, ensure_ascii=False, indent=2, default=encode) + '\n').encode('utf-8')
    with target.open('xb') as stream:
        stream.write(content)
    print(json.dumps({'banco': database, 'data_corte': payload['data_corte'], 'exposicoes': len(payload['exposicoes']),
                      'snapshots': sum(row['snapshot_comportamental'] is not None for row in payload['exposicoes']),
                      'interesses': len(payload['interacoes']), 'historico_completo': False,
                      'sha256': hashlib.sha256(content).hexdigest(), 'arquivo': str(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()

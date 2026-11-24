"""Avaliação exploratória pareada, fora da inferência e sem serializar modelos."""

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from app.supervised.behavior_dataset import BehaviorDataset
from app.supervised.training.preparation import Preprocessor, flatten
from app.supervised.training.splitting import temporal_split, describe
from app.supervised.training.evaluation import choose_threshold, metrics


def evaluate_behavior(dataset: BehaviorDataset, *, seed: int = 42, min_partition: int = 20) -> dict:
    """Compara dois XGBoost novos, com purga temporal e preprocessamento isolado."""
    dataset = BehaviorDataset.model_validate(dataset.model_dump())
    rows = [item.base for item in dataset.registros]
    if not rows:
        raise ValueError('Dataset vazio')
    cutoffs = {row.metadados['data_corte'] for row in rows}
    if len(cutoffs) != 1:
        raise ValueError('Cortes inconsistentes')
    origins = {row.metadados['origem_dados'] for row in rows}
    if len(origins) != 1:
        raise ValueError('Origens de dados misturadas')
    split, audit = temporal_split(rows)
    if any(len(indices) < min_partition for indices in split.values()):
        raise ValueError('Amostra insuficiente em uma divisão temporal')
    base = pd.DataFrame([flatten(item.base.features) for item in dataset.registros])
    behavior = pd.DataFrame([
        {'behavior::' + name: np.nan if value is None else float(value)
         for name, value in item.features_comportamentais.model_dump().items()}
        for item in dataset.registros
    ])
    availability = {}
    for name, indices in split.items():
        availability[name] = {
            'snapshot_ausente': sum(dataset.registros[i].decisao_em is None for i in indices),
            'historico_completo': sum(dataset.registros[i].features_comportamentais.historico_completo_90d is True for i in indices),
            'historico_incompleto': sum(dataset.registros[i].features_comportamentais.historico_completo_90d is False for i in indices),
        }
    result = {'origem_dados': next(iter(origins)), 'split': describe(rows, split), 'temporal': audit, 'cobertura': availability,
              'seed': seed, 'modelos': {},
              'limitacoes': ['Dois modelos experimentais novos; não é comparação com o modelo instalado.',
                            'Amostra condicionada à exposição; não demonstra efeito causal.',
                            'Dados sintéticos não estimam desempenho em usuários reais.',
                            'Diferenças pontuais não incluem intervalos de confiança nem medem significância.']}
    for name, frame in [('base', base), ('comportamental', pd.concat([base, behavior], axis=1))]:
        train = split['train']
        processor = Preprocessor().fit(frame.iloc[train])
        encoded = {part: processor.transform(frame.iloc[indices]) for part, indices in split.items()}
        y = {part: np.asarray([rows[i].rotulo.target for i in indices], dtype=int) for part, indices in split.items()}
        model = XGBClassifier(n_estimators=200, max_depth=3, learning_rate=.05, min_child_weight=8,
                              subsample=.85, colsample_bytree=.85, reg_lambda=5,
                              objective='binary:logistic', eval_metric='logloss',
                              n_jobs=2, random_state=seed, tree_method='hist')
        model.fit(encoded['train'], y['train'])
        predictions = {part: model.predict_proba(data)[:, 1] for part, data in encoded.items()}
        threshold = choose_threshold(y['validation'], predictions['validation'])
        result['modelos'][name] = {
            'colunas_selecionadas': processor.selected_,
            'metricas': {part: metrics(y[part], predictions[part], threshold, rows, indices)
                         for part, indices in split.items()},
        }
    b = result['modelos']['base']['metricas']['test']
    c = result['modelos']['comportamental']['metricas']['test']
    result['diferencas_teste'] = {key: c[key] - b[key] for key in ('roc_auc', 'average_precision', 'brier_score')}
    return result

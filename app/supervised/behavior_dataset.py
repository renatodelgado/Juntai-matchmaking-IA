"""Exportação e dataset experimentais; não alteram o contrato do modelo v1."""

from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas import Contrato
from app.supervised.backend_export import StoredExposure, adapt_exposure
from app.supervised.behavior import BehaviorSnapshot
from app.supervised.dataset import build_dataset
from app.supervised.schemas import DatasetInput, DatasetRow, QualityIssue


class StoredBehaviorExposure(StoredExposure):
    # Ausente em exportações anteriores à migration e nulo para contextos legados.
    snapshot_comportamental: BehaviorSnapshot | None = None

    @model_validator(mode='after')
    def behavior_provenance(self):
        behavior = self.snapshot_comportamental
        if behavior is not None:
            if self.origem_recomendacao != 'supervised':
                raise ValueError('Snapshot comportamental exige origem supervised')
            if (behavior.investidor_id, behavior.startup_id) != (self.investidor_id, self.startup_id):
                raise ValueError('Par inconsistente no snapshot comportamental')
            if behavior.decisao_em > self.ocorrido_em:
                raise ValueError('Decisão posterior à confirmação da exposição')
        return self


class BehaviorFeatures(Contrato):
    historico_completo_90d: bool | None
    aberturas: Annotated[int, Field(ge=0, strict=True)] | None
    visitas_temporizadas: Annotated[int, Field(ge=0, strict=True)] | None
    segundos_perfil: Annotated[int, Field(ge=0, strict=True)] | None
    salvamentos: Annotated[int, Field(ge=0, strict=True)] | None
    remocoes: Annotated[int, Field(ge=0, strict=True)] | None


class BehaviorDatasetRow(Contrato):
    base: DatasetRow
    versao_features_comportamentais: Literal['behavior-v1'] = 'behavior-v1'
    features_comportamentais: BehaviorFeatures
    decisao_em: str | None


class BehaviorDataset(Contrato):
    registros: list[BehaviorDatasetRow]
    qualidade: list[QualityIssue]


def build_behavior_dataset(rows: Iterable[dict], *, interactions: list, cutoff,
                           origin: Literal['real', 'sintetica'], history_complete: bool,
                           complete_until=None) -> BehaviorDataset:
    """Usa apenas snapshots persistidos; não reconstrói eventos ou perfis históricos."""
    stored = [StoredBehaviorExposure.model_validate(row) for row in rows]
    if any(row.origem_dados != origin for row in stored):
        raise ValueError('Origem de dados incompatível ou misturada')
    if len({row.id for row in stored}) != len(stored):
        raise ValueError('Exposição duplicada')
    exposures, profiles, behaviors = [], [], {}
    for row in stored:
        legacy = row.model_dump(mode='json', exclude={'snapshot_comportamental'})
        exposure, profile = adapt_exposure(legacy)
        exposures.append(exposure)
        profiles.append(profile)
        behaviors[str(row.id)] = row.snapshot_comportamental
    base = build_dataset(DatasetInput(exposicoes=exposures, snapshots=profiles, interacoes=interactions,
                         data_corte=cutoff, origem_dados=origin, historico_completo=history_complete,
                         completo_ate=complete_until))
    output = []
    keys = ('historico_completo_90d', 'aberturas', 'visitas_temporizadas',
            'segundos_perfil', 'salvamentos', 'remocoes')
    for item in base.registros:
        snapshot = behaviors[item.metadados['exposicao_id']]
        features = {key: getattr(snapshot, key) if snapshot is not None else None for key in keys}
        output.append(BehaviorDatasetRow(base=item, features_comportamentais=BehaviorFeatures(**features),
                                         decisao_em=snapshot.decisao_em.isoformat() if snapshot else None))
    return BehaviorDataset(registros=output, qualidade=base.qualidade)


def paired_training_records(dataset: BehaviorDataset) -> list[dict]:
    """Mesmas linhas rotuladas em duas variantes; não ajusta nem treina modelo."""
    from app.supervised.training.preparation import flatten

    records = []
    for item in dataset.registros:
        if item.base.rotulo.target is None:
            continue
        baseline = flatten(item.base.features)
        signals = item.features_comportamentais.model_dump()
        augmented = {**baseline, **{'behavior::' + name: value for name, value in signals.items()}}
        records.append({'exposicao_id': item.base.metadados['exposicao_id'],
                        't0': item.base.metadados['t0'], 'target': item.base.rotulo.target,
                        'baseline': baseline, 'comportamental': augmented})
    return records

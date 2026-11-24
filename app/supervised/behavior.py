"""Features experimentais pontuais; não usadas pela inferência em produção."""

from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictBool, model_validator

from app.schemas import Contrato


class BehaviorSnapshot(Contrato):
    """Contrato experimental para persistir o estado observado na decisão."""
    versao: Literal['behavior-v1'] = 'behavior-v1'
    investidor_id: UUID
    startup_id: UUID
    decisao_em: AwareDatetime
    historico_completo_desde: AwareDatetime | None
    historico_completo_90d: StrictBool
    aberturas: Annotated[int, Field(strict=True, ge=0)] | None
    visitas_temporizadas: Annotated[int, Field(strict=True, ge=0)] | None
    segundos_perfil: Annotated[int, Field(strict=True, ge=0)] | None
    salvamentos: Annotated[int, Field(strict=True, ge=0)] | None
    remocoes: Annotated[int, Field(strict=True, ge=0)] | None

    @model_validator(mode='after')
    def coverage_consistent(self):
        complete = (self.historico_completo_desde is not None and
                    self.historico_completo_desde <= self.decisao_em - timedelta(days=90))
        values = (self.aberturas, self.visitas_temporizadas, self.segundos_perfil,
                  self.salvamentos, self.remocoes)
        if self.historico_completo_90d != complete or any((v is None) == complete for v in values):
            raise ValueError('Cobertura e valores comportamentais inconsistentes')
        return self


class DiscoveryEvent(Contrato):
    id: UUID
    investidor_id: UUID
    startup_id: UUID
    tipo: Literal['perfil_aberto', 'tempo_perfil', 'salvou', 'removeu_salvo']
    ocorrido_em: AwareDatetime
    segundos: Annotated[int, Field(strict=True, ge=10, le=300)] | None = None

    @model_validator(mode='after')
    def duration_matches_type(self):
        if (self.tipo == 'tempo_perfil') != (self.segundos is not None):
            raise ValueError('Duração é obrigatória apenas para tempo_perfil')
        return self


def behavior_features(events: list[DiscoveryEvent], *, investor_id: UUID, startup_id: UUID,
                      decision_at, history_complete_since) -> dict[str, int | bool | None]:
    """Agrega eventos do par nos 90 dias anteriores, desde que haja cobertura comprovada.

    Timestamps devem ser de recebimento no servidor, e decision_at deve representar
    o instante real da decisão, não o ACK posterior da exposição do card.
    """
    if decision_at.tzinfo is None or decision_at.utcoffset() is None:
        raise ValueError('decision_at deve conter timezone')
    if history_complete_since is not None and (history_complete_since.tzinfo is None or history_complete_since.utcoffset() is None):
        raise ValueError('history_complete_since deve conter timezone')
    start = decision_at - timedelta(days=90)
    complete = history_complete_since is not None and history_complete_since <= start
    names = ('aberturas', 'visitas_temporizadas', 'segundos_perfil', 'salvamentos', 'remocoes')
    if not complete:
        return {'historico_completo_90d': False, **{name: None for name in names}}
    selected = {}
    for item in events:
        event = DiscoveryEvent.model_validate(item.model_dump() if isinstance(item, DiscoveryEvent) else item)
        if event.id in selected and selected[event.id] != event:
            raise ValueError('Eventos com mesmo ID e conteúdo divergente')
        selected[event.id] = event
    prior = [e for e in selected.values() if e.investidor_id == investor_id and e.startup_id == startup_id
             and start <= e.ocorrido_em < decision_at]
    return {
        'historico_completo_90d': True,
        'aberturas': sum(e.tipo == 'perfil_aberto' for e in prior),
        'visitas_temporizadas': sum(e.tipo == 'tempo_perfil' for e in prior),
        'segundos_perfil': sum(e.segundos or 0 for e in prior),
        'salvamentos': sum(e.tipo == 'salvou' for e in prior),
        'remocoes': sum(e.tipo == 'removeu_salvo' for e in prior),
    }


def capture_behavior_snapshot(events: list[DiscoveryEvent], *, investor_id: UUID, startup_id: UUID,
                              decision_at, history_complete_since) -> BehaviorSnapshot:
    """Constrói um registro versionado; o chamador é responsável pela persistência."""
    return BehaviorSnapshot(investidor_id=investor_id, startup_id=startup_id,
                            decisao_em=decision_at, historico_completo_desde=history_complete_since,
                            **behavior_features(events, investor_id=investor_id, startup_id=startup_id,
                                                decision_at=decision_at, history_complete_since=history_complete_since))

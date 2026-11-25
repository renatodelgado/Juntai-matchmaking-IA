# Sinais comportamentais para o modelo supervisionado

Esta primeira etapa é experimental e não altera o ranking, o contrato HTTP, o
treinamento ou o modelo existente. `app/supervised/behavior.py` transforma uma
lista já disponibilizada de eventos de descoberta em contagens do par
investidor/startup durante os 90 dias anteriores à decisão. Contabiliza aberturas,
visitas temporizadas, segundos recebidos, salvamentos e remoções. Os eventos são
deduplicados por ID; dados conflitantes são rejeitados.

O instante de decisão é exclusivo: eventos no mesmo instante ou posteriores são
ignorados. O limite inicial de 90 dias é inclusivo. Os timestamps precisam ter
timezone e representar a disponibilidade no servidor. O ACK da exposição é
posterior à decisão e não serve como substituto para seu instante. A declaração
`history_complete_since` exige evidência de que a fonte está completa durante
toda a janela; sem ela os valores são desconhecidos (`None`), não zero.
Mesmo com coleta completa, tempo de perfil é apenas tempo recebido pelo servidor,
pois o navegador pode não conseguir enviá-lo. Salvamentos e remoções são eventos,
não o estado atual do favorito, que não pode ser reconstruído com segurança sem
histórico anterior e ordenação confiável.

`capture_behavior_snapshot` cria um registro `behavior-v1` serializável, com os
IDs do par, instante da decisão, início comprovado da cobertura e valores
calculados. O contrato rejeita declarações inconsistentes de cobertura e valores.
O backend agora possui captura experimental desligada por padrão, com migration
separada ainda não aplicada. A captura usa a visão de uma única instrução SQL e
guarda o snapshot na confirmação do card; o timestamp sozinho não comprova que
uma transação concorrente já estava visível. Contextos emitidos antes da alteração
continuam válidos, sem inventar snapshots para eles. O exportador e o dataset
originais não leem essa coluna; `app/supervised/behavior_dataset.py` oferece um
caminho experimental separado. Ele aceita exportações com ou sem a coluna,
valida par, origem, cobertura e instante da decisão, e associa o snapshot à
primeira exposição. Snapshots ausentes e com histórico incompleto permanecem
distintos. Exposições duplicadas e origens misturadas são rejeitadas.

`paired_training_records` prepara, para as mesmas linhas rotuladas, a versão
base e a versão com sinais; IDs, datas e target ficam fora das features. Linhas
censuradas são descartadas. A função não divide dados nem treina modelos. Uma
avaliação posterior deve usar divisão temporal com rótulos maduros antes de cada
corte, ajustar pré-processamento só no treino e não tratar ausências como zero.
A autenticidade e completude da origem ainda exigem garantias externas.

Para exportar do banco configurado, em uma transação somente de leitura e visão
consistente, execute a partir da raiz:

```powershell
python -m app.supervised.behavior_export --env-file ..\Juntai-Backend\.env --output data\behavior\exportacao.json
```

O destino deve ser novo e fica em `data/behavior/`, ignorado pelo Git. O arquivo
contém IDs e snapshots de perfis: mantenha-o protegido e não o compartilhe sem
autorização. A exportação inclui todas as exposições reais dos pares que possuem
ao menos um snapshot comportamental, inclusive anteriores, e seus interesses
confirmados até o corte. Assim a seleção da primeira exposição permanece fiel
ao histórico disponível. Metadados de interesse não são exportados. O arquivo
declara histórico incompleto por padrão: não usar para treino supervisionado
completo até haver comprovação independente da cobertura histórica e do corte.
Não inclui pares sem snapshot comportamental, nem recupera dados de outros
ambientes, ou dados que ainda não foram coletados.

`app.supervised.training.behavior_evaluation.evaluate_behavior(dataset)` compara
dois novos modelos XGBoost com e sem sinais sobre as mesmas linhas. Reutiliza a
separação temporal com dois intervalos de 30 dias, exige duas classes em cada
partição e um mínimo padrão de 20 linhas por partição. Os processadores são
ajustados apenas no treino; limiares são escolhidos na validação. O relatório
contém cobertura dos sinais, AUC, precisão média, Brier e métricas de ranking
entre candidatos expostos. Não serializa modelos nem modifica inferência.

Não é uma comparação contra o modelo já instalado, não inclui intervalos de
confiança e não mede impacto causal. Amostras pequenas ou selecionadas pela
exposição podem distorcer resultados. Um teste sintético automatizado constrói
uma relação artificial entre abertura e interesse apenas para verificar o fluxo;
o resultado não é estimativa de melhoria real.

Não usar a tabela atual de favoritos ou o segmento atual da startup para inventar
estado histórico. Este módulo não incorpora exposições, interesse confirmado ou
afinidade por setor; exigem tratamento histórico e cobertura próprios. Não usar os
atributos como features do modelo existente: ele foi treinado com outro contrato
e verifica versões e hashes. Antes de um novo treino é necessário registrar o
instante real da decisão e um snapshot das features efetivamente disponíveis,
versionar o contrato, preservar completude e avaliar dados reais com divisão
temporal, janela de target madura e comparação com o modelo atual. Nenhuma
estimativa de ganho real decorre destes testes.

Teste: `python -m pytest tests/test_supervised_behavior.py -q -p no:cacheprovider`.

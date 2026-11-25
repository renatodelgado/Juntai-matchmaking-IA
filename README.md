# Juntaí! Motor de matchmaking

Serviço de recomendação do Juntaí!, plataforma acadêmica que aproxima startups, investidores anjo e mentores. O motor recebe projeções de perfis do backend e devolve listas ordenadas. A afinidade apoia a descoberta; não é garantia de interesse, contato, retorno ou investimento.

**Demonstração da plataforma na Azure:** https://delightful-beach-0c45f1a10.4.azurestaticapps.net/

Repositórios: [frontend](https://github.com/renatodelgado/Juntai-Frontend), [backend](https://github.com/renatodelgado/Juntai-Backend) e [motor de matchmaking](https://github.com/renatodelgado/Juntai-matchmaking-IA).

## Arquitetura e métodos

O navegador chama o backend Node.js; o backend autentica a solicitação, consulta o PostgreSQL e envia somente os atributos necessários ao FastAPI. O motor não consulta o banco diretamente. A resposta é validada pelo backend e apresentada na interface. Veja o [diagrama de componentes e dados](docs/arquitetura.md).

- **Regras estruturadas (`POST /match/rules`):** comparação de segmento, estágio, região, modelo de negócio e necessidades de apoio. O resultado informa pontuação, cobertura e evidências. Dados insuficientes não são convertidos em incompatibilidade. É a estratégia padrão do beta.
- **Conteúdo semântico (`POST /match/content`):** compara textos com embeddings locais, em caminho separado; requer `requirements-content.txt` e pesos do modelo. A primeira execução pode exigir download. A similaridade não é probabilidade de investimento.
- **Supervisionado (`POST /match/supervised`):** implementação experimental, treinada com dados sintéticos e dependente de artefatos e bibliotecas adicionais. O backend pode selecioná-la por configuração, com fallback para regras em certas falhas; não há validação de desempenho com usuários reais. Consulte [inferência](docs/supervised-inference.md) e [treinamento](docs/supervised-training.md).

Não há combinação híbrida desses métodos. Os pesos das regras são hipóteses de produto, não medidas científicas; a cobertura informa quanto foi possível avaliar e não representa confiança estatística.

## Executar localmente

Requisitos: Git e Python 3.12 recomendado para compatibilidade com os pacotes experimentais. Para a API básica e seus testes de regras:

```sh
git clone https://github.com/renatodelgado/Juntai-matchmaking-IA.git
cd Juntai-matchmaking-IA
python -m venv .venv
```

Ative o ambiente: no PowerShell, `.venv\Scripts\Activate.ps1`; em macOS/Linux, `source .venv/bin/activate`. Em seguida:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_rules.py tests/test_eligibility.py tests/test_service_auth.py -q -p no:cacheprovider
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Com o serviço ativo, `http://127.0.0.1:8000/health` informa sua disponibilidade e `/docs` apresenta os contratos HTTP. A documentação da API não comprova integração com o backend ou qualidade das recomendações. O backend deve definir `MATCHMAKING_API_URL=http://127.0.0.1:8000`.

Para exigir autenticação entre serviços, configure `MATCHMAKING_REQUIRE_AUTH=true` e um `MATCHMAKING_API_KEY` longo e aleatório no ambiente do processo do motor; configure a mesma chave somente no backend. O arquivo `.env.example` documenta os nomes, mas não é carregado automaticamente pelo comando acima. O backend envia `X-Matchmaking-Key`; `/health` permanece público. Se a exigência estiver ativa sem chave configurada, a API retorna erro. Sem essa configuração, o ambiente local pode aceitar chamadas sem chave: não exponha essa configuração na internet.

## Dependências e testes

`requirements.txt` reúne a API básica; `requirements-dev.txt` adiciona pytest e cliente HTTP. Os testes indicados acima cobrem o caminho de regras e a autenticação sem baixar modelos ou consultar banco. `requirements-content.txt`, `requirements-training.txt`, `requirements-supervised.txt` e `requirements-synthetic.txt` acrescentam dependências para experimentos específicos; consulte a documentação em `docs/` antes de usá-los.

A suíte completa (`python -m pytest -q -p no:cacheprovider`) precisa também das dependências de treinamento, pois alguns módulos importam NumPy e joblib durante a coleta. Instalar apenas `requirements-dev.txt` não é suficiente para essa suíte. As dependências usam faixas de versão, exceto o ambiente supervisionado fixado; não há lockfile geral. Testes com embeddings simulados não comprovam a qualidade do modelo real.

## Regra ECA

Evento: o backend solicita recomendações; condição: atributos de perfis podem ser comparados; ação: o motor calcula afinidade e cobertura e ordena candidatas. Executor: FastAPI, com regras em `app/rules.py`. `tests/test_rules.py` exercita compatibilidade e dados insuficientes; o comando de testes acima inclui essa evidência.

## Estrutura, segurança e limitações

`app/main.py` define endpoints e autenticação; `app/rules.py`, `app/eligibility.py` e `app/schemas.py` implementam regras e contratos; `app/content*.py` e `app/embeddings.py` tratam conteúdo; `app/supervised` reúne os experimentos; `tests` e `docs` contêm validações e detalhes técnicos. A [referência técnica das regras](docs/referencia-regras.md) preserva exemplos e detalhes anteriores. Não versione segredos, bancos ou perfis reais. Revise artefatos, permissões e isolamento de rede antes de publicar o serviço.

## Equipe e uso de IA

Os integrantes e o contexto acadêmico estão no [frontend](https://github.com/renatodelgado/Juntai-Frontend/blob/main/docs/projeto-integrador.md). O histórico Git demonstra apenas as contribuições nele registradas. O Codex auxiliou na revisão desta documentação; a equipe deve completar a declaração de ferramentas anteriores e das verificações que realizou. A licença de distribuição ainda não foi definida neste repositório.

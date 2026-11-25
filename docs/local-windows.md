# Execução local no Windows

Execute os comandos em terminais PowerShell separados. Parta da pasta
`Juntai-matchmaking-IA`. Os projetos Backend e Frontend devem estar na mesma
pasta pai. Esta configuração executa Node e Python no Windows e mantém somente
o PostgreSQL no Docker; não depende da comunicação Docker → Windows.

## 1. Banco

```powershell
docker start postgres_juntai
```

Confira a porta publicada com `docker ps`. Neste computador, o container publica
5434 e o `.env` do backend já usa `DB_HOST=localhost` e `DB_PORT=5434`.

## 2. IA

Na primeira execução:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Para iniciar:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Se `/health` já responder na porta 8000, não inicie outra instância nessa porta.
Documentação: http://127.0.0.1:8000/docs.

## 3. Backend

```powershell
cd ..\Juntai-Backend
$env:PORT = '3336'
$env:MATCHMAKING_API_URL = 'http://127.0.0.1:8000'
$env:MATCHMAKING_STRATEGY = 'rules'
npm.cmd run dev
```

As dependências Node já estão instaladas neste computador. Em um checkout novo,
instale-as antes com `npm.cmd ci`.

## 4. Frontend

```powershell
cd ..\Juntai-Frontend
$env:VITE_API_URL = 'http://localhost:3336'
npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Abra http://127.0.0.1:5174. As variáveis acima valem somente no terminal atual;
repita os comandos ao reiniciar. O frontend acessa o backend, que chama a IA.

## Verificação

- Frontend: http://127.0.0.1:5174
- Backend: http://127.0.0.1:3336
- IA: http://127.0.0.1:8000/health

Os endpoints responderam HTTP 200 durante o diagnóstico. O fluxo autenticado
de recomendações precisa ser verificado com uma conta de teste.

As dependências básicas permitem executar as regras. Inferência semântica e
supervisionada exigem dependências e, respectivamente, pesos/modelo adicionais.
A suíte completa também exige as dependências de treinamento; somente
`requirements-dev.txt` não fornece `joblib` para `test_training.py`.

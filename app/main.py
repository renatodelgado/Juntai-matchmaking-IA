import os
import secrets
from starlette.responses import JSONResponse

from fastapi import Depends, FastAPI, HTTPException
from app.content import rank_content
from app.content_schemas import ContentRequest, ContentResponse
from app.embeddings import Encoder, EmbeddingError, get_encoder
from app.rules import rank
from app.schemas import RulesRequest, RulesResponse
from app.supervised.inference.schemas import SupervisedRequest, SupervisedResponse
from app.supervised.inference.service import Predictor, SupervisedUnavailable, get_predictor

app = FastAPI(
    title="Juntai Matchmaking IA",
    description="API de recomendação de startups para investidores",
    version="0.1.0",
)


@app.middleware("http")
async def service_auth(request, call_next):
    if request.url.path != "/health":
        key = os.getenv("MATCHMAKING_API_KEY", "")
        required = os.getenv("MATCHMAKING_REQUIRE_AUTH") == "true"
        if required and not key:
            return JSONResponse({"detail": "Service authentication unavailable."}, status_code=503)
        if key and not secrets.compare_digest(request.headers.get("x-matchmaking-key", ""), key):
            return JSONResponse({"detail": "Unauthorized."}, status_code=401)
    return await call_next(request)


@app.get("/")
def home():
    return {
        "mensagem": "API de matchmaking funcionando!"
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/match/rules", response_model=RulesResponse)
def match_rules(payload: RulesRequest) -> RulesResponse:
    return rank(payload)


@app.post("/match/content", response_model=ContentResponse)
def match_content(payload: ContentRequest, encoder: Encoder = Depends(get_encoder)) -> ContentResponse:
    try:
        return rank_content(payload, encoder)
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail="Serviço de embeddings indisponível.") from exc


@app.post("/match/supervised", response_model=SupervisedResponse)
def match_supervised(payload: SupervisedRequest, predictor: Predictor = Depends(get_predictor)) -> SupervisedResponse:
    try:
        return predictor.rank(payload)
    except SupervisedUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

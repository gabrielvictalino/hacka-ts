"""Preflight explícito no ambiente da API: python -m app.check_bedrock.

Executa uma chamada faturável com evidência sintética, sem dados do acervo.
Não altera configuração, políticas IAM, assinaturas ou recursos AWS.
"""

import json
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.bedrock import generate_claims
from app.config import get_settings
from app.contracts import Citation, QuestionRequest


def main() -> int:
    try:
        settings = get_settings()
    except ValidationError as exc:
        # Não serializar str(exc), input, ctx ou mensagens com valores recebidos.
        fields = [
            {"field": str(error["loc"][0]) if error["loc"] else "settings", "type": error["type"]}
            for error in exc.errors(include_input=False, include_context=False, include_url=False)
        ]
        print(json.dumps({"available": False, "error": "configuration_error", "fields": fields}))
        return 2
    except Exception as exc:
        # Inclui erros de parsing de variáveis JSON do pydantic-settings.
        print(json.dumps({"available": False, "error": "configuration_error", "type": type(exc).__name__}))
        return 2
    status = {"region": settings.bedrock_region, "model_id": settings.bedrock_model_id}
    if not settings.bedrock_model_id:
        print(json.dumps({**status, "available": False, "error": "BEDROCK_MODEL_ID não configurado"}))
        return 2
    identifier = UUID("00000000-0000-4000-8000-000000000019")
    citation = Citation(
        document_id=identifier,
        version_id=identifier,
        passage_id=identifier,
        title="Verificação sintética de acesso",
        version="1.0",
        physical_page=1,
        section="1",
        excerpt="O prazo de verificação é de 2 dias corridos.",
    )
    try:
        generate_claims(
            QuestionRequest(
                topic_id=identifier,
                question="Qual o prazo de verificação?",
                reference_date=datetime.now(ZoneInfo("America/Recife")).date(),
            ),
            [citation],
        )
    except Exception as exc:
        # Não imprimir credenciais, conteúdo ou mensagens de erro remotas.
        error = type(exc).__name__
        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            error = response.get("Error", {}).get("Code", error)
        print(json.dumps({**status, "available": False, "error": error}))
        return 1
    print(json.dumps({**status, "available": True, "citations_validated": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

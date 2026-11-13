# Ambiente de desenvolvimento · issue #8

Execute os comandos na raiz do repositório (a pasta que contém `compose.yaml`). São necessários Docker Engine/Desktop com Compose v2+ e Python 3. O Node e o Python da aplicação ficam nos containers.

## Inicialização

```sh
python3 scripts/init_env.py
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps -a
```

O script cria `.env` com permissão `0600`, senha do banco e chave de assinatura aleatórias. Se já existir, não o sobrescreve. `.env`, acervo, dependências e dados locais estão no `.gitignore`; o contexto de build também exclui os segredos. `.env.example` contém somente configuração de exemplo, sem credenciais válidas. Não coloque segredos em variáveis `VITE_*`, que são públicas no navegador.

O frontend fica em `http://localhost:5173`, a API em `http://localhost:8000` e o Swagger em `/docs`. As portas são configuráveis em `.env`. Os serviços só publicam portas em `127.0.0.1`; o banco fica na rede interna do Compose.

O PostgreSQL precisa passar no healthcheck e o serviço `migrate` precisa concluir antes de iniciar API e worker. É esperado que `migrate` apareça como `Exited (0)`. O frontend inicia após a API ficar pronta. `GET /health/live` verifica o processo e `GET /health/ready` verifica banco e revisão da migração. O healthcheck do worker usa um heartbeat atualizado após cada consulta à fila.

O readiness compara o conjunto de revisões aplicadas no banco com os heads esperados pelos arquivos Alembic, inclusive quando há mais de um head. Uma nova revisão aplicada corretamente continua permitindo iniciar o frontend; banco indisponível ou revisão pendente retorna 503. A resposta saudável lista as revisões em `migrations`.

API e frontend recarregam alterações dos fontes montados. Reinicie o worker após alterar seu código. Alterações em dependências exigem rebuild; se mudar o `package-lock.json`, atualize também o volume de dependências com `docker compose run --rm --no-deps frontend npm ci`.

```sh
docker compose logs -f api worker
docker compose restart worker
docker compose down
```

`down` preserva volumes do banco e dos originais. `docker compose down -v` **apaga os dados locais**, incluindo o acervo importado. Após mudar senhas de um banco já criado, atualize também as credenciais no PostgreSQL; editar `.env` sozinho não altera a senha persistida.

## Migrações

A migração `0001` cria `topics`, `documents`, `document_versions`, `pages`, `passages`, `curated_facts` e `fact_citations`. A página física começa em 1, é única por versão e fica na tabela `pages`, inclusive para páginas vazias. Um trecho pertence a exatamente uma página. Os fatos curados referenciam trechos por `fact_citations`. A busca textual tem índice GIN com configuração `portuguese`.

```sh
docker compose run --rm migrate
docker compose run --rm --no-deps migrate alembic -c backend/alembic.ini current
docker compose run --rm --no-deps --user "$(id -u):$(id -g)" migrate alembic -c backend/alembic.ini revision -m "descricao"
```

Preencha `upgrade` e `downgrade` da nova revisão antes de aplicá-la. O serviço `migrate` e a CI usam `upgrade heads` para aplicar todas as revisões, inclusive quando há múltiplos heads. Em banco descartável, é possível testar a reversão com `alembic -c backend/alembic.ini downgrade base`; isso remove as tabelas documentais e seus dados. A CI aplica, reverte e reaplica as migrações.

## Importação do acervo

O caminho do acervo é informado por bind mount somente leitura. PDFs e caminhos pessoais não são versionados. Cada subpasta imediatamente abaixo da raiz define o nome de um tema, e PDFs em seus descendentes herdam esse tema. PDFs da raiz, como o catálogo auxiliar, não viram fontes operacionais.

```text
documentos_desafio_2/
  catalogo.pdf
  Férias/
    norma-v2.pdf
    norma-v3.pdf
  Inovação e Ideias em Campo/
    regulamento.pdf
  Locação de coworking/
    contrato.pdf
```

```sh
docker compose run --rm \
  -v "/caminho/absoluto/documentos_desafio_2:/acervo:ro" \
  api python -m app.import_collection /acervo
docker compose logs -f worker
```

O comando imprime uma linha JSON por arquivo com versão, estado e indicação de duplicação. O êxito do comando confirma o **enfileiramento**. A conclusão do processamento deve ser conferida no worker ou em `GET /api/documents?topic_id=…`. Arquivos rejeitados causam código de saída 1 sem impedir a tentativa dos demais. Falhas posteriores de extração aparecem na versão como `failed`, com motivo legível.

O CLI é uma ferramenta administrativa local com acesso direto ao banco. O upload HTTP (`POST /api/documents`, multipart com `topic_id` e `file`) exige sessão com permissão `documents:ingest`. Ambos chamam `app.ingestion.enqueue` e usam o mesmo worker. O limite é 25 MiB por PDF. Texto é extraído com pypdf, sem OCR nem chamadas externas.

O hash SHA-256 por tema evita duplicação, inclusive entre chamadas concorrentes. Reenviar um PDF com falha o recoloca na fila. O worker usa `FOR UPDATE SKIP LOCKED`: múltiplos workers podem compartilhar a fila e uma queda antes do commit devolve o trabalho ao estado anterior. Páginas, trechos e estado `ready` são gravados atomicamente. O estado `processing` fica na transação do worker; observadores veem `queued` até `ready` ou `failed`. Uma página vazia conserva sua posição, mas não gera trecho vazio.

Antes de reutilizar um original, a ingestão confere seu SHA-256. Se estiver ausente ou corrompido, restaura atomicamente os bytes recebidos, inclusive ao enviar o mesmo PDF para outro tema. O reenvio restaura o arquivo antes de reenfileirar a versão com falha, preservando seu ID. Para uma versão já pronta, restaura somente o arquivo e conserva páginas e IDs dos trechos. Se a restauração falhar, a versão não é recolocada na fila. No upload HTTP, abertura da conexão, transação, espera de locks, gravação do PDF e commit executam juntos no threadpool, permitindo que a API continue atendendo outras requisições.

PDFs cujo texto extraído contém caracteres nulos são marcados como `failed` antes de gravar páginas, com orientação para gerar outra cópia pesquisável. Isso preserva o texto literal dos documentos aceitos e permite que o worker continue processando os próximos arquivos da fila.

Os originais ficam no volume `documents`, por hash, e são servidos por `GET /api/documents/{version_id}/file`. Uma futura interface pode acrescentar `#page=2` ao URL para abrir uma página física. Reenvios não alteram IDs de versões já prontas nem suas citações.

Esta fundação mantém `code`, `version`, tipo, camada, fase e datas como campos opcionais. A leitura automática de cabeçalhos, a associação de edições de um mesmo documento e a detecção de metadados conflitantes pertencem à evolução da ingestão. Nesta etapa cada PDF distinto recebe sua própria identidade documental; nenhuma versão ou vigência é inferida pelo nome do arquivo. Fatos curados têm estrutura persistente, mas não são criados automaticamente.

## Identidade e autorização

O simulador é habilitado explicitamente por `AUTH_DEMO_ENABLED=true`. As contas fictícias e seus perfis ficam no JSON `AUTH_DEMO_USERS` do `.env`. O frontend inicial identifica a simulação e permite selecionar uma dessas contas; isso não é um provedor corporativo real.

`POST /api/auth/demo/session` aceita somente `user_id` de uma conta configurada e emite cookie `HttpOnly`, `SameSite=Strict`, com validade de uma hora. O servidor valida assinatura HS256, emissor, público e validade antes de resolver a identidade em `GET /api/auth/me`. Nome e perfil enviados pelo navegador não concedem permissões. Sem sessão, as rotas de domínio retornam 401; sem permissão, o upload retorna 403.

`empregado` e `gestor` recebem `documents:read`. `gestao` também recebe `documents:ingest` e `facts:curate`. Essas permissões são derivadas no servidor. A alteração de perspectiva visual não altera autorização. Com o simulador desativado, suas rotas retornam 404 e sessões simuladas não são aceitas. A integração com IdP real e cookies HTTPS será implementada separadamente; este Compose é para desenvolvimento local.

## Contratos compartilhados

`backend/app/contracts.py` é a fonte dos modelos de ingestão, citação, pergunta/resposta, identidade, perfis e permissões. `packages/contracts/openapi.json` publica o OpenAPI e `packages/contracts/index.d.ts` publica os tipos TypeScript usados pelo React, sem duplicar interfaces manualmente.

O contrato de consulta aceita `perspective` opcional (`deadline`, `value`, `obligation` ou `risk`) e filtro por área em `filters.area`. `deadline` corresponde a Prazos e `value` a Valores; as demais perspectivas ficam previstas para evolução. Os campos são opcionais para manter compatibilidade com perguntas apenas por tema, texto e data. Exemplo de entrada válida:

```json
{
  "topic_id": "00000000-0000-0000-0000-000000000001",
  "question": "Qual o prazo de solicitação?",
  "perspective": "deadline",
  "filters": {"area": "GGC"}
}
```

O erro 422 do upload declara tanto `detail` textual (PDF ou tema não aceito) quanto a lista de erros de validação dos campos. O download declara corpo binário `application/pdf` no OpenAPI e nos tipos gerados.

```sh
docker compose run --rm --no-deps api python -m app.export_contracts > packages/contracts/openapi.json
docker compose run --rm --no-deps frontend npm run contracts:generate
```

A CI verifica se os arquivos gerados correspondem aos fontes. `POST /api/questions` disponibiliza o contrato e retorna 501 até a implementação da consulta em issue própria. A tela inicial também é uma base técnica: upload na interface, respostas, sínteses e divergências serão implementados nos respectivos cartões.

## Validação em ambiente isolado

Use um projeto Compose separado, sem worker concorrente durante os testes. Os volumes desse projeto não compartilham os dados do ambiente de desenvolvimento.

```sh
docker compose -p ipbot-test build
docker compose -p ipbot-test up -d db
docker compose -p ipbot-test run --rm migrate
docker compose -p ipbot-test run --rm --no-deps api ruff check backend
docker compose -p ipbot-test run --rm --no-deps api ruff format --check backend
docker compose -p ipbot-test run --rm --no-deps api pytest backend/tests
docker compose -p ipbot-test run --rm --no-deps frontend npm run build
docker compose -p ipbot-test down -v
```

Os testes usam PostgreSQL real e PDFs sintéticos gerados na hora. Cobrem página física após página vazia, trecho literal, reenvio concorrente, falha sem páginas parciais, reprocessamento e acesso por perfil. As regressões também verificam atendimento de requisições durante upload bloqueado, restauração de original ausente sem alterar citações, novas migrações e múltiplos heads, perspectiva e área na consulta e os formatos de resposta publicados no OpenAPI. A CI também sobe todos os serviços e aguarda os healthchecks.

Para atualizar dependências Python, edite `backend/requirements.in` e gere o lock com `uv pip compile backend/requirements.in --python-version 3.12 --output-file backend/requirements.txt --upgrade`. O frontend usa `npm ci` e `package-lock.json` versionado.

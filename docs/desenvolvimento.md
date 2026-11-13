# Ambiente de desenvolvimento e ingestão · issues #8 e #9

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

Também é possível configurar `COLLECTION_PATH=/caminho/absoluto/documentos_desafio_2` no `.env` e executar:

```sh
docker compose --profile tools run --rm importer
```

O importador usa a pasta configurada como montagem somente leitura. `ferias`, `inovacao` e `locacao` aparecem como Férias, Inovação e Locação; outras subpastas conservam o nome. PDFs de `substituidos/` herdam o tema da pasta superior. O catálogo da raiz não é importado. Os PDFs continuam fora do repositório.

O comando imprime uma linha JSON por arquivo com ID da versão, estado e indicação de duplicação. O êxito confirma o enfileiramento. Acompanhe a conclusão em `GET /api/documents?topic_id=…`. Arquivos rejeitados causam saída 1 sem impedir os demais. Repetir o comando restaura originais ausentes ou corrompidos e recoloca versões com falha na fila.

A API fornece código, título da edição, versão, fase, tipo, vínculos, datas declaradas, estado e progresso por página de cada arquivo. Falhas incluem um motivo legível. Fase “Vigente” não é convertida automaticamente em aplicabilidade temporal. A tela de Gestão em `/documentos` será integrada pelo trabalho de frontend, seguindo o design do projeto; esta entrega não inclui essa interface.

O CLI é uma ferramenta administrativa local com acesso direto ao banco. O upload HTTP exige `documents:ingest`. Rotas:

- `GET /api/topics`: lista os temas disponíveis.
- `GET /api/documents?topic_id=…`: lista versões, metadados, `status`, `processed_pages`, `page_count` e `error` para acompanhamento por arquivo.
- `POST /api/topics`: JSON com `name`, cria ou reutiliza um tema.
- `POST /api/documents`: multipart com `topic_id` e `file`.
- `POST /api/documents/batch`: multipart com `topic_id` e vários campos `files`; retorna um resultado ou erro por arquivo, preservando a ordem.
- `POST /api/documents/{version_id}/retry`: tenta novamente com o original armazenado; se estiver ausente ou corrompido, orienta reenviar o PDF.

O frontend pode enviar arquivos pelo endpoint individual ou pelo endpoint de lote e acompanhar as versões pela listagem de documentos. Upload, lote e importação chamam `app.ingestion.enqueue` e compartilham o worker. O limite é 25 MiB por PDF. O pypdf extrai o texto por página, sem OCR, extração de fatos ou chamadas externas. Páginas vazias conservam sua posição e não geram trechos vazios.

O cabeçalho ACME fornece código, versão, tipo, título, fase, vigência e vínculos explícitos (`Vinculado a` e `Referência`). Códigos iguais no mesmo tema compartilham uma identidade documental; cada edição conserva seu título e metadados. Um código/versão já publicado com bytes diferentes é marcado como falha, com orientação para conferir a edição. Documentos fora desse padrão continuam pesquisáveis, com metadados ausentes, sem inferência pelo nome do arquivo. Datas de aprovação e assinatura não são usadas como início de vigência.

O recorte respeita itens numerados, cláusulas, anexos, tabelas e blocos. Não divide itens pelo tamanho em caracteres. Quando um item continua na página seguinte, conserva o identificador da seção em uma passagem daquela página. Cada trecho é uma substring literal do texto extraído da página física; tabelas e fluxogramas conservam o texto disponível no PDF, sem reconstrução ou OCR.

O hash SHA-256 por tema evita duplicação inclusive entre chamadas concorrentes. Reenviar uma versão pronta conserva IDs de páginas e trechos. Antes de reutilizar o original, a ingestão verifica seu hash e restaura atomicamente os bytes recebidos quando necessário. O worker também verifica o hash antes da extração. Caracteres nulos e PDFs sem texto extraível geram falha legível, sem publicação parcial.

A seleção usa `FOR UPDATE SKIP LOCKED` e um advisory lock de sessão por versão. O estado `processing` e o progresso são visíveis em transações curtas, enquanto páginas, trechos e `ready` são publicados atomicamente em outra transação. A queda da conexão libera o advisory lock e permite retomar uma versão em `processing`, sem duplicar citações. Falhas de extração ou persistência revertem a publicação e não bloqueiam o próximo arquivo.

Os originais ficam no volume `documents`, por hash, e são servidos por `GET /api/documents/{version_id}/file`. Acrescente `#page=2` para abrir uma página física. Fatos curados não são criados automaticamente; a curadoria pertence à issue #14.

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

A CI verifica se os arquivos gerados correspondem aos fontes. `POST /api/questions` disponibiliza o contrato e retorna 501 até a implementação da consulta em issue própria. Os endpoints de ingestão estão disponíveis para integrar upload e acompanhamento à tela de Gestão. A interface segue o trabalho de frontend; respostas, sínteses e divergências pertencem aos respectivos cartões.

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

Os testes usam PostgreSQL real e PDFs sintéticos gerados na hora. Cobrem página física após página vazia, trecho literal, reenvio concorrente, falha sem páginas parciais, reprocessamento e acesso por perfil. A ingestão verifica cabeçalhos, edições do mesmo documento, itens longos, cláusulas, progresso visível, recuperação após queda e rejeições isoladas no lote. As regressões também verificam atendimento de requisições durante upload bloqueado, restauração de original ausente sem alterar citações, novas migrações e múltiplos heads, perspectiva e área na consulta e os formatos de resposta publicados no OpenAPI. A CI também sobe todos os serviços e aguarda os healthchecks.

Para atualizar dependências Python, edite `backend/requirements.in` e gere o lock com `uv pip compile backend/requirements.in --python-version 3.12 --output-file backend/requirements.txt --upgrade`. O frontend usa `npm ci` e `package-lock.json` versionado.

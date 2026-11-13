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

O comando imprime uma linha JSON por arquivo com ID da versão, estado e indicação de duplicação. O êxito confirma o enfileiramento. Acompanhe a conclusão em `GET /api/documents?topic_id=…`. Arquivos rejeitados ou retornados com `status=failed` causam saída 1, mesmo sem exceção, sem impedir a tentativa dos demais arquivos. Saída 0 indica enfileiramento ou reutilização sem falha conhecida; a extração posterior ainda deve ser acompanhada na API. Repetir o comando restaura originais ausentes ou corrompidos e recoloca falhas recuperáveis na fila; conflitos legados mantêm o aviso para revisão.

A API fornece código, título da edição, versão, fase, tipo, vínculos, datas declaradas, estado e progresso por página de cada arquivo. Falhas incluem um motivo legível. Fase “Vigente” não é convertida automaticamente em aplicabilidade temporal. A tela de Gestão em `/documentos` será integrada pelo trabalho de frontend, seguindo o design do projeto; esta entrega não inclui essa interface. A issue #9 deve permanecer aberta até a integração e validação do fluxo na interface.

O CLI é uma ferramenta administrativa local com acesso direto ao banco. O upload HTTP exige `documents:ingest`. Rotas:

- `GET /api/topics`: lista os temas disponíveis.
- `GET /api/documents?topic_id=…`: lista versões, metadados, `status`, `processed_pages`, `page_count` e `error` para acompanhamento por arquivo.
- `POST /api/topics`: JSON com `name`, cria ou reutiliza um tema.
- `POST /api/documents`: multipart com `topic_id` e `file`.
- `POST /api/documents/batch`: multipart com `topic_id` e vários campos `files`; retorna um resultado ou erro por arquivo, preservando a ordem.
- `POST /api/documents/{version_id}/retry`: tenta novamente com o original armazenado; se estiver ausente ou corrompido, orienta reenviar o PDF.

O frontend pode enviar arquivos pelo endpoint individual ou pelo endpoint de lote e acompanhar as versões pela listagem de documentos. O lote retorna um resultado por arquivo também quando há falha de banco: arquivos já confirmados permanecem na fila, o arquivo que falhou recebe uma mensagem para reenvio e os seguintes são tentados em transações próprias. Upload, lote e importação chamam `app.ingestion.enqueue` e compartilham o worker. O limite é 25 MiB por PDF. O pypdf extrai o texto por página, sem OCR, extração de fatos ou chamadas externas. Páginas vazias conservam sua posição e não geram trechos vazios.

O cabeçalho ACME fornece código, versão, tipo, título, fase, vigência e vínculos explícitos (`Vinculado a` e `Referência`). Códigos iguais no mesmo tema compartilham uma identidade documental; cada edição conserva seu título e metadados. Um código/versão já publicado com bytes diferentes é marcado como falha, com orientação para conferir a edição. Documentos fora desse padrão continuam pesquisáveis, com metadados ausentes, sem inferência pelo nome do arquivo. Datas de aprovação e assinatura não são usadas como início de vigência.

O recorte respeita itens numerados, cláusulas, anexos, tabelas e blocos. Não divide itens pelo tamanho em caracteres. Quando um item continua na página seguinte, conserva o identificador da seção em uma passagem daquela página. Cada trecho é uma substring literal do texto extraído da página física; tabelas e fluxogramas conservam o texto disponível no PDF, sem reconstrução ou OCR.

A migração `0003` preenche os metadados das versões prontas importadas antes desta entrega usando o texto da primeira página já persistida. Ela agrupa as edições pelo código e conserva os IDs das versões, páginas e trechos, o conteúdo literal e os vínculos com fatos curados. Não depende de originais disponíveis em disco. Versões sem cabeçalho recebem o nome do arquivo como título, mantendo os demais campos ausentes. Se dois PDFs legados de conteúdo diferente declaram o mesmo código e versão, a primeira fonte importada permanece `ready` e a posterior recebe `status=failed` e um `error` com o código, a versão e o ID da fonte conflitante. Seus metadados são preenchidos e o original, páginas, trechos e vínculos curados são preservados; a migração continua com os demais arquivos. O registro fica visível na listagem para revisão pela Gestão, e seu original continua acessível. Falhas técnicas inesperadas ainda revertem a transação, sem alterar as citações publicadas. Reverter para `0002` conserva os metadados corrigidos.

Reenviar ou reimportar uma versão pronta ainda sem metadados também a atualiza a partir da página armazenada, sem reenfileirar o documento nem recriar suas citações. Os recortes legados são preservados; os novos documentos usam o recorte por item ou cláusula. Reenviar ou tentar novamente uma fonte legada conflitante conserva seu estado e seu erro, sem enfileirar uma nova extração sobre as citações existentes. A Gestão precisa conferir e corrigir a identificação da edição antes de enviar um conteúdo corrigido. Novos arquivos com a mesma identificação também são bloqueados, inclusive quando a outra fonte legada está em conflito.

O hash SHA-256 por tema evita duplicação inclusive entre chamadas concorrentes. Reenviar uma versão pronta conserva IDs de páginas e trechos. Antes de reutilizar o original, a ingestão verifica seu hash e restaura atomicamente os bytes recebidos quando necessário. O worker também verifica o hash antes da extração. Caracteres nulos e PDFs sem texto extraível geram falha legível, sem publicação parcial.

A seleção usa `FOR UPDATE SKIP LOCKED` e um advisory lock de sessão por versão. O estado `processing` e o progresso são visíveis em transações curtas, enquanto páginas, trechos e `ready` são publicados atomicamente em outra transação. A queda da conexão libera o advisory lock e permite retomar uma versão em `processing`, sem duplicar citações. Falhas de extração ou persistência revertem a publicação e não bloqueiam o próximo arquivo.

Os originais ficam no volume `documents`, por hash, e são servidos por `GET /api/documents/{version_id}/file`. Acrescente `#page=2` para abrir uma página física. Fatos curados não são criados pela ingestão; a curadoria é uma etapa própria, descrita abaixo.

## Fatos curados e regras · issue #14

`backend/app/fatos/catalogo.py` registra os fatos de Férias e Inovação revisados manualmente contra os PDFs do acervo, para as perspectivas Prazos (`deadline`) e Valores (`value`). Cada fato guarda atributo normalizado, área, enunciado, responsável, valor numérico, valor como aparece na fonte (`value_text`), unidade, período (`starts_on`/`ends_on`) e condições. Cada fonte aponta documento, versão, página física, item e o trecho literal revisado. A migração `0004` acrescenta esses campos a `curated_facts` e `fact_citations`.

Depois de importar o acervo e concluir a extração, publique o catálogo:

```sh
docker compose run --rm api python -m app.fatos.curadoria --strict
```

A Gestão também pode publicar por `POST /api/fatos/curadoria`, que exige o perfil `gestao`. A publicação localiza cada trecho na passagem da edição exata revisada, que precisa estar `ready`, tolerando só diferenças de espaço e quebra de linha, e grava o texto literal encontrado. Um fato cuja fonte não é encontrada fica `pending`, com o motivo, e não é apresentado. Uma nova ingestão nunca cria fatos e uma nova edição não herda os fatos da anterior: atualizar a fonte exige revisar o catálogo e publicá-lo outra vez. Repetir a publicação é idempotente, e chaves retiradas do catálogo deixam de ser exibidas nos temas que ele cobre. Com o acervo de referência, os 59 fatos são publicados sem pendências.

`GET /fatos` (alias `GET /api/fatos`) aceita `categoria` (`deadline`, `value`, `obligation` ou `risk`), `assunto` (ID do tema) e `area` (sem diferenciar maiúsculas). A resposta traz os fatos na ordem do catálogo, com `tags` como `jornada`, `linha_do_tempo`, `grafico_orcamento` e `alcada` para os visuais, e cada citação no formato canônico de evidência. Obrigações, Riscos e Locação ainda não têm curadoria e retornam lista vazia; a extração automática fica para a evolução (#24).

Os cálculos rodam em código, com parâmetros lidos dos fatos curados. Cada passo devolve o resultado, a demonstração (`computation`) e as citações dos fatos usados. Sem os fatos necessários, a rota responde 409.

| Rota | Cálculo |
| --- | --- |
| `POST /ferias/calcular` (alias `POST /api/regras/ferias/prazos`) | A partir do início de gozo: dia vedado, D-45, decisões do gestor e do diretor, D-35, assinatura, pagamento antecipado para o dia útil anterior e marcos de alteração. Aceita `holidays`, `request_registered_on` e `notice_received_on`. |
| `POST /api/regras/ferias/ausencia-simultanea` | 30% da equipe, arredondado para baixo, com mínimo de 1. |
| `POST /api/regras/ferias/dias-por-faltas` | Faixa da Tabela 1 do TB_1111-001. |
| `POST /api/regras/ferias/ressarcimento` | Ressarcimento limitado a R$ 2.500,00 por evento. |
| `POST /api/regras/inovacao/alcada` | Faixas de R$ 18.000,00 e R$ 120.000,00 por ideia. |
| `GET /api/regras/inovacao/orcamento` | Soma dos itens, R$ 24.000,00 de premiações dentro dos R$ 96.000,00 de orçamento total e participação de cada item. Divergências entre as fontes aparecem em `warnings`. |
| `GET /api/regras/inovacao/pagamento-premiacao` | Premiação em 30/06/2027 + 30 dias. |

O acervo não traz o calendário de feriados da sede. Os dias úteis excluem sábados, domingos e os feriados informados em `holidays`, e a resposta registra essa premissa. O exemplo 1 do Anexo C da NG_111 é coberto pelos testes. A divergência AC-03 entre a NG_111 (D-35) e o PX_1111-001 (item 8.4.2) é tratada na #15.

## Identidade e autorização

O simulador é habilitado explicitamente por `AUTH_DEMO_ENABLED=true`. As contas fictícias e seus perfis ficam no JSON `AUTH_DEMO_USERS` do `.env`. O frontend inicial identifica a simulação e permite selecionar uma dessas contas; isso não é um provedor corporativo real.

Com `AUTH_DEMO_ENABLED=true`, a interface lista as três contas fictícias de `AUTH_DEMO_USERS`. `POST /api/auth/demo/assertion` recebe apenas o identificador escolhido e devolve um token assinado pelo simulador, válido por 60 segundos. `POST /auth/callback` recebe esse token no corpo JSON e valida assinatura, emissor, público e validade antes de criar uma sessão de 15 minutos. `GET /eu` devolve a identidade da sessão. Os contratos `/api/auth/demo/session` e `/api/auth/me` continuam disponíveis para os consumidores da fundação.

Os grupos `clause-empregados`, `clause-gestores` e `clause-gestao-acervo` correspondem a `empregado`, `gestor` e `gestao`. Quando há mais de um grupo reconhecido, vale a ordem Gestão, gestor, empregado. Todos os perfis autenticados consultam o mesmo acervo e podem abrir o PDF diretamente em `GET /api/documents/{version_id}/file`. O servidor responde 401 sem sessão válida e 403 quando a conta não pertence à Gestão em upload e alertas completos. A rota `/conflitos` aplica essa proteção e reserva a resposta dos alertas para a #15. O seletor **Ver para** muda a perspectiva exibida, sem modificar a sessão.

`scripts/init_env.py` cria as contas e duas chaves distintas no `.env` local. Se você já tem um `.env` da #8, acrescente uma chave aleatória de pelo menos 32 caracteres em `AUTH_DEMO_SSO_SECRET`, troque o campo `role` de cada conta por `groups` com a lista de grupos acima e ajuste `AUTH_COOKIE_SECURE=false` para HTTP local. Em HTTPS mantenha `AUTH_COOKIE_SECURE=true`. O cookie usa `HttpOnly` e `SameSite=Strict`. Com a demo desativada, o simulador e o callback retornam 404 e os cookies simulados deixam de ser aceitos.

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

A CI verifica se os arquivos gerados correspondem aos fontes. `POST /api/questions` e `POST /perguntar` executam a consulta extrativa autenticada. Os endpoints de ingestão estão disponíveis para integrar upload e acompanhamento à tela de Gestão. A interface inclui consulta e painel de evidência; sínteses e divergências seguem nos respectivos cartões.

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

Os testes usam PostgreSQL real e PDFs sintéticos gerados na hora. Cobrem página física após página vazia, trecho literal, reenvio concorrente, falha sem páginas parciais, reprocessamento e acesso por perfil. A ingestão verifica cabeçalhos, edições do mesmo documento, itens longos, cláusulas, progresso visível, recuperação após queda, falha de banco no meio do lote e permissões do SSO para upload, lote, reenvio e criação de temas. A atualização de metadados é testada com versões prontas no schema `0001`, incluindo citações curadas e recuperação transacional após falha. As regressões também verificam atendimento de requisições durante upload bloqueado, restauração de original ausente sem alterar citações, novas migrações e múltiplos heads, perspectiva e área na consulta e os formatos de resposta publicados no OpenAPI. A CI também sobe todos os serviços e aguarda os healthchecks.

Para atualizar dependências Python, edite `backend/requirements.in` e gere o lock com `uv pip compile backend/requirements.in --python-version 3.12 --output-file backend/requirements.txt --upgrade`. O frontend usa `npm ci` e `package-lock.json` versionado.


## Perguntas e evidências (#10)

A tela Consulta envia tema, pergunta, perspectiva, área e data para `POST /perguntar`
(também disponível em `POST /api/questions`). Os mesmos perfis com acesso ao acervo podem consultar.
A busca usa o índice `tsvector` em português, ranqueia os trechos e preserva seu texto literal.
O filtro de área exige a presença textual da área no trecho; as perspectivas restringem por
vocabulário de prazos, valores, obrigações ou riscos. Não há inferência de área ou responsável.

As perguntas são separadas em pontos por `?`, `;`, quebra de linha ou ` e `, com até 12 pontos.
A classificação `supported` exige evidência para cada ponto da pergunta. A recuperação usa
expansões de vocabulário; a confirmação usa separadamente a ação e a medida da mesma afirmação.
Pedir, solicitar e solicitação compartilham uma ação, e prazo e antecedência compartilham um
marcador temporal. O título da versão fornece o contexto documental (por exemplo, Férias),
sem substituir a evidência da ação e do número no item. O texto literal apresentado não muda.

Para prazo ou valor, a medida precisa seguir um marcador da mesma ação. Comparações,
encaminhamentos e frases que misturam ações diferentes continuam parciais: os 45 dias de
solicitação não confirmam o prazo de cancelamento. Qualificadores e condições após a medida
são preservados, como “antecedência mínima de 45 dias corridos do início de gozo” no item 4.3.1
original. As quebras de linha da extração não interrompem a afirmação. A classificação não
exige igualdade literal entre o sujeito da frase e a pergunta.

São recuperados até 48 candidatos por ponto e priorizados até oito trechos verificáveis,
com evidências confirmadas antes das apenas relacionadas. `partial` indica pontos sem
confirmação completa; `insufficient` indica ausência de trechos verificáveis. As lacunas não
são preenchidas pelo modelo. O reconhecimento é local e limitado ao vocabulário e às relações
tratadas pelo extrator; não equivale a uma análise semântica irrestrita. Não há detecção de
divergências nesta issue.

Só versões `ready` do tema entram na busca. Datas explícitas limitam a elegibilidade; a data de
referência informada no campo tem prioridade. Uma única data `DD/MM/AAAA` ou `AAAA-MM-DD` na
pergunta também é reconhecida; várias datas exigem o campo explícito. Sem data, usa-se o dia
em `America/Recife`. Uma versão futura pode ser consultada escolhendo sua data de vigência.
A sucessão considera `superseded_by` ou declaração inequívoca `Substitui a v2` / `Substitui a versão
2.0.0` / `Substitui a NG_111 versão 2.0.0` na primeira página do mesmo documento, com início
confirmado da sucessora. Quando a declaração inclui um código, ele precisa corresponder ao
documento substituído. Uma negação que governa a substituição (inclusive “não\nsubstitui”) ou
rejeita a própria afirmação não estabelece sucessão. Negar outra ação, como “sem alterar os
procedimentos” depois da versão citada, preserva a sucessão afirmativa. A fase “Versão anterior”
continua elegível antes do início da sucessora. Não se presume
substituição por ordem de upload ou maior número da edição. Fases anteriores com aplicabilidade
incerta são excluídas; sem datas em uma fonte corrente, a interface mostra a ausência do intervalo.
Regras temporais mais amplas seguem no cartão de vigência.

Cada citação contém documento, ID imutável da versão, ID do trecho, título, versão declarada,
página física (começando em 1), item/cláusula quando identificado e trecho literal conferido
contra a página persistida. `GET /api/citations/{passage_id}` resolve a evidência autenticada
sem aplicar os filtros da nova consulta. `GET /api/documents/{version_id}/file#page=N` abre o
mesmo PDF, inclusive após a entrada da sucessora. Retornar da evidência mantém a resposta.

### Bedrock opcional

Sem `BEDROCK_MODEL_ID`, nenhuma chamada AWS é feita. Para habilitar, configure esse campo,
`BEDROCK_REGION` e credenciais AWS pelas variáveis do ambiente (`AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY` e, se necessário, `AWS_SESSION_TOKEN`), com permissão de invocação
para o modelo escolhido. Não versione credenciais. A integração usa a
[API Converse oficial](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html).

O modelo só pode selecionar trechos completos recebidos, sem reescrever nem recortar condições
ou negações. IDs desconhecidos, texto alterado, resposta vazia ou inválida, erro de autenticação,
indisponibilidade e timeout retornam os trechos locais originais, com um aviso curto.
O timeout de leitura é `BEDROCK_TIMEOUT_SECONDS` (padrão 5 s, entre 1 e 30), o de conexão
é 2 s, sem retentativas da invocação. A recuperação no PostgreSQL acontece antes da chamada;
a geração nunca decide elegibilidade, lacunas ou URLs das fontes. Todos os trechos recuperados
continuam acessíveis na tela, mesmo quando o modelo seleciona apenas alguns. Antes de aceitar
a seleção, o backend exige na resposta principal ao menos uma evidência que confirma cada ponto
confirmado e uma evidência relacionada a cada ponto parcial recuperado. Se o modelo omitir um
desses pontos ou escolher apenas uma fonte relacionada para um ponto confirmado, retorna a
resposta extrativa completa com o aviso de contingência.

No Compose, somente a API recebe a configuração Bedrock e as credenciais AWS. Worker, migrador
e importador recebem apenas as configurações locais necessárias.

Os testes de consulta usam PDFs sintéticos para Férias, Inovação e Locação e PostgreSQL real.
Cobrem filtros, respostas parciais, ausência de evidência, data histórica, sucessão, literalidade,
página física após página vazia, autenticação e continuação por contingência. O Bedrock é simulado
nos testes; nenhuma credencial ou chamada AWS real é necessária.

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
solicitação não confirmam o prazo de cancelamento. Uma ação mencionada somente em uma
exceção (“salvo”, “exceto”, “com exceção de”) não recebe o prazo ou valor da regra geral.
A confirmação avalia a oração afirmativa, incluindo exceções iniciais ou intercaladas, e a
citação continua exibindo a condição completa. Uma regra explícita na mesma frase ou em outra
frase pode confirmar a ação excluída da regra geral. Se a exceção acrescenta “quando o prazo
para cancelar férias é de 5 dias úteis”, essa atribuição é avaliada separadamente dos 45 dias
da regra geral. A confirmação exige a ação e a medida na regra específica; não transfere o
número geral para uma exceção sem prazo informado. Regras específicas entre parênteses
balanceados são isoladas antes de analisar as vírgulas da regra externa, inclusive quando a
exceção antecede a regra geral. A ação e a medida do parêntese são avaliadas juntas, sem
incorporar o número da regra geral. Parênteses sem atribuição própria ou com informação
negada não confirmam o ponto. A citação literal conserva todos os parênteses e condições.
Qualificadores e condições após a medida
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
rejeita a própria afirmação não estabelece sucessão. Incisos entre vírgulas não encerram
o alcance de “não se confirma que”; a v2 continua elegível quando a sucessão é incerta.
Negar outra ação, como “sem alterar os
procedimentos” depois da versão citada, preserva a sucessão afirmativa. A fase “Versão anterior”
continua elegível antes do início da sucessora. Não se presume
substituição por ordem de upload ou maior número da edição. Fases anteriores com aplicabilidade
incerta são excluídas; sem datas em uma fonte corrente, a interface mostra a ausência do intervalo.
A mesma classificação alimenta a tela de vigência (#13), descrita abaixo.

Cada citação contém documento, ID imutável da versão, ID do trecho, título, versão declarada,
página física (começando em 1), item/cláusula quando identificado e trecho literal conferido
contra a página persistida. `GET /api/citations/{passage_id}` resolve a evidência autenticada
sem aplicar os filtros da nova consulta. `GET /api/documents/{version_id}/file#page=N` abre o
mesmo PDF, inclusive após a entrada da sucessora. Retornar da evidência mantém a resposta.

### Bedrock opcional

Sem `BEDROCK_MODEL_ID`, nenhuma chamada AWS é feita. O modelo inicial sugerido é
**Claude Haiku 4.5**, com `BEDROCK_REGION=us-east-1` e
`BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0`, se disponível para a conta.
O campo aceita ID ou ARN de modelo/perfil compatível com a
[API Converse](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html).
Confira a [disponibilidade do Haiku 4.5](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html)
antes de escolher outro perfil/região. Não é necessário provisionar Knowledge Bases ou embeddings.

Requisitos para a validação real (não exigidos pelos testes simulados):

- Credenciais disponíveis no ambiente da API pela cadeia padrão do boto3: role da aplicação,
  perfil AWS local ou credenciais temporárias. Não envie chaves por chat nem as versione.
- `bedrock:InvokeModel` no modelo e, quando utilizado, no perfil de inferência. Para perfis entre
  regiões, autorize também os modelos nas regiões de destino e confira bloqueios por SCP.
  Use a [documentação de permissões de perfis](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-prereq.html)
  para restringir os ARNs da conta; a aplicação não precisa criar ou listar perfis.
- Modelo habilitado para a conta, requisitos iniciais da Anthropic e eventual assinatura
  Marketplace resolvidos por um administrador. Essas permissões de ativação não precisam
  permanecer na role da aplicação. Veja [acesso a modelos](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).
- Rede HTTPS até `bedrock-runtime` na região escolhida e cota disponível para inferência.

A [política de exemplo](aws/bedrock-invoke-policy.example.json) restringe a invocação ao
perfil US do Haiku 4.5 a partir de `us-east-1`. Um administrador deve substituir a conta
fictícia `111122223333` pela conta real e conferir regiões de destino e SCPs antes de anexá-la
à role. Ela não concede ativação Marketplace, administração, listagem nem streaming.

No Compose local, somente a API recebe `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e
`AWS_SESSION_TOKEN` do ambiente; perfis SSO do host não são montados automaticamente.
Para executar fora do Docker, boto3 também encontra perfis por `AWS_PROFILE`.
Em produção, use a role do serviço e a cadeia de credenciais correspondente ao ambiente.
Worker, migrador e frontend não recebem credenciais Bedrock.

Após configurar o ambiente, execute o preflight **no mesmo ambiente da API**:

```sh
docker compose run --rm --no-deps api python -m app.check_bedrock
```

O comando realiza uma chamada faturável pequena, com pergunta e evidência sintéticas, e valida
as citações recebidas. Não envia o acervo nem altera IAM ou assinaturas. Retorna JSON com
região, modelo e disponibilidade; código 0 significa invocação e validação bem-sucedidas,
1 indica falha (por exemplo, `AccessDeniedException`, `ThrottlingException` ou timeout) e
2 indica modelo não configurado ou configuração inválida. Na configuração inválida, retorna
`error=configuration_error` e apenas o nome do campo raiz e o tipo de validação (ou a classe
do erro de parsing), sem valores, contexto, mensagens ou traceback. Mensagens remotas e
credenciais não são impressas.
Sem executar esse comando com credenciais válidas, o acesso real permanece não verificado.

O modelo recebe a pergunta, a mesma data efetiva resolvida para a busca (inclusive quando
omitida no pedido), perspectiva, filtros e somente os trechos já elegíveis e
conferidos contra as páginas persistidas. Documentos e pergunta são tratados como dados;
a instrução de sistema proíbe seguir comandos documentais, completar lacunas ou calcular.
O backend aceita JSON puro ou envolvido em uma única cerca Markdown (`json` ou sem linguagem),
sem prosa antes ou depois. O conteúdo continua exigindo afirmações literais completas e IDs únicos presentes nas
evidências. Metadados (versão, página, item e trecho) sempre vêm do banco. Lacunas e situação
da resposta continuam calculadas localmente. A seleção precisa manter evidência de cada
ponto recuperado, inclusive os pontos com confirmação completa.

No MVP a organização é feita por seleção e ordenação de trechos; não se valida uma paráfrase
arbitrária apenas pela existência de uma citação. Isso preserva condições e negações.
Os cálculos de datas e valores continuam em `app.regras` e nos endpoints `/api/regras/*`, com
fatos curados, premissas e memória de cálculo. A consulta também permite um cálculo explícito
em `calculation`, sem interpretar parâmetros numéricos por LLM nem aceitar resultados do cliente.
Não há extração automática de fatos ou detecção geral de conflitos.

### Explicar um cálculo na consulta

`POST /perguntar` (ou `/api/questions`) aceita `calculation` opcional. Informe a regra e seus
parâmetros tipados. Exemplo, substituindo o UUID pelo tema que contém os fatos curados:

```json
{
  "topic_id": "00000000-0000-4000-8000-000000000019",
  "question": "Explique o ressarcimento para uma despesa de R$ 3.000,00.",
  "reference_date": "2026-11-13",
  "calculation": {"rule": "ferias.ressarcimento", "amount": 3000}
}
```

Regras disponíveis e parâmetros (iguais aos endpoints `/api/regras/*`):

- `ferias.prazos`: `start_date`, opcionais `holidays`, `request_registered_on`, `notice_received_on`.
- `ferias.ausencia_simultanea`: `team_size`.
- `ferias.dias_por_faltas`: `absences`.
- `ferias.ressarcimento` e `inovacao.alcada`: `amount`.
- `inovacao.orcamento` e `inovacao.pagamento_premiacao`: sem parâmetros adicionais.

A regra explícita define a operação; o texto da pergunta fornece contexto para sua apresentação.
Pedidos com cálculo são dedicados a essa operação, sem executar busca textual para outras perguntas
no mesmo texto. Para consultar outro ponto, faça um pedido separado sem `calculation`.
O servidor executa o mesmo motor Python das rotas de regras usando somente fatos curados do
tema e do filtro de área, com todas as fontes em versões elegíveis na data efetiva.
A perspectiva textual não filtra os fatos necessários a uma regra explícita, inclusive quando
um cliente da API envia `perspective` junto de `calculation`. Cada citação é
reconferida contra a página persistida; sem todos os parâmetros curados elegíveis, retorna
lacuna e não chama o Bedrock. O cliente não pode enviar resultados, memória ou citações.

A resposta inclui `calculation` (`RuleResult`) com resultados numéricos/datas, memória de cálculo,
avisos, premissas e fontes. O modelo recebe essa estrutura e explicações determinísticas de cada
passo para organizar a apresentação. Afirmações calculadas usam `calculation_step` (índice começando
em zero) e devem copiar a explicação inteira correspondente. O backend rejeita números, unidades,
memória ou fontes alterados, índices desconhecidos/duplicados e omissão de qualquer passo.
Uma citação documental sozinha não valida um resultado calculado. Avisos e premissas são preservados
fora do controle do modelo e exibidos na interface.

Sem modelo ou em contingência, a mesma resposta local conserva todos os resultados e as fontes;
com modelo, a organização pode mudar, mas a memória e as premissas permanecem iguais. O modo
`extractive` continua identificando a resposta local, incluindo resultados calculados em código.
A inferência de cálculos a partir de texto livre e novas regras (por exemplo, multa de Locação)
não são implementadas aqui. O formulário de consulta oferece **Cálculo com explicação (opcional)** com as sete regras e
campos específicos: valores monetários, tamanho da equipe, faltas, início das férias, datas
opcionais e feriados adicionados individualmente. Campos obrigatórios e limites numéricos são
validados antes do envio. Ao trocar de regra, os parâmetros são limpos; trocar de tema também
volta para **Sem cálculo**. Regras de orçamento e pagamento de premiações não exigem campos
adicionais. Ao escolher uma regra, o seletor de perspectiva é desabilitado e mostra
**Definida pela regra**; `perspective` é omitido do pedido. A perspectiva anterior é preservada
para voltar à busca textual. A pergunta, o tema, a data de referência e o filtro de área acompanham `calculation`;
**Sem cálculo** envia `calculation=null` e mantém a busca textual. O período das férias e a data
de referência são campos distintos: um alimenta a conta e o outro seleciona as fontes elegíveis.

IDs desconhecidos, duplicatas, metadados injetados, texto alterado, JSON inválido, resposta
vazia, truncamento, bloqueio de conteúdo, perda de cobertura, erros AWS e timeout preservam
a resposta extrativa completa, com aviso curto na interface. Os logs registram somente a
classe do erro, sem pergunta, trechos ou resposta remota. O cliente usa conexão de 2 segundos,
leitura de `BEDROCK_TIMEOUT_SECONDS` (1–30, padrão 5) e uma tentativa, sem retries automáticos.
Esses limites são de socket, não um deadline global que inclui resolução de credenciais.
Entradas acima de 120.000 bytes e saídas acima de 64.000 bytes também usam contingência;
não se cortam evidências para caber no modelo.

Os testes de consulta usam PDFs sintéticos para Férias, Inovação e Locação e PostgreSQL real.
Cobrem filtros, respostas parciais, ausência de evidência, data histórica, sucessão, literalidade,
página física após página vazia, autenticação e continuação por contingência. O Bedrock é simulado
nos testes; nenhuma credencial ou chamada AWS real é necessária.

## Vigência, camadas e mudanças de versão · issue #13

`GET /api/vigencia?topic_id=…&reference_date=AAAA-MM-DD` (alias `GET /vigencia`) mostra, para cada documento do tema, a situação de cada edição publicada na data de referência. Sem data, usa o dia em `America/Recife`. Qualquer perfil autenticado pode consultar; tema inexistente retorna 404. A Consulta exibe o painel **Vigência, camadas e versões**, com tema e data de referência.

A resposta separa três informações e não deriva uma da outra:

- **Fase declarada** (`declared_phase`): o rótulo impresso, como “Vigente” ou “Versão anterior”. Ele não prova aplicação em uma data.
- **Datas de vigência** (`valid_from`/`valid_until`): o intervalo do cabeçalho. Datas de aprovação ou assinatura não contam como início.
- **Substituição** (`superseded_by`/`supersedes`): sucessão declarada pela própria sucessora, com a citação do trecho que a declara. `in_effect` indica se a sucessora já começou.

`status` combina essas informações na data de referência com a mesma regra da consulta (`app/vigencia/situacao.py`), e `applicable` indica se a edição entra nas respostas:

| `status` | Significado |
| --- | --- |
| `em_vigor` | Dentro do intervalo documentado e sem sucessora em vigor. |
| `fase_declarada` | Sem datas no cabeçalho; usada porque nenhuma sucessora declarada está em vigor. A tela mostra “datas não informadas”. |
| `a_iniciar` | O intervalo documentado começa depois da data. Não é orientação vigente, mesmo com fase “Vigente”. |
| `encerrada` | O intervalo documentado terminou. |
| `substituida` | Uma sucessora declarada já começou. |
| `sem_confirmacao` | Fase de versão anterior sem início ou sucessão com data confirmada. |

Cada edição traz `explanation` e `header_citation`, o cabeçalho com fase e vigência impressas. Nenhuma versão é escondida: as anteriores continuam na lista, com suas citações e o PDF original. O documento traz `current_version_ids` (o selo “Em vigor, versão X”) e `notice`, um aviso curto de substituição feita, prevista ou de vigência a iniciar. No acervo de referência, em 13/11/2026, o `CTR_2026-012` aparece “A iniciar em 30/11/2026” e não é usado nas respostas; com data a partir de 30/11/2026, passa a `em_vigor`. Em 10/07/2026, a `NG_111 v2.0.0` aparece em vigor e a v3 como substituição prevista para 03/08/2026.

A camada (`document_layer`) vem do prefixo do código, e `links` lista os vínculos declarados no cabeçalho (`Vinculado a` e `Referência`). `document_id` fica nulo quando o documento vinculado não consta do tema. `precedence` lista declarações como “Em divergência, prevalece a NG_111” encontradas nos trechos do próprio documento, com a citação. Valem as mesmas proteções da sucessão: negação antes da declaração (inclusive “não se confirma que”) e rejeição depois dela (“não procede”) impedem a publicação. `applicable` indica se a edição que declara a precedência é aplicável na data; a tela só mostra as aplicáveis. Não se presume precedência sem declaração documental.

`changes` lista as mudanças entre edições do mesmo documento revisadas em `app/vigencia/catalogo.py`: 30 para 45 dias na `NG_111` (v2 → v3) e no `FM_1111-001` (v1 → v2), e 3 para 2 ideias no `RG_1100` (v1 → v2). Cada trecho é localizado na edição exata publicada, como na curadoria de fatos. Uma mudança com alguma fonte não encontrada não é exibida. O PDF da `RG_1100 v1.0.0` não está no acervo; por isso `previous_available` é falso e o valor anterior é citado pelo histórico da v2. `kind=version_change` identifica uma mudança de versão, que não é divergência entre fontes aplicáveis. `in_effect` indica se a edição nova é aplicável na data de referência, e `to_status`, `to_valid_from` e `to_valid_until` trazem sua situação e seu intervalo documentado. Quando ela não se aplica, a tela diz o motivo: começa depois, vigência encerrada ou substituída por edição posterior. As divergências entre fontes estão na seção seguinte.

## Divergência AC-03 por curadoria manual · issue #15

No MVP, a única divergência entre fontes apresentada é o cenário AC-03, cadastrado por curadoria manual em `app/divergencias/catalogo.py`. A `NG_111 v3.0.0` (p. 3, item 4.5.3) prevê a emissão do aviso pela GGC até D-35. O `PX_1111-001 v1.0.0` (p. 3, item 8.4.2) prevê a emissão no dia seguinte à aprovação quando ela ocorre com menos de 35 dias para o início. O próprio procedimento declara que, em divergência, prevalece a `NG_111` (p. 1, item 2.2). O IPBOT mostra as duas passagens e a precedência declarada, sem escolher uma das orientações. A detecção automática de divergências entre todos os documentos, inclusive em PDFs inéditos, pertence à evolução e não faz parte deste aceite.

`GET /api/divergencias?topic_id=…&reference_date=AAAA-MM-DD` exige o perfil `gestao` (403 para os demais). A resposta traz `curation_note`, que declara a curadoria manual, e, para cada divergência, o cenário, as condições de aplicação, a consequência, as orientações (`guidances`) com a situação da edição na data e a citação, a precedência declarada (`precedence`) e `missing_information`. Cada trecho é localizado na edição, página e item exatos revisados, como na curadoria de fatos. As citações abrem a versão e a página publicadas. `kind=source_divergence` distingue a divergência das mudanças históricas entre versões (`kind=version_change`, em `/api/vigencia`).

`status` vale:

- `confirmed`: as duas passagens foram localizadas e as duas edições são aplicáveis na data;
- `possible`: falta suporte para confirmar, como passagem não localizada ou aplicação da edição não confirmada. O dado faltante aparece em `missing_information`;
- `not_applicable`: alguma edição não se aplica na data, por exemplo antes do início do `PX_1111-001` em 10/08/2026. As passagens continuam consultáveis como fontes históricas.

Quando a precedência não é localizada, a divergência continua sendo apresentada com `precedence` nulo, e a lacuna aparece em `missing_information`. Um tema sem nenhuma das fontes revisadas não lista a divergência.

A Consulta recebe só o aviso curto, sem passagens, cenário ou precedência. `GET /api/divergencias/avisos` atende qualquer perfil autenticado e não lista divergências `not_applicable`. Em `POST /perguntar`, `divergence_notices` traz o aviso quando a resposta recupera uma das passagens. O aviso também aparece quando a pergunta menciona o assunto curado (“aviso”) e cita uma das edições envolvidas. Os painéis de pergunta e de vigência exibem esse aviso. O painel **Gestão · Divergências entre fontes** aparece só para quem tem `alerts:read-details`.

Com o acervo de referência importado, o AC-03 é confirmado em 13/11/2026, com as citações `NG_111 · 3.0.0 · p. 3 · 4.5.3`, `PX_1111-001 · 1.0.0 · p. 3 · 8.4.2` e `PX_1111-001 · 1.0.0 · p. 1 · 2.2`.

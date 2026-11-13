# Handoff para o Kiro

Atualizado em 13/11/2026. Trabalho da issue #12 (Consulta e Gestão no React).

## Branch e commits

Branch `feat/12-consulta-gestao-react`, criada de `origin/dev` `19d2712` e atualizada por merge com `origin/dev` `7db0c8b`, que já contém a #15 (PR #33). PR em rascunho para `dev`. Ver `git log origin/dev..`.

| Commit | Conteúdo |
| --- | --- |
| `ef20264` | `feat(frontend)`: Consulta e Gestão com upload e evidência |
| `8d52043` | `docs(kiro)`: steering e handoff |
| `4229ffc` | `fix(frontend)`: título `<h1>`, status `divergent` e falha de rede no "Tentar novamente" |
| `e5ac359` | `docs(kiro)`: handoff com ambiente local e revisão |
| `af148d0` | `chore(ambiente)`: `scripts/dev-local.sh` e `docs/ambiente-sem-docker.md` |
| merge | `origin/dev` (#15), com resolução dos conflitos previstos |
| `fix(ambiente)` | `stop` do ambiente local passa a encerrar o grupo de processos |

## O que mudou

| Arquivo | Mudança |
| --- | --- |
| `frontend/src/main.tsx` | Navegação Consulta/Gestão. Identidade de `/eu`, sem formulário de login; o SSO simulado só oferece contas fictícias. A aba Gestão aparece com `documents:ingest` ou `alerts:read-details`; o upload exige a primeira e o painel de divergências da #15, a segunda. As áreas ficam montadas e só são ocultadas, preservando a resposta da Consulta. "Ver para" agrupado na Consulta, com aviso de que não altera permissões |
| `frontend/src/ManagementPanel.tsx` (novo) | Upload individual ou em lote, resultado por arquivo (enfileirado, duplicado, inválido), versões do tema com código, título, versão, tipo, fase, vigência documentada, estado e progresso, atualização automática enquanto houver fila, motivo da falha, "Tentar novamente", "Abrir PDF original" e criação de tema |
| `frontend/src/QuestionPanel.tsx` | Resposta primeiro: situação, aviso curto de geração indisponível (`notice`), aviso curto de divergência (#15), afirmações com a fonte logo abaixo. Em respostas `partial` e `insufficient`, as lacunas aparecem antes dos trechos, identificados como relacionados. Metadados depois. Registra a visão escolhida |
| `frontend/src/app.css` (novo) | Estilos da navegação e da Gestão, separados de `style.css` |
| `scripts/dev-local.sh`, `docs/ambiente-sem-docker.md` (novos) | Ambiente local sem Docker com PostgreSQL 16 exclusivo de desenvolvimento, caminhos e portas configuráveis e recuperação |
| `docs/desenvolvimento.md` | Ponteiro para o ambiente sem Docker |

Nenhuma rota, contrato, migração ou dependência foi alterado pela #12. A lista "Temas do acervo" saiu da tela inicial; os temas seguem visíveis nos seletores e na Gestão.

## Integração com a #15

A PR #33 entrou na `dev` antes desta PR. O merge conflitou só nos dois arquivos previstos; `style.css`, `ValidityPanel.tsx` e `desenvolvimento.md` se fundiram sozinhos.

- `QuestionPanel.tsx`: ordem nova mantida, com `<DivergenceNotices notices={result.divergence_notices ?? []} />` logo após o aviso de geração.
- `main.tsx`: estrutura nova mantida, com `DivergencePanel` **só na área de Gestão**.

A posição segue a #15 ("aviso curto na Consulta e os detalhes completos apenas na Gestão, respeitando o perfil da sessão") e a especificação (D13 e a tabela Consulta × Gestão). Hoje `documents:ingest` e `alerts:read-details` vêm juntas, só no perfil `gestao` (`backend/app/auth.py`); a aba considera as duas para não depender desse acoplamento.

## Validação executada (árvore integrada)

| Verificação | Resultado |
| --- | --- |
| `npm run build` (`tsc --noEmit` + Vite) | Passa |
| Contratos: export OpenAPI e `contracts:generate` | Sem diferença |
| `ruff check` / `ruff format --check` | Passam |
| `pytest backend/tests` contra PostgreSQL 16.2 local | **315 passed** (290 anteriores + 25 da #15), código 0 |
| Roteiro de API pelo proxy do Vite, com acervo e fatos publicados | 25/25 |
| Interface no Chromium 131 headless (Playwright), desktop 1280×900 e celular 375×740 | **35/35** |
| `scripts/dev-local.sh`: `bash -n`, `shellcheck` 0.10.0 e execução do zero em estado isolado | Sem avisos; migrações, 290 testes, 13/13 versões e 59 fatos publicados; `stop` sem processos restantes |

A interface cobre: ausência de formulário de login; abas por permissão; AC-01 com fonte `NG_111 · 3.0.0 · p. 2 · 4.3.1` logo abaixo; PDF em `#page=2`; foco no painel de evidência e retorno; resposta preservada ao trocar de área; upload em lote; falha de PDF sem texto com motivo; atualização automática; "Tentar novamente"; teclado; empregado sem Gestão e com 403; "Ver para" sem conceder upload; celular sem rolagem horizontal; AC-03 completo só na Gestão, com as duas fontes e a precedência; aviso curto do AC-03 na Consulta, antes das afirmações; sem erros no console (exceto o 401 esperado de `/eu` sem sessão).

**Não verificado:** aviso de geração indisponível com Bedrock configurado (sem chamadas AWS nos testes); leitores de tela reais; navegadores além do Chromium; a CI do GitHub (usa Compose, não este ambiente).

## Ambiente do Kiro usado

Versão portátil: [`scripts/dev-local.sh`](../scripts/dev-local.sh) e [`docs/ambiente-sem-docker.md`](ambiente-sem-docker.md). Nesta máquina há uma cópia específica em `/kiro/.tools/` (`ipbot-dev.sh`, `LEIA-ME.md`), que serve o ambiente em uso:

```sh
/kiro/.tools/ipbot-dev.sh start | status | stop   # PostgreSQL, worker, API e frontend
```

- Linux na AWS, sem Docker nem `sudo`. As worktrees do computador anterior não estão acessíveis aqui; não foram transportadas.
- PostgreSQL 16.2 dos binários de `pgserver==0.1.4`, só em `127.0.0.1:55432`, bancos `ipbot_dev` (testes) e `ipbot_e2e` (acervo, fatos e arquivos de teste enviados pela interface). Credenciais aleatórias em arquivo `600` fora do repositório. `mmap` para memória compartilhada, porque a máquina limpa `/dev/shm` ao fim de cada sessão.
- Chromium do Playwright 1.49.1 com bibliotecas e fontes extraídas de RPMs oficiais para uma pasta local.
- Persistência: `/kiro` e a pasta pessoal ficam no disco raiz (XFS) e persistem entre comandos e reconexões; `/tmp` e `/dev/shm` são apagados ao reiniciar. Os serviços não voltam sozinhos após reboot. **Não confirmado** se a máquina sobrevive ao fim da sessão ou do evento (conta AWS do evento com limpeza automática). O GitHub é o único lugar garantido para o código.

## Pendências confirmadas

- Revisão humana e CI da PR; sair de rascunho só após aprovação. Merge não autorizado ainda.
- Observações do backend da consulta (#10), fora do escopo da #12:
  - AC-01: os itens 4.3.1 e 8.1.2 estão entre as afirmações, mas o Anexo G vem em primeiro.
  - AC-13 (aluguel do coworking com Férias selecionado): status `partial`, com trechos de Férias como afirmações; a matriz espera evidência insuficiente. A lacuna é informada corretamente.
- Rótulos que envolvem `select` têm nome acessível que inclui as opções (padrão existente). Avaliar `<label htmlFor>` numa revisão de acessibilidade.
- A branch `fix/10-integrar-fatos-curados` (conflito em `backend/app/main.py`) existe só no computador anterior; não foi transportada, por decisão do usuário.

## Próximo passo

Acompanhar a CI e a revisão da PR da #12. Em seguida, tratar AC-01 e AC-13 numa issue da consulta ou seguir para a #16 (validação integrada e CI de frontend e backend).

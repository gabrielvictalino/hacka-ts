# Handoff para o Kiro

Atualizado em 13/11/2026. Trabalho da issue #12 (Consulta e Gestão no React).

## Branch e commit

- Branch local `feat/12-consulta-gestao-react`, criada de `origin/dev` `19d2712`. **Sem push** e sem PR.
- Commit `ef20264` `feat(frontend): integra Consulta e Gestão com upload e evidência (#12)`.
- Este handoff e `.kiro/steering/` vão em um commit de documentação separado.

## O que mudou

| Arquivo | Mudança |
| --- | --- |
| `frontend/src/main.tsx` | Navegação Consulta/Gestão. Identidade de `/eu`, sem formulário de login; o SSO simulado só oferece as contas fictícias. A aba Gestão só aparece com `documents:ingest`. As áreas ficam montadas e só são ocultadas, preservando a resposta da Consulta. "Ver para" agrupado na Consulta, com aviso de que não altera permissões |
| `frontend/src/ManagementPanel.tsx` (novo) | Upload individual ou em lote (`POST /api/documents/batch`), resultado por arquivo (enfileirado, duplicado, inválido), lista de versões do tema com código, título, versão, tipo, fase, vigência documentada, estado e progresso, atualização automática enquanto houver fila, motivo da falha, "Tentar novamente" (`POST /api/documents/{id}/retry`), "Abrir PDF original" e criação de tema (`POST /api/topics`) |
| `frontend/src/QuestionPanel.tsx` | Resposta primeiro: situação, aviso curto de geração indisponível (`notice`), afirmações com a fonte logo abaixo. Sem sustentação completa, as lacunas aparecem antes dos trechos, que ficam identificados como relacionados. Metadados depois. Registra a visão escolhida no resultado |
| `frontend/src/app.css` (novo) | Estilos da navegação e da Gestão, em arquivo próprio para não colidir com o final de `style.css` |

Nenhuma rota, contrato ou permissão do backend foi alterado.

## Validação executada

| Verificação | Resultado |
| --- | --- |
| `npm run build` (`tsc --noEmit` + Vite) | Passa |
| Contratos: export OpenAPI e `contracts:generate` | Sem diferença |
| `ruff check` / `ruff format --check` | Passam |
| Migrações `upgrade heads` → `downgrade base` → `upgrade heads` em PostgreSQL 16.2 local | `0004 (head)` |
| `pytest backend/tests` contra PostgreSQL real | **290 passed**, código 0 |
| Roteiro de API pelo proxy do Vite, com acervo importado e fatos publicados | 25/25 verificações |
| Interface no Chromium 131 headless (Playwright), desktop 1280×900 e celular 375×740 | 29/29 verificações |

O roteiro de interface cobre: ausência de formulário de login; abas por permissão; AC-01 sustentado com fonte `NG_111 · 3.0.0 · p. 2 · 4.3.1` logo abaixo; abertura do PDF em `#page=2` com a sessão; foco no painel de evidência e retorno; resposta preservada ao ir e voltar da Gestão; upload em lote com resultado por arquivo; falha de PDF sem texto com motivo; atualização automática até "Pronto para consulta"; "Tentar novamente"; ativação da aba pelo teclado; empregado sem aba nem área de upload e com 403 na API; "Ver para" registrado no resultado sem conceder upload; sem rolagem horizontal no celular; sem erros no console (exceto o 401 esperado de `/eu` sem sessão).

**Não verificado:** o aviso de geração indisponível com Bedrock configurado (os testes não habilitaram chamadas AWS; o texto vem de `notice`, sem lógica nova); leitores de tela reais; navegadores além do Chromium.

## Compatibilidade com a PR #33 (`feat/15-divergencia-ac03`, aberta)

Um merge de teste, feito numa worktree descartável e já desfeito, conflita só em dois arquivos. `style.css` e `ValidityPanel.tsx` se fundem sozinhos. A resolução abaixo compila:

- `QuestionPanel.tsx`: manter a ordem nova e inserir `<DivergenceNotices notices={result.divergence_notices ?? []} />` logo após a linha do `result.notice`.
- `main.tsx`: manter a estrutura nova e renderizar `DivergencePanel` **dentro da área de Gestão**, após o `ManagementPanel`, com a condição `identity.permissions.includes("alerts:read-details")`.

## Ambiente do Kiro usado (específico desta máquina, fora do repositório)

- Linux na AWS, sem Docker nem `sudo`. As worktrees do computador anterior não estão acessíveis aqui; não foram transportadas.
- PostgreSQL 16.2 dos binários do pacote Python `pgserver==0.1.4`, numa venv de ferramentas fora do repositório. Cluster exclusivo, só em `127.0.0.1:55432`, com bancos `ipbot_dev` (suíte de testes) e `ipbot_e2e` (acervo importado, arquivos de teste enviados pela interface e fatos publicados). Credenciais aleatórias em arquivo `600` fora do repositório. Configurado com `dynamic_shared_memory_type = mmap`, porque esta máquina limpa `/dev/shm` ao fim de cada sessão.
- Chromium do Playwright 1.49.1 com bibliotecas gráficas e fontes DejaVu extraídas de RPMs oficiais para uma pasta local (sem instalar no sistema).
- Serviços parados ao final. O banco preserva os dados.

## Pendências confirmadas

- Abrir a PR da #12 para `dev` quando autorizado. Antes, atualizar com `origin/dev`.
- Se a PR #33 entrar antes, aplicar a resolução descrita acima.
- Observações do backend da consulta (#10), fora do escopo da #12, sem alteração:
  - AC-01: o item 4.3.1 e o 8.1.2 aparecem entre as afirmações, mas o Anexo G vem em primeiro.
  - AC-13 (aluguel do coworking com Férias selecionado): status `partial`, com trechos de Férias como afirmações; a matriz espera evidência insuficiente. A lacuna é informada corretamente.
- Os rótulos que envolvem `select` têm nome acessível que inclui as opções (padrão já existente no app). Avaliar trocar por `<label htmlFor>` em uma revisão de acessibilidade.
- A branch `fix/10-integrar-fatos-curados` (com conflito em `backend/app/main.py`) existe só no computador anterior. Não foi transportada, por decisão do usuário.

## Próximo passo

Revisar o diff da #12 e autorizar o push e a abertura da PR. Depois, revisar a PR #33 ou atacar as observações de AC-01 e AC-13 em uma issue de consulta.

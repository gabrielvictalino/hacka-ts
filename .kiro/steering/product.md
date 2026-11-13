# IPBOT · produto

Plataforma do Hacka/TS 2026 (BBTS, Desafio 2) para consultar o acervo sintético da ACME com respostas apoiadas em fontes verificáveis.

## Regras inegociáveis

- Toda afirmação aponta para documento, versão, página física (começa em 1) e trecho literal. Nunca inventar evidência, vigência ou precedência normativa.
- Se o acervo não sustenta um ponto, mostrar a lacuna (`partial` ou `insufficient`). Não completar com conhecimento externo nem pelo modelo.
- Cálculos de datas e valores ficam em código (`app.regras`), com parâmetros dos fatos curados. O modelo nunca calcula.
- A consulta funciona sem modelo (modo extrativo). Bedrock é opcional e só seleciona/ordena trechos literais validados pelo servidor. Ver `docs/adr/0001-consulta-local-com-geracao-opcional.md`.
- Fase declarada, datas impressas e situação temporal calculada são campos distintos.
- Consulta e Gestão são áreas separadas. Identidade vem do SSO simulado (`/eu`), sem formulário de login ou cadastro. O seletor "Ver para" muda só a perspectiva, nunca permissões.

## Onde estão os requisitos

- Glossário: `CONTEXT.md`.
- Especificação e critérios RF-01 a RF-11: `docs/spec-ipbot.md`.
- Cenários de aceite AC-01 a AC-22: `docs/acervo-e-cenarios-ipbot.md`.
- Escopo e prioridade vigentes: issues do GitHub (`gabrielvictalino/hacka-ts`), rótulos `prioridade:P0..P3` e `escopo:mvp|opcional|evolucao`.

O README lista funcionalidades **esperadas**; não as trate como implementadas sem conferir o código.

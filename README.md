# IPBOT — Plataforma de Inteligência Empresarial

**Hacka/TS 2026 · BBTS · Desafio 2**

A equipe IPBOT propõe uma plataforma web responsiva para consultar manuais, contratos e normas internas, obter respostas com fontes verificáveis e sintetizar informações para apoiar a tomada de decisão.

## O problema

Documentos empresariais concentram informações sobre riscos, prazos, obrigações e valores. Como esses materiais costumam ser extensos e distribuídos entre diferentes sistemas, encontrar uma regra, conferir sua vigência ou consolidar informações para um relatório pode exigir tempo e apoio de especialistas.

## Funcionalidades esperadas

| Funcionalidade | O que a plataforma deve permitir |
| --- | --- |
| Base documental | Enviar e processar documentos sintéticos individualmente ou em lote, com organização por tema. |
| Perguntas e respostas | Responder com base nos documentos fornecidos, citando a fonte, a versão e o trecho que sustenta a resposta. |
| Síntese e destaques | Destacar riscos, prazos, obrigações ou valores conforme a perspectiva escolhida. |
| Recursos visuais e interativos | Apresentar informações em fluxogramas, mapas mentais, infográficos, quadros ou gráficos, com referências às fontes. |
| Perspectivas de análise | Consultar a mesma informação por área, tema ou prazo, usando filtros. |
| Resumo executivo | Gerar um resumo ou uma apresentação a partir das informações selecionadas. |
| Vigência e conflitos | Indicar a versão em vigor e a camada normativa. Sinalizar divergências e exibir as fontes envolvidas. |
| Reaproveitamento e feedback | Sugerir análises anteriores semelhantes e permitir que o usuário avalie as respostas. |

## MVP proposto

Para as 24 horas do hackathon, a proposta é entregar um fluxo funcional e navegável.

1. Enviar um documento sintético e associá-lo a um tema.
2. Fazer uma pergunta sobre o conteúdo e abrir o trecho citado para conferir a resposta.
3. Gerar uma síntese com os principais prazos e obrigações, mantendo as citações.
4. Demonstrar como a plataforma sinaliza divergências ou informa que os documentos disponíveis são insuficientes para responder.

**Exemplo de demonstração**

> Qual é o prazo para renovar este contrato?

A plataforma deve apresentar o prazo, identificar o documento e a versão consultada e mostrar o trecho correspondente. Se duas fontes indicarem prazos diferentes, deve sinalizar a divergência e exibir as duas citações.

## Tecnologias e execução

A BBTS recomenda **React ou Angular** no front-end, **Java, Node.js ou Python** no back-end, **PostgreSQL** para persistência e **AWS** na nuvem. O ambiente oferecido pela organização pode apoiar o desenvolvimento com Kiro e serviços de IA.

O ambiente de desenvolvimento usa **React + TypeScript**, **FastAPI**, **PostgreSQL** e um **worker Python** com fila persistida no banco.

Requisitos: Docker com Compose v2 ou superior e Python 3 para gerar a configuração local.

```sh
python3 scripts/init_env.py
docker compose up --build -d --wait
```

Abra o frontend em <http://localhost:5173> e a documentação da API em <http://localhost:8000/docs>.
O frontend inicial permite selecionar uma conta fictícia do simulador de SSO e conferir os temas importados.

Consulte o [guia de desenvolvimento](docs/desenvolvimento.md) para importar o acervo, executar migrações, regenerar contratos e rodar os testes.

## Roadmap proposto de seis meses

| Período | Evolução prevista |
| --- | --- |
| Meses 1–2 | Consolidar a consulta com citações, avaliar a qualidade das respostas e ampliar o processamento de documentos em lote. |
| Meses 3–4 | Evoluir a análise de vigência e conflitos, adicionar filtros por perspectiva e testar resumos executivos com usuários. |
| Meses 5–6 | Ampliar os recursos visuais com citações, incorporar feedback e validar o reaproveitamento de análises anteriores. |

## Equipe IPBOT

- Lucas Berenguer Avelino de Souza
- Rafael Lucas
- Fernanda Ramalho
- Gabriel Victalino Mancebo

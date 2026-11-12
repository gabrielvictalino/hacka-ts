# IPBOT · Plano de entrega em 8h45

Este plano complementa a [especificação do MVP](spec-ipbot.md) com a ordem de implementação aprovada para a janela de menos de nove horas. As janelas são relativas ao início do trabalho. O cronograma termina em 8h45 e deixa margem para a entrega antes do limite.

## O que entra na entrega

- Aplicação local com React, FastAPI, PostgreSQL e um worker de ingestão. Docker Compose sobe o ambiente. O README cobre configuração, migração, carga inicial e uso.
- Acervo inicial de Férias, Inovação e Ideias em Campo e Locação de coworking, importado de uma pasta configurável. Upload individual de PDF pesquisável na interface, com estado de processamento.
- Consulta extrativa por tema com acesso ao documento, à versão, à página e ao trecho literal. Síntese de prazos e obrigações, indicação de vigência e sinalização de divergências, inclusive em PDFs inéditos. A aplicação apresenta as premissas citadas nas inferências e indica a lacuna nos casos inconclusivos.
- Testes de integração com PostgreSQL, recuperação do worker, controle de acesso à fonte e teste de carga com até 100 usuários virtuais. O [plano técnico e de capacidade](spec-operacional-e-capacidade-ipbot.md) define o cenário, as metas e o que registrar.

A geração e a análise semântica permanecem opcionais e entram quando o fluxo principal estiver validado. Redis, broker dedicado, balanceador e deploy AWS ficam para evolução. O roteiro de produto de seis meses continua na especificação do MVP.

## Cronograma e condições de avanço

| Janela | Trabalho | Condição para avançar |
| --- | --- | --- |
| 0h–0h45 | Criar a estrutura do projeto, o Compose, a primeira migração e a entrada do comando de importação. Acordar os formatos de estado e citação nos primeiros 30 minutos. | Um integrante consegue subir o ambiente pelo README. Frontend e backend usam os mesmos campos no fluxo principal. |
| 0h45–2h30 | Implementar upload, persistência do original, fila no PostgreSQL e worker. Usar a mesma ingestão no comando de carga inicial. | PDF pesquisável de aproximadamente 100 páginas chega a `pronto`. Uma versão parcialmente processada fica fora da busca. |
| 2h30–4h30 | Entregar Biblioteca e Consulta no React. Integrar busca textual, resposta extrativa e abertura da fonte na página certa. | O fluxo upload → pergunta → citação → PDF funciona com o modelo desligado. |
| 4h30–6h15 | Implementar síntese, vigência e divergências. Priorizar regras explícitas e inferências verificáveis com premissas citadas. | Demonstrar versão substituída, evidência insuficiente e divergência implícita em PDFs novos. |
| 6h15–7h45 | Validar acesso aos documentos, limites de processamento, recuperação de jobs e desempenho durante ingestão. Executar a suíte de integração e o teste de carga. | Testes de citação e recuperação executados. Resultados de carga e limitações registrados. |
| 7h45–8h45 | Congelar funcionalidades, corrigir falhas do fluxo principal, atualizar o README e ensaiar o pitch. | A equipe executa a demo do início ao fim em ambiente local e identifica os critérios que ficaram pendentes. |

Com trabalho em paralelo, distribuir quatro frentes conforme a disponibilidade da equipe.

| Frente | Responsabilidade |
| --- | --- |
| Ingestão e banco | Migração, upload, persistência, fila, worker e carga inicial. |
| Consulta e evidências | Busca textual, resposta extrativa, citação, vigência, síntese e divergências. |
| Frontend | Biblioteca, acompanhamento do upload, consulta, síntese e abertura da evidência. |
| Testes e demo | Fixtures sintéticas, integração, carga, registro de resultados e ensaio. |

## Roteiro da demonstração

1. Com os três temas carregados, enviar um PDF pesquisável longo e mostrar o estado de processamento. Consultar um documento já indexado enquanto o worker processa o novo arquivo.
2. Abrir uma citação na página exata. Com o modelo desligado, mostrar a resposta extrativa e uma divergência com premissas verificáveis.
3. Apresentar o resultado medido de carga, incluindo concorrência, latência, erros e ingestão. Se houver tempo no pitch, mostrar a recuperação do worker. O [roteiro de teste](spec-operacional-e-capacidade-ipbot.md#testes-de-integração-e-falha) define como reproduzir a falha.

## Checklist de entrega

- [ ] README com pré-requisitos, variáveis, migração, carga inicial e execução dos testes.
- [ ] Fluxo local demonstrado com PDF pesquisável próximo de 100 páginas e abertura da citação.
- [ ] Evidência de recuperação do worker, autorização da fonte e consulta com o modelo desligado.
- [ ] Resultado de carga com o cenário efetivamente executado, metas atingidas ou não e ambiente de teste.
- [ ] Estado dos [cenários de aceite](acervo-e-cenarios-ipbot.md) registrado como validado, falhou ou pendente. Indicar as funcionalidades opcionais entregues.

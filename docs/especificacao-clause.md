# IPBOT · Especificação do produto

Versão revisada de `arquitetura-clause.md`. O [plano de arquitetura](arquitetura-clause.md) descreve tecnologias, implementação, operação e deploy.

## 1. O desafio

**Pergunta do desafio [Edital 8.1.2, Slides]:** como organizar, sintetizar e destacar as informações mais relevantes sob diferentes perspectivas de análise, por meio de recursos visuais, gráficos e interativos, transformando documentos e conteúdos complexos em inteligência empresarial, com respostas confiáveis e acesso rápido para apoiar a decisão.

**Contexto:** manuais, contratos e normas internas concentram o conhecimento da empresa, mas são extensos e dispersos. Consultá-los consome tempo, exige especialistas e demanda consolidação para relatórios e apresentações executivas.

### Regras que afetam o projeto

| Tema | Regra |
|---|---|
| Duração | 24 h seguidas, das 07h30 de 12/11/2026 às 07h30 de 13/11/2026 [Edital] |
| Entrega | MVP **funcional**. Telas estáticas não contam (8.5) [Edital] |
| Pitch | 5 min de apresentação + 3 min de perguntas (11.2) [Edital] |
| Plano de evolução | Obrigatório no pitch: cronograma e escopo dos próximos **6 meses** (8.6) [Edital] |
| Tecnologia | Sem custo para a BBTS. Preferência: Java/Node/**Python**, Angular/**React**, **PostgreSQL**, **AWS** (8.2) [Edital]. Os slides dizem "plataforma livre, dentro das tecnologias permitidas" |
| IA | Permitida como apoio e como parte da solução, desde que a equipe explique como foi usada (8.2.5) [Edital] |
| Dados | Sintéticos [Slides] |
| Originalidade | Código desenvolvido durante o evento. Plágio desclassifica (8.4) [Edital] |
| Propriedade | Código, documentação, bases e modelos são cedidos à BBTS e entregues no ambiente indicado (15) [Edital] |
| Escopo | **"Não é preciso fazer tudo: priorize o mais crítico e viável em 24h e justifique no pitch."** [Slides] |
| Resultado | Premiação em 13/11 às 17h [Edital] |

### Critérios de avaliação, nota de 1 a 5 cada [Edital 10, Slides]

1. **Aderência ao desafio**: alinhamento com o problema.
2. **Inovação**: originalidade e diferenciação da solução.
3. **Viabilidade**: potencial de implementação na BBTS.
4. **Experiência do usuário**: usabilidade, acessibilidade e qualidade da experiência.
5. **Pitch**: clareza, objetividade e comunicação da proposta.

UX e pitch pesam 2 de 5 critérios. A demo precisa ser clara, bonita e confiável.

### As 8 funcionalidades esperadas [Slides]

| # | Funcionalidade | O que pede |
|---|---|---|
| 1 | Base e processamento de documentos | Envio e processamento de documentos individuais ou em lote, organizados por tema |
| 2 | Perguntas e respostas com fonte | Responde só com base nas fontes fornecidas, citando fonte, versão e trecho |
| 3 | Síntese e destaques | Resumo do mais relevante conforme a perspectiva: riscos, prazos, obrigações ou valores |
| 4 | Recursos visuais e interativos | Fluxograma, mapa mental, infográfico, quadro ou gráfico, **cada elemento remetendo à fonte** |
| 5 | Perspectivas de análise | Alternar a visão da mesma informação por área, tema ou prazo, com filtros |
| 6 | Resumo executivo | Resumo ou apresentação gerada a partir das informações selecionadas |
| 7 | Vigência, camadas e conflito | Indica a versão em vigor e a camada da norma; **sinaliza divergência entre fontes em vez de escolher uma** |
| 8 | Reaproveitamento e retorno | Sugere análises anteriores semelhantes e permite avaliar a resposta |

## 2. O acervo

Empresa fictícia **ACME Tecnologia e Serviços**. Documentos anonimizados nas pastas `ferias/`, `inovacao/` e `locacao/`, em uma pasta local configurável, mais o catálogo `INSTRUÇÕES SOBRE O ACERVO DE DADOS SINTÉTICOS.pdf`.

| Assunto | Versões de referência | Substituídos |
|---|---|---|
| Férias | NG_111 v3.0.0 (norma), PX_1111-001 v1.0.0 (procedimento), FM_1111-001 v2.0.0 (formulário), TB_1111-001 v1.0.0 (tabelas), FL_1111-001 v1.0.0 (fluxograma) | NG_111 v2.0.0, FM_1111-001 v1.0.0 |
| Inovação (Ideias em Campo) | NG_1130 v1.0.0 (norma), PX_1130-001 v1.0.0 (funil), RG_1100 v2.0.0 (regulamento), NT_2026-021 v1.0.0 (nota técnica de orçamento) | RG_1100 v1.0.0 (não veio na pasta) |
| Locação de coworking | CTR_2026-012 v1.0.0 (contrato com início em 30/11/2026), NT_2026-018 v1.0.0 (nota técnica) | - |

O catálogo explica as 12 categorias de documento, a numeração e as séries, e lista 3 "jornadas de referência" (Férias, Inovação, Locação) que **não recebemos**. Ele descreve a jornada como leitura guiada com "resumo, fluxo, ação por perfil, exemplo e perguntas frequentes". É uma pista do formato de síntese esperado.

O [Inventário e matriz de cenários](acervo-e-cenarios-ipbot.md) registra a leitura dos 14 PDFs pesquisáveis, com 77 páginas.

### Estrutura comum dos documentos [Acervo]

Todos têm um cabeçalho padronizado: tipo, título, sigla e número, versão, elaborado por, aprovado por, **fase** (Vigente), vigência ou data de aprovação e, quando existe, **Vinculado a**. Isso permite ler os metadados por regras simples, sem depender da LLM. As normas usam itens numerados (4.3.1 etc.), e contratos usam cláusulas.

O `FL_1111-001` vem como **código Mermaid** dentro do PDF, então o fluxograma pode ser desenhado diretamente no front.

### Camadas de norma [Acervo]

- O PX_1111-001 (item 2.2) diz que, em divergência, **prevalece a NG_111**. O PX_1130-001 diz o mesmo da NG_1130.
- Hierarquia observada: **NG** manda; **PX** detalha; **FM, TB e FL** apoiam. **RG** (regulamento de programa) se liga à NG e **NT e CTR** (instrumentos) têm numeração própria e referenciam outras normas.
- Alçadas (R$ 18.000,00 e R$ 120.000,00) vêm da **NG_012**, citada em três documentos, mas a NG_012 **não está no acervo** [A confirmar].

### Armadilhas do acervo (o que a solução precisa tratar bem)

1. **Versões substituídas.** Responder pela versão vigente e saber apontar a que foi substituída. Exemplos: o FM v1 pedia 30 dias de antecedência e o v2 pede 45; o RG v1 permitia 3 ideias e o v2 permite 2. Isso é mudança de versão, não conflito.
2. **Numeração ambígua.** `PX_1111-001` liga-se à `NG_111`, e `PX_1130-001` à `NG_1130`. A fonte de verdade é o campo "Vinculado a".
3. **Lacunas legítimas.** O catálogo diz que não há resposta nas fontes sobre "mesma pessoa elaborar, revisar e aprovar". A NT_2026-021 diz que não trata de empregados afastados. A solução deve responder **"não consta"**.
4. **Regras com cálculo.** Prazos em camadas, antecipação para o dia útil anterior, 30% de ausência arredondado para baixo (TB Tabela 4), faixas de alçada (R$ 18.000,00 vs R$ 18.000,01), multa de 5% de R$ 18.250,00 (R$ 912,50).
5. **Cruzamentos.** A NT_2026-021 distingue R$ 96.000,00 de orçamento total e R$ 24.000,00 destinados à premiação do RG_1100. O valor do coworking (R$ 18.250,00) cai na faixa de diretor, igual nos dois documentos de locação.
6. **Exclusões.** A NG_111 (item 4.12) diz que estagiários e aprendizes não são regidos pela norma de férias.
7. **Conflitos entre fontes.** No cenário AC-03, a norma prevê aviso até D-35 e o procedimento prevê emissão no dia seguinte à aprovação nas condições que descreve. Mostrar as duas passagens e a precedência declarada.

## 3. Comportamento do produto

| ID de origem | Decisão funcional |
| --- | --- |
| D3 | Férias é o tema aprofundado. Inovação e Locação têm cobertura progressiva. |
| D4 | A resposta leva à evidência. Se faltar informação, a interface explicita a lacuna. |
| D5 | Os fatos preservam os números e as condições das fontes. |
| D6 | Prazos, datas e valores calculados seguem regras verificáveis. |
| D7 | A pessoa pode alternar perspectivas por tema ou prazo e filtrar por área. A jornada destaca ações por papel. |
| D9 | O núcleo é priorizado para a demo. As extensões entram conforme a estabilidade do núcleo. |
| D10 | A consulta oferece geração e modo extrativo. Se a geração ou a busca semântica estiver indisponível, a pessoa ainda pode pesquisar o acervo publicado e abrir as fontes. |
| D12 | Cada evidência identifica documento, versão, página física e trecho literal. Item ou cláusula acompanha a citação quando disponível. |
| D13 | Consulta e Gestão têm fluxos próprios. Gestão mantém upload, versões e detalhes de divergências. |
| D14 | A demo usa contas de teste com perfis empregado, gestor e gestão do acervo. A conta define a visão inicial. O seletor “Ver para” permite explorar as regras de outro papel. |
| D15 | A Consulta mostra a resposta e a fonte logo abaixo. A jornada principal tem cinco passos e o fluxograma completo fica acessível por link técnico. |
| D16 | Todo usuário autenticado pode consultar o mesmo acervo. Só o perfil de Gestão pode enviar documentos e acessar alertas completos. |
| D17 | A equipe valida a capacidade de consulta com até 100 usuários simultâneos, incluindo o cenário com ingestão concorrente. |

| | Consulta | Gestão |
|---|---|---|
| Quem usa | Funcionários que querem perguntar e entender | Quem mantém o acervo |
| Telas | Início, Resposta, Guia do assunto (jornada), Resumo | Documentos (upload em lote, versões, situação) e Alertas |
| Vê versões e conflitos? | Só o selo "Em vigor, versão X" e o link para versões anteriores; aviso curto quando duas fontes divergem | Lista completa de versões, mudanças entre versões e divergências entre fontes |
| Acesso | Exige entrar; todos os perfis autenticados podem consultar todos os documentos | Exige entrar com o perfil de gestão do acervo |

### Perspectivas e papéis [Decisão D7]

- **Controle principal:** perspectiva (Prazos, Valores, Obrigações, Riscos) + filtros por assunto e área.
- **Seção "ação por perfil"** dentro do guia de cada assunto: Empregado, Gestor, Diretoria/Apoio e o caso especial Estagiário/Aprendiz (exclusão do item 4.12 da NG_111). Os nomes "Diretoria/Apoio" e a divisão por perfil são criação da equipe, a partir dos papéis que os documentos descrevem.
- **Nível de detalhe:** Resumo ou Completo.
- **Visão inicial vs. "Ver para":** a visão inicial vem do perfil da conta. O seletor "Ver para" (Empregado, Gestor, Diretoria ou apoio, Estagiário ou aprendiz) deixa a pessoa olhar o assunto pela ótica de outro papel, com um link "Voltar à minha visão". A visão escolhida acompanha a consulta.
- **Escopo:** o sistema responde sobre **normas**, não sobre **dados de pessoas** (como o caso de um estagiário específico). Pergunta sobre uma pessoa não é atendida.
- **Visão sem norma própria:** para Estagiário ou aprendiz, o acervo só tem o item 4.12 da NG_111 (a norma de férias não se aplica a eles). A tela mostra esse item e diz que não há outra norma no acervo, em vez de inventar regras.
- Princípio: **uma única fonte de verdade**. Se a norma mudar, atualiza-se uma vez e todas as telas mudam.

## 4. Priorização das funcionalidades

Não vamos implementar as 8 com a mesma profundidade. O slide permite priorizar, desde que seja justificado.

### Nível 1 · Núcleo (precisa funcionar na demo)

| # | Funcionalidade | Entrega mínima |
|---|---|---|
| 1 | Base e processamento | Na área de **Gestão**: upload (individual e em lote) de PDFs no formato do acervo; leitura do cabeçalho; organização por tema; lista de documentos com versão e fase |
| 2 | Perguntas com fonte | Resposta com documento, versão, **página**, item e trecho; "não consta" quando não houver; indicação do que ficou **sem confirmação**; validador de citações; funciona **com e sem IA** |
| 3 + 5 | Destaques e perspectivas | Seletor de perspectiva (Prazos, Valores, Obrigações, Riscos) e filtros por assunto e área, alimentados pela tabela de fatos |
| 4 | Visuais com fonte | **Jornada em 5 passos** como visual principal, gráfico de orçamento e linha do tempo; cada elemento abre o item de origem. O fluxograma completo (`FL_1111-001`) fica atrás de um link técnico |
| 7 | Vigência, camadas, conflito | Selo de versão em vigor, aviso de versão substituída, camada da norma (NG > PX > apoio) e alerta quando duas fontes divergem |

### Nível 2 · Barato, se o núcleo estiver estável

| # | Funcionalidade | Entrega mínima |
|---|---|---|
| 6 | Resumo executivo | O usuário marca fatos e gera uma página (Markdown/HTML para PDF) com as fontes. Reaproveita a tabela de fatos |
| 8 | Reaproveitamento e retorno | Botão "ajudou?" com comentário, histórico das perguntas e sugestão de perguntas parecidas por similaridade simples de palavras |

### Nível 3 · Plano de 6 meses (não entra no MVP)

- Mapa mental interativo completo.
- Exportação em apresentação (PowerPoint).
- Similaridade entre análises anteriores e aprendizado a partir das avaliações.
- Integração com a fonte oficial de documentos.

### Como justificar no pitch

"Priorizamos o que gera confiança e decisão: documentos processados, respostas com fonte, perspectivas e conflito entre fontes. Resumo executivo e retorno do usuário entram como extensão da mesma base de fatos. Mapa mental e apresentação ficam para o plano de 6 meses, porque dependem da mesma base e não mudam o valor central."

## 5. Critérios de aceite do fluxo principal

- A Gestão envia PDFs individuais ou em lote e acompanha o processamento de cada arquivo. A lista exibe tema, versão e fase. Uma falha informa o motivo e permite corrigir ou reenviar.
- Uma pessoa autenticada consulta o tema, recebe resposta sustentada ou passagens extrativas e abre a versão original na página física citada. Uma resposta parcial indica o que ficou sem confirmação.
- O acervo publicado continua consultável se a geração ou a busca semântica falhar. O resultado indica o modo usado quando a consulta opera em contingência.
- Um item da jornada, da linha do tempo ou do gráfico aponta para a respectiva evidência. Mudanças de versão e divergências entre fontes aparecem de acordo com a fase e a aplicabilidade documentadas.
- O seletor “Ver para” altera a perspectiva. A autorização segue o perfil da conta. Cada um dos três perfis autenticados pode abrir a mesma fonte, e somente Gestão pode enviar arquivos e ler alertas completos.
- O teste de capacidade previsto em D17 usa até 100 usuários simultâneos. Durante ingestão concorrente, a meta da consulta extrativa é p95 de até 2 segundos, com menos de 1% de erros inesperados. Os resultados são registrados após medição. Consulte o [plano de arquitetura](arquitetura-clause.md#9-validação-de-capacidade-e-acesso).

## 6. Roteiro da demo

1. O problema: documentos densos, perguntas repetidas, decisões lentas (15 s).
2. **Gestão:** upload em lote dos documentos, que aparecem organizados por tema, com versão e situação (30 s). Depois, volta para a Consulta.
3. **Perspectiva "Prazos"** em Férias: jornada e linha do tempo com abertura da fonte (45 s).
4. **Pergunta** em linguagem natural na aplicação publicada. Abrir a página física da versão citada. Em contingência, a demo mostra as passagens do modo extrativo (45 s).
5. **Pergunta sem resposta**: o sistema diz "não consta" (20 s).
6. **Vigência e conflito**: na Consulta, o selo "Em vigor" e o aviso curto; na Gestão, os alertas com a mudança entre versões e as divergências entre fontes (45 s).
7. **Troca de perspectiva** para Valores em Inovação e Locação: orçamento e alçadas (30 s).
8. **Resumo executivo** gerado com as fontes e **avaliação** da resposta (30 s), se estiver pronto.
9. Plano de 6 meses (30 s).

## 7. Evolução do produto em seis meses

Exigido pelo edital (8.6). Rascunho a refinar:

- **Mês 1:** processamento contínuo de novos documentos e controle automático de versões.
- **Meses 2-3:** Ampliar o acervo da Knowledge Base, avaliar a recuperação por tema e integrar fontes oficiais de documentos. Evoluir os visuais com mapa mental interativo.
- **Mês 4:** autenticação e papéis reais (diretório da empresa), trilha de auditoria, exportação em apresentação.
- **Mês 5:** detecção de conflitos entre todos os documentos, alertas de vigência a vencer, aprendizado a partir das avaliações.
- **Mês 6:** piloto com usuários, métricas de uso e de confiabilidade das respostas.

## 8. Pontos de produto em aberto

- Confirmar se as três jornadas de referência e a NG_012 podem ser disponibilizadas.
- Confirmar o nome definitivo do produto. A interface usa IPBOT.

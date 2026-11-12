# IPBOT · Especificação do MVP

Especificação consolidada em 12/11/2026. Aguarda confirmação final para implementação.

## Objetivo e entrega

Uma pessoa de uma equipe administrativa, operacional ou de compliance seleciona um tema, consulta os PDFs sintéticos da ACME em linguagem natural e abre a página que sustenta cada afirmação. Pode pedir uma síntese de prazos, obrigações e responsáveis, além de identificar divergências e lacunas antes de agir.

O marco inicial é o fluxo completo de upload, processamento, pergunta e abertura da evidência em desktop e celular. Em seguida entram síntese, vigência e divergências. O MVP roda localmente no repositório `hacka-ts`, com React, FastAPI/Python e PostgreSQL. A arquitetura deve permitir integração futura com AWS. A execução da demo tem o ambiente local como base.

A demo começa com os temas Férias, Inovação e Ideias em Campo e Locação de coworking já importados a partir de uma pasta local configurável. O upload individual também faz parte do fluxo demonstrado. A consulta tem modo extrativo e detecção local de divergências. Com um modelo configurado, pode gerar respostas e fazer análise semântica complementar de casos que dependam de interpretação mais aberta.

## Escopo e rastreabilidade

As imagens descrevem o desafio e autorizam a priorização para 24 horas. As páginas 1–3 do plano contêm a proposta da IPBOT. Seu anexo reproduz o regulamento. O catálogo e os PDFs da ACME são dados de referência para o produto. As regras de férias, inovação e locação têm validade apenas dentro dos cenários sintéticos.

| Item das imagens | Entrega de 24 horas acordada | Evolução prevista |
| --- | --- | --- |
| 1. Base e processamento | Upload individual de PDF com texto, atribuição de tema e status de processamento | Lote e OCR |
| 2. Perguntas e respostas | Pergunta por tema, resposta sustentada e abertura de fonte, versão, página e trecho | Filtros avançados e avaliação de recuperação |
| 3. Síntese e destaques | Prazos, obrigações e responsáveis identificados, com citações por item | Perspectivas de risco, valores e outros destaques |
| 4. Recursos visuais | Navegação entre citação e página do PDF no fluxo principal | Fluxogramas, mapas, quadros e gráficos com evidência por elemento |
| 5. Perspectivas de análise | Seleção de tema | Filtros por área e prazo, visões operacional, executiva e de compliance |
| 6. Resumo executivo | Síntese de consulta na interface | Resumo executivo a partir de itens selecionados, com opção de apresentação |
| 7. Vigência, camadas e conflito | Tipo e camada documental, fase e datas quando disponíveis, identificação de substituição e indicação de divergência com as passagens envolvidas | Histórico navegável, comparação de versões e revisão humana |
| 8. Reaproveitamento e retorno | Etapa posterior. O plano original considera feedback simples caso haja tempo | Avaliação, histórico e sugestões de análises semelhantes |

O regulamento anexado ao plano exige MVP funcional e original, ausência de custos para a BBTS e parceiros e cronograma de evolução de seis meses no pitch (itens 8.2, 8.4–8.6). O pitch tem até cinco minutos, com até três minutos de perguntas (11.2). A equipe deve conseguir explicar o uso de IA (8.2.5). A disponibilização de recursos AWS depende do onboarding (14.4). A entrega institucional prevista no item 15.4 pertence ao processo do evento.

## Fluxos e critérios de aceite

| ID | Fluxo | Aceite |
| --- | --- | --- |
| RF-01 | Biblioteca | Listar versões pelo tema. Exibir título, código, versão, tipo, fase ou situação temporal disponível e estado do processamento. O usuário consegue abrir o PDF original. |
| RF-02 | Upload | Selecionar um tema e um PDF pesquisável. Exibir processamento, conclusão ou falha com ação clara. Uma versão só entra na consulta após concluir a extração e indexação. PDF inválido, ilegível ou sem camada de texto retorna motivo compreensível e pode ser reenviado após correção. |
| RF-03 | Consulta | Enviar pergunta em português no tema selecionado. Mostrar afirmações sustentadas e evidências acessíveis. Em resposta parcial, identificar separadamente o que o acervo confirma e o ponto sem confirmação. Sem evidência suficiente, informar a lacuna sem completar com conhecimento externo. |
| RF-04 | Verificação de fonte | Abrir uma citação na página indicada do PDF importado e exibir o trecho literal. Conferir título ou código, versão e página pelo mesmo registro. Funciona no celular com retorno à consulta ou à síntese. |
| RF-05 | Síntese | Gerar uma lista de prazos e obrigações a partir do tema. Mostrar responsável e condições quando explicitados, com evidência por item. Uma ausência de responsável é identificada como informação não encontrada. Prazos mantêm unidade, tipo de dia e marco de referência. |
| RF-06 | Vigência e camada | Apresentar fase declarada, data de referência, datas explícitas e indicação de substituição. Exibir o tipo e o papel da fonte na questão. Uma versão anterior pode aparecer como evidência de comparação histórica, identificada como tal. |
| RF-07 | Divergência | Detectar automaticamente divergências explícitas e implícitas para o mesmo cenário, inclusive em PDFs novos de estrutura livre com texto extraível, com o modelo desativado. Mostrar as passagens, suas versões, camadas e aplicabilidade quando identificadas. Em uma divergência implícita, explicar como as passagens levam à incompatibilidade. Se faltar confirmação sobre escopo, versão ou vigência, apresentar possível divergência, as fontes e o dado faltante. Quando a fonte explicita precedência, citar essa regra junto às orientações. |
| RF-08 | Uso em tela pequena | Selecionar tema, enviar pergunta, ler resposta, abrir evidência e retornar sem perder o resultado. Controles acessíveis por teclado e estados de erro ou carregamento perceptíveis. |
| RF-09 | Consulta sem modelo | Com o modelo desativado ou indisponível, a consulta devolve trechos do tema com as mesmas citações navegáveis e indica os pontos sem confirmação. A interface identifica o modo extrativo. |
| RF-10 | Acervo inicial | Um comando aceita o caminho para uma cópia local do acervo e importa os três temas e suas versões disponíveis. A biblioteca identifica versões substituídas. O upload pela interface usa o mesmo processamento documental da carga inicial. Reexecutar o comando preserva as versões e citações já processadas. |
| RF-11 | Análise semântica opcional | Com um modelo configurado, analisar relações menos diretas entre passagens recuperadas. Expor a interpretação como possível divergência quando faltarem premissas verificáveis, com citações e a descrição da lacuna. Se o modelo falhar ou estiver desligado, o fluxo extrativo e a detecção local seguem disponíveis. |

### Regras de evidência e vigência

- Usar somente os PDFs processados e elegíveis para a consulta. O catálogo auxilia na classificação. Uma regra operacional deve apontar para a versão documental que a contém.
- Guardar o texto por página. A busca pode normalizar caracteres para localizar termos. O trecho exibido preserva o conteúdo literal da página, admitindo normalização de espaços e quebras para visualização. A navegação usa a numeração física do PDF, começando em 1.
- Uma afirmação sobre prazo, valor, papel ou condição precisa de evidência que sustente o mesmo cenário. Validar a correspondência de cada citação com a página recuperada. Em geração por modelo, validar também o suporte à afirmação e retornar os trechos ou marcar lacuna quando não houver suporte.
- Manter fase declarada, datas impressas e situação calculada em campos separados. Para um intervalo explícito, a situação pode ser em vigor, a iniciar ou encerrada na data de referência. Sem intervalo ou sucessão suficiente, exibir o que a fonte declara e indicar a limitação do cálculo. Edição de programa, assinatura e aprovação têm significados distintos.
- A sucessão explícita limita a aplicabilidade da versão anterior a partir da entrada da sucessora, preservando as datas publicadas. Uma pergunta sobre período anterior pode usar a versão histórica disponível. Uma pergunta sobre vigência atual não usa versão substituída como orientação corrente.
- Em pergunta de planejamento, permitir consultar o conteúdo de documento com vigência futura e mostrar a data de início. Em perguntas sobre aplicação na data atual, deixar a situação temporal visível. Se houver período explícito na pergunta, aplicá-lo e mostrá-lo na resposta.
- Identificar relações por cabeçalho ou texto. O código numérico sozinho pode sugerir mais de uma norma. Comparar fase, escopo, papel e edição antes de sinalizar divergência.
- Manter valores monetários, unidades, condições e responsáveis tal como documentados. Quando houver arredondamento ou regra de cálculo relevante, indicar a evidência que o explica.

## Desenho técnico proposto

Os nomes de rotas, a estratégia de busca e as estruturas abaixo orientam a próxima rodada.

1. O React apresenta Biblioteca e Consulta. A consulta tem seletor de tema, resposta, síntese e painel de evidência reutilizável. O painel apresenta o trecho e abre o PDF na página citada.
2. A FastAPI valida o upload, guarda o original e extrai texto por página. Identifica código, versão, tipo, fase, datas e vínculos quando declarados. Valores não identificados ficam explícitos na biblioteca e não são inferidos pelo nome do arquivo.
3. O PostgreSQL persiste tema, documento, versão, páginas e trechos. A busca é textual em português e restrita ao tema, com correspondência exata de códigos, datas e termos para complementar o ranqueamento. Uma consulta recupera também versões relacionadas e passagens potencialmente divergentes quando necessárias ao cenário.
4. A camada de resposta devolve afirmações ou trechos e citações estruturadas. O modo extrativo usa passagens do acervo e sinaliza lacunas. Se configurada e disponível, a geração recebe a pergunta e as evidências recuperadas. Os PDFs são dados de consulta, inclusive quando contêm texto no imperativo. O backend controla as fontes elegíveis, verifica a saída e decide como exibir lacunas. [Decisão sobre a consulta local e a geração opcional](adr/0001-consulta-local-com-geracao-opcional.md).
5. Na execução local, os PDFs podem ficar em armazenamento local e os metadados no PostgreSQL. A integração AWS deverá manter o contrato de evidências. Serviço de armazenamento, modelo, credenciais e recursos AWS seguem condicionados à disponibilidade e à decisão de integração.
6. A carga inicial lê a pasta informada no comando e reconhece os três temas pelas subpastas do acervo. A carga preserva os históricos disponíveis. O catálogo da raiz permanece como referência auxiliar. O comando informa os resultados por arquivo e usa a mesma rotina de ingestão do upload.

### Detecção local de divergências

A detecção trabalha sobre o texto extraído de PDFs com estruturas diferentes, inclusive arquivos enviados depois da carga inicial. A proposta é representar as orientações recuperadas pelo assunto, ação, envolvidos, prazo, condições e período, mantendo a evidência de cada campo. A comparação normaliza números, unidades, datas e expressões.

- **Divergência explícita.** As passagens atribuem datas, prazos, valores, responsáveis ou obrigações incompatíveis à mesma situação. Para confirmar a divergência, verificar que as condições se sobrepõem.
- **Divergência implícita.** A incompatibilidade aparece ao combinar passagens. O aceite do modo local cobre relações de dependência, janelas de tempo e regras condicionais ou exceções. A resposta explicita o cenário, as premissas citadas e a consequência.
- **Possível divergência.** Há indício de incompatibilidade e faltam dados para confirmar que as orientações se aplicam à mesma situação. Mostrar os trechos e o dado faltante. Usar a fase, as datas e os vínculos documentados quando disponíveis.

Os testes do modo local usam PDFs inéditos, com novos códigos, estruturas diferentes e frases parafraseadas, enviados com o modelo desativado. O aceite exige detecção de divergência direta e derivada, citações navegáveis e distinção de escopo ou sucessão histórica.

A análise semântica opcional recebe os trechos já recuperados pela busca textual e propõe relações, premissas e citações para casos de interpretação mais aberta. Cada evidência apresentada precisa corresponder ao PDF original. Quando a relação depender de uma premissa que a base deixa em aberto, classificar como possível divergência e declarar a lacuna. Com a análise desativada, a comparação local conserva os mesmos critérios de aceite.

### Contratos propostos

| Operação | Entrada | Resultado |
| --- | --- | --- |
| `GET /api/topics` | — | Temas disponíveis com identificador e nome |
| `GET /api/documents?topic_id=…` | Tema | Versões, metadados e estado de processamento |
| `POST /api/documents` | PDF e tema, via multipart | Identificador da versão e estado. Resposta legível para arquivo não aceito ou duplicado |
| `GET /api/documents/{version_id}/file` | Identificador da versão | PDF original correspondente à citação |
| `POST /api/questions` | Tema, pergunta e data de referência opcional | Modo de resposta, estado, data efetiva, afirmações ou trechos com citações, lacunas e divergências |
| `POST /api/summaries` | Tema e data de referência opcional | Itens com categoria, obrigação ou prazo, responsável quando explícito e citações |

- Uma citação carrega identificador da versão, título, código e versão quando declarados, página física e trecho literal. Tipo, camada e informação temporal podem acompanhar a evidência na apresentação. Uma versão sem metadados confirmados exibe o nome do PDF e o estado “versão não identificada”.
- A proposta de estados de resposta é `sustentada`, `parcial`, `insuficiente` ou `divergente`, com lacunas representadas à parte. Cada divergência referencia duas ou mais citações, podendo estar na mesma versão, e tem classificação confirmada ou possível. Na implícita, o resultado inclui o raciocínio que relaciona as evidências. Na possível, inclui o dado faltante.
- Uma tentativa repetida de importação do mesmo PDF para o mesmo tema deve devolver a versão existente ou permitir recuperar um processamento com falha, sem duplicar trechos. Arquivos distintos com mesmo código e versão vão para verificação de metadados antes de substituição ou indexação conjunta. Uma falha parcial não torna páginas incompletas elegíveis à consulta.
- Preservar o PDF associado a cada versão, inclusive após entrada de uma sucessora. Uma citação já exibida precisa continuar resolvendo a mesma página.

## Demonstração e evolução

1. Enviar um PDF pesquisável, acompanhar o processamento, perguntar sobre um prazo e abrir a fonte. A prorrogação do coworking fornece um caso com prazo, parte responsável e data explícita.
2. Consultar Férias em 12/11/2026. Mostrar a norma v3.0.0 como orientação corrente, abrir a v2.0.0 no cenário histórico e verificar a divergência sobre aviso quando a aprovação ocorre em D-32.
3. Com o modelo desativado, consultar os PDFs novos do cenário AC-15 e abrir as premissas da divergência implícita. Se a análise semântica estiver disponível, usar AC-22 para mostrar uma interpretação sinalizada como possível.
4. Gerar síntese de Férias com prazos e responsáveis. Em Inovação, perguntar sobre participação durante afastamento para mostrar a lacuna e o encaminhamento documentado.
5. Usar a [matriz do acervo](acervo-e-cenarios-ipbot.md) para validar também o fluxo em tela pequena.

| Mês | Evolução proposta no plano, com complementos de rastreabilidade |
| --- | --- |
| 1 | Consolidar o fluxo de consulta, estruturar perguntas de avaliação e testar com usuários. |
| 2 | Adicionar lote, OCR e revisão de processamento. |
| 3 | Evoluir histórico, filtros de vigência e comparação de versões. |
| 4 | Ampliar perspectivas, resumo executivo e visuais com citações por elemento. |
| 5 | Incluir permissões, auditoria e feedback sobre qualidade das respostas. |
| 6 | Pilotar com usuários, testar reaproveitamento de análises e medir tempo de consulta e qualidade das citações. |

## Retomada da entrevista

| Decisão | Estado |
| --- | --- |
| Q1 · Escopo inicial | Confirmado. MVP do plano com upload, consulta, síntese e divergências. |
| Q2 · Repositório | Confirmado. `hacka-ts`. |
| Q3 · Execução da demo | Confirmado. Base local, com possibilidade de integração AWS. |
| Q4 · Stack | Confirmado. React, FastAPI/Python e PostgreSQL. |
| Q5 · Modo de resposta e indisponibilidade do modelo | Confirmado. Resposta extrativa local, com geração opcional. |
| Q6 · Carga inicial | Confirmado. Pré-carregar os três temas e manter upload pela interface. |
| Q7 · Recuperação de trechos | Confirmado. Busca textual no PostgreSQL. |
| Q8 · Cobertura de divergências sem modelo | Confirmado. Detecção automática também em PDFs novos de estrutura livre com texto extraível. |
| Q9 · Localização do acervo inicial | Confirmado. Importar de uma pasta local configurável. |
| Q10 · Categorias da detecção local | Confirmado. Cobrir também divergências implícitas que dependam da interpretação das passagens. |
| Q11 · Classificação com contexto incompleto | Confirmado. Sinalizar possível divergência com as fontes e indicar o dado faltante. |
| Q12 · Aceite de divergência implícita | Confirmado. Inferências rastreáveis no modo local e análise semântica opcional para interpretações mais abertas. |

A rodada de decisões está concluída. A confirmação conjunta da especificação consolida o entendimento antes de implementar, conforme a skill `grill-with-docs`.

## Fontes

- `Plano_IPBOT_HACKATS_2026.pdf`, pp. 1–4 para a proposta da equipe e pp. 5–11 para o regulamento reproduzido.
- Imagens anexadas “Desafio 2 · Plataforma de Inteligência Empresarial” e “Desafio 2 · Funcionalidades esperadas”.
- `hacka-ats/documentos_desafio_2`, com inventário e referências por página na [matriz do acervo](acervo-e-cenarios-ipbot.md).
- Respostas do usuário a Q1–Q12. [Glossário](../CONTEXT.md).

# IPBOT · Acervo e cenários de aceite

Fonte local em `C:/Users/gabri/hacka-ats/documentos_desafio_2`. Foram lidos 14 PDFs com 77 páginas, todas com texto extraível. O catálogo ocupa 9 páginas. As outras 68 páginas correspondem a 13 versões de 11 documentos. A numeração usada aqui é a página física do arquivo.

## Inventário

| Pasta | Documento | Versão | Páginas | Evidência de metadados |
| --- | --- | --- | ---: | --- |
| Raiz | Catálogo do Arquivo Central de Normas | 0.1.0 | 9 | Guia auxiliar da ACME fictícia |
| `ferias` | `NG_111` · Férias | 3.0.0 | 10 | Fase vigente. 03/08/2026–03/02/2028. Substitui a v2 |
| `ferias/substituidos` | `NG_111` · Férias | 2.0.0 | 1 | Versão anterior. Intervalo impresso de 10/12/2025 a 10/06/2027 |
| `ferias` | `PX_1111-001` · Procedimento de Férias | 1.0.0 | 7 | Vinculado à NG_111. 10/08/2026–10/02/2028 |
| `ferias` | `FM_1111-001` · Solicitação de Férias | 2.0.0 | 2 | Aprovado em 10/08/2026. Substitui a v1 |
| `ferias/substituidos` | `FM_1111-001` · Solicitação de Férias | 1.0.0 | 1 | Versão anterior. Aprovado em 10/12/2025 |
| `ferias` | `TB_1111-001` · Tabelas de Férias | 1.0.0 | 2 | Apoio à NG_111. Aprovado em 10/08/2026 |
| `ferias` | `FL_1111-001` · Fluxograma de Férias | 1.0.0 | 1 | Apoio à NG_111. Fluxograma disponível como texto Mermaid |
| `inovacao` | `NG_1130` · Gestão da Inovação | 1.0.0 | 7 | Fase vigente. 06/07/2026–06/01/2028 |
| `inovacao` | `PX_1130-001` · Funil de Inovação | 1.0.0 | 7 | Vinculado à NG_1130. 13/07/2026–13/01/2028 |
| `inovacao` | `RG_1100` · Regulamento do Programa Ideias em Campo | 2.0.0 | 10 | Vinculado à NG_1130. Aprovado em 20/10/2026 para a edição 2027. Declara substituição da v1 |
| `inovacao` | `NT_2026-021` · Orçamento, competências e elegibilidade | 1.0.0 | 5 | Refere-se ao RG_1100 v2. Assinada em 14/10/2026 e aprovada em 16/10/2026 |
| `locacao` | `CTR_2026-012` · Contrato de Locação de Espaço | 1.0.0 | 9 | Fase impressa “Vigente”. Intervalo de 30/11/2026 a 29/04/2027 |
| `locacao` | `NT_2026-018` · Nota Técnica de Contratação | 1.0.0 | 6 | Refere-se ao CTR_2026-012. Assinada em 05/11/2026 |

O catálogo descreve 12 tipos e 13 séries. Nas pp. 2–6, diferencia norma geral, procedimento, documentos de apoio, regulamento de programa, contrato e nota técnica. Na p. 6, alerta que o vínculo pelo número pode ser ambíguo. Nas pp. 7–9, descreve regras gerais, lista documentos e registra perguntas de referência.

O índice cita a versão 1.0.0 de `RG_1100` e três jornadas de referência sem PDFs correspondentes no lote. As normas `NG_010` e `NG_012` aparecem como referências, sem arquivos próprios. Uma resposta sobre esses documentos deve atribuir o que encontra à fonte secundária disponível e apontar a limitação. Os links locais do catálogo dependem do disco de origem. A aplicação deve abrir o PDF efetivamente importado.

## Cenários com resultado verificável

| ID | Pergunta ou condição | Resultado esperado | Evidência |
| --- | --- | --- | --- |
| AC-01 | Em 12/11/2026, com quantos dias de antecedência devo pedir férias? | Solicitar até D-45, em dias corridos. A v3 é a versão aplicável. | `NG_111 v3.0.0`, p. 1 §2.2, p. 2 §4.3.1 e p. 3 §4.5.1 |
| AC-02 | Qual regra valia em 10/07/2026? | 30 dias na versão 2.0.0. A resposta identifica o uso histórico e conserva a data final impressa. | `NG_111 v2.0.0`, p. 1 §2.3, e `NG_111 v3.0.0`, p. 1 §2.2 |
| AC-03 | A solicitação foi aprovada 32 dias antes das férias. Quando a GGC emite o aviso? | Mostrar D-35 na norma e emissão no dia seguinte à aprovação na condição prevista pelo procedimento. Exibir os dois trechos e a precedência declarada, com indicação de divergência para o cenário. | `NG_111 v3.0.0`, p. 3 §4.5.3, e `PX_1111-001 v1.0.0`, p. 3 §8.4.2 e p. 1 §2.2 |
| AC-04 | Quem recebe o escalonamento se o gozo segue sem programação? | Mostrar as duas indicações, DIRAF na diretriz e diretor da área no Anexo B, com localização individual. | `NG_111 v3.0.0`, p. 4 §4.10.3 e p. 7 Anexo B |
| AC-05 | Sintetize os prazos de solicitação, decisão, aviso e assinatura das férias. | Solicitação em D-45 pelo empregado, decisão pelo gestor em até 7 dias corridos após registro, aviso pela GGC até D-35 e assinatura pelo empregado em até 5 dias úteis do recebimento e até D-30. Cada item traz citação e condições aplicáveis. | `NG_111 v3.0.0`, pp. 2–3 §§4.3 e 4.5, e `PX_1111-001 v1.0.0`, p. 3 §8.4.2 para a divergência do aviso |
| AC-06 | Qual o prazo para pedir prorrogação do coworking e quem pede? | A LOCATÁRIA solicita até 30 dias corridos antes do fim da vigência. Para o período inicial, a data é 30/03/2027. | `CTR_2026-012 v1.0.0`, p. 1 cláusulas 2–3 e p. 5 Apêndice C |
| AC-07 | O contrato já está em vigor em 12/11/2026? | Exibir fase declarada “Vigente” e situação temporal “a iniciar” em 30/11/2026. O documento pode ser consultado para planejamento. | `CTR_2026-012 v1.0.0`, p. 1 cabeçalho e cláusula 2 |
| AC-08 | Empregado em afastamento pode se inscrever no Ideias em Campo 2027? | O acervo deixa a elegibilidade desse caso sem confirmação. A nota técnica orienta consultar o NIN. | `NT_2026-021 v1.0.0`, p. 2 §5.4, e `RG_1100 v2.0.0`, p. 2 §4.1 |
| AC-09 | O programa de 2027 tem cinco ou sete fases? | A edição do programa tem sete fases. O funil corporativo tem cinco etapas. Mostrar os respectivos escopos. | `RG_1100 v2.0.0`, p. 2 §4.2, `NG_1130 v1.0.0`, p. 2 §4.2, e `PX_1130-001 v1.0.0`, p. 2 §4 |
| AC-10 | Qual o aluguel e o orçamento total do contrato? | R$ 3.650,00 mensais e R$ 18.250,00 no total de cinco meses. Identificar o valor contratual e distinguir o preço referencial se a nota técnica aparecer. | `CTR_2026-012 v1.0.0`, p. 2 cláusula 7, e `NT_2026-018 v1.0.0`, pp. 2–3 |
| AC-11 | Qual o orçamento da edição 2027 e a verba de premiação? | R$ 96.000,00 no total e R$ 24.000,00 em premiações. Separar os valores e abrir as linhas correspondentes da nota. | `NT_2026-021 v1.0.0`, p. 1 §3 e p. 2 Anexo A |
| AC-12 | Abra a versão 1.0.0 do regulamento Ideias em Campo. | Informar que o PDF original está indisponível no acervo local. Se resumir mudanças, citar o histórico da v2 com a atribuição correta. | `RG_1100 v2.0.0`, p. 1 §2.1, e catálogo, p. 8 |
| AC-13 | Consulte dados de locação com o tema Férias selecionado. | Informar que o tema consultado não oferece evidência suficiente. O usuário pode escolher Locação para uma nova consulta. | Escopo do tema selecionado |

Casos de processamento complementam a matriz. Importar um PDF válido, conferir que a nova versão aparece no tema e abrir uma citação na página física correta. Testar reenvio do mesmo arquivo, PDF inválido e PDF sem texto, verificando que nenhum trecho incompleto fica consultável. Repetir AC-01, AC-03 e AC-06 com perguntas parafraseadas. A matriz define resultados esperados para a futura aplicação.

## Cenários adicionais com PDFs inéditos

Os textos abaixo descrevem os dados de teste a criar. Eles serão enviados pela interface, usando PDFs pesquisáveis com estruturas diferentes e sem configuração específica por código, nome de arquivo ou tema. Executar AC-14 a AC-20 com o modelo desativado. AC-21 simula sua indisponibilidade. AC-22 usa a análise semântica opcional. A interface deve abrir cada evidência na página física correspondente.

| ID | Dados de teste | Resultado esperado |
| --- | --- | --- |
| AC-14 | Um regulamento dá dez dias corridos para apresentar o recurso após a notificação. Um guia aplicável ao mesmo recurso e período dá quinze. | Identificar automaticamente a divergência de prazo. Exibir os dois valores, o marco comum e as citações. |
| AC-15 | A política fixa o envio de um relatório em até cinco dias corridos após a vistoria. O procedimento exige validação antes do envio e só permite validá-lo a partir do sétimo dia após a mesma vistoria. | Detectar a divergência implícita. Citar prazo e pré-requisito e explicar que a validação começa após a janela de envio. |
| AC-16 | Repetir AC-14 com uma fonte sem versão ou vigência verificável. | Sinalizar possível divergência, mostrar as duas passagens e indicar o metadado faltante. |
| AC-17 | Uma fonte fixa cinco dias para o recurso do fornecedor. Outra dá quinze dias para a revisão interna, após outro evento. | Apresentar os dois prazos com seus respectivos escopos. A diferença de prazo entre processos distintos não constitui divergência. |
| AC-18 | Uma versão sucessora passa a exigir quinze dias e declara substituir a versão que exigia dez. | Identificar a mudança histórica, manter ambos os PDFs acessíveis e usar a versão aplicável na data de referência. |
| AC-19 | A política dispensa segunda aprovação para compras emergenciais de até R$ 5.000. Um procedimento diz que toda compra feita fora do expediente exige aprovação de um segundo responsável. Consultar uma compra emergencial de R$ 3.000 fora do expediente. | Mostrar que as condições se sobrepõem e levam a orientações diferentes sobre a segunda aprovação. Citar ambas as condições e a exigência correspondente. |
| AC-20 | Um documento exige uma mensalidade fixa de R$ 1.000 durante seis meses. O anexo do mesmo instrumento, para os mesmos seis meses e sem descontos, fixa o total em R$ 5.500. | Apresentar a divergência implícita com as premissas citadas e o cálculo de R$ 6.000. |
| AC-21 | Configurar um modelo indisponível e repetir uma pergunta com evidência suficiente. | Exibir resposta extrativa com a indicação do modo, as páginas e os trechos consultáveis. |
| AC-22 | Uma política reserva a aprovação de reembolsos à unidade que administra o centro de custo. Um guia atribui a autorização da mesma despesa à equipe que acompanha a execução. Nenhuma fonte identifica se as descrições correspondem à mesma unidade no caso consultado. Executar com análise semântica habilitada. | Relacionar as duas orientações como possível divergência, explicar que a identidade das unidades ficou em aberto e citar as duas fontes. |

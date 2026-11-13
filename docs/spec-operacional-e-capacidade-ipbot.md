# IPBOT · Especificação operacional e plano de capacidade

Complemento à [especificação do MVP](spec-ipbot.md) e ao [plano de entrega em 8h45](plano-entrega-9h-ipbot.md). As metas abaixo orientam a validação. A capacidade depende dos resultados medidos no ambiente de teste.

## Premissas de carga

- A população da empresa é de aproximadamente 3.000 pessoas. O alvo de teste é de até 100 usuários simultâneos consultando o acervo. Usuários virtuais representam sessões com pausas entre ações. Registrar também a taxa efetiva de requisições por segundo.
- Os PDFs pesquisáveis têm em torno de 100 páginas, com variação para baixo e para cima. O plano testa documentos menores, próximos de 100 páginas e pelo menos um acima desse tamanho. Registrar a contagem real de páginas, os bytes e o volume total indexado.
- A consulta extrativa com o modelo desligado é o cenário de referência. Medições com geração ou análise semântica habilitada têm resultados próprios.

## Arquitetura local e contratos

O Docker Compose inicia frontend, API, PostgreSQL e um worker. API e worker compartilham um volume local para os originais, com acesso via backend. O PostgreSQL guarda versões, páginas, trechos, índice textual e estado dos jobs. A API serve consultas enquanto o worker processa os arquivos. [Decisão sobre a fila no PostgreSQL](adr/0002-fila-de-ingestao-no-postgresql.md).

| Operação | Comportamento |
| --- | --- |
| `POST /api/documents` | Recebe PDF e tema. Após guardar o original e confirmar versão e job no banco, retorna `202 Accepted` com `version_id`, `job_id` e estado. Upload inválido retorna erro explicável. |
| `GET /api/documents?topic_id=…` | Lista versões autorizadas com estado `pendente`, `processando`, `pronto` ou `falhou`. Em falha, informa uma mensagem adequada ao usuário. A tela pode atualizar o estado por consultas periódicas. |
| `GET /api/documents/{version_id}/file` | Valida acesso à versão e entrega o original correspondente à citação. A interface abre a página física, numerada a partir de 1. |
| `POST /api/questions` e `POST /api/summaries` | Consultam versões autorizadas e prontas. A busca textual em português usa `tsvector` e índice GIN. As evidências preservam versão, página e trecho literal. |

### Consistência e recuperação da ingestão

1. A API valida a entrada, armazena o original e grava versão pendente e job na mesma transação do banco. O original recebe uma chave gerada pelo backend. Remover um arquivo órfão apenas após confirmar que nenhuma versão o referencia. Um upload só é aceito após confirmar a persistência.
2. O banco garante unicidade por tema e hash do conteúdo, inclusive em uploads concorrentes. Reenvios usam a mesma versão e o job existente quando em andamento. Se a versão já estiver pronta, devolver seu identificador. Uma versão com falha recuperável pode ser reprocessada sem criar cópias. Arquivos diferentes com o mesmo código e versão seguem a verificação prevista na spec principal.
3. O worker reivindica o job com transação curta e prazo de recuperação superior ao limite de execução da tentativa. A extração ocorre fora dessa transação. Um job abandonado volta a ficar disponível após o prazo. Limitar tentativas e aplicar intervalo entre falhas transitórias. Falhas permanentes, como PDF sem texto, têm motivo visível e encerram a tentativa.
4. O worker grava páginas e trechos e publica a versão como `pronto` em uma transação. A publicação exige que a tentativa ainda seja a dona do job. Se o worker perder o prazo e outro recuperar o job, a tentativa antiga fica impedida de publicar. Antes desse commit, a versão permanece fora da busca.
5. O comando de carga inicial usa a mesma rotina do upload, aceita o caminho do acervo e informa o resultado por arquivo. Pode ser executado novamente, preservando os identificadores e as citações já publicados.

### Segurança e operação

- Aplicar autenticação e autorização no backend para importar, listar, consultar e abrir PDFs. A consulta restringe a recuperação ao tema e às versões acessíveis. O acesso direto pelo identificador passa pela mesma regra. Para a demo, testar um perfil com acesso e outro sem acesso ao documento.
- Validar que o arquivo é um PDF legível e estabelecer limites configuráveis de bytes, páginas e tempo de extração. Escolher valores que comportem as amostras maiores que 100 páginas e registrar a configuração usada no teste. PDF ilegível, sem texto ou acima do limite termina com motivo compreensível.
- Tratar texto extraído como dado. Se houver geração ou análise semântica, enviar apenas trechos elegíveis e validar as citações retornadas. Manter credenciais fora do repositório e texto de documentos e perguntas fora dos logs operacionais.
- Correlacionar upload, tentativas e publicação pelo ID do job e da versão. Registrar duração, resultado, tentativas e idade dos jobs pendentes. Começar com um worker e concorrência limitada para preservar recursos da consulta durante a ingestão.

## Testes de integração e falha

| ID | Cenário | Critério |
| --- | --- | --- |
| OP-01 | Subir a aplicação com Compose, importar os três temas e reenviar um PDF válido de aproximadamente 100 páginas. | Biblioteca exibe estado e a ingestão termina. Reenvio preserva a versão, sem duplicar páginas ou trechos. |
| OP-02 | Durante a indexação de uma versão nova, interromper o worker e reiniciá-lo. Fazer consultas ao acervo já indexado nesse intervalo. | A API responde. O job abandonado é recuperado. A versão aparece inteira após a conclusão e apenas uma vez. |
| OP-03 | Enviar PDF ilegível, sem texto ou acima dos limites configurados. | A aplicação apresenta o motivo. O arquivo não gera evidência consultável. |
| OP-04 | Consultar, listar e tentar abrir diretamente a versão como usuário sem acesso. | Nenhum trecho, metadado protegido ou arquivo da versão é exposto. O usuário autorizado abre a página indicada. |
| OP-05 | Usar PDF novo com modelo desligado. Repetir a consulta após simular indisponibilidade do modelo configurado. | A resposta extrativa abre o trecho literal na página esperada. Uma divergência implícita sustentada mostra suas premissas, como no AC-15. |
| OP-06 | Indexar uma sucessora durante consultas sobre a regra corrente e abrir uma citação anterior. | A regra corrente passa a usar a versão aplicável. A citação histórica ainda resolve o mesmo original e página. |

Executar os testes com PostgreSQL real. A [matriz de aceite](acervo-e-cenarios-ipbot.md) detalha os casos funcionais, incluindo vigência, escopo, divergência possível e análise semântica opcional.

## Teste de carga reproduzível

1. Preparar o acervo base e perguntas conhecidas por tema. Usar PDFs sintéticos de tamanhos variados. Incluir perguntas que abram uma citação e registrar os tamanhos e a quantidade de documentos, páginas e trechos.
2. Executar patamares de **25, 50 e 100 usuários virtuais**. Cada sessão consulta, pausa para leitura e, em parte das interações, abre uma citação. Como ponto de partida para o teste, usar pausas de 5 a 15 segundos e abrir a fonte em cerca de um terço das interações. Registrar duração, pausas e proporção de abertura de PDF para reproduzir a carga.
3. Em 100 usuários, repetir o cenário com ingestão concorrente. Enfileirar pelo comando de importação um conjunto com PDFs próximos de 100 páginas e pelo menos um acima de 100. Registrar o intervalo em que consulta e processamento de fato se sobrepuseram.
4. Medir por patamar e fase. Usar a latência de `POST /api/questions` no modo extrativo para a meta de consulta. Reportar abertura de PDF à parte. Contar falhas de conexão, timeouts, respostas 5xx e falhas nas verificações esperadas como erros inesperados.

| Medida | Meta ou registro |
| --- | --- |
| Latência de consulta extrativa | **p95 ≤ 2 s** com 100 usuários virtuais no cenário com ingestão concorrente. |
| Erros inesperados | **< 1%** das operações no cenário de carga, com denominador e contagem registrados. |
| Ingestão | Tempo em fila, tempo de processamento e tempo até `pronto`, por tamanho de arquivo. Registrar falhas e repetições. |
| Ambiente e tráfego | CPU, RAM, versão do código, número de workers e réplicas, volume do acervo, duração, RPS efetivo, modo de IA e limitações observadas. |

Registrar uma linha por execução com esses campos e vincular a saída da ferramenta usada. Se a execução com 100 usuários não for concluída, registrar o maior patamar medido e o que limitou o teste.

## Critérios para evoluir a infraestrutura

| Sinal medido | Próximo experimento |
| --- | --- |
| A idade da fila cresce e a API e o banco têm folga. | Aumentar a concorrência dos workers e comparar vazão e p95 de consulta. Considerar broker dedicado quando a fila competir por recursos do banco ou precisar de operação independente. |
| A API satura enquanto o banco tem capacidade. | Testar duas réplicas atrás de um balanceador, com o estado no PostgreSQL e os PDFs em armazenamento compartilhado. Repetir o mesmo teste de carga. |
| Consultas repetidas dominam a latência mesmo com a busca indexada. | Medir o ganho de cache em sínteses. Incluir tema, revisão do acervo, data de referência e escopo de acesso na chave. |
| A necessidade de operação ultrapassa a demo local. | Dimensionar a integração AWS com dados do teste. Avaliar armazenamento de objetos, execução independente de API e workers e uma fila gerenciada conforme o gargalo. |

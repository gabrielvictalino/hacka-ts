---
status: accepted
---

# Fila de ingestão no PostgreSQL

O IPBOT precisa extrair PDFs longos durante consultas simultâneas na demo local. O MVP registra a versão e o job na mesma transação do PostgreSQL e usa um worker separado para extração e indexação. A fila no banco reduz dependências dentro da janela de entrega e permite recuperar jobs interrompidos. O teste de carga mede se a fila compete com as consultas antes de avaliar um broker dedicado.

[Especificação operacional e plano de capacidade](../spec-operacional-e-capacidade-ipbot.md).

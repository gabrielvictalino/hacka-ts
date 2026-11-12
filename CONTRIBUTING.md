# Colaboração no IPBOT

## Branches e revisão

| Branch | Papel | Entrada |
| --- | --- | --- |
| `main` | Entregas revisadas | PR de `dev` deste repositório |
| `dev` | Integração do trabalho em andamento | PR de uma branch de trabalho |
| `<tipo>/<descricao-curta>` | Uma mudança por branch | Criada a partir de `dev` |

Use descrições em kebab-case e um dos tipos `feat`, `fix`, `docs`, `refactor`, `test`, `chore` ou `style`. Inclua o número da issue quando houver, como em `feat/42-upload-pdf`. Escreva Conventional Commits no formato `<tipo>(<escopo>): <resumo>`, por exemplo, `feat(biblioteca): adiciona upload de PDF`.

1. Atualize a `dev` local e crie a branch de trabalho.

   ```sh
   git switch dev
   git pull --ff-only origin dev
   git switch -c feat/upload-pdf
   ```

2. Antes de abrir o PR, atualize a branch com `origin/dev`. Abra o PR para `dev`, descreva o motivo, a validação e a documentação afetada. Faça ajustes de revisão em novos commits.
3. Faça merge em `dev` após uma aprovação e a CI verde. Use merge commit para preservar o histórico ou squash para reunir commits intermediários. Exclua a branch de trabalho após o merge.
4. Abra o PR de `dev` para `main` quando a entrega estiver validada. Depois que os templates estiverem na branch padrão, use o [modelo de entrega](https://github.com/gabrielvictalino/hacka-ts/compare/main...dev?quick_pull=1&template=entrega-main.md). Faça merge com **Create a merge commit** para preservar a ancestralidade de `dev`.

Após promover uma entrega, sincronize o novo commit de `main` com `dev` por PR. Rode `git fetch origin`, crie `chore/sincronizar-main` a partir de `origin/dev` e faça merge de `origin/main` nessa branch. Abra um PR para `dev` e use **Create a merge commit** para que a próxima entrega já inclua o histórico de `main`.

## Issues e milestones

Use os modelos de funcionalidade, bug e tarefa. Agrupe issues no milestone da entrega e atribua um responsável a cada issue. O fluxo de upload, pergunta e abertura da fonte é o primeiro marco técnico do MVP.

Referencie a issue com `#número` nos PRs para `dev`. Use `Closes #número` no PR de entrega para `main` quando a issue estiver concluída. O GitHub fecha issues vinculadas automaticamente no merge para a branch padrão. [Vincular PRs a issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)

## CI

O check **CI IPBOT** roda em PRs para `dev` e `main`. Ele valida o caminho de integração e usa `git diff --check` no merge de teste do GitHub. A CI deve ganhar build, lint e testes do front-end e do back-end quando a stack e os comandos do projeto estiverem disponíveis. Acrescente os testes de integração com o banco assim que houver código e ambiente para executá-los.

## Ativação no GitHub

1. Crie a branch remota `dev` a partir de `main`, caso ainda não exista. Publique os arquivos desta configuração em uma branch `chore/configurar-workflow` baseada em `dev` e abra o primeiro PR para `dev`.
2. Confirme a execução do check **CI IPBOT** e faça merge do PR em `dev` após a revisão. Depois, abra o PR de `dev` para `main` e confirme que o mesmo check é exibido.
3. Um administrador deve manter **Allow merge commits** e **Allow squash merging** disponíveis em **Settings → General → Pull Requests**. Os arquivos JSON precisam ser importados para que as proteções entrem em vigor. Em **Settings → Rules → Rulesets**, confira as regras existentes e importe os JSONs de [`dev`](.github/rulesets/dev.json) e [`main`](.github/rulesets/main.json). Confira o check **CI IPBOT** em cada ruleset e selecione **GitHub Actions** como origem do check quando estiver disponível. [Importar rulesets no GitHub](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#importing-prebuilt-rulesets)
4. Confira que ambas as branches exigem PR, uma aprovação e CI verde, com force push e exclusão bloqueados e sem atores com bypass. Em `main`, confirme também que o PR precisa estar atualizado com a base e que o método permitido é merge commit. Faça merge do PR de entrega após a aprovação para disponibilizar os templates no GitHub.

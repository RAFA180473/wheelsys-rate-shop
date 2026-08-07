# Fluxo de atualização de preços

## Objetivo

Garantir que uma nova atualização usa as versões mais recentes dos ficheiros SharePoint e que o painel é regenerado sem editar manualmente as tarifas dentro do HTML.

## Configuração inicial — uma vez

1. Guardar a versão atual do painel HTML localmente.
2. Executar:

```bash
python scripts/import_html.py /caminho/ICONIQ_Rate_Shop_DiscoverCars.html
```

3. O ficheiro é copiado para `public/index.template.html` apenas se contiver exatamente uma definição `const RATES = ...;`.

## Em cada atualização

1. Copiar os Excel do SharePoint para `data/incoming/`.
2. Executar:

```bash
python scripts/build_all.py
```

3. `select_latest.py` agrupa os ficheiros por família e escolhe o mais recente, dando prioridade à data no nome e usando a data de modificação apenas quando necessário.
4. `build_rates.py` lê os Excel escolhidos e gera `public/data/rates.json`.
5. `inject_rates.py` substitui **apenas** a constante `RATES` do template e escreve `public/index.html`.
6. `validate_build.py` confirma BK, FCI, Lisboa, Porto, Faro e marcadores funcionais do painel.
7. Rever `selection_manifest.json` e `build_manifest.json`.

## Colunas de tarifário esperadas

- Group
- Pickup start
- Pickup end
- Rate zone
- Booking start
- Booking end
- 1 per day
- 2 per day
- 3 per day
- 4 - 6 per day
- 7 per day
- 8 - 13 per day
- 14 - 29 per day
- 30+ per day

## Princípio de segurança

Se o HTML real não estiver configurado ou a validação falhar, o processo termina com erro. Não publica silenciosamente um template de teste ou dados incompletos.

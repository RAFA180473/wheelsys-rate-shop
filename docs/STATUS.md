# Estado do projeto

## Concluído

- Estrutura independente do Wheelsys Rate Shop.
- Seleção automática da versão mais recente por família de ficheiros.
- Suporte de datas no nome em formatos comuns, com fallback para data de modificação.
- Separação automática BK / FCI.
- Conversão de Rate zones LXA / OPT / FAO para Lisboa / Porto / Faro.
- Geração de `rates.json`.
- Injeção isolada da constante `RATES` no HTML.
- Validação final obrigatória antes de publicação.

## Próximo passo operacional

Importar a versão real atual de `ICONIQ_Rate_Shop_DiscoverCars.html` com `scripts/import_html.py` e depois executar `scripts/build_all.py` com os ficheiros reais mais recentes do SharePoint em `data/incoming/`.

# Wheelsys Rate Shop

Projeto **Rate Iconiq / Wheelsys Rate Shop** para atualização, tratamento e publicação de preços.

> Projeto independente. Não reutilizar ficheiros, pastas, regras ou referências de outros projetos sem indicação explícita.

## Regra principal

Em cada atualização, usar **sempre a versão mais recente de cada família de ficheiros proveniente do SharePoint**:

1. data reconhecida no nome do ficheiro (`YYYY-MM-DD`, `YYYYMMDD`, `DD-MM-YYYY`, `DDMMYYYY` ou `DDMMYY`);
2. data de modificação como fallback.

A decisão fica registada em `selection_manifest.json`.

## Estrutura

```text
wheelsys-rate-shop/
├── data/
│   ├── incoming/          # ficheiros novos do SharePoint (não versionados)
│   ├── selected/          # latest por família (não versionados)
│   └── processed/
├── public/
│   ├── index.template.html # HTML real, importado uma vez
│   ├── index.html          # HTML final gerado
│   └── data/rates.json
├── scripts/
│   ├── import_html.py
│   ├── select_latest.py
│   ├── build_rates.py
│   ├── inject_rates.py
│   ├── validate_build.py
│   └── build_all.py
├── docs/UPDATE_FLOW.md
├── requirements.txt
├── selection_manifest.json
└── build_manifest.json
```

## Primeira configuração

```bash
python -m pip install -r requirements.txt
python scripts/import_html.py /caminho/ICONIQ_Rate_Shop_DiscoverCars.html
```

O importador valida que existe exatamente uma constante JavaScript `RATES` antes de aceitar o HTML.

## Atualização de preços

1. Colocar os novos Excel em `data/incoming/` **sem apagar necessariamente os anteriores**.
2. Executar:

```bash
python scripts/build_all.py
```

O processo executa automaticamente:

**latest → rates.json → RATES no HTML → validação final**.

## BK / FCI

- nome contendo `FCI` → `FCI`;
- restantes ficheiros de tarifas → `BK`.

## Localizações

| Rate zone | Localização |
|---|---|
| LXA | Lisboa |
| OPT | Porto |
| FAO | Faro |

## Controlo antes de publicar

Confirmar:

- `selection_manifest.json`: ficheiros efetivamente escolhidos;
- `build_manifest.json`: linhas importadas e avisos;
- `public/index.html`: resultado final;
- `python scripts/validate_build.py`: deve terminar em `VALIDAÇÃO OK`.

## Segurança

Os ficheiros brutos do SharePoint e os ficheiros selecionados ficam fora do Git através do `.gitignore`.

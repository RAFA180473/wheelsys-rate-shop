# Publicação

Esta pasta recebe o painel final.

Antes do primeiro build, importar o HTML real atual:

```bash
python scripts/import_html.py /caminho/ICONIQ_Rate_Shop_DiscoverCars.html
```

Depois, em cada atualização:

```bash
python scripts/build_all.py
```

`index.template.html` é a interface protegida; `index.html` é regenerado substituindo apenas `const RATES = ...;`.

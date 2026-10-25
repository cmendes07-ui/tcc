# Conversor de Templates LaTeX UEMA (`proposta` $\leftrightarrow$ `monografia`)

O script [`converter.py`](./converter.py) converte automaticamente um projeto entre **Proposta Tecnológica** e **Monografia**, preservando os metadados do aluno (`info_documento.tex`), referências (`bib/`), imagens (`img/`), elementos pré-textuais e migrando o texto dos capítulos (`textuais/`).

> **Download Automático via GitHub:** Caso o usuário tenha apenas um dos projetos baixado no computador, o script baixa automaticamente o outro modelo direto do repositório oficial [`https://github.com/mfklcp/templates-tex`](https://github.com/mfklcp/templates-tex) (sem precisar instalar bibliotecas externas).

---

## Como usar no Terminal

### 1. Converter gerando uma nova pasta ao lado (Recomendado)
Detecta automaticamente se a pasta é `proposta` ou `monografia` e cria uma nova pasta convertida:

```bash
python3 templates/converters/converter.py templates/proposta-tecnologia-uema
```
*(Gera a pasta `templates/proposta-tecnologia-uema-monografia`)*

### 2. Especificar a pasta de saída (`-s` / `--saida`)
```bash
python3 templates/converters/converter.py ./meu-tcc -s ./meu-tcc-monografia
```

### 3. Converter a própria pasta (`--in-place`)
Converte o projeto no próprio diretório e salva uma cópia dos capítulos antigos em `textuais/_backup_*`:
```bash
python3 templates/converters/converter.py ./meu-tcc --in-place
```

### 4. Forçar busca da versão mais recente direto do GitHub (`--github`)
Mesmo se você tiver os dois modelos locais, pode forçar o download do template de referência direto do GitHub:
```bash
python3 templates/converters/converter.py ./meu-tcc --github
```

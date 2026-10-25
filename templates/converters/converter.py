#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversor entre os templates LaTeX da UEMA:
  - Proposta Tecnológica (proposta-tecnologia-uema)
  - Monografia (monografia-uema)

Se o template de destino não estiver disponível localmente, o script baixa
automaticamente os arquivos oficiais direto do repositório GitHub:
https://github.com/mfklcp/templates-tex
"""

import argparse
import io
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

GITHUB_REPO = "mfklcp/templates-tex"
GITHUB_BRANCHES = ["master", "main"]

TEMPLATE_FOLDERS = {
    "proposta": "proposta-tecnologia-uema",
    "monografia": "monografia-uema",
}


def detectar_tipo_projeto(caminho_projeto: Path) -> str:
    """Detecta se o projeto de origem é 'proposta' ou 'monografia'."""
    info_file = caminho_projeto / "info_documento.tex"
    if info_file.exists():
        conteudo = info_file.read_text(encoding="utf-8", errors="ignore").lower()
        if "\\tipotrabalho{monografia}" in conteudo:
            return "monografia"
        if "\\tipotrabalho{proposta" in conteudo:
            return "proposta"

    textuais_dir = caminho_projeto / "textuais"
    if (textuais_dir / "01-introducao.tex").exists():
        return "monografia"
    if (textuais_dir / "01-justificativa.tex").exists():
        return "proposta"

    raise ValueError(
        f"Não foi possível detectar o tipo do projeto em '{caminho_projeto}'. "
        "Certifique-se de apontar para uma pasta contendo 'main.tex' e 'info_documento.tex'."
    )


def baixar_template_github(nome_pasta_template: str, destino_temp: Path) -> Path:
    """Baixa o repositório do GitHub como ZIP e extrai o template desejado."""
    ultimo_erro = None
    for branch in GITHUB_BRANCHES:
        url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{branch}.zip"
        try:
            print(f"[GitHub] Baixando template '{nome_pasta_template}' de {url} ...")
            req = urllib.request.Request(url, headers={"User-Agent": "uema-template-converter/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                dados_zip = resp.read()

            with zipfile.ZipFile(io.BytesIO(dados_zip)) as zf:
                prefixo_alvo = None
                for member in zf.namelist():
                    partes = member.split("/")
                    if len(partes) >= 3 and partes[1] == "templates" and partes[2] == nome_pasta_template:
                        prefixo_alvo = "/".join(partes[:3]) + "/"
                        break

                if not prefixo_alvo:
                    raise FileNotFoundError(
                        f"A pasta 'templates/{nome_pasta_template}' não foi encontrada na branch '{branch}' do GitHub."
                    )

                pasta_extraida = destino_temp / nome_pasta_template
                pasta_extraida.mkdir(parents=True, exist_ok=True)

                for member in zf.namelist():
                    if member.startswith(prefixo_alvo) and not member.endswith("/"):
                        caminho_rel = member[len(prefixo_alvo):]
                        destino_arquivo = pasta_extraida / caminho_rel
                        destino_arquivo.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(destino_arquivo, "wb") as dst:
                            shutil.copyfileobj(src, dst)

                print(f"[GitHub] Template '{nome_pasta_template}' baixado com sucesso!")
                return pasta_extraida
        except Exception as e:
            ultimo_erro = e

    raise RuntimeError(
        f"Falha ao baixar o template '{nome_pasta_template}' do GitHub ({GITHUB_REPO}): {ultimo_erro}"
    )


def obter_caminho_template_referencia(
    tipo_destino: str, caminho_origem: Path, temp_dir: Path, forcar_github: bool = False
) -> Path:
    """
    Procura o template de destino localmente; caso não exista (usuário baixou
    apenas um projeto) ou '--github' seja usado, baixa direto do GitHub.
    """
    nome_pasta = TEMPLATE_FOLDERS[tipo_destino]

    if not forcar_github:
        possiveis_locais = [
            Path(__file__).resolve().parent.parent / nome_pasta,
            caminho_origem.resolve().parent / nome_pasta,
            Path.cwd() / "templates" / nome_pasta,
            Path.cwd() / nome_pasta,
        ]
        for local in possiveis_locais:
            if (local / "main.tex").exists() and (local / "configs").is_dir():
                print(f"[Local] Usando template de referência encontrado em: {local}")
                return local

    return baixar_template_github(nome_pasta, temp_dir)


def converter_info_documento(conteudo_atual: str, tipo_destino: str) -> str:
    """Atualiza \\tipotrabalho e \\preambulo preservando autor, título, curso, etc."""
    if tipo_destino == "monografia":
        conteudo = re.sub(
            r"\\tipotrabalho\{[^}]*\}",
            r"\\tipotrabalho{Monografia}",
            conteudo_atual,
        )
        conteudo = re.sub(
            r"(\\preambulo\{)\s*Proposta\s+Tecnol[óo]gica\s+apresentad[ao]",
            r"\1Monografia apresentada",
            conteudo,
            flags=re.IGNORECASE,
        )
        if "TÍTULO DA PROPOSTA TECNOLÓGICA" in conteudo:
            conteudo = conteudo.replace(
                "TÍTULO DA PROPOSTA TECNOLÓGICA",
                "TÍTULO DA MONOGRAFIA: subtítulo (se houver)",
            )
    else:
        conteudo = re.sub(
            r"\\tipotrabalho\{[^}]*\}",
            r"\\tipotrabalho{Proposta Tecnológica}",
            conteudo_atual,
        )
        conteudo = re.sub(
            r"(\\preambulo\{)\s*Monografia\s+apresentad[ao]",
            r"\1Proposta Tecnológica apresentada",
            conteudo,
            flags=re.IGNORECASE,
        )
        if "TÍTULO DA MONOGRAFIA: subtítulo (se houver)" in conteudo:
            conteudo = conteudo.replace(
                "TÍTULO DA MONOGRAFIA: subtítulo (se houver)",
                "TÍTULO DA PROPOSTA TECNOLÓGICA",
            )
    return conteudo


def remover_comando_chapter(texto: str) -> str:
    """Remove a linha \\chapter{...} inicial de um arquivo textual para mesclagem."""
    return re.sub(r"^\s*\\chapter\{[^}]*\}\s*", "", texto, count=1).strip()


def migrar_textuais_proposta_para_monografia(
    textuais_origem: Path, textuais_template_mono: Path, textuais_destino: Path
):
    """Converte os capítulos da Proposta Tecnológica para a estrutura de Monografia sem perda de dados."""
    textuais_destino.mkdir(parents=True, exist_ok=True)
    arquivos_processados = set()

    # 1. Introdução: mescla 01-justificativa, 02-objetivos e 04-metodologia
    partes_intro = ["\\chapter{INTRODUÇÃO}"]
    arquivos_para_intro = [
        ("01-justificativa.tex", "Justificativa"),
        ("02-objetivos.tex", "Objetivos"),
        ("04-metodologia.tex", "Metodologia"),
    ]
    encontrou_intro = False
    for nome_arq, rotulo in arquivos_para_intro:
        arq = textuais_origem / nome_arq
        if arq.exists():
            encontrou_intro = True
            arquivos_processados.add(nome_arq)
            corpo = remover_comando_chapter(arq.read_text(encoding="utf-8", errors="ignore"))
            partes_intro.append(f"% --- Conteúdo migrado de {nome_arq} ({rotulo}) ---\n{corpo}")

    if encontrou_intro:
        (textuais_destino / "01-introducao.tex").write_text(
            "\n\n".join(partes_intro) + "\n", encoding="utf-8"
        )
    else:
        shutil.copy2(textuais_template_mono / "01-introducao.tex", textuais_destino / "01-introducao.tex")

    # 2. Referencial Teórico: migra de 03-referencial_teorico.tex
    ref_origem = textuais_origem / "03-referencial_teorico.tex"
    if ref_origem.exists():
        arquivos_processados.add("03-referencial_teorico.tex")
        shutil.copy2(ref_origem, textuais_destino / "02-referencial_teorico.tex")
    else:
        shutil.copy2(
            textuais_template_mono / "02-referencial_teorico.tex",
            textuais_destino / "02-referencial_teorico.tex",
        )

    # 3. Resultados e Discussão: mescla 05-proposta_tecnologica.tex e 06-cronograma.tex
    partes_res = ["\\chapter{RESULTADOS E DISCUSSÃO}"]
    arquivos_para_res = [
        ("05-proposta_tecnologica.tex", "Proposta Tecnológica"),
        ("06-cronograma.tex", "Cronograma"),
    ]
    encontrou_res = False
    for nome_arq, rotulo in arquivos_para_res:
        arq = textuais_origem / nome_arq
        if arq.exists():
            encontrou_res = True
            arquivos_processados.add(nome_arq)
            corpo = remover_comando_chapter(arq.read_text(encoding="utf-8", errors="ignore"))
            partes_res.append(f"% --- Conteúdo migrado de {nome_arq} ({rotulo}) ---\n{corpo}")

    if encontrou_res:
        (textuais_destino / "03-resultados_discussao.tex").write_text(
            "\n\n".join(partes_res) + "\n", encoding="utf-8"
        )
    else:
        shutil.copy2(
            textuais_template_mono / "03-resultados_discussao.tex",
            textuais_destino / "03-resultados_discussao.tex",
        )

    # 4. Considerações Finais: copia do template de monografia
    shutil.copy2(
        textuais_template_mono / "04-consideracoes_finais.tex",
        textuais_destino / "04-consideracoes_finais.tex",
    )

    # Preserva quaisquer arquivos .tex extras criados pelo usuário em textuais/
    for arq_extra in textuais_origem.iterdir():
        if arq_extra.is_file() and arq_extra.name not in arquivos_processados:
            shutil.copy2(arq_extra, textuais_destino / arq_extra.name)


def migrar_textuais_monografia_para_proposta(
    textuais_origem: Path, textuais_template_prop: Path, textuais_destino: Path
):
    """Converte os capítulos da Monografia para a estrutura de Proposta Tecnológica sem perda de dados."""
    textuais_destino.mkdir(parents=True, exist_ok=True)
    arquivos_processados = set()

    # 1. Justificativa: recebe conteúdo de 01-introducao.tex
    intro_origem = textuais_origem / "01-introducao.tex"
    if intro_origem.exists():
        arquivos_processados.add("01-introducao.tex")
        corpo_intro = remover_comando_chapter(intro_origem.read_text(encoding="utf-8", errors="ignore"))
        conteudo_just = (
            "\\chapter{JUSTIFICATIVA}\n"
            "% --- Conteúdo migrado de 01-introducao.tex ---\n"
            f"{corpo_intro}\n"
        )
        (textuais_destino / "01-justificativa.tex").write_text(conteudo_just, encoding="utf-8")
    else:
        shutil.copy2(textuais_template_prop / "01-justificativa.tex", textuais_destino / "01-justificativa.tex")

    # 2. Objetivos: copia do template de proposta
    shutil.copy2(textuais_template_prop / "02-objetivos.tex", textuais_destino / "02-objetivos.tex")

    # 3. Referencial Teórico: migra de 02-referencial_teorico.tex
    ref_origem = textuais_origem / "02-referencial_teorico.tex"
    if ref_origem.exists():
        arquivos_processados.add("02-referencial_teorico.tex")
        shutil.copy2(ref_origem, textuais_destino / "03-referencial_teorico.tex")
    else:
        shutil.copy2(
            textuais_template_prop / "03-referencial_teorico.tex",
            textuais_destino / "03-referencial_teorico.tex",
        )

    # 4. Metodologia: copia do template de proposta
    shutil.copy2(textuais_template_prop / "04-metodologia.tex", textuais_destino / "04-metodologia.tex")

    # 5. Proposta Tecnológica: mescla 03-resultados_discussao.tex e 04-consideracoes_finais.tex
    partes_prop = ["\\chapter{PROPOSTA TECNOLÓGICA}"]
    arquivos_para_prop = [
        ("03-resultados_discussao.tex", "Resultados e Discussão"),
        ("04-consideracoes_finais.tex", "Considerações Finais"),
    ]
    encontrou_prop = False
    for nome_arq, rotulo in arquivos_para_prop:
        arq = textuais_origem / nome_arq
        if arq.exists():
            encontrou_prop = True
            arquivos_processados.add(nome_arq)
            corpo = remover_comando_chapter(arq.read_text(encoding="utf-8", errors="ignore"))
            partes_prop.append(f"% --- Conteúdo migrado de {nome_arq} ({rotulo}) ---\n{corpo}")

    if encontrou_prop:
        (textuais_destino / "05-proposta_tecnologica.tex").write_text(
            "\n\n".join(partes_prop) + "\n", encoding="utf-8"
        )
    else:
        shutil.copy2(
            textuais_template_prop / "05-proposta_tecnologica.tex",
            textuais_destino / "05-proposta_tecnologica.tex",
        )

    # 6. Cronograma: copia do template de proposta
    shutil.copy2(textuais_template_prop / "06-cronograma.tex", textuais_destino / "06-cronograma.tex")

    # Preserva quaisquer arquivos .tex extras criados pelo usuário em textuais/
    for arq_extra in textuais_origem.iterdir():
        if arq_extra.is_file() and arq_extra.name not in arquivos_processados:
            shutil.copy2(arq_extra, textuais_destino / arq_extra.name)


def converter_projeto(
    caminho_origem: Path,
    caminho_saida: Path,
    tipo_destino: str = None,
    in_place: bool = False,
    forcar_github: bool = False,
):
    caminho_origem = caminho_origem.resolve()
    if not caminho_origem.is_dir():
        raise FileNotFoundError(f"A pasta de origem '{caminho_origem}' não existe.")

    tipo_origem = detectar_tipo_projeto(caminho_origem)
    if tipo_destino is None:
        tipo_destino = "monografia" if tipo_origem == "proposta" else "proposta"

    if tipo_origem == tipo_destino:
        print(f"Aviso: O projeto de origem já é do tipo '{tipo_destino}'. Atualizando configurações...")

    with tempfile.TemporaryDirectory() as tmp_str:
        temp_dir = Path(tmp_str)
        template_ref = obter_caminho_template_referencia(
            tipo_destino, caminho_origem, temp_dir, forcar_github=forcar_github
        )

        # Trabalha em um diretório temporário de montagem para suportar tanto in-place quanto nova pasta
        staging_dir = temp_dir / "staging_output"
        shutil.copytree(caminho_origem, staging_dir)

        # 1. Atualiza configs/ e main.tex a partir do template de referência
        if (staging_dir / "configs").exists():
            shutil.rmtree(staging_dir / "configs")
        shutil.copytree(template_ref / "configs", staging_dir / "configs")
        shutil.copy2(template_ref / "main.tex", staging_dir / "main.tex")

        # 2. Atualiza info_documento.tex preservando dados do autor
        info_staging = staging_dir / "info_documento.tex"
        if info_staging.exists():
            novo_info = converter_info_documento(
                info_staging.read_text(encoding="utf-8", errors="ignore"), tipo_destino
            )
            info_staging.write_text(novo_info, encoding="utf-8")
        else:
            shutil.copy2(template_ref / "info_documento.tex", info_staging)

        # 3. Sincroniza pre-textuais/ sem sobrescrever arquivos já existentes do usuário
        pre_ref = template_ref / "pre-textuais"
        pre_staging = staging_dir / "pre-textuais"
        pre_staging.mkdir(parents=True, exist_ok=True)
        if pre_ref.is_dir():
            for arq_pre in pre_ref.iterdir():
                if arq_pre.is_file() and not (pre_staging / arq_pre.name).exists():
                    shutil.copy2(arq_pre, pre_staging / arq_pre.name)

        # 4. Migra capítulos em textuais/ e guarda backup integral dos originais
        textuais_antigos = temp_dir / "textuais_origem"
        shutil.copytree(staging_dir / "textuais", textuais_antigos)
        shutil.rmtree(staging_dir / "textuais")

        if tipo_origem == "proposta" and tipo_destino == "monografia":
            migrar_textuais_proposta_para_monografia(
                textuais_antigos, template_ref / "textuais", staging_dir / "textuais"
            )
        elif tipo_origem == "monografia" and tipo_destino == "proposta":
            migrar_textuais_monografia_para_proposta(
                textuais_antigos, template_ref / "textuais", staging_dir / "textuais"
            )
        else:
            shutil.copytree(textuais_antigos, staging_dir / "textuais")

        # Salva cópia de segurança dos capítulos originais em textuais/_backup_<tipo_origem>
        backup_textuais = staging_dir / "textuais" / f"_backup_{tipo_origem}"
        if backup_textuais.exists():
            shutil.rmtree(backup_textuais)
        shutil.copytree(textuais_antigos, backup_textuais)

        # Remove arquivos auxiliares de compilação antigos
        for ext in ("*.aux", "*.lof", "*.lot", "*.toc", "*.log", "*.bbl", "*.blg", "*.out", "*.brf", "*.fls", "*.fdb_latexmk", "*.synctex.gz"):
            for aux_file in staging_dir.rglob(ext):
                aux_file.unlink(missing_ok=True)

        # 5. Grava no destino final
        if in_place:
            caminho_saida = caminho_origem
            shutil.rmtree(caminho_saida)
            shutil.copytree(staging_dir, caminho_saida)
            print(f"[OK] Projeto convertido no próprio diretório: {caminho_saida}")
        else:
            caminho_saida = caminho_saida.resolve()
            if caminho_saida.exists():
                shutil.rmtree(caminho_saida)
            shutil.copytree(staging_dir, caminho_saida)
            print(f"[OK] Projeto convertido ({tipo_origem} -> {tipo_destino}) criado em:\n     {caminho_saida}")
        print(f"     (Backup integral dos capítulos originais salvo em: textuais/_backup_{tipo_origem}/)")


def main():
    parser = argparse.ArgumentParser(
        description="Converte projetos LaTeX UEMA entre Proposta Tecnológica e Monografia."
    )
    parser.add_argument(
        "origem",
        nargs="?",
        default=".",
        help="Caminho da pasta do projeto LaTeX de origem (padrão: diretório atual '.')",
    )
    parser.add_argument(
        "-p",
        "--para",
        choices=["monografia", "proposta"],
        default=None,
        help="Tipo de destino ('monografia' ou 'proposta'). Se omitido, inverte automaticamente o tipo atual.",
    )
    parser.add_argument(
        "-s",
        "--saida",
        default=None,
        help="Caminho da pasta de saída. Se omitido, cria '<pasta-origem>-<tipo-destino>'.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Converte o próprio diretório de origem (mantendo backup dos capítulos antigos em textuais/_backup_*).",
    )
    parser.add_argument(
        "--github",
        action="store_true",
        help="Força o download do template de referência direto do GitHub (mfklcp/templates-tex).",
    )

    args = parser.parse_args()
    caminho_origem = Path(args.origem).resolve()

    try:
        tipo_origem = detectar_tipo_projeto(caminho_origem)
        tipo_destino = args.para or ("monografia" if tipo_origem == "proposta" else "proposta")

        if args.in_place:
            caminho_saida = caminho_origem
        elif args.saida:
            caminho_saida = Path(args.saida)
        else:
            caminho_saida = caminho_origem.parent / f"{caminho_origem.name}-{tipo_destino}"

        converter_projeto(
            caminho_origem=caminho_origem,
            caminho_saida=caminho_saida,
            tipo_destino=tipo_destino,
            in_place=args.in_place,
            forcar_github=args.github,
        )
    except Exception as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

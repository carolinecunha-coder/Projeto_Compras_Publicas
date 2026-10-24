"""
carregar.py - CARGA NO POSTGRESQL

Lê e valida os arquivos processados, recria o banco,
cria as tabelas, carrega os dados e confere os resultados.

Execute pela pasta raiz do projeto:
    python -m src.carregar

ATENÇÃO:
banco.recriar_banco() apaga e recria o banco configurado.
"""

import pandas as pd

from src import banco, config


def ler(nome, **opcoes):
    """Lê CSVs processados, preservando campos vazios como valores ausentes."""

    return pd.read_csv(
        config.PASTA_PROCESSED / f"{nome}.csv",
        keep_default_na=False,
        na_values=[""],
        **opcoes,
    )


def tuplas(tabela, colunas):
    """Converte o DataFrame em tuplas, transformando ausências em None."""

    dados = tabela[colunas].astype(object)
    dados = dados.where(pd.notna(dados), None)

    return [
        tuple(linha)
        for linha in dados.itertuples(index=False, name=None)
    ]


def inserir(conexao, tabela, colunas, dados):
    """Insere os registros em lote no PostgreSQL."""

    marcadores = ", ".join(["%s"] * len(colunas))

    comando = (
        f"INSERT INTO {tabela} ({', '.join(colunas)}) "
        f"VALUES ({marcadores})"
    )

    banco.inserir_em_lote(
        conexao,
        comando,
        tuplas(dados, colunas),
    )

    print(f"   {tabela}: {len(dados)} linhas")


def converter_comparavel(coluna):
    """
    Mantém comparavel como inteiro:
    1 = item comparável
    0 = item não comparável

    Impede valores desconhecidos ou vazios.
    """

    texto = coluna.astype("string").str.strip().str.lower()

    mapa = {
        "1": 1,
        "0": 0,
        "1.0": 1,
        "0.0": 0,
    }

    convertido = texto.map(mapa)

    invalidos = convertido.isna()

    if invalidos.any():
        valores = coluna[invalidos].drop_duplicates().tolist()

        raise ValueError(
            "A coluna 'comparavel' contém valores vazios "
            "ou diferentes de 0 e 1: "
            f"{valores[:10]!r}. "
            "A carga foi interrompida antes de recriar o banco."
        )

    return convertido.astype("int64")


def preparar_fato():
    """Lê e valida a tabela fato antes de recriar o banco."""

    fato = ler("fato_item_contratado")

    colunas_obrigatorias = [
        "numero_controle_pncp",
        "numero_item",
        "sk_orgao",
        "sk_fornecedor",
        "sk_modalidade",
        "sk_localidade",
        "data_publicacao",
        "data_homologacao",
        "descricao_item",
        "perfil_gasto",
        "quantidade",
        "valor_unitario_estimado",
        "valor_total_estimado",
        "valor_unitario_homologado",
        "valor_total_homologado",
        "comparavel",
        "economia_valor",
        "dias_ciclo",
    ]

    faltantes = [
        coluna
        for coluna in colunas_obrigatorias
        if coluna not in fato.columns
    ]

    if faltantes:
        raise ValueError(
            "Colunas ausentes em fato_item_contratado.csv: "
            f"{faltantes}"
        )

    # Preserva os valores 0 e 1 definidos no montar_tabelas.py.
    fato["comparavel"] = converter_comparavel(
        fato["comparavel"]
    )

    # Preserva os ciclos ausentes como NULL no PostgreSQL.
    fato["dias_ciclo"] = pd.to_numeric(
        fato["dias_ciclo"],
        errors="coerce",
    ).astype("Int64")

    if len(fato) != 6126:
        raise ValueError(
            f"A fato tem {len(fato)} linhas; "
            "o esperado pelo professor é 6126. "
            "A carga foi interrompida antes de recriar o banco."
        )

    comparaveis = int(
        (fato["comparavel"] == 1).sum()
    )

    nao_comparaveis = int(
        (fato["comparavel"] == 0).sum()
    )

    nulos = int(
        fato["comparavel"].isna().sum()
    )

    print(
        "Validação de comparavel no CSV: "
        f"comparáveis={comparaveis}, "
        f"não comparáveis={nao_comparaveis}, "
        f"nulos={nulos}"
    )

    if (
        comparaveis != 5457
        or nao_comparaveis != 669
        or nulos != 0
    ):
        raise ValueError(
            "Os valores de comparavel não correspondem "
            "à conferência esperada: "
            "5457 comparáveis, 669 não comparáveis e "
            "zero nulos. A carga foi interrompida."
        )

    return fato[colunas_obrigatorias]


def main():
    # Primeiro valida os CSVs, antes de recriar o banco.
    fato = preparar_fato()

    tabelas_dimensao = [
        (
            "dim_orgao",
            [
                "sk_orgao",
                "cnpj_orgao",
                "nome_orgao",
                "poder",
            ],
        ),
        (
            "dim_fornecedor",
            [
                "sk_fornecedor",
                "ni_fornecedor",
                "nome_fornecedor",
                "tipo_pessoa",
                "porte",
            ],
        ),
        (
            "dim_modalidade",
            [
                "sk_modalidade",
                "modalidade_id",
                "nome_modalidade",
            ],
        ),
        (
            "dim_localidade",
            [
                "sk_localidade",
                "uf_sigla",
                "uf_nome",
                "regiao",
            ],
        ),
    ]

    dimensoes = {
        nome: ler(nome, dtype=str)
        for nome, _ in tabelas_dimensao
    }

    for nome, colunas in tabelas_dimensao:
        faltantes = [
            coluna
            for coluna in colunas
            if coluna not in dimensoes[nome].columns
        ]

        if faltantes:
            raise ValueError(
                f"Colunas ausentes em {nome}.csv: {faltantes}"
            )

    # ATENÇÃO: a partir deste ponto o banco será recriado.
    banco.recriar_banco()
    conexao = banco.conectar()

    try:
        banco.executar_script(
            conexao,
            config.PASTA_SQL / "01_criar_banco.sql",
        )

        print("\nCarga das dimensões:")

        for nome, colunas in tabelas_dimensao:
            inserir(
                conexao,
                nome,
                colunas,
                dimensoes[nome],
            )

        colunas_fato = [
            "numero_controle_pncp",
            "numero_item",
            "sk_orgao",
            "sk_fornecedor",
            "sk_modalidade",
            "sk_localidade",
            "data_publicacao",
            "data_homologacao",
            "descricao_item",
            "perfil_gasto",
            "quantidade",
            "valor_unitario_estimado",
            "valor_total_estimado",
            "valor_unitario_homologado",
            "valor_total_homologado",
            "comparavel",
            "economia_valor",
            "dias_ciclo",
        ]

        print("\nCarga da tabela fato:")

        inserir(
            conexao,
            "fato_item_contratado",
            colunas_fato,
            fato,
        )

        print("\nConferência das tabelas:")

        esperados = [
            ("fato_item_contratado", 6126),
            ("dim_orgao", 363),
            ("dim_fornecedor", 2652),
            ("dim_modalidade", 7),
            ("dim_localidade", 27),
        ]

        for tabela, esperado in esperados:
            quantidade = banco.consultar(
                conexao,
                f"SELECT COUNT(*) FROM {tabela}",
            )[0][0]

            status = (
                "OK"
                if quantidade == esperado
                else "DIVERGENTE"
            )

            print(
                f"   {tabela}: {quantidade} "
                f"(esperado {esperado}) -> {status}"
            )

            if quantidade != esperado:
                raise RuntimeError(
                    f"Contagem divergente em {tabela}: "
                    f"{quantidade}; esperado {esperado}."
                )

        contagens = banco.consultar(
            conexao,
            """
            SELECT
                COUNT(*) FILTER (WHERE comparavel = 1),
                COUNT(*) FILTER (WHERE comparavel = 0),
                COUNT(*) FILTER (WHERE comparavel IS NULL)
            FROM fato_item_contratado
            """,
        )[0]

        print(
            "\nConferência de comparavel:"
            f"\n   1 (comparáveis): {contagens[0]}"
            f"\n   0 (não comparáveis): {contagens[1]}"
            f"\n   NULL: {contagens[2]}"
        )

        if contagens != (5457, 669, 0):
            raise RuntimeError(
                "A contagem de comparavel divergiu. "
                "Esperado: 5457, 669 e 0 nulos."
            )

        print("\nCarga e conferências concluídas com sucesso.")

    finally:
        conexao.close()


if __name__ == "__main__":
    main()
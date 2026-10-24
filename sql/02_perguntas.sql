/*
Projeto Compras Públicas — Projeto Avaliativo Módulo 2
Arquivo: sql/02_perguntas.sql

As seis perguntas de negócio foram executadas e validadas no pgAdmin.
A nomenclatura das colunas de saída corresponde à utilizada nos testes.

comparavel = 1: item comparável
comparavel = 0: item não comparável
A economia é calculada apenas com itens comparáveis.
*/

/* =========================================================
   PERGUNTA 1 — ECONOMIA GLOBAL DO PODER PÚBLICO
   ========================================================= */

SELECT
    COUNT(*) FILTER (
        WHERE comparavel = 1
    ) AS itens_comparaveis,

    SUM(valor_total_estimado) FILTER (
        WHERE comparavel = 1
    ) AS valor_estimado_comparavel,

    SUM(valor_total_homologado) FILTER (
        WHERE comparavel = 1
    ) AS valor_homologado_comparavel,

    SUM(valor_total_estimado) FILTER (
        WHERE comparavel = 1
    )
    -
    SUM(valor_total_homologado) FILTER (
        WHERE comparavel = 1
    ) AS economia_estimada,

    ROUND(
        100.0 * (
            SUM(valor_total_estimado) FILTER (
                WHERE comparavel = 1
            )
            -
            SUM(valor_total_homologado) FILTER (
                WHERE comparavel = 1
            )
        )
        / NULLIF(
            SUM(valor_total_estimado) FILTER (
                WHERE comparavel = 1
            ),
            0
        ),
        2
    ) AS economia_percentual,

    SUM(valor_total_homologado)
        AS valor_total_homologado_todos_os_itens

FROM public.fato_item_contratado;


/* =========================================================
   PERGUNTA 2 — CONCENTRAÇÃO E RISCO POR FORNECEDOR
   ========================================================= */

WITH total_geral AS (
    SELECT
        SUM(valor_total_homologado) AS valor_total_homologado
    FROM public.fato_item_contratado
),

volume_fornecedor AS (
    SELECT
        d.sk_fornecedor,
        d.ni_fornecedor,
        d.nome_fornecedor,
        SUM(f.valor_total_homologado) AS valor_total_homologado
    FROM public.fato_item_contratado AS f
    INNER JOIN public.dim_fornecedor AS d
        ON f.sk_fornecedor = d.sk_fornecedor
    GROUP BY
        d.sk_fornecedor,
        d.ni_fornecedor,
        d.nome_fornecedor
),

ranking AS (
    SELECT
        ROW_NUMBER() OVER (
            ORDER BY
                valor_total_homologado DESC,
                nome_fornecedor ASC
        ) AS posicao,
        ni_fornecedor,
        nome_fornecedor,
        valor_total_homologado
    FROM volume_fornecedor
)

SELECT
    r.posicao,
    r.ni_fornecedor,
    r.nome_fornecedor,
    r.valor_total_homologado,

    ROUND(
        100.0 * r.valor_total_homologado
        / NULLIF(t.valor_total_homologado, 0),
        2
    ) AS participacao_percentual,

    ROUND(
        100.0 * SUM(r.valor_total_homologado) OVER ()
        / NULLIF(t.valor_total_homologado, 0),
        2
    ) AS concentracao_top10_percentual

FROM ranking AS r
CROSS JOIN total_geral AS t
WHERE r.posicao <= 10
ORDER BY r.posicao;


/* =========================================================
   PERGUNTA 3 — EFICÁCIA POR MODALIDADE
   ========================================================= */

WITH total_geral AS (
    SELECT
        100.0 * (
            SUM(valor_total_estimado) FILTER (
                WHERE comparavel = 1
            )
            -
            SUM(valor_total_homologado) FILTER (
                WHERE comparavel = 1
            )
        )
        /
        NULLIF(
            SUM(valor_total_estimado) FILTER (
                WHERE comparavel = 1
            ),
            0
        ) AS economia_percentual_geral
    FROM public.fato_item_contratado
),

por_modalidade AS (
    SELECT
        d.nome_modalidade,
        COUNT(*) AS quantidade_itens,
        SUM(f.valor_total_homologado) AS valor_total_homologado,
        SUM(f.valor_total_estimado) FILTER (
            WHERE f.comparavel = 1
        ) AS valor_estimado_comparavel,
        SUM(f.valor_total_homologado) FILTER (
            WHERE f.comparavel = 1
        ) AS valor_homologado_comparavel
    FROM public.fato_item_contratado AS f
    INNER JOIN public.dim_modalidade AS d
        ON f.sk_modalidade = d.sk_modalidade
    GROUP BY d.nome_modalidade
),

indicadores AS (
    SELECT
        nome_modalidade,
        quantidade_itens,
        valor_total_homologado,

        100.0 * valor_total_homologado
        / NULLIF(
            SUM(valor_total_homologado) OVER (),
            0
        ) AS participacao_volume_percentual,

        100.0 * (
            valor_estimado_comparavel
            - valor_homologado_comparavel
        )
        / NULLIF(valor_estimado_comparavel, 0)
            AS economia_percentual
    FROM por_modalidade
)

SELECT
    i.nome_modalidade,
    i.quantidade_itens,
    i.valor_total_homologado,

    ROUND(
        i.participacao_volume_percentual,
        2
    ) AS participacao_volume_percentual,

    ROUND(
        i.economia_percentual,
        2
    ) AS economia_percentual,

    ROUND(
        i.economia_percentual
        - t.economia_percentual_geral,
        2
    ) AS desagio_vs_media_geral_pp

FROM indicadores AS i
CROSS JOIN total_geral AS t
ORDER BY i.valor_total_homologado DESC;


/* =========================================================
   PERGUNTA 4 — CICLO DE COMPRA POR ÓRGÃO
   Exibe órgãos com pelo menos cinco registros com ciclo calculado.
   ========================================================= */

SELECT
    d.nome_orgao,
    COUNT(f.dias_ciclo) AS quantidade_ciclos,
    ROUND(AVG(f.dias_ciclo), 1) AS media_dias_ciclo,
    MAX(f.dias_ciclo) AS maior_ciclo_dias
FROM public.fato_item_contratado AS f
INNER JOIN public.dim_orgao AS d
    ON f.sk_orgao = d.sk_orgao
WHERE f.dias_ciclo IS NOT NULL
GROUP BY d.nome_orgao
HAVING COUNT(f.dias_ciclo) >= 5
ORDER BY
    media_dias_ciclo DESC,
    d.nome_orgao;


/* =========================================================
   PERGUNTA 5A — DISTRIBUIÇÃO REGIONAL DAS COMPRAS PÚBLICAS
   ========================================================= */

SELECT
    d.regiao,
    COUNT(*) AS quantidade_itens,
    SUM(f.valor_total_homologado) AS valor_total_homologado,

    ROUND(
        100.0 * SUM(f.valor_total_homologado)
        / NULLIF(
            SUM(SUM(f.valor_total_homologado)) OVER (),
            0
        ),
        2
    ) AS participacao_volume_percentual,

    SUM(f.valor_total_estimado) FILTER (
        WHERE f.comparavel = 1
    ) AS valor_estimado_comparavel,

    SUM(f.valor_total_homologado) FILTER (
        WHERE f.comparavel = 1
    ) AS valor_homologado_comparavel,

    ROUND(
        100.0 * (
            SUM(f.valor_total_estimado) FILTER (
                WHERE f.comparavel = 1
            )
            -
            SUM(f.valor_total_homologado) FILTER (
                WHERE f.comparavel = 1
            )
        )
        / NULLIF(
            SUM(f.valor_total_estimado) FILTER (
                WHERE f.comparavel = 1
            ),
            0
        ),
        2
    ) AS economia_percentual

FROM public.fato_item_contratado AS f
INNER JOIN public.dim_localidade AS d
    ON f.sk_localidade = d.sk_localidade
GROUP BY d.regiao
ORDER BY valor_total_homologado DESC;


/* =========================================================
   PERGUNTA 5B — DISTRIBUIÇÃO DAS COMPRAS PÚBLICAS POR ESTADO
   ========================================================= */

SELECT
    d.uf_sigla,
    d.uf_nome,
    d.regiao,
    COUNT(*) AS quantidade_itens,
    SUM(f.valor_total_homologado) AS valor_total_homologado,

    ROUND(
        100.0 * SUM(f.valor_total_homologado)
        / NULLIF(
            SUM(SUM(f.valor_total_homologado)) OVER (),
            0
        ),
        2
    ) AS participacao_volume_percentual,

    SUM(f.valor_total_estimado) FILTER (
        WHERE f.comparavel = 1
    ) AS valor_estimado_comparavel,

    SUM(f.valor_total_homologado) FILTER (
        WHERE f.comparavel = 1
    ) AS valor_homologado_comparavel,

    ROUND(
        100.0 * (
            SUM(f.valor_total_estimado) FILTER (
                WHERE f.comparavel = 1
            )
            -
            SUM(f.valor_total_homologado) FILTER (
                WHERE f.comparavel = 1
            )
        )
        / NULLIF(
            SUM(f.valor_total_estimado) FILTER (
                WHERE f.comparavel = 1
            ),
            0
        ),
        2
    ) AS economia_percentual

FROM public.fato_item_contratado AS f
INNER JOIN public.dim_localidade AS d
    ON f.sk_localidade = d.sk_localidade
GROUP BY
    d.uf_sigla,
    d.uf_nome,
    d.regiao
ORDER BY valor_total_homologado DESC;


/* =========================================================
   PERGUNTA 6 — PERFIL DOS GASTOS
   ========================================================= */

SELECT
    perfil_gasto,
    COUNT(*) AS quantidade_itens,

    COUNT(*) FILTER (
        WHERE comparavel = 1
    ) AS itens_comparaveis,

    SUM(valor_total_homologado) AS valor_total_homologado,

    ROUND(
        100.0 * SUM(valor_total_homologado)
        / NULLIF(
            SUM(SUM(valor_total_homologado)) OVER (),
            0
        ),
        2
    ) AS participacao_volume_percentual,

    SUM(valor_total_estimado) FILTER (
        WHERE comparavel = 1
    ) AS valor_estimado_comparavel,

    SUM(valor_total_homologado) FILTER (
        WHERE comparavel = 1
    ) AS valor_homologado_comparavel,

    SUM(valor_total_estimado) FILTER (
        WHERE comparavel = 1
    )
    -
    SUM(valor_total_homologado) FILTER (
        WHERE comparavel = 1
    ) AS economia_valor,

    ROUND(
        100.0 * (
            SUM(valor_total_estimado) FILTER (
                WHERE comparavel = 1
            )
            -
            SUM(valor_total_homologado) FILTER (
                WHERE comparavel = 1
            )
        )
        / NULLIF(
            SUM(valor_total_estimado) FILTER (
                WHERE comparavel = 1
            ),
            0
        ),
        2
    ) AS economia_percentual,

    ROUND(
        SUM(valor_total_homologado)
        / NULLIF(COUNT(*), 0),
        2
    ) AS ticket_medio

FROM public.fato_item_contratado
GROUP BY perfil_gasto
ORDER BY valor_total_homologado DESC;

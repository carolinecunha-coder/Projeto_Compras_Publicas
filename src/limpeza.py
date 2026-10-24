
import re
import unicodedata
from datetime import datetime, date
from decimal import Decimal, InvalidOperation


# ============================================================
# 1. LIMPEZA DE TEXTO
# ============================================================

def limpar_texto(valor):
    """Remove caracteres invisíveis e normaliza espaços."""

    if valor is None:
        return None

    texto = str(valor)

    texto = texto.replace("\ufeff", "")
    texto = texto.replace("\u200b", "")
    texto = texto.replace("\xa0", " ")

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Cc"
        or caractere in "\n\t"
    )

    texto = re.sub(r"\s+", " ", texto).strip()

    if texto == "":
        return None

    return texto


# ============================================================
# 2. CORREÇÃO DE ACENTOS
# ============================================================

def consertar_acento(valor):
    """Tenta corrigir textos com problemas de codificação."""

    texto = limpar_texto(valor)

    if texto is None:
        return None

    try:
        corrigido = texto.encode("latin1").decode("utf-8")

        if corrigido and corrigido != texto:
            return corrigido

    except (UnicodeEncodeError, UnicodeDecodeError):
        pass

    return texto


# ============================================================
# 3. TRATAMENTO DE VALORES NULOS
# ============================================================

NULOS = {
    "",
    "NULL",
    "NULO",
    "NULOS",
    "NONE",
    "NAN",
    "N/A",
    "NA",
    "N.A.",
    "NÃO INFORMADO",
    "NAO INFORMADO",
    "NÃO SE APLICA",
    "NAO SE APLICA",
    "-"
}


def limpar_nulo(valor):
    """Converte representações textuais de nulo para None."""

    if valor is None:
        return None

    texto = limpar_texto(valor)

    if texto is None:
        return None

    if texto.upper() in NULOS:
        return None

    return texto


# ============================================================
# 4. LIMPEZA DE DOCUMENTOS
# ============================================================

def limpar_documento(valor, tipo=None):
    """
    Limpa documentos e valida o formato.

    tipo:
        PF = Pessoa Física (CPF)
        PJ = Pessoa Jurídica (CNPJ)
        PE = Documento estrangeiro ou especial
    """

    documento = limpar_nulo(valor)

    if documento is None:
        return None

    documento = re.sub(r"[^A-Za-z0-9]", "", documento)
    documento = documento.upper()

    if documento == "":
        return None

    if tipo == "PF":
        if not documento.isdigit() or len(documento) > 11:
            return None

        # Recupera zeros à esquerda perdidos na leitura/exportação.
        return documento.zfill(11)

    if tipo == "PJ":
        if not documento.isdigit() or len(documento) > 14:
            return None

        # Recupera zeros à esquerda perdidos na leitura/exportação.
        return documento.zfill(14)

    if tipo == "PE":
        return documento

    return documento


# ============================================================
# 5. CONVERSÃO DE NÚMEROS
# ============================================================

def converter_numero(valor):
    """Converte números brasileiros e internacionais para Decimal.

    Na base PNCP, um separador sozinho é decimal; separadores repetidos
    em grupos de três dígitos são milhares; com ponto e vírgula juntos,
    o último separador é o decimal.
    """

    texto = limpar_nulo(valor)
    if texto is None:
        return None

    texto = str(texto).strip()
    texto = texto.replace("R$", "").replace("$", "").replace(" ", "")

    negativo = texto.startswith("(") and texto.endswith(")")
    if negativo:
        texto = texto[1:-1]

    if "." in texto and "," in texto:
        pos_decimal = max(texto.rfind("."), texto.rfind(","))
        parte_inteira = re.sub(r"[.,]", "", texto[:pos_decimal])
        parte_decimal = re.sub(r"[.,]", "", texto[pos_decimal + 1:])
        texto = parte_inteira + "." + parte_decimal

    elif "." in texto or "," in texto:
        separador = "." if "." in texto else ","
        partes = texto.split(separador)

        if len(partes) > 2 and all(len(parte) == 3 for parte in partes[1:]):
            texto = "".join(partes)
        elif len(partes) > 2:
            texto = "".join(partes[:-1]) + "." + partes[-1]
        else:
            texto = texto.replace(separador, ".")

    try:
        numero = Decimal(texto)
        return -numero if negativo else numero
    except InvalidOperation:
        return None


# ============================================================
# 6. CONVERSÃO DE DATAS
# ============================================================

def converter_data(valor):
    """Converte datas para o formato datetime."""

    texto = limpar_nulo(valor)

    if texto is None:
        return None

    if isinstance(valor, datetime):
        return valor

    if isinstance(valor, date):
        return datetime.combine(valor, datetime.min.time())

    texto = str(texto).strip()

    formatos = [
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y%m%d",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato)

        except ValueError:
            continue

    try:
        return datetime.fromisoformat(texto)

    except ValueError:
        return None


# ============================================================
# 7. TESTES AUTOMÁTICOS
# ============================================================

CASOS = [
    ("limpar_texto", ("  Dados   públicos  ",), "Dados públicos"),
    ("limpar_texto", ("",), None),
    ("limpar_texto", (None,), None),

    ("limpar_nulo", ("NULL",), None),
    ("limpar_nulo", ("NÃO INFORMADO",), None),
    ("limpar_nulo", ("123",), "123"),

    ("limpar_documento", ("123.456.789-00", "PF"), "12345678900"),
    ("limpar_documento", ("12.345.678/0001-99", "PJ"), "12345678000199"),
    ("limpar_documento", ("ABC123", "PE"), "ABC123"),
    ("limpar_documento", ("123456789012345", "PJ"), None),

    ("converter_numero", ("1.234,56",), Decimal("1234.56")),
    ("converter_numero", ("R$ 250,00",), Decimal("250.00")),
    ("converter_numero", ("(150,50)",), Decimal("-150.50")),
    ("converter_numero", ("valor inválido",), None),

    (
        "converter_data",
        ("10/03/2025",),
        datetime(2025, 3, 10),
    ),
    (
        "converter_data",
        ("2025-03-10",),
        datetime(2025, 3, 10),
    ),
    ("converter_data", ("data inválida",), None),
]


def testar():
    """Executa todos os casos de teste."""

    erros = 0

    print("\n" + "=" * 50)
    print("TESTES DO MÓDULO DE LIMPEZA")
    print("=" * 50)

    for nome_funcao, argumentos, esperado in CASOS:

        funcao = globals()[nome_funcao]
        resultado = funcao(*argumentos)

        if resultado == esperado:
            print("[OK] " + nome_funcao)

        else:
            erros += 1

            print("[ERRO] " + nome_funcao)
            print("  Esperado: " + str(esperado))
            print("  Obtido:   " + str(resultado))

    print("\n" + "=" * 50)
    print("Total de testes: " + str(len(CASOS)))
    print("Erros encontrados: " + str(erros))

    if erros == 0:
        print("TODOS OS TESTES PASSARAM!")

    else:
        print("Existem testes que precisam de correção.")

    print("=" * 50)


# ============================================================
# 8. EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    testar()

"""Acesso ao Oracle ADB e ao Select AI (showsql -> executa -> chat).

Usa 'chat' em vez de 'narrate' no passo final: 'narrate' re-executa sua
propria consulta e pode estourar o limite de tokens do modelo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import oracledb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


class ConfiguracaoAusente(RuntimeError):
    """Levantado quando uma variavel de ambiente obrigatoria nao foi definida."""


def _env(nome: str, obrigatorio: bool = True, default: str | None = None) -> str:
    valor = os.getenv(nome, default)
    if obrigatorio and not valor:
        raise ConfiguracaoAusente(
            f"Variavel de ambiente '{nome}' nao definida. Copie .env.example para "
            f".env e preencha os valores antes de usar a pagina Pergunte aos Dados."
        )
    return valor or ""


def get_connection() -> oracledb.Connection:
    """Abre uma conexao com o Oracle ADB usando a wallet do projeto."""
    wallet_dir = _env("ORACLE_WALLET_DIR", default="./wallet")

    return oracledb.connect(
        user=_env("ORACLE_USER"),
        password=_env("ORACLE_PASSWORD"),
        dsn=_env("ORACLE_DSN"),
        config_dir=wallet_dir,
        wallet_location=wallet_dir,
        wallet_password=_env("ORACLE_WALLET_PASSWORD", obrigatorio=False),
    )


def chat_simples(prompt: str, profile: str) -> str:
    """Chama Select AI action='chat' direto, sem SQL -- usado no roteamento por IA."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            return _select_ai_generate(cursor, prompt, profile, "chat").strip()


def _select_ai_generate(cursor: oracledb.Cursor, prompt: str, profile: str, action: str) -> str:
    """Chama DBMS_CLOUD_AI.GENERATE e devolve o resultado como texto."""
    resultado = cursor.var(oracledb.DB_TYPE_CLOB)
    cursor.execute(
        """
        BEGIN
            :resultado := DBMS_CLOUD_AI.GENERATE(
                prompt        => :prompt,
                profile_name  => :profile,
                action        => :action
            );
        END;
        """,
        resultado=resultado,
        prompt=prompt,
        profile=profile,
        action=action,
    )
    valor = resultado.getvalue()
    return valor.read() if hasattr(valor, "read") else str(valor)


def _extrair_sql(sql_bruto: str) -> tuple[str | None, str | None]:
    """Extrai o SQL do retorno do showsql, ou (None, motivo) se a geracao falhou."""
    texto = sql_bruto.strip()
    if "```" in texto:
        linhas = [l for l in texto.splitlines() if not l.strip().startswith("```")]
        texto = "\n".join(linhas).strip()

    if not texto:
        return None, "O Select AI nao retornou nenhum SQL."

    inicio = texto.lstrip().lower()
    if not (inicio.startswith("select") or inicio.startswith("with")):
        return None, texto  # nao e SQL puro, nao arriscar executar

    return texto.rstrip(";"), None


_LIMITE_LINHAS_TABELA = 500
_LIMITE_LINHAS_PROMPT = 15


def _resumir_tabela_para_prompt(tabela: pd.DataFrame, truncada: bool) -> str:
    """Amostra pequena da tabela pro prompt do Cohere (nunca a tabela inteira)."""
    if tabela.empty:
        return "(a consulta nao retornou nenhuma linha)"

    amostra = tabela.head(_LIMITE_LINHAS_PROMPT).to_csv(index=False)
    total = len(tabela)
    if truncada:
        return f"{amostra}\n(mostrando as primeiras {min(total, _LIMITE_LINHAS_PROMPT)} linhas; ha mais linhas alem dessa amostra)"
    if total > _LIMITE_LINHAS_PROMPT:
        return f"{amostra}\n(mostrando {_LIMITE_LINHAS_PROMPT} de {total} linhas no total)"
    return amostra


@dataclass
class RespostaSelectAI:
    pergunta: str
    sql_gerado: str
    tabela: pd.DataFrame
    explicacao: str
    erro: str | None = None


_MAX_TENTATIVAS_SQL = 2


def perguntar(
    pergunta: str, profile: str, contexto: str | None = None, dicas_sql: str | None = None
) -> RespostaSelectAI:
    """Executa o fluxo completo: showsql -> executa SQL -> chat (explicacao).

    Retenta ate _MAX_TENTATIVAS_SQL vezes se o showsql nao gerar SQL valido.

    `contexto` (persona/recomendacao) so entra na explicacao final -- misturar
    com a pergunta confunde a geracao de SQL. `dicas_sql` (regras tecnicas de
    schema/dialeto, ex. "nao use SYSDATE/SDO_GEOM/PI()") entra JUNTO com a
    pergunta no showsql, pois e la que esses erros acontecem.
    """
    texto_para_sql = f"{pergunta}\n\n{dicas_sql}" if dicas_sql else pergunta
    sql_gerado = ""
    try:
        with get_connection() as conn:
            motivo_falha = None
            for _ in range(_MAX_TENTATIVAS_SQL):
                with conn.cursor() as cursor:
                    bruto = _select_ai_generate(cursor, texto_para_sql, profile, "showsql")
                sql_gerado, motivo_falha = _extrair_sql(bruto)
                if sql_gerado:
                    break

            if not sql_gerado:
                return RespostaSelectAI(
                    pergunta=pergunta,
                    sql_gerado="",
                    tabela=pd.DataFrame(),
                    explicacao="",
                    erro=(
                        "O Select AI nao conseguiu gerar uma consulta valida para essa "
                        "pergunta. Tente reformular de forma mais direta, citando "
                        f"hospitais, municipios ou periodo.\n\nDetalhe tecnico: {(motivo_falha or '')[:400]}"
                    ),
                )

            with conn.cursor() as cursor:
                cursor.execute(sql_gerado)
                colunas = [c[0] for c in cursor.description]
                linhas = cursor.fetchmany(_LIMITE_LINHAS_TABELA)
                truncada = len(linhas) == _LIMITE_LINHAS_TABELA and cursor.fetchone() is not None
                tabela = pd.DataFrame(linhas, columns=colunas)

            resumo = _resumir_tabela_para_prompt(tabela, truncada)
            contexto_texto = f"{contexto}\n\n" if contexto else ""
            prompt_explicacao = (
                f"{contexto_texto}"
                f"Pergunta original do gestor: {pergunta}\n\n"
                f"Este e o resultado real de uma consulta ja executada no banco "
                f"(colunas: {', '.join(colunas)}):\n{resumo}\n\n"
                "Com base nesses dados (e em qualquer orientacao/contexto adicional que "
                "acompanhe a pergunta original), escreva uma resposta curta e direta em "
                "portugues para o gestor. Nao invente numeros que nao estejam nos dados "
                "acima -- mas pode usar o contexto fornecido para orientar a recomendacao."
            )
            with conn.cursor() as cursor:
                explicacao = _select_ai_generate(cursor, prompt_explicacao, profile, "chat")

        return RespostaSelectAI(
            pergunta=pergunta, sql_gerado=sql_gerado, tabela=tabela, explicacao=explicacao.strip()
        )
    except ConfiguracaoAusente as e:
        return RespostaSelectAI(pergunta=pergunta, sql_gerado="", tabela=pd.DataFrame(), explicacao="", erro=str(e))
    except oracledb.Error as e:
        mensagem = str(e)
        if "TOO_MANY_TOKENS" in mensagem or "ORA-20400" in mensagem:
            erro = (
                "Essa pergunta levou o modelo a gerar uma consulta grande demais para "
                "processar. Tente ser mais especifico: peca um top N, um periodo mais "
                "curto, ou cite um hospital/municipio."
            )
        else:
            erro = f"Erro ao consultar o Oracle/Select AI: {e}"
        return RespostaSelectAI(pergunta=pergunta, sql_gerado=sql_gerado, tabela=pd.DataFrame(), explicacao="", erro=erro)

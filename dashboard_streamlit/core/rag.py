"""Base de conhecimento (RAG) dos agentes do Chat MedData -- indexada em Chroma."""

from __future__ import annotations

import streamlit as st
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# conhecimento geral: peculiaridades tecnicas do banco
_TECNICO = [
    "Os dados de internacao (FATO_INTERNACAO_V2) tem registros ate novembro "
    "de 2024. Ao interpretar palavras como 'recente', 'ultimos meses' ou "
    "'atualmente', use novembro de 2024 como referencia de 'hoje' -- NAO use "
    "SYSDATE (a data real do sistema), pois isso faz a consulta nao encontrar "
    "nenhum registro e retornar vazio.",
    "As colunas de latitude e longitude (em DIM_HOSPITAL_V2, DIM_MUNICIPIO_V2 "
    "e FATO_INTERNACAO_V2) sao numeros decimais simples (NUMBER). NAO existe "
    "tipo de dado espacial (SDO_GEOMETRY) nem indice espacial cadastrado neste "
    "banco -- funcoes como SDO_GEOM.SDO_DISTANCE vao falhar, pois exigem "
    "metadados espaciais que nao existem aqui. Para calcular distancia real "
    "em quilometros entre duas coordenadas, use EXATAMENTE esta formula (lei "
    "dos cossenos esferica, equivalente a Haversine, com RADIANS() -- "
    "SEM converter para radianos manualmente e SEM usar diferenca de graus "
    "ao quadrado, que NAO e uma distancia real em km):\n"
    "    6371 * ACOS(\n"
    "        COS(RADIANS(lat1)) * COS(RADIANS(lat2)) * COS(RADIANS(lon2) - RADIANS(lon1))\n"
    "        + SIN(RADIANS(lat1)) * SIN(RADIANS(lat2))\n"
    "    )\n"
    "Troque lat1/lon1 pelas coordenadas do primeiro ponto e lat2/lon2 pelas "
    "do segundo -- o resultado ja vem em quilometros (6371 e o raio da Terra "
    "em km). NUNCA use a diferenca de latitude/longitude ao quadrado (ex.: "
    "(lat1-lat2)*(lat1-lat2) + (lon1-lon2)*(lon1-lon2)) como se fosse "
    "distancia -- isso mede graus ao quadrado, nao quilometros, e gera "
    "numeros pequenos e sem sentido para distancias reais grandes. IMPORTANTE: "
    "o Oracle SQL NAO TEM funcao PI() (isso existe em outros bancos, como "
    "PostgreSQL/MySQL/SQL Server, mas nao no Oracle) -- usar PI() aqui "
    "sempre falha com o erro 'ORA-00904: PI: invalid identifier' e faz a "
    "consulta inteira ser rejeitada. Use SEMPRE a funcao RADIANS() (nativa "
    "do Oracle, ja pronta) para converter graus em radianos -- NUNCA tente "
    "multiplicar por PI()/180 ou qualquer variacao com PI() manualmente.",
    "Ao buscar o 'hospital mais proximo com vaga' a partir de um paciente ou "
    "hospital de origem, NAO restrinja os hospitais candidatos ao mesmo "
    "municipio de origem -- busque entre TODOS os hospitais com "
    "leitos_disponiveis > 0 (VW_OCUPACAO_DIARIA) de qualquer municipio, "
    "ordenando pela distancia real calculada (formula acima) e pegando o "
    "menor valor. Restringir ao mesmo municipio da origem e um erro comum: "
    "o hospital mais proximo com vaga costuma estar em OUTRO municipio, "
    "exatamente quando o municipio de origem esta sem vagas.",
    "Os codigos de hospital (id_hospital) e de municipio (codigo_municipio) "
    "sao armazenados como texto (VARCHAR2), com zeros a esquerda (ex.: "
    "'0008028'). Ao comparar ou filtrar por esses codigos, trate-os como "
    "texto, nao como numero.",
    "Nomes de municipio (nome_municipio, nome_municipio_paciente, "
    "nome_municipio_hospital) tem acentuacao correta no banco (ex.: 'Sao "
    "Paulo' com o til, 'Ribeirao Preto' com o til, 'Jundiai' com acento). "
    "Uma comparacao exata (=) com o nome escrito sem acento NAO encontra "
    "nada e retorna vazio silenciosamente, sem erro. Para filtrar por nome "
    "de municipio, SEMPRE compare usando NLSSORT com sort insensivel a "
    "acento e maiusculas/minusculas, assim: WHERE NLSSORT(coluna, "
    "'NLS_SORT=BINARY_AI') = NLSSORT('valor pesquisado', "
    "'NLS_SORT=BINARY_AI') -- funciona independente de acento ou "
    "maiusculas/minusculas dos dois lados, e e mais confiavel que tentar "
    "reescrever o texto sem acento manualmente.",
    "Para perguntas sobre ocupacao, leitos disponiveis ou leitos ocupados, "
    "SEMPRE use diretamente as colunas ja calculadas leitos_totais, "
    "leitos_ocupados, leitos_disponiveis e taxa_ocupacao da "
    "VW_OCUPACAO_DIARIA (agrupando/somando por municipio ou hospital "
    "conforme a pergunta). NUNCA recalcule 'leitos ocupados' somando "
    "dias_internacao direto de FATO_INTERNACAO_V2 (isso soma internacoes "
    "de anos inteiros, nao os ultimos 30 dias, e gera numeros sem "
    "sentido) nem busque leitos_totais em DIM_HOSPITAL_V2 (tem o bug de "
    "geracao ja mencionado) -- a VW_OCUPACAO_DIARIA ja resolve os dois "
    "problemas.",
]

# guia das views pre-construidas, por agente
_VIEWS_CAPACIDADE = [
    "VW_OCUPACAO_DIARIA traz, por hospital, a ocupacao real da media movel "
    "dos ultimos 30 dias de dados disponiveis: leitos_ocupados, "
    "leitos_disponiveis (pode ser negativo, indicando sobrecarga) e "
    "taxa_ocupacao (%). E a fonte mais confiavel para responder 'quem esta "
    "lotado agora'.",
    "VW_ALERTAS_COLAPSO usa a taxa_ocupacao da VW_OCUPACAO_DIARIA e classifica "
    "cada hospital por posicao relativa (percentil) entre todos os hospitais: "
    "Vermelho (top 10%), Laranja (proximos 15%), Amarelo (proximos 25%), Verde "
    "(restante). E uma classificacao relativa, nao um limite fixo absoluto.",
    "VW_ROTATIVIDADE_LEITOS NAO e taxa de ocupacao -- mede quantas internacoes "
    "aconteceram por leito, em cada mes (giro de leito). Pode legitimamente "
    "passar de 100% num hospital com muitos pacientes de curta permanencia. "
    "Nao confundir com a taxa_ocupacao da VW_OCUPACAO_DIARIA.",
    "VW_PERMANENCIA_MEDIA traz o tempo medio de internacao (dias) por "
    "hospital, considerando os ultimos 12 meses de dados e so hospitais com "
    "pelo menos 5 internacoes no periodo. NAO use esta view para ranking de "
    "hospitais por TOTAL de internacoes (ex.: 'quais hospitais tem mais "
    "internacoes') -- o total ali tambem esta limitado aos ultimos 12 meses "
    "e exclui hospitais pequenos, dando um numero menor que o real. Para "
    "ranking geral de internacoes por hospital sem filtro de tempo, conte "
    "direto em FATO_INTERNACAO_V2 agrupado por id_hospital.",
    "VW_OCUPACAO_REGIONAL agrega por MUNICIPIO DO HOSPITAL (nao do paciente) "
    "os ultimos 12 meses de dados: soma de leitos e de internacoes, com uma "
    "taxa_ocupacao_media que e internacoes/leitos do periodo (nao um "
    "percentual instantaneo 0-100% como na VW_OCUPACAO_DIARIA). NAO use esta "
    "view para responder 'qual o total geral de internacoes' -- o resultado "
    "sai bem menor que o real, pois cobre so 12 meses. Para total geral "
    "historico, use FATO_INTERNACAO_V2 (COUNT) ou VW_MUNICIPIO_INTERNACOES "
    "(SUM), que nao tem esse filtro de tempo.",
]

_VIEWS_PREDICAO = [
    "VW_CRESCIMENTO_MUNICIPIO compara o total de internacoes de um municipio "
    "entre o periodo atual (ultimos 12 meses de dados) e o periodo anterior "
    "(12 meses antes disso), calculando a variacao percentual. So inclui "
    "municipios com pelo menos 5 internacoes em algum dos dois periodos -- e "
    "a fonte certa para responder perguntas de tendencia/crescimento por "
    "municipio.",
    "VW_MUNICIPIO_INTERNACOES traz o total de internacoes por municipio, "
    "separado por ano (todos os anos disponiveis, nao so os ultimos 12 "
    "meses) -- util para ver a serie historica completa de um municipio.",
    "VW_DIAGNOSTICO_SIMPLES traz o total de internacoes por diagnostico e "
    "ano (todos os anos disponiveis) -- util para ver como um diagnostico "
    "especifico evoluiu ao longo do tempo.",
]

_VIEWS_OTIMIZACAO = [
    "VW_PRESSAO_ASSISTENCIAL agrega por municipio (nao por hospital) os "
    "ultimos 12 meses de dados: soma de leitos, total de internacoes, e um "
    "'indicador_pressao' que combina taxa de internacoes/leito com volume de "
    "pacientes viajantes. O campo chamado taxa_ocupacao aqui NAO e ocupacao "
    "instantanea -- e o total de internacoes do ano dividido pelos leitos, "
    "um numero de volume anual, nao um percentual de 0-100% como na "
    "VW_OCUPACAO_DIARIA.",
    "VW_PACIENTES_VIAJANTES lista, para os ultimos 12 meses, pacientes que "
    "viajaram para internar (paciente_viajou = 'True'), por hospital e "
    "municipio de origem, com a distancia estimada -- boa fonte para "
    "perguntas sobre falta de capacidade local/fluxo entre regioes.",
    "VW_INTERNACOES_POR_DIAGNOSTICO traz, para os ultimos 12 meses, total de "
    "internacoes, media de dias de internacao e custo total por diagnostico "
    "-- util para comparar diagnosticos por custo ou tempo de tratamento.",
]

# conhecimento geral: limitacoes de qualidade de dado
_QUALIDADE_DADO = [
    "Cerca de 2% das internacoes tem diagnostico_id = 0, um valor sentinela "
    "usado quando o codigo de diagnostico informado e mais generico do que o "
    "nivel de detalhe da dimensao de diagnosticos (ex.: informado so ate a "
    "categoria, sem o digito de subcategoria). Nao trate isso como um "
    "diagnostico valido.",
    "A coluna leitos_totais em DIM_HOSPITAL_V2 tinha um problema de geracao "
    "(valores ~12-16x maiores que o real) que ja foi corrigido diretamente na "
    "tabela para 1.404 dos 1.466 hospitais (casados pelo codigo CNES com "
    "DIM_HOSPITAL, a versao anterior dos dados). Pode usar leitos_totais de "
    "DIM_HOSPITAL_V2 normalmente agora -- so os ~62 hospitais sem "
    "correspondencia em DIM_HOSPITAL podem ainda ter um valor impreciso.",
    "Para 'taxa de ocupacao media da rede' (visao agregada de varios "
    "hospitais, nao de um hospital so), calcule como SOMA(leitos_ocupados) / "
    "SOMA(leitos_totais) * 100 usando a VW_OCUPACAO_DIARIA -- uma media "
    "ponderada pelo tamanho de cada hospital. NAO calcule como AVG(taxa_"
    "ocupacao) simples entre os hospitais: isso da peso igual a hospitais "
    "grandes e pequenos e produz um numero bem diferente (e inconsistente "
    "com o resto do dashboard, que sempre usa a versao ponderada).",
    "As datas de internacao (data_internacao) cobrem de 2008 a 2024, mas "
    "cerca de 98% do volume real de internacoes esta concentrado nos ultimos "
    "12 meses de dados. Registros muito antigos, especialmente sem "
    "data_saida preenchida, podem ser dado incompleto/backlog, nao "
    "internacoes realmente em andamento.",
    "A coluna nome_hospital em DIM_HOSPITAL_V2 NAO e um nome real de "
    "hospital -- e sempre o texto 'Hospital CNES ' seguido do codigo. Ao "
    "identificar um hospital numa resposta, mencione o codigo CNES.",
    "A coluna alta_complexidade em DIM_HOSPITAL tem o mesmo valor "
    "('Baixa/Media Complexidade') para TODOS os hospitais da base -- nao "
    "existe nenhum hospital marcado como alta complexidade nestes dados. "
    "NAO use essa coluna como criterio de filtro (sempre retorna vazio). "
    "Para diferenciar estrutura/porte de um hospital, use porte_hospitalar "
    "(valores reais: Grande Porte, Medio Porte, Pequeno Porte, Micro Porte).",
]

# conhecimento do agente Otimizacao: governanca de regulacao de leitos
_GOVERNANCA_REGULACAO = [
    "No SUS, o encaminhamento de pacientes entre hospitais normalmente e "
    "coordenado por uma Central de Regulacao (ou Complexo Regulador), que "
    "decide a vaga disponivel considerando nao so a proximidade geografica, "
    "mas tambem a estrutura/porte do hospital e a disponibilidade real de "
    "um leito compativel.",
    "IMPORTANTE: a coluna alta_complexidade em DIM_HOSPITAL tem o mesmo "
    "valor ('Baixa/Media Complexidade') para TODOS os hospitais da base -- "
    "nao existe nenhum hospital marcado como alta complexidade nestes dados, "
    "entao essa coluna NAO deve ser usada como criterio de filtro (filtrar "
    "por ela sempre retorna vazio). Para diferenciar a estrutura/porte de "
    "um hospital, use porte_hospitalar (valores reais: Grande Porte, Medio "
    "Porte, Pequeno Porte, Micro Porte).",
    "Na pratica, ao recomendar um hospital para onde encaminhar um paciente, "
    "priorize: (1) disponibilidade de leito (leitos_disponiveis > 0 na "
    "VW_OCUPACAO_DIARIA), (2) porte_hospitalar compativel (hospitais de "
    "Grande/Medio Porte tendem a ter mais estrutura), e (3) menor distancia. "
    "Nao filtre por alta_complexidade.",
]

# conhecimento geral: uso responsavel de IA em saude
_USO_RESPONSAVEL = [
    "Este sistema e uma ferramenta de apoio analitico baseada em dados "
    "historicos agregados -- as respostas geradas devem ser tratadas como "
    "sugestoes informadas por dados, nunca como uma decisao clinica ou "
    "administrativa definitiva.",
    "Qualquer recomendacao gerada aqui (ex.: transferencia de paciente, "
    "prioridade de leito) deve ser validada por um profissional responsavel "
    "antes de qualquer acao real -- o sistema nao substitui avaliacao "
    "clinica.",
    "O sistema nao tem acesso a informacoes clinicas individuais de "
    "pacientes especificos (diagnostico do caso concreto, gravidade, "
    "condicao atual) -- so trabalha com dados agregados e historicos.",
]

CONHECIMENTO_GERAL: list[str] = _TECNICO + _QUALIDADE_DADO + _USO_RESPONSAVEL

CONHECIMENTO_POR_AGENTE: dict[str, list[str]] = {
    "capacidade": [
        "Ocupacao de leitos e o percentual de leitos efetivamente ocupados em "
        "relacao ao total disponivel. Acima de 85-90% costuma ser considerado "
        "critico, pois nao sobra margem para picos inesperados de demanda.",
        "Ocupacao sustentada acima de 90% por varios dias seguidos, combinada "
        "com alta proporcao de pacientes vindos de outros municipios, indica "
        "que a rede local ja nao consegue absorver a demanda da regiao.",
        "Diante de ocupacao critica, as acoes recomendadas sao: redistribuir "
        "pacientes nao urgentes para hospitais da mesma regiao com folga de "
        "leitos, acionar leitos de contingencia, e priorizar altas de "
        "pacientes ja estaveis para liberar capacidade.",
        "Leitos disponiveis e simplesmente leitos totais menos leitos "
        "ocupados. Um valor negativo (ou proximo de zero) indica que o "
        "hospital esta operando acima ou no limite da sua capacidade oficial.",
        *_VIEWS_CAPACIDADE,
    ],
    "predicao": [
        "Para avaliar se um crescimento de internacoes e uma tendencia real "
        "(e nao uma flutuacao pontual), compare a taxa de crescimento mes a "
        "mes: um aumento sustentado por 2-3 meses seguidos e um sinal mais "
        "confiavel do que um unico pico isolado.",
        "Internacoes costumam ter padroes sazonais (por exemplo, doencas "
        "respiratorias aumentam no inverno). Sempre que possivel, compare um "
        "periodo com o mesmo periodo do ano anterior, nao so com o mes "
        "imediatamente anterior.",
        "Diante de uma tendencia de crescimento sustentado, a recomendacao e "
        "antecipar reforco de leitos e equipe antes que a ocupacao chegue ao "
        "nivel critico -- agir de forma preventiva, nao reativa.",
        *_VIEWS_PREDICAO,
    ],
    "otimizacao": [
        "Comparar hospitais ou municipios so pelo volume de internacoes pode "
        "enganar. Vale considerar tambem o tempo medio de internacao e a "
        "distancia percorrida pelo paciente: muitos pacientes vindo de longe "
        "costuma indicar falta de capacidade local mais proxima.",
        "Reduzir o tempo medio de internacao (sem comprometer a qualidade do "
        "atendimento) libera leitos mais rapido e aumenta a capacidade "
        "efetiva da rede sem precisar de investimento em infraestrutura nova.",
        "Redistribuir a demanda entre os hospitais de uma mesma regiao, em "
        "vez de concentrar tudo em poucos hospitais de grande porte, tende a "
        "reduzir o tempo de espera e o custo total para a rede.",
        *_VIEWS_OTIMIZACAO,
        *_GOVERNANCA_REGULACAO,
    ],
}

_NOME_MODELO_EMBEDDING = "sentence-transformers/all-MiniLM-L6-v2"
_TAG_GERAL = "geral"


@st.cache_resource(
    show_spinner=(
        "Carregando modelo de IA local (so na primeira pergunta apos abrir o app -- "
        "pode levar ate 2 minutos nesta maquina; as proximas perguntas sao rapidas)..."
    )
)
def _obter_vectorstore() -> Chroma:
    """Constroi (uma vez por processo, via cache_resource) o indice vetorial Chroma.

    Primeira chamada demora ~2min (import de torch/sentence-transformers,
    nao e download); chamadas seguintes reusam o indice em cache.
    """
    embeddings = HuggingFaceEmbeddings(model_name=_NOME_MODELO_EMBEDDING)

    textos, metadados = [], []
    for trecho in CONHECIMENTO_GERAL:
        textos.append(trecho)
        metadados.append({"agente": _TAG_GERAL})
    for agente_key, trechos in CONHECIMENTO_POR_AGENTE.items():
        for trecho in trechos:
            textos.append(trecho)
            metadados.append({"agente": agente_key})

    return Chroma.from_texts(
        textos, embedding=embeddings, metadatas=metadados, collection_name="meddata_conhecimento"
    )


def buscar_conhecimento(agente_key: str, pergunta: str, k: int = 3) -> list[str]:
    """Retorna os k trechos mais relevantes (conhecimento do agente + geral)."""
    vectorstore = _obter_vectorstore()
    resultados = vectorstore.similarity_search(
        pergunta, k=k, filter={"$or": [{"agente": agente_key}, {"agente": _TAG_GERAL}]}
    )
    return [doc.page_content for doc in resultados]

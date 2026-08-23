-- ============================================================
-- SCRIPT DE CRIAÇÃO DAS TABELAS - MEDDATA
-- Projeto: MedData - Challenge Oracle 2026
-- ============================================================
-- ============================================================
-- SCRIPT DDL - MEDDATA STAR SCHEMA
-- ============================================================
--
-- MUDANCAS REALIZADAS:
-- 1. Removida coluna LEITOS_CONTRATADOS (100% zerado)
-- 2. Removida coluna ESFERA_CLASSIFICACAO (todos "Nao informado")
-- 3. Adicionadas colunas UF_HOSPITAL e ESTADO_HOSPITAL
-- 4. Adicionadas colunas UF_PACIENTE e ESTADO_PACIENTE
-- 5. Latitude/longitude no formato NUMBER(13,6)
-- ============================================================

-- DROP DAS TABELAS (caso existam)
-- DROP TABLE FATO_INTERNACAO CASCADE CONSTRAINT;
-- DROP TABLE DIM_HOSPITAL CASCADE CONSTRAINT;
-- DROP TABLE DIM_MUNICIPIO CASCADE CONSTRAINT;
-- DROP TABLE DIM_TEMPO CASCADE CONSTRAINT;


-- ============================================================
-- 1. DIM_MUNICIPIO (Dimensao Municipios)
-- ============================================================

CREATE TABLE DIM_MUNICIPIO (
    codigo_municipio NUMBER(6) NOT NULL,
    nome_municipio VARCHAR2(100) NOT NULL,
    uf VARCHAR2(2) NOT NULL,
    estado VARCHAR2(50) NOT NULL,
    latitude NUMBER(13,6),
    longitude NUMBER(13,6)
);

COMMENT ON TABLE DIM_MUNICIPIO IS 'Dimensao com dados dos municipios.';
COMMENT ON COLUMN DIM_MUNICIPIO.codigo_municipio IS 'Codigo IBGE do municipio (6 digitos).';
COMMENT ON COLUMN DIM_MUNICIPIO.nome_municipio IS 'Nome do municipio.';
COMMENT ON COLUMN DIM_MUNICIPIO.uf IS 'UF do estado';
COMMENT ON COLUMN DIM_MUNICIPIO.estado IS 'Nome do estado';
COMMENT ON COLUMN DIM_MUNICIPIO.latitude IS 'Latitude da localizacao do municipio.';
COMMENT ON COLUMN DIM_MUNICIPIO.longitude IS 'Longitude da localizacao do municipio.';


-- ============================================================
-- 2. DIM_HOSPITAL (Dimensao Hospitais)
-- ============================================================

CREATE TABLE DIM_HOSPITAL (
    id_hospital VARCHAR2(7) PRIMARY KEY,
    codigo_municipio VARCHAR2(6),
    nome_municipio_hospital VARCHAR2(100) NOT NULL,
    uf_hospital VARCHAR2(2),
    estado_hospital VARCHAR2(50),
    latitude_hospital NUMBER(13,6) DEFAULT 0,
    longitude_hospital NUMBER(13,6) DEFAULT 0,
    leitos_totais NUMBER DEFAULT 0,
    leitos_sus NUMBER DEFAULT 0,
    leitos_nao_sus NUMBER DEFAULT 0,
    esfera VARCHAR2(50),
    tipo_unidade VARCHAR2(50),
    nivel_hierarquico VARCHAR2(50),
    natureza_juridica VARCHAR2(50),
    porte_hospitalar VARCHAR2(50),
    alta_complexidade VARCHAR2(50),
    percentual_sus NUMBER(6,2) DEFAULT 0
);

COMMENT ON TABLE DIM_HOSPITAL IS 'Dimensao com dados dos hospitais.';
COMMENT ON COLUMN DIM_HOSPITAL.id_hospital IS 'Codigo CNES do hospital (7 digitos).';
COMMENT ON COLUMN DIM_HOSPITAL.codigo_municipio IS 'Codigo do municipio onde o hospital esta localizado.';
COMMENT ON COLUMN DIM_HOSPITAL.nome_municipio_hospital IS 'Nome do municipio do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.uf_hospital IS 'UF onde o hospital esta localizado.';
COMMENT ON COLUMN DIM_HOSPITAL.estado_hospital IS 'Nome do estado do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.latitude_hospital IS 'Latitude da localizacao do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.longitude_hospital IS 'Longitude da localizacao do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.leitos_totais IS 'Numero total de leitos do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.leitos_sus IS 'Numero de leitos SUS.';
COMMENT ON COLUMN DIM_HOSPITAL.leitos_nao_sus IS 'Numero de leitos nao SUS.';
COMMENT ON COLUMN DIM_HOSPITAL.esfera IS 'Esfera administrativa (E/M/F).';
COMMENT ON COLUMN DIM_HOSPITAL.tipo_unidade IS 'Tipo da unidade hospitalar.';
COMMENT ON COLUMN DIM_HOSPITAL.nivel_hierarquico IS 'Nivel hierarquico do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.natureza_juridica IS 'Natureza juridica do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.porte_hospitalar IS 'Porte do hospital (Micro, Pequeno, Medio, Grande).';
COMMENT ON COLUMN DIM_HOSPITAL.alta_complexidade IS 'Indica se o hospital realiza procedimentos de alta complexidade.';
COMMENT ON COLUMN DIM_HOSPITAL.percentual_sus IS 'Percentual de leitos SUS em relacao ao total.';


-- ============================================================
-- 3. DIM_TEMPO (Dimensao Tempo)
-- ============================================================

CREATE TABLE DIM_TEMPO (
    tempo_id NUMBER PRIMARY KEY,
    data_referencia DATE NOT NULL,
    ano NUMBER(4) NOT NULL,
    mes NUMBER(2) NOT NULL,
    trimestre NUMBER(1) NOT NULL,
    dia_semana VARCHAR2(20),
    ano_mes VARCHAR2(7) NOT NULL
);

COMMENT ON TABLE DIM_TEMPO IS 'Dimensao com datas e periodos.';
COMMENT ON COLUMN DIM_TEMPO.tempo_id IS 'Identificador unico da data.';
COMMENT ON COLUMN DIM_TEMPO.data_referencia IS 'Data de referencia.';
COMMENT ON COLUMN DIM_TEMPO.ano IS 'Ano da data.';
COMMENT ON COLUMN DIM_TEMPO.mes IS 'Mes da data (1-12).';
COMMENT ON COLUMN DIM_TEMPO.trimestre IS 'Trimestre do ano (1-4).';
COMMENT ON COLUMN DIM_TEMPO.dia_semana IS 'Dia da semana.';
COMMENT ON COLUMN DIM_TEMPO.ano_mes IS 'Ano-mes (ex: 2024-01).';


-- ============================================================
-- 4. FATO_INTERNACAO (Fato Internacoes)
-- ============================================================

CREATE TABLE FATO_INTERNACAO (
    internacao_id NUMBER PRIMARY KEY,
    id_hospital VARCHAR2(7) NOT NULL,
    codigo_municipio_paciente VARCHAR2(6),
    tempo_id NUMBER NOT NULL,
    codigo_diagnostico VARCHAR2(20),
    data_internacao DATE NOT NULL,
    data_saida DATE,
    valor_procedimento NUMBER(15,2) DEFAULT 0,
    dias_internacao NUMBER DEFAULT 0,
    paciente_viajou VARCHAR2(3),
    nome_municipio_paciente VARCHAR2(100),
    uf_paciente VARCHAR2(2),
    estado_paciente VARCHAR2(50),
    latitude_paciente NUMBER(13,6) DEFAULT 0,
    longitude_paciente NUMBER(13,6) DEFAULT 0,
    nome_municipio_hospital VARCHAR2(100),
    latitude_hospital NUMBER(13,6) DEFAULT 0,
    longitude_hospital NUMBER(13,6) DEFAULT 0,
    distancia_estimada_km NUMBER(10,2) DEFAULT 0,
    ano_competencia NUMBER(4),
    mes_competencia NUMBER(2),
    dia_semana VARCHAR2(20),
    tipo_dia VARCHAR2(20),
    CONSTRAINT fk_fato_hospital FOREIGN KEY (id_hospital) REFERENCES DIM_HOSPITAL(id_hospital),
    CONSTRAINT fk_fato_tempo FOREIGN KEY (tempo_id) REFERENCES DIM_TEMPO(tempo_id)
);

COMMENT ON TABLE FATO_INTERNACAO IS 'Fato de internacoes hospitalares.';
COMMENT ON COLUMN FATO_INTERNACAO.internacao_id IS 'Identificador unico da internacao.';
COMMENT ON COLUMN FATO_INTERNACAO.id_hospital IS 'Codigo CNES do hospital.';
COMMENT ON COLUMN FATO_INTERNACAO.codigo_municipio_paciente IS 'Codigo do municipio do paciente.';
COMMENT ON COLUMN FATO_INTERNACAO.tempo_id IS 'Referencia a dimensao de tempo.';
COMMENT ON COLUMN FATO_INTERNACAO.codigo_diagnostico IS 'CID-10 do diagnostico principal.';
COMMENT ON COLUMN FATO_INTERNACAO.data_internacao IS 'Data de internacao.';
COMMENT ON COLUMN FATO_INTERNACAO.data_saida IS 'Data de alta.';
COMMENT ON COLUMN FATO_INTERNACAO.valor_procedimento IS 'Valor do procedimento.';
COMMENT ON COLUMN FATO_INTERNACAO.dias_internacao IS 'Numero de dias de permanencia.';
COMMENT ON COLUMN FATO_INTERNACAO.paciente_viajou IS 'Indica se o paciente viajou para outro municipio.';
COMMENT ON COLUMN FATO_INTERNACAO.nome_municipio_paciente IS 'Nome do municipio do paciente.';
COMMENT ON COLUMN FATO_INTERNACAO.uf_paciente IS 'UF do paciente.';
COMMENT ON COLUMN FATO_INTERNACAO.estado_paciente IS 'Estado do paciente.';
COMMENT ON COLUMN FATO_INTERNACAO.latitude_paciente IS 'Latitude do municipio do paciente.';
COMMENT ON COLUMN FATO_INTERNACAO.longitude_paciente IS 'Longitude do municipio do paciente.';
COMMENT ON COLUMN FATO_INTERNACAO.nome_municipio_hospital IS 'Nome do municipio do hospital.';
COMMENT ON COLUMN FATO_INTERNACAO.latitude_hospital IS 'Latitude do hospital.';
COMMENT ON COLUMN FATO_INTERNACAO.longitude_hospital IS 'Longitude do hospital.';
COMMENT ON COLUMN FATO_INTERNACAO.distancia_estimada_km IS 'Distancia estimada entre municipio do paciente e hospital.';
COMMENT ON COLUMN FATO_INTERNACAO.ano_competencia IS 'Ano de competencia do SIH.';
COMMENT ON COLUMN FATO_INTERNACAO.mes_competencia IS 'Mes de competencia do SIH.';
COMMENT ON COLUMN FATO_INTERNACAO.dia_semana IS 'Dia da semana da internacao.';
COMMENT ON COLUMN FATO_INTERNACAO.tipo_dia IS 'Tipo do dia (Dia Util / Fim de Semana).';


-- ============================================================
-- 5. CONSULTAS DE VERIFICACAO
-- ============================================================

-- Verificar estrutura das tabelas
SELECT table_name, column_name, data_type, data_length, nullable
FROM user_tab_columns
WHERE table_name IN ('DIM_MUNICIPIO', 'DIM_HOSPITAL', 'DIM_TEMPO', 'FATO_INTERNACAO')
ORDER BY table_name, column_id;

-- Verificar constraints
SELECT table_name, constraint_name, constraint_type, status
FROM user_constraints
WHERE table_name IN ('DIM_MUNICIPIO', 'DIM_HOSPITAL', 'DIM_TEMPO', 'FATO_INTERNACAO')
ORDER BY table_name;


-- ============================================================
-- 6. EXEMPLO DE CONSULTA - TAXA DE OCUPACAO
-- ============================================================

/*
SELECT 
    h.id_hospital,
    h.nome_municipio_hospital,
    h.leitos_totais,
    COUNT(f.internacao_id) AS leitos_ocupados,
    ROUND((COUNT(f.internacao_id) / h.leitos_totais) * 100, 2) AS taxa_ocupacao_percentual
FROM DIM_HOSPITAL h
LEFT JOIN FATO_INTERNACAO f 
    ON h.id_hospital = f.id_hospital
    AND f.data_internacao <= DATE '2024-01-15'
    AND f.data_saida >= DATE '2024-01-15'
WHERE h.leitos_totais > 0
GROUP BY h.id_hospital, h.nome_municipio_hospital, h.leitos_totais
ORDER BY taxa_ocupacao_percentual DESC;
*/
-- ============================================================
-- SCRIPT DE CRIAÇÃO DAS TABELAS - MEDDATA
-- Autor: Isabella Oliveira
-- Projeto: MedData - Challenge Oracle 2026
-- ============================================================

-- ============================================================
-- 1. TABELA DIM_HOSPITAL (Dimensão Hospitais)
-- ============================================================

CREATE TABLE DIM_HOSPITAL (
    hospital_id         VARCHAR2(50) PRIMARY KEY,
    codigo_municipio    VARCHAR2(20),
    municipio_nome      VARCHAR2(100),
    leitos_totais       NUMBER,
    leitos_contratados  NUMBER,
    leitos_sus          NUMBER,
    leitos_nao_sus      NUMBER,
    porte               VARCHAR2(50),
    alta_complexidade   VARCHAR2(10),
    esfera              VARCHAR2(50),
    percentual_sus      NUMBER(5,2),
    latitude            NUMBER(10,6),
    longitude           NUMBER(10,6)
);

-- Comentários para o SELECT AI entender
COMMENT ON TABLE DIM_HOSPITAL IS 'Cadastro de hospitais com informações de leitos e localização.';
COMMENT ON COLUMN DIM_HOSPITAL.hospital_id IS 'Identificador único do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.codigo_municipio IS 'Código do município onde o hospital está localizado.';
COMMENT ON COLUMN DIM_HOSPITAL.municipio_nome IS 'Nome do município do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.leitos_totais IS 'Número total de leitos disponíveis no hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.leitos_contratados IS 'Número de leitos contratados pelo SUS.';
COMMENT ON COLUMN DIM_HOSPITAL.leitos_sus IS 'Número de leitos exclusivos para o SUS.';
COMMENT ON COLUMN DIM_HOSPITAL.leitos_nao_sus IS 'Número de leitos não SUS (privados).';
COMMENT ON COLUMN DIM_HOSPITAL.porte IS 'Porte do hospital (ex: pequeno, médio, grande).';
COMMENT ON COLUMN DIM_HOSPITAL.alta_complexidade IS 'Indica se o hospital realiza procedimentos de alta complexidade.';
COMMENT ON COLUMN DIM_HOSPITAL.esfera IS 'Esfera administrativa (ex: público, privado, filantrópico).';
COMMENT ON COLUMN DIM_HOSPITAL.percentual_sus IS 'Percentual de leitos SUS em relação ao total.';
COMMENT ON COLUMN DIM_HOSPITAL.latitude IS 'Latitude da localização do hospital.';
COMMENT ON COLUMN DIM_HOSPITAL.longitude IS 'Longitude da localização do hospital.';

-- ============================================================
-- 2. TABELA DIM_MUNICIPIO (Dimensão Municípios)
-- ============================================================

CREATE TABLE DIM_MUNICIPIO (
    municipio_id        VARCHAR2(20) PRIMARY KEY,
    nome_municipio      VARCHAR2(100),
    latitude            NUMBER(10,6),
    longitude           NUMBER(10,6),
    distancia_media     NUMBER(10,2)
);

COMMENT ON TABLE DIM_MUNICIPIO IS 'Dados dos municípios para análise regional.';
COMMENT ON COLUMN DIM_MUNICIPIO.municipio_id IS 'Código do município (IBGE).';
COMMENT ON COLUMN DIM_MUNICIPIO.nome_municipio IS 'Nome do município.';
COMMENT ON COLUMN DIM_MUNICIPIO.latitude IS 'Latitude da localização do município.';
COMMENT ON COLUMN DIM_MUNICIPIO.longitude IS 'Longitude da localização do município.';
COMMENT ON COLUMN DIM_MUNICIPIO.distancia_media IS 'Distância média do município até o hospital de referência.';

-- ============================================================
-- 3. TABELA DIM_TEMPO (Dimensão Tempo)
-- ============================================================

CREATE TABLE DIM_TEMPO (
    tempo_id            NUMBER PRIMARY KEY,
    data_referencia     DATE NOT NULL,
    ano                 NUMBER(4),
    mes                 NUMBER(2),
    ano_mes             VARCHAR2(7)
);

COMMENT ON TABLE DIM_TEMPO IS 'Dimensão de tempo para análise histórica e projeções.';
COMMENT ON COLUMN DIM_TEMPO.tempo_id IS 'Identificador único da data.';
COMMENT ON COLUMN DIM_TEMPO.data_referencia IS 'Data de referência (geralmente início do mês).';
COMMENT ON COLUMN DIM_TEMPO.ano IS 'Ano da data de referência.';
COMMENT ON COLUMN DIM_TEMPO.mes IS 'Mês da data de referência (1-12).';
COMMENT ON COLUMN DIM_TEMPO.ano_mes IS 'Ano-mês (ex: 2024-01).';

-- ============================================================
-- 4. TABELA FATO_INTERNACAO (Fato Internações)
-- ============================================================

CREATE TABLE FATO_INTERNACAO (
    internacao_id       NUMBER PRIMARY KEY,
    hospital_id         VARCHAR2(50) NOT NULL,
    municipio_id        VARCHAR2(20) NOT NULL,
    tempo_id            NUMBER NOT NULL,
    diagnostico         VARCHAR2(20),
    data_saida          DATE,
    valor               NUMBER(15,2),
    dias_internacao     NUMBER,
    viajou              VARCHAR2(3),
    tipo_leito          VARCHAR2(50),
    tipo_unidade        VARCHAR2(50),
    CONSTRAINT fk_fato_hospital FOREIGN KEY (hospital_id) REFERENCES DIM_HOSPITAL(hospital_id),
    CONSTRAINT fk_fato_municipio FOREIGN KEY (municipio_id) REFERENCES DIM_MUNICIPIO(municipio_id),
    CONSTRAINT fk_fato_tempo FOREIGN KEY (tempo_id) REFERENCES DIM_TEMPO(tempo_id)
);

COMMENT ON TABLE FATO_INTERNACAO IS 'Fato de internações hospitalares para análise de capacidade e perfil de atendimento.';
COMMENT ON COLUMN FATO_INTERNACAO.internacao_id IS 'Identificador único da internação.';
COMMENT ON COLUMN FATO_INTERNACAO.hospital_id IS 'Referência ao hospital (DIM_HOSPITAL).';
COMMENT ON COLUMN FATO_INTERNACAO.municipio_id IS 'Referência ao município (DIM_MUNICIPIO).';
COMMENT ON COLUMN FATO_INTERNACAO.tempo_id IS 'Referência à data (DIM_TEMPO).';
COMMENT ON COLUMN FATO_INTERNACAO.diagnostico IS 'Código CID do diagnóstico da internação.';
COMMENT ON COLUMN FATO_INTERNACAO.data_saida IS 'Data de alta do paciente.';
COMMENT ON COLUMN FATO_INTERNACAO.valor IS 'Valor total do procedimento ou internação.';
COMMENT ON COLUMN FATO_INTERNACAO.dias_internacao IS 'Número de dias de permanência.';
COMMENT ON COLUMN FATO_INTERNACAO.viajou IS 'Indica se o paciente viajou para outro município para o atendimento.';
COMMENT ON COLUMN FATO_INTERNACAO.tipo_leito IS 'Tipo de leito utilizado.';
COMMENT ON COLUMN FATO_INTERNACAO.tipo_unidade IS 'Tipo de unidade de atendimento.';

-- ============================================================
-- FIM DO SCRIPT
-- ============================================================
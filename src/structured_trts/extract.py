"""
Extraction module for structured data from labor court sentences.
"""

from __future__ import annotations
from typing import Literal, List, Optional
from enum import Enum
import time
import json
from pydantic import BaseModel, Field
from tqdm import tqdm
import tiktoken
import pandas as pd
from openai import OpenAI
from groq import Groq
from google import genai
from google.genai import types

# ---------- Enums: taxonomias e estados ----------

class Gratuidade(Enum):
    """Indica se a gratuidade foi concedida ao trabalhador."""
    CONCEDIDA = "concedida"
    NAO_CONCEDIDA = "nao_concedida"

class DecisionType(Enum):
    """Tipo de decisão."""
    SENTENCA_MERITO = "sentenca_merito"
    HOMOLOGACAO_ACORDO = "homologacao_acordo"
    EXTINCAO_SEM_MERITO = "extincao_sem_julgamento_merito"

class DecisionOutcome(Enum):
    """Resultado da decisão."""
    PROCEDENTE = "procedente"
    PARCIALMENTE_PROCEDENTE = "parcialmente_procedente"
    IMPROCEDENTE = "improcedente"
    ACORDO = "acordo"
    PREJUDICADO = "prejudicado"

class Reflexos(Enum):
    """Indica se houve reflexos para o pedido específico."""
    SIM = "sim"
    NAO = "nao"

class ClaimType(Enum):
    """Tipo de pedido."""
    AVISO_PREVIO_13994 = "(13994) Aviso Prévio"
    INTEGRACAO_EM_VERBAS_RESCISORIAS_13924 = "(13924) Integração em Verbas Rescisórias"
    VERBAS_RESCISORIAS_13970 = "(13970) Verbas Rescisórias"
    ANOTACAO_RETENCAO_DA_CTPS_14017 = "(14017) Anotação/Retenção da CTPS"
    ANOTACAO_BAIXA_RETIFICACAO_13745 = "(13745) Anotação/Baixa/Retificação"
    ASSEDIO_MORAL_14018 = "(14018) Assédio Moral"
    ADICIONAL_DE_HORAS_EXTRAS_13787 = "(13787) Adicional de Horas Extras"
    RECONHECIMENTO_DE_RELACAO_DE_EMPREGO_13722 = "(13722) Reconhecimento de Relação de Emprego"
    FGTS_13719 = "(13719) FGTS"
    TRABALHADOR_AVULSO_13828 = "(13828) Trabalhador Avulso"
    DESCONFIGURACAO_DE_JUSTA_CAUSA_14023 = "(14023) Desconfiguração de Justa Causa"
    ADICIONAL_DE_HORA_EXTRA_13799 = "(13799) Adicional de Hora Extra"
    ADICIONAL_DE_INSALUBRIDADE_13875 = "(13875) Adicional de Insalubridade"
    HORAS_EXTRAS_13769 = "(13769) Horas Extras"
    ABONO_13832 = "(13832) Abono"
    HONORARIOS_NA_JUSTICA_DO_TRABALHO_13184 = "(13184) Honorários na Justiça do Trabalho "
    CTPS_13716 = "(13716) CTPS"
    ESTABILIDADE_DECORRENTE_DE_NORMA_COLETIVA_13984 = "(13984) Estabilidade Decorrente de Norma Coletiva"
    ADICIONAL_DE_PERICULOSIDADE_13877 = "(13877) Adicional de Periculosidade"
    ESTABILIDADE_ACIDENTARIA_13983 = "(13983) Estabilidade Acidentária"
    JUSTA_CAUSA_FALTA_GRAVE_13962 = "(13962) Justa Causa/Falta Grave"
    RESCISAO_INDIRETA_13968 = "(13968) Rescisão Indireta"
    INTERVALO_INTRAJORNADA_13772 = "(13772) Intervalo Intrajornada"
    DEPOSITO_DIFERENCAS_13749 = "(13749) Depósito/Diferenças"
    ADICIONAL_13833 = "(13833) Adicional"
    HORAS_EXTRAS_13186 = "(13186) Horas Extras "
    MULTA_DO_ARTIGO_477_DA_CLT_14000 = "(14000) Multa do Artigo  477 da CLT"
    ACUMULO_DE_FUNCAO_13732 = "(13732) Acúmulo de Função"
    CONTRATUAIS_13385 = "(13385) Contratuais "
    INDENIZACAO_POR_DANO_MORAL_14033 = "(14033) Indenização por Dano Moral"
    REINTEGRACAO_DE_EMPREGADO_13609 = "(13609) Reintegração de Empregado "
    DECIMO_TERCEIRO_SALARIO_PROPORCIONAL_13995 = "(13995) Décimo Terceiro Salário Proporcional"
    DIVISOR_13793 = "(13793) Divisor"
    PLANO_DE_SAUDE_13605 = "(13605) Plano de Saúde "
    INCORPORACAO_13913 = "(13913) Incorporação"
    ANULACAO_NULIDADE_DE_ATO_OU_NEGOCIO_JURIDICO_12948 = "(12948) Anulação / Nulidade de Ato ou Negócio Jurídico "
    INDENIZACAO_POR_RESCISAO_ANTECIPADA_DO_CONTRATO_A_TERMO_13961 = "(13961) Indenização por Rescisão Antecipada do Contrato a Termo"
    TERMO_DE_RESCISAO_CONTRATUAL_13978 = "(13978) Termo de Rescisão Contratual"
    VALE_TRANSPORTE_13864 = "(13864) Vale Transporte"
    PROPORCIONAL_14005 = "(14005) Proporcional"
    GRUPO_ECONOMICO_14036 = "(14036) Grupo Econômico"
    ISONOMIA_DIFERENCA_SALARIAL_13692 = "(13692) isonomia/Diferença Salarial"
    ADICIONAL_NOTURNO_13765 = "(13765) Adicional Noturno"
    ANOTACAO_NA_CTPS_13062 = "(13062) Anotação na CTPS "
    ALIMENTACAO_11848 = "(11848) Alimentação"
    DESCONTOS_FISCAIS_12975 = "(12975) Descontos Fiscais "
    ACORDO_COMISSAO_DE_CONCILIACAO_PREVIA_13976 = "(13976) Acordo - Comissão de Conciliação Prévia"
    DISPENSA_RESCISAO_DO_CONTRATO_DE_TRABALHO_13406 = "(13406) Dispensa / Rescisão do Contrato de Trabalho "
    ABONO_PECUNIARIO_13810 = "(13810) Abono Pecuniário"
    QUEBRA_DE_CAIXA_13855 = "(13855) Quebra de Caixa"
    RESPONSABILIDADE_CIVIL_EM_OUTRAS_RELACOES_DE_TRABALHO_14031 = "(14031) Responsabilidade Civil em Outras Relações de Trabalho"
    CARGO_DE_CONFIANCA_13789 = "(13789) Cargo de Confiança"
    MULTA_DE_40_DO_FGTS_13998 = "(13998) Multa de 40% do FGTS"
    REFLEXOS_13796 = "(13796) Reflexos"
    COOPERATIVA_DE_TRABALHO_13752 = "(13752) Cooperativa de Trabalho"
    AUMENTO_COMPENSATORIO_ESPECIAL_13920 = "(13920) Aumento Compensatório Especial"
    INDENIZACAO_POR_DANO_MORAL_14010 = "(14010) Indenização por Dano Moral"
    RESCISAO_DO_CONTRATO_DE_TRABALHO_13949 = "(13949) Rescisão do Contrato de Trabalho"
    SUCESSAO_DE_EMPREGADORES_14039 = "(14039) Sucessão de Empregadores"
    CONTROLE_DE_JORNADA_13768 = "(13768) Controle de Jornada"
    DESPEDIDA_DISPENSA_IMOTIVADA_13954 = "(13954) Despedida/Dispensa Imotivada"
    RELACAO_DE_TRABALHO_13525 = "(13525) Relação de Trabalho "
    BANCARIOS_13648 = "(13648) Bancários"
    TERCEIRIZACAO_TOMADOR_DE_SERVICOS_14040 = "(14040) Terceirização/Tomador de Serviços"
    DOENCA_OCUPACIONAL_14024 = "(14024) Doença Ocupacional"
    GESTANTE_13988 = "(13988) Gestante"
    SUPRESSAO_REDUCAO_DE_HORAS_EXTRAS_HABITUAIS_INDENIZACAO_13861 = "(13861) Supressão/Redução de Horas Extras Habituais - Indenização"
    SUBEMPREITADA_14120 = "(14120) Subempreitada"
    VERBAS_REMUNERATORIAS_INDENIZATORIAS_E_BENEFICIOS_13831 = "(13831) Verbas Remuneratórias, Indenizatórias e Benefícios"
    ACIDENTE_DE_TRABALHO_14012 = "(14012) Acidente de Trabalho"
    ACIDENTE_DE_TRABALHO_14016 = "(14016) Acidente de Trabalho"
    REAJUSTE_SALARIAL_13931 = "(13931) Reajuste Salarial"
    ENTE_PUBLICO_14043 = "(14043) Ente Público"
    DIFERENCAS_POR_DESVIO_DE_FUNCAO_13922 = "(13922) Diferenças por Desvio de Função"
    COMISSIONISTA_13790 = "(13790) Comissionista"
    DISPENSA_DISCRIMINATORIA_13990 = "(13990) Dispensa Discriminatória"
    RADIALISTAS_13671 = "(13671) Radialistas"
    ACORDO_E_CONVENCAO_COLETIVOS_DE_TRABALHO_13048 = "(13048) Acordo e Convenção Coletivos de Trabalho "
    DOENCA_OCUPACIONAL_14014 = "(14014) Doença Ocupacional"
    ANTECIPACAO_DE_TUTELA_TUTELA_ESPECIFICA_8961 = "(8961) Antecipação de Tutela / Tutela Específica"
    CONEXAO_13109 = "(13109) Conexão "
    BANCO_DE_HORAS_13781 = "(13781) Banco de Horas"
    COMPETENCIA_DA_JUSTICA_DO_TRABALHO_10652 = "(10652) Competência da Justiça do Trabalho"
    PERMUTA_13254 = "(13254) Permuta "
    APLICABILIDADE_4435 = "(4435) Aplicabilidade"
    SUSPENSAO_INTERRUPCAO_DO_CONTRATO_DE_TRABALHO_13724 = "(13724) Suspensão/Interrupção do Contrato de Trabalho"
    DECIMO_TERCEIRO_SALARIO_13843 = "(13843) Décimo Terceiro Salário"
    UTILIZACAO_DE_BENS_PUBLICOS_11870 = "(11870) Utilização de bens públicos"
    DURACAO_DO_TRABALHO_13764 = "(13764) Duração do Trabalho"
    UNICIDADE_CONTRATUAL_13725 = "(13725) Unicidade Contratual"
    NEGOCIACAO_COLETIVA_TRABALHISTA_13013 = "(13013) Negociação Coletiva Trabalhista "
    PIS_INDENIZACAO_13852 = "(13852) PIS - Indenização"
    ADVERTENCIA_SUSPENSAO_13709 = "(13709) Advertência/Suspensão"
    MULTA_DO_ARTIGO_467_DA_CLT_13999 = "(13999) Multa do Artigo 467 da CLT "
    SALARIO_POR_FORA_INTEGRACAO_13940 = "(13940) Salário por Fora - Integração"
    CONTRIBUICAO_SINDICAL_13621 = "(13621) Contribuição Sindical"
    INDENIZACAO_DOBRA_TERCO_CONSTITUCIONAL_13814 = "(13814) Indenização/Dobra/Terço Constitucional"
    FERIAS_PROPORCIONAIS_13996 = "(13996) Férias Proporcionais"
    NULIDADE_13974 = "(13974) Nulidade"
    PROFESSORES_13667 = "(13667) Professores"
    DANO_MORAL_MATERIAL_13390 = "(13390) Dano Moral / Material "
    DEVOLUCAO_ENTREGA_DE_OBJETOS_DOCUMENTOS_12979 = "(12979) Devolução / Entrega de Objetos / Documentos "
    PENSAO_VITALICIA_14015 = "(14015) Pensão Vitalícia"
    PROMOCAO_13930 = "(13930) Promoção"
    INDENIZACAO_POR_DANO_MATERIAL_14009 = "(14009) Indenização por Dano Material"
    GORJETA_13846 = "(13846) Gorjeta"
    CORRECAO_MONETARIA_13748 = "(13748) Correção Monetária"
    SALARIO_POR_EQUIPARACAO_ISONOMIA_13939 = "(13939) Salário por Equiparação/Isonomia"
    OUTROS_DESCONTOS_SALARIAIS_13899 = "(13899) Outros Descontos Salariais"
    RESPONSABILIDADE_SOLIDARIA_SUBSIDIARIA_14034 = "(14034) Responsabilidade Solidária/Subsidiária"
    FERIADO_EM_DOBRO_13805 = "(13805) Feriado em Dobro"
    SUPRESSAO_REDUCAO_DE_HORAS_EXTRAS_INDENIZACAO_13797 = "(13797) Supressão/Redução de Horas Extras/Indenização"
    FERIAS_COLETIVAS_13812 = "(13812) Férias Coletivas"
    MORA_14066 = "(14066) Mora"
    PLANO_DE_CARGOS_E_SALARIOS_13929 = "(13929) Plano de Cargos e Salários"
    CONTRATO_POR_PRAZO_DETERMINADO_13715 = "(13715) Contrato por Prazo Determinado"

    # --- helpers úteis ---
    @property
    def code(self) -> int:
        """Retorna o código inteiro do item, extraindo do value '(####) Descrição'."""
        # value começa com '(' + dígitos + ') '
        return int(self.value[1:self.value.find(')')])

    @property
    def description(self) -> str:
        """Retorna a descrição sem o código."""
        return self.value[self.value.find(')') + 2 :]

    @classmethod
    def from_code(cls, code: int) -> "ClaimType":
        """Obtém o Enum pelo código. Lança KeyError se não existir."""
        for item in cls:
            if item.code == int(code):
                return item
        raise KeyError(f"Código não mapeado no ClaimType: {code}")


# ---------- Tipos de apoio ----------

class Money(BaseModel):
    """Representa um valor monetário."""
    amount: float = Field(description="Valor monetário em reais")
    currency: str = Field(description="Moeda utilizada (geralmente BRL)")
    is_liquidacao: Optional[bool] = Field(description="Indica se o valor é de liquidação")

class ClaimDecision(BaseModel):
    """Decisão por pedido (núcleo da extração)."""
    claim_type: ClaimType = Field(description="Tipo de pedido, extraído dos metadados do processo ou da decisão")
    outcome: DecisionOutcome = Field(description="Resultado da decisão, extraído do texto da decisão, provavelmente na parte do dispositivo ou da fundamentação/decisão")
    valor_recebido: Optional[Money] = Field(description="Valor de indenização ou do acordo celebrado, específico do pedido, extraído do texto da decisão, provavelmente na parte do dispositivo ou da fundamentação/decisão")
    reflexos: Optional[Reflexos] = Field(description="Indica se houve reflexos para o pedido específico, extraído do texto da decisão, provavelmente na parte do dispositivo ou da fundamentação/decisão")

class LaborSentenceExtraction(BaseModel):
    """Representa a extração de uma sentença em processo trabalhista."""
    decision_type: DecisionType = Field(description="Tipo de decisão, extraído do texto da decisão, provavelmente na parte do dispositivo ou da fundamentação/decisão")
    claims: List[ClaimDecision] = Field(description="Lista de pedidos e suas decisões, extraídos de todo o conteúdo da entrada")
    custas: Optional[Money] = Field(description="Valor das custas processuais aplicadas ao caso, extraído do texto da decisão")
    gratuidade: Optional[Gratuidade] = Field(description="Indica se a gratuidade foi concedida ao trabalhador, extraído do texto da decisão")
    valor_total_decisao: Optional[Money] = Field(description="Valor de indenização total ou valor do acordo total, extraído dos textos disponíveis")

class ExtractionResult(BaseModel):
    """Resultado da extração."""
    model_name: str
    provider: str
    input_tokens: int
    output_tokens: int
    extraction_time_seconds: float
    success: bool
    error_message: Optional[str] = None
    extracted_data: Optional[LaborSentenceExtraction] = None

# ---------- Model Configurations ----------

class ModelConfig(BaseModel):
    """Configuração de um modelo."""
    name: str
    provider: Literal["openai", "gemini", "groq"]
    model_id: str
    max_tokens: Optional[int] = None
    temperature: float = 0.0
    price_input_1M: float = 0.0
    price_output_1M: float = 0.0

# Predefined model configurations
MODEL_CONFIGS = {
    "gpt-4.1": ModelConfig(name="OpenAI GPT-4.1", provider="openai", model_id="gpt-4.1", temperature=0.0, price_input_1M=3.0, price_output_1M=12.0),
    "gpt-4.1-mini": ModelConfig(name="OpenAI GPT-4.1-mini", provider="openai", model_id="gpt-4.1-mini", temperature=0.0, price_input_1M=0.8, price_output_1M=3.2),
    "gpt-4.1-nano": ModelConfig(name="OpenAI GPT-4.1-nano", provider="openai", model_id="gpt-4.1-nano", temperature=0.0, price_input_1M=0.2, price_output_1M=0.8),
    "gemini-2.5-pro": ModelConfig(name="Gemini 2.5 Pro", provider="gemini", model_id="gemini-2.5-pro", temperature=0.0, price_input_1M=1.25, price_output_1M=10.0),
    "gemini-2.5-flash": ModelConfig(name="Gemini 2.5 Flash", provider="gemini", model_id="gemini-2.5-flash", temperature=0.0, price_input_1M=0.3, price_output_1M=2.5),
    "gpt-oss-120b": ModelConfig(name="GPT OSS 120B", provider="groq", model_id="openai/gpt-oss-120b", temperature=0.0, price_input_1M=0.15, price_output_1M=0.75),
    "gpt-oss-20b": ModelConfig(name="GPT OSS 20B", provider="groq", model_id="openai/gpt-oss-20b", temperature=0.0, price_input_1M=0.10, price_output_1M=0.50),
    "llama-4-maverick": ModelConfig(name="Llama 4 Maverick", provider="groq", model_id="meta-llama/llama-4-maverick-17b-128e-instruct", temperature=0.0, price_input_1M=0.20, price_output_1M=0.60),
    "llama-4-scout": ModelConfig(name="Llama 4 Scout", provider="groq", model_id="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0.0, price_input_1M=0.11, price_output_1M=0.34),
    "kimi-k2": ModelConfig(name="Kimi K2", provider="groq", model_id="moonshotai/kimi-k2-instruct", temperature=0.0, price_input_1M=1.0, price_output_1M=3.0),
}

# ---------- Extraction Functions ----------

def load_prompt(prompt_path: str) -> str:
    """Carrega o prompt do arquivo."""
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()

def token_count(text: str) -> int:
    """Contagem de tokens."""
    enc = tiktoken.encoding_for_model("gpt-4o")
    return len(enc.encode(text))

def extract_with_direct_api(text: str, prompt: str, model_key: str) -> ExtractionResult:
    """
    Extração de dados usando APIs diretas (OpenAI, Google, Groq).
    """
    start_time = time.time()
    model_config = MODEL_CONFIGS[model_key]
    # token count if model fails
    input_tokens = token_count(prompt + text)
    
    try:
        if model_config.provider == "openai":
            result = _extract_openai(text, prompt, model_config)            
        elif model_config.provider == "gemini":
            result = _extract_gemini(text, prompt, model_config)
        elif model_config.provider == "groq":
            result = _extract_groq(text, prompt, model_config)
        else:
            raise ValueError(f"Unsupported provider: {model_config.provider}")

        return ExtractionResult(
            model_name=model_config.name,
            provider=model_config.provider,
            input_tokens=result['input_tokens'],
            output_tokens=result['output_tokens'],
            extraction_time_seconds=time.time() - start_time,
            success=True,
            extracted_data=result["data"]
        )
        
    except Exception as e:
        return ExtractionResult(
            model_name=model_config.name,
            provider=model_config.provider,
            input_tokens=input_tokens,
            output_tokens=0,
            extraction_time_seconds=time.time() - start_time,
            success=False,
            error_message=str(e)
        )

def _extract_openai(text: str, prompt: str, model_config: ModelConfig) -> dict:
    """Extração usando OpenAI Responses API."""
    client = OpenAI()

    response = client.responses.parse(
        model=model_config.model_id,
        instructions=prompt,
        input=text,
        text_format=LaborSentenceExtraction,
        temperature=model_config.temperature
    )

    return {
        "data": json.loads(response.output_parsed.model_dump_json()),
        "input_tokens": getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0,
        "output_tokens": getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0
    }

def _extract_gemini(text: str, prompt: str, model_config: ModelConfig) -> dict:
    """Extração usando Google Gemini API."""
    client = genai.Client()

    response = client.models.generate_content(
        model=model_config.model_id,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=prompt,
            temperature=model_config.temperature,
            response_mime_type="application/json",
            response_schema=LaborSentenceExtraction
        ),
    )

    prompt_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) if hasattr(response, 'usage_metadata') else 0
    thought_tokens = getattr(response.usage_metadata, 'thoughts_token_count', 0) if hasattr(response, 'usage_metadata') else 0
    candidate_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) if hasattr(response, 'usage_metadata') else 0
    output_tokens = thought_tokens + candidate_tokens

    return {
        "data": json.loads(response.text),
        "output_tokens": output_tokens,
        "input_tokens": prompt_tokens
    }

def _extract_groq(text: str, prompt: str, model_config: ModelConfig) -> dict:
    """Extração usando Groq API."""
    client = Groq()

    response = client.chat.completions.create(
        model=model_config.model_id,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "labor_decision",
                "schema": LaborSentenceExtraction.model_json_schema()
            }
        },
        temperature=model_config.temperature
    )

    data = json.loads(response.choices[0].message.content)

    return {
        "data": data,
        "output_tokens": getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') else 0,
        "input_tokens": getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') else 0
    }

def run_extraction_batch(
    df: pd.DataFrame,
    text_column: str,
    prompt_path: str,
    models: List[str],
    max_tokens: int = 120000,
    output_path: Optional[str] = None
) -> pd.DataFrame:
    """Realiza extração em lote de textos com múltiplos modelos."""
    
    # Load prompt
    prompt = load_prompt(prompt_path)
    
    # Filter by token count
    df_filtered = df[df["enc_len"] < max_tokens].copy()
    
    results = []
    
    for idx, row in tqdm(df_filtered.iterrows(), total=len(df_filtered), desc="Processing texts"):
        text = row[text_column]
        processo = row.get("processo", f"doc_{idx}")
        
        for model_key in models:
            try:
                result = extract_with_direct_api(text, prompt, model_key)
                
                # Convert to dict for storage
                result_dict = {
                    "processo": processo,
                    "model_name": result.model_name,
                    "provider": result.provider,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "extraction_time_seconds": result.extraction_time_seconds,
                    "success": result.success,
                    "error_message": result.error_message,
                    "extracted_data": result.extracted_data.model_dump() if result.extracted_data else None,
                }

                results.append(result_dict)

            except Exception as e:
                # Log error and continue
                error_dict = {
                    "processo": processo,
                    "model_name": MODEL_CONFIGS[model_key].name,
                    "provider": MODEL_CONFIGS[model_key].provider,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "extraction_time_seconds": 0,
                    "success": False,
                    "error_message": str(e),
                    "extracted_data": None,
                }
                results.append(error_dict)
    results_df = pd.DataFrame(results)
    if output_path:
        results_df.to_parquet(output_path, index=False)
    return results_df

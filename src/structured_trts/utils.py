"""
Utils para leitura de arquivos
"""
from pathlib import Path
import json
import tiktoken
import pandas as pd
import numpy as np

enc = tiktoken.encoding_for_model("gpt-4.1-mini")

def ler_arquivo(path: str) -> str:
    """
    Leitura tolerante a erros; converte para UTF-8
    
    Args:
        path (str): caminho do arquivo
    
    Returns:
        str: texto lido
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        s = f.read()
    # garante utf-8 "limpo" (remove bytes inválidos se houver)
    return s.encode("utf-8", "ignore").decode("utf-8", "ignore")


def ler_arquivo_json(path: str) -> dict:
    """
    Leitura tolerante a erros; converte para UTF-8
    
    Args:
        path (str): caminho do arquivo
    
    Returns:
        dict: texto lido
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        s = f.read()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {}

def clean_metadata(metadata_list):
    """
    Processa lista de metadados:
    1. Mantém apenas tramitação atual se for G1
    2. Mantém apenas tramitação G1
    """
    if not metadata_list or not isinstance(metadata_list, list):
        return []
    resultado = []
    for metadata in metadata_list:
        if not isinstance(metadata, dict):
            continue
        # Verifica se tramitação atual é G1
        tramitacao_atual = metadata.get('tramitacaoAtual', {})
        grau_atual = tramitacao_atual.get('grau', {})
        # se tramitação atual é G1, mantém apenas ela
        if grau_atual.get('sigla') == 'G1':
            resultado.append(tramitacao_atual)
        # se tramitação atual não é G1, busca a tramitação G1 e mantém apenas ela
        else:
            tramitacoes = metadata.get('tramitacoes', [{}])
            for tram in tramitacoes:
                if tram.get('grau', {}).get('sigla') == 'G1':
                    resultado.append(tram)
    return resultado

def juntar_com_separador(group):
    """Junta textos com separador incluindo nome do arquivo"""
    textos_com_separador = []
    textos_sentencas_com_separador = []
    for _, row in group.iterrows():
        nome_arquivo = Path(row['value']).name
        separador = f"\n\n# Arquivo {nome_arquivo} ---------------------------\n\n"
        # Adiciona separador + texto para todos os arquivos
        textos_com_separador.append(separador + row['txt'])
        # Para sentenças/audiências, só adiciona se o arquivo contém esses termos
        termos = ['sentença', 'sentenca', 'audiência', 'audiencia']
        if pd.notna(row['value']) and any(termo in row['value'].lower() for termo in termos):
            textos_sentencas_com_separador.append(separador + row['txt'])
    return pd.Series({
        'txt': '\n'.join(textos_com_separador),
        'txt_sentencas': '\n'.join(textos_sentencas_com_separador)
    })

def numpy_to_python(obj):
    """Converte objetos numpy para Python"""
    if isinstance(obj, np.ndarray):
        return [numpy_to_python(x) for x in obj.tolist()]
    elif isinstance(obj, dict):
        return {k: numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [numpy_to_python(x) for x in obj]
    else:
        return obj

def adicionar_metadados_ao_texto(row):
    """Adiciona metadados em formato JSON ao início dos textos"""
    # Converter metadados para formato serializável
    metadata_serializavel = numpy_to_python(row['metadata'])
    # Converter metadados para JSON pretty
    metadados_json = json.dumps(metadata_serializavel, indent=2, ensure_ascii=False)    
    # Estrutura com tags
    prefixo = f"<metadados>\n{metadados_json}\n</metadados>\n\n<textos>\n"
    sufixo = "\n</textos>"
    # Aplicar aos dois campos de texto
    txt_completo = prefixo + row['txt'] + sufixo if pd.notna(row['txt']) else ""
    txt_sentencas_completo = prefixo + \
      row['txt_sentencas'] + \
      sufixo if pd.notna(row['txt_sentencas']) else ""
    return pd.Series({
        'txt_com_metadados': txt_completo,
        'txt_sentencas_com_metadados': txt_sentencas_completo
    })

def contar_tokens(texto: str) -> int:
    """
    Contagem de tokens
    
    Args:
        texto (str): texto a ser contado
    
    Returns:
        int: número de tokens
    """
    return len(enc.encode(texto))

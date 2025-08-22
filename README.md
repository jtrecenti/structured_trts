# Structured TRTs

Sistema para extração estruturada de dados de sentenças trabalhistas usando LLMs (Large Language Models).

## 📋 Pré-requisitos

- Python 3.11 ou superior
- [uv](https://docs.astral.sh/uv/) - Gerenciador de pacotes Python ultrarrápido
- VS Code ou Cursor IDE
- Chaves de API para os modelos que deseja usar (OpenAI, Google Gemini, Groq)

## 🚀 Instalação e Configuração

### 1. Instalar uv

Se ainda não tem o uv instalado:

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clonar e configurar o projeto

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd structured_trts

# Sincronizar dependências com uv
uv sync

# Ativar o ambiente virtual
# No Windows:
.venv\Scripts\activate
# No macOS/Linux:
source .venv/bin/activate
```

### 3. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
# Copie o template (se existir) ou crie um novo
cp .env.example .env  # ou crie manualmente
```

Adicione suas chaves de API no arquivo `.env`:

```env
# OpenAI
OPENAI_API_KEY=sua_chave_openai_aqui

# Google Gemini
GOOGLE_API_KEY=sua_chave_google_aqui

# Groq
GROQ_API_KEY=sua_chave_groq_aqui
```

## 🔧 Configuração no VS Code/Cursor

### 1. Abrir o projeto

```bash
# Para VS Code
code .

# Para Cursor
cursor .
```

### 2. Selecionar o interpretador Python

1. Abra a paleta de comandos (`Ctrl+Shift+P` / `Cmd+Shift+P`)
2. Digite "Python: Select Interpreter"
3. Selecione o interpretador do ambiente virtual: `.venv/bin/python` (Linux/macOS) ou `.venv\Scripts\python.exe` (Windows)

### 3. Extensões recomendadas

Instale as seguintes extensões no VS Code/Cursor:

- **Python** - Suporte completo para Python
- **Jupyter** - Para executar notebooks `.qmd`
- **Quarto** - Suporte para arquivos Quarto
- **Python Docstring Generator** - Geração automática de docstrings

### 4. Configuração do workspace (opcional)

Crie `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "jupyter.notebookFileRoot": "${workspaceFolder}",
    "files.associations": {
        "*.qmd": "quarto"
    }
}
```

## 📊 Estrutura do Projeto

```text
structured_trts/
├── src/structured_trts/     # Código principal
│   ├── extract.py          # Módulo de extração com LLMs
│   └── utils.py            # Utilitários
├── notebooks/              # Notebooks de análise
│   ├── 0-read.qmd         # Leitura de dados
│   ├── 1-extract-loop.qmd # Loop de extração
│   └── 2-explore.qmd      # Exploração de resultados
├── prompts/               # Templates de prompts
│   └── prompt.md         # Prompt principal para extração
├── data/                 # Dados (criado automaticamente)
├── pyproject.toml       # Configuração do projeto
├── uv.lock             # Lock file do uv
└── README.md           # Este arquivo
```

## 🎯 Como usar

### 1. Preparar os dados

Coloque seus arquivos de dados na pasta `data/`. O sistema espera arquivos Parquet com colunas de texto para processar.

### 2. Executar notebooks

**Opção A: Via VS Code/Cursor**

1. Abra o arquivo `.qmd` desejado
2. Execute as células uma por uma ou todas de uma vez

**Opção B: Via terminal**

```bash
# Ativar ambiente se não estiver ativo
uv run python -m jupyter lab

# Ou executar diretamente com quarto (se instalado)
quarto render notebooks/1-extract-loop.qmd
```

### 3. Workflow típico

1. **Leitura de dados** (`0-read.qmd`):
   - Carrega e processa os textos
   - Calcula tokens e filtra por tamanho

2. **Extração estruturada** (`1-extract-loop.qmd`):
   - Configura modelos LLM
   - Executa extração em lote
   - Salva resultados

3. **Exploração** (`2-explore.qmd`):
   - Analisa resultados
   - Gera visualizações
   - Calcula métricas de performance

### 4. Modelos disponíveis

O sistema suporta múltiplos provedores:

- **OpenAI**: GPT-4.1, GPT-4.1-mini, GPT-4.1-nano
- **Google**: Gemini 2.5 Pro, Gemini 2.5 Flash  
- **Groq**: Llama 4, GPT OSS, Kimi K2

Configure as chaves de API correspondentes no arquivo `.env`.

## 🔍 Exemplo de uso rápido

```python
from structured_trts.extract import extract_with_chatlas, load_prompt

# Carregar prompt
prompt = load_prompt("prompts/prompt.md")

# Extrair dados de um texto
text = "Sua sentença trabalhista aqui..."
result = extract_with_chatlas(text, prompt, "gpt-4.1-mini")

if result.success:
    print("Extração bem-sucedida!")
    print(result.extracted_data)
else:
    print(f"Erro: {result.error_message}")
```

## 🛠️ Comandos úteis com uv

```bash
# Sincronizar dependências
uv sync

# Adicionar nova dependência
uv add nome-do-pacote

# Remover dependência
uv remove nome-do-pacote

# Executar script no ambiente
uv run python script.py

# Atualizar dependências
uv sync --upgrade

# Verificar dependências desatualizadas
uv tree --outdated
```

## 🐛 Troubleshooting

### Problema: Erro de importação de módulos

**Solução**: Certifique-se de que o ambiente virtual está ativo e execute `uv sync`

### Problema: Chaves de API não encontradas

**Solução**: Verifique se o arquivo `.env` está na raiz do projeto e contém as chaves corretas

### Problema: Jupyter não encontra o kernel

**Solução**:

```bash
uv run python -m ipykernel install --user --name structured_trts
```

### Problema: Erro de tokens/contexto muito grande

**Solução**: Ajuste o parâmetro `max_tokens` nas funções de extração ou use textos menores

## 📝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença [especificar licença].

## 🤝 Suporte

Para dúvidas ou problemas:

1. Verifique a seção de troubleshooting acima
2. Abra uma issue no repositório
3. Consulte a documentação dos provedores de LLM para problemas de API
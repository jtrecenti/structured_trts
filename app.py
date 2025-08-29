from shiny import App, ui, render, reactive
import pandas as pd
import psycopg2
import psycopg2.extras
import os
from pathlib import Path
import json
import re
import logging
from datetime import datetime
from dotenv import load_dotenv
from src.structured_trts.extract import MODEL_CONFIGS

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global variables
DATA_DIR = Path("data")
EXTRACTED_DIR = DATA_DIR / "extracted"
NEON_DB_URL = os.getenv("NEON_DB")
TEXTOS_FILE = DATA_DIR / "textos_completo.parquet"

def get_db_connection():
    """Get a connection to the NeonDB PostgreSQL database."""
    if not NEON_DB_URL:
        raise ValueError("NEON_DB environment variable not set")
    return psycopg2.connect(NEON_DB_URL)

# Initialize validation database
def parse_input_text(text):
    """Parse the input text to extract metadata and separate files."""
    logger.info("Starting text parsing")
    if not text:
        logger.warning("No text provided for parsing")
        return None, []
    
    # Extract metadata section
    metadata_match = re.search(r'<metadados>(.*?)</metadados>', text, re.DOTALL)
    textos_match = re.search(r'<textos>(.*?)</textos>', text, re.DOTALL)
    
    metadata_content = None
    files_list = []
    
    if metadata_match:
        metadata_raw = metadata_match.group(1).strip()
        logger.info(f"Found metadata section with {len(metadata_raw)} characters")
        try:
            # Try to parse and format JSON
            metadata_json = json.loads(metadata_raw)
            metadata_content = json.dumps(metadata_json, indent=2, ensure_ascii=False)
            logger.info("Successfully parsed metadata JSON")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse metadata as JSON: {e}")
            metadata_content = metadata_raw
    else:
        logger.warning("No metadata section found")
    
    if textos_match:
        textos_content = textos_match.group(1).strip()
        # Split by file separators
        files = re.split(r'# Arquivo ([^\n]+\.txt) --+', textos_content)
        
        if len(files) > 1:
            logger.info(f"Found {(len(files)-1)//2} files using standard pattern")
            for i in range(1, len(files), 2):
                if i + 1 < len(files):
                    filename = files[i]
                    content = files[i + 1].strip()
                    logger.info(f"Extracted file: {filename} ({len(content)} chars)")
                    files_list.append({"filename": filename, "content": content})
        else:
            # If no file separators found, try to split by common patterns or treat as single file
            # Look for potential file patterns in the content
            potential_files = re.split(r'\n(?=\w+\.txt|\d+\.txt|arquivo)', textos_content, flags=re.IGNORECASE)
            if len(potential_files) > 1:
                for i, file_content in enumerate(potential_files):
                    if file_content.strip():
                        # Try to extract filename from content
                        first_line = file_content.split('\n')[0].strip()
                        if '.txt' in first_line.lower():
                            filename = first_line
                            content = '\n'.join(file_content.split('\n')[1:]).strip()
                        else:
                            filename = f"Arquivo {i+1}"
                            content = file_content.strip()
                        files_list.append({"filename": filename, "content": content})
            else:
                logger.info("No file patterns found, treating as single document")
                files_list.append({"filename": "Documento Principal", "content": textos_content})
    else:
        logger.warning("No textos section found")
    
    logger.info(f"Parsing completed: {len(files_list)} files extracted")
    return metadata_content, files_list

def init_validation_db():
    """Initialize the validation database if it doesn't exist."""
    logger.info("Initializing validation database on NeonDB")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validations (
                id SERIAL PRIMARY KEY,
                processo VARCHAR(255),
                model_name VARCHAR(255),
                gratuidade_correct VARCHAR(50),  -- sim/não/não aplicável
                decision_type_correct VARCHAR(50),  -- sim/não/não aplicável
                custas_correct VARCHAR(50),  -- sim/não
                claims_list_correct VARCHAR(50),  -- sim/não
                claim_outcomes TEXT,  -- JSON with individual claim validations
                claim_values TEXT,  -- JSON with individual value validations
                claim_relevance TEXT,  -- JSON with individual claim relevance
                valor_total_decisao_correct VARCHAR(50),  -- sim/não/não aplicável
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info("Validation database schema created successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def get_extracted_files():
    """Get list of extracted parquet files."""
    logger.info(f"Looking for extracted files in {EXTRACTED_DIR}")
    if not EXTRACTED_DIR.exists():
        logger.warning(f"Extracted directory {EXTRACTED_DIR} doesn't exist")
        return []
    files = [f.stem for f in EXTRACTED_DIR.glob("*.parquet")]
    logger.info(f"Found {len(files)} extracted files")
    return files

def load_extracted_data(filename, model_name=None):
    """Load extracted data from parquet file."""
    file_path = EXTRACTED_DIR / f"{filename}.parquet"
    logger.info(f"Loading extracted data from {file_path} for model {model_name}")
    if not file_path.exists():
        logger.error(f"File {file_path} doesn't exist")
        return pd.DataFrame()
    
    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Loaded {len(df)} rows from {filename}")
        if model_name:
            df_filtered = df[df['model_name'] == model_name]
            logger.info(f"Filtered to {len(df_filtered)} rows for model {model_name}")
            return df_filtered
        return df
    except Exception as e:
        logger.error(f"Error loading parquet file {file_path}: {e}")
        return pd.DataFrame()

def load_textos_data():
    """Load the complete texts data."""
    logger.info(f"Loading textos data from {TEXTOS_FILE}")
    if not TEXTOS_FILE.exists():
        logger.error(f"Textos file {TEXTOS_FILE} doesn't exist")
        return pd.DataFrame()
    try:
        df = pd.read_parquet(TEXTOS_FILE)
        logger.info(f"Loaded {len(df)} text records")
        return df
    except Exception as e:
        logger.error(f"Error loading textos file: {e}")
        return pd.DataFrame()

def get_validated_cases(model_name):
    """Get set of processo numbers that have been validated for a given model."""
    logger.info(f"Getting validated cases for model: {model_name}")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT processo 
            FROM validations 
            WHERE model_name = %s
        """, (model_name,))
        
        result = cursor.fetchall()
        validated_set = {row[0] for row in result}
        logger.info(f"Found {len(validated_set)} validated cases for model {model_name}")
        return validated_set
    except Exception as e:
        logger.error(f"Error querying validated cases: {e}")
        return set()
    finally:
        cursor.close()
        conn.close()

def is_case_validated(processo, model_name):
    """Check if a specific processo-model combination has been validated."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM validations 
            WHERE processo = %s AND model_name = %s
        """, (processo, model_name))
        
        result = cursor.fetchone()
        return result[0] > 0
    except Exception as e:
        logger.error(f"Error checking if case is validated: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def save_validation(validation_data):
    """Save validation data to database."""
    logger.info(f"Saving validation for processo {validation_data.get('processo')} and model {validation_data.get('model_name')}")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Convert claim validations to JSON
        claim_outcomes_json = json.dumps(validation_data.get('claim_outcomes', {}))
        claim_values_json = json.dumps(validation_data.get('claim_values', {}))
        claim_relevance_json = json.dumps(validation_data.get('claim_relevance', {}))
        
        cursor.execute("""
            INSERT INTO validations (
                processo, model_name, gratuidade_correct, decision_type_correct,
                custas_correct, claims_list_correct, claim_outcomes, claim_values, 
                claim_relevance, valor_total_decisao_correct
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            validation_data['processo'],
            validation_data['model_name'],
            validation_data['gratuidade_correct'],
            validation_data['decision_type_correct'],
            validation_data['custas_correct'],
            validation_data['claims_list_correct'],
            claim_outcomes_json,
            claim_values_json,
            claim_relevance_json,
            validation_data['valor_total_decisao_correct']
        ))
        
        conn.commit()
        logger.info("Validation data saved successfully")
        
    except Exception as e:
        logger.error(f"Error saving validation: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

# Initialize database
logger.info("Starting Shiny app initialization")
init_validation_db()

# UI Definition
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h3("Configurações"),
        ui.input_select(
            "process_selector",
            "Selecionar Processo:",
            choices={},
            selected=None
        ),
        ui.input_select(
            "model_selector",
            "Selecionar Modelo:",
            choices={key: config.name for key, config in MODEL_CONFIGS.items()},
            selected=list(MODEL_CONFIGS.keys())[0]
        ),
        ui.input_checkbox(
            "include_annotated",
            "Incluir casos já anotados?",
            value=False
        ),
        ui.br(),
        ui.output_text("status_text")
    ),
    
    ui.h2("Validação Manual de Extrações"),
    
    # Main content area
    ui.div(
        ui.row(
            ui.column(
                6,
                ui.h4("Texto de Entrada"),
                ui.div(
                    ui.output_ui("input_text"),
                    style="height: 400px; overflow-y: auto;"
                )
            ),
            ui.column(
                6,
                ui.h4("Saída do Modelo"),
                ui.div(
                    ui.output_ui("model_output"),
                    style="height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; background-color: #f0f8ff;"
                )
            )
        ),
        
        ui.br(),
        ui.hr(),
        
        # Validation fields
        ui.div(
            ui.h4("Campos de Validação"),
            ui.row(
                ui.column(
                    2,
                    ui.input_select(
                        "gratuidade_validation",
                        "Decisão de gratuidade está correta?",
                        choices={"sim": "Sim", "nao": "Não", "na": "Não aplicável"},
                        selected="sim"
                    )
                ),
                ui.column(
                    2,
                    ui.input_select(
                        "decision_type_validation",
                        "O tipo de decisão do modelo está correto?",
                        choices={"sim": "Sim", "nao": "Não", "na": "Não aplicável"},
                        selected="sim"
                    )
                ),
                ui.column(
                    2,
                    ui.input_select(
                        "custas_validation",
                        "Custas processuais estão corretas?",
                        choices={"sim": "Sim", "nao": "Não", "na": "Não aplicável"},
                        selected="sim"
                    )
                ),
                ui.column(
                    2,
                    ui.input_select(
                        "claims_list_validation",
                        "A lista de assuntos apresentada está correta?",
                        choices={"sim": "Sim", "nao": "Não"},
                        selected="sim"
                    )
                ),
                ui.column(
                    2,
                    ui.input_select(
                        "valor_total_decisao_validation",
                        "Valor total da decisão está correto?",
                        choices={"sim": "Sim", "nao": "Não", "na": "Não aplicável"},
                        selected="sim"
                    )
                )
            ),
            
            ui.br(),
            
            # Dynamic claim validations
            ui.div(
                ui.output_ui("claim_validations")
            ),
            
            ui.br(),
            
            ui.input_action_button(
                "save_validation",
                "Salvar Validação",
                class_="btn-primary btn-lg"
            ),
            
            ui.br(),
            ui.output_text("save_status")
        )
    )
)

# Server Logic
def server(input, output, session):
    
    # Reactive values
    current_data = reactive.Value(None)
    current_text = reactive.Value("")
    is_already_validated = reactive.Value(False)
    
    @reactive.effect
    def update_process_choices():
        """Update process selector based on available files and model selection."""
        logger.info("Updating process choices")
        files = get_extracted_files()
        choices = {f: f for f in files}
        logger.info("Setting process choices.")
        ui.update_select("process_selector", choices=choices)
    
    @reactive.effect
    def load_current_data():
        """Load data when process or model selection changes."""
        logger.info("Loading current data")
        if not input.process_selector():
            logger.info("No process selected, skipping data load")
            current_data.set(None)
            current_text.set("")
            is_already_validated.set(False)
            return
            
        model_name = MODEL_CONFIGS[input.model_selector()].name
        logger.info(f"Loading data for process: {input.process_selector()}, model: {model_name}")
        df = load_extracted_data(input.process_selector(), model_name)
        
        if not df.empty:
            logger.info(f"Loaded {len(df)} records from extracted data")
            
            # Get first case (could be validated or not)
            selected_case = df.iloc[0]
            processo_num = selected_case['processo']
            
            # Check if this specific case is already validated
            case_validated = is_case_validated(processo_num, model_name)
            logger.info(f"Case {processo_num} validation status: {case_validated}")
            
            # If case is validated and user doesn't want to include annotated cases
            if case_validated and not input.include_annotated():
                logger.info(f"Case {processo_num} already validated and include_annotated is False")
                is_already_validated.set(True)
                current_data.set(selected_case)  # Still set data for processo info
                current_text.set("Caso já anotado para este modelo")
                return
            
            # Normal case - either not validated or user wants to include annotated
            is_already_validated.set(False)
            logger.info(f"Selected case: processo {processo_num}")
            current_data.set(selected_case)
            
            # Load corresponding text
            textos_df = load_textos_data()
            if not textos_df.empty:
                logger.info(f"Looking for text for processo {processo_num}")
                text_row = textos_df[textos_df['processo'] == processo_num]
                if not text_row.empty:
                    logger.info(f"Found text with {len(text_row.iloc[0]['txt_sentencas'])} characters")
                    current_text.set(text_row.iloc[0]['txt_sentencas'])
                else:
                    logger.warning(f"No text found for processo {processo_num}")
                    current_text.set("Texto não encontrado para este processo")
            else:
                logger.warning("No textos data available")
                current_text.set("Dados de texto não disponíveis")
        else:
            logger.info("No data available for selected process/model")
            current_data.set(None)
            current_text.set("Nenhum dado disponível")
            is_already_validated.set(False)
    
    @output
    @render.text
    def status_text():
        data = current_data.get()
        if data is not None:
            return f"Processo: {data['processo']} | Modelo: {data['model_name']}"
        return "Nenhum processo selecionado"
    
    @output
    @render.ui
    def input_text():
        # Check if case is already validated
        if is_already_validated.get():
            return ui.div(
                ui.h5("⚠️ Caso já anotado para este modelo", style="color: orange; text-align: center; margin: 50px 0;"),
                ui.p("Este processo já foi validado para o modelo selecionado. Para visualizar e editar a validação, marque a opção 'Incluir casos já anotados'.", 
                     style="text-align: center; color: #666;")
            )
        
        raw_text = current_text.get()
        metadata_content, files_list = parse_input_text(raw_text)
        
        accordion_items = []
        
        # Add metadata accordion item
        if metadata_content:
            accordion_items.append(
                ui.accordion_panel(
                    "📋 Metadados",
                    ui.pre(metadata_content, style="font-size: 11px; line-height: 1.3; margin: 0; white-space: pre-wrap;")
                )
            )
        
        # Add file accordion items
        for file_info in files_list:
            accordion_items.append(
                ui.accordion_panel(
                    f"📄 {file_info['filename']}",
                    ui.pre(file_info['content'], style="font-size: 11px; line-height: 1.3; margin: 0; white-space: pre-wrap;")
                )
            )
        
        if not accordion_items:
            return ui.p("Nenhum conteúdo disponível")
        
        return ui.accordion(*accordion_items, id="input_accordion", open=False)
    
    @output
    @render.ui
    def model_output():
        # Check if case is already validated
        if is_already_validated.get():
            return ui.div(
                ui.h5("⚠️ Caso já anotado para este modelo", style="color: orange; text-align: center; margin: 50px 0;"),
                ui.p("Este processo já foi validado para o modelo selecionado. Para visualizar e editar a validação, marque a opção 'Incluir casos já anotados'.", 
                     style="text-align: center; color: #666;")
            )
        
        data = current_data.get()
        if data is None:
            return ui.p("Nenhum dado carregado")
        
        if not data.get('success', False):
            return ui.div(
                ui.h5("❌ Modelo falhou", style="color: red;"),
                ui.p(f"Erro: {data.get('error_message', 'Erro desconhecido')}")
            )
        
        extracted = data.get('extracted_data')
        if not extracted:
            return ui.p("Nenhum dado extraído")
        
        # Format the extracted data nicely
        content = []
        
        # Decision type
        if 'decision_type' in extracted:
            content.append(ui.p(ui.strong("Tipo de Decisão: "), extracted['decision_type']))
        
        # Gratuidade
        if 'gratuidade' in extracted:
            content.append(ui.p(ui.strong("Gratuidade: "), str(extracted['gratuidade'])))
        
        # Custas
        if 'custas' in extracted:
            custas = extracted['custas']
            if custas:
                content.append(ui.p(ui.strong("Custas: "), f"R$ {custas.get('amount', 0):.2f}"))
        
        # Valor total da decisão
        if 'valor_total_decisao' in extracted:
            valor_total = extracted['valor_total_decisao']
            if valor_total:
                content.append(ui.p(ui.strong("Valor Total da Decisão: "), f"R$ {valor_total.get('amount', 0):.2f}"))
        
        # Claims
        if 'claims' in extracted and len(extracted.get('claims', [])) > 0:
            content.append(ui.h5("Pedidos:"))
            for i, claim in enumerate(extracted['claims']):
                content.append(ui.div(
                    ui.p(ui.strong(f"Pedido {i+1}: "), claim.get('claim_type', 'N/A')),
                    ui.p(ui.strong("Resultado: "), claim.get('outcome', 'N/A')),
                    ui.p(ui.strong("Valor Recebido: "), 
                         f"R$ {claim['valor_recebido']['amount']:.2f}" if claim.get('valor_recebido') else "N/A"),
                    ui.p(ui.strong("Reflexos: "), claim.get('reflexos', 'N/A')),
                    style="margin-left: 20px; border-left: 3px solid #007bff; padding-left: 10px; margin-bottom: 10px;"
                ))
        
        return ui.div(*content)
    
    @output
    @render.ui
    def claim_validations():
        data = current_data.get()
        if data is None or not data.get('success', False):
            return ui.div()
        
        extracted = data.get('extracted_data', {})
        claims = extracted.get('claims', [])
        
        if len(claims) == 0:
            return ui.div()
        
        content = [ui.h5("Validação por Pedido:")]
        
        for i, claim in enumerate(claims):
            claim_type = claim.get('claim_type', f'Pedido {i+1}')
            
            content.extend([
                ui.h6(f"{claim_type}"),
                ui.row(
                    ui.column(
                        4,
                        ui.input_select(
                            f"claim_relevance_{i}",
                            "O caso envolve esse assunto?",
                            choices={"sim": "Sim", "nao": "Não"},
                            selected="sim"
                        )
                    ),
                    ui.column(
                        4,
                        ui.input_select(
                            f"claim_outcome_{i}",
                            "Decisão está correta?",
                            choices={"sim": "Sim", "nao": "Não", "na": "Não aplicável"},
                            selected="na"
                        )
                    ),
                    ui.column(
                        4,
                        ui.input_select(
                            f"claim_value_{i}",
                            "Valor de indenização está correto?",
                            choices={"sim": "Sim", "nao": "Não", "na": "Não aplicável"},
                            selected="sim" if claim.get('valor_recebido') else "na"
                        )
                    )
                ),
                ui.br()
            ])
        
        return ui.div(*content)
    
    @reactive.effect
    @reactive.event(input.save_validation)
    def save_validation_data():
        """Save the validation data to database."""
        logger.info("Save validation button clicked")
        data = current_data.get()
        if data is None:
            logger.warning("No current data to save")
            return
        
        # Collect claim validations
        extracted = data.get('extracted_data', {})
        claims = extracted.get('claims', [])
        logger.info(f"Processing {len(claims)} claims for validation")
        
        claim_outcomes = {}
        claim_values = {}
        claim_relevance = {}
        
        for i in range(len(claims)):
            relevance_input = f"claim_relevance_{i}"
            outcome_input = f"claim_outcome_{i}"
            value_input = f"claim_value_{i}"
            
            if hasattr(input, relevance_input):
                claim_relevance[i] = getattr(input, relevance_input)()
            if hasattr(input, outcome_input):
                claim_outcomes[i] = getattr(input, outcome_input)()
            if hasattr(input, value_input):
                claim_values[i] = getattr(input, value_input)()
        
        validation_data = {
            'processo': data['processo'],
            'model_name': data['model_name'],
            'gratuidade_correct': input.gratuidade_validation(),
            'decision_type_correct': input.decision_type_validation(),
            'custas_correct': input.custas_validation(),
            'claims_list_correct': input.claims_list_validation(),
            'valor_total_decisao_correct': input.valor_total_decisao_validation(),
            'claim_outcomes': claim_outcomes,
            'claim_values': claim_values,
            'claim_relevance': claim_relevance
        }
        
        try:
            save_validation(validation_data)
            m = ui.modal(
                "Validação salva com sucesso!",
                title="Sucesso",
                easy_close=True,
                footer=None
            )
            ui.modal_show(m)
            logger.info("Validation saved successfully, moving to next case")
        except Exception as e:
            logger.error(f"Error saving validation: {e}")
            print(f"Error saving validation: {e}")
    
    @output
    @render.text
    def save_status():
        return ""

# Create the app
app = App(app_ui, server)

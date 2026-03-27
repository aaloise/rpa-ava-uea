import asyncio
import re
import os
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout, expect

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações globais
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

NOME_PLANILHA = "BASE-AVA-UEA"


def setup_google_sheets():
    """Configura e retorna o objeto da aba 'Salas' do Google Sheets"""
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
    cliente = gspread.authorize(creds)
    planilha = cliente.open(NOME_PLANILHA)
    return planilha.worksheet("Salas")

def gerar_shortname(nome_disciplina):
    """
    Gera um shortname único baseado no nome da disciplina.
    Exemplo: "Cálculo Diferencial e Integral I" -> "CALC-DIF-INT-I"
    """
    # Remove acentos e caracteres especiais
    shortname = nome_disciplina.upper()
    shortname = re.sub(r'[ÀÁÂÃÄÅ]', 'A', shortname)
    shortname = re.sub(r'[ÈÉÊË]', 'E', shortname)
    shortname = re.sub(r'[ÌÍÎÏ]', 'I', shortname)
    shortname = re.sub(r'[ÒÓÔÕÖ]', 'O', shortname)
    shortname = re.sub(r'[ÙÚÛÜ]', 'U', shortname)
    shortname = re.sub(r'[Ç]', 'C', shortname)
    
    # Remove caracteres não alfanuméricos e substitui por hífen
    shortname = re.sub(r'[^A-Z0-9\s]', '', shortname)
    shortname = re.sub(r'\s+', '-', shortname)
    
    # Limita a 100 caracteres (limite do Moodle)
    return shortname[:100].strip('-')


def calcular_num_secoes(carga_horaria):
    """
    Calcula número de seções baseado na carga horária.
    15h = 1 seção, 30h = 2 seções, 60h = 4 seções, etc.
    """
    try:
        ch = int(carga_horaria)
        return max(1, ch // 15)  # Pelo menos 1 seção
    except (ValueError, TypeError):
        return 1  # Default: 1 seção

async def acessar_pagina_inicial(page):
    """Navega para a página inicial do AVA e retorna a página de login"""
    print("Acessando o AVA da UEA...")
    await page.goto("https://avauea.uea.edu.br", wait_until="domcontentloaded", timeout=30000)
    
    login_link = page.locator('a[href*="avauea.uea.edu.br/login"]').filter(has_text="Login manual")
    await login_link.wait_for(state="visible", timeout=10000)
    await login_link.click()
    
    await page.wait_for_load_state("networkidle", timeout=20000)
    return page


async def login_ava(page, username, password):
    """Realiza o login no AVA com as credenciais fornecidas"""
    print("Preenchendo credenciais...")
    
    if not username or not password:
        raise ValueError("Credenciais não definidas. Verifique o arquivo .env")
    
    await page.get_by_placeholder("Identificação / email").fill(username)
    await page.locator("#password").fill(password)
    await page.locator("#loginbtn").click()
    
    await page.wait_for_load_state("networkidle", timeout=30000)
    
    if await page.locator("#username").is_visible():
        raise Exception("Falha no login: ainda na tela de autenticação")
    
    print("Login efetuado com sucesso!")
    return page


async def navegar_para_categoria(page, category_id):
    """Navega para a página de uma categoria específica de cursos"""
    print(f"Navegando para categoria de curso ID: {category_id}...")
    
    url = f"https://avauea.uea.edu.br/course/index.php?categoryid={category_id}"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_load_state("networkidle", timeout=20000)
    
    return page


async def clicar_botao_adicionar_curso(page):
    """Localiza e clica no botão 'Adicionar um novo curso/disciplina'"""
    print("Localizando botão para adicionar nova disciplina...")
    
    # Seleção pelo texto visível e role semântico
    botao_adicionar = page.get_by_role("button", name="Adicionar um novo curso/disciplina")
    
    # Usa expect para aguardar visibilidade e estado habilitado
    await expect(botao_adicionar).to_be_visible(timeout=15000)
    await expect(botao_adicionar).to_be_enabled(timeout=5000)
    
    print("Clicando no botão para adicionar nova disciplina...")
    await botao_adicionar.click()
    
    return page


async def aguardar_formulario_disciplina(page, timeout=30000):
    """Aguarda o formulário de nova disciplina estar pronto para preenchimento"""
    print("Aguardando carregamento do formulário de nova disciplina...")
    
    await page.wait_for_load_state("networkidle", timeout=timeout)
    await page.wait_for_selector("input[name='shortname'], #id_shortname", timeout=10000)
    
    print("Formulário de nova disciplina carregado com sucesso!")
    return page


async def preencher_formulario_disciplina(page, nome_disciplina, carga_horaria):
    """
    Preenche o formulário de nova disciplina com os dados fornecidos.
    
    Args:
        page: objeto page do Playwright
        nome_disciplina: nome completo da disciplina (fullname)
        carga_horaria: carga horária em horas (para cálculo de seções)
    """
    shortname = gerar_shortname(nome_disciplina)
    num_secoes = calcular_num_secoes(carga_horaria)
    
    print(f"  - Shortname: {shortname}")
    print(f"  - Carga Horária: {carga_horaria}h")
    print(f"  - Número de seções: {num_secoes}")
    
    # Preenche shortname
    try:
        await page.locator("#id_shortname").fill(shortname)
    except Exception as e:
        print(f"  Erro ao preencher shortname: {e}")
    
    # Preenche fullname (nome completo da disciplina)
    try:
        await page.locator("#id_fullname").fill(nome_disciplina)
    except Exception as e:
        print(f"  Erro ao preencher fullname: {e}")
    
    # Preenche resumo/descrição (opcional)
    try:
        summary = f"Disciplina: {nome_disciplina}\nCarga Horária: {carga_horaria}h"
        await page.locator("#id_summary_editoreditable").fill(summary)
    except Exception as e:
        print(f"  Erro ao preencher resumo: {e}")
    
    # Seleciona o formato do curso: "Formato de curso com botões"
    try:
        print("  Clicando na opção de formato do curso...")
        botao_expandir = page.locator("fieldset#id_courseformathdr legend a.fheader").first
        await botao_expandir.click()
        print("  Seção 'Formato de curso' expandida!")

        print("  Selecionando formato do curso...")
        formato_select = page.locator("#id_format")
        await formato_select.wait_for(state="attached", timeout=10000)
        
        await formato_select.select_option(label="Formato de curso com botões", timeout=10000)
        print("  Formato 'Curso com botões' selecionado!")
    except Exception as e:
        print(f"  Erro ao selecionar formato do curso: {e}")
        # Tenta alternativa: selecionar pelo valor ou texto
        try:
            await page.locator("select[name='format']").select_option("format_buttons")
        except:
            print("  Usando formato padrão do sistema")

    # Define número de seções - USANDO .first() PARA EVITAR DUPLICATA
    try:
        # Aguarda o campo estar visível
        campo_secoes = page.locator("#id_numsections").first
        await campo_secoes.wait_for(state="visible", timeout=5000)
        
        # Garante que o valor é string
        valor_secoes = str(num_secoes)
        await campo_secoes.select_option(label={valor_secoes}, timeout=10000)
        print(f"  Número de seções definido: {num_secoes}")
        
    except Exception as e:
        print(f"  Erro ao definir número de seções: {e}")
        # Tenta alternativa: campo pode ser um select
        try:
            await page.locator("select[name='numsections']").first.select_option(str(num_secoes))
            print(f"  Número de seções definido via select: {num_secoes}")
        except Exception as e2:
            print(f"  Erro na alternativa: {e2}")
    
    return page

async def salvar_disciplina(page):
    """Clica no botão de salvar e aguarda confirmação"""
    print("Salvando disciplina...")
    
    # Tenta encontrar o botão de salvar (pode ter diferentes seletores no Moodle)
    botoes_salvar = [
        page.locator("#id_saveanddisplay"),
        page.locator("button[type='submit'][name='save']"),
        page.get_by_role("button", name="Salvar e mostrar")
    ]
    
    botao_encontrado = None
    for botao in botoes_salvar:
        if await botao.is_visible(timeout=10000):
            botao_encontrado = botao
            break
    
    if botao_encontrado:
        await botao_encontrado.click()
        await page.wait_for_load_state("networkidle", timeout=30000)
        print("Disciplina salva com sucesso!")
        return True
    else:
        print("Botão de salvar não encontrado!")
        return False

async def atualizar_status_planilha(aba_salas, linha, url_da_sala_criada, status):
    """
    Atualiza o status da disciplina na planilha Google Sheets.
    
    Args:
        aba_salas: objeto da worksheet
        linha: número da linha (1-indexed, considerando cabeçalho)
        url_da_sala_criada: URL da sala de aula criada
        status: novo status ("Criada", "Erro", etc.)
    """
    try:
        # Coluna D é Status_Sala (coluna 4)
        await asyncio.to_thread(aba_salas.update_cell, linha + 1, 4, status)
        print(f"  Status atualizado na planilha: {status}")
    except Exception as e:
        print(f"  Erro ao atualizar planilha: {e}")
    
    try:
        # Atualiza a aba Salas. O número 6 representa a Coluna F.
        await asyncio.to_thread(aba_salas.update_cell, linha + 1, 6, url_da_sala_criada)
        print(f"  URL da sala atualizada na planilha: {url_da_sala_criada}")
    except Exception as e:
        print(f"  Erro ao atualizar URL na planilha: {e}")
    

async def processar_disciplina(page, aba_salas, registro, indice, total):
    """
    Processa uma única disciplina: navega, preenche formulário e salva.
    
    Args:
        page: objeto page do Playwright
        aba_salas: objeto da worksheet Google Sheets
        registro: dict com dados da disciplina (Nome_Disciplina, CH, Status_Sala)
        indice: índice atual (para logging)
        total: total de disciplinas (para logging)
    """
    nome_disciplina = registro.get("Nome_Disciplina", "")
    carga_horaria = registro.get("CH", "0")
    status_atual = registro.get("Status_Sala", "Pendente")
    
    print(f"\n[{indice}/{total}] Processando: {nome_disciplina}")
    print(f"  Status atual: {status_atual}")
    
    # Pula se já foi processada
    if status_atual == "Criada":
        print("  Já foi criada, pulando...")
        return True
    
    try:
        # Navega para categoria de cursos
        page = await navegar_para_categoria(page, category_id=361)
        
        # Clica no botão para adicionar curso
        page = await clicar_botao_adicionar_curso(page)
        
        # Aguarda formulário carregar
        page = await aguardar_formulario_disciplina(page)
        
        # Preenche o formulário
        await preencher_formulario_disciplina(page, nome_disciplina, carga_horaria)
        
        # Salva a disciplina
        sucesso = await salvar_disciplina(page)
        url_limpa = page.url.split("&")[0]  # Remove parâmetros da URL
        
        if sucesso:
            # Atualiza status na planilha
            await atualizar_status_planilha(aba_salas, indice, url_limpa, "Criada")
            return True
        else:
            await atualizar_status_planilha(aba_salas, indice, url_limpa, "Erro ao salvar")
            return False
            
    except Exception as e:
        print(f"  Erro ao processar disciplina: {type(e).__name__} - {e}")
        await atualizar_status_planilha(aba_salas, indice, url_limpa, "Erro")
        await page.screenshot(path=f"erro_disciplina_{indice}.png")
        return False

async def executar_bot_arquiteto():
    """Função principal que orquestra todo o fluxo do bot"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Configura planilha
            aba_salas = await asyncio.to_thread(setup_google_sheets)
            
            # Carrega credenciais
            username = os.getenv("AVA_USERNAME")
            password = os.getenv("AVA_PASSWORD")
            
            # Login
            page = await acessar_pagina_inicial(page)
            page = await login_ava(page, username, password)
            
            # Carrega registros da planilha
            print("\nCarregando dados da planilha...")
            registos = await asyncio.to_thread(aba_salas.get_all_records)
            print(f"{len(registos)} disciplinas encontradas.\n")
            
            # Filtra apenas disciplinas pendentes (opcional)
            # registos = [r for r in registos if r.get("Status_Sala") == "Pendente"]
            
            # Processa cada disciplina
            total = len(registos)
            sucesso = 0
            falhas = 0
            
            for i, registro in enumerate(registos, start=1):
                resultado = await processar_disciplina(page, aba_salas, registro, i, total)
                if resultado:
                    sucesso += 1
                else:
                    falhas += 1
                
                # Pequena pausa entre disciplinas para evitar sobrecarga
                await asyncio.sleep(2)
            
            # Resumo final
            print("\n" + "="*60)
            print("RESUMO DA EXECUÇÃO")
            print("="*60)
            print(f"Total processado: {total}")
            print(f"Sucessos: {sucesso}")
            print(f"Falhas: {falhas}")
            print("="*60)
            
        except PlaywrightTimeout as e:
            print(f"Timeout: elemento não encontrado ou página lenta. Detalhes: {e}")
            await page.screenshot(path="erro_timeout.png")
        except ValueError as e:
            print(f"Erro de configuração: {e}")
        except Exception as e:
            print(f"Erro inesperado: {type(e).__name__} - {e}")
            await page.screenshot(path="erro_debug.png")
        finally:
            await browser.close()
            print("\nNavegador fechado.")


if __name__ == "__main__":
    asyncio.run(executar_bot_arquiteto())
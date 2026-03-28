import asyncio
import os
import time
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
    """Configura e retorna o objeto da aba 'Alunos' do Google Sheets"""
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
    cliente = gspread.authorize(creds)
    planilha = cliente.open(NOME_PLANILHA)
    return planilha.worksheet("Alunos")

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

async def atualizar_status_planilha(aba_alunos, linha, status):
    """
    Atualiza o status da matrícula na planilha Google Sheets.
    
    Args:
        aba_alunos: objeto da worksheet
        linha: número da linha (1-indexed, considerando cabeçalho)
        status: novo status ("Matriculado", "Erro", etc.)
    """
    try:
        # Coluna C é Status_Matricula (coluna 3)
        await asyncio.to_thread(aba_alunos.update_cell, linha + 1, 3, status)
        print(f"  Status atualizado na planilha: {status}")
    except Exception as e:
        print(f"  Erro ao atualizar planilha: {e}")

async def matricular_usuario(page, email, perfil):
    """
    Executa os cliques na interface para matricular um usuário.
    Espera-se que o navegador já esteja na página de Participantes da disciplina.
    """
    try:
        # Clica em "Inscrever usuários"
        print("  Localizando botão de inscrição...")
        botao_inscrever = page.locator("input[type='submit'][value='Inscrever usuários']").first
        await expect(botao_inscrever).to_be_visible(timeout=10000)
        await botao_inscrever.click()

        # Preenche o e-mail na busca (espera o modal abrir)
        print(f"  Buscando email: {email}")
        campo_busca = page.locator("input[role='combobox'][placeholder='Buscar']").first
        await expect(campo_busca).to_be_visible(timeout=10000)
        await campo_busca.fill(email)
        #await page.keyboard.press("Enter")
        
        print("  Aguardando o usuário aparecer na lista suspensa...")
        usuario_resultado = page.locator(f"li[role='option']:has-text('{email}')")
        
        await expect(usuario_resultado).to_be_visible(timeout=5000)
        await usuario_resultado.click()

        # Seleciona o perfil (Papel)
        print(f"  Definindo papel como: {perfil}")
        select_papel = page.locator("select[name='roletoassign']")
        if perfil.lower() == "tutor":
            await select_papel.select_option(label="Moderador")
        else:
            await select_papel.select_option(label="Estudante")

        # Confirma a inscrição
        print("  Confirmando inscrição no modal...")
        botao_confirmar = page.locator("button[data-action='save']:visible")       
        await expect(botao_confirmar).to_be_visible(timeout=10000)
        
        print("  Iniciando navegação por Tab até o botão de salvar...")
        
        # Clica no campo de perfil apenas para garantir que o cursor/foco comece dali
        await select_papel.click()

        # Pressiona Tab até o foco chegar no botão (limite de 10 vezes para segurança)
        foco_encontrado = False
        for i in range(10):
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.3) # Pequena pausa entre cada Tab
            
            # Verifica se o elemento atualmente focado no navegador é o nosso botão
            is_focused = await botao_confirmar.evaluate("node => document.activeElement === node")
            
            if is_focused:
                print(f"  🎯 Botão focado após {i+1} Tabs! Disparando Enter...")
                await page.keyboard.press("Enter")
                foco_encontrado = True
                break
                
        if not foco_encontrado:
            print("  ⚠️ Aviso: Não conseguiu focar via Tab. Tentando clique nativo alternativo...")
            await botao_confirmar.dispatch_event("click")
        
        print("  Aguardando fechamento do modal...")
        await page.wait_for_load_state("networkidle", timeout=10000)
        return True
        
    except Exception as e:
        print(f"  Erro durante os cliques de matrícula: {e}")
        return False

async def processar_matricula(page, aba_alunos, registro, indice, total):
    """
    Processa um único aluno: navega para a sala e inscreve.
    """
    nome = registro.get("Nome", "")
    email = registro.get("Email", "")
    perfil = registro.get("Perfil", "Estudante")
    status_atual = registro.get("Status_Matricula", "Pendente")
    url_alvo = registro.get("URL_Sala", "")
    
    print(f"\n[{indice}/{total}] Processando: {nome} ({perfil})")
    print(f"  Status atual: {status_atual}")
    
    # Pula se já foi processado ou se a sala ainda não existe
    if status_atual == "Matriculado":
        print("  Já matriculado, pulando...")
        return True
    
    if not url_alvo:
        print("  URL da sala em branco (Disciplina não criada). Pulando...")
        return False
        
    try:
        # Navega direto para a página da sala usando a URL da planilha
        print(f"  Navegando para a sala...")
        await page.goto(url_alvo, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        
        # Executa a matrícula
        sucesso = await matricular_usuario(page, email, perfil)
        
        if sucesso:
            await atualizar_status_planilha(aba_alunos, indice, "Matriculado")
            print(f"  ✅ Matrícula de {nome} concluída com sucesso!")
            return True
        else:
            await atualizar_status_planilha(aba_alunos, indice, "Erro na Inscrição")
            return False
            
    except Exception as e:
        print(f"  Erro ao processar matrícula: {type(e).__name__} - {e}")
        await atualizar_status_planilha(aba_alunos, indice, "Erro")
        await page.screenshot(path=f"erro_matricula_{indice}.png")
        return False

async def executar_bot_gestor():
    """Função principal que orquestra todo o fluxo do bot"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Configura planilha
            aba_alunos = await asyncio.to_thread(setup_google_sheets)
            
            # Carrega credenciais
            username = os.getenv("AVA_USERNAME")
            password = os.getenv("AVA_PASSWORD")
            
            # Login
            page = await acessar_pagina_inicial(page)
            page = await login_ava(page, username, password)
            
            # Carrega registros da planilha
            print("\nCarregando dados da planilha...")
            registos = await asyncio.to_thread(aba_alunos.get_all_records)
            print(f"{len(registos)} alunos/tutores encontrados.\n")
            
            total = len(registos)
            sucesso = 0
            falhas = 0
            
            # Processa cada aluno
            for i, registro in enumerate(registos, start=1):
                resultado = await processar_matricula(page, aba_alunos, registro, i, total)
                if resultado:
                    sucesso += 1
                else:
                    falhas += 1
                
                # Pequena pausa didática e para evitar sobrecarga
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
            await page.screenshot(path="erro_timeout_matricula.png")
        except ValueError as e:
            print(f"Erro de configuração: {e}")
        except Exception as e:
            print(f"Erro inesperado: {type(e).__name__} - {e}")
            await page.screenshot(path="erro_debug_matricula.png")
        finally:
            await browser.close()
            print("\nNavegador fechado.")

if __name__ == "__main__":
    asyncio.run(executar_bot_gestor())

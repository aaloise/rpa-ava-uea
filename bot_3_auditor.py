import asyncio
import os
import aiohttp
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Carrega as variáveis do .env
load_dotenv()

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

NOME_PLANILHA = "BASE-AVA-UEA"

def setup_google_sheets():
    """Configura e retorna a planilha (gspread ainda é síncrono, então manteremos em thread)"""
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
    cliente = gspread.authorize(creds)
    return cliente.open(NOME_PLANILHA)

async def auditar_e_notificar():
    print("🔍 Iniciando auditoria dos dados no Google Sheets...")
    
    try:
        # 1. Conecta no Google Sheets (Em thread, pois a lib gspread é síncrona)
        planilha = await asyncio.to_thread(setup_google_sheets)

        # 2. Lê e calcula os dados das Salas
        print("  - Lendo aba de Salas...")
        aba_salas = await asyncio.to_thread(planilha.worksheet, "Salas")
        salas = await asyncio.to_thread(aba_salas.get_all_records)
        
        total_salas = len(salas)
        salas_criadas = sum(1 for s in salas if s.get("Status_Sala") == "Criada")
        salas_erro = sum(1 for s in salas if "Erro" in s.get("Status_Sala", ""))
        salas_pendentes = total_salas - salas_criadas - salas_erro

        # 3. Lê e calcula os dados dos Alunos
        print("  - Lendo aba de Alunos...")
        aba_alunos = await asyncio.to_thread(planilha.worksheet, "Alunos")
        alunos = await asyncio.to_thread(aba_alunos.get_all_records)
        
        total_alunos = len(alunos)
        alunos_matriculados = sum(1 for a in alunos if a.get("Status_Matricula") == "Matriculado")
        alunos_erro = sum(1 for a in alunos if "Erro" in a.get("Status_Matricula", ""))
        alunos_pendentes = total_alunos - alunos_matriculados - alunos_erro

        # 4. Formata a mensagem para o Telegram
        dashboard_url = os.getenv("LOOKER_STUDIO_URL", "https://lookerstudio.google.com/...")
        
        mensagem = (
            "🤖 *Relatório de Automação RPA - AVA UEA*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏫 *Módulo 1: Criação de Salas*\n"
            f"✅ Criadas: {salas_criadas}\n"
            f"⏳ Pendentes: {salas_pendentes}\n"
            f"❌ Erros: {salas_erro}\n\n"
            "👨‍🎓 *Módulo 2: Matrículas*\n"
            f"✅ Matriculados: {alunos_matriculados}\n"
            f"⏳ Pendentes: {alunos_pendentes}\n"
            f"❌ Erros: {alunos_erro}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 *Acompanhe no Dashboard (Looker Studio):*\n{dashboard_url}"
        )

        # 5. Envia a notificação NATIVAMENTE ASSÍNCRONA
        print("📲 Enviando notificação para o Telegram...")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not token or not chat_id:
            print("⚠️ Erro: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não encontrados no arquivo .env!")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "Markdown"
        }
        
        # Uso do aiohttp para a requisição de rede sem bloquear o loop
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resposta:
                if resposta.status == 200:
                    print("✅ Notificação enviada com sucesso para o seu celular!")
                else:
                    texto_erro = await resposta.text()
                    print(f"❌ Erro ao enviar notificação: {texto_erro}")
            
    except Exception as e:
        print(f"❌ Erro crítico durante a auditoria: {type(e).__name__} - {e}")

if __name__ == "__main__":
    asyncio.run(auditar_e_notificar())
# 🤖 RPA Educacional - Automação Moodle (AVA UEA)

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Async-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Google Sheets](https://img.shields.io/badge/Google_Sheets-API-34A853?style=for-the-badge&logo=google-sheets&logoColor=white)

Este projeto apresenta uma arquitetura completa de **Automação Robótica de Processos (RPA)** desenvolvida para otimizar a gestão do Ambiente Virtual de Aprendizagem (Moodle) da Universidade do Estado do Amazonas (UEA).

O sistema substitui o trabalho manual e repetitivo de criação de disciplinas e matrícula de usuários por um fluxo 100% automatizado, orquestrado via planilhas e monitorado em tempo real por painéis de BI e mensagens no celular.

---

## 🎯 Objetivos e Impacto
* **Redução de Tempo:** Tarefas que levariam horas de cliques manuais são executadas em minutos.
* **Zero Erro Humano:** A automação garante que os nomes das salas, cargas horárias e perfis de usuário (Estudante/Tutor) sejam aplicados com precisão cirúrgica.
* **Monitoramento Ativo:** Gestores não precisam abrir o sistema para saber se o trabalho foi feito; os relatórios vão ativamente até eles.

---

## 🏗️ Arquitetura e Fluxo de Dados

A solução foi dividida em três microsserviços (Bots) orquestrados de forma assíncrona:

1. **📥 Extração e Planejamento (Google Sheets):** A base de dados principal é uma planilha no Google Sheets (`BASE-AVA-UEA`), que serve como fila de processamento.
2. **⚙️ Bot 1 (Arquiteto de Salas):** Lê a aba "Salas", faz o login no AVA e utiliza automação web para criar as disciplinas e configurar a carga horária. Ao final, atualiza o status na planilha.
3. **👥 Bot 2 (Gestor de Matrículas):** Lê a aba "Alunos", navega até as disciplinas criadas, busca os usuários pelo e-mail e realiza a inscrição com os papéis corretos.
4. **📊 Looker Studio (Dashboard):** Conectado diretamente à planilha, gera painéis executivos visuais e dinâmicos para acompanhamento de Salas e Participantes.
5. **📲 Bot 3 (Auditor e Notificador):** Microsserviço que consolida os resultados e dispara um relatório via API do Telegram, contendo as métricas de sucesso/erro e o link direto para o Looker Studio.

---

## 🧠 Destaques Técnicos (Engineering Highlights)

Este projeto não é apenas um script linear, mas uma aplicação de engenharia de software resiliente:
* **Concorrência Assíncrona:** Utilização massiva de `asyncio` e bibliotecas não-bloqueantes (`aiohttp`). Operações de I/O bloqueantes (como a biblioteca `gspread`) foram isoladas utilizando `asyncio.to_thread`.
* **Bypass de Frameworks Legados (YUI):** O Moodle utiliza o framework JavaScript YUI, que frequentemente bloqueia cliques sintéticos do Playwright. Para contornar isso e garantir resiliência contra mudanças de layout, o Bot 2 implementa simulação de navegação humana por teclado (`Tab` dinâmico para focar elementos e `Enter` nativo).
* **Seletores Semânticos:** Uso de locators robustos (ARIA roles, placeholders e XPath estrutural) em vez de IDs dinâmicos, garantindo que o bot não quebre a cada atualização do Moodle.

---

## 📂 Estrutura do Repositório

```text
📦 desafio-bots
 ┣ 📜 bot_1_salas.py         # Script de criação de disciplinas
 ┣ 📜 bot_2_matriculas.py    # Script de inscrição de usuários
 ┣ 📜 bot_3_auditor.py       # Script de auditoria e notificação
 ┣ 🐳 Dockerfile             # Configuração da imagem do container
 ┣ 🐳 docker-compose.yml     # Orquestração dos serviços
 ┣ 📜 requirements.txt       # Dependências do Python
 ┗ 📜 .gitignore             # Proteção de credenciais

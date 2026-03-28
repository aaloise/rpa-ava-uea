# Usa a imagem oficial do Playwright preparada para Python
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Define o diretório de trabalho
WORKDIR /app

# Instala o serviço de cron no Linux do container
RUN apt-get update && apt-get install -y cron

# Copia o arquivo de requisitos e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código do projeto para dentro do container
COPY . .

# Cria o arquivo de log para o cron
RUN touch /var/log/cron.log

# Configura o crontab dentro do container usando o caminho absoluto do Python
# (Exemplo: Bot 1 às 02h00, Bot 2 às 03h00 e Bot 3 às 04h00 todos os dias)
RUN echo "0 2 * * * root /usr/local/bin/python /app/bot_1_salas.py >> /var/log/cron.log 2>&1" >> /etc/crontab
RUN echo "0 3 * * * root /usr/local/bin/python /app/bot_2_matriculas.py >> /var/log/cron.log 2>&1" >> /etc/crontab
RUN echo "0 4 * * * root /usr/local/bin/python /app/bot_3_auditor.py >> /var/log/cron.log 2>&1" >> /etc/crontab

# Inicia o serviço do cron no background e lê o log para manter o container rodando
CMD cron && tail -f /var/log/cron.log
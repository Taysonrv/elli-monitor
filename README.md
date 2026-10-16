# Elli Monitor

Painel local para @dicasdaellishop, feito em Python sem dependências externas. Abra esta pasta no VS Code e execute `python app.py` no terminal. Acesse http://127.0.0.1:8765. Requer Python 3.10 ou superior.

## Estado da primeira versão

O painel e o envio pelo Telegram estão implementados. Os conectores automáticos de Metricool e TikTok Shop ainda não estão implementados. A instalação do Metricool no chat não fornece credenciais ao programa local. Nenhum número fictício é carregado. Não publica posts nem altera pedidos.

Você pode importar dados reais no formato de import.example.json pelo painel. Substitua todos os exemplos antes de importar. Também pode salvar um arquivo inbox.json nesta pasta: o monitor verifica esse arquivo a cada 30 segundos, importa e remove após sucesso. Essa entrada permite conectar um coletor externo no futuro. Escreva primeiro um arquivo temporário e renomeie para inbox.json para evitar leituras incompletas.

IDs estáveis por origem evitam contar novamente o mesmo registro. Cada importação mescla os registros; não apaga históricos. Registros de Metricool representam totais acumulados por publicação. Registros shop representam pedidos e affiliate representam conversões. Receita da loja e comissão de afiliada aparecem separadas. Valores são em BRL. Esta versão não calcula receita líquida, devoluções ou cancelamentos; importe somente eventos que deseja acompanhar. Os totais cobrem todos os registros importados, sem filtro de período.

## Telegram

1. No Telegram, converse com https://t.me/BotFather e use /newbot para criar seu bot.
2. Copie config.example.json como config.json. Insira o token em telegram_token somente nesse arquivo local, nunca no chat ou em repositórios.
3. Abra a conversa com o seu novo bot e envie /start.
4. Descubra o ID da conversa pelo método oficial getUpdates (https://core.telegram.org/bots/api#getupdates). Use o campo message.chat.id da SUA conversa. Não compartilhe a URL que contém o token.
5. Preencha telegram_chat_id e mude telegram_enabled para true. Também pode usar as variáveis TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.
6. No painel, clique em Testar Telegram. O envio requer internet e uma conversa iniciada com o bot.

Novos registros de pedidos ou conversões geram alertas no painel e entram na fila do Telegram. Habilitar Telegram envia os alertas pendentes, inclusive de importações anteriores. Falhas mantêm a fila para nova tentativa. Uma interrupção após o envio e antes de salvar pode duplicar uma mensagem. Não há garantia de entrega exatamente uma vez.

O bot só monitora enquanto `python app.py` está executando e o computador está ligado. Não há serviço em nuvem ou inicialização automática configurados. O servidor aceita apenas conexões locais e não deve ser exposto à internet. Não contém autenticação para hospedagem pública.

## Próxima integração

Para métricas automáticas, precisamos verificar o acesso à API do Metricool da sua conta e implementar o coletor com os endpoints e permissões reais. Para pedidos e comissões, precisamos das autorizações adequadas no TikTok Shop Partner Center (vendedor e criador são acessos diferentes). O painel distingue dados importados de conexão automática.

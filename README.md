# 🚀 Bot de IA para Instagram da SkyPaper (100% na Nuvem)

Este projeto resolve exatamente as limitações do ManyChat Free:
- ✅ **Comentários em TODOS os Posts e Reels:** Envia mensagem privada no Direct (DM) e resposta pública de forma automática para quem comentar em **qualquer** publicação.
- ✅ **Atendimento Inteligente no Direct (DM):** Conecta a IA do **Google Gemini** para responder dúvidas de clientes e lojistas em linguagem natural com a persona da SkyPaper.
- ✅ **100% Gratuito na Nuvem:** Roda continuamente em plano gratuito (Render.com, Railway ou Cloud Run) sem limite de contatos ou cobranças por inscrito.

---

## 📁 Estrutura do Código

- [app.py](file:///home/antigravity/skypaper-instagram-bot/app.py): Servidor FastAPI com os Webhooks oficiais da Meta (`GET /webhook` e `POST /webhook`).
- [gemini_agent.py](file:///home/antigravity/skypaper-instagram-bot/gemini_agent.py): Agente de IA com o prompt da Sofia (persona da SkyPaper) e integração com a API do Gemini.
- [meta_client.py](file:///home/antigravity/skypaper-instagram-bot/meta_client.py): Integração com os endpoints oficiais da Meta Graph API (DMs privadas, comentários e respostas públicas).
- [config.py](file:///home/antigravity/skypaper-instagram-bot/config.py): Carregamento das variáveis de ambiente.
- [Dockerfile](file:///home/antigravity/skypaper-instagram-bot/Dockerfile) & [render.yaml](file:///home/antigravity/skypaper-instagram-bot/render.yaml): Configurações prontas para deploy com 1 clique na nuvem.

---

## 🛠️ Passo a Passo de Configuração

### 1. Obter a Chave do Google Gemini (Gratuito)
1. Acesse **[Google AI Studio](https://aistudio.google.com)**.
2. Clique em **Get API Key** ➔ **Create API Key**.
3. Guarde sua chave (`AIzaSy...`).

---

### 2. Configurar o App no Meta for Developers
1. Acesse **[developers.facebook.com](https://developers.facebook.com/)** e faça login com a conta do Facebook que administra a página da SkyPaper.
2. Clique em **Meus Aplicativos** ➔ **Criar Aplicativo**.
3. Escolha o tipo de aplicativo **Outro** (ou **Empresa** / *Business*).
4. No painel do app, adicione o produto **API do Instagram Graph** e **Webhooks**.
5. No menu lateral do Instagram Graph API, gere o **Token de Acesso do Usuário/Página** com as permissões:
   - `instagram_basic`
   - `instagram_manage_messages`
   - `instagram_manage_comments`
   - `pages_show_list`
   - `pages_read_engagement`
6. Guarde o **Token de Acesso** e o **ID da conta do Instagram**.

---

### 3. Subir o Servidor 100% na Nuvem (Render.com - Gratuito)
1. Crie uma conta gratuita no **[Render.com](https://render.com)**.
2. Suba essa pasta em um repositório no seu GitHub.
3. No painel do Render, clique em **New +** ➔ **Web Service**.
4. Conecte o repositório do GitHub.
5. Em **Environment Variables**, adicione:
   - `META_VERIFY_TOKEN`: `skypaper_verify_secret_123` (ou qualquer senha que preferir).
   - `META_PAGE_ACCESS_TOKEN`: *(O Token de Acesso gerado na Meta)*.
   - `INSTAGRAM_ACCOUNT_ID`: *(O ID da conta do Instagram da SkyPaper)*.
   - `GEMINI_API_KEY`: *(Sua chave do Google AI Studio)*.
   - `GEMINI_MODEL`: `gemini-2.5-flash`.
6. Clique em **Create Web Service**. Em 1 minuto ele estará no ar com uma URL HTTPS (ex: `https://skypaper-bot.onrender.com`).

---

### 4. Conectar o Webhook no Meta for Developers
1. No painel do Meta for Developers, vá em **Webhooks** ➔ Selecione o objeto **Instagram**.
2. Clique em **Editar URL de Retorno de Chamada** (*Callback URL*):
   - **URL de Retorno:** `https://sua-url-do-render.onrender.com/webhook`
   - **Token de Verificação:** `skypaper_verify_secret_123` (o mesmo definido no `.env`).
3. Clique em **Verificar e Salvar**.
4. Em **Campos de Assinatura**, ative:
   - `messages` (para receber as DMs).
   - `comments` (para receber comentários de todos os posts e Reels).

Pronto! O bot responderá em tempo real a todos os posts e a todas as mensagens diretas no Instagram da SkyPaper.

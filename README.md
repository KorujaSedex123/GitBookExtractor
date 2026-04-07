# 📚 GitBook Codex Extractor

Um exportador profissional de linha de comando (CLI) que transforma projetos do GitBook em um **Aplicativo Web Offline (HTML único)**. 

Criado originalmente para manuais de RPG de mesa, este script consome a API oficial do GitBook e gera uma documentação linda, responsiva, com busca instantânea e pronta para ser exportada como um livro PDF.

## ✨ Funcionalidades Principais

* **Modo Offline Absoluto:** Todo o seu livro (incluindo estilos) é compilado em um único arquivo `.html`. Leve seu Codex para qualquer lugar sem precisar de internet.
* **UI/UX Premium:** Interface construída com Tailwind CSS, incluindo efeito *Glassmorphism*, fontes otimizadas (Inter) e leitura imersiva.
* **Modo Escuro Nativo (Dark Mode):** Alternância instantânea de tema (claro/escuro) que salva a preferência do usuário.
* **Mobile-First:** Navegação em celulares perfeita com menu hambúrguer, overlay e fechamento automático.
* **Busca Inteligente:** Pesquise regras, monstros ou termos e veja o menu e o conteúdo se filtrarem em tempo real.
* **Mini-TOC Flutuante:** Para telas grandes, um índice lateral inteligente rastreia a rolagem da página e mostra os subtítulos do capítulo atual.
* **Exportação para PDF Inteligente:** Abra o arquivo gerado, aperte `Ctrl + P` (Imprimir) e a página se transformará magicamente em um livro: o menu some, uma capa é gerada dinamicamente e os capítulos ganham quebras de página automáticas.
* **CLI Interativa:** Menu visual no terminal (graças à biblioteca *Rich*), com barras de progresso animadas e resiliência contra bloqueios da API (Error 429).

## 🚀 Como Instalar

1. Clone este repositório para a sua máquina:
   ```bash
   git clone https://github.com/KorujaSedex123/GitBookExtractor.git
   cd codex-extractor

2. Instale as dependências necessárias utilizando o arquivo requirements.txt:
   ```Bash
    pip install -r requirements.txt

## ⚙️ Configuração (Token da API)
Para que o script consiga ler os seus projetos privados, você precisa de um Personal Access Token do GitBook.

1. Acesse o seu GitBook.
2. Clique na sua foto de perfil (canto inferior esquerdo) > **Developer Settings** > **Personal Access Tokens.**

3. Clique em Create new token e copie o código gerado (`gb_api_...`).

4. Na pasta principal do projeto, crie um arquivo chamado `.env`.

5. Cole o seu token dentro do `.env` da seguinte forma:

   ```Bash 
        GITBOOK_TOKEN=gb_api_seu_token_aqui_12345
## 🎮 Como Usar
Com as bibliotecas instaladas e o `.env` configurado, basta rodar o script principal:
        
           python extrator_api.py
          

O painel interativo vai listar todas as suas organizações e espaços. Digite o número do projeto desejado e o robô fará o resto! Ao final, um arquivo como `nome_do_projeto_codex.html` será criado na pasta.

## 🖨️ Exportando para PDF
Para transformar o HTML gerado em um livro digital perfeito:

1. Abra o arquivo .html em qualquer navegador moderno (Chrome, Edge, Brave).
2. Pressione Ctrl + P (ou clique em Imprimir).
3. Selecione o destino como "Salvar como PDF".
4. Em Mais Configurações, marque a opção "Gráficos de segundo plano" para preservar as cores das caixas de dica e alertas.
import os
import requests
import markdown
import re
import time
from datetime import datetime
from dotenv import load_dotenv

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

console = Console()

def fetch_com_resiliencia(url, headers, max_tentativas=4):
    for tentativa in range(max_tentativas):
        res = requests.get(url, headers=headers)
        if res.status_code == 429:
            tempo_espera = int(res.headers.get('Retry-After', 3))
            console.print(f"[yellow]⏳ API Limitada. Pausando por {tempo_espera}s...[/yellow]")
            time.sleep(tempo_espera)
            continue
        return res
    return None

def limpar_markdown_gitbook(texto_md):
    texto_md = re.sub(r'^---\n.*?\n---\n', '', texto_md, flags=re.DOTALL)
    texto_md = re.sub(r'^\s*#+\s+.*?$', '', texto_md, count=1, flags=re.MULTILINE)
    
    def substituir_hint(match):
        estilo = match.group(1) or "info"
        conteudo = match.group(2).strip()
        cores = {"info": "blue", "warning": "amber", "danger": "red", "success": "emerald"}
        icones = {"info": "ℹ️", "warning": "⚠️", "danger": "🚫", "success": "✅"}
        cor = cores.get(estilo, "blue")
        icone = icones.get(estilo, "💡")
        
        conteudo_html = markdown.markdown(conteudo, extensions=['extra', 'sane_lists', 'toc', 'tables'])
        
        return f"""
<div class="my-6 p-4 lg:p-5 rounded-xl border-l-8 border-{cor}-500 bg-{cor}-50/50 dark:bg-{cor}-900/30 backdrop-blur-sm text-{cor}-900 dark:text-{cor}-100 shadow-sm print-hint transition-colors">
    <div class="flex items-start">
        <span class="mr-3 lg:mr-4 text-xl lg:text-2xl">{icone}</span>
        <div class="hint-content font-medium w-full prose-sm dark:prose-invert leading-relaxed">{conteudo_html}</div>
    </div>
</div>"""

    padrao_hint = r'\{% hint style="(.*?)" %}(.*?)\{% endhint %\}'
    texto_md = re.sub(padrao_hint, substituir_hint, texto_md, flags=re.DOTALL)
    texto_md = re.sub(r'\{%[^%]*%\}', '', texto_md)
    return texto_md

def buscar_conteudo_recursivo(pages, nivel=0):
    lista_final = []
    for p in pages:
        item = {"id": p.get("id"), "title": p.get("title"), "nivel": nivel, "subpages": []}
        if 'pages' in p:
            item["subpages"] = buscar_conteudo_recursivo(p['pages'], nivel + 1)
        lista_final.append(item)
    return lista_final

def contar_total_paginas(itens):
    total = 0
    for item in itens:
        total += 1
        if item.get('subpages'):
            total += contar_total_paginas(item['subpages'])
    return total

def escolher_espaco(headers):
    console.print(Panel("[bold cyan]Conectando ao GitBook...[/bold cyan]", expand=False))
    
    r_orgs = fetch_com_resiliencia("https://api.gitbook.com/v1/orgs", headers)
    if not r_orgs or r_orgs.status_code != 200:
        console.print("[red]❌ Erro ao acessar Organizações. Verifique o Token no .env.[/red]")
        return None
        
    orgs = r_orgs.json().get('items', [])
    espacos = []
    
    with console.status("[bold green]Buscando projetos...") as status:
        for org in orgs:
            r_spaces = fetch_com_resiliencia(f"https://api.gitbook.com/v1/orgs/{org['id']}/spaces", headers)
            if r_spaces and r_spaces.status_code == 200:
                for sp in r_spaces.json().get('items', []):
                    sp['org_name'] = org.get('title', 'Sua Organização')
                    espacos.append(sp)

    if not espacos: 
        console.print("[red]❌ Nenhum projeto encontrado.[/red]")
        return None
        
    # --- NOVO MENU INTERATIVO (MOUSE E SETAS) ---
    print("\n")
    opcoes = []
    for sp in espacos:
        titulo = sp.get('title', 'Sem Nome')
        org_nome = sp.get('org_name', '')
        opcoes.append(questionary.Choice(f"📚 {titulo} (Org: {org_nome})", value=sp))
        
    opcoes.append(questionary.Choice("❌ Cancelar e Sair", value=None))

    espaco_escolhido = questionary.select(
        "Selecione o projeto que deseja exportar:",
        choices=opcoes,
        pointer="👉",
        use_indicator=True,
        style=questionary.Style([
            ('pointer', 'fg:#00ffff bold'),
            ('highlighted', 'fg:#00ffff bold'),
            ('question', 'bold'),
        ])
    ).ask()

    return espaco_escolhido

def gerar_html():
    os.system('cls' if os.name == 'nt' else 'clear')
    console.print(Panel.fit("[bold blue]Codex Extractor v2.2[/bold blue]\n[dim]Exportador Web App + Menu Interativo[/dim]", border_style="blue"))
    
    load_dotenv()
    TOKEN = os.getenv("GITBOOK_TOKEN")
    if not TOKEN: 
        console.print("[red]❌ ERRO: O arquivo .env não foi encontrado ou está vazio.[/red]")
        return
        
    HEADERS = {"Authorization": f"Bearer {TOKEN}"}
    espaco_escolhido = escolher_espaco(HEADERS)
    if not espaco_escolhido: 
        return console.print("[yellow]Extração cancelada pelo usuário.[/yellow]")
        
    SPACE_ID = espaco_escolhido['id']
    nome_projeto = espaco_escolhido.get('title', 'Codex')
    
    console.print(f"\n🚀 [bold green]Iniciando extração:[/bold green] {nome_projeto}...")
    
    r_paginas = fetch_com_resiliencia(f"https://api.gitbook.com/v1/spaces/{SPACE_ID}/content", headers=HEADERS)
    arvore = buscar_conteudo_recursivo(r_paginas.json().get('pages', []))
    total_paginas = contar_total_paginas(arvore)
    
    html_corpo = ""
    contador = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        
        task_id = progress.add_task("[cyan]Mapeando árvore...", total=total_paginas)

        def processar_tudo(itens):
            nonlocal html_corpo, contador
            resultado_sidebar = ""
            
            for item in itens:
                idx = contador
                contador += 1
                
                titulo_curto = (item['title'][:25] + '..') if len(item['title']) > 25 else item['title']
                progress.update(task_id, description=f"[cyan]Baixando: {titulo_curto}")
                
                res = fetch_com_resiliencia(f"https://api.gitbook.com/v1/spaces/{SPACE_ID}/content/page/{item['id']}?format=markdown", headers=HEADERS)
                md_puro = res.json().get("markdown", "") if res and res.status_code == 200 else ""
                
                md_limpo = limpar_markdown_gitbook(md_puro)
                
                corpo_pag = markdown.markdown(md_limpo, extensions=['extra', 'sane_lists', 'toc', 'tables'])
                
                corpo_pag = corpo_pag.replace('<table>', '<div class="overflow-x-auto my-8 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm"><table class="min-w-full m-0">')
                corpo_pag = corpo_pag.replace('</table>', '</table></div>')
                corpo_pag = corpo_pag.replace('<th>', '<th class="bg-slate-50 dark:bg-slate-800/50 p-4 font-bold text-slate-900 dark:text-white">')
                corpo_pag = corpo_pag.replace('<td>', '<td class="border-t border-slate-200 dark:border-slate-700 p-4">')

                classe_quebra = "capitulo-principal" if item['nivel'] == 0 else ""
                html_corpo += f"""
                <section id="sec_{idx}" class="mb-24 lg:mb-32 scroll-mt-24 lg:scroll-mt-20 {classe_quebra} section-content" data-title="{item['title'].lower()}">
                    <div class="mb-6 lg:mb-10">
                        <span class="inline-block px-3 py-1 bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-200 text-[10px] lg:text-xs font-bold rounded-full mb-3 lg:mb-4 uppercase tracking-widest shadow-sm border border-transparent dark:border-blue-700 transition-colors">Seção {idx+1}</span>
                        <h2 class="text-4xl lg:text-5xl font-black text-slate-900 dark:text-white tracking-tight leading-tight transition-colors">{item['title']}</h2>
                    </div>
                    <article class="prose prose-slate dark:prose-invert prose-base lg:prose-lg max-w-none prose-headings:text-slate-900 dark:prose-headings:text-white prose-strong:text-slate-900 dark:prose-strong:text-white prose-img:rounded-xl lg:prose-img:rounded-2xl prose-img:shadow-lg prose-a:text-blue-600 dark:prose-a:text-blue-400 transition-colors">
                        {corpo_pag}
                    </article>
                </section>"""

                tem_filhos = len(item['subpages']) > 0
                classe_link = "font-extrabold text-slate-800 dark:text-slate-200" if item['nivel'] == 0 else "font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400"
                
                if tem_filhos:
                    sidebar_filhos = processar_tudo(item['subpages'])
                    resultado_sidebar += f'''
                    <li class="nav-item my-1" data-title="{item["title"].lower()}">
                        <div class="flex items-center justify-between rounded-lg hover:bg-slate-200/60 dark:hover:bg-slate-800 transition-all px-3 cursor-pointer group" onclick="toggleMenu('submenu_{idx}', this)">
                            <a href="#sec_{idx}" class="block py-2 flex-1 {classe_link} action-link">{item["title"]}</a>
                            <button class="p-1 text-slate-400 dark:text-slate-500 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors">
                                <svg class="w-4 h-4 transition-transform duration-200 transform -rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"></path></svg>
                            </button>
                        </div>
                        <ul id="submenu_{idx}" class="hidden pl-4 mt-1 border-l-2 border-slate-200 dark:border-slate-700 ml-3 space-y-1 transition-colors">
                            {sidebar_filhos}
                        </ul>
                    </li>
                    '''
                else:
                    padding_extra = "pl-3" if item['nivel'] == 0 else "pl-4"
                    resultado_sidebar += f'''
                    <li class="nav-item my-1" data-title="{item["title"].lower()}">
                        <a href="#sec_{idx}" class="block py-2 {padding_extra} rounded-lg hover:bg-slate-200/60 dark:hover:bg-slate-800 transition-all {classe_link} action-link">{item["title"]}</a>
                    </li>
                    '''
                    
                progress.advance(task_id)
                    
            return resultado_sidebar

        html_sidebar = processar_tudo(arvore)

    data_atual = datetime.now().strftime("%d/%m/%Y")

    final = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>{nome_projeto} | Codex</title>
        
        <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
        <script>
            tailwind.config = {{ darkMode: 'class', }};
            function applyTheme() {{
                if (localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
                    document.documentElement.classList.add('dark');
                }} else {{ document.documentElement.classList.remove('dark'); }}
            }}
            applyTheme();
        </script>
        
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800;900&display=swap" rel="stylesheet">
        
        <style>
            html {{ scroll-behavior: smooth; }}
            body {{ font-family: 'Inter', sans-serif; }}
            .sidebar-glass {{ background: rgba(248, 250, 252, 0.95); backdrop-filter: blur(12px); }}
            .dark .sidebar-glass {{ background: rgba(15, 23, 42, 0.95); }}
            
            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: transparent; }}
            ::-webkit-scrollbar-thumb {{ background: #cbd5e1; border-radius: 10px; }}
            .dark ::-webkit-scrollbar-thumb {{ background: #475569; }}
            
            @media print {{
                html, body {{ height: auto !important; overflow: visible !important; display: block !important; background: white !important; color: black !important; }}
                aside, #mobile-header, #sidebar-overlay, #mini-toc, .theme-toggle, #dice-toast {{ display: none !important; }}
                main {{ margin-left: 0 !important; width: 100% !important; padding: 0 !important; }}
                .capa-pdf {{ display: flex !important; flex-direction: column; justify-content: center; align-items: center; height: 100vh; page-break-after: always; }}
                .titulo-tela {{ display: none !important; }}
                .capitulo-principal {{ page-break-before: always; break-before: page; padding-top: 40px; }}
                section {{ page-break-inside: avoid; break-inside: auto; }}
                h2, h3, h4 {{ page-break-after: avoid; }}
                .print-hint {{ border-left-width: 4px !important; border-left-style: solid !important; border-color: #cbd5e1 !important; }}
                .overflow-x-auto {{ overflow: visible !important; border: none !important; box-shadow: none !important; }}
            }}
            @media screen {{ .capa-pdf {{ display: none !important; }} }}
        </style>
    </head>
    <body class="flex flex-col lg:flex-row h-screen overflow-hidden bg-[#fdfdfd] dark:bg-slate-900 transition-colors duration-300">
        
        <header id="mobile-header" class="lg:hidden flex items-center justify-between bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 p-4 z-40 shadow-sm shrink-0 transition-colors">
            <h1 class="text-xl font-black text-slate-900 dark:text-white tracking-tighter uppercase truncate pr-4">{nome_projeto}</h1>
            <div class="flex items-center gap-2">
                <button onclick="toggleTheme()" class="theme-toggle p-2 text-slate-600 dark:text-slate-300 focus:outline-none bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center w-10 h-10 transition-colors">
                    <span class="block dark:hidden text-lg">🌙</span>
                    <span class="hidden dark:block text-lg">☀️</span>
                </button>
                <button id="menu-toggle" class="p-2 text-slate-600 dark:text-slate-300 focus:outline-none bg-slate-100 dark:bg-slate-800 rounded-lg flex items-center justify-center w-10 h-10 transition-colors">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
                </button>
            </div>
        </header>

        <div id="sidebar-overlay" class="fixed inset-0 bg-slate-900/60 dark:bg-black/60 z-40 hidden transition-opacity lg:hidden backdrop-blur-sm"></div>

        <aside id="sidebar" class="w-80 sidebar-glass border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0 z-50 fixed inset-y-0 left-0 transform -translate-x-full transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0 shadow-2xl lg:shadow-none">
            <div class="p-6 lg:p-8 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center transition-colors">
                <div>
                    <h1 class="text-2xl lg:text-3xl font-black text-slate-900 dark:text-white tracking-tighter uppercase">{nome_projeto}</h1>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="toggleTheme()" class="theme-toggle hidden lg:flex items-center justify-center w-10 h-10 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-full transition-colors">
                        <span class="block dark:hidden text-lg">🌙</span>
                        <span class="hidden dark:block text-lg">☀️</span>
                    </button>
                    <button id="close-sidebar" class="lg:hidden p-2 text-slate-500 dark:text-slate-400 bg-slate-200/50 dark:bg-slate-800 rounded-full transition-colors">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                </div>
            </div>
            <div class="px-6 pt-6 pb-2 relative">
                <input type="text" id="search" placeholder="Pesquisar..." class="w-full px-4 py-3 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 dark:text-white shadow-sm outline-none transition-all">
            </div>
            <nav class="flex-1 overflow-y-auto p-4 scrollbar-hide">
                <ul id="nav-list" class="space-y-1">{html_sidebar}</ul>
            </nav>
        </aside>
        
        <main id="main-content" class="flex-1 overflow-y-auto relative bg-transparent">
            
            <div id="mini-toc" class="hidden xl:block fixed right-8 top-32 w-64 bg-slate-50/80 dark:bg-slate-800/80 backdrop-blur-md p-6 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm z-30 transition-opacity duration-300 opacity-0">
                <h4 class="text-xs font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-4">Nesta Página</h4>
                <div id="mini-toc-links" class="space-y-2 max-h-[60vh] overflow-y-auto scrollbar-hide"></div>
            </div>

            <div id="dice-toast" class="fixed bottom-8 left-1/2 transform -translate-x-1/2 bg-slate-900 dark:bg-slate-800 text-white px-6 py-4 rounded-2xl shadow-2xl z-50 flex items-center gap-4 transition-all duration-300 translate-y-24 opacity-0 pointer-events-none font-mono font-bold border border-slate-700 dark:border-slate-600">
                <span class="text-3xl animate-bounce">🎲</span>
                <span id="dice-result" class="text-lg"></span>
            </div>

            <div class="capa-pdf">
                <h1 class="text-6xl font-black text-gray-900 mb-4 text-center">{nome_projeto}</h1>
                <p class="text-2xl text-gray-500 font-semibold tracking-widest uppercase">Codex de Sobrevivência</p>
                <p class="text-md text-gray-400 mt-16 font-mono">Gerado em: {data_atual}</p>
            </div>
            <div class="max-w-4xl mx-auto px-6 py-10 lg:px-12 xl:pr-32 lg:py-20">
                <div class="titulo-tela mb-12 lg:mb-16 pb-6 lg:pb-8 border-b border-gray-200 dark:border-slate-800 transition-colors">
                    <h1 class="text-4xl lg:text-5xl font-black text-gray-900 dark:text-white tracking-tight transition-colors">{nome_projeto}</h1>
                </div>
                {html_corpo}
            </div>
        </main>

        <script>
            function rollDice(qtd, faces, sinal, mod) {{
                let total = 0;
                let rolagens = [];
                for(let i=0; i<qtd; i++) {{
                    let r = Math.floor(Math.random() * faces) + 1;
                    rolagens.push(r);
                    total += r;
                }}
                let mathStr = "";
                if(mod && sinal) {{
                    if(sinal === '+') total += parseInt(mod);
                    else total -= parseInt(mod);
                    mathStr = ` ${{sinal}} ${{mod}}`;
                }}
                
                const toast = document.getElementById('dice-toast');
                const resText = document.getElementById('dice-result');
                resText.innerHTML = `<span class="text-slate-400 text-sm block mb-1">[${{rolagens.join(', ')}}]${{mathStr}}</span> <span class="text-blue-400 font-black text-3xl block">= ${{total}}</span>`;
                
                toast.classList.remove('translate-y-24', 'opacity-0');
                
                if(window.diceTimeout) clearTimeout(window.diceTimeout);
                window.diceTimeout = setTimeout(() => {{
                    toast.classList.add('translate-y-24', 'opacity-0');
                }}, 4000);
            }}

            document.addEventListener('DOMContentLoaded', () => {{
                const proseElements = document.querySelectorAll('.prose');
                const diceRegex = /\\b(\\d+)d(\\d+)(?:\\s*([+-])\\s*(\\d+))?\\b/gi;

                proseElements.forEach(container => {{
                    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
                    const textNodes = [];
                    let node;
                    while(node = walker.nextNode()) {{
                        const pNode = node.parentNode.tagName;
                        if(pNode !== 'SCRIPT' && pNode !== 'STYLE' && pNode !== 'BUTTON' && pNode !== 'CODE' && pNode !== 'A' && pNode !== 'H1' && pNode !== 'H2' && pNode !== 'H3' && pNode !== 'TH') {{
                            textNodes.push(node);
                        }}
                    }}

                    textNodes.forEach(textNode => {{
                        if(diceRegex.test(textNode.nodeValue)) {{
                            const span = document.createElement('span');
                            span.innerHTML = textNode.nodeValue.replace(diceRegex, `<button class="font-mono font-bold text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-900/60 px-2 py-0.5 rounded shadow-sm border border-blue-200 dark:border-blue-800 hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors cursor-pointer active:scale-95 mx-1" onclick="rollDice('$1', '$2', '$3', '$4')">$&</button>`);
                            textNode.parentNode.replaceChild(span, textNode);
                        }}
                    }});
                }});
            }});

            function toggleTheme() {{
                if (document.documentElement.classList.contains('dark')) {{
                    document.documentElement.classList.remove('dark');
                    localStorage.setItem('theme', 'light');
                }} else {{
                    document.documentElement.classList.add('dark');
                    localStorage.setItem('theme', 'dark');
                }}
            }}

            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            
            document.getElementById('menu-toggle').addEventListener('click', () => {{
                sidebar.classList.remove('-translate-x-full');
                overlay.classList.remove('hidden');
            }});
            
            function closeSidebar() {{
                sidebar.classList.add('-translate-x-full');
                overlay.classList.add('hidden');
            }}
            
            document.getElementById('close-sidebar').addEventListener('click', closeSidebar);
            overlay.addEventListener('click', closeSidebar);

            document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
                anchor.addEventListener('click', function (e) {{
                    const targetId = this.getAttribute('href').substring(1);
                    if (!targetId) return;
                    const targetElement = document.getElementById(targetId);
                    if (targetElement) {{
                        e.preventDefault();
                        const mainContainer = document.getElementById('main-content');
                        const topPos = targetElement.getBoundingClientRect().top + mainContainer.scrollTop - mainContainer.getBoundingClientRect().top - 40;
                        mainContainer.scrollTo({{ top: topPos, behavior: 'smooth' }});
                        history.pushState(null, null, '#' + targetId);
                        if(window.innerWidth < 1024) closeSidebar();
                    }}
                }});
            }});

            function toggleMenu(id, el) {{
                const submenu = document.getElementById(id);
                if(!submenu) return;
                submenu.classList.toggle('hidden');
                const icon = el.querySelector('svg');
                if(submenu.classList.contains('hidden')) icon.classList.add('-rotate-90');
                else icon.classList.remove('-rotate-90');
            }}

            document.getElementById('search').addEventListener('input', function(e) {{
                const term = e.target.value.toLowerCase();
                const items = document.querySelectorAll('.nav-item');
                const sections = document.querySelectorAll('.section-content');
                
                items.forEach((item) => {{
                    const title = item.getAttribute('data-title');
                    if(!title) return;
                    if (term === '') {{
                        item.style.display = '';
                    }} else {{
                        const hasMatchingChild = Array.from(item.querySelectorAll('.nav-item')).some(child => child.getAttribute('data-title').includes(term));
                        if (title.includes(term) || hasMatchingChild) {{
                            item.style.display = '';
                            const submenu = item.querySelector('ul');
                            if(submenu) {{
                                submenu.classList.remove('hidden');
                                const icon = item.querySelector('svg');
                                if(icon) icon.classList.remove('-rotate-90');
                            }}
                        }} else {{ item.style.display = 'none'; }}
                    }}
                }});
                
                sections.forEach((sec) => {{
                    const secTitle = sec.getAttribute('data-title') || '';
                    sec.style.display = secTitle.includes(term) || term === '' ? 'block' : 'none';
                }});
            }});

            const tocContainer = document.getElementById('mini-toc-links');
            const miniTocBox = document.getElementById('mini-toc');
            const sections = document.querySelectorAll('.section-content');
            
            const observer = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) buildToc(entry.target);
                }});
            }}, {{ root: document.getElementById('main-content'), rootMargin: '-10% 0px -70% 0px' }});

            sections.forEach(sec => observer.observe(sec));

            function buildToc(section) {{
                tocContainer.innerHTML = '';
                const headings = section.querySelectorAll('article h2, article h3');
                if (headings.length === 0) {{
                    miniTocBox.style.opacity = '0';
                    return;
                }}
                miniTocBox.style.opacity = '1';
                headings.forEach(h => {{
                    if (!h.id) h.id = h.textContent.toLowerCase().replace(/[^a-z0-9]+/g, '-');
                    const link = document.createElement('a');
                    link.href = '#' + h.id;
                    link.textContent = h.textContent;
                    if (h.tagName === 'H2') {{
                        link.className = 'block text-sm font-semibold text-slate-800 dark:text-slate-200 hover:text-blue-600 dark:hover:text-blue-400 transition-colors truncate';
                    }} else {{
                        link.className = 'block text-xs text-slate-500 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-300 pl-4 transition-colors truncate';
                    }}
                    tocContainer.appendChild(link);
                }});
            }}
        </script>
    </body>
    </html>
    """
    
    pasta_saida = "exportacoes"
    if not os.path.exists(pasta_saida):
        os.makedirs(pasta_saida)
        
    nome_arquivo = f"{nome_projeto.replace(' ', '_').lower()}_codex.html"
    arquivo_saida = os.path.join(pasta_saida, nome_arquivo)
    
    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        f.write(final)
        
    console.print(Panel(f"[bold green]✅ Sucesso![/bold green]\nO manual [bold white]{nome_projeto}[/bold white] foi salvo na pasta:\n[cyan]{arquivo_saida}[/cyan]", border_style="green"))

if __name__ == "__main__":
    gerar_html()
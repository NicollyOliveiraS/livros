from flask import Flask, render_template, request
import requests
from deep_translator import GoogleTranslator

app = Flask(__name__)

# Configuração do Tradutor para Português
translator = GoogleTranslator(source='auto', target='pt')

def buscar_livro_openlibrary(nome):
    url = "https://openlibrary.org/search.json"
    
    # Primeira tentativa: busca exata com filtro de idioma português
    params = {
        "q": f'"{nome}"',  # Aspas para busca exata
        "language": "por",
        "fields": "key,title,author_name,subject,cover_i,first_publish_year",
        "limit": 10  # Pegamos mais resultados para filtrar
    }
    
    try:
        # Primeira tentativa: busca exata
        res = requests.get(url, params=params, timeout=10).json()
        
        livro = None
        docs = res.get("docs", [])
        
        # Se encontrou resultados, procura o mais relevante
        if docs:
            # Função para calcular relevância
            def calcular_relevancia(doc, termo_busca):
                titulo = doc.get("title", "").lower()
                termo = termo_busca.lower()
                pontuacao = 0
                
                # Pontuação por correspondência exata
                if titulo == termo:
                    pontuacao += 100
                elif titulo.startswith(termo):
                    pontuacao += 50
                elif termo in titulo:
                    pontuacao += 30
                
                # Prefere livros com capa
                if doc.get("cover_i"):
                    pontuacao += 10
                
                # Prefere livros com assunto definido
                if doc.get("subject"):
                    pontuacao += 5
                    
                return pontuacao
            
            # Ordena por relevância
            docs_ordenados = sorted(docs, 
                                   key=lambda x: calcular_relevancia(x, nome), 
                                   reverse=True)
            
            livro = docs_ordenados[0]
            
            # Busca os detalhes do livro específico
            chave_livro = livro.get("key")
            if chave_livro:
                detalhes_url = f"https://openlibrary.org{chave_livro}.json"
                res_detalhes = requests.get(detalhes_url, timeout=10).json()
                
                # Tratamento da descrição
                raw_desc = res_detalhes.get("description", "Sinopse não disponível para este título.")
                if isinstance(raw_desc, dict):
                    texto_original = raw_desc.get("value", "")
                else:
                    texto_original = raw_desc

                # Tradução para Português
                try:
                    if texto_original and len(texto_original) > 10:
                        descricao_pt = translator.translate(texto_original[:4000])
                    else:
                        descricao_pt = "Sinopse não disponível para este título."
                except Exception as e:
                    print(f"Erro na tradução: {e}")
                    descricao_pt = texto_original if texto_original else "Sinopse não disponível para este título."

                return {
                    "titulo": livro.get("title"),
                    "autor": ", ".join(livro.get("author_name", ["Desconhecido"])),
                    "assunto": livro.get("subject", [None])[0] if livro.get("subject") else None,
                    "descricao": descricao_pt,
                    "capa": f"https://covers.openlibrary.org/b/id/{livro.get('cover_i')}-L.jpg" if livro.get("cover_i") else None
                }
        
        # Segunda tentativa: se não encontrou com busca exata, tenta busca mais ampla
        params_amplo = {
            "q": nome,
            "language": "por",
            "limit": 5
        }
        
        res_amplo = requests.get(url, params=params_amplo, timeout=10).json()
        docs_amplo = res_amplo.get("docs", [])
        
        if docs_amplo:
            livro = docs_amplo[0]
            chave_livro = livro.get("key")
            
            if chave_livro:
                detalhes_url = f"https://openlibrary.org{chave_livro}.json"
                res_detalhes = requests.get(detalhes_url, timeout=10).json()
                
                raw_desc = res_detalhes.get("description", "Sinopse não disponível para este título.")
                if isinstance(raw_desc, dict):
                    texto_original = raw_desc.get("value", "")
                else:
                    texto_original = raw_desc

                try:
                    if texto_original and len(texto_original) > 10:
                        descricao_pt = translator.translate(texto_original[:4000])
                    else:
                        descricao_pt = "Sinopse não disponível para este título."
                except:
                    descricao_pt = texto_original if texto_original else "Sinopse não disponível para este título."

                return {
                    "titulo": livro.get("title"),
                    "autor": ", ".join(livro.get("author_name", ["Desconhecido"])),
                    "assunto": livro.get("subject", [None])[0] if livro.get("subject") else None,
                    "descricao": descricao_pt,
                    "capa": f"https://covers.openlibrary.org/b/id/{livro.get('cover_i')}-L.jpg" if livro.get("cover_i") else None
                }
                
    except Exception as e:
        print(f"Erro na busca: {e}")
    
    return None

def buscar_semelhantes_openlibrary(assunto, titulo_atual=None):
    if not assunto:
        return []
    
    # Remove caracteres especiais e formata o assunto
    import re
    assunto_clean = re.sub(r'[^\w\s]', '', assunto)
    assunto_url = assunto_clean.lower().strip().replace(' ', '_')
    
    semelhantes = []
    
    try:
        # Tenta buscar pelo assunto
        url = f"https://openlibrary.org/subjects/{assunto_url}.json"
        res = requests.get(url, params={"limit": 8}, timeout=10).json()
        
        for livro in res.get("works", []):
            # Evita duplicar o livro principal
            if titulo_atual and livro.get("title") == titulo_atual:
                continue
                
            # Pega informações dos autores
            autores = []
            for autor in livro.get("authors", []):
                if isinstance(autor, dict) and "name" in autor:
                    autores.append(autor["name"])
            
            semelhantes.append({
                "titulo": livro.get("title"),
                "autor": ", ".join(autores) if autores else "Autor desconhecido",
                "capa": f"https://covers.openlibrary.org/b/id/{livro.get('cover_id')}-M.jpg" if livro.get("cover_id") else None
            })
        
        # Se não encontrou pelo assunto, busca por título similar
        if not semelhantes and titulo_atual:
            url_search = "https://openlibrary.org/search.json"
            params = {
                "q": titulo_atual,
                "language": "por",
                "limit": 6
            }
            
            res_search = requests.get(url_search, params=params, timeout=10).json()
            
            for livro in res_search.get("docs", [])[:5]:
                if livro.get("title") != titulo_atual:
                    semelhantes.append({
                        "titulo": livro.get("title"),
                        "autor": ", ".join(livro.get("author_name", ["Desconhecido"])),
                        "capa": f"https://covers.openlibrary.org/b/id/{livro.get('cover_i')}-M.jpg" if livro.get("cover_i") else None
                    })
        
        # Remove duplicatas mantendo a ordem
        seen = set()
        semelhantes_unicos = []
        for livro in semelhantes:
            if livro["titulo"] not in seen:
                seen.add(livro["titulo"])
                semelhantes_unicos.append(livro)
        
        return semelhantes_unicos[:5]  # Retorna no máximo 6 livros
        
    except Exception as e:
        print(f"Erro ao buscar semelhantes: {e}")
        return []

@app.route("/", methods=["GET", "POST"])
def index():
    livro_principal = None
    semelhantes = []
    
    # Lista de sugestões rápidas em português
    sugestoes = [
        "Dom Casmurro", 
        "1984", 
        "A Hora da Estrela", 
        "O Hobbit",
        "Memórias Póstumas de Brás Cubas"
    ]

    if request.method == "POST":
        nome = request.form.get("livro")
        if nome and nome.strip():
            nome = nome.strip()
            print(f"Buscando por: {nome}")  # Log para debug
            livro_principal = buscar_livro_openlibrary(nome)
            
            # Se encontrou o livro, busca os semelhantes
            if livro_principal:
                print(f"Livro encontrado: {livro_principal['titulo']}")
                semelhantes = buscar_semelhantes_openlibrary(
                    livro_principal["assunto"], 
                    livro_principal["titulo"]
                )
            else:
                print("Nenhum livro encontrado")

    return render_template("index.html", 
                           livro_principal=livro_principal,
                           semelhantes=semelhantes,
                           sugestoes=sugestoes)


# ========== HANDLERS DE ERRO ==========
@app.errorhandler(404)
def pagina_nao_encontrada(error):
    """Handler para erro 404 - Página não encontrada"""
    sugestoes = [
        "Dom Casmurro", 
        "1984", 
        "A Hora da Estrela", 
        "O Hobbit",
        "Memórias Póstumas de Brás Cubas"
    ]
    return render_template('404.html', sugestoes=sugestoes), 404

@app.errorhandler(500)
def erro_interno_servidor(error):
    """Handler para erro 500 - Erro interno do servidor"""
    sugestoes = [
        "Dom Casmurro", 
        "1984", 
        "A Hora da Estrela", 
        "O Hobbit",
        "Memórias Póstumas de Brás Cubas"
    ]
    return render_template('500.html', sugestoes=sugestoes), 500

if __name__ == "__main__":
    app.run(debug=True)
import csv
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple
import requests

IBGE_MUNICIPIOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
CACHE_IBGE = "ibge_municipios_cache.json"
RESULTADO_CSV = "resultado.csv"
#ACCESS_TOKEN = "SEU_TOKEN_AQUI"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6ImR0TG03UVh1SkZPVDJwZEciLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL215bnhsdWJ5a3lsbmNpbnR0Z2d1LnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiIxNGU3ZDI4Yy04OTQwLTQ2OTktOTk2Ny1kNzYxNjU3YTdmZDMiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzY4NTEyNDUzLCJpYXQiOjE3Njg1MDg4NTMsImVtYWlsIjoiY2FpYW5xbUBnbWFpbC5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsIjoiY2FpYW5xbUBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwibm9tZSI6IkNhaWFuIFF1aXJpbm8gZGUgTW9yYWlzIiwicGhvbmVfdmVyaWZpZWQiOmZhbHNlLCJzdWIiOiIxNGU3ZDI4Yy04OTQwLTQ2OTktOTk2Ny1kNzYxNjU3YTdmZDMifSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc2ODUwODg1M31dLCJzZXNzaW9uX2lkIjoiNzA4YjdjYjItMWMwYy00MWQ2LTkxNTEtM2QzMWI0N2QxNGUwIiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.NSsoIb8H1EtU_P3oSjQG5fhO7ta40OKjhZG-V2MDbI8"

FUNCTION_URL = "https://mynxlubykylncinttggu.functions.supabase.co/ibge-submit"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im15bnhsdWJ5a3lsbmNpbnR0Z2d1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjUxODg2NzAsImV4cCI6MjA4MDc2NDY3MH0.Z-zqiD6_tjnF2WLU167z7jT5NzZaG72dWH0dpQW1N-Y"

# classe para guardar os dados do IBGE
@dataclass
class MunicipioIBGE:
    id_ibge: int
    nome: str
    uf_sigla: str
    regiao: str


# remove acentuação, pontuação e caracteres especiais, deixa tudo minusculo
def padronizar_nomes_municipios(nome: str) -> str:
    nome = nome.strip().lower()
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(ch for ch in nome if not unicodedata.combining(ch))
    nome = re.sub(r"[^a-z0-9\s]", " ", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome


# função para ler e retornar os dados de input.csv
def ler_input_csv(path: str) -> List[Tuple[str, int]]:
    # inicia uma lista, abre e le input.csv
    linhas = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, linha in enumerate(reader, start=2):
            # para cada linha de input.csv:
            # - pega municipio como string
            # - pega populacao como int
            # - guarda numa tupla
            municipio = (linha.get("municipio") or "").strip()

            populacao = (linha.get("populacao") or "").strip()
            populacao_int = int(populacao)

            linhas.append((municipio, populacao_int))

    return linhas


# FUNÇÃO QUE BUSCA OS MUNICIPIOS DA LISTA DO IBGE
# OBS: ESSA FUNÇÃO GUARDA OS MUNICIPIOS EM UM "CACHE" EM JSON PARA EVITAR CARREGAR OS MUNICIPIOS TODA VEZ QUE RODAR
def busca_lista_ibge(cache: str = CACHE_IBGE) -> List[MunicipioIBGE]:
    # se o cache existir, le o cache e retorna os dados
    if os.path.exists(cache):
        with open(cache, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [MunicipioIBGE(**item) for item in data]

    resp = requests.get(IBGE_MUNICIPIOS_URL)
    resp.raise_for_status()
    items = resp.json()

    municipios: List[MunicipioIBGE] = []
    # para cada item na lista do IBGE pega:
    # id, nome, uf do estado e região
    # salva na lista estruturada com a classe criada e retorna
    for item in items:
        mid = int(item["id"])
        nome = item["nome"]

        uf_sigla = ""
        regiao = ""

        #existem MICROREGIOES OU MESOREIGOES que estão nulas na API do IBGE
        # se esse for o caso o codigo nao tenta indexar, evitando que quebre
        microrregiao = item.get("microrregiao")
        if isinstance(microrregiao, dict):
            mesorregiao = microrregiao.get("mesorregiao")
            if isinstance(mesorregiao, dict):
                uf = mesorregiao.get("UF")
                if isinstance(uf, dict):
                    uf_sigla = uf.get("sigla") or ""
                    regiao = (uf.get("regiao") or {}).get("nome") or ""

        municipios.append(MunicipioIBGE(id_ibge=mid, nome=nome, uf_sigla=uf_sigla, regiao=regiao))

    # with open(cache, "w", encoding="utf-8") as f:
    #     json.dump([m.__dict__ for m in municipios], f, ensure_ascii=False, indent=2)

    return municipios


# função para criar um índice de busca para matching de municipios
def indice_busca(municipios: List[MunicipioIBGE]) -> Dict[str, List[MunicipioIBGE]]:
    indice = {}
    for municipio in municipios:
        key = padronizar_nomes_municipios(municipio.nome)
        indice.setdefault(key, []).append(municipio)
    return indice


# função com a lógica de matching de municipios por igualdade ou por similiaridade
# tendo em vista que em input.csv temos municipios escrito errado, eu optei por usar o fuzzy

def match_municipio(
    name: str,
    indice: Dict[str, List[MunicipioIBGE]],
    lista_municipios: List[MunicipioIBGE],
    pontuacao_referencia=0.85
):
    nome_municipio = padronizar_nomes_municipios(name)

    # tenta achar o municipio que bate exatamente com algum do IBGE usando o indice de busca
    if nome_municipio in indice:
        candidatos = indice[nome_municipio]

        #no caso de Santo Andre, a preferência é em SP
        if nome_municipio == "santo andre":
            for c in candidatos:
                if c.uf_sigla == "SP":
                    return c, "OK"

        completos = [c for c in candidatos if c.uf_sigla and c.regiao]
        return (completos[0] if completos else candidatos[0]), "OK"

    # fuzzy para pegar o municipio da lista do IGBE que o nome se parece com o nome correto
    parecidos: Optional[MunicipioIBGE] = None
    pontuacao = 0.0

    # para cada municipio
    for municipio in lista_municipios:
        # calcula o quanto o nome do municipio se parece com um da lista de municipios
        similaridade = SequenceMatcher(None, nome_municipio, padronizar_nomes_municipios(municipio.nome)).ratio()
        if similaridade > pontuacao:
            # guarda o municipio com a maior pontuação de similaridade na lista de resultado
            pontuacao = similaridade
            parecidos = municipio

    # se a similaridade for menor que 85% nao considera ele parecido o suficiente
    if parecidos is None or pontuacao < pontuacao_referencia:
        return None, "NAO_ENCONTRADO"
    return parecidos, "OK"


#função que pega os resultados para salvar num csv
def resultado_csv(linhas: List[Dict[str, object]], path: str = RESULTADO_CSV) -> None:
    campos = ["municipio_input", "populacao_input", "municipio_ibge", "uf", "regiao", "id_ibge", "status"]
    with open(path, "w", encoding="utf-8", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        for linha in linhas:
            writer.writerow(linha)

# função que calcula as metricas passadas no desafio 
def calcula_estatistica(linhas: List[Dict[str, object]]) -> Dict[str, object]:
    
    total_municipios = len(linhas)
    total_ok = sum(1 for r in linhas if r["status"] == "OK") #municipio que foi identificado
    total_nao_encontrado = sum(1 for r in linhas if r["status"] == "NAO_ENCONTRADO") # municipio nao identificado
    total_erro_api = sum(1 for r in linhas if r["status"] == "ERRO_API") # linhas que deram erro na consulta
    pop_total_ok = sum(int(r["populacao_input"]) for r in linhas if r["status"] == "OK") # soma da populacao

    # calcula a media por regiao
    soma_por_regiao: Dict[str, int] = {}
    contagem_por_regiao: Dict[str, int] = {}

    for linha in linhas:
        if linha["status"] == "OK":
            # pega a regiao, soma a população atual com a populacao da regiao
            regiao = str(linha["regiao"])
            if not regiao:
                continue
            soma_por_regiao[regiao] = soma_por_regiao.get(regiao, 0) + int(linha["populacao_input"])
            contagem_por_regiao[regiao] = contagem_por_regiao.get(regiao, 0) + 1

    # calcula a media por regiao
    medias_por_regiao: Dict[str, float] = {}
    for regiao, soma in soma_por_regiao.items():
        medias_por_regiao[regiao] = round(soma / contagem_por_regiao[regiao], 2)

    return {
        "total_municipios": total_municipios,
        "total_ok": total_ok,
        "total_nao_encontrado": total_nao_encontrado,
        "total_erro_api": total_erro_api,
        "pop_total_ok": pop_total_ok,
        "medias_por_regiao": medias_por_regiao,
    }

# função que envia as estatisticas para o supabase com meu ACCESS_TOKEN
def envia_stats(access_token: str, stats: Dict[str, object]) -> Dict[str, object]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": API_KEY,
        "Content-Type": "application/json",
    }
    data = {"stats": stats}

    resp = requests.post(FUNCTION_URL, headers=headers, json=data, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"POST falhou: HTTP {resp.status_code} - {resp.text}")
    return resp.json()


def main() -> int:
    access_token = ACCESS_TOKEN.strip()
    input_csv = "input.csv"

    # carrega os dados do input.csv e do IBGE e cria indice de busca para achar os municipios na lista do IBGE
    input_rows = ler_input_csv(input_csv)
    municipios = busca_lista_ibge()
    idx = indice_busca(municipios)

    linhas_saida: List[Dict[str, object]] = []
    for municipio_input, populacao in input_rows:
        # para cada municipio do input.csv busca o match
        match, status = match_municipio(municipio_input, idx, municipios)
        # se deu match acrescenta o municipio na saida com os dados do IBGE inclusos
        if status == "OK" and match is not None:
            linhas_saida.append({
                "municipio_input": municipio_input,
                "populacao_input": populacao,
                "municipio_ibge": match.nome,
                "uf": match.uf_sigla,
                "regiao": match.regiao,
                "id_ibge": match.id_ibge,
                "status": "OK",
            })
        # senao coloca os dados do input.csv sem os dados do IBGE
        else:
            linhas_saida.append({
                "municipio_input": municipio_input,
                "populacao_input": populacao,
                "municipio_ibge": "",
                "uf": "",
                "regiao": "",
                "id_ibge": "",
                "status": status,
            })

    # escreve o resultado.csv com os dados tratados
    resultado_csv(linhas_saida, RESULTADO_CSV)
    print(f"Arquivo gerado: {RESULTADO_CSV}")

    # calcula e da print nas estatisticas
    stats = calcula_estatistica(linhas_saida)
    print("Stats calculadas:")
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    # envia oara o SUPABASE
    resp = envia_stats(access_token=access_token, stats=stats)
    print("\nResposta da correção:")
    print(f"Score: {resp.get('score')}")
    print(f"Feedback: {resp.get('feedback')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

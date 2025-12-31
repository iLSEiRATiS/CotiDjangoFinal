import requests
from bs4 import BeautifulSoup


def comparar_precios(nombre: str) -> str:
    url = "https://www.cotodigital3.com.ar/sitios/coto/"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except requests.RequestException:
        return f"No se pudo obtener información en este momento para {nombre}."

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.string.strip() if soup.title else "Cotidigital"
    return f"Comparar precios de {nombre}: simulación de scraping en {title}"

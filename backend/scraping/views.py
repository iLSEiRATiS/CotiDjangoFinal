from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from .utils import comparar_precios


class CompararPrecios(APIView):
    permission_classes = [AllowAny]

    def get(self, request, nombre: str):
        resultado = comparar_precios(nombre)
        return Response({"resultado": resultado, "nombre": nombre})

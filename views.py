# These views are not required for traversal. Instead,
# are sample views used by the included test application,
# yamluser, to illustrate how traversal can be used
# rest framework is not required to use traversal,
# however it is needed to run the example application.

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class Rest(APIView):
    def get(self, request, node, *args, **kwargs):
        print kwargs
        if hasattr(node, "qs"):
            serializer = node.serializer(node.qs, many=True)
        else:
            serializer = node.serializer(node.model)
        return Response(serializer.data)

    def post(self, request, node, *args, **kwargs):
        serializer = node.serializer(data=request.DATA)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        pass

    def put(self, request, node, *args, **kwargs):
        serializer = node.serializer(node.model, data=request.DATA)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

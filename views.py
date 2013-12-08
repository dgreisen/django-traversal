# These views are not required for traversal. Instead,
# are sample views used by the included test application,
# yamluser, to illustrate how traversal can be used
# rest framework is not required to use traversal,
# however it is needed to run the example application.

from django.views.generic import View
from django.http import HttpResponse
from django.contrib.auth.models import User, Group


class Users(View):
    def get(self, request, models, variables, *args, **kwargs):
        serializer = UserSerializer(models["users"], many=True)
        return HttpResponse(serializer.data)

    def put(self, request, models, variables, *args, **kwargs):
        pass
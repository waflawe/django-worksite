from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated


class IsApplicant(BasePermission):
    message = "Вы не соискатель."

    def has_permission(self, request, view):
        if request.user.first_name == "":
            return True
        return False


class IsCompany(BasePermission):
    message = "Вы не компания."

    def has_permission(self, request, view):
        return request.user.first_name != ""


class IsAuthenticatedCompanyOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return IsAuthenticated().has_permission(request, view) and IsCompany().has_permission(request, view)

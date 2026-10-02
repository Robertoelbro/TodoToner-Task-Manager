from accounts.views import not_found


class FriendlyNotFoundMiddleware:
    """Evita páginas técnicas 404 incluso con DEBUG en desarrollo local."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 404:
            return not_found(request)
        return response

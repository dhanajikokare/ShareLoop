from django.http import HttpResponse

class CorsMiddleware:
    """
    Lightweight CORS middleware enabling mobile client communication 
    with the Django REST API without altering existing web views.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'OPTIONS' and request.path.startswith('/api/'):
            response = HttpResponse(status=200)
            response['Content-Length'] = '0'
        else:
            response = self.get_response(request)

        if request.path.startswith('/api/') or request.path.startswith('/media/'):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, Accept, Origin'
            response['Access-Control-Allow-Credentials'] = 'true'

        return response

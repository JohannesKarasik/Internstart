class RedirectLoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code in (301, 302):
            print(f"🔁 Redirect {request.path} → {response.get('Location')}")
        return response

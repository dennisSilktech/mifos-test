from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """
    Wraps DRF's default error response in a consistent envelope:
        {"error": {"code": "...", "message": "...", "detail": ...}}
    """
    response = exception_handler(exc, context)
    if response is None:
        return response

    code = getattr(exc, "default_code", exc.__class__.__name__.upper())
    message = str(getattr(exc, "detail", response.data))

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "detail": response.data,
        }
    }
    return response

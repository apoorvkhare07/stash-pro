from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        detail = response.data.get('detail', response.data)
        if isinstance(detail, list):
            detail = detail[0] if detail else str(exc)
        elif isinstance(detail, dict):
            first_key = next(iter(detail), None)
            if first_key:
                val = detail[first_key]
                detail = val[0] if isinstance(val, list) else str(val)
            else:
                detail = str(exc)

        response.data = {
            'error': str(detail),
            'code': response.status_code,
        }

    return response


from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import ErrorDetail
from rest_framework.utils.serializer_helpers import ReturnList

class CustomResponseRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        status_code = renderer_context["response"].status_code
        print("inside the custom renders")

        if isinstance(data, ReturnList):
            # Handle ReturnList (list-like object) differently, if needed
            return super().render(data, accepted_media_type, renderer_context)

        if isinstance(data.get("detail"), ErrorDetail) and (
            data.get("detail") == "Token authentication failed."
        ):
            status_code = 401
            renderer_context["response"].status_code = 401
            data[
                "details"
            ] = "Please send correct user or admin token to access the API endpoints"
            data["message"] = "Token authentication Failed"
        elif isinstance(data.get("detail"), ErrorDetail):
            renderer_context["response"].status_code = status_code
            data["message"] = data["detail"]

        if str(status_code) == "401":
            status_message = "Unauthorized"
        elif 400 <= status_code < 500:
            status_message = "Client Error"
        elif 500 <= status_code < 600:
            status_message = "Server Error"
        else:
            status_message = "Success"

        try:
            response = {
                "session": {
                    "refresh": data.get("access", None),
                    "token": data.get("token", None),
                    "validity": 1,
                    "specialMessage": None,
                },
                "data": data.get("data", None),
                "total_count": data.get("total_count", None),
                "details": data.get("details", None),
                "status": {
                    "code": status_code,
                    "status": status_message,
                    "message": data.get("message", None),
                },
            }
        except AttributeError:
            response = data

        return super(CustomResponseRenderer, self).render(
            response, accepted_media_type, renderer_context
        )


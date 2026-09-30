from django.views.generic import TemplateView


class AppView(TemplateView):
    """Serves the single-page web UI; routing happens client-side."""
    template_name = 'web/index.html'

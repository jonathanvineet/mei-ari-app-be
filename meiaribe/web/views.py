from pathlib import Path

from django.views.generic import TemplateView

STATIC_DIR = Path(__file__).resolve().parent / 'static' / 'web'


class AppView(TemplateView):
    """Serves the single-page web UI; routing happens client-side."""
    template_name = 'web/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Changes whenever app.js / app.css change, so browsers never run a stale copy
        context['asset_version'] = int(max((STATIC_DIR / name).stat().st_mtime for name in ('app.js', 'app.css')))
        return context

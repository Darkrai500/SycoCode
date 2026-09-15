from django import template
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt
register = template.Library()
# Never execute embedded HTML or request remote images from model output.
renderer = MarkdownIt("commonmark", {"html": False}).disable(["image", "link", "autolink"])
renderer.enable("table")
renderer.renderer.rules["table_open"] = lambda tokens, idx, options, env: '<div class="table-wrap"><table>\n'
renderer.renderer.rules["table_close"] = lambda tokens, idx, options, env: '</table></div>\n'

@register.filter
def prose(value):
    return mark_safe(renderer.render(str(value)))

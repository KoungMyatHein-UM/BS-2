

LEFT_BAR_FEATURE_TEMPLATE = """
{% for name, meta in features.items() %}
<div class="feature" onclick="runFeature('{{ name }}')">
    {{ meta.display_name }} {{ meta.version }}
</div>
{% endfor %}
"""


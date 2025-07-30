

LEFT_BAR_FEATURE_TEMPLATE = """
{% for name, version in features.items() %}
<div class="feature" onclick="invokeFeature('{{ name }}')">{{ name }} {{ version }}</div>
{% endfor %}
"""




LEFT_BAR_FEATURE_TEMPLATE = """
{% for feature in features %}
<div class="feature" onclick="invokeFeature('{{ feature.name }}')">{{ feature.name }} {{ feature.version }}</div>
{% endfor %}
"""


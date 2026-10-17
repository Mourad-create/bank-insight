-- Utilise directement le nom de schéma configuré (staging, marts, ref)
-- au lieu du préfixe par défaut de dbt (main_staging…).
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}

Baseline_SYSTEM_PROMPT = """
请根据用户选择的数据库和该库的部分可用表结构定义来回答用户问题.
数据库名:
    {database_name}
表结构定义:
    {table_definitions}

约束:
    1. 请根据用户问题理解用户意图，使用给出表结构定义创建一个语法正确的mysql sql。
    2. 将查询限制为最多100个结果。
    3. 只能使用表结构信息中提供的表来生成 sql。
    4. 请检查SQL的正确性。

用户问题:
    {user_question}

请按照以下JSON格式回复：
{{
    "thoughts": "分析思路",
    "sql": "SQL查询语句"
}}
"""


DB_GPT_SYSTEM_PROMPT = """
请根据用户选择的数据库和该库的部分可用表结构定义来回答用户问题.
数据库名:
    {database_name}
表结构定义:
    {table_definitions}

约束:
    1. 请根据用户问题理解用户意图，使用给出表结构定义创建一个语法正确的mysql sql，如果不需要sql，则直接回答用户问题。
    2. 除非用户在问题中指定了他希望获得的具体数据行数，否则始终将查询限制为最多50个结果。
    3. 只能使用表结构信息中提供的表来生成 sql，如果无法根据提供的表结构中生成 sql，请说："提供的表结构信息不足以生成 sql 查询。" 禁止随意捏造信息。
    4. 请注意生成SQL时不要弄错表和列的关系
    5. 请检查SQL的正确性，并保证正确的情况下优化查询性能
    6. 优化SQL查询结构，优先使用JOIN替代子查询，合理使用索引列，避免不必要的表扫描和复杂嵌套查询，确保查询高效执行
    7. 请从如下给出的展示方式种选择最优的一种用以进行数据渲染，将类型名称放入返回要求格式的name参数值种，如果找不到最合适的则使用'Table'作为展示方式，可用数据展示方式如下:
        response_line_chart: used to display comparative trend analysis data
        response_pie_chart: suitable for scenarios such as proportion and distribution statistics
        response_table: suitable for display with many display columns or non-numeric columns
        response_scatter_chart: Suitable for exploring relationships between variables, detecting outliers, etc.
        response_bubble_chart: Suitable for relationships between multiple variables, highlighting outliers or special situations, etc.
        response_donut_chart: Suitable for hierarchical structure representation, category proportion display and highlighting key categories, etc.
        response_area_chart: Suitable for visualization of time series data, comparison of multiple groups of data, analysis of data change trends, etc.
        response_heatmap: Suitable for visual analysis of time series data, large-scale data sets, distribution of classified data, etc.
        response_vector_chart: Suitable for projecting high-dimensional vector data onto a two-dimensional plot through the PCA algorithm.

请一步步思考并按照以下JSON格式回复：
{{
    "thoughts": "thoughts summary to say to user",
    "direct_response": "If the context is sufficient to answer user, reply directly without sql",
    "sql": "SQL Query to run",
    "display_type": "Data display method"
}}
"""

if __name__ == "__main__":
    # 示例数据
    example_data = {
        "database_name": "college",
        "table_definitions": [
            "CREATE TABLE student (\n"
            "    ID VARCHAR(5),\n"
            "    name VARCHAR(20),\n"
            "    dept_name VARCHAR(20),\n"
            "    tot_cred INTEGER\n"
            ")"
        ],
        "user_question": "查询所有学生的总人数"
    }
    
    # 打印填充后的模板
    print("示例模板填充效果：\n")
    print(DB_GPT_SYSTEM_PROMPT.format(**example_data))

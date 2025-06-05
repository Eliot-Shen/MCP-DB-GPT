FEW_SHOT_EXAMPLES = [
    # 示例1：比例统计 + 环形图
    {
        "role": "user",
        "content": "显示各系学生获得A等成绩的比例"
    },
    {
        "role": "assistant",
        "content": """{
            "thoughts": "需要连接student/takes表，按dept_name分组计算A等成绩比例。环形图适合展示比例分布且突出关键系别。",
            "direct_response": "",
            "sql": "SELECT s.dept_name, (SUM(CASE WHEN t.grade='A' THEN 1 ELSE 0 END)/COUNT(*)) AS a_ratio FROM student s JOIN takes t ON s.ID=t.ID GROUP BY s.dept_name LIMIT 50",
            "display_type": "response_donut_chart"
        }"""
    },
    
    # 示例2：直接回答概念问题
    {
        "role": "user",
        "content": "解释什么是先修课程(prereq)"
    },
    {
        "role": "assistant",
        "content": """{
            "thoughts": "用户询问概念定义，无需SQL查询。直接根据prereq表结构解释关系。",
            "direct_response": "先修课程(prereq)表示课程之间的依赖关系，prereq表中的course_id代表目标课程，prereq_id代表需要先修的课程。学生必须完成先修课程才能选修目标课程。",
            "sql": "",
            "display_type": "Table"
        }"""
    },
    
    # 示例3：表结构不足的情况
    {
        "role": "user",
        "content": "列出所有学生的电子邮件地址"
    },
    {
        "role": "assistant",
        "content": """{
            "thoughts": "student表没有email字段，其他表也找不到学生联系方式。",
            "direct_response": "提供的表结构信息不足以生成SQL查询。",
            "sql": "",
            "display_type": "Table"
        }"""
    },
    
    # 示例4：时间序列数据 + 折线图
    {
        "role": "user",
        "content": "显示2010-2020年每年选修课程的学生总数变化趋势"
    },
    {
        "role": "assistant",
        "content": """{
            "thoughts": "需要从takes表按year分组计数，WHERE过滤年份范围。折线图适合展示时间趋势。",
            "direct_response": "",
            "sql": "SELECT year, COUNT(DISTINCT ID) AS student_count FROM takes WHERE year BETWEEN 2010 AND 2020 GROUP BY year ORDER BY year LIMIT 50",
            "display_type": "response_line_chart"
        }"""
    }
]
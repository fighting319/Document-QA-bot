"""Question type classification."""

BASIC_QUERY_KEYWORDS = [
    "什么时候", "在哪里", "谁", "哪些", "如何定义", "是什么",
    "怎么说", "什么是", "在哪", "多少钱", "什么时间",
    "地点", "位置", "规则", "要求", "条件", "步骤",
]

STATISTICAL_QUERY_KEYWORDS = [
    "多少个", "多少种", "多少名", "多少人", "多少项", "多少届",
    "共有几", "总共有", "一共有", "有几个", "有多少",
    "统计", "数量", "比例", "百分比", "排名", "最多", "最少", "比较",
]

OPEN_QUERY_KEYWORDS = [
    "如何", "怎么", "建议", "方法", "策略", "技巧", "经验",
    "准备", "应对", "提高", "增强", "评价", "看法", "观点",
    "为什么", "原因", "好处", "优势", "缺点", "影响", "未来", "趋势",
]

# 分类问题
def classify_question(question: str) -> str:
    for keyword in STATISTICAL_QUERY_KEYWORDS:
        if keyword in question:
            return "statistical"

    for keyword in BASIC_QUERY_KEYWORDS:
        if keyword in question:
            return "basic"

    for keyword in OPEN_QUERY_KEYWORDS:
        if keyword in question:
            return "open"

    return "basic"

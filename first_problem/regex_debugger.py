import re
import logging


class RegexDebugger:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)

    def test_pattern(self, text, patterns):
        """
        测试多个正则模式
        """
        results = {}
        for name, pattern in patterns.items():
            try:
                matches = re.findall(pattern, text, re.DOTALL)
                results[name] = {
                    'matches': matches,
                    'count': len(matches)
                }
            except Exception as e:
                self.logger.error(f"模式 {name} 匹配失败: {e}")

        return results

    def analyze_pattern_performance(self, text, pattern):
        """
        分析正则表达式性能
        """
        import timeit

        def match_function():
            re.findall(pattern, text)

        execution_time = timeit.timeit(match_function, number=100)

        return {
            'average_time': execution_time / 100,
            'complexity': self._calculate_regex_complexity(pattern)
        }

    def _calculate_regex_complexity(self, pattern):
        """
        计算正则表达式复杂度
        """
        complexity_score = 0
        complexity_map = {
            r'\d': 1,  # 数字
            r'\w': 1,  # 单词字符
            r'.*': 2,  # 任意字符
            r'.+': 3,  # 至少一个字符
            r'\s': 1,  # 空白
            r'[^]': 2,  # 取反
            r'()': 2,  # 分组
        }

        for key, value in complexity_map.items():
            if key in pattern:
                complexity_score += value

        return complexity_score


# 使用示例
# debugger = RegexDebugger()
#
# text = "第七届全国青少年人工智能创新挑战赛"
# patterns = {
#     '赛事名称': r'(.*?挑战赛)',
#     '届数': r'第(\d+)届',
#     '主题': r'(青少年.*?)赛'
# }
#
# results = debugger.test_pattern(text, patterns)
# print(results)
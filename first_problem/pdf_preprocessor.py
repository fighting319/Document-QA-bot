import pdfplumber
import re
import logging
import unicodedata

class PDFPreprocessor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def clean_extracted_text(self, text):
        """
        改进的文本清洁处理方法
        1. 删除多余空白和换行
        2. 去除特殊符号和控制字符
        3. 规范化标点和空白
        4. 处理Unicode异常字符
        """
        # 删除控制字符和特殊Unicode字符
        text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C')

        # 规范化空白和换行
        text = re.sub(r'\s+', ' ', text)

        # 去除特殊符号和标记字符
        text = re.sub(r'[•·\u200b\u200c\u200d\u2060\ufeff\x00-\x1f\x7f-\x9f]', '', text)

        # 规范化中英文标点，将英文字符替换为中文字符
        translations = str.maketrans({
            ':': '：',
            ',': '，',
            '.': '。',
            '!': '！',
            '?': '？',
            ';': '；',
            '(': '（',
            ')': '）'
        })
        text = text.translate(translations)

        return text.strip()

    def extract_text_with_layout(self):
        """
        保留文档布局的文本提取
        """
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                full_text = []
                for page in pdf.pages:
                    # 提取文本并保留基本布局
                    page_text = page.extract_text(
                        x_tolerance=3,  # 水平容错
                        y_tolerance=3,  # 垂直容错
                        keep_blank_chars=True  # 保留空白字符
                    )
                    full_text.append(page_text)

                return '\n'.join(full_text)
        except Exception as e:
            self.logger.error(f"提取文本时发生错误: {e}")
            return ""

    def detect_text_encoding(self):
        """
        检测PDF文本编码
        """
        encodings = ['utf-8', 'gbk', 'gb2312', 'big5']
        for encoding in encodings:
            try:
                with open(self.pdf_path, 'rb') as f:
                    f.read().decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue
        return 'utf-8'  # 默认编码


def advanced_pdf_text_extraction(pdf_path):
    """
    高级PDF文本提取流程
    """
    preprocessor = PDFPreprocessor(pdf_path)

    # 提取文本
    raw_text = preprocessor.extract_text_with_layout()

    # 清洁文本
    clean_text = preprocessor.clean_extracted_text(raw_text)

    return clean_text


# 使用示例
# pdf_path = '../data/03_2024年（第12届）“泰迪杯”数据挖掘挑战赛竞赛通知.pdf'
# extracted_text = advanced_pdf_text_extraction(pdf_path)
# print(extracted_text)
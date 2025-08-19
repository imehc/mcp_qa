# 对比问题1中统计的两组主题词，找出两组共有的词语以及各自特有的词语。
# 输出格式要求：以英文冒号和英文逗号分隔，词语与标点之间不留空格，各词语之间用逗号分隔，最后一个词后不留逗号。
# 输出示例（词语为例子，非答案）：
# 共有词语：改革,…(略),深化
# 2019特有：企业,…(略),加强
# 2018特有：效益,…(略),创新

# ......

# d = {}

# ......

# lt = list(d.items())
# lt.sort(key = lambda x:x[1],reverse = True)

# ......

#######################################################################################################################################
import jieba


def print_result(year):
    fa = open("./demo/66data{}.txt".format(year), "r")
    txt = fa.read()  # 读取文件内容
    fa.close()  # 关闭文件
    # 使用jieba分词，将文本内容切分为词语
    words = jieba.lcut(txt)
    # 统计词语出现次数，长度为1的词语忽略
    d = {}
    for word in words:
        if len(word) == 1:
            continue
        else:
            d[word] = d.get(word, 0) + 1  # 如果词语已存在字典中，计数加1；否则初始化为1
    lt = list(d.items())
    lt.sort(key=lambda x: x[1], reverse=True)
    # 输出前10个词语及其出现次数
    print("{}:".format(year), end="")
    for i in range(10):
        word, count = lt[i]
        if i < 9:
            print("{}:{}".format(word, count), end=",")
        else:
            print("{}:{}".format(word, count))


print_result(2019)
print_result(2018)

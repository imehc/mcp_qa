# 考生文件夹下的 data.txt 文件包含技术信息资料的内容

# 请修改编辑器中的代码，完成以下功能：

# 使用 jieba 库对 data.txt 文件进行分词。
# 将长度大于等于3个字符的关键词写入文件 out1.txt，每行一个关键词，关键词不得重复，输出顺序不做要求。

# 输出文件示例（out1.txt 内容）：
# 人工智能
# 科幻小说
# 机器学习

# f = open('out1.txt','w')

# ... #此处可用多行

# f.close()

#######################################################################################################################################

import jieba

f = open("./demo/72八十天环游地球.txt")

chapters = []
current_chapter = None
current_content = []

for line in f:
    if line.startswith("第") and "章" in line:  # 假设章节题目形如"第一章"、"第二章"
        if current_chapter:
            chapters.append((current_chapter, "".join(current_content)))
        current_chapter = line.strip()
        current_content = []
    else:
        current_content.append(line.strip())

if current_chapter:
    chapters.append((current_chapter, "".join(current_content)))

f.close()


def get_most_frequent_word(text):
    words = jieba.lcut(text)
    filtered_words = [word for word in words if len(word) > 1]
    word_freq = {}
    for word in filtered_words:
        if word in word_freq:
            word_freq[word] += 1
        else:
            word_freq[word] = 1
    # 找到最高频的词语
    most_common_word, count = max(word_freq.items(), key=lambda x: x[1])
    return most_common_word, word_freq[most_common_word]


for chapter, content in chapters:
    most_common_word, freq = get_most_frequent_word(content)
    print(f"{chapter} {most_common_word} {freq}")

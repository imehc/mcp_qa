# 请修改编辑器中的代码，完成以下功能：使用 turtle 库的 turtle.fd() 函数和 turtle.seth() 函数绘制一个边长为200像素的正菱形，菱形的四个内角均为90度，效果如图所示。

# import turtle
# turtle.pensize(2)
# d = ____(1)____
# for i in range(4):
#     turtle.seth(d)
#     d  += ____(2)____
#     turtle.fd(____(3)____)

#######################################################################################################################################

import jieba

s = input("请输入一段中文文本，句子之间以逗号或句号分隔：")

slist = jieba.lcut(s)
m = 0

word_list = []

for i in slist:
    if i in "，。":
        continue
    m += 1
    word_list.append("{}/".format(i))


print("".join(word_list), end="\n")
print("\n中文词语数是：{}\n".format(m))

slice = s.replace("，", "。").split("。")
for i in slice:
    print("{:^20}".format(i))


# import jieba

# s = input("请输入一段中文文本，句子之间以逗号或句号分隔：")
# # 精确模式分词
# slist = jieba.cut(s)
# # 初始化数值m和列表s，m用于统计词数，s用于连接词语
# m = 0
# word_list = []
# for i in slist:
#     if i in "，。":
#         continue
#     # 累加m，将元素i添加到列表s里
#     m += 1
#     word_list.append(i)
# # 将列表以斜杠连接为字符串输出。
# print("/".join(word_list) + "/")


# print("\n中文词语数是：{}\n".format(m))
# # 将逗号替换为句号后，按句号分割为列表。
# # 0为基础数据，2为填充数据（这里用空格），1为总长度（基础数据+填充数据）。^表示居中
# senses = s.replace("，", "。").split("。")
# for i in senses:
#     print("{:^20}".format(i, " "))

# 请修改编辑器中的代码，完成以下功能：

# 键盘输入一组高校所对应的学校类型，以空格分隔，共一行。
# 程序统计各类型的数量，并按数量从多到少的顺序输出每种类型及对应数量，每个类型占一行，格式为“类型: 数量”，其中冒号为英文字符。
# 输入示例：
# 综合 理工 综合 综合 综合 师范 理工

# 输出示例：
# 综合: 4
# 理工: 2
# 师范: 1

# txt = input("请输入类型序列: ")
# ...
# d = {}
# ...
# ls = list(d.items())
# ls.sort(key=lambda x:x[1], reverse=True)  # 按照数量排序
# for k in ls:
#     print("{}:{}".format(k[0], k[1]))

#######################################################################################################################################

import turtle as t
import random as r

r.seed(1)
t.pensize(2)
for i in range(3):
    lenth = r.randint(20, 80)
    x0 = r.randint(-100, 100)
    y0 = r.randint(-100, 100)

    t.penup()
    t.goto(x0, y0)
    t.pendown()
    for j in range(4):
        t.fd(lenth)
        t.seth(90 * (j + 1))
t.done()
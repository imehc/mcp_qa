# 请修改编辑器中的代码，完成以下功能：利用 random 库和 turtle 库，在屏幕上绘制5个圆圈。圆圈的半径和圆心的坐标由 randint() 函数产生，圆心的 X 和 Y 坐标范围在 [-100,100] 之间，半径大小范围在 [20,50] 之间。圆圈的颜色从 color 列表中随机选择。

# import random as r
# color = ['red','orange','blue','green','purple']
# r.seed(1)
# for i in range(5):
#     rad = r.____________
#     x0 = r.____________
#     y0 = r.randint(-100,100)
#     t.color(r.choice(color))
#     t.penup()
#     t.____________
#     t.pendown()
#     t.____________(rad)
# t.done()

#######################################################################################################################################å

data = input()
d = {}

while data:
    t = data.split()
    if len(t) == 2:
        d[t[0]] = t[1]
    data = input()

ls = list(d.items())
ls.sort(key=lambda x: x[1], reverse=True)
s1, g1 = ls[0]
s2, g2 = ls[len(ls) - 1]
a = 0
for i in d.values():
    a = a + int(i)
a = a / len(ls)

print("最高分课程是{} {}, 最低分课程是{} {}, 平均分是{:.2f}".format(s1, g1, s2, g2, a))

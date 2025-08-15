# 请修改编辑器中的代码，完成以下功能：根据列表 Ls 中的数据，使用 turtle 库绘制柱状图，并将图形显示在屏幕上。
# 数据列表示例：
# Ls = [69, 292, 33, 131, 61, 254]

# ____________
# ls = [69, 292, 33, 131, 61, 254]
# X_len = 400
# Y_len = 300
# x0 = -200
# y0 = -100

# t.penup()
# t.goto(x0, y0)
# t.pendown()

# t.fd(X_len)
# t.fd(-X_len)
# t.seth(____________)
# t.fd(Y_len)

# t.pencolor('red')
# t.pensize(5)
# for i in range(len(ls)):
#     t.____________
#     t.goto(x0 + (i+1)*50, ____________)
#     t.seth(90)
#     t.pendown()
#     t.fd(____________)
# t.done()

#######################################################################################################################################

import turtle as t
import random as r

color = ["red", "blue", "purple", "black"]
r.seed(1)
for j in range(4):
    t.pencolor(color[r.randint(0, 3)])
    t.penup()
    t.goto(r.randint(-100, 100), r.randint(-100, 100))
    t.pendown()
    ra = r.randint(50, 200)
    for i in range(1, 5):
        t.fd(ra)
        t.seth(90 * i)
t.done()

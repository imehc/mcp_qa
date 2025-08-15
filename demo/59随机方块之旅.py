# 请修改编辑器中的代码，完成以下功能：利用 random 库和 turtle 库，在屏幕上绘制3个黑色的正方形。正方形的左下角坐标和边长由 randint() 函数产生，具体参数在代码中给出。

# import turtle as t
# import random as r
# r.seed(1)
# t.pensize(2)
# for i in range(3):
#     length = r.____________(20,80)
#     x0 = r.randint(-100, 100)
#     y0 = r.randint(-100, 100)

#     t.penup()
#     t.goto(____________)
#     t.____________
#     for j in range(4):
#         t.____________(length)
#         t.____________(90*(j+1))
# t.done()

#######################################################################################################################################
import random as r
import turtle as t

color = ["red", "green", "blue", "purple", "black"]
r.seed(1)
for j in range(5):
    t.pencolor(color[r.randint(0, 4)])
    t.penup()
    t.goto(r.randint(-100, 100), r.randint(-100, 100))
    t.pendown()
    t.circle(r.randint(10, 30))
t.done()

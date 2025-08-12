# 请修改编辑器中的代码，完成以下功能：利用 random 库和 turtle 库，在屏幕上绘制4个小雪花。雪花的中心点坐标由列表 points 给出，雪花的半径长度由 randint() 函数产生，雪花的颜色为红色。

# 坐标示例：
# points = [(0, 0), (50, 50), (-50, -50), (100, -100)]

# import turtle as t
# import random as r

# r.seed(1)
# t.pensize(2)
# t.____________('red')
# angles = 6
# points= [[0,0],[50,40],[70,80],[-40,30]]

# for i in range(____________):
#     x0,y0 = points[i]
#     t.penup()
#     t.goto(____________)
#     t.pendown()

#     length = r.randint(6, 16)
#     for j in range(angles):
#         t.____________(length)
#         t.____________(length)
#         t.right(360 / angles)
# t.done()


#######################################################################################################################################

ls = [111, 222, 333, 444, 555, 666, 777, 888, 999]
lt = [999, 777, 555, 333, 111, 888, 666, 444, 222]
s = 0
for i in range(len(ls)):
    s += ls[i] * lt[i]
print(s)

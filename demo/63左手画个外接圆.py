# 请修改编辑器中的代码，完成以下功能：使用 turtle 库的 turtle.fd() 函数和 turtle.left() 函数绘制一个边长为200像素的正方形，并在正方形的四个顶点处绘制一个紧挨正方形的圆形。
# import turtle
# turtle.pensize(2)
# for i in range(_______(1)_________):
#     turtle.fd(200)
#     turtle.left(90)
# turtle.left(_______(2)_________)
# turtle.circle(_______(3)_________*pow(2,0.5))

#######################################################################################################################################

import turtle

turtle.pensize(2)
d = 0
for i in range(1, 13):
    turtle.fd(40)
    d += 30
    turtle.seth(d)
turtle.done()
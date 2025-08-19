# 请修改编辑器中的代码，完成以下功能：使用 turtle 库的 turtle.fd() 函数和 turtle.seth() 函数绘制一个十字形，每个方向的长度为100像素
# import turtle
# for i in range(4):
#     turtle.fd(100)
#     ___(1)___(-100)
#     ___(2)___((i+1)*90)

#######################################################################################################################################

import turtle

turtle.pensize(2)
for i in range(4):
    turtle.fd(200)
    turtle.left(90)
turtle.left(-45)
turtle.circle(100 * pow(2, 0.5))

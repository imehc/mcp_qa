# 请修改编辑器中的代码，完成以下功能：使用 turtle 库的 turtle.fd() 函数和 turtle.seth() 函数绘制一个边长为100像素的正八边形。
# import turtle
# turtle.pensize(2)
# d = 0
# for i in range(1, ______(1)______):
#     ______(2)______
#     d += ______(3)______
#     turtle.seth(d)

#######################################################################################################################################

import turtle

turtle.pensize(2)
d = -45
for i in range(4):
    turtle.seth(d)
    d += 90
    turtle.fd(200)

turtle.done()

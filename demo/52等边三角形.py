# 请修改编辑器中的代码，完成以下功能：使用 turtle 库的 turtle.fd() 函数和 turtle.seth() 函数绘制一个等边三角形，边长为200像素。

# import turtle as ___(1)___
# for i in range(___(2)___):
#     ___(3)___(i*120)
#     t.fd(200)

#######################################################################################################################################


import turtle as t

ls = [69, 292, 33, 131, 61, 254]
X_len = 400
Y_len = 300
x0 = -200
y0 = -100

t.penup()
t.goto(x0, y0)
t.pendown()

t.fd(X_len)
t.fd(-X_len)
t.seth(90)
t.fd(Y_len)

t.pencolor("red")
t.pensize(5)
for i in range(len(ls)):
    t.penup()
    t.goto(x0 + (i + 1) * 50, y0)
    t.pendown()
    t.fd(ls[i])
t.done()

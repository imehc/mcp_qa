# 请修改编辑器中的代码，完成以下功能：使用 turtle 库的 turtle.fd() 函数和 turtle.seth() 函数绘制一个边长为40像素的正12边形。
# import turtle
# turtle.pensize(2)
# d=0
# for i in range(1, _______(1)_________):
#     _______(2)_________
#     d += _______(3)_________
#     turtle.seth(d)

#######################################################################################################################################

import jieba

dela = '-;:,.()"<>'
s = input("请输入一句话:")
print("\n这句话是:{}".format(s))
for i in dela:
    s = s.replace(i, "")
ls = jieba.lcut(s)
print("替换之后是:{}".format(s))
print("里面有 {}个词语。".format(len(ls)))

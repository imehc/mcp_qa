# 请修改编辑器中的代码，完成以下功能：使用 turtle 库的 turtle.fd() 函数和 turtle.seth() 函数绘制一个边长为100的正五边形。

# import turtle
# turtle.pensize(2)
# d = 0
# for i in range(1, ______(1)________):
#     ______(2)________
#     d += ______(3)________
#     turtle.seth(d)

#######################################################################################################################################

img = [0.244, 0.832, 0.903, 0.145, 0.26, 0.452]
filter = [0.1, 0.8, 0.1]
res = []

for i in range(len(img) - 2):
    k = 0
    k = 0  # 有多个和，所以每次赋初始值0
    for j in range(3):  # 求3次累计和
        k += filter[j] * img[i + j]  # 求3次累计和
        print(
            "k={:<10.3f},filter[{}]={:<10.3f},img[{}+{}]={:<10.3f}".format(
                k, j, filter[j], i, j, img[i + j]
            )
        )
    res.append(k)
for r in res:
    print("{:<10.3f}".format(r), end="")

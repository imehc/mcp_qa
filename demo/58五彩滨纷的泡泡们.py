# 请修改编辑器中的代码，完成以下功能：使用 turtle 库和 random 库，在屏幕上绘制5个彩色的圆。

# 圆的颜色从颜色列表 color 中随机选择。
# 圆的圆心坐标 (x, y) 在 [-100, 100] 范围内随机选择。
# 圆的半径在 [10, 30] 范围内随机选择。
# import turtle as t
# import random as r

# color = ['red','green','blue','purple','black']
# r.seed(1)
# for j in range(__(1)__):
#     t.pencolor(color[r. __(2)__])
#     t.penup()
#     t.goto(__(3)__)
#     t. __(4)__
#     t.circle(__(5)__)
# t.done()

#######################################################################################################################################


sumtime = 0
percls = []
ts = {}
with open("./demo/57out.txt", "r") as f:
    for line in f:
        percls.append(line.strip("\n").split(","))
    print(percls)
    n = [x[1] for x in percls]
    print(n)
    for i in range(len(n)):
        sumtime += eval(n[i])

    ts = {x[0]: x[2] for x in percls}
    print(ts)

print("the total execute time is ", sumtime)

tns = list(ts.items())
tns.sort(key=lambda x: x[1], reverse=True)
for i in range(3):
    print(
        'the top {} percentage time is {}, spent in "{}" operation'.format(
            i, tns[i][1], tns[i][0]
        )
    )

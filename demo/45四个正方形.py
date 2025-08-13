# 请修改编辑器中的代码，完成以下功能：使用 turtle 库函数绘制4个等距排列的正方形。正方形的边长为40像素，间距宽度为40，最左边正方形的左上角坐标为 (0,0)
# import turtle
# n = __(1)__
# for j in range(n):
#     turtle. __(2)__
#     for i in range(4):
#         turtle. __(3)__
#         turtle.right(__(4)__)
#     turtle.penup()
#     turtle.fd(__(5)__)
# turtle.done()

#######################################################################################################################################å

# f = open("./demo/44data.txt", "r")
# D = {}
# for line in f:
#     lines = line.strip().split(",")
#     if len(lines) == 3:
#         if lines[2] not in D:
#             D[lines[2]] = [lines[1]]
#         else:
#             D[lines[2]].append(lines[1])

# unis = D.items()

# for d in unis:
#     print('{:>4}: {:>4} : {}'.format(d[0], len(d[1]), " ".join(d[1])))


import csv

f = open("./demo/44data.txt", "r")
unis = []
L = list(csv.reader(f))
L = list(filter(None, L))
country = {}
for j in range(len(L)):
    country[L[j][2]] = country.get(L[j][2], 0) + 1

for key in country:
    ss = []
    ss.append(key)
    ss.append(country[key])
    school = ""
    for j in range(len(L)):
        if L[j][2] == key:
            school += L[j][1]
            school += " "
    ss.append(school)
    unis.append(ss)

for d in unis:
    print("{:>4}: {:>4} : {}".format(d[0], d[1], d[2]))
